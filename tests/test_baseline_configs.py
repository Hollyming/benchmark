from pathlib import Path

import yaml

from ultra_long_benchmark.pipelines.baseline_configs import run_baseline_config, run_baseline_config_dir, validate_baseline_config, validate_baseline_config_dir
from ultra_long_benchmark.pipelines.gharchive_pilot import DEFAULT_FIXTURE_PATH as DEFAULT_GHARCHIVE_FIXTURE_PATH
from ultra_long_benchmark.pipelines.gharchive_pilot import run_gharchive_pilot
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.project_release import export_project_submission_inputs
from ultra_long_benchmark.shared.io import load_yaml, read_json, read_jsonl, write_jsonl


ROOT = Path(__file__).resolve().parents[1]


def test_baseline_config_directory_validates_checked_in_configs():
    report = validate_baseline_config_dir(ROOT / "configs" / "baselines")

    assert report["passed"] is True
    assert report["summary"]["configs_total"] >= 4
    names = {item["baseline_name"] for item in report["configs"]}
    assert {
        "oracle_policy_graph",
        "raw_rag_project",
        "temporal_raw_rag_project",
        "gharchive_prediction_submission_example",
        "project_release_prediction_dir",
        "full_event_log_project",
        "no_memory_project",
        "gharchive_action_trace_scoring",
        "submission_input_raw_event_rag",
        "memory_submission_event_profile_stub",
        "memory_submission_event_profile_stub_hardened",
        "mem0_project",
        "a_mem_project",
        "mem0_submission_placeholder",
        "a_mem_submission_placeholder",
        "graphiti_submission_placeholder",
    } <= names


def test_baseline_config_validator_rejects_gpu_config_without_gpu_request(tmp_path: Path):
    bad_config = tmp_path / "bad_baseline.yaml"
    bad_config.write_text(
        """
baseline:
  name: bad_gpu
  family: memory_system
  entrypoint: runner:main
  requires_llm_api: true
  requires_gpu: true
  memory_backend: mem0
data:
  project_dir: examples/generated/projects/project_gharchive_001
  output_path: examples/generated/evaluation_harness/bad.json
evaluation:
  mode: project_probe_action_trace
  metrics: [boundary_violation_rate]
resources:
  partition: RTX4090
  gpus: 0
  cpus_per_task: 4
  mem: 16G
  time: "01:00:00"
reproducibility:
  seed: 0
environment:
  required: [OPENAI_API_KEY]
""",
        encoding="utf-8",
    )

    report = validate_baseline_config(bad_config)

    assert report["passed"] is False
    assert any("resources.gpus > 0" in issue for issue in report["issues"])


def test_baseline_config_validator_rejects_llm_config_without_required_env(tmp_path: Path):
    bad_config = tmp_path / "bad_env.yaml"
    bad_config.write_text(
        """
baseline:
  name: bad_env
  family: memory_system
  entrypoint: runner:main
  requires_llm_api: true
  requires_gpu: false
  memory_backend: external
data:
  project_dir: examples/generated/projects/project_gharchive_001
  output_path: examples/generated/evaluation_harness/bad.json
evaluation:
  mode: project_probe_text
  metrics: [evidence_recall]
resources:
  partition: cpu
  gpus: 0
  cpus_per_task: 2
  mem: 8G
  time: "00:20:00"
reproducibility:
  seed: 0
""",
        encoding="utf-8",
    )

    report = validate_baseline_config(bad_config)

    assert report["passed"] is False
    assert any("environment.required" in issue for issue in report["issues"])


def test_baseline_config_validator_rejects_unknown_project_baseline(tmp_path: Path):
    bad_config = tmp_path / "bad_project_baseline.yaml"
    bad_config.write_text(
        """
baseline:
  name: bad_project_baseline
  family: retrieval
  entrypoint: ultra_long_benchmark.cli:evaluate-project
  requires_llm_api: false
  requires_gpu: false
  memory_backend: none
data:
  project_dir: examples/generated/projects/project_gharchive_001
  output_path: examples/generated/evaluation_harness/bad.json
evaluation:
  mode: project_probe_text
  baselines: [not_a_baseline]
  metrics: [evidence_recall]
resources:
  partition: cpu
  gpus: 0
  cpus_per_task: 2
  mem: 8G
  time: "00:20:00"
reproducibility:
  seed: 0
""",
        encoding="utf-8",
    )

    report = validate_baseline_config(bad_config)

    assert report["passed"] is False
    assert any("unsupported project baselines" in issue for issue in report["issues"])


def test_run_baseline_config_executes_raw_rag_project_config(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    config_path = _copy_config_with_data(
        ROOT / "configs" / "baselines" / "raw_rag_project.yaml",
        tmp_path / "raw_rag_project.yaml",
        {
            "project_dir": summary["project_dir"],
            "output_path": str(tmp_path / "raw_rag_report.json"),
        },
    )

    runner_report = run_baseline_config(config_path, tmp_path / "runner_report.json")

    assert runner_report["status"] == "completed"
    assert runner_report["executed"] is True
    assert runner_report["result_summary"]["probes"] == 3
    result = read_json(tmp_path / "raw_rag_report.json")
    assert result["project_id"] == "project_gharchive_001"
    assert set(result["baselines"]) == {"raw_rag"}


def test_run_baseline_config_executes_temporal_raw_rag_project_config(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    config_path = _copy_config_with_data(
        ROOT / "configs" / "baselines" / "temporal_raw_rag_project.yaml",
        tmp_path / "temporal_raw_rag_project.yaml",
        {
            "project_dir": summary["project_dir"],
            "output_path": str(tmp_path / "temporal_raw_rag_report.json"),
        },
    )

    runner_report = run_baseline_config(config_path, tmp_path / "runner_report.json")

    assert runner_report["status"] == "completed"
    assert runner_report["executed"] is True
    result = read_json(tmp_path / "temporal_raw_rag_report.json")
    assert result["summary"]["baseline_names"] == ["temporal_raw_rag"]
    assert set(result["baselines"]) == {"temporal_raw_rag"}


def test_run_baseline_config_executes_action_trace_scoring_config(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    config_path = _copy_config_with_data(
        ROOT / "configs" / "baselines" / "gharchive_action_trace_scoring.yaml",
        tmp_path / "gharchive_action_trace_scoring.yaml",
        {
            "project_dir": summary["project_dir"],
            "traces_path": str(ROOT / "examples" / "action_traces" / "gharchive_trace_examples.jsonl"),
            "output_path": str(tmp_path / "trace_report.json"),
        },
    )

    runner_report = run_baseline_config(config_path, tmp_path / "runner_report.json")

    assert runner_report["status"] == "completed"
    assert runner_report["executed"] is True
    assert runner_report["result_summary"]["traces"] == 2
    assert runner_report["result_summary"]["boundary_violation_rate"] == 0.5


def test_run_baseline_config_executes_prediction_submission_config(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    config_path = _copy_config_with_data(
        ROOT / "configs" / "baselines" / "gharchive_prediction_submission_example.yaml",
        tmp_path / "gharchive_prediction_submission_example.yaml",
        {
            "project_dir": summary["project_dir"],
            "predictions_path": str(ROOT / "examples" / "project_predictions" / "gharchive_prediction_examples.jsonl"),
            "output_path": str(tmp_path / "prediction_report.json"),
        },
    )

    runner_report = run_baseline_config(config_path, tmp_path / "runner_report.json")

    assert runner_report["status"] == "completed"
    assert runner_report["executed"] is True
    assert runner_report["result_summary"]["predictions"] == 3
    assert runner_report["result_summary"]["pass_rate"] < 1.0
    assert read_json(tmp_path / "prediction_report.json")["system_name"] == "gharchive_prediction_submission_example"


def test_run_baseline_config_generates_predictions_from_submission_inputs(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    release_dir = tmp_path / "release"
    input_dir = tmp_path / "submission_inputs"
    export_project_benchmark_release([Path(summary["project_dir"])], release_dir)
    export_project_submission_inputs(release_dir, input_dir)
    predictions_path = tmp_path / "submission_predictions.jsonl"
    config_path = _copy_config_with_data(
        ROOT / "configs" / "baselines" / "submission_input_raw_event_rag.yaml",
        tmp_path / "submission_input_raw_event_rag.yaml",
        {
            "project_dir": str(release_dir),
            "submission_input_dir": str(input_dir),
            "predictions_path": str(predictions_path),
            "output_path": str(tmp_path / "submission_runner_report.json"),
        },
    )

    runner_report = run_baseline_config(config_path, tmp_path / "runner_report.json")

    assert runner_report["status"] == "completed"
    assert runner_report["executed"] is True
    assert runner_report["result_summary"]["predictions"] == 3
    predictions = predictions_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(predictions) == 3
    assert read_json(tmp_path / "submission_runner_report.json")["constraints"]["uses_gold_memory_graph"] is False


def test_run_baseline_config_generates_memory_submission_predictions(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    release_dir = tmp_path / "release"
    input_dir = tmp_path / "submission_inputs"
    export_project_benchmark_release([Path(summary["project_dir"])], release_dir)
    export_project_submission_inputs(release_dir, input_dir)
    predictions_path = tmp_path / "memory_submission_predictions.jsonl"
    config_path = _copy_config_with_data(
        ROOT / "configs" / "baselines" / "memory_submission_event_profile_stub.yaml",
        tmp_path / "memory_submission_event_profile_stub.yaml",
        {
            "project_dir": str(release_dir),
            "submission_input_dir": str(input_dir),
            "predictions_path": str(predictions_path),
            "output_path": str(tmp_path / "memory_submission_runner_report.json"),
        },
    )

    runner_report = run_baseline_config(config_path, tmp_path / "runner_report.json")

    assert runner_report["status"] == "completed"
    assert runner_report["executed"] is True
    assert runner_report["result_summary"]["predictions"] == 3
    assert len(read_jsonl(predictions_path)) == 3
    result = read_json(tmp_path / "memory_submission_runner_report.json")
    assert result["adapter"] == "event_profile_stub"
    assert result["constraints"]["uses_gold_memory_graph"] is False


def test_run_baseline_config_scores_release_prediction_directory(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    release_dir = tmp_path / "release"
    export_project_benchmark_release([Path(summary["project_dir"])], release_dir)
    submissions_dir = tmp_path / "release_submissions"
    submissions_dir.mkdir()
    predictions_path = submissions_dir / "oracle_like.jsonl"
    project_dir = Path(summary["project_dir"])
    project_id = read_json(project_dir / "project_profile.json")["project_id"]
    rows = []
    for probe in read_jsonl(project_dir / "probes.jsonl"):
        rows.append(
            {
                "prediction_id": f"pred_{probe['probe_id']}",
                "project_id": project_id,
                "probe_id": probe["probe_id"],
                "prediction": (
                    " ".join(probe["expected_behavior"].get("must_include", []))
                    + " do not "
                    + " ".join(probe["expected_behavior"].get("must_not_include", []))
                    + " "
                    + " ".join(_positive_boundary_terms(project_dir, probe))
                ),
                "retrieved_memory_ids": probe["evidence"]["positive"],
                "retrieved_event_ids": _positive_event_ids(project_dir, probe),
                "retrieved_artifact_ids": [],
            }
        )
    from ultra_long_benchmark.shared.io import write_jsonl

    write_jsonl(predictions_path, rows)
    output_path = tmp_path / "prediction_scoring_batch" / "prediction_scoring_batch_report.json"
    config_path = _copy_config_with_data(
        ROOT / "configs" / "baselines" / "project_release_prediction_dir.yaml",
        tmp_path / "project_release_prediction_dir.yaml",
        {
            "project_dir": str(release_dir),
            "predictions_dir": str(submissions_dir),
            "output_path": str(output_path),
        },
    )

    runner_report = run_baseline_config(config_path, tmp_path / "runner_report.json")

    assert runner_report["status"] == "completed"
    assert runner_report["executed"] is True
    assert runner_report["result_summary"]["systems"] == 1
    assert read_json(output_path)["summary"]["systems"] == 1


def test_run_baseline_config_validates_release_prediction_submission(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    release_dir = tmp_path / "release"
    export_project_benchmark_release([Path(summary["project_dir"])], release_dir)
    project_dir = Path(summary["project_dir"])
    project_id = read_json(project_dir / "project_profile.json")["project_id"]
    predictions_path = tmp_path / "release_predictions.jsonl"
    write_jsonl(
        predictions_path,
        [
            {
                "prediction_id": f"pred_{probe['probe_id']}",
                "project_id": project_id,
                "probe_id": probe["probe_id"],
                "prediction": "Follow the user's grounded policy and preserve action boundaries.",
            }
            for probe in read_jsonl(project_dir / "probes.jsonl")
        ],
    )
    output_path = tmp_path / "prediction_submission_validation.json"
    config_path = _copy_config_with_data(
        ROOT / "configs" / "baselines" / "project_release_prediction_validation.yaml",
        tmp_path / "project_release_prediction_validation.yaml",
        {
            "project_dir": str(release_dir),
            "predictions_path": str(predictions_path),
            "output_path": str(output_path),
        },
    )

    runner_report = run_baseline_config(config_path, tmp_path / "runner_report.json")

    assert runner_report["status"] == "completed"
    assert runner_report["executed"] is True
    assert runner_report["result_summary"]["coverage"]["probe_coverage"] == 1.0
    assert read_json(output_path)["passed"] is True


def test_run_baseline_config_dry_runs_llm_api_placeholder_without_paths(tmp_path: Path):
    runner_report = run_baseline_config(
        ROOT / "configs" / "baselines" / "mem0_project_placeholder.yaml",
        tmp_path / "mem0_dry_run.json",
        dry_run=True,
    )

    assert runner_report["status"] == "dry_run_requires_llm_api"
    assert runner_report["executed"] is False
    assert not runner_report["issues"]


def test_run_baseline_config_dir_executes_offline_and_dry_runs_external_configs(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    _copy_config_with_data(
        ROOT / "configs" / "baselines" / "raw_rag_project.yaml",
        config_dir / "raw_rag_project.yaml",
        {
            "project_dir": summary["project_dir"],
            "output_path": str(tmp_path / "raw_rag_report.json"),
        },
    )
    _copy_config_with_data(
        ROOT / "configs" / "baselines" / "gharchive_action_trace_scoring.yaml",
        config_dir / "gharchive_action_trace_scoring.yaml",
        {
            "project_dir": summary["project_dir"],
            "traces_path": str(ROOT / "examples" / "action_traces" / "gharchive_trace_examples.jsonl"),
            "output_path": str(tmp_path / "trace_report.json"),
        },
    )
    _copy_config_with_data(
        ROOT / "configs" / "baselines" / "mem0_project_placeholder.yaml",
        config_dir / "mem0_project_placeholder.yaml",
        {
            "project_dir": summary["project_dir"],
            "output_path": str(tmp_path / "mem0_report.json"),
        },
    )

    report = run_baseline_config_dir(config_dir, tmp_path / "batch_reports")

    assert report["passed"] is True
    assert report["summary"]["configs_total"] == 3
    assert report["summary"]["completed"] == 2
    assert report["summary"]["dry_run"] == 1
    assert report["summary"]["blocked"] == 0
    assert read_json(tmp_path / "batch_reports" / "baseline_batch_report.json")["summary"]["completed"] == 2


def _copy_config_with_data(source_path: Path, target_path: Path, data_updates: dict[str, str]) -> Path:
    config = load_yaml(source_path)
    config["data"].update(data_updates)
    target_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return target_path


def _positive_event_ids(project_dir: Path, probe: dict) -> list[str]:
    graph = read_json(project_dir / "memory_graph.json")
    memory_by_id = {memory["memory_id"]: memory for memory in graph["memories"]}
    event_ids = []
    for memory_id in probe["evidence"]["positive"]:
        event_ids.extend(memory_by_id[memory_id]["source_events"])
    return sorted(set(event_ids))


def _positive_boundary_terms(project_dir: Path, probe: dict) -> list[str]:
    graph = read_json(project_dir / "memory_graph.json")
    memory_by_id = {memory["memory_id"]: memory for memory in graph["memories"]}
    terms = []
    for memory_id in probe["evidence"]["positive"]:
        boundary = memory_by_id[memory_id].get("action_boundary") or {}
        for key in ["allowed_actions", "forbidden_actions", "requires_approval", "requires_clarification", "authorized_tools", "forbidden_tools"]:
            terms.extend(str(value).replace("_", " ") for value in boundary.get(key, []))
    return terms
