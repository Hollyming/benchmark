from __future__ import annotations

import importlib.util
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from ultra_long_benchmark.models import ProjectPrediction, model_validate
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_json, write_jsonl


LOCAL_MEMORY_SUBMISSION_ADAPTERS = ("event_profile_stub",)
EXTERNAL_MEMORY_SUBMISSION_ADAPTERS = ("mem0", "a_mem", "graphiti")
SUPPORTED_MEMORY_SUBMISSION_ADAPTERS = LOCAL_MEMORY_SUBMISSION_ADAPTERS + EXTERNAL_MEMORY_SUBMISSION_ADAPTERS
EXTERNAL_ADAPTER_SPECS = {
    "mem0": {
        "display_name": "Mem0",
        "python_modules": ["mem0"],
        "required_env": ["OPENAI_API_KEY"],
        "optional_env": ["ULB_OPENAI_BASE_URL", "OPENAI_BASE_URL", "HF_HOME"],
        "requires_gpu": True,
        "recommended_partition": "RTX4090",
        "notes": "Install/configure Mem0 and a provider model before enabling execution. This harness does not vendor Mem0.",
    },
    "a_mem": {
        "display_name": "A-MEM",
        "python_modules": ["a_mem"],
        "required_env": ["OPENAI_API_KEY"],
        "optional_env": ["ULB_OPENAI_BASE_URL", "OPENAI_BASE_URL", "HF_HOME"],
        "requires_gpu": True,
        "recommended_partition": "RTX4090",
        "notes": "A-MEM has no in-repo implementation here; add a method-specific runner that emits ProjectPrediction JSONL.",
    },
    "graphiti": {
        "display_name": "Graphiti/Zep temporal KG",
        "python_modules": ["graphiti_core"],
        "required_env": ["OPENAI_API_KEY"],
        "optional_env": ["ULB_OPENAI_BASE_URL", "OPENAI_BASE_URL", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"],
        "requires_gpu": False,
        "recommended_partition": "cpu",
        "notes": "Graphiti usually needs a graph storage backend plus provider credentials; configure those before execution.",
    },
}


def supported_memory_submission_adapters() -> tuple[str, ...]:
    return SUPPORTED_MEMORY_SUBMISSION_ADAPTERS


def plan_external_memory_submission_adapter(
    input_dir: Path,
    predictions_path: Path,
    *,
    adapter: str,
    report_path: Path | None = None,
    system_name: str | None = None,
) -> dict[str, Any]:
    """Return dependency and command guidance for a gated external adapter."""

    adapter = _validate_adapter(adapter)
    if adapter not in EXTERNAL_MEMORY_SUBMISSION_ADAPTERS:
        raise ValueError(f"adapter is not external: {adapter}")
    input_dir = Path(input_dir)
    predictions_path = Path(predictions_path)
    system_name = system_name or adapter
    report = _external_adapter_report(
        input_dir,
        predictions_path,
        adapter=adapter,
        allow_external=True,
        system_name=system_name,
    )
    report["status"] = "plan_ready" if not report["checks"]["missing_input_files"] else "plan_input_incomplete"
    report["issues"] = []
    if report["checks"]["missing_input_files"]:
        report["issues"].append("submission input pack is incomplete")
    if report_path is not None:
        write_json(report_path, report)
    return report


def run_memory_submission_baseline(
    input_dir: Path,
    predictions_path: Path,
    *,
    adapter: str = "event_profile_stub",
    top_k: int = 5,
    report_path: Path | None = None,
    allow_external: bool = False,
    system_name: str | None = None,
    provider_config_path: Path | None = None,
    model: str | None = None,
    max_output_tokens: int = 512,
    request_timeout: float = 60.0,
    max_retries: int = 3,
    retry_backoff_seconds: float = 2.0,
) -> dict[str, Any]:
    """Generate ProjectPrediction JSONL from no-gold submission inputs.

    This runner is the common contract for memory-system baselines. The local
    `event_profile_stub` adapter is deterministic and reads only exported
    no-gold submission files. External systems such as Mem0, A-MEM, and
    Graphiti are deliberately gated so benchmark scripts cannot call APIs or
    non-repo dependencies without an explicit opt-in runner.
    """

    input_dir = Path(input_dir)
    predictions_path = Path(predictions_path)
    adapter = _validate_adapter(adapter)
    system_name = system_name or adapter

    if adapter in EXTERNAL_MEMORY_SUBMISSION_ADAPTERS:
        if allow_external:
            report = _run_openai_compatible_memory_adapter(
                input_dir,
                predictions_path,
                adapter=adapter,
                top_k=top_k,
                report_path=report_path,
                system_name=system_name,
                provider_config_path=provider_config_path,
                model=model,
                max_output_tokens=max_output_tokens,
                request_timeout=request_timeout,
                max_retries=max_retries,
                retry_backoff_seconds=retry_backoff_seconds,
            )
            return report
        report = _external_adapter_report(
            input_dir,
            predictions_path,
            adapter=adapter,
            allow_external=False,
            system_name=system_name,
        )
        if report_path is not None:
            write_json(report_path, report)
        return report

    input_issues = _submission_input_issues(input_dir)
    if input_issues:
        report = _runner_report(
            input_dir,
            predictions_path,
            adapter=adapter,
            system_name=system_name,
            status="invalid_input",
            executed=False,
            issues=input_issues,
            projects=[],
            probes=[],
            events=[],
            predictions=[],
            top_k=top_k,
        )
        if report_path is not None:
            write_json(report_path, report)
        return report

    projects = read_jsonl(input_dir / "projects.jsonl")
    events = read_jsonl(input_dir / "events.jsonl")
    probes = read_jsonl(input_dir / "probes.jsonl")
    events_by_project: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        events_by_project.setdefault(str(event.get("project_id")), []).append(event)

    profiles = {
        project_id: _build_event_profile(project_id, project_events)
        for project_id, project_events in sorted(events_by_project.items())
    }
    prediction_rows: list[dict[str, Any]] = []
    for probe in probes:
        project_id = str(probe.get("project_id"))
        project_events = events_by_project.get(project_id, [])
        retrieved = _retrieve_events_for_probe(probe, project_events, top_k=top_k)
        row = _event_profile_prediction_row(probe, profiles.get(project_id, {}), retrieved, system_name=system_name)
        model_validate(ProjectPrediction, row)
        prediction_rows.append(row)

    write_jsonl(predictions_path, prediction_rows)
    report = _runner_report(
        input_dir,
        predictions_path,
        adapter=adapter,
        system_name=system_name,
        status="completed",
        executed=True,
        issues=[],
        projects=projects,
        probes=probes,
        events=events,
        predictions=prediction_rows,
        top_k=top_k,
    )
    if report_path is not None:
        write_json(report_path, report)
    return report


def _validate_adapter(adapter: str) -> str:
    adapter = str(adapter)
    if adapter not in SUPPORTED_MEMORY_SUBMISSION_ADAPTERS:
        raise ValueError(f"unsupported memory submission adapter: {adapter}; supported={sorted(SUPPORTED_MEMORY_SUBMISSION_ADAPTERS)}")
    return adapter


def _submission_input_issues(input_dir: Path) -> list[str]:
    issues = []
    for filename in ["projects.jsonl", "events.jsonl", "probes.jsonl", "submission_manifest.json"]:
        path = input_dir / filename
        if not path.exists():
            issues.append(f"missing no-gold submission input file: {path}")
    if (input_dir / "submission_manifest.json").exists():
        manifest = read_json(input_dir / "submission_manifest.json")
        constraints = manifest.get("constraints", {}) if isinstance(manifest, dict) else {}
        if constraints.get("contains_gold_memory_graph") is not False:
            issues.append("submission manifest does not explicitly declare contains_gold_memory_graph=false")
        if constraints.get("contains_probe_expected_behavior") is not False:
            issues.append("submission manifest does not explicitly declare contains_probe_expected_behavior=false")
    return issues


def _external_adapter_report(
    input_dir: Path,
    predictions_path: Path,
    *,
    adapter: str,
    allow_external: bool,
    system_name: str,
) -> dict[str, Any]:
    spec = EXTERNAL_ADAPTER_SPECS[adapter]
    input_issues = _submission_input_issues(input_dir)
    dependency_check = _external_dependency_check(adapter)
    status = "blocked_external_adapter_not_implemented" if allow_external else "blocked_requires_external_adapter"
    issue = _external_blocking_issue(adapter, allow_external=allow_external, dependency_check=dependency_check)
    return {
        "input_dir": str(input_dir),
        "predictions_path": str(predictions_path),
        "adapter": adapter,
        "system_name": system_name,
        "status": status,
        "executed": False,
        "issues": [issue],
        "warnings": [],
        "summary": {
            "projects": len(read_jsonl(input_dir / "projects.jsonl")) if (input_dir / "projects.jsonl").exists() else 0,
            "probes": len(read_jsonl(input_dir / "probes.jsonl")) if (input_dir / "probes.jsonl").exists() else 0,
            "predictions": 0,
            "events": len(read_jsonl(input_dir / "events.jsonl")) if (input_dir / "events.jsonl").exists() else 0,
            "retrieved_events_total": 0,
        },
        "constraints": _runner_constraints(external_dependency_invoked=False),
        "external_adapter": {
            "display_name": spec["display_name"],
            "requires_gpu": spec["requires_gpu"],
            "recommended_partition": spec["recommended_partition"],
            "python_modules": spec["python_modules"],
            "required_env": spec["required_env"],
            "optional_env": spec["optional_env"],
            "notes": spec["notes"],
        },
        "checks": {
            "input_contract_passed": not input_issues,
            "missing_input_files": input_issues,
            "dependencies": dependency_check,
        },
        "next_steps": _external_next_steps(adapter, input_dir, predictions_path, system_name=system_name),
    }


def _external_dependency_check(adapter: str) -> dict[str, Any]:
    spec = EXTERNAL_ADAPTER_SPECS[adapter]
    module_status = {
        module: importlib.util.find_spec(module) is not None
        for module in spec["python_modules"]
    }
    env_status = {
        name: bool(os.environ.get(name))
        for name in spec["required_env"]
    }
    optional_env_status = {
        name: bool(os.environ.get(name))
        for name in spec["optional_env"]
    }
    return {
        "python_modules": module_status,
        "required_env": env_status,
        "optional_env": optional_env_status,
        "modules_ready": all(module_status.values()),
        "required_env_ready": all(env_status.values()),
        "ready_for_external_execution": all(module_status.values()) and all(env_status.values()),
    }


def _external_blocking_issue(adapter: str, *, allow_external: bool, dependency_check: dict[str, Any]) -> str:
    if not allow_external:
        return f"{adapter} requires an explicit external runner/API opt-in; dry-run only"
    if not dependency_check["ready_for_external_execution"]:
        return f"{adapter} dependencies or required environment variables are missing; external execution was not invoked"
    return f"{adapter} dependency preflight passed, but method-specific execution is not implemented in this repository yet"


def _external_next_steps(adapter: str, input_dir: Path, predictions_path: Path, *, system_name: str) -> dict[str, Any]:
    score_path = predictions_path.with_suffix(".score.json")
    validation_path = predictions_path.with_suffix(".validation.json")
    return {
        "runner_contract": "Implement a method-specific runner that reads the no-gold input_dir and writes ProjectPrediction JSONL to predictions_path.",
        "prediction_schema": {
            "required": ["prediction_id", "project_id", "probe_id", "prediction"],
            "optional": ["retrieved_memory_ids", "retrieved_event_ids", "retrieved_artifact_ids", "metadata"],
        },
        "recommended_commands": [
            f"python -m ultra_long_benchmark.cli run-memory-submission-baseline {input_dir} --adapter {adapter} --predictions {predictions_path} --allow-external --system-name {system_name}",
            f"python -m ultra_long_benchmark.cli validate-project-prediction-submission <project_release_dir> {predictions_path} --output {validation_path}",
            f"python -m ultra_long_benchmark.cli score-project-release-predictions <project_release_dir> {predictions_path} --output {score_path} --system-name {system_name}",
        ],
    }


def _runner_report(
    input_dir: Path,
    predictions_path: Path,
    *,
    adapter: str,
    system_name: str,
    status: str,
    executed: bool,
    issues: list[str],
    projects: list[dict[str, Any]],
    probes: list[dict[str, Any]],
    events: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    top_k: int,
) -> dict[str, Any]:
    return {
        "input_dir": str(input_dir),
        "predictions_path": str(predictions_path),
        "adapter": adapter,
        "system_name": system_name,
        "status": status,
        "executed": executed,
        "top_k": top_k,
        "issues": issues,
        "warnings": [],
        "summary": {
            "projects": len({str(project.get("project_id")) for project in projects}),
            "probes": len(probes),
            "predictions": len(predictions),
            "events": len(events),
            "retrieved_events_total": sum(len(row.get("retrieved_event_ids", [])) for row in predictions),
        },
        "constraints": _runner_constraints(external_dependency_invoked=False),
    }


def _run_openai_compatible_memory_adapter(
    input_dir: Path,
    predictions_path: Path,
    *,
    adapter: str,
    top_k: int,
    report_path: Path | None,
    system_name: str,
    provider_config_path: Path | None,
    model: str | None,
    max_output_tokens: int,
    request_timeout: float,
    max_retries: int,
    retry_backoff_seconds: float,
) -> dict[str, Any]:
    input_issues = _submission_input_issues(input_dir)
    if input_issues:
        report = _runner_report(
            input_dir,
            predictions_path,
            adapter=adapter,
            system_name=system_name,
            status="invalid_input",
            executed=False,
            issues=input_issues,
            projects=[],
            probes=[],
            events=[],
            predictions=[],
            top_k=top_k,
        )
        report["constraints"] = _runner_constraints(external_dependency_invoked=False)
        if report_path is not None:
            write_json(report_path, report)
        return report

    try:
        provider = _load_openai_compatible_provider(provider_config_path, model=model)
    except Exception as exc:
        projects = read_jsonl(input_dir / "projects.jsonl")
        probes = read_jsonl(input_dir / "probes.jsonl")
        events = read_jsonl(input_dir / "events.jsonl")
        report = _runner_report(
            input_dir,
            predictions_path,
            adapter=adapter,
            system_name=system_name,
            status="blocked_missing_provider_config",
            executed=False,
            issues=[str(exc)],
            projects=projects,
            probes=probes,
            events=events,
            predictions=[],
            top_k=top_k,
        )
        report["constraints"] = _runner_constraints(external_dependency_invoked=False)
        report["external_adapter"] = _external_adapter_metadata(adapter)
        if report_path is not None:
            write_json(report_path, report)
        return report

    projects = read_jsonl(input_dir / "projects.jsonl")
    events = read_jsonl(input_dir / "events.jsonl")
    probes = read_jsonl(input_dir / "probes.jsonl")
    events_by_project: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        events_by_project.setdefault(str(event.get("project_id")), []).append(event)
    profiles = {
        project_id: _build_event_profile(project_id, project_events)
        for project_id, project_events in sorted(events_by_project.items())
    }

    prediction_rows, skipped_predictions, resume_warnings = _load_resume_predictions(predictions_path, probes)
    loaded_existing_predictions = len(prediction_rows)
    completed_keys = {(str(row.get("project_id")), str(row.get("probe_id"))) for row in prediction_rows}
    issues: list[str] = []
    warnings: list[str] = list(resume_warnings)
    status = "completed"
    for probe in probes:
        project_id = str(probe.get("project_id"))
        probe_id = str(probe.get("probe_id"))
        if (project_id, probe_id) in completed_keys:
            continue
        project_events = events_by_project.get(project_id, [])
        retrieved = _retrieve_events_for_probe(probe, project_events, top_k=top_k)
        messages = _openai_compatible_memory_messages(adapter, probe, profiles.get(project_id, {}), retrieved)
        try:
            response_text = _openai_chat_completion_with_retry(
                provider,
                messages,
                max_output_tokens=max_output_tokens,
                request_timeout=request_timeout,
                max_retries=max_retries,
                retry_backoff_seconds=retry_backoff_seconds,
            )
        except Exception as exc:
            status = "provider_api_failed"
            issues.append(f"provider API call failed for {project_id}/{probe.get('probe_id')}: {exc}")
            break
        row = _external_llm_prediction_row(
            probe,
            retrieved,
            prediction_text=response_text,
            adapter=adapter,
            system_name=system_name,
            provider=provider,
        )
        model_validate(ProjectPrediction, row)
        prediction_rows.append(row)
        completed_keys.add((project_id, probe_id))
        write_jsonl(predictions_path, prediction_rows)

    report = _runner_report(
        input_dir,
        predictions_path,
        adapter=adapter,
        system_name=system_name,
        status=status,
        executed=True,
        issues=issues,
        projects=projects,
        probes=probes,
        events=events,
        predictions=prediction_rows,
        top_k=top_k,
    )
    report["warnings"] = warnings
    report["summary"]["loaded_existing_predictions"] = loaded_existing_predictions
    report["summary"]["new_predictions"] = max(0, len(prediction_rows) - loaded_existing_predictions)
    report["summary"]["skipped_existing_predictions"] = skipped_predictions
    report["summary"]["remaining_probes"] = max(0, len(probes) - len(completed_keys))
    report["constraints"] = _runner_constraints(
        external_dependency_invoked=True,
        llm_generation_performed=True,
    )
    report["external_adapter"] = _external_adapter_metadata(adapter) | {
        "execution_mode": "openai_compatible_prompt_adapter",
        "provider_base_url": provider["base_url"],
        "provider_model": provider["model"],
        "provider_config_path": provider.get("config_path"),
        "api_key_loaded": bool(provider.get("api_key")),
        "method_package_imported": False,
        "method_package_note": "This runner adapts the benchmark data to the method's memory style with an OpenAI-compatible model; it does not import the upstream method package.",
        "max_retries": max_retries,
        "retry_backoff_seconds": retry_backoff_seconds,
    }
    if report_path is not None:
        write_json(report_path, report)
    return report


def _runner_constraints(*, external_dependency_invoked: bool, llm_generation_performed: bool = False) -> dict[str, bool]:
    return {
        "reads_submission_inputs_only": True,
        "uses_gold_memory_graph": False,
        "uses_probe_expected_behavior": False,
        "uses_gold_evidence_ids": False,
        "llm_generation_performed": llm_generation_performed,
        "external_dependency_invoked": external_dependency_invoked,
    }


def _external_adapter_metadata(adapter: str) -> dict[str, Any]:
    spec = EXTERNAL_ADAPTER_SPECS[adapter]
    return {
        "display_name": spec["display_name"],
        "requires_gpu": spec["requires_gpu"],
        "recommended_partition": spec["recommended_partition"],
        "python_modules": spec["python_modules"],
        "required_env": spec["required_env"],
        "optional_env": spec["optional_env"],
        "notes": spec["notes"],
    }


def _load_openai_compatible_provider(provider_config_path: Path | None, *, model: str | None) -> dict[str, Any]:
    config_path = Path(
        provider_config_path
        or os.environ.get("ULB_OPENCODE_CONFIG")
        or os.environ.get("OPENCODE_CONFIG")
        or "opencode.json"
    )
    base_url = os.environ.get("ULB_OPENAI_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    api_key = os.environ.get("OPENAI_API_KEY")
    model_name = model or os.environ.get("ULB_OPENAI_MODEL") or "gpt-5.4-mini"
    config_loaded = False
    if config_path.exists():
        config_loaded = True
        config = read_json(config_path)
        openai = ((config.get("provider") or {}).get("openai") or {}) if isinstance(config, dict) else {}
        options = openai.get("options") or {}
        base_url = base_url or options.get("baseURL") or options.get("base_url")
        api_key = api_key or options.get("apiKey") or options.get("api_key")
        models = openai.get("models") or {}
        if model is None and os.environ.get("ULB_OPENAI_MODEL") is None and model_name not in models and models:
            model_name = sorted(models)[0]
    if not base_url:
        raise ValueError(f"missing OpenAI-compatible base URL; set ULB_OPENAI_BASE_URL/OPENAI_BASE_URL or provide {config_path}")
    if not api_key:
        raise ValueError(f"missing OpenAI-compatible API key; set OPENAI_API_KEY or provide {config_path}")
    return {
        "base_url": str(base_url).rstrip("/"),
        "api_key": str(api_key),
        "model": str(model_name),
        "config_path": str(config_path) if config_loaded else None,
    }


def _load_resume_predictions(predictions_path: Path, probes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, list[str]]:
    if not predictions_path.exists():
        return [], 0, []
    expected_keys = {(str(probe.get("project_id")), str(probe.get("probe_id"))) for probe in probes}
    rows = read_jsonl(predictions_path)
    kept: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    skipped = 0
    warnings: list[str] = []
    for row in rows:
        key = (str(row.get("project_id")), str(row.get("probe_id")))
        try:
            model_validate(ProjectPrediction, row)
        except Exception:
            skipped += 1
            continue
        if key not in expected_keys or key in seen:
            skipped += 1
            continue
        seen.add(key)
        kept.append(row)
    if skipped:
        warnings.append(f"ignored {skipped} invalid, duplicate, or out-of-release existing prediction rows while resuming")
    if kept:
        write_jsonl(predictions_path, kept)
    return kept, skipped, warnings


def _openai_chat_completion_with_retry(
    provider: dict[str, Any],
    messages: list[dict[str, str]],
    *,
    max_output_tokens: int,
    request_timeout: float,
    max_retries: int,
    retry_backoff_seconds: float,
) -> str:
    attempts = max(1, int(max_retries) + 1)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return _openai_chat_completion(
                provider,
                messages,
                max_output_tokens=max_output_tokens,
                request_timeout=request_timeout,
            )
        except Exception as exc:
            last_error = exc
            if attempt >= attempts - 1 or not _is_retryable_provider_error(exc):
                break
            time.sleep(max(0.0, retry_backoff_seconds) * (2**attempt))
    assert last_error is not None
    raise last_error


def _openai_chat_completion(
    provider: dict[str, Any],
    messages: list[dict[str, str]],
    *,
    max_output_tokens: int,
    request_timeout: float,
) -> str:
    endpoint = f"{provider['base_url']}/chat/completions"
    payload = {
        "model": provider["model"],
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_output_tokens,
        "store": False,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
            "User-Agent": "OpenAI/Python 1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {_safe_provider_error(body)}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc
    payload = json.loads(body)
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("provider response has no choices")
    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        content = "\n".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content)
    text = str(content).strip()
    if not text:
        raise RuntimeError("provider response content is empty")
    return text


def _is_retryable_provider_error(exc: Exception) -> bool:
    text = str(exc).lower()
    retry_markers = [
        "429",
        "500",
        "502",
        "503",
        "504",
        "timed out",
        "timeout",
        "unexpected_eof",
        "eof occurred",
        "connection reset",
        "remote end closed",
        "temporarily unavailable",
        "ssl",
    ]
    return any(marker in text for marker in retry_markers)


def _safe_provider_error(body: str) -> str:
    text = re.sub(r"sk-[A-Za-z0-9_\-]+", "sk-<redacted>", body)
    return text[:1000]


def _build_event_profile(project_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    label_counts: Counter[str] = Counter()
    assignee_counts: Counter[str] = Counter()
    actor_counts: Counter[str] = Counter()
    signal_counts: Counter[str] = Counter()
    repos: Counter[str] = Counter()
    for event in events:
        content = str(event.get("content", ""))
        actor = str(event.get("actor", ""))
        if actor:
            actor_counts[actor] += 1
        repo = str((event.get("metadata") or {}).get("repo") or "")
        if repo:
            repos[repo] += 1
        for label in _extract_labels(content):
            label_counts[label] += 1
        for assignee in _extract_assignees(content):
            assignee_counts[assignee] += 1
        for signal in _workflow_signals(content):
            signal_counts[signal] += 1
    return {
        "project_id": project_id,
        "repos": [item for item, _ in repos.most_common(5)],
        "top_labels": [item for item, _ in label_counts.most_common(10)],
        "top_assignees": [item for item, _ in assignee_counts.most_common(10)],
        "top_actors": [item for item, _ in actor_counts.most_common(10)],
        "workflow_signals": [item for item, _ in signal_counts.most_common(10)],
    }


def _retrieve_events_for_probe(probe: dict[str, Any], events: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    query = str(probe.get("query", ""))
    scored = sorted(
        [(_event_score(query, event), event) for event in events],
        key=lambda item: (item[0], str(item[1].get("timestamp", ""))),
        reverse=True,
    )
    retrieved = [event for score, event in scored if score > 0][:top_k]
    if not retrieved:
        retrieved = [event for _, event in scored[:top_k]]
    return retrieved


def _event_score(query: str, event: dict[str, Any]) -> float:
    text = _event_text(event)
    score = _lexical_score(query, text)
    query_tokens = set(_tokens(query))
    event_tokens = set(_tokens(text))
    signal_tokens = {
        "assign",
        "assigned",
        "blocked",
        "boundary",
        "ci",
        "close",
        "failed",
        "label",
        "merge",
        "pipeline",
        "review",
        "triage",
        "validation",
    }
    score += 0.05 * len(query_tokens & event_tokens & signal_tokens)
    return score


def _event_profile_prediction_row(
    probe: dict[str, Any],
    profile: dict[str, Any],
    retrieved: list[dict[str, Any]],
    *,
    system_name: str,
) -> dict[str, Any]:
    query = str(probe.get("query", ""))
    sections = [
        "No-gold event-profile memory baseline.",
        f"Future task: {query}",
    ]
    profile_lines = _policy_lines_from_query(query, profile)
    if profile_lines:
        sections.append("Induced policy/action profile:")
        sections.extend(profile_lines)
    else:
        sections.append(
            "Induced policy/action profile: use the retrieved workflow events conservatively; ask for clarification before irreversible, externally visible, or privacy-sensitive actions."
        )
    if retrieved:
        sections.append("Retrieved no-gold workflow events:")
        for event in retrieved:
            sections.append(f"- {event.get('event_id')}: {event.get('event_type')} {event.get('content')}")
    row = {
        "prediction_id": f"pred_{probe['project_id']}_{probe['probe_id']}",
        "project_id": probe["project_id"],
        "probe_id": probe["probe_id"],
        "prediction": "\n".join(sections),
        "retrieved_memory_ids": [],
        "retrieved_event_ids": _unique([str(event.get("event_id")) for event in retrieved if event.get("event_id")]),
        "retrieved_artifact_ids": _unique([str(artifact_id) for event in retrieved for artifact_id in event.get("artifacts", [])]),
        "metadata": {
            "baseline": system_name,
            "adapter": "event_profile_stub",
            "split": probe.get("split"),
            "no_gold_submission_input": True,
        },
    }
    return row


def _openai_compatible_memory_messages(
    adapter: str,
    probe: dict[str, Any],
    profile: dict[str, Any],
    retrieved: list[dict[str, Any]],
) -> list[dict[str, str]]:
    style = _adapter_prompt_style(adapter)
    event_lines = []
    for event in retrieved:
        event_lines.append(
            "\n".join(
                [
                    f"event_id: {event.get('event_id')}",
                    f"timestamp: {event.get('timestamp')}",
                    f"type: {event.get('event_type')}",
                    f"actor: {event.get('actor')}",
                    f"content: {event.get('content')}",
                ]
            )
        )
    profile_text = json.dumps(profile, ensure_ascii=True, sort_keys=True)
    user = f"""Future task:
{probe.get('query')}

Public probe metadata:
- project_id: {probe.get('project_id')}
- probe_id: {probe.get('probe_id')}
- task_type: {probe.get('task_type')}
- capabilities: {', '.join(str(item) for item in probe.get('capabilities', []))}

No-gold induced event profile:
{profile_text}

Retrieved no-gold workflow events:
{chr(10).join(event_lines) if event_lines else '(none)'}

Write the prediction text only. Include the policy you infer, the action you would take or avoid, and cite relevant event_id values when useful. Do not claim access to hidden gold memories or expected answers."""
    return [
        {
            "role": "system",
            "content": (
                "You are evaluating an agent-memory method on LongUserPolicyBench. "
                "Use only the supplied no-gold submission inputs. Do not assume hidden expected behavior. "
                f"Emulate this memory style: {style}"
            ),
        },
        {"role": "user", "content": user},
    ]


def _adapter_prompt_style(adapter: str) -> str:
    if adapter == "a_mem":
        return (
            "A-MEM-style agentic memory: convert observations into compact evolving notes, connect related policy cues, "
            "separate durable workflow policy from one-off negative examples, and apply the linked memory to future tool-action boundaries."
        )
    if adapter == "mem0":
        return (
            "Mem0-style long-term memory: extract durable user/workflow facts, consolidate repeated evidence, retrieve the most relevant memories, "
            "and answer with a conservative policy/action decision."
        )
    if adapter == "graphiti":
        return (
            "Graphiti/Zep-style temporal knowledge graph memory: track actors, repos, labels, actions, and temporal policy changes as relations, "
            "then reason over the current graph state and action boundaries."
        )
    return "generic no-gold memory-system baseline"


def _external_llm_prediction_row(
    probe: dict[str, Any],
    retrieved: list[dict[str, Any]],
    *,
    prediction_text: str,
    adapter: str,
    system_name: str,
    provider: dict[str, Any],
) -> dict[str, Any]:
    return {
        "prediction_id": f"pred_{probe['project_id']}_{probe['probe_id']}",
        "project_id": probe["project_id"],
        "probe_id": probe["probe_id"],
        "prediction": prediction_text,
        "retrieved_memory_ids": [],
        "retrieved_event_ids": _unique([str(event.get("event_id")) for event in retrieved if event.get("event_id")]),
        "retrieved_artifact_ids": _unique([str(artifact_id) for event in retrieved for artifact_id in event.get("artifacts", [])]),
        "metadata": {
            "baseline": system_name,
            "adapter": adapter,
            "split": probe.get("split"),
            "no_gold_submission_input": True,
            "openai_compatible_model": provider["model"],
        },
    }


def _policy_lines_from_query(query: str, profile: dict[str, Any]) -> list[str]:
    query_norm = _normalize_text(query)
    lines: list[str] = []
    if {"negative", "blocked", "failed", "habit", "storage"} & set(_tokens(query)):
        lines.extend(
            [
                "Allowed actions: suppress blocked workflow as agent habit; treat blocked workflow signal as a boundary for the workflow.",
                "Forbidden actions: do not store blocked or failed action as default habit; do not treat a blocked workflow signal as a default habit.",
            ]
        )
    if "merge" in query_norm or "execution boundary" in query_norm or "boundary conditions" in query_norm:
        lines.extend(
            [
                "Allowed actions: respect execution boundary; merge after observed boundary conditions; wait until observed boundary conditions are present.",
                "Forbidden actions: do not merge without boundary check; do not ignore the execution boundary.",
            ]
        )
    label = _extract_query_label(query)
    assignees = _extract_query_assignees(query)
    if label or assignees or "triage" in query_norm:
        allowed = []
        if label:
            allowed.append(f"apply {label} label")
        for assignee in assignees:
            allowed.append(f"assign {assignee}")
            allowed.append(f"request {assignee} triage")
        if not allowed and profile.get("top_assignees"):
            assignee = str(profile["top_assignees"][0])
            allowed.extend([f"assign {assignee}", f"request {assignee} triage"])
        if allowed:
            lines.append("Allowed actions: " + "; ".join(_unique(allowed)) + ".")
        lines.append("Authorized tools: github; issue_tracker.")
        lines.append("Forbidden actions: do not close without triage owner; do not escalate without triage context.")
    return _unique(lines)


def _extract_labels(content: str) -> list[str]:
    labels = []
    for match in re.finditer(r"labels=([^;\n]+)", content, flags=re.IGNORECASE):
        raw = match.group(1)
        raw = re.split(r",\s*(?:assignees?|comment|review|pull_request|issue):", raw, maxsplit=1)[0]
        labels.extend(_clean_label(part) for part in re.split(r"[|,]", raw) if _clean_label(part))
    return labels


def _extract_assignees(content: str) -> list[str]:
    assignees = []
    for match in re.finditer(r"\bassignees?=([^;\n,]+)", content, flags=re.IGNORECASE):
        assignees.extend(_clean_handle(part) for part in re.split(r"[|,\s]+", match.group(1)) if _clean_handle(part))
    return assignees


def _extract_query_label(query: str) -> str:
    patterns = [
        r"apply(?: the)? ([a-z0-9_\- ]+?) label",
        r"under the ([a-z0-9_\- ]+?) label condition",
        r"in the issue_label_([a-z0-9_\-]+) workflow",
        r"under the issue_label_([a-z0-9_\-]+) condition",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            return _humanize(match.group(1)).strip()
    return ""


def _extract_query_assignees(query: str) -> list[str]:
    handles = []
    for pattern in [
        r"\bassign ([A-Za-z0-9_.\-\[\]/]+)",
        r"\brequest ([A-Za-z0-9_.\-\[\]/]+) triage",
    ]:
        for match in re.finditer(pattern, query):
            value = _clean_handle(match.group(1))
            if value and value.lower() not in {"the", "a", "an"}:
                handles.append(_humanize(value))
    return _unique(handles)


def _workflow_signals(content: str) -> list[str]:
    text = _normalize_text(content)
    signals = []
    for signal in ["blocked", "failed", "validation completed", "azure pipeline passed", "changes requested", "moderator approved"]:
        if signal in text:
            signals.append(signal)
    return signals


def _event_text(event: dict[str, Any]) -> str:
    fragments = [
        event.get("event_type", ""),
        event.get("actor", ""),
        event.get("content", ""),
        " ".join(str(claim) for claim in event.get("claims", [])),
        " ".join(str(entity) for entity in event.get("entities", [])),
    ]
    return " ".join(str(fragment) for fragment in fragments if fragment)


def _lexical_score(query: str, text: str) -> float:
    query_tokens = set(_tokens(query))
    text_tokens = set(_tokens(text))
    if not query_tokens or not text_tokens:
        return 0.0
    return len(query_tokens & text_tokens) / len(query_tokens)


def _tokens(value: str) -> list[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "as",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "or",
        "the",
        "to",
        "with",
    }
    return [token for token in re.split(r"[^a-z0-9]+", _humanize(value).lower()) if token and token not in stopwords]


def _clean_label(value: str) -> str:
    return _humanize(value).strip(" .:;")


def _clean_handle(value: str) -> str:
    return value.strip(" .,:;()")


def _humanize(value: str) -> str:
    return str(value).replace("_", " ").replace("-", " ")


def _normalize_text(value: str) -> str:
    return " ".join(_tokens(value))


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
