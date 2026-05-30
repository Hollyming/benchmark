from pathlib import Path

from ultra_long_benchmark.pipelines.gharchive_pilot import DEFAULT_FIXTURE_PATH as DEFAULT_GHARCHIVE_FIXTURE_PATH
from ultra_long_benchmark.pipelines.gharchive_pilot import run_gharchive_pilot
from ultra_long_benchmark.pipelines.memory_submission import plan_external_memory_submission_adapter
from ultra_long_benchmark.pipelines.memory_submission import run_memory_submission_baseline
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.project_release import export_project_submission_inputs
from ultra_long_benchmark.project_release import validate_project_prediction_submission
from ultra_long_benchmark.shared.io import read_json, read_jsonl


def test_event_profile_memory_submission_generates_no_gold_predictions(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
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


def test_external_memory_submission_plan_reports_dependency_and_contract_status(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
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
