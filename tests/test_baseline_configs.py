from pathlib import Path

import yaml

from ultra_long_benchmark.pipelines.baseline_configs import run_baseline_config
from ultra_long_benchmark.pipelines.baseline_configs import run_baseline_config_dir
from ultra_long_benchmark.pipelines.baseline_configs import validate_baseline_config
from ultra_long_benchmark.pipelines.baseline_configs import validate_baseline_config_dir
from ultra_long_benchmark.pipelines.baseline_configs import verify_baseline_batch_report
from ultra_long_benchmark.pipelines.baseline_configs import verify_baseline_config_validation_report
from ultra_long_benchmark.pipelines.gharchive import DEFAULT_FIXTURE_PATH as DEFAULT_GHARCHIVE_FIXTURE_PATH
from ultra_long_benchmark.pipelines.gharchive import build_gharchive_project_fixture
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.project_release import export_project_submission_inputs
from ultra_long_benchmark.shared.io import load_yaml
from ultra_long_benchmark.shared.io import read_json
from ultra_long_benchmark.shared.io import read_jsonl
from ultra_long_benchmark.shared.io import write_json


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASELINE_CONFIGS = {
    "a_mem_submission_placeholder",
    "external_memory_runner_echo_contract",
    "graphiti_submission_placeholder",
    "mem0_submission_placeholder",
    "memory_submission_event_profile_stub",
    "memory_submission_event_profile_stub_hardened",
}


def test_baseline_config_directory_validates_checked_in_configs():
    report = validate_baseline_config_dir(ROOT / "configs" / "baselines")

    assert report["passed"] is True
    assert report["summary"]["configs_total"] == len(EXPECTED_BASELINE_CONFIGS)
    assert report["summary"]["configs_hashed"] == report["summary"]["configs_total"]
    assert all(item.get("sha256") and item.get("bytes") for item in report["configs"])
    assert {item["baseline_name"] for item in report["configs"]} == EXPECTED_BASELINE_CONFIGS


def test_baseline_config_validation_report_verifies_config_hashes(tmp_path: Path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    _write_minimal_baseline_config(config_dir / "baseline_a.yaml", "baseline_a")
    _write_minimal_baseline_config(config_dir / "baseline_b.yaml", "baseline_b")
    report_path = tmp_path / "baseline_validation.json"
    validate_baseline_config_dir(config_dir, output_path=report_path)

    verification = verify_baseline_config_validation_report(report_path)

    assert verification["passed"] is True
    assert verification["summary"]["configs_total"] == 2
    assert verification["summary"]["configs_verified"] == 2


def test_baseline_config_validation_report_fails_when_config_changes(tmp_path: Path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_path = config_dir / "baseline_a.yaml"
    _write_minimal_baseline_config(config_path, "baseline_a")
    report_path = tmp_path / "baseline_validation.json"
    validate_baseline_config_dir(config_dir, output_path=report_path)
    config_path.write_text(config_path.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")

    verification = verify_baseline_config_validation_report(report_path)

    assert verification["passed"] is False
    assert "baseline_config_sha256_mismatch" in verification["summary"]["issue_codes"]


def test_baseline_config_validation_report_fails_when_summary_counts_drift(tmp_path: Path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    _write_minimal_baseline_config(config_dir / "baseline_a.yaml", "baseline_a")
    report_path = tmp_path / "baseline_validation.json"
    validate_baseline_config_dir(config_dir, output_path=report_path)
    report = read_json(report_path)
    report["summary"]["configs_total"] = 2
    write_json(report_path, report)

    verification = verify_baseline_config_validation_report(report_path)

    assert verification["passed"] is False
    assert "baseline_config_summary_configs_total_mismatch" in verification["summary"]["issue_codes"]


def test_baseline_config_validation_report_fails_without_config_dir(tmp_path: Path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    _write_minimal_baseline_config(config_dir / "baseline_a.yaml", "baseline_a")
    report_path = tmp_path / "baseline_validation.json"
    validate_baseline_config_dir(config_dir, output_path=report_path)
    report = read_json(report_path)
    report.pop("config_dir")
    write_json(report_path, report)

    verification = verify_baseline_config_validation_report(report_path)

    assert verification["passed"] is False
    assert "baseline_config_dir_missing" in verification["summary"]["issue_codes"]


def test_baseline_config_validator_rejects_gpu_config_without_gpu_request(tmp_path: Path):
    bad_config = tmp_path / "bad_baseline.yaml"
    bad_config.write_text(
        """
baseline:
  name: bad_gpu
  family: memory_system
  entrypoint: ultra_long_benchmark.cli:run-memory-submission-baseline
  requires_llm_api: true
  requires_gpu: true
  memory_backend: mem0
data:
  project_dir: examples/generated/release_packaging/gharchive_formal_project_benchmark
  submission_input_dir: examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened
  predictions_path: examples/generated/evaluation_harness/bad_predictions.jsonl
  output_path: examples/generated/evaluation_harness/bad.json
evaluation:
  mode: memory_submission_prediction_generation
  adapter: mem0
  metrics: [prediction_coverage]
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
  entrypoint: ultra_long_benchmark.cli:run-memory-submission-baseline
  requires_llm_api: true
  requires_gpu: false
  memory_backend: graphiti
data:
  project_dir: examples/generated/release_packaging/gharchive_formal_project_benchmark
  submission_input_dir: examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened
  predictions_path: examples/generated/evaluation_harness/bad_predictions.jsonl
  output_path: examples/generated/evaluation_harness/bad.json
evaluation:
  mode: memory_submission_prediction_generation
  adapter: graphiti
  metrics: [prediction_coverage]
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


def test_run_baseline_config_generates_memory_submission_predictions(tmp_path: Path):
    release_dir, input_dir = _tiny_release_and_inputs(tmp_path)
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


def test_run_baseline_config_generates_hardened_memory_submission_predictions(tmp_path: Path):
    release_dir, input_dir = _tiny_release_and_inputs(tmp_path, hardened=True)
    predictions_path = tmp_path / "memory_submission_hardened_predictions.jsonl"
    config_path = _copy_config_with_data(
        ROOT / "configs" / "baselines" / "memory_submission_event_profile_stub_hardened.yaml",
        tmp_path / "memory_submission_event_profile_stub_hardened.yaml",
        {
            "project_dir": str(release_dir),
            "submission_input_dir": str(input_dir),
            "predictions_path": str(predictions_path),
            "output_path": str(tmp_path / "memory_submission_hardened_runner_report.json"),
        },
    )

    runner_report = run_baseline_config(config_path, tmp_path / "runner_report.json")

    assert runner_report["status"] == "completed"
    assert runner_report["executed"] is True
    assert runner_report["result_summary"]["predictions"] == 3
    assert read_json(input_dir / "submission_manifest.json")["query_hardening"]["enabled"] is True


def test_run_baseline_config_external_memory_runner_requires_explicit_allow(tmp_path: Path):
    release_dir, input_dir = _tiny_release_and_inputs(tmp_path, hardened=True)
    predictions_path = tmp_path / "echo_predictions.jsonl"
    config_path = tmp_path / "external_memory_runner_echo.yaml"
    config_path.write_text(
        f"""
baseline:
  name: external_memory_runner_echo
  family: memory_system_contract
  entrypoint: ultra_long_benchmark.cli:run-external-memory-submission-runner
  requires_llm_api: false
  requires_gpu: false
  memory_backend: external_runner
data:
  project_dir: {release_dir}
  submission_input_dir: {input_dir}
  predictions_path: {predictions_path}
  output_path: {tmp_path / "echo_runner_report.json"}
evaluation:
  mode: external_memory_submission_runner
  runner: examples.external_memory_adapters.echo_policy_runner:run
  runner_config:
    max_events: 1
  metrics:
    - prediction_coverage
    - no_gold_input_contract
resources:
  partition: cpu
  gpus: 0
  cpus_per_task: 1
  mem: 4G
  time: "00:05:00"
reproducibility:
  seed: 0
""",
        encoding="utf-8",
    )

    blocked = run_baseline_config(config_path, tmp_path / "blocked_runner_report.json")

    assert blocked["status"] == "blocked_requires_external_runner"
    assert blocked["executed"] is False
    assert not predictions_path.exists()

    completed = run_baseline_config(
        config_path,
        tmp_path / "completed_runner_report.json",
        allow_external_runner=True,
    )

    assert completed["status"] == "completed"
    assert completed["executed"] is True
    assert completed["result_summary"]["predictions"] == 3
    assert len(read_jsonl(predictions_path)) == 3
    report = read_json(tmp_path / "echo_runner_report.json")
    assert report["constraints"]["release_gold_supplied_to_runner"] is False
    assert report["output_validation"]["passed"] is True


def test_run_baseline_config_external_memory_runner_reports_bad_config_path(tmp_path: Path):
    release_dir, input_dir = _tiny_release_and_inputs(tmp_path)
    config_path = tmp_path / "external_memory_runner_bad_config.yaml"
    config_path.write_text(
        f"""
baseline:
  name: external_memory_runner_bad_config
  family: memory_system_contract
  entrypoint: ultra_long_benchmark.cli:run-external-memory-submission-runner
  requires_llm_api: false
  requires_gpu: false
  memory_backend: external_runner
data:
  project_dir: {release_dir}
  submission_input_dir: {input_dir}
  predictions_path: {tmp_path / "echo_predictions.jsonl"}
  output_path: {tmp_path / "echo_runner_report.json"}
  runner_config_path: {tmp_path / "missing_runner_config.json"}
evaluation:
  mode: external_memory_submission_runner
  runner: examples.external_memory_adapters.echo_policy_runner:run
  metrics:
    - prediction_coverage
resources:
  partition: cpu
  gpus: 0
  cpus_per_task: 1
  mem: 4G
  time: "00:05:00"
reproducibility:
  seed: 0
""",
        encoding="utf-8",
    )

    report = run_baseline_config(config_path, tmp_path / "runner_report.json", allow_external_runner=True)

    assert report["status"] == "invalid_runner_config"
    assert report["executed"] is False
    assert any("failed to load runner_config_path" in issue for issue in report["issues"])
    assert not (tmp_path / "echo_predictions.jsonl").exists()


def test_run_baseline_config_dry_runs_llm_api_placeholder_without_paths(tmp_path: Path):
    runner_report = run_baseline_config(
        ROOT / "configs" / "baselines" / "mem0_submission_placeholder.yaml",
        tmp_path / "mem0_dry_run.json",
        dry_run=True,
    )

    assert runner_report["status"] == "dry_run_requires_llm_api"
    assert runner_report["executed"] is False
    assert not runner_report["issues"]


def test_run_baseline_config_dir_executes_local_stub_and_dry_runs_external_configs(tmp_path: Path):
    release_dir, input_dir = _tiny_release_and_inputs(tmp_path)
    _, hardened_input_dir = _tiny_release_and_inputs(tmp_path / "hardened", hardened=True)
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    _copy_config_with_data(
        ROOT / "configs" / "baselines" / "memory_submission_event_profile_stub.yaml",
        config_dir / "memory_submission_event_profile_stub.yaml",
        {
            "project_dir": str(release_dir),
            "submission_input_dir": str(input_dir),
            "predictions_path": str(tmp_path / "memory_stub_predictions.jsonl"),
            "output_path": str(tmp_path / "memory_stub_report.json"),
        },
    )
    _copy_config_with_data(
        ROOT / "configs" / "baselines" / "external_memory_runner_echo_contract.yaml",
        config_dir / "external_memory_runner_echo_contract.yaml",
        {
            "project_dir": str(release_dir),
            "submission_input_dir": str(hardened_input_dir),
            "predictions_path": str(tmp_path / "echo_predictions.jsonl"),
            "output_path": str(tmp_path / "echo_report.json"),
        },
    )
    _copy_config_with_data(
        ROOT / "configs" / "baselines" / "mem0_submission_placeholder.yaml",
        config_dir / "mem0_submission_placeholder.yaml",
        {
            "project_dir": str(release_dir),
            "submission_input_dir": str(hardened_input_dir),
            "predictions_path": str(tmp_path / "mem0_predictions.jsonl"),
            "output_path": str(tmp_path / "mem0_report.json"),
        },
    )

    report = run_baseline_config_dir(config_dir, tmp_path / "batch_reports")

    assert report["passed"] is True
    assert report["summary"]["configs_total"] == 3
    assert report["summary"]["completed"] == 1
    assert report["summary"]["dry_run"] == 2
    assert report["summary"]["blocked"] == 0
    assert report["summary"]["runner_reports_hashed"] == 3
    assert report["summary"]["output_artifacts_hashed"] == 1
    assert all(item.get("runner_report_sha256") and item.get("runner_report_bytes") for item in report["reports"])
    assert all(item.get("output_artifact", {}).get("sha256") for item in report["reports"] if item["executed"])
    assert read_json(tmp_path / "batch_reports" / "baseline_batch_report.json")["summary"]["completed"] == 1


def test_baseline_batch_verifier_passes_for_unchanged_runner_reports_and_outputs(tmp_path: Path):
    config_dir = _single_executable_config_dir(tmp_path)
    batch_dir = tmp_path / "batch_reports"
    run_baseline_config_dir(config_dir, batch_dir)

    verification = verify_baseline_batch_report(batch_dir / "baseline_batch_report.json")

    assert verification["passed"] is True
    assert verification["summary"]["reports_total"] == 1
    assert verification["summary"]["runner_reports_verified"] == 1
    assert verification["summary"]["output_artifacts_verified"] == 1


def test_baseline_batch_verifier_fails_when_runner_report_changes(tmp_path: Path):
    config_dir = _single_executable_config_dir(tmp_path)
    batch_dir = tmp_path / "batch_reports"
    batch = run_baseline_config_dir(config_dir, batch_dir)
    runner_report_path = Path(batch["reports"][0]["runner_report_path"])
    runner_report = read_json(runner_report_path)
    runner_report["status"] = "changed_after_batch"
    write_json(runner_report_path, runner_report)

    verification = verify_baseline_batch_report(batch_dir / "baseline_batch_report.json")

    assert verification["passed"] is False
    assert "baseline_batch_runner_report_sha256_mismatch" in verification["summary"]["issue_codes"]


def test_baseline_batch_verifier_fails_when_output_artifact_changes(tmp_path: Path):
    config_dir = _single_executable_config_dir(tmp_path)
    batch_dir = tmp_path / "batch_reports"
    batch = run_baseline_config_dir(config_dir, batch_dir)
    output_path = Path(batch["reports"][0]["output_path"])
    output = read_json(output_path)
    output["changed_after_batch"] = True
    write_json(output_path, output)

    verification = verify_baseline_batch_report(batch_dir / "baseline_batch_report.json")

    assert verification["passed"] is False
    assert "baseline_batch_output_artifact_sha256_mismatch" in verification["summary"]["issue_codes"]


def _tiny_release_and_inputs(tmp_path: Path, *, hardened: bool = False) -> tuple[Path, Path]:
    summary = build_gharchive_project_fixture(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    release_dir = tmp_path / "release"
    input_dir = tmp_path / ("submission_inputs_hardened" if hardened else "submission_inputs")
    export_project_benchmark_release([Path(summary["project_dir"])], release_dir)
    export_project_submission_inputs(release_dir, input_dir, harden_probe_queries=hardened)
    return release_dir, input_dir


def _copy_config_with_data(source_path: Path, target_path: Path, data_updates: dict[str, str]) -> Path:
    config = load_yaml(source_path)
    config["data"].update(data_updates)
    target_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return target_path


def _single_executable_config_dir(tmp_path: Path) -> Path:
    release_dir, input_dir = _tiny_release_and_inputs(tmp_path)
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    _copy_config_with_data(
        ROOT / "configs" / "baselines" / "memory_submission_event_profile_stub.yaml",
        config_dir / "memory_submission_event_profile_stub.yaml",
        {
            "project_dir": str(release_dir),
            "submission_input_dir": str(input_dir),
            "predictions_path": str(tmp_path / "memory_stub_predictions.jsonl"),
            "output_path": str(tmp_path / "memory_stub_report.json"),
        },
    )
    return config_dir


def _write_minimal_baseline_config(path: Path, name: str) -> None:
    path.write_text(
        f"""
baseline:
  name: {name}
  family: memory_system_contract
  entrypoint: ultra_long_benchmark.cli:run-memory-submission-baseline
  requires_llm_api: false
  requires_gpu: false
  memory_backend: event_profile_stub
data:
  project_dir: examples/generated/release_packaging/gharchive_formal_project_benchmark
  submission_input_dir: examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened
  predictions_path: examples/generated/evaluation_harness/{name}_predictions.jsonl
  output_path: examples/generated/evaluation_harness/{name}.json
evaluation:
  mode: memory_submission_prediction_generation
  adapter: event_profile_stub
  metrics: [prediction_coverage]
resources:
  partition: cpu
  gpus: 0
  cpus_per_task: 1
  mem: 4G
  time: "00:05:00"
reproducibility:
  seed: 0
""",
        encoding="utf-8",
    )
