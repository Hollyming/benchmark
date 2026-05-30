from __future__ import annotations

from pathlib import Path
from typing import Any

from ultra_long_benchmark.shared.io import load_yaml, write_json


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
        score_project_predictions,
        score_project_release_prediction_dir,
        score_project_release_predictions,
    )
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
    project_dir = Path(data["project_dir"])
    baseline_output = Path(data["output_path"])
    if mode == "project_probe_text" and baseline.get("entrypoint") == "ultra_long_benchmark.cli:evaluate-project":
        result = run_project_baseline_evaluation(
            project_dir,
            baseline_output,
            top_k=int(evaluation.get("top_k", 5)),
            baseline_names=evaluation.get("baselines"),
        )
        report["executed"] = True
        report["status"] = "completed"
        report["result_summary"] = result["summary"]
    elif mode == "project_probe_action_trace" and baseline.get("entrypoint") == "ultra_long_benchmark.cli:score-action-traces":
        traces_path = data.get("traces_path")
        if not traces_path:
            report["status"] = "blocked_missing_traces_path"
            report["issues"].append("project_probe_action_trace config requires data.traces_path")
        else:
            result = score_action_traces(project_dir, Path(traces_path), baseline_output)
            report["executed"] = True
            report["status"] = "completed"
            report["result_summary"] = result["summary"]
    elif mode == "project_probe_prediction_submission" and baseline.get("entrypoint") == "ultra_long_benchmark.cli:score-project-predictions":
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
    elif mode == "submission_input_prediction_generation" and baseline.get("entrypoint") == "ultra_long_benchmark.cli:run-submission-input-baseline":
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
    elif mode == "memory_submission_prediction_generation" and baseline.get("entrypoint") == "ultra_long_benchmark.cli:run-memory-submission-baseline":
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
            )
            report["executed"] = bool(result.get("executed"))
            report["status"] = "completed" if result.get("status") == "completed" else str(result.get("status"))
            report["result_summary"] = result["summary"]
            report["issues"].extend(str(issue) for issue in result.get("issues", []))
    elif mode == "project_release_prediction_submission" and baseline.get("entrypoint") == "ultra_long_benchmark.cli:score-project-release-predictions":
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
    elif mode == "project_release_prediction_submission_validation" and baseline.get("entrypoint") == "ultra_long_benchmark.cli:validate-project-prediction-submission":
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
    elif mode == "project_release_prediction_submission_dir" and baseline.get("entrypoint") == "ultra_long_benchmark.cli:score-project-release-prediction-dir":
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
) -> dict[str, Any]:
    """Run a directory of baseline configs with explicit external-system gates."""

    config_dir = Path(config_dir)
    output_dir = Path(output_dir)
    reports = []
    for config_path in sorted(config_dir.glob("*.yaml")):
        config = load_yaml(config_path)
        baseline = config.get("baseline", {}) if isinstance(config, dict) else {}
        dry_run = bool(dry_run_external and baseline.get("requires_llm_api"))
        report_path = output_dir / f"{config_path.stem}_runner_report.json"
        reports.append(
            run_baseline_config(
                config_path,
                output_path=report_path,
                dry_run=dry_run,
                allow_llm_api=allow_llm_api,
            )
        )

    summary = {
        "configs_total": len(reports),
        "completed": sum(1 for report in reports if report["status"] == "completed"),
        "dry_run": sum(1 for report in reports if str(report["status"]).startswith("dry_run")),
        "blocked": sum(1 for report in reports if str(report["status"]).startswith("blocked")),
        "failed": sum(1 for report in reports if report["status"] in {"invalid_config", "unsupported_entrypoint"} or (report["issues"] and not str(report["status"]).startswith("blocked"))),
        "executed": sum(1 for report in reports if report["executed"]),
    }
    batch_report = {
        "config_dir": str(config_dir),
        "output_dir": str(output_dir),
        "dry_run_external": dry_run_external,
        "allow_llm_api": allow_llm_api,
        "reports": reports,
        "summary": summary,
        "passed": summary["failed"] == 0 and (allow_llm_api or summary["blocked"] == 0),
    }
    write_json(output_dir / "baseline_batch_report.json", batch_report)
    return batch_report


def validate_baseline_config_dir(config_dir: Path, output_path: Path | None = None, strict_paths: bool = False) -> dict[str, Any]:
    config_dir = Path(config_dir)
    reports = [validate_baseline_config(path, strict_paths=strict_paths) for path in sorted(config_dir.glob("*.yaml"))]
    report = {
        "config_dir": str(config_dir),
        "configs": reports,
        "summary": {
            "configs_total": len(reports),
            "configs_passed": sum(1 for item in reports if item["passed"]),
            "configs_failed": sum(1 for item in reports if not item["passed"]),
            "warnings_total": sum(len(item["warnings"]) for item in reports),
        },
        "passed": all(item["passed"] for item in reports),
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


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
