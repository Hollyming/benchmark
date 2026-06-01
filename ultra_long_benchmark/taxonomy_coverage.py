from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ultra_long_benchmark.models import Capability
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_json


CORE_TASK_TAXONOMY = {
    "name": "Longitudinal User Policy / Habit Induction for Tool-Using Agents",
    "short_name": "longitudinal_user_policy_habit_induction",
    "unit": "future tool-use probe grounded in longitudinal workflow traces",
    "description": (
        "Systems infer user/workflow policies, habits, action boundaries, and scoped exceptions "
        "from longitudinal traces, then apply them to future tool actions."
    ),
}


TASK_FAMILIES = {
    "contextual_workflow_policy_selection": "contextual_policy_selection",
    "tool_action_policy_alignment": "tool_action_alignment",
    "negative_example_storage_gating": "negative_example_storage_gating",
    "privacy_authorization_boundary": "privacy_authorization_boundary",
    "policy_update_and_exception_handling": "policy_update_exception_handling",
    "routine_completion": "proactive_routine_recognition",
}


DOMAIN_DEFINITIONS = {
    "github_developer_workflow": {
        "label": "GitHub developer workflow",
        "source_dataset_tokens": ["gharchive", "github"],
        "source_stream_tokens": ["gharchive", "github"],
        "status_when_absent": "planned_not_released",
    },
    "email_workflow": {
        "label": "Email workflow",
        "source_dataset_tokens": ["email", "enron", "avocado"],
        "source_stream_tokens": ["email", "enron", "avocado"],
        "status_when_absent": "blocked_license_privacy_manifest",
    },
    "calendar_workflow": {
        "label": "Calendar workflow",
        "source_dataset_tokens": ["calendar"],
        "source_stream_tokens": ["calendar"],
        "status_when_absent": "planned_not_released",
    },
    "docs_workflow": {
        "label": "Document workflow",
        "source_dataset_tokens": ["docs", "document"],
        "source_stream_tokens": ["docs", "document"],
        "status_when_absent": "planned_not_released",
    },
    "chat_workflow": {
        "label": "Chat workflow",
        "source_dataset_tokens": ["chat", "slack", "teams"],
        "source_stream_tokens": ["chat", "slack", "teams"],
        "status_when_absent": "planned_not_released",
    },
    "browser_web_workflow": {
        "label": "Browser/web-search workflow",
        "source_dataset_tokens": ["browser", "web", "search", "web_search", "workarena", "mind2web"],
        "source_stream_tokens": ["browser", "web", "search", "web_search", "workarena", "mind2web"],
        "status_when_absent": "planned_not_released",
    },
}


BRIDGE_OR_SYNTHETIC_STREAMS = {"synthetic", "synthetic_bridge", "fixture", "manual"}


def audit_project_release_taxonomy_coverage(
    release_dir: Path,
    output_path: Path | None = None,
    *,
    require_multi_domain: bool = False,
) -> dict[str, Any]:
    """Summarize task-taxonomy and workflow-domain coverage for a project release."""

    release_dir = Path(release_dir)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    manifest_path = release_dir / "project_release_manifest.json"
    if not manifest_path.exists():
        _issue(issues, "project_release_manifest_missing", f"project release manifest missing: {manifest_path}")
        report = _report(release_dir, issues, warnings, checks={}, require_multi_domain=require_multi_domain)
        if output_path is not None:
            write_json(output_path, report)
        return report

    manifest = read_json(manifest_path)
    projects = list(manifest.get("projects", []))
    probes = _release_probe_rows(release_dir, projects, issues)
    release_counts = manifest.get("counts", {})
    task_type_counts = Counter(str(probe.get("task_type") or "unknown") for probe in probes)
    capability_counts: Counter[str] = Counter()
    task_family_counts: Counter[str] = Counter()
    metric_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    difficulty_counts: Counter[str] = Counter()
    for probe in probes:
        split_counts[str(probe.get("split") or "unknown")] += 1
        difficulty_counts[str(probe.get("difficulty") or "unknown")] += 1
        task_type = str(probe.get("task_type") or "unknown")
        task_family_counts[TASK_FAMILIES.get(task_type, task_type)] += 1
        for capability in probe.get("capabilities", []):
            capability_counts[str(capability)] += 1
        evaluation = probe.get("evaluation") if isinstance(probe.get("evaluation"), dict) else {}
        for metric in evaluation.get("metrics", []):
            metric_counts[str(metric)] += 1

    project_source_stream_counts: Counter[str] = Counter()
    source_manifest_stream_counts: Counter[str] = Counter()
    event_source_dataset_counts: Counter[str] = Counter()
    event_type_counts: Counter[str] = Counter()
    github_event_type_counts: Counter[str] = Counter()
    artifact_source_dataset_counts: Counter[str] = Counter()
    artifact_type_counts: Counter[str] = Counter()
    memory_type_counts: Counter[str] = Counter()
    action_boundary_memory_count = 0
    project_rows = []

    for project in projects:
        project_dir = _resolve_reference_path(project.get("project_dir"), release_dir)
        project_id = str(project.get("project_id") or "")
        for stream in project.get("source_streams", []):
            project_source_stream_counts[str(stream)] += 1
        source_manifest = _read_optional_json(project_dir / "source_manifest.json")
        for stream in source_manifest.get("source_streams", []):
            source_manifest_stream_counts[str(stream)] += 1
        events = read_jsonl(project_dir / "events.jsonl")
        artifacts = read_jsonl(project_dir / "artifacts.jsonl")
        graph = _read_optional_json(project_dir / "memory_graph.json")
        for event in events:
            event_source_dataset_counts[str(event.get("source_dataset") or "unknown")] += 1
            event_type_counts[str(event.get("event_type") or "unknown")] += 1
            metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
            github_event_type = metadata.get("github_event_type")
            if github_event_type:
                github_event_type_counts[str(github_event_type)] += 1
        for artifact in artifacts:
            artifact_source_dataset_counts[str(artifact.get("source_dataset") or "unknown")] += 1
            artifact_type_counts[str(artifact.get("artifact_type") or "unknown")] += 1
        for memory in graph.get("memories", []):
            memory_type_counts[str(memory.get("memory_type") or "unknown")] += 1
            if memory.get("action_boundary"):
                action_boundary_memory_count += 1
        project_rows.append(
            {
                "project_id": project_id,
                "split": project.get("split"),
                "split_key": project.get("split_key"),
                "source_streams": list(project.get("source_streams", [])),
                "source_manifest_streams": list(source_manifest.get("source_streams", [])),
                "task_types": dict(sorted(project.get("probe_task_types", {}).items())),
                "capabilities": dict(sorted(project.get("capabilities", {}).items())),
                "event_source_datasets": dict(sorted(Counter(str(event.get("source_dataset") or "unknown") for event in events).items())),
                "events": len(events),
                "probes": int(project.get("counts", {}).get("probes", 0) or 0),
            }
        )

    domain_coverage = _domain_coverage(
        event_source_dataset_counts,
        project_source_stream_counts + source_manifest_stream_counts,
    )
    covered_domains = [name for name, item in domain_coverage.items() if item["status"] == "covered"]
    bridge_streams = sorted(
        stream
        for stream in set(project_source_stream_counts) | set(source_manifest_stream_counts)
        if _is_bridge_or_synthetic_stream(stream)
    )
    missing_capabilities = [capability.value for capability in Capability if capability_counts.get(capability.value, 0) == 0]
    if missing_capabilities:
        _warn(
            warnings,
            "capabilities_not_in_current_release",
            f"current release does not cover {len(missing_capabilities)} capability enum values",
            capabilities=missing_capabilities,
        )
    missing_domains = [name for name, item in domain_coverage.items() if item["status"] != "covered"]
    if missing_domains:
        _warn(
            warnings,
            "workflow_domains_not_in_current_release",
            f"current release does not cover {len(missing_domains)} planned workflow domains",
            domains=missing_domains,
        )
    if bridge_streams:
        _warn(
            warnings,
            "bridge_streams_not_counted_as_real_domains",
            "synthetic/bridge source streams were observed but are not counted as real workflow domains",
            streams=bridge_streams,
        )
    if not probes:
        _issue(issues, "project_release_has_no_probes", "project release has no probe rows")
    if not covered_domains:
        _issue(issues, "project_release_has_no_real_workflow_domain", "no covered real workflow domain was detected")
    if require_multi_domain and len(covered_domains) < 2:
        _issue(issues, "multi_domain_release_required", "release does not cover at least two real workflow domains")

    current_scope = _current_domain_scope(covered_domains)
    checks = {
        "core_task_taxonomy": CORE_TASK_TAXONOMY
        | {
            "capability_enum": [capability.value for capability in Capability],
            "task_family_mapping": dict(sorted(TASK_FAMILIES.items())),
        },
        "release_counts": {
            "manifest": release_counts,
            "projects": len(projects),
            "probes": len(probes),
            "splits": dict(sorted(split_counts.items())),
            "difficulties": dict(sorted(difficulty_counts.items())),
        },
        "task_taxonomy_coverage": {
            "task_types": dict(sorted(task_type_counts.items())),
            "task_families": dict(sorted(task_family_counts.items())),
            "capabilities": dict(sorted(capability_counts.items())),
            "capability_status": {
                capability.value: {
                    "count": int(capability_counts.get(capability.value, 0)),
                    "status": "covered" if capability_counts.get(capability.value, 0) else "planned_not_in_current_release",
                }
                for capability in Capability
            },
            "metrics": dict(sorted(metric_counts.items())),
        },
        "workflow_domain_coverage": domain_coverage,
        "source_evidence": {
            "event_source_datasets": dict(sorted(event_source_dataset_counts.items())),
            "event_types": dict(sorted(event_type_counts.items())),
            "github_event_types": dict(sorted(github_event_type_counts.items())),
            "artifact_source_datasets": dict(sorted(artifact_source_dataset_counts.items())),
            "artifact_types": dict(sorted(artifact_type_counts.items())),
            "project_source_streams": dict(sorted(project_source_stream_counts.items())),
            "source_manifest_streams": dict(sorted(source_manifest_stream_counts.items())),
            "bridge_or_synthetic_streams": bridge_streams,
        },
        "memory_policy_schema": {
            "memory_types": dict(sorted(memory_type_counts.items())),
            "memories_with_action_boundary": action_boundary_memory_count,
        },
        "projects": project_rows,
        "claim_boundary": {
            "supported_claims": [
                "longitudinal_user_policy_habit_induction_task_taxonomy",
                "github_developer_workflow_domain_release",
            ]
            if current_scope == "github_developer_workflow_only"
            else ["longitudinal_user_policy_habit_induction_task_taxonomy"],
            "unsupported_claims_for_current_release": [
                "multi_domain_email_calendar_docs_chat_browser_office_workflow_release",
                "reviewed_real_email_workflow_release",
                "calendar_docs_chat_browser_workflow_release",
                "browser_web_search_workflow_release",
            ],
            "current_release_domain_scope": current_scope,
            "multi_domain_release_ready": len(covered_domains) > 1,
        },
    }
    report = _report(release_dir, issues, warnings, checks=checks, require_multi_domain=require_multi_domain)
    if output_path is not None:
        write_json(output_path, report)
    return report


def verify_project_release_taxonomy_coverage_audit(
    report_path: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Verify that a taxonomy coverage audit still matches its project release."""

    report_path = Path(report_path)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not report_path.exists():
        report = {
            "passed": False,
            "report_path": str(report_path),
            "summary": {
                "issues": 1,
                "warnings": 0,
                "issue_codes": ["taxonomy_coverage_audit_report_missing"],
                "warning_codes": [],
            },
            "issues": [
                {
                    "code": "taxonomy_coverage_audit_report_missing",
                    "message": "taxonomy coverage audit report is missing",
                    "path": str(report_path),
                }
            ],
            "warnings": [],
        }
        if output_path is not None:
            write_json(output_path, report)
        return report

    original = read_json(report_path)
    release_dir = Path(str(original.get("release_dir") or ""))
    require_multi_domain = bool(original.get("require_multi_domain", False))
    if not release_dir.exists():
        _issue(issues, "taxonomy_coverage_release_dir_missing", "taxonomy coverage release_dir is missing", path=str(release_dir))
        recomputed = None
    else:
        recomputed = audit_project_release_taxonomy_coverage(
            release_dir,
            require_multi_domain=require_multi_domain,
        )
        for key in ["summary", "checks", "issues", "warnings", "passed"]:
            if original.get(key) != recomputed.get(key):
                _issue(
                    issues,
                    f"taxonomy_coverage_{key}_mismatch",
                    f"taxonomy coverage {key} changed after recomputation",
                    path=str(report_path),
                )

    summary = {
        "issues": len(issues),
        "warnings": len(warnings),
        "issue_codes": sorted({issue["code"] for issue in issues}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
        "release_dir": str(release_dir) if str(release_dir) else None,
    }
    report = {
        "passed": not issues,
        "report_path": str(report_path),
        "release_dir": str(release_dir) if str(release_dir) else None,
        "source_summary": original.get("summary", {}),
        "recomputed_summary": recomputed.get("summary", {}) if isinstance(recomputed, dict) else {},
        "summary": summary,
        "issues": issues,
        "warnings": warnings,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def _release_probe_rows(release_dir: Path, projects: list[dict[str, Any]], issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    all_probes_path = release_dir / "probes" / "all.jsonl"
    if all_probes_path.exists():
        return read_jsonl(all_probes_path)
    _issue(issues, "release_all_probes_missing", f"release probe aggregate missing: {all_probes_path}")
    rows: list[dict[str, Any]] = []
    for project in projects:
        project_dir = _resolve_reference_path(project.get("project_dir"), release_dir)
        for row in read_jsonl(project_dir / "probes.jsonl"):
            rows.append(row | {"split": project.get("split")})
    return rows


def _domain_coverage(source_dataset_counts: Counter[str], source_stream_counts: Counter[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    datasets = dict(sorted(source_dataset_counts.items()))
    streams = dict(sorted(source_stream_counts.items()))
    for domain, definition in DOMAIN_DEFINITIONS.items():
        matched_datasets = _matching_counts(datasets, definition["source_dataset_tokens"])
        matched_streams = _matching_counts(streams, definition["source_stream_tokens"])
        covered = bool(matched_datasets or matched_streams)
        result[domain] = {
            "label": definition["label"],
            "status": "covered" if covered else definition["status_when_absent"],
            "matched_event_source_datasets": matched_datasets,
            "matched_source_streams": matched_streams,
            "evidence_count": sum(matched_datasets.values()),
        }
    return result


def _matching_counts(counts: dict[str, int], tokens: list[str]) -> dict[str, int]:
    matched = {}
    lowered_tokens = [token.lower() for token in tokens]
    for name, count in counts.items():
        lowered = name.lower()
        if any(token in lowered for token in lowered_tokens):
            matched[name] = count
    return matched


def _current_domain_scope(covered_domains: list[str]) -> str:
    if covered_domains == ["github_developer_workflow"]:
        return "github_developer_workflow_only"
    if len(covered_domains) > 1:
        return "multi_domain"
    if covered_domains:
        return f"{covered_domains[0]}_only"
    return "unknown_or_no_real_domain"


def _resolve_reference_path(value: Any, release_dir: Path) -> Path:
    path = Path(str(value or ""))
    if path.is_absolute() or path.exists():
        return path
    return release_dir / path


def _read_optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.exists() else {}


def _is_bridge_or_synthetic_stream(stream: str) -> bool:
    lowered = stream.lower()
    return any(token in lowered for token in BRIDGE_OR_SYNTHETIC_STREAMS)


def _report(
    release_dir: Path,
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    *,
    checks: dict[str, Any],
    require_multi_domain: bool,
) -> dict[str, Any]:
    covered_domains = []
    current_scope = "unknown_or_no_real_domain"
    if checks:
        domain_coverage = checks.get("workflow_domain_coverage", {})
        covered_domains = [name for name, item in domain_coverage.items() if item.get("status") == "covered"]
        current_scope = checks.get("claim_boundary", {}).get("current_release_domain_scope", _current_domain_scope(covered_domains))
    return {
        "release_dir": str(release_dir),
        "passed": not issues,
        "require_multi_domain": require_multi_domain,
        "summary": {
            "issues": len(issues),
            "warnings": len(warnings),
            "covered_workflow_domains": covered_domains,
            "current_release_domain_scope": current_scope,
            "multi_domain_release_ready": len(covered_domains) > 1,
            "task_types": len(checks.get("task_taxonomy_coverage", {}).get("task_types", {})) if checks else 0,
            "capabilities_covered": sum(
                1
                for item in checks.get("task_taxonomy_coverage", {}).get("capability_status", {}).values()
                if item.get("status") == "covered"
            )
            if checks
            else 0,
            "issue_codes": sorted({issue["code"] for issue in issues}),
            "warning_codes": sorted({warning["code"] for warning in warnings}),
        },
        "checks": checks,
        "issues": issues,
        "warnings": warnings,
    }


def _issue(issues: list[dict[str, Any]], code: str, message: str, **extra: Any) -> None:
    issues.append({"code": code, "message": message} | extra)


def _warn(warnings: list[dict[str, Any]], code: str, message: str, **extra: Any) -> None:
    warnings.append({"code": code, "message": message} | extra)
