from __future__ import annotations

from pathlib import Path
from typing import Any

from ultra_long_benchmark.audit import audit_generated
from ultra_long_benchmark.data_discovery import discover_public_data_sources
from ultra_long_benchmark.paper_scale import assess_release_scale
from ultra_long_benchmark.pipelines.verifier import run_project_verifier
from ultra_long_benchmark.probe_audit import audit_project_release_probe_leakage
from ultra_long_benchmark.project_release import verify_project_benchmark_release
from ultra_long_benchmark.project_release import verify_project_submission_inputs
from ultra_long_benchmark.release_integrity import verify_annotation_release_integrity
from ultra_long_benchmark.shared.io import read_json, write_json
from ultra_long_benchmark.source_audit import audit_workflow_data_sources


def build_readiness_report(
    generated_dir: Path,
    output_path: Path | None = None,
    baseline_batch_dir: Path | None = None,
    annotation_release_dir: Path | None = None,
    prompt_export_dir: Path | None = None,
    rewrite_job_dir: Path | None = None,
    rewrite_project_dir: Path | None = None,
    staged_slice_manifest: Path | None = None,
    gharchive_stage_plan_path: Path | None = None,
    scale_summary_path: Path | None = None,
    window_report_path: Path | None = None,
    public_data_discovery_path: Path | None = None,
    workflow_source_audit_path: Path | None = None,
    batch_rewrite_validation_path: Path | None = None,
    batch_rewrite_projects_path: Path | None = None,
    project_release_dir: Path | None = None,
    project_submission_input_dir: Path | None = None,
    project_release_baseline_path: Path | None = None,
    project_release_prediction_path: Path | None = None,
    paper_table_dir: Path | None = None,
    rewrite_human_audit_path: Path | None = None,
    probe_leakage_audit_path: Path | None = None,
    paper_scale_profile: str = "paper",
    require_paper_scale: bool = False,
) -> dict[str, Any]:
    """Aggregate release-readiness evidence without rerunning expensive stages."""

    generated_dir = Path(generated_dir)
    baseline_batch_dir = baseline_batch_dir or generated_dir / "evaluation_harness" / "baseline_batch"
    annotation_release_dir = annotation_release_dir or generated_dir / "release_packaging" / "gharchive_annotation_pack"
    prompt_export_dir = prompt_export_dir or generated_dir / "annotation_packs" / "gharchive_prompt_exports"
    rewrite_job_dir = rewrite_job_dir or generated_dir / "annotation_packs" / "rewrite_jobs"
    rewrite_project_dir = rewrite_project_dir or generated_dir / "projects" / "project_gharchive_rewrite_001"
    staged_slice_manifest = staged_slice_manifest or generated_dir / "gharchive_staged_slice_manifest.json"
    gharchive_stage_plan_path = gharchive_stage_plan_path or generated_dir / "gharchive_stage_plan.json"
    scale_summary_path = scale_summary_path or generated_dir / "gharchive_scale_summary.json"
    window_report_path = window_report_path or generated_dir / "gharchive_window_report.json"
    public_data_discovery_path = public_data_discovery_path or generated_dir / "public_data_discovery_report.json"
    workflow_source_audit_path = workflow_source_audit_path or generated_dir / "workflow_data_source_audit.json"
    batch_rewrite_validation_path = batch_rewrite_validation_path or generated_dir / "annotation_packs" / "gharchive_rewrite_validation_batch" / "batch_rewrite_validation_report.json"
    batch_rewrite_projects_path = batch_rewrite_projects_path or generated_dir / "projects" / "batch_rewrite_project_report.json"
    project_release_dir = project_release_dir or generated_dir / "release_packaging" / "project_benchmark"
    project_submission_input_dir = project_submission_input_dir or generated_dir / "evaluation_harness" / "project_submission_inputs"
    project_release_baseline_path = project_release_baseline_path or generated_dir / "evaluation_harness" / "project_release_baselines.json"
    project_release_prediction_path = project_release_prediction_path or generated_dir / "evaluation_harness" / "project_release_prediction_report.json"
    paper_table_dir = paper_table_dir or generated_dir / "evaluation_harness" / "paper_tables"
    rewrite_human_audit_path = rewrite_human_audit_path or generated_dir / "annotation_packs" / "rewrite_human_audit" / "audit_validation_report.json"
    probe_leakage_audit_path = probe_leakage_audit_path or generated_dir / "evaluation_harness" / "project_release_probe_leakage_audit.json"

    audit = audit_generated(generated_dir)
    checks = {
        "offline_smoke_audit": _audit_check(audit),
        "baseline_batch": _baseline_batch_check(baseline_batch_dir),
        "annotation_release": _annotation_release_check(annotation_release_dir),
        "prompt_exports": _prompt_exports_check(prompt_export_dir),
        "rewrite_jobs": _rewrite_jobs_check(rewrite_job_dir),
        "release_integrity": _release_integrity_check(annotation_release_dir, prompt_export_dir),
        "paper_scale": _paper_scale_check(
            annotation_release_dir,
            prompt_export_dir,
            scale_summary_path,
            window_report_path,
            profile=paper_scale_profile,
            required=require_paper_scale,
        ),
        "public_data_discovery": _public_data_discovery_check(public_data_discovery_path),
        "workflow_source_audit": _workflow_source_audit_check(
            workflow_source_audit_path,
            public_data_discovery_path,
            gharchive_stage_plan_path,
            required=require_paper_scale,
        ),
        "batch_rewrite_validation": _batch_rewrite_validation_check(batch_rewrite_validation_path),
        "batch_rewrite_projects": _batch_rewrite_projects_check(batch_rewrite_projects_path),
        "project_benchmark_release": _project_release_check(project_release_dir),
        "project_submission_inputs": _project_submission_inputs_check(project_submission_input_dir),
        "project_release_baselines": _project_release_baseline_check(project_release_baseline_path),
        "project_release_prediction_scoring": _project_release_prediction_check(project_release_prediction_path),
        "paper_tables": _paper_tables_check(paper_table_dir),
        "rewrite_human_audit": _rewrite_human_audit_check(rewrite_human_audit_path),
        "probe_leakage_audit": _probe_leakage_audit_check(
            probe_leakage_audit_path,
            project_release_dir,
            required=require_paper_scale,
        ),
        "rewrite_project_verifier": _rewrite_project_check(rewrite_project_dir),
        "gharchive_stage_plan": _gharchive_stage_plan_check(gharchive_stage_plan_path, required=require_paper_scale),
        "staged_slice_manifest": _staged_slice_manifest_check(staged_slice_manifest),
    }
    blocking = [name for name, check in checks.items() if check["status"] == "fail"]
    warnings = [name for name, check in checks.items() if check["status"] == "warn"]
    report = {
        "generated_dir": str(generated_dir),
        "checks": checks,
        "summary": {
            "checks_total": len(checks),
            "passed": sum(1 for check in checks.values() if check["status"] == "pass"),
            "warnings": len(warnings),
            "failed": len(blocking),
            "blocking_checks": blocking,
            "warning_checks": warnings,
        },
        "passed": not blocking,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def _audit_check(audit: dict[str, Any]) -> dict[str, Any]:
    issues = []
    counts = audit.get("counts", {})
    if audit.get("passed") is not True:
        issues.append("audit_generated did not pass")
    for key in ("source_documents", "personas", "trajectories", "queries"):
        if int(counts.get(key, 0)) <= 0:
            issues.append(f"missing generated {key}")
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "evidence": {
            "passed": audit.get("passed"),
            "counts": {key: counts.get(key) for key in ("source_documents", "personas", "trajectories", "sessions", "queries")},
        },
    }


def _baseline_batch_check(baseline_batch_dir: Path) -> dict[str, Any]:
    report_path = Path(baseline_batch_dir) / "baseline_batch_report.json"
    if not report_path.exists():
        return _missing("baseline batch report missing", report_path)
    report = read_json(report_path)
    summary = report.get("summary", {})
    issues = []
    if report.get("passed") is not True:
        issues.append("baseline batch report did not pass")
    if int(summary.get("completed", 0)) < 1:
        issues.append("no deterministic baselines completed")
    if int(summary.get("failed", 0)) > 0:
        issues.append("baseline batch has failed configs")
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "evidence": {
            "path": str(report_path),
            "summary": summary,
            "dry_run_external": report.get("dry_run_external"),
            "allow_llm_api": report.get("allow_llm_api"),
        },
    }


def _annotation_release_check(annotation_release_dir: Path) -> dict[str, Any]:
    manifest_path = Path(annotation_release_dir) / "release_manifest.json"
    if not manifest_path.exists():
        return _missing("annotation release manifest missing", manifest_path)
    manifest = read_json(manifest_path)
    counts = manifest.get("counts", {})
    constraints = manifest.get("constraints", {})
    issues = []
    if int(counts.get("packs", 0)) <= 0:
        issues.append("annotation release has no packs")
    if int(counts.get("tasks", 0)) <= 0:
        issues.append("annotation release has no tasks")
    if constraints.get("llm_generation_allowed") is not False:
        issues.append("annotation release must mark llm_generation_allowed=false")
    if constraints.get("requires_validate_policy_rewrites") is not True:
        issues.append("annotation release must require validate-policy-rewrites")
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "evidence": {
            "path": str(manifest_path),
            "counts": counts,
            "splits": manifest.get("splits", {}),
            "constraints": constraints,
        },
    }


def _prompt_exports_check(prompt_export_dir: Path) -> dict[str, Any]:
    report_path = Path(prompt_export_dir) / "rewrite_prompt_batch_report.json"
    if not report_path.exists():
        return _missing("rewrite prompt batch report missing", report_path)
    report = read_json(report_path)
    summary = report.get("summary", {})
    constraints = report.get("constraints", {})
    issues = []
    if int(summary.get("packs_total", 0)) <= 0:
        issues.append("prompt export has no packs")
    if int(summary.get("prompts_total", 0)) <= 0:
        issues.append("prompt export has no prompts")
    if constraints.get("llm_generation_performed") is not False:
        issues.append("prompt export must not perform LLM generation")
    if constraints.get("requires_validate_policy_rewrites") is not True:
        issues.append("prompt export must require validate-policy-rewrites")
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "evidence": {
            "path": str(report_path),
            "summary": summary,
            "constraints": constraints,
        },
    }


def _rewrite_jobs_check(rewrite_job_dir: Path) -> dict[str, Any]:
    rewrite_job_dir = Path(rewrite_job_dir)
    manifest_path = rewrite_job_dir / "rewrite_job_manifest.json"
    if not manifest_path.exists():
        return {
            "status": "warn",
            "issues": ["rewrite job manifest missing; prompt exports have not been packaged for LLM/human annotation handoff"],
            "evidence": {"path": str(manifest_path)},
        }
    manifest = read_json(manifest_path)
    summary = manifest.get("summary", {})
    constraints = manifest.get("constraints", {})
    issues = []
    if int(summary.get("jobs_total", 0)) <= 0:
        issues.append("rewrite job package has no jobs")
    if int(summary.get("prompts_total", 0)) <= 0:
        issues.append("rewrite job package has no prompts")
    if int(summary.get("estimated_tokens_total", 0)) <= 0:
        issues.append("rewrite job package has no token estimate")
    if constraints.get("llm_generation_performed") is not False:
        issues.append("rewrite job package must record llm_generation_performed=false")
    if constraints.get("requires_validate_policy_rewrites_batch") is not True:
        issues.append("rewrite job package must require validate-policy-rewrites-batch")
    missing_job_files = []
    for job in manifest.get("jobs", []):
        for key in ("prompts_path", "proposal_template_path", "job_manifest_path"):
            path = Path(str(job.get(key, "")))
            if not path.exists():
                missing_job_files.append(str(path))
    if missing_job_files:
        issues.append("rewrite job package missing job files: " + ", ".join(missing_job_files[:5]))
    return {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "evidence": {
            "path": str(manifest_path),
            "summary": summary,
            "constraints": constraints,
        },
    }


def _release_integrity_check(annotation_release_dir: Path, prompt_export_dir: Path) -> dict[str, Any]:
    report = verify_annotation_release_integrity(annotation_release_dir, prompt_export_dir=prompt_export_dir)
    issues = [issue["message"] for issue in report["issues"]]
    warnings = [warning["message"] for warning in report["warnings"]]
    status = "fail" if issues else ("warn" if warnings else "pass")
    return {
        "status": status,
        "issues": issues + warnings,
        "evidence": {
            "release_dir": report["release_dir"],
            "prompt_export_dir": report["prompt_export_dir"],
            "summary": report["summary"],
            "checks": report["checks"],
        },
    }


def _paper_scale_check(
    annotation_release_dir: Path,
    prompt_export_dir: Path,
    scale_summary_path: Path,
    window_report_path: Path,
    *,
    profile: str,
    required: bool,
) -> dict[str, Any]:
    report = assess_release_scale(
        annotation_release_dir,
        profile=profile,
        scale_summary_path=scale_summary_path,
        window_report_path=window_report_path,
        prompt_export_dir=prompt_export_dir,
    )
    issues = [issue["message"] for issue in report["issues"]]
    warnings = [warning["message"] for warning in report["warnings"]]
    if not report["passed"] and required:
        status = "fail"
    elif not report["passed"] or report["warnings"]:
        status = "warn"
    else:
        status = "pass"
    return {
        "status": status,
        "issues": issues + warnings,
        "evidence": {
            "profile": report["profile"],
            "required": required,
            "summary": report["summary"],
            "checks": report["checks"],
            "recommended_next_actions": report["recommended_next_actions"],
        },
    }


def _public_data_discovery_check(discovery_path: Path) -> dict[str, Any]:
    discovery_path = Path(discovery_path)
    if discovery_path.exists():
        report = read_json(discovery_path)
    else:
        report = discover_public_data_sources(output_path=discovery_path)
    summary = report.get("summary", {})
    issues = []
    warnings = []
    if int(summary.get("usable_sources", 0)) <= 0:
        warnings.append("no locally discovered public workflow source is directly usable for paper-scale construction")
    if int(summary.get("github_code_only_sources", 0)) > 0:
        warnings.append("local GitHub code-text corpora were found but are not workflow event timelines")
    return {
        "status": "warn" if warnings else "pass",
        "issues": issues + warnings,
        "evidence": {
            "path": str(discovery_path),
            "summary": summary,
            "recommended_next_actions": report.get("recommended_next_actions", []),
        },
    }


def _workflow_source_audit_check(
    audit_path: Path,
    discovery_path: Path,
    stage_plan_path: Path,
    *,
    required: bool,
) -> dict[str, Any]:
    audit_path = Path(audit_path)
    discovery_path = Path(discovery_path)
    stage_plan_path = Path(stage_plan_path)
    if audit_path.exists():
        report = read_json(audit_path)
    elif discovery_path.exists():
        report = audit_workflow_data_sources(
            discovery_path,
            output_path=audit_path,
            gharchive_stage_plan_path=stage_plan_path if stage_plan_path.exists() else None,
            require_paper_ready=required,
        )
    else:
        status = "fail" if required else "warn"
        return {
            "status": status,
            "issues": ["workflow source audit missing and public data discovery report is unavailable"],
            "evidence": {"path": str(audit_path), "discovery_path": str(discovery_path), "required": required},
        }

    issues = [issue["message"] for issue in report.get("issues", [])]
    warnings = [warning["message"] for warning in report.get("warnings", [])]
    if required and report.get("paper_ready") is not True:
        status = "fail"
    elif report.get("passed") is not True or report.get("annotation_budget_ready") is not True or warnings:
        status = "warn"
    else:
        status = "pass"
    return {
        "status": status,
        "issues": issues + warnings,
        "evidence": {
            "path": str(audit_path),
            "discovery_report_path": report.get("discovery_report_path"),
            "gharchive_stage_plan_path": report.get("gharchive_stage_plan_path"),
            "summary": report.get("summary", {}),
            "annotation_budget_ready": report.get("annotation_budget_ready"),
            "paper_ready": report.get("paper_ready"),
            "stage_plan_decision": report.get("stage_plan_decision"),
            "recommended_next_actions": report.get("recommended_next_actions", []),
        },
    }


def _batch_rewrite_validation_check(report_path: Path) -> dict[str, Any]:
    report_path = Path(report_path)
    if not report_path.exists():
        return {
            "status": "warn",
            "issues": ["batch rewrite validation report missing; LLM/human proposal batch has not been validated"],
            "evidence": {"path": str(report_path)},
        }
    report = read_json(report_path)
    summary = report.get("summary", {})
    constraints = report.get("constraints", {})
    issues = []
    if report.get("passed") is not True:
        issues.append("batch rewrite validation report did not pass")
    if int(summary.get("packs_total", 0)) <= 0:
        issues.append("batch rewrite validation has no packs")
    if int(summary.get("packs_failed", 0)) > 0:
        issues.append("batch rewrite validation has failed packs")
    if int(summary.get("proposals_failed", 0)) > 0:
        issues.append("batch rewrite validation has failed proposals")
    if summary.get("require_complete") is not True:
        issues.append("batch rewrite validation should require complete annotation coverage for release")
    if constraints.get("llm_generation_performed") is not False:
        issues.append("batch rewrite validation must record llm_generation_performed=false")
    if constraints.get("requires_validate_policy_rewrites") is not True:
        issues.append("batch rewrite validation must require validate-policy-rewrites")
    return {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "evidence": {
            "path": str(report_path),
            "summary": summary,
            "constraints": constraints,
        },
    }


def _batch_rewrite_projects_check(report_path: Path) -> dict[str, Any]:
    report_path = Path(report_path)
    if not report_path.exists():
        return {
            "status": "warn",
            "issues": ["batch rewrite project report missing; validated proposal batch has not been converted into verifier-checked projects"],
            "evidence": {"path": str(report_path)},
        }
    report = read_json(report_path)
    summary = report.get("summary", {})
    constraints = report.get("constraints", {})
    issues = []
    if report.get("passed") is not True:
        issues.append("batch rewrite project report did not pass")
    if int(summary.get("projects_total", 0)) <= 0:
        issues.append("batch rewrite project report has no projects")
    if int(summary.get("projects_failed", 0)) > 0:
        issues.append("batch rewrite project report has failed projects")
    if constraints.get("requires_batch_rewrite_validation_passed") is not True:
        issues.append("batch rewrite project report must require passed batch validation")
    if constraints.get("requires_project_verifier_passed") is not True:
        issues.append("batch rewrite project report must require project verifier pass")
    return {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "evidence": {
            "path": str(report_path),
            "summary": summary,
            "constraints": constraints,
        },
    }


def _project_release_check(release_dir: Path) -> dict[str, Any]:
    release_dir = Path(release_dir)
    manifest_path = release_dir / "project_release_manifest.json"
    if not manifest_path.exists():
        return _missing("project benchmark release manifest missing", manifest_path)
    report = verify_project_benchmark_release(release_dir)
    issues = [issue["message"] for issue in report["issues"]]
    warnings = [warning["message"] for warning in report["warnings"]]
    status = "fail" if issues else ("warn" if warnings else "pass")
    return {
        "status": status,
        "issues": issues + warnings,
        "evidence": {
            "release_dir": report["release_dir"],
            "summary": report["summary"],
            "checks": report["checks"],
        },
    }


def _project_submission_inputs_check(input_dir: Path) -> dict[str, Any]:
    input_dir = Path(input_dir)
    manifest_path = input_dir / "submission_manifest.json"
    if not manifest_path.exists():
        return _missing("project submission input manifest missing", manifest_path)
    report = verify_project_submission_inputs(input_dir)
    issues = [issue["message"] for issue in report["issues"]]
    warnings = [warning["message"] for warning in report["warnings"]]
    status = "fail" if issues else ("warn" if warnings else "pass")
    return {
        "status": status,
        "issues": issues + warnings,
        "evidence": {
            "input_dir": report["input_dir"],
            "summary": report["summary"],
            "checks": report["checks"],
        },
    }


def _project_release_baseline_check(report_path: Path) -> dict[str, Any]:
    report_path = Path(report_path)
    if not report_path.exists():
        return _missing("project release baseline report missing", report_path)
    report = read_json(report_path)
    summary = report.get("summary", {})
    baseline_names = list(summary.get("baseline_names", []))
    baselines = summary.get("baselines", {})
    issues = []
    if int(summary.get("projects", 0)) <= 0:
        issues.append("project release baseline report has no projects")
    probes = int(summary.get("probes", 0))
    if probes <= 0:
        issues.append("project release baseline report has no probes")
    for required in ("raw_rag", "oracle_policy_graph"):
        if required not in baseline_names:
            issues.append(f"project release baseline report missing required baseline {required}")
    for baseline_name in baseline_names:
        baseline = baselines.get(baseline_name)
        if not isinstance(baseline, dict):
            issues.append(f"project release baseline summary missing metrics for {baseline_name}")
            continue
        if int(baseline.get("predictions", 0)) != probes:
            issues.append(f"project release baseline {baseline_name} predictions do not cover all probes")
        for metric in ("micro_evidence_recall", "micro_boundary_action_recall"):
            if metric not in baseline:
                issues.append(f"project release baseline {baseline_name} missing {metric}")
    return {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "evidence": {
            "path": str(report_path),
            "summary": summary,
        },
    }


def _project_release_prediction_check(report_path: Path) -> dict[str, Any]:
    report_path = Path(report_path)
    if not report_path.exists():
        return _missing("project release prediction scoring report missing", report_path)
    report = read_json(report_path)
    summary = report.get("summary", {})
    issues = []
    if int(summary.get("projects", 0)) <= 0:
        issues.append("project release prediction report has no projects")
    if int(summary.get("release_probes", 0)) <= 0:
        issues.append("project release prediction report has no release probes")
    if int(summary.get("predictions", 0)) <= 0:
        issues.append("project release prediction report has no predictions")
    if float(summary.get("probe_coverage", 0.0)) < 1.0:
        issues.append("project release prediction example does not cover all probes")
    if int(summary.get("unknown_or_invalid_predictions", 0)) > 0:
        issues.append("project release prediction report has invalid predictions")
    if int(summary.get("extra_predictions", 0)) > 0:
        issues.append("project release prediction report has extra predictions outside the release")
    for metric in ("micro_pass_rate", "micro_evidence_recall", "micro_boundary_action_recall"):
        if metric not in summary:
            issues.append(f"project release prediction report missing {metric}")
    return {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "evidence": {
            "path": str(report_path),
            "system_name": report.get("system_name"),
            "summary": summary,
        },
    }


def _paper_tables_check(table_dir: Path) -> dict[str, Any]:
    table_dir = Path(table_dir)
    json_path = table_dir / "paper_tables.json"
    if not json_path.exists():
        return _missing("paper table export missing", json_path)
    report = read_json(json_path)
    counts = report.get("counts", {})
    issues = []
    required_files = [
        "main_results.csv",
        "main_results.md",
        "task_breakdown.csv",
        "task_breakdown.md",
        "capability_breakdown.csv",
        "capability_breakdown.md",
        "failure_breakdown.csv",
        "failure_breakdown.md",
        "confidence_intervals.csv",
        "confidence_intervals.md",
    ]
    missing_files = [name for name in required_files if not (table_dir / name).exists()]
    if missing_files:
        issues.append("paper table export missing files: " + ", ".join(missing_files))
    if int(counts.get("systems", 0)) <= 0:
        issues.append("paper table export has no systems")
    if int(counts.get("task_rows", 0)) <= 0:
        issues.append("paper table export has no task breakdown rows")
    if int(counts.get("capability_rows", 0)) <= 0:
        issues.append("paper table export has no capability breakdown rows")
    if int(counts.get("confidence_interval_rows", 0)) <= 0:
        issues.append("paper table export has no confidence interval rows")
    main_results = report.get("main_results", [])
    if not isinstance(main_results, list) or len(main_results) != int(counts.get("systems", 0)):
        issues.append("paper table main_results count does not match systems count")
    confidence_intervals = report.get("confidence_intervals", [])
    if not isinstance(confidence_intervals, list) or len(confidence_intervals) != int(counts.get("confidence_interval_rows", 0)):
        issues.append("paper table confidence_intervals count does not match confidence_interval_rows count")
    source_reports = report.get("source_reports", [])
    if not source_reports:
        issues.append("paper table export records no source reports")
    return {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "evidence": {
            "table_dir": str(table_dir),
            "path": str(json_path),
            "counts": counts,
            "source_reports": source_reports,
        },
    }


def _rewrite_human_audit_check(report_path: Path) -> dict[str, Any]:
    report_path = Path(report_path)
    if not report_path.exists():
        return {
            "status": "warn",
            "issues": ["human audit validation report missing; LLM rewrite proposals have not been spot-checked by reviewers"],
            "evidence": {"path": str(report_path)},
        }
    report = read_json(report_path)
    summary = report.get("summary", {})
    issues = [issue.get("code", str(issue)) for issue in report.get("issues", [])]
    warnings = [warning.get("code", str(warning)) for warning in report.get("warnings", [])]
    status = "fail" if report.get("passed") is not True else ("warn" if warnings else "pass")
    return {
        "status": status,
        "issues": issues + warnings,
        "evidence": {
            "path": str(report_path),
            "audit_pack_dir": report.get("audit_pack_dir"),
            "decisions_path": report.get("decisions_path"),
            "summary": summary,
            "sample": report.get("sample", {}),
        },
    }


def _probe_leakage_audit_check(report_path: Path, release_dir: Path, *, required: bool) -> dict[str, Any]:
    report_path = Path(report_path)
    if report_path.exists():
        report = read_json(report_path)
    elif Path(release_dir, "project_release_manifest.json").exists():
        report = audit_project_release_probe_leakage(release_dir, output_path=report_path)
    else:
        status = "fail" if required else "warn"
        return {
            "status": status,
            "issues": ["probe leakage audit missing and project release is unavailable"],
            "evidence": {"path": str(report_path), "release_dir": str(release_dir), "required": required},
        }
    summary = report.get("summary", {})
    issues = []
    warnings = []
    high_any = int(summary.get("high_any_overlap_probes", 0))
    probes = int(summary.get("probes", 0))
    high_rate = high_any / max(1, probes)
    if probes <= 0:
        issues.append("probe leakage audit contains no probes")
    if high_rate >= 0.25:
        warnings.append(
            f"high lexical overlap between probe queries and gold policy/action terms: {high_any}/{probes} probes >= threshold"
        )
    status = "fail" if issues else ("warn" if warnings else "pass")
    return {
        "status": status,
        "issues": issues + warnings,
        "evidence": {
            "path": str(report_path),
            "release_dir": report.get("release_dir"),
            "high_overlap_threshold": report.get("high_overlap_threshold"),
            "summary": summary,
        },
    }


def _rewrite_project_check(rewrite_project_dir: Path) -> dict[str, Any]:
    project_dir = Path(rewrite_project_dir)
    if not project_dir.exists():
        return _missing("rewrite-derived project missing", project_dir)
    report = run_project_verifier(project_dir)
    issues = list(report.issues)
    return {
        "status": "pass" if report.passed else "fail",
        "issues": issues,
        "evidence": {
            "project_dir": str(project_dir),
            "project_id": report.project_id,
            "verifier_passed": report.passed,
            "counts": report.counts,
        },
    }


def _staged_slice_manifest_check(manifest_path: Path) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        return {
            "status": "warn",
            "issues": ["staged GHArchive slice manifest missing; real public-data scale run not yet staged"],
            "evidence": {"path": str(manifest_path)},
        }
    manifest = read_json(manifest_path)
    counts = manifest.get("counts", {})
    constraints = manifest.get("constraints", {})
    issues = []
    warnings = []
    if int(counts.get("records_selected", 0)) <= 0:
        issues.append("staged slice selected no records")
    if constraints.get("network_download_performed") is not False:
        issues.append("staged slice manifest must record network_download_performed=false")
    if constraints.get("llm_generation_allowed") is not False:
        issues.append("staged slice manifest must record llm_generation_allowed=false")
    if int(counts.get("repos_eligible", 0)) <= 0:
        warnings.append("staged slice has no eligible repos")
    status = "fail" if issues else ("warn" if warnings else "pass")
    return {
        "status": status,
        "issues": issues + warnings,
        "evidence": {
            "path": str(manifest_path),
            "counts": counts,
            "eligible_repos": manifest.get("eligible_repos", []),
            "constraints": constraints,
        },
    }


def _gharchive_stage_plan_check(report_path: Path, *, required: bool) -> dict[str, Any]:
    report_path = Path(report_path)
    if not report_path.exists():
        status = "fail" if required else "warn"
        return {
            "status": status,
            "issues": ["GHArchive stage plan missing; raw-slice annotation-budget decision has not been recorded"],
            "evidence": {"path": str(report_path), "required": required},
        }
    report = read_json(report_path)
    summary = report.get("summary", {})
    decision = report.get("decision", {})
    constraints = report.get("constraints", {})
    issues = []
    warnings = []
    if constraints.get("network_download_performed") is not False:
        issues.append("GHArchive stage plan must record network_download_performed=false")
    if constraints.get("llm_generation_performed") is not False:
        issues.append("GHArchive stage plan must record llm_generation_performed=false")
    if decision.get("ready_for_annotation_budget") is not True:
        message = "GHArchive stage plan is not ready for annotation budget"
        if required:
            issues.append(message)
        else:
            warnings.append(message)
    if summary.get("passed") is not True:
        message = "GHArchive stage plan has failed raw-slice checks"
        if required:
            issues.append(message)
        else:
            warnings.append(message)
    status = "fail" if issues else ("warn" if warnings else "pass")
    return {
        "status": status,
        "issues": issues + warnings,
        "evidence": {
            "path": str(report_path),
            "required": required,
            "profile": report.get("profile"),
            "summary": summary,
            "decision": decision,
        },
    }


def _missing(issue: str, path: Path) -> dict[str, Any]:
    return {"status": "fail", "issues": [issue], "evidence": {"path": str(path)}}
