from __future__ import annotations

from pathlib import Path
from typing import Any

from ultra_long_benchmark.data_discovery import verify_public_data_discovery_report
from ultra_long_benchmark.shared.io import read_json, write_json


def audit_workflow_data_sources(
    discovery_report_path: Path,
    output_path: Path | None = None,
    *,
    gharchive_stage_plan_path: Path | None = None,
    require_paper_ready: bool = False,
) -> dict[str, Any]:
    """Audit whether local workflow data sources are usable for construction.

    This is a source-readiness gate, not a benchmark scorer. It records whether
    the pipeline is grounded in reusable workflow traces or still blocked by
    missing GHArchive slices, missing email manifests, or license/privacy gates.
    """

    discovery_report_path = Path(discovery_report_path)
    discovery = read_json(discovery_report_path)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    source_entries = []

    for item in discovery.get("authoritative_source_plan", []):
        source_entries.append(
            {
                "source": item.get("source"),
                "domain": item.get("domain"),
                "reuse_role": item.get("reuse_role"),
                "current_local_status": item.get("current_local_status"),
                "pipeline_entry": item.get("pipeline_entry"),
                "license_privacy_notes": item.get("license_privacy_notes"),
            }
        )

    summary = discovery.get("summary", {})
    usable_sources = discovery.get("usable_sources", [])
    gharchive_sources = [item for item in usable_sources if item.get("dataset_kind") == "gharchive_public_events"]
    email_sources = [item for item in usable_sources if item.get("dataset_kind") == "email_workflow_manifest"]
    calendar_sources = [item for item in usable_sources if item.get("dataset_kind") == "calendar_workflow_manifest"]
    docs_sources = [item for item in usable_sources if item.get("dataset_kind") == "docs_workflow_manifest"]
    chat_sources = [item for item in usable_sources if item.get("dataset_kind") == "chat_workflow_manifest"]
    browser_web_sources = [item for item in usable_sources if item.get("dataset_kind") == "browser_web_workflow_manifest"]

    if not gharchive_sources:
        _issue(issues, "gharchive_source_missing", "No local GHArchive workflow event source was discovered.")
    if not email_sources:
        _warn(warnings, "email_manifest_missing", "No reviewed email workflow manifest was discovered; email corpora remain license/privacy gated.")
    if int(summary.get("github_code_only_sources", 0)) > 0:
        _warn(warnings, "github_code_corpus_not_workflow", "GitHub code-text corpora were found but are not workflow timelines.")

    stage_plan = None
    if gharchive_stage_plan_path is not None:
        stage_plan_path = Path(gharchive_stage_plan_path)
        if stage_plan_path.exists():
            stage_plan = read_json(stage_plan_path)
            decision = stage_plan.get("decision", {})
            if decision.get("ready_for_annotation_budget") is not True:
                code = "gharchive_stage_not_ready_for_annotation"
                message = "GHArchive stage plan is not ready for LLM/API or human annotation budget."
                if require_paper_ready:
                    _issue(issues, code, message)
                else:
                    _warn(warnings, code, message)
            if require_paper_ready and stage_plan.get("profile") != "paper":
                _issue(issues, "gharchive_stage_profile_not_paper", f"stage plan profile must be paper, found {stage_plan.get('profile')!r}")
        else:
            _issue(issues, "gharchive_stage_plan_missing", f"GHArchive stage-plan path does not exist: {stage_plan_path}", path=stage_plan_path)
    elif require_paper_ready:
        _issue(issues, "gharchive_stage_plan_required", "require_paper_ready needs a GHArchive stage-plan report.")

    paper_ready = not issues and bool(gharchive_sources) and (
        stage_plan is None or stage_plan.get("decision", {}).get("ready_for_annotation_budget") is True
    )
    annotation_budget_ready = bool(gharchive_sources) and not any(issue["code"] == "gharchive_source_missing" for issue in issues)
    if stage_plan is not None:
        annotation_budget_ready = annotation_budget_ready and stage_plan.get("decision", {}).get("ready_for_annotation_budget") is True

    report = {
        "discovery_report_path": str(discovery_report_path),
        "gharchive_stage_plan_path": str(gharchive_stage_plan_path) if gharchive_stage_plan_path is not None else None,
        "passed": not issues,
        "paper_ready": paper_ready,
        "annotation_budget_ready": annotation_budget_ready,
        "summary": {
            "issues": len(issues),
            "warnings": len(warnings),
            "issue_codes": sorted({issue["code"] for issue in issues}),
            "warning_codes": sorted({warning["code"] for warning in warnings}),
            "usable_sources": len(usable_sources),
            "gharchive_sources": len(gharchive_sources),
            "email_manifest_sources": len(email_sources),
            "calendar_manifest_sources": len(calendar_sources),
            "docs_manifest_sources": len(docs_sources),
            "chat_manifest_sources": len(chat_sources),
            "browser_web_manifest_sources": len(browser_web_sources),
            "require_paper_ready": require_paper_ready,
        },
        "source_entries": source_entries,
        "usable_sources": usable_sources,
        "stage_plan_decision": stage_plan.get("decision") if isinstance(stage_plan, dict) else None,
        "recommended_next_actions": _source_audit_recommendations(discovery, stage_plan, require_paper_ready),
        "issues": issues,
        "warnings": warnings,
        "constraints": {
            "network_download_performed": False,
            "llm_generation_performed": False,
            "source_grounding_required": True,
            "email_requires_license_privacy_manifest": True,
            "non_github_domains_require_manifest_first_adapter": True,
        },
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def verify_workflow_data_source_audit(
    report_path: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Verify that a workflow source audit still matches discovery and stage-plan inputs."""

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
                "issue_codes": ["workflow_source_audit_report_missing"],
                "warning_codes": [],
            },
            "issues": [
                {
                    "code": "workflow_source_audit_report_missing",
                    "message": "workflow source audit report is missing",
                    "path": str(report_path),
                }
            ],
            "warnings": [],
        }
        if output_path is not None:
            write_json(output_path, report)
        return report

    original = read_json(report_path)
    discovery_path = Path(str(original.get("discovery_report_path") or ""))
    stage_plan_path = Path(str(original.get("gharchive_stage_plan_path") or "")) if original.get("gharchive_stage_plan_path") else None
    require_paper_ready = bool(original.get("summary", {}).get("require_paper_ready", False)) if isinstance(original.get("summary"), dict) else False

    if not discovery_path.exists():
        _issue(issues, "workflow_source_audit_discovery_missing", "workflow source audit discovery report is missing", discovery_path)
        recomputed = None
        discovery_verification = None
    else:
        discovery_verification = verify_public_data_discovery_report(discovery_path)
        if discovery_verification.get("passed") is not True:
            _issue(issues, "workflow_source_audit_discovery_verification_not_passed", "workflow source audit discovery report changed or lacks digests", discovery_path)
        recomputed = audit_workflow_data_sources(
            discovery_path,
            gharchive_stage_plan_path=stage_plan_path,
            require_paper_ready=require_paper_ready,
        )

    if stage_plan_path is not None and not stage_plan_path.exists():
        _issue(issues, "workflow_source_audit_stage_plan_missing", "workflow source audit stage-plan report is missing", stage_plan_path)

    if recomputed is not None:
        for key in ["summary", "passed", "paper_ready", "annotation_budget_ready", "stage_plan_decision", "source_entries"]:
            if original.get(key) != recomputed.get(key):
                _issue(
                    issues,
                    f"workflow_source_audit_{key}_mismatch",
                    f"workflow source audit {key} changed after recomputation",
                    report_path,
                )

    summary = {
        "issues": len(issues),
        "warnings": len(warnings),
        "issue_codes": sorted({issue["code"] for issue in issues}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
        "discovery_verification": discovery_verification.get("summary", {}) if isinstance(discovery_verification, dict) else {},
    }
    report = {
        "passed": not issues,
        "report_path": str(report_path),
        "discovery_report_path": str(discovery_path) if str(discovery_path) else None,
        "gharchive_stage_plan_path": str(stage_plan_path) if stage_plan_path is not None else None,
        "summary": summary,
        "issues": issues,
        "warnings": warnings,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def _source_audit_recommendations(discovery: dict[str, Any], stage_plan: dict[str, Any] | None, require_paper_ready: bool) -> list[str]:
    actions = list(discovery.get("recommended_next_actions", []))
    if stage_plan is not None and stage_plan.get("decision", {}).get("ready_for_annotation_budget") is not True:
        actions.extend(stage_plan.get("recommended_next_actions", []))
    if require_paper_ready:
        actions.append("Require a paper-profile GHArchive stage plan with ready_for_annotation_budget=true before LLM/human rewrite annotation.")
    return _dedupe(actions)


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _issue(issues: list[dict[str, Any]], code: str, message: str, path: Path | None = None) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        item["path"] = str(path)
    issues.append(item)


def _warn(warnings: list[dict[str, Any]], code: str, message: str, path: Path | None = None) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        item["path"] = str(path)
    warnings.append(item)
