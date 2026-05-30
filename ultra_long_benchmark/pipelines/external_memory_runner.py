from __future__ import annotations

import importlib
import inspect
import traceback
from pathlib import Path
from typing import Any

from ultra_long_benchmark.models import ProjectPrediction, model_validate
from ultra_long_benchmark.project_release import verify_project_submission_inputs
from ultra_long_benchmark.shared.io import read_jsonl, write_json


def run_external_memory_submission_runner(
    input_dir: Path,
    predictions_path: Path,
    *,
    runner: str,
    report_path: Path | None = None,
    runner_config: dict[str, Any] | None = None,
    allow_external_runner: bool = False,
    system_name: str | None = None,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Run a user-supplied memory-system plugin on no-gold submission inputs.

    The benchmark side supplies only the `export-project-submission-inputs`
    directory and a prediction output path. The plugin is responsible for any
    Mem0/A-MEM/Graphiti-specific indexing, retrieval, model calls, and
    prediction generation, then must write `ProjectPrediction` JSONL.
    """

    input_dir = Path(input_dir)
    predictions_path = Path(predictions_path)
    runner_config = runner_config or {}
    system_name = system_name or _system_name_from_runner(runner)
    input_report = verify_project_submission_inputs(input_dir)
    input_issues = [issue.get("message", str(issue)) for issue in input_report.get("issues", [])]
    probe_rows = read_jsonl(input_dir / "probes.jsonl")
    event_rows = read_jsonl(input_dir / "events.jsonl")
    project_rows = read_jsonl(input_dir / "projects.jsonl")

    if input_issues:
        report = _external_runner_report(
            input_dir,
            predictions_path,
            runner=runner,
            system_name=system_name,
            status="invalid_input",
            executed=False,
            issues=input_issues,
            warnings=[],
            input_report=input_report,
            output_validation=None,
            runner_result=None,
            projects=project_rows,
            probes=probe_rows,
            events=event_rows,
        )
        if report_path is not None:
            write_json(report_path, report)
        return report

    if not allow_external_runner:
        report = _external_runner_report(
            input_dir,
            predictions_path,
            runner=runner,
            system_name=system_name,
            status="blocked_requires_external_runner",
            executed=False,
            issues=[
                "external memory runner execution requires --allow-external-runner; dry-run did not import or invoke the plugin"
            ],
            warnings=[],
            input_report=input_report,
            output_validation=None,
            runner_result=None,
            projects=project_rows,
            probes=probe_rows,
            events=event_rows,
        )
        if report_path is not None:
            write_json(report_path, report)
        return report

    try:
        target = _load_runner_target(runner)
        runner_result = _invoke_runner(
            target,
            input_dir=input_dir,
            predictions_path=predictions_path,
            config=runner_config,
            system_name=system_name,
        )
    except Exception as exc:
        report = _external_runner_report(
            input_dir,
            predictions_path,
            runner=runner,
            system_name=system_name,
            status="runner_failed",
            executed=True,
            issues=[f"external runner failed: {exc}"],
            warnings=[],
            input_report=input_report,
            output_validation=None,
            runner_result={"exception_type": type(exc).__name__, "traceback": traceback.format_exc()},
            projects=project_rows,
            probes=probe_rows,
            events=event_rows,
        )
        if report_path is not None:
            write_json(report_path, report)
        return report

    output_validation = validate_external_memory_predictions_against_input(
        input_dir,
        predictions_path,
        require_complete=require_complete,
    )
    output_issues = [issue["message"] for issue in output_validation["issues"]]
    status = "completed" if output_validation["passed"] else "output_validation_failed"
    report = _external_runner_report(
        input_dir,
        predictions_path,
        runner=runner,
        system_name=system_name,
        status=status,
        executed=True,
        issues=output_issues,
        warnings=[warning["message"] for warning in output_validation["warnings"]],
        input_report=input_report,
        output_validation=output_validation,
        runner_result=runner_result,
        projects=project_rows,
        probes=probe_rows,
        events=event_rows,
    )
    if report_path is not None:
        write_json(report_path, report)
    return report


def validate_external_memory_predictions_against_input(
    input_dir: Path,
    predictions_path: Path,
    *,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Validate plugin output against no-gold probe ids without reading gold."""

    input_dir = Path(input_dir)
    predictions_path = Path(predictions_path)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    probes = read_jsonl(input_dir / "probes.jsonl")
    expected_keys = {(str(probe.get("project_id")), str(probe.get("probe_id"))) for probe in probes}
    expected_project_ids = {project_id for project_id, _ in expected_keys}
    rows = read_jsonl(predictions_path)
    predictions: list[ProjectPrediction] = []
    seen_keys: set[tuple[str, str]] = set()
    seen_prediction_ids: set[str] = set()

    if not predictions_path.exists():
        _issue(issues, "prediction_output_missing", f"prediction output file is missing: {predictions_path}")

    for index, row in enumerate(rows, start=1):
        try:
            prediction = model_validate(ProjectPrediction, row)
        except Exception as exc:
            _issue(issues, "prediction_schema_invalid", f"row {index} does not match ProjectPrediction schema: {exc}")
            continue
        predictions.append(prediction)
        key = (prediction.project_id, prediction.probe_id)
        if prediction.prediction_id in seen_prediction_ids:
            _issue(issues, "prediction_duplicate_id", f"duplicate prediction_id {prediction.prediction_id}")
        seen_prediction_ids.add(prediction.prediction_id)
        if key in seen_keys:
            _issue(issues, "prediction_duplicate_probe", f"duplicate prediction for project/probe {key}")
        seen_keys.add(key)
        if key not in expected_keys:
            code = "prediction_unknown_project" if prediction.project_id not in expected_project_ids else "prediction_unknown_probe"
            _issue(issues, code, f"prediction references project/probe not present in submission input: {key}")
        if not prediction.prediction.strip():
            _issue(issues, "prediction_empty", f"empty prediction for project/probe {key}")

    missing_keys = sorted(expected_keys - seen_keys)
    extra_keys = sorted(seen_keys - expected_keys)
    if require_complete and missing_keys:
        _issue(issues, "prediction_missing_probes", f"missing predictions for {len(missing_keys)} input probes; first={missing_keys[:10]}")
    elif missing_keys:
        _warn(warnings, "prediction_partial_coverage", f"partial output is missing {len(missing_keys)} input probes")

    checks = {
        "coverage": {
            "input_probes": len(expected_keys),
            "prediction_rows": len(rows),
            "valid_prediction_rows": len(predictions),
            "covered_probes": len(expected_keys & seen_keys),
            "missing_probes": len(missing_keys),
            "extra_predictions": len(extra_keys),
            "probe_coverage": round(len(expected_keys & seen_keys) / max(1, len(expected_keys)), 4),
            "require_complete": require_complete,
        },
        "projects": {
            "input_projects": len(expected_project_ids),
            "submitted_projects": len({prediction.project_id for prediction in predictions}),
        },
    }
    return {
        "input_dir": str(input_dir),
        "predictions_path": str(predictions_path),
        "passed": not issues,
        "issues": issues,
        "warnings": warnings,
        "checks": checks,
        "summary": {
            "issues": len(issues),
            "warnings": len(warnings),
            "probe_coverage": checks["coverage"]["probe_coverage"],
        },
    }


def _external_runner_report(
    input_dir: Path,
    predictions_path: Path,
    *,
    runner: str,
    system_name: str,
    status: str,
    executed: bool,
    issues: list[str],
    warnings: list[str],
    input_report: dict[str, Any],
    output_validation: dict[str, Any] | None,
    runner_result: Any,
    projects: list[dict[str, Any]],
    probes: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    predictions = read_jsonl(predictions_path) if predictions_path.exists() else []
    return {
        "input_dir": str(input_dir),
        "predictions_path": str(predictions_path),
        "runner": runner,
        "system_name": system_name,
        "status": status,
        "executed": executed,
        "issues": issues,
        "warnings": warnings,
        "summary": {
            "projects": len({str(project.get("project_id")) for project in projects}),
            "probes": len(probes),
            "events": len(events),
            "predictions": len(predictions),
            "input_contract_passed": bool(input_report.get("passed")),
            "output_validation_passed": bool(output_validation.get("passed")) if output_validation is not None else False,
        },
        "constraints": {
            "benchmark_supplies_submission_inputs_only": True,
            "release_gold_supplied_to_runner": False,
            "uses_gold_memory_graph": False,
            "uses_probe_expected_behavior": False,
            "uses_gold_evidence_ids": False,
            "external_dependency_invoked": executed,
        },
        "risk_notes": [
            "The harness passes only the no-gold input_dir and predictions_path to the plugin.",
            "The plugin is arbitrary local code; run it in a controlled environment if dependency/API side effects matter.",
        ],
        "input_report": input_report,
        "output_validation": output_validation,
        "runner_result": runner_result,
    }


def _load_runner_target(runner: str) -> Any:
    if ":" not in runner:
        raise ValueError("runner must use module:object syntax, for example my_mem0_runner:run")
    module_name, target_name = runner.split(":", 1)
    if not module_name or not target_name:
        raise ValueError("runner must use module:object syntax with both parts present")
    module = importlib.import_module(module_name)
    target: Any = module
    for part in target_name.split("."):
        if not part:
            raise ValueError(f"invalid empty attribute in runner target: {runner}")
        target = getattr(target, part)
    return target


def _invoke_runner(target: Any, *, input_dir: Path, predictions_path: Path, config: dict[str, Any], system_name: str) -> Any:
    if inspect.isclass(target):
        instance = _call_with_supported_kwargs(target, config=config, system_name=system_name)
        if not hasattr(instance, "run"):
            raise TypeError("runner class must expose a run(...) method")
        return _call_with_supported_kwargs(
            instance.run,
            input_dir=input_dir,
            predictions_path=predictions_path,
            config=config,
            system_name=system_name,
        )
    if hasattr(target, "run") and callable(target.run):
        return _call_with_supported_kwargs(
            target.run,
            input_dir=input_dir,
            predictions_path=predictions_path,
            config=config,
            system_name=system_name,
        )
    if callable(target):
        return _call_with_supported_kwargs(
            target,
            input_dir=input_dir,
            predictions_path=predictions_path,
            config=config,
            system_name=system_name,
        )
    raise TypeError("runner target must be a callable, a class, or an object with run(...)")


def _call_with_supported_kwargs(callable_obj: Any, **kwargs: Any) -> Any:
    signature = inspect.signature(callable_obj)
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
        return callable_obj(**kwargs)
    accepted = {name: value for name, value in kwargs.items() if name in signature.parameters}
    missing = [
        name
        for name, parameter in signature.parameters.items()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        and name not in accepted
    ]
    if missing:
        raise TypeError(f"runner callable has unsupported required parameters: {missing}")
    return callable_obj(**accepted)


def _system_name_from_runner(runner: str) -> str:
    return runner.replace(":", ".").replace("/", ".")


def _issue(issues: list[dict[str, Any]], code: str, message: str) -> None:
    issues.append({"code": code, "message": message})


def _warn(warnings: list[dict[str, Any]], code: str, message: str) -> None:
    warnings.append({"code": code, "message": message})
