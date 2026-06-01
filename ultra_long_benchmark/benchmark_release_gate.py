from __future__ import annotations

from pathlib import Path
from typing import Any

from ultra_long_benchmark.artifact_bundle import verify_artifact_bundle_manifest
from ultra_long_benchmark.claim_boundary import verify_paper_claim_boundary_audit
from ultra_long_benchmark.claim_lint import verify_paper_claim_lint_report
from ultra_long_benchmark.domain_expansion import verify_domain_expansion_readiness_report
from ultra_long_benchmark.pipelines.baseline_configs import verify_baseline_config_validation_report
from ultra_long_benchmark.pipelines.workflow_manifest_project import verify_workflow_manifest_preflight_batch_report
from ultra_long_benchmark.pipelines.workflow_manifest_project import verify_workflow_manifest_preflight_report
from ultra_long_benchmark.shared.io import read_json, write_json
from ultra_long_benchmark.taxonomy_coverage import verify_project_release_taxonomy_coverage_audit


DEFAULT_GATE_REPORTS = {
    "readiness_report": "examples/generated/readiness_report_gharchive_formal.json",
    "claim_boundary_audit": "examples/generated/evaluation_harness/gharchive_formal_claim_boundary_audit.json",
    "claim_boundary_verification": "examples/generated/evaluation_harness/gharchive_formal_claim_boundary_verification.json",
    "claim_lint": "examples/generated/evaluation_harness/gharchive_formal_claim_lint.json",
    "artifact_bundle_manifest": "examples/generated/evaluation_harness/gharchive_formal_artifact_bundle_manifest.json",
    "artifact_bundle_verification": "examples/generated/evaluation_harness/gharchive_formal_artifact_bundle_verification.json",
    "taxonomy_coverage_audit": "examples/generated/evaluation_harness/gharchive_formal_taxonomy_coverage_audit.json",
    "domain_expansion_readiness": "examples/generated/evaluation_harness/gharchive_formal_domain_expansion_readiness.json",
    "baseline_config_validation": "examples/generated/evaluation_harness/baseline_config_validation_after_artifact_bundle.json",
}

EXPECTED_WARNING_CHECKS = {
    "rewrite_human_audit",
    "taxonomy_coverage_audit",
    "claim_boundary_audit",
    "artifact_bundle_manifest",
}
EXPECTED_ARTIFACT_WARNING_CODES = {
    "claim_boundary_has_blocked_claims",
    "github_only_release_scope",
}
EXPECTED_TAXONOMY_WARNING_CODES = {
    "bridge_streams_not_counted_as_real_domains",
    "capabilities_not_in_current_release",
    "workflow_domains_not_in_current_release",
}
EXPECTED_BLOCKED_CLAIMS = {
    "multi_domain_office_release",
    "reviewed_real_email_workflow_release",
    "human_audited_rewrite_quality",
    "executed_sota_memory_baselines",
    "original_query_scores_as_sota",
}


def build_benchmark_release_gate_report(
    reports: dict[str, Path | str] | None = None,
    output_path: Path | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Summarize benchmark release gate status from existing reports."""

    root = Path(root or Path.cwd())
    report_paths = reports or {name: root / rel_path for name, rel_path in DEFAULT_GATE_REPORTS.items()}
    loaded: dict[str, dict[str, Any]] = {}
    checks: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for name, raw_path in sorted(report_paths.items()):
        path = _resolve_path(Path(raw_path), root)
        if not path.exists():
            checks[name] = {"status": "fail", "path": str(path), "issues": ["report missing"]}
            _issue(issues, "gate_report_missing", f"gate report missing: {name}", path)
            continue
        payload = read_json(path)
        loaded[name] = payload
        checks[name] = {
            "status": "pass",
            "path": str(path),
            "summary": payload.get("summary", {}),
        }

    _expand_workflow_manifest_preflight_batches(loaded, checks, issues, root)
    _check_readiness(loaded.get("readiness_report"), checks, issues, warnings)
    _check_claim_boundary(loaded.get("claim_boundary_audit"), checks, issues, warnings)
    _check_claim_verification(loaded.get("claim_boundary_verification"), checks, issues)
    _check_claim_verification_target(loaded.get("claim_boundary_verification"), checks, issues)
    _check_claim_boundary_live_verification(checks, issues)
    _check_claim_lint(loaded.get("claim_lint"), checks, issues)
    _check_artifact_bundle(loaded.get("artifact_bundle_manifest"), "artifact_bundle_manifest", checks, issues, warnings)
    _check_artifact_bundle(loaded.get("artifact_bundle_verification"), "artifact_bundle_verification", checks, issues, warnings)
    _check_artifact_bundle_verification_target(loaded.get("artifact_bundle_verification"), checks, issues)
    _check_taxonomy(loaded.get("taxonomy_coverage_audit"), checks, issues, warnings)
    _check_domain_expansion(loaded.get("domain_expansion_readiness"), checks, issues, warnings)
    _check_baseline_config(loaded.get("baseline_config_validation"), checks, issues)
    _check_workflow_manifest_preflights(loaded, checks, issues, root)

    for check in checks.values():
        if check.get("status") == "fail":
            continue
        if check.get("warnings"):
            check["status"] = "warn"

    workflow_preflight_checks = {
        name: check for name, check in checks.items() if _is_workflow_manifest_preflight_name(name)
    }
    summary = {
        "reports_total": len(checks),
        "reports_present": sum(1 for check in checks.values() if "report missing" not in check.get("issues", [])),
        "checks_failed": sum(1 for check in checks.values() if check.get("status") == "fail"),
        "checks_warn": sum(1 for check in checks.values() if check.get("status") == "warn"),
        "checks_passed": sum(1 for check in checks.values() if check.get("status") == "pass"),
        "issues": len(issues),
        "warnings": len(warnings),
        "issue_codes": sorted({issue["code"] for issue in issues}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
        "release_scope": _release_scope(loaded.get("taxonomy_coverage_audit")),
        "supported_claims": _claim_count(loaded.get("claim_boundary_audit"), "supported"),
        "blocked_claims": _claim_count(loaded.get("claim_boundary_audit"), "blocked"),
        "workflow_manifest_preflights": len(workflow_preflight_checks),
        "workflow_manifest_preflight_domains": sorted(
            {
                str(check.get("domain"))
                for check in workflow_preflight_checks.values()
                if check.get("status") != "fail" and check.get("domain")
            }
        ),
    }
    report = {
        "passed": not issues,
        "root": str(root),
        "scope": "github_developer_workflow_only",
        "summary": summary,
        "checks": checks,
        "issues": issues,
        "warnings": warnings,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def _check_readiness(
    report: dict[str, Any] | None,
    checks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    if report is None:
        return
    check = checks["readiness_report"]
    summary = report.get("summary", {})
    warning_checks = set(summary.get("warning_checks", []))
    if report.get("passed") is not True or int(summary.get("failed", 0)) != 0:
        _fail(check, issues, "readiness_not_passed", "readiness report did not pass")
    unexpected = sorted(warning_checks - EXPECTED_WARNING_CHECKS)
    missing = sorted(EXPECTED_WARNING_CHECKS - warning_checks)
    if unexpected:
        _fail(check, issues, "unexpected_readiness_warnings", "readiness has unexpected warning checks: " + ", ".join(unexpected))
    if missing:
        _warn(check, warnings, "missing_expected_readiness_warnings", "readiness no longer records expected caveats: " + ", ".join(missing))
    if not unexpected and not missing and warning_checks == EXPECTED_WARNING_CHECKS:
        _warn(check, warnings, "readiness_expected_caveats", "readiness records the expected benchmark-release caveats")
    if int(summary.get("checks_total", 0)) < 23:
        _fail(check, issues, "readiness_check_count_low", "readiness report has fewer than 23 checks")


def _check_claim_boundary(
    report: dict[str, Any] | None,
    checks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    if report is None:
        return
    check = checks["claim_boundary_audit"]
    summary = report.get("summary", {})
    blocked = set(summary.get("blocked_claims", []))
    if report.get("passed") is not True:
        _fail(check, issues, "claim_boundary_not_passed", "claim-boundary audit did not pass")
    if int(summary.get("supported", 0)) < 6:
        _fail(check, issues, "supported_claim_count_low", "claim-boundary audit has fewer than 6 supported claims")
    if blocked != EXPECTED_BLOCKED_CLAIMS:
        _fail(check, issues, "blocked_claim_set_changed", "claim-boundary blocked claim set changed")
    else:
        _warn(check, warnings, "claim_boundary_has_blocked_claims", "claim-boundary audit intentionally blocks unreleased paper claims")


def _check_claim_verification(
    report: dict[str, Any] | None,
    checks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    if report is None:
        return
    check = checks["claim_boundary_verification"]
    summary = report.get("summary", {})
    if report.get("passed") is not True or int(summary.get("issues", 0)) != 0:
        _fail(check, issues, "claim_boundary_verification_not_passed", "claim-boundary verification did not pass")
    if summary.get("original_supported") != summary.get("recomputed_supported") or summary.get("original_blocked") != summary.get("recomputed_blocked"):
        _fail(check, issues, "claim_boundary_verification_mismatch", "claim-boundary verification counts changed")


def _check_claim_verification_target(
    report: dict[str, Any] | None,
    checks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    check = checks.get("claim_boundary_verification")
    claim_check = checks.get("claim_boundary_audit")
    if report is None or not check or not claim_check or claim_check.get("status") == "fail":
        return
    expected = Path(claim_check["path"]).resolve()
    actual_raw = report.get("report_path")
    actual = Path(str(actual_raw)).resolve() if actual_raw else None
    check["expected_report_path"] = str(expected)
    if actual is None or actual != expected:
        _fail(
            check,
            issues,
            "claim_boundary_verification_target_mismatch",
            "claim-boundary verification report does not target the gate claim-boundary audit",
        )


def _check_claim_boundary_live_verification(
    checks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    check = checks.get("claim_boundary_verification")
    claim_check = checks.get("claim_boundary_audit")
    if not check or not claim_check or claim_check.get("status") == "fail":
        return
    verification = verify_paper_claim_boundary_audit(Path(claim_check["path"]))
    check["live_verification_summary"] = verification.get("summary", {})
    if verification.get("passed") is not True:
        _fail(check, issues, "claim_boundary_live_verification_not_passed", "claim-boundary audit inputs changed or recomputation drifted")


def _check_claim_lint(
    report: dict[str, Any] | None,
    checks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    if report is None:
        return
    check = checks["claim_lint"]
    summary = report.get("summary", {})
    if report.get("passed") is not True or int(summary.get("issues", 0)) != 0:
        _fail(check, issues, "claim_lint_not_passed", "paper claim lint did not pass")
    if int(summary.get("files_scanned", 0)) < 4:
        _fail(check, issues, "claim_lint_file_count_low", "paper claim lint scanned fewer than 4 files")
    verification = verify_paper_claim_lint_report(Path(check["path"]))
    check["verification_summary"] = verification.get("summary", {})
    if verification.get("passed") is not True:
        _fail(check, issues, "claim_lint_verification_not_passed", "paper claim lint source files changed or lack digests")


def _check_artifact_bundle(
    report: dict[str, Any] | None,
    name: str,
    checks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    if report is None:
        return
    check = checks[name]
    summary = report.get("summary", {})
    if report.get("passed") is not True or int(summary.get("issues", 0)) != 0:
        _fail(check, issues, f"{name}_not_passed", f"{name} did not pass")
    present_or_verified = int(summary.get("artifacts_present", summary.get("artifacts_verified", 0)))
    total = int(summary.get("artifacts_total", 0))
    if total < 20 or present_or_verified != total:
        _fail(check, issues, f"{name}_coverage_mismatch", f"{name} does not cover all required artifacts")
    warning_codes = set(summary.get("warning_codes", []))
    if warning_codes != EXPECTED_ARTIFACT_WARNING_CODES:
        _fail(check, issues, f"{name}_warning_set_changed", f"{name} warning set changed")
    else:
        _warn(check, warnings, f"{name}_expected_caveats", f"{name} carries expected GitHub-only and blocked-claim caveats")
    if name == "artifact_bundle_manifest":
        verification = verify_artifact_bundle_manifest(Path(check["path"]))
        check["verification_summary"] = verification.get("summary", {})
        if verification.get("passed") is not True:
            _fail(
                check,
                issues,
                "artifact_bundle_manifest_live_verification_not_passed",
                "artifact bundle manifest artifacts changed or lack digests",
            )


def _check_artifact_bundle_verification_target(
    report: dict[str, Any] | None,
    checks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    check = checks.get("artifact_bundle_verification")
    manifest_check = checks.get("artifact_bundle_manifest")
    if report is None or not check or not manifest_check or manifest_check.get("status") == "fail":
        return
    expected = Path(manifest_check["path"]).resolve()
    actual_raw = report.get("manifest_path")
    actual = Path(str(actual_raw)).resolve() if actual_raw else None
    check["expected_manifest_path"] = str(expected)
    if actual is None or actual != expected:
        _fail(
            check,
            issues,
            "artifact_bundle_verification_target_mismatch",
            "artifact-bundle verification report does not target the gate artifact-bundle manifest",
        )


def _check_taxonomy(
    report: dict[str, Any] | None,
    checks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    if report is None:
        return
    check = checks["taxonomy_coverage_audit"]
    summary = report.get("summary", {})
    if report.get("passed") is not True:
        _fail(check, issues, "taxonomy_coverage_not_passed", "taxonomy coverage audit did not pass")
    if summary.get("current_release_domain_scope") != "github_developer_workflow_only":
        _fail(check, issues, "release_scope_changed", "release scope is not github_developer_workflow_only")
    if summary.get("multi_domain_release_ready") is True:
        _fail(check, issues, "unexpected_multi_domain_ready", "taxonomy audit unexpectedly marks multi-domain release ready")
    warning_codes = set(summary.get("warning_codes", []))
    if warning_codes != EXPECTED_TAXONOMY_WARNING_CODES:
        _fail(check, issues, "taxonomy_warning_set_changed", "taxonomy warning set changed")
    else:
        _warn(check, warnings, "taxonomy_github_only_scope", "taxonomy audit intentionally records GHArchive/GitHub-only scope")
    verification = verify_project_release_taxonomy_coverage_audit(Path(check["path"]))
    check["verification_summary"] = verification.get("summary", {})
    if verification.get("passed") is not True:
        _fail(check, issues, "taxonomy_coverage_verification_not_passed", "taxonomy coverage audit release artifacts changed or lack digests")


def _check_baseline_config(
    report: dict[str, Any] | None,
    checks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    if report is None:
        return
    check = checks["baseline_config_validation"]
    summary = report.get("summary", {})
    if int(summary.get("configs_failed", 0)) != 0:
        _fail(check, issues, "baseline_configs_failed", "baseline config validation has failures")
    if int(summary.get("configs_passed", 0)) < 6:
        _fail(check, issues, "baseline_config_count_low", "baseline config validation passed fewer than 6 formal configs")
    verification = verify_baseline_config_validation_report(Path(check["path"]))
    check["verification_summary"] = verification.get("summary", {})
    if verification.get("passed") is not True:
        _fail(check, issues, "baseline_config_verification_not_passed", "baseline config files changed or lack digests")


def _check_domain_expansion(
    report: dict[str, Any] | None,
    checks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    if report is None:
        return
    check = checks["domain_expansion_readiness"]
    summary = report.get("summary", {})
    if report.get("passed") is not True or int(summary.get("issues", 0)) != 0:
        _fail(check, issues, "domain_expansion_not_passed", "domain expansion readiness did not pass")
    verification = verify_domain_expansion_readiness_report(Path(check["path"]))
    check["verification_summary"] = verification.get("summary", {})
    if verification.get("passed") is not True:
        _fail(check, issues, "domain_expansion_verification_not_passed", "domain expansion input reports changed or lack digests")
    if summary.get("release_ready_domains") != ["github_developer_workflow"]:
        _fail(check, issues, "domain_expansion_ready_domain_set_changed", "domain expansion ready domain set changed")
    if summary.get("multi_domain_release_ready") is True:
        _fail(check, issues, "unexpected_domain_expansion_multi_domain_ready", "domain expansion unexpectedly marks multi-domain release ready")
    required = {
        "multi_domain_expansion_not_ready",
    }
    allowed = {
        "domain_release_pipeline_missing",
        "email_license_privacy_manifest_missing",
        "multi_domain_expansion_not_ready",
        "planned_domains_not_released",
    }
    warning_codes = set(summary.get("warning_codes", []))
    missing = sorted(required - warning_codes)
    unexpected = sorted(warning_codes - allowed)
    if missing or unexpected:
        detail = []
        if missing:
            detail.append("missing expected warning codes: " + ", ".join(missing))
        if unexpected:
            detail.append("unexpected warning codes: " + ", ".join(unexpected))
        _fail(check, issues, "domain_expansion_warning_set_changed", "domain expansion warning set changed; " + "; ".join(detail))
    else:
        _warn(check, warnings, "domain_expansion_expected_caveats", "domain expansion audit records expected GitHub-only caveats")


def _check_workflow_manifest_preflights(
    loaded: dict[str, dict[str, Any]],
    checks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    root: Path,
) -> None:
    names = sorted(name for name in loaded if _is_workflow_manifest_preflight_name(name))
    if not names:
        return
    domain_expansion = loaded.get("domain_expansion_readiness") or {}
    domain_summary = domain_expansion.get("summary", {}) if isinstance(domain_expansion.get("summary"), dict) else {}
    recorded_preflight_domains = set(domain_summary.get("preflight_ready_domains", []) or [])

    for name in names:
        report = loaded[name]
        check = checks[name]
        summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
        constraints = report.get("constraints", {}) if isinstance(report.get("constraints"), dict) else {}
        domain = str(report.get("domain") or "")
        check["domain"] = domain
        check["project_id"] = report.get("project_id")
        check["constraints"] = {
            "llm_generation_performed": constraints.get("llm_generation_performed"),
            "release_ready_claim": constraints.get("release_ready_claim"),
            "benchmark_release_gate_integration_required": constraints.get("benchmark_release_gate_integration_required"),
        }
        if report.get("passed") is not True or int(summary.get("issues", 0) or 0) != 0:
            _fail(check, issues, "workflow_manifest_preflight_not_passed", f"workflow manifest preflight did not pass: {name}")
        if constraints.get("llm_generation_performed") is not False:
            _fail(
                check,
                issues,
                "workflow_manifest_preflight_llm_generation_ambiguous",
                f"workflow manifest preflight must record llm_generation_performed=false: {name}",
            )
        if constraints.get("release_ready_claim") is not False:
            _fail(
                check,
                issues,
                "workflow_manifest_preflight_release_claim_ambiguous",
                f"workflow manifest preflight must record release_ready_claim=false: {name}",
            )
        verification = verify_workflow_manifest_preflight_report(Path(check["path"]), root=root)
        check["verification_summary"] = verification.get("summary", {})
        if verification.get("passed") is not True:
            _fail(
                check,
                issues,
                "workflow_manifest_preflight_verification_not_passed",
                f"workflow manifest preflight artifacts changed or lack digests: {name}",
            )
        if domain and verification.get("passed") is True and domain not in recorded_preflight_domains:
            _fail(
                check,
                issues,
                "workflow_manifest_preflight_not_recorded_in_domain_expansion",
                f"workflow manifest preflight domain is not recorded by domain-expansion readiness: {domain}",
            )


def _expand_workflow_manifest_preflight_batches(
    loaded: dict[str, dict[str, Any]],
    checks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    root: Path,
) -> None:
    batch_names = sorted(name for name in loaded if _is_workflow_manifest_preflight_batch_name(name))
    next_index = _next_workflow_manifest_preflight_index(loaded)
    for batch_name in batch_names:
        batch_report = loaded[batch_name]
        batch_check = checks[batch_name]
        verification = verify_workflow_manifest_preflight_batch_report(Path(batch_check["path"]), root=root)
        batch_check["verification_summary"] = verification.get("summary", {})
        batch_check["domains"] = batch_report.get("summary", {}).get("domains", [])
        if verification.get("passed") is not True or batch_report.get("passed") is not True:
            _fail(
                batch_check,
                issues,
                "workflow_manifest_preflight_batch_verification_not_passed",
                f"workflow manifest preflight batch did not verify: {batch_name}",
            )
            continue
        for item in batch_report.get("preflight_reports", []):
            if not isinstance(item, dict) or not item.get("report_path"):
                _fail(
                    batch_check,
                    issues,
                    "workflow_manifest_preflight_batch_record_invalid",
                    f"workflow manifest preflight batch has invalid item: {batch_name}",
                )
                continue
            preflight_path = _resolve_path(Path(str(item["report_path"])), root)
            preflight_name = f"workflow_manifest_preflight_{next_index}"
            next_index += 1
            if preflight_name in loaded:
                continue
            if not preflight_path.exists():
                loaded[preflight_name] = {}
                checks[preflight_name] = {"status": "fail", "path": str(preflight_path), "issues": ["report missing"], "source_batch": batch_name}
                _issue(issues, "gate_report_missing", f"gate report missing: {preflight_name}", preflight_path)
                continue
            payload = read_json(preflight_path)
            loaded[preflight_name] = payload
            checks[preflight_name] = {
                "status": "pass",
                "path": str(preflight_path),
                "summary": payload.get("summary", {}),
                "source_batch": batch_name,
            }


def _release_scope(report: dict[str, Any] | None) -> str | None:
    if report is None:
        return None
    return report.get("summary", {}).get("current_release_domain_scope")


def _claim_count(report: dict[str, Any] | None, key: str) -> int | None:
    if report is None:
        return None
    value = report.get("summary", {}).get(key)
    return int(value) if value is not None else None


def _resolve_path(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def _is_workflow_manifest_preflight_name(name: str) -> bool:
    return name.startswith("workflow_manifest_preflight_") and not name.startswith("workflow_manifest_preflight_batch_")


def _is_workflow_manifest_preflight_batch_name(name: str) -> bool:
    return name.startswith("workflow_manifest_preflight_batch")


def _next_workflow_manifest_preflight_index(loaded: dict[str, dict[str, Any]]) -> int:
    prefix = "workflow_manifest_preflight_"
    indices = []
    for name in loaded:
        if not _is_workflow_manifest_preflight_name(name):
            continue
        suffix = name.removeprefix(prefix)
        if suffix.isdigit():
            indices.append(int(suffix))
    return (max(indices) + 1) if indices else 0


def _fail(check: dict[str, Any], issues: list[dict[str, Any]], code: str, message: str) -> None:
    check.setdefault("issues", []).append(message)
    check["status"] = "fail"
    _issue(issues, code, message, check.get("path"))


def _warn(check: dict[str, Any], warnings: list[dict[str, Any]], code: str, message: str) -> None:
    check.setdefault("warnings", []).append(message)
    _warning(warnings, code, message, check.get("path"))


def _issue(issues: list[dict[str, Any]], code: str, message: str, path: Path | str | None = None) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        item["path"] = str(path)
    issues.append(item)


def _warning(warnings: list[dict[str, Any]], code: str, message: str, path: Path | str | None = None) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        item["path"] = str(path)
    warnings.append(item)
