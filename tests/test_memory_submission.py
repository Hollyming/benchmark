from pathlib import Path

from ultra_long_benchmark.pipelines.gharchive import DEFAULT_FIXTURE_PATH as DEFAULT_GHARCHIVE_FIXTURE_PATH
from ultra_long_benchmark.pipelines.gharchive import build_gharchive_project_fixture
from ultra_long_benchmark.pipelines.external_memory_runner import run_external_memory_submission_runner
from ultra_long_benchmark.pipelines.external_memory_runner import validate_external_memory_predictions_against_input
import ultra_long_benchmark.pipelines.memory_submission as memory_submission
from ultra_long_benchmark.pipelines.memory_submission import plan_external_memory_submission_adapter
from ultra_long_benchmark.pipelines.memory_submission import run_memory_submission_baseline
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.project_release import export_project_submission_inputs
from ultra_long_benchmark.project_release import validate_project_prediction_submission
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_jsonl


def _write_provider_config(tmp_path: Path) -> Path:
    provider_config = tmp_path / "opencode.json"
    provider_config.write_text(
        """
{
  "provider": {
    "openai": {
      "options": {"baseURL": "https://example.test/v1", "apiKey": "sk-test"},
      "models": {"gpt-5.4-mini": {"name": "GPT-5.4 Mini"}}
    }
  }
}
""",
        encoding="utf-8",
    )
    return provider_config


def test_event_profile_memory_submission_generates_no_gold_predictions(tmp_path: Path):
    summary = build_gharchive_project_fixture(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    release_dir = tmp_path / "release"
    input_dir = tmp_path / "submission_inputs"
    export_project_benchmark_release([Path(summary["project_dir"])], release_dir)
    export_project_submission_inputs(release_dir, input_dir)
    predictions_path = tmp_path / "memory_profile_predictions.jsonl"
    report_path = tmp_path / "memory_profile_report.json"

    report = run_memory_submission_baseline(
        input_dir,
        predictions_path,
        adapter="event_profile_stub",
        top_k=3,
        report_path=report_path,
        system_name="test_event_profile_stub",
    )

    assert report["status"] == "completed"
    assert report["executed"] is True
    assert report["summary"]["predictions"] == 3
    assert report["constraints"]["uses_gold_memory_graph"] is False
    assert report["constraints"]["uses_probe_expected_behavior"] is False
    assert report["constraints"]["llm_generation_performed"] is False
    rows = read_jsonl(predictions_path)
    assert len(rows) == 3
    assert all(row["prediction"] for row in rows)
    assert all(row["metadata"]["no_gold_submission_input"] is True for row in rows)
    validation = validate_project_prediction_submission(release_dir, predictions_path)
    assert validation["passed"] is True
    assert read_json(report_path)["system_name"] == "test_event_profile_stub"


def test_external_memory_submission_adapter_is_gated(tmp_path: Path):
    input_dir = tmp_path / "submission_inputs"
    input_dir.mkdir()
    (input_dir / "projects.jsonl").write_text("", encoding="utf-8")
    (input_dir / "events.jsonl").write_text("", encoding="utf-8")
    (input_dir / "probes.jsonl").write_text("", encoding="utf-8")
    (input_dir / "submission_manifest.json").write_text(
        '{"constraints":{"contains_gold_memory_graph":false,"contains_probe_expected_behavior":false}}\n',
        encoding="utf-8",
    )

    report = run_memory_submission_baseline(
        input_dir,
        tmp_path / "mem0_predictions.jsonl",
        adapter="mem0",
        report_path=tmp_path / "mem0_report.json",
    )

    assert report["status"] == "blocked_requires_external_adapter"
    assert report["executed"] is False
    assert report["constraints"]["external_dependency_invoked"] is False
    assert not (tmp_path / "mem0_predictions.jsonl").exists()


def test_openai_compatible_external_memory_adapter_generates_no_gold_predictions(tmp_path: Path, monkeypatch):
    summary = build_gharchive_project_fixture(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    release_dir = tmp_path / "release"
    input_dir = tmp_path / "submission_inputs"
    export_project_benchmark_release([Path(summary["project_dir"])], release_dir)
    export_project_submission_inputs(release_dir, input_dir, harden_probe_queries=True)
    provider_config = tmp_path / "opencode.json"
    provider_config.write_text(
        """
{
  "provider": {
    "openai": {
      "options": {"baseURL": "https://example.test/v1", "apiKey": "sk-test"},
      "models": {"gpt-5.4-mini": {"name": "GPT-5.4 Mini"}}
    }
  }
}
""",
        encoding="utf-8",
    )

    def fake_completion(provider, messages, *, max_output_tokens, request_timeout):
        assert provider["model"] == "gpt-5.4-mini"
        assert "no-gold" in messages[0]["content"]
        return "A-MEM-style policy note: wait for review and CI evidence before merge; do not store pre-CI emergency actions as a durable habit."

    monkeypatch.setattr(memory_submission, "_openai_chat_completion", fake_completion)
    predictions_path = tmp_path / "a_mem_predictions.jsonl"
    report = run_memory_submission_baseline(
        input_dir,
        predictions_path,
        adapter="a_mem",
        report_path=tmp_path / "a_mem_report.json",
        allow_external=True,
        provider_config_path=provider_config,
        model="gpt-5.4-mini",
        system_name="a_mem_prompt_adapter_test",
    )

    assert report["status"] == "completed"
    assert report["executed"] is True
    assert report["summary"]["predictions"] == 3
    assert report["constraints"]["uses_gold_memory_graph"] is False
    assert report["constraints"]["llm_generation_performed"] is True
    assert report["external_adapter"]["execution_mode"] == "openai_compatible_prompt_adapter"
    assert report["external_adapter"]["api_key_loaded"] is True
    assert "apiKey" not in read_json(tmp_path / "a_mem_report.json")["external_adapter"]
    rows = read_jsonl(predictions_path)
    assert len(rows) == 3
    assert all(row["metadata"]["adapter"] == "a_mem" for row in rows)
    assert all(row["metadata"]["openai_compatible_model"] == "gpt-5.4-mini" for row in rows)
    assert validate_project_prediction_submission(release_dir, predictions_path)["passed"] is True


def test_openai_compatible_external_memory_adapter_retries_transient_errors(tmp_path: Path, monkeypatch):
    summary = build_gharchive_project_fixture(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    release_dir = tmp_path / "release"
    input_dir = tmp_path / "submission_inputs"
    export_project_benchmark_release([Path(summary["project_dir"])], release_dir)
    export_project_submission_inputs(release_dir, input_dir, harden_probe_queries=True)
    provider_config = _write_provider_config(tmp_path)
    attempts = {"count": 0}

    def flaky_completion(provider, messages, *, max_output_tokens, request_timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol")
        return "Recovered A-MEM-style policy decision after a retry."

    monkeypatch.setattr(memory_submission, "_openai_chat_completion", flaky_completion)
    monkeypatch.setattr(memory_submission.time, "sleep", lambda _: None)
    report = run_memory_submission_baseline(
        input_dir,
        tmp_path / "a_mem_predictions.jsonl",
        adapter="a_mem",
        report_path=tmp_path / "a_mem_report.json",
        allow_external=True,
        provider_config_path=provider_config,
        max_retries=2,
        retry_backoff_seconds=0,
    )

    assert report["status"] == "completed"
    assert attempts["count"] == 4
    assert report["summary"]["predictions"] == 3


def test_openai_compatible_external_memory_adapter_resumes_existing_predictions(tmp_path: Path, monkeypatch):
    summary = build_gharchive_project_fixture(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    release_dir = tmp_path / "release"
    input_dir = tmp_path / "submission_inputs"
    export_project_benchmark_release([Path(summary["project_dir"])], release_dir)
    export_project_submission_inputs(release_dir, input_dir, harden_probe_queries=True)
    provider_config = _write_provider_config(tmp_path)
    first_probe = read_jsonl(input_dir / "probes.jsonl")[0]
    predictions_path = tmp_path / "a_mem_predictions.jsonl"
    write_jsonl(
        predictions_path,
        [
            {
                "prediction_id": f"pred_{first_probe['project_id']}_{first_probe['probe_id']}",
                "project_id": first_probe["project_id"],
                "probe_id": first_probe["probe_id"],
                "prediction": "Existing prediction to keep during resume.",
                "retrieved_memory_ids": [],
                "retrieved_event_ids": [],
                "retrieved_artifact_ids": [],
                "metadata": {"adapter": "a_mem", "no_gold_submission_input": True},
            }
        ],
    )
    calls = {"count": 0}

    def fake_completion(provider, messages, *, max_output_tokens, request_timeout):
        calls["count"] += 1
        return "New resumed A-MEM-style prediction."

    monkeypatch.setattr(memory_submission, "_openai_chat_completion", fake_completion)
    report = run_memory_submission_baseline(
        input_dir,
        predictions_path,
        adapter="a_mem",
        report_path=tmp_path / "a_mem_report.json",
        allow_external=True,
        provider_config_path=provider_config,
    )

    rows = read_jsonl(predictions_path)
    assert report["status"] == "completed"
    assert report["summary"]["loaded_existing_predictions"] == 1
    assert report["summary"]["new_predictions"] == 2
    assert calls["count"] == 2
    assert len(rows) == 3
    assert rows[0]["prediction"] == "Existing prediction to keep during resume."
    assert validate_project_prediction_submission(release_dir, predictions_path)["passed"] is True


def test_external_memory_submission_plan_reports_dependency_and_contract_status(tmp_path: Path):
    summary = build_gharchive_project_fixture(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    release_dir = tmp_path / "release"
    input_dir = tmp_path / "submission_inputs"
    export_project_benchmark_release([Path(summary["project_dir"])], release_dir)
    export_project_submission_inputs(release_dir, input_dir, harden_probe_queries=True)

    report = plan_external_memory_submission_adapter(
        input_dir,
        tmp_path / "mem0_predictions.jsonl",
        adapter="mem0",
        report_path=tmp_path / "mem0_plan.json",
        system_name="mem0_test",
    )

    assert report["status"] == "plan_ready"
    assert report["summary"]["probes"] == 3
    assert report["checks"]["input_contract_passed"] is True
    assert "dependencies" in report["checks"]
    assert report["external_adapter"]["display_name"] == "Mem0"
    assert report["next_steps"]["prediction_schema"]["required"] == ["prediction_id", "project_id", "probe_id", "prediction"]
    assert read_json(tmp_path / "mem0_plan.json")["system_name"] == "mem0_test"


def test_external_memory_runner_is_gated_before_import_or_execution(tmp_path: Path):
    summary = build_gharchive_project_fixture(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    release_dir = tmp_path / "release"
    input_dir = tmp_path / "submission_inputs"
    export_project_benchmark_release([Path(summary["project_dir"])], release_dir)
    export_project_submission_inputs(release_dir, input_dir, harden_probe_queries=True)
    predictions_path = tmp_path / "external_predictions.jsonl"

    report = run_external_memory_submission_runner(
        input_dir,
        predictions_path,
        runner="missing_external_module:run",
        report_path=tmp_path / "external_runner_report.json",
    )

    assert report["status"] == "blocked_requires_external_runner"
    assert report["executed"] is False
    assert report["summary"]["input_contract_passed"] is True
    assert report["constraints"]["external_dependency_invoked"] is False
    assert report["constraints"]["release_gold_supplied_to_runner"] is False
    assert not predictions_path.exists()
    assert read_json(tmp_path / "external_runner_report.json")["status"] == "blocked_requires_external_runner"


def test_external_memory_runner_executes_example_plugin_and_validates_no_gold_output(tmp_path: Path):
    summary = build_gharchive_project_fixture(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    release_dir = tmp_path / "release"
    input_dir = tmp_path / "submission_inputs"
    export_project_benchmark_release([Path(summary["project_dir"])], release_dir)
    export_project_submission_inputs(release_dir, input_dir, harden_probe_queries=True)
    predictions_path = tmp_path / "echo_predictions.jsonl"

    report = run_external_memory_submission_runner(
        input_dir,
        predictions_path,
        runner="examples.external_memory_adapters.echo_policy_runner:run",
        report_path=tmp_path / "echo_runner_report.json",
        runner_config={"max_events": 1},
        allow_external_runner=True,
        system_name="echo_policy_runner_test",
    )

    assert report["status"] == "completed"
    assert report["executed"] is True
    assert report["summary"]["predictions"] == 3
    assert report["summary"]["output_validation_passed"] is True
    assert report["constraints"]["benchmark_supplies_submission_inputs_only"] is True
    assert report["constraints"]["release_gold_supplied_to_runner"] is False
    assert report["constraints"]["uses_gold_memory_graph"] is False
    assert report["constraints"]["uses_probe_expected_behavior"] is False
    assert report["runner_result"] == {"rows_written": 3, "max_events": 1}
    rows = read_jsonl(predictions_path)
    assert len(rows) == 3
    assert all(row["metadata"]["system"] == "echo_policy_runner_test" for row in rows)
    assert all(row["metadata"]["no_gold_submission_input"] is True for row in rows)
    assert all(len(row["retrieved_event_ids"]) <= 1 for row in rows)
    assert validate_external_memory_predictions_against_input(input_dir, predictions_path)["passed"] is True
    assert validate_project_prediction_submission(release_dir, predictions_path)["passed"] is True
    assert read_json(tmp_path / "echo_runner_report.json")["status"] == "completed"


def test_external_memory_output_validation_rejects_missing_and_unknown_probes(tmp_path: Path):
    summary = build_gharchive_project_fixture(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    release_dir = tmp_path / "release"
    input_dir = tmp_path / "submission_inputs"
    export_project_benchmark_release([Path(summary["project_dir"])], release_dir)
    export_project_submission_inputs(release_dir, input_dir)
    probe = read_jsonl(input_dir / "probes.jsonl")[0]
    bad_predictions = tmp_path / "bad_predictions.jsonl"
    write_jsonl(
        bad_predictions,
        [
            {
                "prediction_id": "pred_unknown_probe",
                "project_id": probe["project_id"],
                "probe_id": "unknown_probe",
                "prediction": "This row should not validate against the public input probe ids.",
            }
        ],
    )

    report = validate_external_memory_predictions_against_input(input_dir, bad_predictions)

    assert report["passed"] is False
    issue_codes = {issue["code"] for issue in report["issues"]}
    assert "prediction_unknown_probe" in issue_codes
    assert "prediction_missing_probes" in issue_codes
