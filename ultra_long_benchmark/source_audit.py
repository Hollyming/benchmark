from __future__ import annotations

from pathlib import Path
from typing import Any

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
        },
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
