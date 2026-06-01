from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ultra_long_benchmark.shared.io import load_yaml, read_json, write_json


REQUIRED_TOP_LEVEL = {"baseline", "data", "evaluation", "resources", "reproducibility"}
REQUIRED_BASELINE = {"name", "family", "entrypoint", "requires_llm_api", "requires_gpu", "memory_backend"}
REQUIRED_DATA = {"project_dir", "output_path"}
REQUIRED_EVALUATION = {"mode", "metrics"}
REQUIRED_RESOURCES = {"partition", "gpus", "cpus_per_task", "mem", "time"}


def validate_baseline_config(config_path: Path, output_path: Path | None = None, strict_paths: bool = False) -> dict[str, Any]:
    config_path = Path(config_path)
    config = load_yaml(config_path)
    issues: list[str] = []
    warnings: list[str] = []

    if not isinstance(config, dict):
        issues.append("config must be a mapping")
        config = {}

    _require_keys(config, REQUIRED_TOP_LEVEL, "root", issues)
    baseline = _mapping(config.get("baseline"), "baseline", issues)
    data = _mapping(config.get("data"), "data", issues)
    evaluation = _mapping(config.get("evaluation"), "evaluation", issues)
    resources = _mapping(config.get("resources"), "resources", issues)
    reproducibility = _mapping(config.get("reproducibility"), "reproducibility", issues)

    _require_keys(baseline, REQUIRED_BASELINE, "baseline", issues)
    _require_keys(data, REQUIRED_DATA, "data", issues)
    _require_keys(evaluation, REQUIRED_EVALUATION, "evaluation", issues)
    _require_keys(resources, REQUIRED_RESOURCES, "resources", issues)

    if baseline.get("requires_llm_api") is True and not _required_env(config):
        issues.append("LLM/API baseline must declare environment.required")
    if baseline.get("requires_gpu") is True and int(resources.get("gpus", 0)) <= 0:
        issues.append("GPU baseline must request resources.gpus > 0")
    if baseline.get("requires_gpu") is False and int(resources.get("gpus", 0)) != 0:
        warnings.append("non-GPU baseline requests GPUs")
    if not isinstance(evaluation.get("metrics", []), list) or not evaluation.get("metrics"):
        issues.append("evaluation.metrics must be a non-empty list")
    if evaluation.get("mode") == "project_probe_text" and "baselines" in evaluation:
        from ultra_long_benchmark.pipelines.evaluation import supported_project_baselines

        baselines = evaluation.get("baselines")
        if not isinstance(baselines, list) or not baselines:
            issues.append("evaluation.baselines must be a non-empty list when set")
        else:
            unknown = sorted(set(str(name) for name in baselines) - set(supported_project_baselines()))
            if unknown:
                issues.append(f"evaluation.baselines contains unsupported project baselines: {unknown}")
    if evaluation.get("mode") == "external_memory_submission_runner" and not evaluation.get("runner"):
        issues.append("external_memory_submission_runner config requires evaluation.runner")
    if "placeholder" in config_path.stem and baseline.get("requires_llm_api") is not True:
        warnings.append("placeholder config usually requires llm/api dependencies")
    if reproducibility.get("seed") is None:
        warnings.append("reproducibility.seed is not set")

    project_dir = Path(str(data.get("project_dir", "")))
    if strict_paths and project_dir and not project_dir.exists():
        issues.append(f"data.project_dir does not exist: {project_dir}")
    traces_path = data.get("traces_path")
    if strict_paths and traces_path and not Path(str(traces_path)).exists():
        issues.append(f"data.traces_path does not exist: {traces_path}")

    report = {
        "config_path": str(config_path),
        "baseline_name": baseline.get("name"),
        "passed": not issues,
        "issues": issues,
        "warnings": warnings,
        "bytes": config_path.stat().st_size,
        "sha256": _file_sha256(config_path),
        "summary": {
            "family": baseline.get("family"),
            "requires_llm_api": baseline.get("requires_llm_api"),
            "requires_gpu": baseline.get("requires_gpu"),
            "partition": resources.get("partition"),
            "gpus": resources.get("gpus"),
            "metrics": evaluation.get("metrics", []),
        },
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def run_baseline_config(
    config_path: Path,
    output_path: Path | None = None,
    dry_run: bool = False,
    allow_llm_api: bool = False,
    allow_external_runner: bool = False,
) -> dict[str, Any]:
    """Run a supported baseline config or report why it is gated.

    This dispatcher deliberately executes only deterministic in-repo baselines.
    External memory systems such as Mem0/A-MEM stay behind explicit dependency
    gates until their runners and API credentials are available.
    """

    from ultra_long_benchmark.pipelines.evaluation import (
        run_project_baseline_evaluation,
        run_submission_input_baseline,
        score_action_traces,
        score_project_release_action_traces,
        score_project_predictions,
        score_project_release_prediction_dir,
        score_project_release_predictions,
    )
    from ultra_long_benchmark.pipelines.external_memory_runner import run_external_memory_submission_runner
    from ultra_long_benchmark.pipelines.memory_submission import run_memory_submission_baseline
    from ultra_long_benchmark.project_release import validate_project_prediction_submission

    config_path = Path(config_path)
    config = load_yaml(config_path)
    validation = validate_baseline_config(config_path, strict_paths=not dry_run)
    baseline = config.get("baseline", {}) if isinstance(config, dict) else {}
    data = config.get("data", {}) if isinstance(config, dict) else {}
    evaluation = config.get("evaluation", {}) if isinstance(config, dict) else {}
    report = {
        "config_path": str(config_path),
        "baseline_name": baseline.get("name"),
        "dry_run": dry_run,
        "executed": False,
        "status": "pending",
        "issues": list(validation["issues"]),
        "warnings": list(validation["warnings"]),
        "validation": validation,
        "output_path": data.get("output_path"),
    }
    if not validation["passed"]:
        report["status"] = "invalid_config"
        if output_path is not None:
            write_json(output_path, report)
        return report

    if dry_run:
        report["status"] = "dry_run_requires_llm_api" if baseline.get("requires_llm_api") else "dry_run_ok"
        if baseline.get("requires_llm_api"):
            report["warnings"].append("baseline requires LLM/API credentials; dry-run did not execute external dependencies")
        if output_path is not None:
            write_json(output_path, report)
        return report

    if baseline.get("requires_llm_api") and not allow_llm_api:
        report["status"] = "blocked_requires_llm_api"
        report["issues"].append("baseline requires LLM/API credentials; rerun with an explicit implementation and allow_llm_api")
        if output_path is not None:
            write_json(output_path, report)
        return report

    mode = evaluation.get("mode")
    entrypoint = baseline.get("entrypoint")
    project_dir = Path(data["project_dir"])
    baseline_output = Path(data["output_path"])
    if mode == "project_probe_text" and entrypoint == "ultra_long_benchmark.cli:evaluate-project":
        result = run_project_baseline_evaluation(
            project_dir,
            baseline_output,
            top_k=int(evaluation.get("top_k", 5)),
            baseline_names=evaluation.get("baselines"),
        )
        report["executed"] = True
        report["status"] = "completed"
        report["result_summary"] = result["summary"]
    elif mode == "project_probe_action_trace" and entrypoint == "ultra_long_benchmark.cli:score-action-traces":
        traces_path = data.get("traces_path")
        if not traces_path:
            report["status"] = "blocked_missing_traces_path"
            report["issues"].append("project_probe_action_trace config requires data.traces_path")
        else:
            result = score_action_traces(project_dir, Path(traces_path), baseline_output)
            report["executed"] = True
            report["status"] = "completed"
            report["result_summary"] = result["summary"]
    elif mode == "project_release_action_trace" and entrypoint == "ultra_long_benchmark.cli:score-project-release-action-traces":
        traces_path = data.get("traces_path")
        if not traces_path:
            report["status"] = "blocked_missing_traces_path"
            report["issues"].append("project_release_action_trace config requires data.traces_path")
        else:
            result = score_project_release_action_traces(
                project_dir,
                Path(traces_path),
                baseline_output,
                system_name=str(evaluation.get("system_name") or baseline.get("name") or "external_trace_system"),
            )
            report["executed"] = True
            report["status"] = "completed"
            report["result_summary"] = result["summary"]
    elif mode == "project_probe_prediction_submission" and entrypoint == "ultra_long_benchmark.cli:score-project-predictions":
        predictions_path = data.get("predictions_path")
        if not predictions_path:
            report["status"] = "blocked_missing_predictions_path"
            report["issues"].append("project_probe_prediction_submission config requires data.predictions_path")
        else:
            result = score_project_predictions(
                project_dir,
                Path(predictions_path),
                baseline_output,
                system_name=str(baseline.get("name") or "external_system"),
            )
            report["executed"] = True
            report["status"] = "completed"
            report["result_summary"] = result["summary"]
    elif mode == "submission_input_prediction_generation" and entrypoint == "ultra_long_benchmark.cli:run-submission-input-baseline":
        input_dir = data.get("submission_input_dir")
        predictions_path = data.get("predictions_path")
        if not input_dir:
            report["status"] = "blocked_missing_submission_input_dir"
            report["issues"].append("submission_input_prediction_generation config requires data.submission_input_dir")
        elif not predictions_path:
            report["status"] = "blocked_missing_predictions_path"
            report["issues"].append("submission_input_prediction_generation config requires data.predictions_path")
        else:
            result = run_submission_input_baseline(
                Path(input_dir),
                Path(predictions_path),
                baseline_name=str(evaluation.get("baseline", "raw_event_rag_input")),
                top_k=int(evaluation.get("top_k", 5)),
                report_path=baseline_output,
            )
            report["executed"] = True
            report["status"] = "completed"
            report["result_summary"] = result["summary"]
    elif mode == "memory_submission_prediction_generation" and entrypoint == "ultra_long_benchmark.cli:run-memory-submission-baseline":
        input_dir = data.get("submission_input_dir")
        predictions_path = data.get("predictions_path")
        if not input_dir:
            report["status"] = "blocked_missing_submission_input_dir"
            report["issues"].append("memory_submission_prediction_generation config requires data.submission_input_dir")
        elif not predictions_path:
            report["status"] = "blocked_missing_predictions_path"
            report["issues"].append("memory_submission_prediction_generation config requires data.predictions_path")
        else:
            result = run_memory_submission_baseline(
                Path(input_dir),
                Path(predictions_path),
                adapter=str(evaluation.get("adapter", baseline.get("memory_backend") or "event_profile_stub")),
                top_k=int(evaluation.get("top_k", 5)),
                report_path=baseline_output,
                allow_external=allow_llm_api,
                system_name=str(baseline.get("name") or evaluation.get("adapter") or "memory_submission"),
                provider_config_path=Path(evaluation["provider_config_path"]) if evaluation.get("provider_config_path") else None,
                model=evaluation.get("model"),
                max_output_tokens=int(evaluation.get("max_output_tokens", 512)),
                request_timeout=float(evaluation.get("request_timeout", 60.0)),
                max_retries=int(evaluation.get("max_retries", 3)),
                retry_backoff_seconds=float(evaluation.get("retry_backoff_seconds", 2.0)),
            )
            report["executed"] = bool(result.get("executed"))
            report["status"] = "completed" if result.get("status") == "completed" else str(result.get("status"))
            report["result_summary"] = result["summary"]
            report["issues"].extend(str(issue) for issue in result.get("issues", []))
    elif mode == "external_memory_submission_runner" and entrypoint == "ultra_long_benchmark.cli:run-external-memory-submission-runner":
        input_dir = data.get("submission_input_dir")
        predictions_path = data.get("predictions_path")
        runner = evaluation.get("runner")
        if not input_dir:
            report["status"] = "blocked_missing_submission_input_dir"
            report["issues"].append("external_memory_submission_runner config requires data.submission_input_dir")
        elif not predictions_path:
            report["status"] = "blocked_missing_predictions_path"
            report["issues"].append("external_memory_submission_runner config requires data.predictions_path")
        elif not runner:
            report["status"] = "blocked_missing_runner"
            report["issues"].append("external_memory_submission_runner config requires evaluation.runner")
        else:
            issue_count_before_runner_config = len(report["issues"])
            runner_config = _runner_config(data, evaluation, report["issues"])
            if len(report["issues"]) > issue_count_before_runner_config:
                report["status"] = "invalid_runner_config"
            else:
                result = run_external_memory_submission_runner(
                    Path(input_dir),
                    Path(predictions_path),
                    runner=str(runner),
                    report_path=baseline_output,
                    runner_config=runner_config,
                    allow_external_runner=allow_external_runner,
                    system_name=str(evaluation.get("system_name") or baseline.get("name") or "external_memory_runner"),
                    require_complete=not bool(evaluation.get("allow_partial", False)),
                )
                report["executed"] = bool(result.get("executed"))
                report["status"] = "completed" if result.get("status") == "completed" else str(result.get("status"))
                report["result_summary"] = result["summary"]
                report["issues"].extend(str(issue) for issue in result.get("issues", []))
    elif mode == "project_release_prediction_submission" and entrypoint == "ultra_long_benchmark.cli:score-project-release-predictions":
        predictions_path = data.get("predictions_path")
        if not predictions_path:
            report["status"] = "blocked_missing_predictions_path"
            report["issues"].append("project_release_prediction_submission config requires data.predictions_path")
        else:
            result = score_project_release_predictions(
                project_dir,
                Path(predictions_path),
                baseline_output,
                system_name=str(baseline.get("name") or "external_system"),
            )
            report["executed"] = True
            report["status"] = "completed"
            report["result_summary"] = result["summary"]
    elif mode == "project_release_prediction_submission_validation" and entrypoint == "ultra_long_benchmark.cli:validate-project-prediction-submission":
        predictions_path = data.get("predictions_path")
        if not predictions_path:
            report["status"] = "blocked_missing_predictions_path"
            report["issues"].append("project_release_prediction_submission_validation config requires data.predictions_path")
        else:
            result = validate_project_prediction_submission(
                project_dir,
                Path(predictions_path),
                output_path=baseline_output,
                require_complete=not bool(evaluation.get("allow_partial", False)),
            )
            report["executed"] = True
            report["status"] = "completed" if result["passed"] else "validation_failed"
            report["result_summary"] = result["summary"] | {"coverage": result.get("checks", {}).get("coverage", {})}
            report["issues"].extend(issue["message"] for issue in result.get("issues", []))
    elif mode == "project_release_prediction_submission_dir" and entrypoint == "ultra_long_benchmark.cli:score-project-release-prediction-dir":
        predictions_dir = data.get("predictions_dir")
        if not predictions_dir:
            report["status"] = "blocked_missing_predictions_dir"
            report["issues"].append("project_release_prediction_submission_dir config requires data.predictions_dir")
        else:
            result = score_project_release_prediction_dir(
                project_dir,
                Path(predictions_dir),
                baseline_output.parent,
                system_name_prefix=evaluation.get("system_name_prefix"),
            )
            report["executed"] = True
            report["status"] = "completed"
            report["result_summary"] = result["summary"]
    else:
        report["status"] = "unsupported_entrypoint"
        report["issues"].append(f"unsupported baseline entrypoint/mode: {baseline.get('entrypoint')} / {mode}")

    if output_path is not None:
        write_json(output_path, report)
    return report


def run_baseline_config_dir(
    config_dir: Path,
    output_dir: Path,
    dry_run_external: bool = True,
    allow_llm_api: bool = False,
    allow_external_runner: bool = False,
) -> dict[str, Any]:
    """Run a directory of baseline configs with explicit external-system gates."""

    config_dir = Path(config_dir)
    output_dir = Path(output_dir)
    reports = []
    for config_path in sorted(config_dir.glob("*.yaml")):
        config = load_yaml(config_path)
        baseline = config.get("baseline", {}) if isinstance(config, dict) else {}
        dry_run = bool(
            dry_run_external
            and (
                baseline.get("requires_llm_api")
                or baseline.get("entrypoint") == "ultra_long_benchmark.cli:run-external-memory-submission-runner"
            )
        )
        report_path = output_dir / f"{config_path.stem}_runner_report.json"
        report = run_baseline_config(
            config_path,
            dry_run=dry_run,
            allow_llm_api=allow_llm_api,
            allow_external_runner=allow_external_runner,
        )
        report["runner_report_path"] = str(report_path)
        if report.get("executed") is True and report.get("output_path"):
            report["output_artifact"] = _artifact_record(Path(str(report["output_path"])))
        write_json(report_path, report)
        report["runner_report_sha256"] = _file_sha256(report_path)
        report["runner_report_bytes"] = report_path.stat().st_size
        reports.append(report)

    summary = {
        "configs_total": len(reports),
        "completed": sum(1 for report in reports if report["status"] == "completed"),
        "dry_run": sum(1 for report in reports if str(report["status"]).startswith("dry_run")),
        "blocked": sum(1 for report in reports if str(report["status"]).startswith("blocked")),
        "failed": sum(1 for report in reports if report["status"] in {"invalid_config", "unsupported_entrypoint"} or (report["issues"] and not str(report["status"]).startswith("blocked"))),
        "executed": sum(1 for report in reports if report["executed"]),
        "runner_reports_hashed": sum(1 for report in reports if report.get("runner_report_sha256")),
        "output_artifacts_hashed": sum(1 for report in reports if report.get("output_artifact", {}).get("sha256")),
    }
    batch_report = {
        "root": str(Path.cwd()),
        "config_dir": str(config_dir),
        "output_dir": str(output_dir),
        "dry_run_external": dry_run_external,
        "allow_llm_api": allow_llm_api,
        "allow_external_runner": allow_external_runner,
        "reports": reports,
        "summary": summary,
        "passed": summary["failed"] == 0 and summary["blocked"] == 0,
    }
    write_json(output_dir / "baseline_batch_report.json", batch_report)
    return batch_report


def validate_baseline_config_dir(config_dir: Path, output_path: Path | None = None, strict_paths: bool = False) -> dict[str, Any]:
    config_dir = Path(config_dir)
    reports = [validate_baseline_config(path, strict_paths=strict_paths) for path in sorted(config_dir.glob("*.yaml"))]
    report = {
        "root": str(Path.cwd()),
        "config_dir": str(config_dir),
        "strict_paths": strict_paths,
        "configs": reports,
        "summary": {
            "configs_total": len(reports),
            "configs_passed": sum(1 for item in reports if item["passed"]),
            "configs_failed": sum(1 for item in reports if not item["passed"]),
            "configs_hashed": sum(1 for item in reports if item.get("sha256")),
            "warnings_total": sum(len(item["warnings"]) for item in reports),
        },
        "passed": all(item["passed"] for item in reports),
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def verify_baseline_config_validation_report(
    report_path: Path,
    output_path: Path | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Verify that a baseline-config validation report still matches its YAML inputs."""

    report_path = Path(report_path)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    config_results: dict[str, dict[str, Any]] = {}

    if not report_path.exists():
        report = {
            "passed": False,
            "report_path": str(report_path),
            "summary": {
                "configs_total": 0,
                "configs_verified": 0,
                "issues": 1,
                "warnings": 0,
                "issue_codes": ["baseline_config_validation_report_missing"],
                "warning_codes": [],
            },
            "configs": {},
            "issues": [
                {
                    "code": "baseline_config_validation_report_missing",
                    "message": "baseline config validation report is missing",
                    "path": str(report_path),
                }
            ],
            "warnings": [],
        }
        if output_path is not None:
            write_json(output_path, report)
        return report

    source = read_json(report_path)
    source_root = Path(root or source.get("root") or Path.cwd())
    source_summary = source.get("summary", {}) if isinstance(source.get("summary"), dict) else {}
    strict_paths = bool(source.get("strict_paths", False))

    if source.get("passed") is not True or int(source_summary.get("configs_failed", 0)) > 0:
        _issue(issues, "baseline_config_validation_not_passed", "baseline config validation report did not pass", report_path)

    expected_configs = source.get("configs", [])
    if not isinstance(expected_configs, list) or not expected_configs:
        _issue(issues, "baseline_config_records_missing", "baseline config validation report has no config records", report_path)
        expected_configs = []
    _check_baseline_config_summary(source_summary, expected_configs, issues, report_path)

    expected_paths: list[Path] = []
    for index, expected in enumerate(expected_configs):
        if not isinstance(expected, dict):
            _issue(issues, "baseline_config_record_invalid", f"baseline config record is not an object: {index}", report_path)
            continue
        expected_path_value = expected.get("config_path") or expected.get("path")
        key = str(expected_path_value or f"config_{index}")
        path = _resolve_path(Path(str(expected_path_value or "")), source_root)
        expected_paths.append(path)
        result = {
            "path": str(path),
            "expected_passed": expected.get("passed"),
            "expected_sha256": expected.get("sha256"),
            "expected_bytes": expected.get("bytes"),
            "actual_sha256": None,
            "actual_bytes": None,
            "current_validation_passed": None,
            "passed": True,
        }
        config_results[key] = result

        if expected.get("passed") is not True:
            result["passed"] = False
            _issue(issues, "baseline_config_source_failed", f"baseline config did not pass in the source report: {key}", path)
        if not path.exists():
            result["passed"] = False
            _issue(issues, "baseline_config_file_missing", f"baseline config file is missing: {key}", path)
            continue
        if not expected.get("sha256"):
            result["passed"] = False
            _issue(issues, "baseline_config_digest_missing", f"baseline config report lacks a source digest: {key}", path)
            continue

        actual_sha256 = _file_sha256(path)
        actual_bytes = path.stat().st_size
        result["actual_sha256"] = actual_sha256
        result["actual_bytes"] = actual_bytes
        if expected.get("sha256") != actual_sha256:
            result["passed"] = False
            _issue(issues, "baseline_config_sha256_mismatch", f"baseline config file changed: {key}", path)
        if expected.get("bytes") is not None and expected.get("bytes") != actual_bytes:
            result["passed"] = False
            _issue(issues, "baseline_config_bytes_mismatch", f"baseline config file size changed: {key}", path)

        current_validation = validate_baseline_config(path, strict_paths=strict_paths)
        result["current_validation_passed"] = current_validation["passed"]
        result["current_validation_issues"] = current_validation["issues"]
        if current_validation["passed"] is not True:
            result["passed"] = False
            _issue(issues, "baseline_config_current_validation_failed", f"baseline config no longer validates: {key}", path)

    config_dir = _resolve_path(Path(str(source.get("config_dir", ""))), source_root) if source.get("config_dir") else None
    current_config_paths: list[Path] = []
    if config_dir is None:
        _issue(issues, "baseline_config_dir_missing", "baseline config validation report does not record config_dir", report_path)
    elif not config_dir.exists():
        _issue(issues, "baseline_config_dir_missing", "baseline config directory is missing", config_dir)
    else:
        current_config_paths = sorted(config_dir.glob("*.yaml"))
        expected_set = {str(path.resolve()) for path in expected_paths}
        current_set = {str(path.resolve()) for path in current_config_paths}
        if expected_set != current_set:
            _issue(
                issues,
                "baseline_config_set_changed",
                "baseline config YAML set changed since validation report generation",
                config_dir,
            )

    summary = {
        "configs_total": len(config_results),
        "configs_verified": sum(1 for result in config_results.values() if result["passed"]),
        "current_configs_total": len(current_config_paths),
        "source_configs_failed": int(source_summary.get("configs_failed", 0)),
        "issues": len(issues),
        "warnings": len(warnings),
        "issue_codes": sorted({issue["code"] for issue in issues}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
    }
    report = {
        "passed": not issues,
        "report_path": str(report_path),
        "root": str(source_root),
        "source_summary": source_summary,
        "summary": summary,
        "configs": config_results,
        "issues": issues,
        "warnings": warnings,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def verify_baseline_batch_report(
    report_path: Path,
    output_path: Path | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Verify that a baseline batch report still matches runner reports and outputs."""

    report_path = Path(report_path)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    report_results: dict[str, dict[str, Any]] = {}

    if not report_path.exists():
        report = {
            "passed": False,
            "report_path": str(report_path),
            "summary": {
                "reports_total": 0,
                "runner_reports_verified": 0,
                "output_artifacts_verified": 0,
                "issues": 1,
                "warnings": 0,
                "issue_codes": ["baseline_batch_report_missing"],
                "warning_codes": [],
            },
            "reports": {},
            "issues": [
                {
                    "code": "baseline_batch_report_missing",
                    "message": "baseline batch report is missing",
                    "path": str(report_path),
                }
            ],
            "warnings": [],
        }
        if output_path is not None:
            write_json(output_path, report)
        return report

    source = read_json(report_path)
    source_root = Path(root or source.get("root") or Path.cwd())
    source_summary = source.get("summary", {}) if isinstance(source.get("summary"), dict) else {}

    if source.get("passed") is not True:
        _issue(issues, "baseline_batch_not_passed", "baseline batch report did not pass", report_path)
    if int(source_summary.get("blocked", 0)) > 0:
        _issue(issues, "baseline_batch_has_blocked_configs", "baseline batch has blocked configs", report_path)
    if int(source_summary.get("failed", 0)) > 0:
        _issue(issues, "baseline_batch_has_failed_configs", "baseline batch has failed configs", report_path)

    expected_reports = source.get("reports", [])
    if not isinstance(expected_reports, list) or not expected_reports:
        _issue(issues, "baseline_batch_records_missing", "baseline batch report has no runner records", report_path)
        expected_reports = []
    _check_baseline_batch_summary(source_summary, expected_reports, issues, report_path)

    for index, expected in enumerate(expected_reports):
        if not isinstance(expected, dict):
            _issue(issues, "baseline_batch_record_invalid", f"baseline batch runner record is not an object: {index}", report_path)
            continue
        key = str(expected.get("baseline_name") or expected.get("config_path") or f"report_{index}")
        result = {
            "baseline_name": expected.get("baseline_name"),
            "status": expected.get("status"),
            "executed": expected.get("executed"),
            "runner_report_path": expected.get("runner_report_path"),
            "output_path": expected.get("output_path"),
            "runner_report_verified": False,
            "output_artifact_verified": False,
            "passed": True,
        }
        report_results[key] = result

        _verify_runner_report_record(key, expected, source_root, result, issues)
        _verify_output_artifact_record(key, expected, source_root, result, issues)

    summary = {
        "reports_total": len(report_results),
        "runner_reports_verified": sum(1 for result in report_results.values() if result["runner_report_verified"]),
        "output_artifacts_verified": sum(1 for result in report_results.values() if result["output_artifact_verified"]),
        "source_failed": int(source_summary.get("failed", 0)),
        "source_blocked": int(source_summary.get("blocked", 0)),
        "issues": len(issues),
        "warnings": len(warnings),
        "issue_codes": sorted({issue["code"] for issue in issues}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
    }
    report = {
        "passed": not issues,
        "report_path": str(report_path),
        "root": str(source_root),
        "source_summary": source_summary,
        "summary": summary,
        "reports": report_results,
        "issues": issues,
        "warnings": warnings,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def _verify_runner_report_record(
    key: str,
    expected: dict[str, Any],
    source_root: Path,
    result: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    runner_report_path = expected.get("runner_report_path")
    if not runner_report_path:
        result["passed"] = False
        _issue(issues, "baseline_batch_runner_report_path_missing", f"baseline batch runner record lacks runner_report_path: {key}")
        return

    path = _resolve_path(Path(str(runner_report_path)), source_root)
    result["runner_report_path"] = str(path)
    if not path.exists():
        result["passed"] = False
        _issue(issues, "baseline_batch_runner_report_missing", f"baseline runner report is missing: {key}", path)
        return
    expected_sha256 = expected.get("runner_report_sha256")
    if not expected_sha256:
        result["passed"] = False
        _issue(issues, "baseline_batch_runner_report_digest_missing", f"baseline runner report lacks a digest: {key}", path)
        return

    actual_sha256 = _file_sha256(path)
    actual_bytes = path.stat().st_size
    result["expected_runner_report_sha256"] = expected_sha256
    result["actual_runner_report_sha256"] = actual_sha256
    result["expected_runner_report_bytes"] = expected.get("runner_report_bytes")
    result["actual_runner_report_bytes"] = actual_bytes
    runner_report_passed = True
    if expected_sha256 != actual_sha256:
        result["passed"] = False
        runner_report_passed = False
        _issue(issues, "baseline_batch_runner_report_sha256_mismatch", f"baseline runner report changed: {key}", path)
    if expected.get("runner_report_bytes") is not None and expected.get("runner_report_bytes") != actual_bytes:
        result["passed"] = False
        runner_report_passed = False
        _issue(issues, "baseline_batch_runner_report_bytes_mismatch", f"baseline runner report size changed: {key}", path)

    try:
        runner_report = read_json(path)
    except Exception as exc:
        result["passed"] = False
        _issue(issues, "baseline_batch_runner_report_unreadable", f"baseline runner report cannot be read: {key}: {exc}", path)
        return
    for field in ["config_path", "baseline_name", "dry_run", "executed", "status", "output_path"]:
        if expected.get(field) != runner_report.get(field):
            result["passed"] = False
            runner_report_passed = False
            _issue(issues, "baseline_batch_runner_report_field_mismatch", f"baseline runner report field changed: {key}.{field}", path)
    if runner_report_passed:
        result["runner_report_verified"] = True


def _verify_output_artifact_record(
    key: str,
    expected: dict[str, Any],
    source_root: Path,
    result: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    output_artifact = expected.get("output_artifact")
    executed = expected.get("executed") is True
    if not isinstance(output_artifact, dict) or not output_artifact:
        if executed:
            result["passed"] = False
            _issue(issues, "baseline_batch_output_artifact_digest_missing", f"executed baseline lacks output artifact digest: {key}", expected.get("output_path"))
        return

    artifact_passed = True
    expected_path_value = output_artifact.get("path")
    if not expected_path_value:
        result["passed"] = False
        artifact_passed = False
        _issue(issues, "baseline_batch_output_artifact_path_missing", f"baseline output artifact record lacks a path: {key}")
        return
    path = _resolve_path(Path(str(expected_path_value)), source_root)
    result["output_artifact_path"] = str(path)
    actual = _artifact_record(path)
    result["expected_output_artifact_sha256"] = output_artifact.get("sha256")
    result["actual_output_artifact_sha256"] = actual.get("sha256")
    result["expected_output_artifact_bytes"] = output_artifact.get("bytes")
    result["actual_output_artifact_bytes"] = actual.get("bytes")
    result["expected_output_artifact_files"] = output_artifact.get("files")
    result["actual_output_artifact_files"] = actual.get("files")

    if executed and output_artifact.get("status") != "present":
        result["passed"] = False
        artifact_passed = False
        _issue(issues, "baseline_batch_output_artifact_not_present", f"executed baseline output artifact was not present when recorded: {key}", path)
    if output_artifact.get("status") != actual.get("status"):
        result["passed"] = False
        artifact_passed = False
        _issue(issues, "baseline_batch_output_artifact_status_mismatch", f"baseline output artifact status changed: {key}", path)
        return
    if actual.get("status") != "present":
        return
    if not output_artifact.get("sha256"):
        result["passed"] = False
        artifact_passed = False
        _issue(issues, "baseline_batch_output_artifact_digest_missing", f"baseline output artifact lacks a digest: {key}", path)
        return
    for field, code in [
        ("kind", "baseline_batch_output_artifact_kind_mismatch"),
        ("sha256", "baseline_batch_output_artifact_sha256_mismatch"),
        ("bytes", "baseline_batch_output_artifact_bytes_mismatch"),
        ("files", "baseline_batch_output_artifact_file_count_mismatch"),
    ]:
        if field in output_artifact and output_artifact.get(field) != actual.get(field):
            result["passed"] = False
            artifact_passed = False
            _issue(issues, code, f"baseline output artifact {field} changed: {key}", path)
    if artifact_passed:
        result["output_artifact_verified"] = True


def _check_baseline_batch_summary(
    source_summary: dict[str, Any],
    expected_reports: list[Any],
    issues: list[dict[str, Any]],
    report_path: Path,
) -> None:
    records = [item for item in expected_reports if isinstance(item, dict)]
    actual = {
        "configs_total": len(records),
        "completed": sum(1 for item in records if item.get("status") == "completed"),
        "dry_run": sum(1 for item in records if str(item.get("status")).startswith("dry_run")),
        "blocked": sum(1 for item in records if str(item.get("status")).startswith("blocked")),
        "failed": sum(
            1
            for item in records
            if item.get("status") in {"invalid_config", "unsupported_entrypoint"}
            or (item.get("issues") and not str(item.get("status")).startswith("blocked"))
        ),
        "executed": sum(1 for item in records if item.get("executed") is True),
        "runner_reports_hashed": sum(1 for item in records if item.get("runner_report_sha256")),
        "output_artifacts_hashed": sum(1 for item in records if item.get("output_artifact", {}).get("sha256")),
    }
    for key, value in actual.items():
        if source_summary.get(key) != value:
            _issue(
                issues,
                f"baseline_batch_summary_{key}_mismatch",
                f"baseline batch summary {key} does not match runner records",
                report_path,
            )


def _check_baseline_config_summary(
    source_summary: dict[str, Any],
    expected_configs: list[Any],
    issues: list[dict[str, Any]],
    report_path: Path,
) -> None:
    records = [item for item in expected_configs if isinstance(item, dict)]
    actual = {
        "configs_total": len(records),
        "configs_passed": sum(1 for item in records if item.get("passed") is True),
        "configs_failed": sum(1 for item in records if item.get("passed") is not True),
        "configs_hashed": sum(1 for item in records if item.get("sha256")),
    }
    for key, value in actual.items():
        if source_summary.get(key) != value:
            _issue(
                issues,
                f"baseline_config_summary_{key}_mismatch",
                f"baseline config validation summary {key} does not match config records",
                report_path,
            )


def _require_keys(mapping: dict[str, Any], required: set[str], label: str, issues: list[str]) -> None:
    missing = sorted(required - mapping.keys())
    if missing:
        issues.append(f"{label} missing required keys: {missing}")


def _mapping(value: Any, label: str, issues: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    issues.append(f"{label} must be a mapping")
    return {}


def _required_env(config: dict[str, Any]) -> list[str]:
    environment = config.get("environment", {})
    if not isinstance(environment, dict):
        return []
    required = environment.get("required", [])
    return required if isinstance(required, list) else []


def _runner_config(data: dict[str, Any], evaluation: dict[str, Any], issues: list[str]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    inline_config = evaluation.get("runner_config", {})
    if inline_config:
        if isinstance(inline_config, dict):
            config.update(inline_config)
        else:
            issues.append("evaluation.runner_config must be a mapping when set")
    config_path = data.get("runner_config_path") or evaluation.get("runner_config_path")
    if config_path:
        try:
            loaded = read_json(Path(str(config_path)))
        except Exception as exc:
            issues.append(f"failed to load runner_config_path {config_path}: {exc}")
            return config
        if isinstance(loaded, dict):
            config.update(loaded)
        else:
            issues.append("runner_config_path must point to a JSON object")
    return config


def _artifact_record(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {
            "path": str(path),
            "status": "missing",
            "kind": "missing",
        }
    if path.is_dir():
        files = sorted(item for item in path.rglob("*") if item.is_file())
        return {
            "path": str(path),
            "status": "present",
            "kind": "directory",
            "files": len(files),
            "bytes": sum(item.stat().st_size for item in files),
            "sha256": _directory_sha256(path, files),
        }
    return {
        "path": str(path),
        "status": "present",
        "kind": "file",
        "bytes": path.stat().st_size,
        "sha256": _file_sha256(path),
    }


def _directory_sha256(root: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        rel_path = path.relative_to(root).as_posix()
        digest.update(rel_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_file_sha256(path).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _resolve_path(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _issue(issues: list[dict[str, Any]], code: str, message: str, path: Path | str | None = None) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        item["path"] = str(path)
    issues.append(item)
