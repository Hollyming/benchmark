from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ultra_long_benchmark.pipelines.workflow_manifest_project import verify_workflow_manifest_preflight_batch_report
from ultra_long_benchmark.pipelines.workflow_manifest_project import verify_workflow_manifest_preflight_report
from ultra_long_benchmark.shared.io import read_json, write_json
from ultra_long_benchmark.taxonomy_coverage import DOMAIN_DEFINITIONS


DEFAULT_DOMAIN_EXPANSION_REPORTS = {
    "readiness_report": "examples/generated/readiness_report_gharchive_formal.json",
    "taxonomy_coverage_audit": "examples/generated/evaluation_harness/gharchive_formal_taxonomy_coverage_audit.json",
    "workflow_source_audit": "examples/generated/workflow_data_source_audit.json",
    "public_data_discovery": "examples/generated/public_data_discovery_report.json",
    "claim_boundary_audit": "examples/generated/evaluation_harness/gharchive_formal_claim_boundary_audit.json",
}

DOMAIN_REQUIREMENTS = [
    "reusable_trace_source",
    "license_privacy_pii_gate",
    "canonical_event_adapter",
    "verifier_checked_project_release",
    "no_gold_submission_input",
    "baseline_and_external_runner_contract",
    "taxonomy_and_claim_boundary",
    "readiness_and_artifact_gate",
]

ADAPTER_STATUS = {
    "github_developer_workflow": "implemented",
    "email_workflow": "implemented_manifest_first",
    "calendar_workflow": "implemented_manifest_first",
    "docs_workflow": "implemented_manifest_first",
    "chat_workflow": "implemented_manifest_first",
    "browser_web_workflow": "implemented_manifest_first",
}

GATE_ARTIFACTS = {
    "reusable_trace_source": "audited reusable longitudinal trace source",
    "license_privacy_pii_gate": "license/privacy/PII review manifest",
    "canonical_event_adapter": "canonical domain event adapter",
    "verifier_checked_project_release": "verifier-checked project release",
    "no_gold_submission_input": "domain no-gold submission input pack",
    "baseline_and_external_runner_contract": "domain baseline and external-runner contract",
    "taxonomy_and_claim_boundary": "taxonomy and paper-claim boundary support",
    "readiness_and_artifact_gate": "readiness and artifact-bundle gate coverage",
}

DOWNSTREAM_RELEASE_GATES = {
    "verifier_checked_project_release",
    "no_gold_submission_input",
    "baseline_and_external_runner_contract",
    "taxonomy_and_claim_boundary",
    "readiness_and_artifact_gate",
}


def build_domain_expansion_readiness_report(
    reports: dict[str, Path | str] | None = None,
    output_path: Path | None = None,
    *,
    root: Path | None = None,
    require_multi_domain: bool = False,
    workflow_manifest_preflight_reports: list[Path | str] | None = None,
    workflow_manifest_preflight_batch_reports: list[Path | str] | None = None,
) -> dict[str, Any]:
    """Audit which workflow domains are release-ready and why others are gated."""

    root = Path(root or Path.cwd())
    report_paths = reports or {name: root / rel_path for name, rel_path in DEFAULT_DOMAIN_EXPANSION_REPORTS.items()}
    loaded: dict[str, dict[str, Any]] = {}
    input_checks: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for name, raw_path in sorted(report_paths.items()):
        path = _resolve_path(Path(raw_path), root)
        required = name == "taxonomy_coverage_audit"
        if not path.exists():
            input_checks[name] = {"status": "fail" if required else "warn", "path": str(path), "issues": ["report missing"]}
            if required:
                _issue(issues, "domain_expansion_required_report_missing", f"required domain-expansion input report missing: {name}", path)
            else:
                _warn(warnings, "domain_expansion_optional_report_missing", f"optional domain-expansion input report missing: {name}", path)
            continue
        loaded[name] = read_json(path)
        input_checks[name] = {
            "status": "pass",
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
            "summary": loaded[name].get("summary", {}),
        }
    expanded_preflight_reports = _expand_workflow_manifest_preflight_batches(
        workflow_manifest_preflight_batch_reports or [],
        root,
        input_checks,
        warnings,
    )
    preflight_inputs = _load_workflow_manifest_preflights(
        [*(workflow_manifest_preflight_reports or []), *expanded_preflight_reports],
        root,
        input_checks,
        warnings,
    )

    taxonomy = loaded.get("taxonomy_coverage_audit", {})
    readiness = loaded.get("readiness_report", {})
    source_audit = loaded.get("workflow_source_audit", {})
    discovery = loaded.get("public_data_discovery", {})
    claim_boundary = loaded.get("claim_boundary_audit", {})
    domains = _domain_rows(taxonomy, readiness, source_audit, discovery, claim_boundary, preflight_inputs)

    ready_domains = [name for name, item in domains.items() if item["ready_for_current_release"] is True]
    covered_domains = [name for name, item in domains.items() if item["taxonomy_status"] == "covered"]
    blocked_domains = [name for name, item in domains.items() if item["status"].startswith("blocked")]
    planned_domains = [name for name, item in domains.items() if item["status"] == "planned_not_released"]
    pipeline_missing_domains = [name for name, item in domains.items() if item["status"] == "source_manifest_ready_release_pipeline_missing"]
    preflight_ready_domains = [name for name, item in domains.items() if item["roadmap"].get("preflight_passed") is True]
    external_input_blocked_domains = [
        name for name, item in domains.items() if item["roadmap"]["external_input_required_for_release"] is True
    ]
    offline_engineering_blocked_domains = [
        name for name, item in domains.items() if item["roadmap"]["offline_engineering_required"] is True
    ]
    multi_domain_ready = len(ready_domains) > 1

    if require_multi_domain and not multi_domain_ready:
        _issue(
            issues,
            "multi_domain_expansion_required",
            "at least two release-ready real workflow domains are required, but the current evidence does not prove that",
        )
    if not multi_domain_ready:
        _warn(
            warnings,
            "multi_domain_expansion_not_ready",
            "current evidence supports a GitHub developer workflow release, not a multi-domain workflow release",
            ready_domains=ready_domains,
        )
    email = domains.get("email_workflow", {})
    if "email_workflow" in blocked_domains and email.get("roadmap", {}).get("preflight_passed") is not True:
        _warn(
            warnings,
            "email_license_privacy_manifest_missing",
            "email workflow expansion is blocked until a reviewed license/privacy/PII manifest is available",
        )
    if planned_domains:
        _warn(
            warnings,
            "planned_domains_not_released",
            "planned non-GitHub workflow domains do not yet have release-ready traces, adapters, verifiers, and no-gold inputs",
            domains=planned_domains,
        )
    if pipeline_missing_domains:
        _warn(
            warnings,
            "domain_release_pipeline_missing",
            "some domains have source evidence but still need verifier-checked release artifacts and evaluation gates",
            domains=pipeline_missing_domains,
        )

    summary = {
        "domains_total": len(domains),
        "release_ready_domains": ready_domains,
        "covered_workflow_domains": covered_domains,
        "blocked_domains": blocked_domains,
        "planned_domains": planned_domains,
        "pipeline_missing_domains": pipeline_missing_domains,
        "preflight_ready_domains": preflight_ready_domains,
        "external_input_blocked_domains": external_input_blocked_domains,
        "offline_engineering_blocked_domains": offline_engineering_blocked_domains,
        "current_release_domain_scope": taxonomy.get("summary", {}).get("current_release_domain_scope"),
        "multi_domain_release_ready": multi_domain_ready,
        "issues": len(issues),
        "warnings": len(warnings),
        "issue_codes": sorted({issue["code"] for issue in issues}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
    }
    report = {
        "passed": not issues,
        "root": str(root),
        "require_multi_domain": require_multi_domain,
        "summary": summary,
        "requirements": DOMAIN_REQUIREMENTS,
        "workflow_manifest_preflight_reports": preflight_inputs,
        "inputs": input_checks,
        "domains": domains,
        "recommended_next_actions": _recommended_next_actions(domains, multi_domain_ready),
        "issues": issues,
        "warnings": warnings,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def verify_domain_expansion_readiness_report(
    report_path: Path,
    output_path: Path | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Verify that a domain-expansion readiness report still matches its input reports."""

    report_path = Path(report_path)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    input_results: dict[str, dict[str, Any]] = {}

    if not report_path.exists():
        report = {
            "passed": False,
            "report_path": str(report_path),
            "summary": {
                "inputs_total": 0,
                "inputs_verified": 0,
                "issues": 1,
                "warnings": 0,
                "issue_codes": ["domain_expansion_report_missing"],
                "warning_codes": [],
            },
            "inputs": {},
            "issues": [{"code": "domain_expansion_report_missing", "message": "domain-expansion readiness report is missing", "path": str(report_path)}],
            "warnings": [],
        }
        if output_path is not None:
            write_json(output_path, report)
        return report

    source = read_json(report_path)
    source_root = Path(root or source.get("root") or report_path.resolve().parent)
    source_summary = source.get("summary", {}) if isinstance(source.get("summary"), dict) else {}
    if source.get("passed") is not True or int(source_summary.get("issues", 0)) > 0:
        _issue(issues, "domain_expansion_not_passed", "domain-expansion readiness report did not pass", report_path)

    inputs = source.get("inputs", {})
    if not isinstance(inputs, dict) or not inputs:
        _issue(issues, "domain_expansion_inputs_missing", "domain-expansion readiness report has no input records", report_path)
        inputs = {}

    for name, expected in sorted(inputs.items()):
        if not isinstance(expected, dict):
            _issue(issues, "domain_expansion_input_invalid", f"domain-expansion input record is not an object: {name}", report_path)
            continue
        path = _resolve_path(Path(str(expected.get("path", ""))), source_root)
        expected_status = expected.get("status")
        result = {
            "path": str(path),
            "expected_status": expected_status,
            "expected_sha256": expected.get("sha256"),
            "expected_bytes": expected.get("bytes"),
            "actual_sha256": None,
            "actual_bytes": None,
            "verification_summary": {},
            "passed": True,
        }
        input_results[name] = result
        if expected_status != "pass":
            result["passed"] = False
            code = "domain_expansion_required_input_missing" if name == "taxonomy_coverage_audit" else "domain_expansion_optional_input_missing"
            if name == "taxonomy_coverage_audit":
                _issue(issues, code, f"domain-expansion input was not present when generated: {name}", expected.get("path") or report_path)
            else:
                _warn(warnings, code, f"optional domain-expansion input was not present when generated: {name}", expected.get("path") or report_path)
            continue
        if not path.exists():
            result["passed"] = False
            _issue(issues, "domain_expansion_input_missing", f"domain-expansion input report is missing: {name}", path)
            continue
        if not expected.get("sha256"):
            result["passed"] = False
            _issue(issues, "domain_expansion_input_digest_missing", f"domain-expansion input lacks a source digest: {name}", path)
            continue
        actual_sha256 = _file_sha256(path)
        actual_bytes = path.stat().st_size
        result["actual_sha256"] = actual_sha256
        result["actual_bytes"] = actual_bytes
        if expected.get("sha256") != actual_sha256:
            result["passed"] = False
            _issue(issues, "domain_expansion_input_sha256_mismatch", f"domain-expansion input report changed: {name}", path)
        if expected.get("bytes") is not None and expected.get("bytes") != actual_bytes:
            result["passed"] = False
            _issue(issues, "domain_expansion_input_bytes_mismatch", f"domain-expansion input report size changed: {name}", path)
        _verify_workflow_manifest_input(name, path, source_root, result, issues)

    summary = {
        "inputs_total": len(input_results),
        "inputs_verified": sum(1 for result in input_results.values() if result["passed"]),
        "source_issues": int(source_summary.get("issues", 0)),
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
        "inputs": input_results,
        "issues": issues,
        "warnings": warnings,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def _verify_workflow_manifest_input(
    name: str,
    path: Path,
    source_root: Path,
    result: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    if _is_workflow_manifest_preflight_batch_input(name):
        verification = verify_workflow_manifest_preflight_batch_report(path, root=source_root)
        result["verification_summary"] = verification.get("summary", {})
        if verification.get("passed") is not True:
            result["passed"] = False
            _issue(
                issues,
                "domain_expansion_preflight_batch_verification_not_passed",
                f"domain-expansion preflight batch input artifacts changed: {name}",
                path,
            )
        return
    if _is_workflow_manifest_preflight_input(name):
        verification = verify_workflow_manifest_preflight_report(path, root=source_root)
        result["verification_summary"] = verification.get("summary", {})
        if verification.get("passed") is not True:
            result["passed"] = False
            _issue(
                issues,
                "domain_expansion_preflight_verification_not_passed",
                f"domain-expansion preflight input artifacts changed: {name}",
                path,
            )


def _is_workflow_manifest_preflight_input(name: str) -> bool:
    return name.startswith("workflow_manifest_preflight_") and not name.startswith("workflow_manifest_preflight_batch_")


def _is_workflow_manifest_preflight_batch_input(name: str) -> bool:
    return name.startswith("workflow_manifest_preflight_batch_")


def _domain_rows(
    taxonomy: dict[str, Any],
    readiness: dict[str, Any],
    source_audit: dict[str, Any],
    discovery: dict[str, Any],
    claim_boundary: dict[str, Any],
    workflow_manifest_preflights: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    domain_coverage = taxonomy.get("checks", {}).get("workflow_domain_coverage", {})
    readiness_checks = readiness.get("checks", {}) if isinstance(readiness.get("checks"), dict) else {}
    release_gates = {
        "project_benchmark_release": _readiness_check_passed(readiness_checks, "project_benchmark_release"),
        "project_submission_inputs": _readiness_check_passed(readiness_checks, "project_submission_inputs"),
        "project_release_baselines": _readiness_check_passed(readiness_checks, "project_release_baselines"),
        "baseline_batch": _readiness_check_passed(readiness_checks, "baseline_batch"),
        "taxonomy_coverage_audit": _readiness_check_passed(readiness_checks, "taxonomy_coverage_audit", allow_warn=True),
        "claim_boundary_audit": _readiness_check_passed(readiness_checks, "claim_boundary_audit", allow_warn=True),
        "artifact_bundle_manifest": _readiness_check_passed(readiness_checks, "artifact_bundle_manifest", allow_warn=True),
    }
    readiness_passed = readiness.get("passed") is True and int(readiness.get("summary", {}).get("failed", 0)) == 0
    source_summary = source_audit.get("summary", {}) if isinstance(source_audit.get("summary"), dict) else {}
    discovery_summary = discovery.get("summary", {}) if isinstance(discovery.get("summary"), dict) else {}
    claim_summary = claim_boundary.get("summary", {}) if isinstance(claim_boundary.get("summary"), dict) else {}
    preflights = workflow_manifest_preflights or {}

    rows: dict[str, dict[str, Any]] = {}
    for domain, definition in DOMAIN_DEFINITIONS.items():
        coverage = domain_coverage.get(domain, {})
        taxonomy_status = coverage.get("status") or definition["status_when_absent"]
        covered = taxonomy_status == "covered"
        source_counts = _source_counts_for_domain(domain, source_summary, discovery_summary)
        preflight = preflights.get(domain)
        if preflight and preflight.get("passed"):
            source_counts = dict(source_counts)
            source_counts["workflow_manifest_preflight"] = 1
        gates = _domain_gates(
            domain,
            taxonomy_status=taxonomy_status,
            source_counts=source_counts,
            release_gates=release_gates,
            readiness_passed=readiness_passed,
        )
        if preflight:
            gates = _gates_with_preflight(gates, preflight)
        ready = _all_required_pass(gates)
        status = _domain_status(domain, ready, taxonomy_status, source_counts)
        roadmap = _domain_roadmap(domain, status, gates)
        if preflight:
            roadmap = _roadmap_with_preflight(domain, roadmap, preflight)
        rows[domain] = {
            "label": definition["label"],
            "status": status,
            "ready_for_current_release": ready,
            "taxonomy_status": taxonomy_status,
            "adapter_status": ADAPTER_STATUS.get(domain, "missing_domain_adapter"),
            "source_counts": source_counts,
            "gates": gates,
            "blockers": _blockers(gates),
            "roadmap": roadmap,
            "evidence": {
                "taxonomy_domain_coverage": coverage,
                "readiness_passed": readiness_passed,
                "claim_boundary_supported_claims": claim_summary.get("supported_claims", []),
                "claim_boundary_blocked_claims": claim_summary.get("blocked_claims", []),
                "workflow_manifest_preflight": preflight or {},
            },
        }
        if covered and not ready:
            rows[domain]["status"] = "covered_but_release_gate_incomplete"
    return rows


def _domain_gates(
    domain: str,
    *,
    taxonomy_status: str,
    source_counts: dict[str, int],
    release_gates: dict[str, bool],
    readiness_passed: bool,
) -> dict[str, dict[str, Any]]:
    source_ready = _source_ready(domain, source_counts)
    covered = taxonomy_status == "covered"
    return {
        "reusable_trace_source": _gate(source_ready, _source_message(domain, source_ready)),
        "license_privacy_pii_gate": _license_gate(domain, source_counts),
        "canonical_event_adapter": _adapter_gate(domain),
        "verifier_checked_project_release": _gate(
            covered and release_gates["project_benchmark_release"],
            "verifier-checked project release exists for this domain" if covered else "domain has no verifier-checked project release",
        ),
        "no_gold_submission_input": _gate(
            covered and release_gates["project_submission_inputs"],
            "no-gold submission input is verified for this domain" if covered else "domain has no no-gold submission input",
        ),
        "baseline_and_external_runner_contract": _gate(
            covered and release_gates["project_release_baselines"] and release_gates["baseline_batch"],
            "release baselines and runner contracts are available for this domain" if covered else "domain baselines and runner checks are not released",
        ),
        "taxonomy_and_claim_boundary": _gate(
            covered and release_gates["taxonomy_coverage_audit"] and release_gates["claim_boundary_audit"],
            "taxonomy and claim-boundary gates cover this domain" if covered else "taxonomy/claim-boundary gates do not support release claims for this domain",
        ),
        "readiness_and_artifact_gate": _gate(
            covered and readiness_passed and release_gates["artifact_bundle_manifest"],
            "readiness and artifact bundle gates pass for this domain" if covered else "domain is absent from readiness/artifact release gates",
        ),
    }


def _source_counts_for_domain(domain: str, source_summary: dict[str, Any], discovery_summary: dict[str, Any]) -> dict[str, int]:
    if domain == "github_developer_workflow":
        return {
            "workflow_source_audit": int(source_summary.get("gharchive_sources", 0) or 0),
            "public_data_discovery": int(discovery_summary.get("gharchive_event_sources", 0) or 0),
        }
    if domain == "email_workflow":
        return {
            "workflow_source_audit": int(source_summary.get("email_manifest_sources", 0) or 0),
            "public_data_discovery": int(discovery_summary.get("email_manifest_sources", 0) or 0),
        }
    manifest_keys = {
        "calendar_workflow": "calendar_manifest_sources",
        "docs_workflow": "docs_manifest_sources",
        "chat_workflow": "chat_manifest_sources",
        "browser_web_workflow": "browser_web_manifest_sources",
    }
    if domain in manifest_keys:
        key = manifest_keys[domain]
        return {
            "workflow_source_audit": int(source_summary.get(key, 0) or 0),
            "public_data_discovery": int(discovery_summary.get(key, 0) or 0),
        }
    return {"workflow_source_audit": 0, "public_data_discovery": 0}


def _source_ready(domain: str, source_counts: dict[str, int]) -> bool:
    if domain == "github_developer_workflow":
        return sum(source_counts.values()) > 0
    if domain == "email_workflow":
        return sum(source_counts.values()) > 0
    if domain in {"calendar_workflow", "docs_workflow", "chat_workflow", "browser_web_workflow"}:
        return sum(source_counts.values()) > 0
    return False


def _source_message(domain: str, source_ready: bool) -> str:
    if source_ready:
        return "reusable source evidence is present"
    if domain == "email_workflow":
        return "no reviewed email workflow manifest is present"
    if domain in {"calendar_workflow", "docs_workflow", "chat_workflow", "browser_web_workflow"}:
        return "no reviewed workflow trace manifest is present for this planned domain"
    return "no reusable trace source has been approved for this planned domain"


def _license_gate(domain: str, source_counts: dict[str, int]) -> dict[str, Any]:
    if domain == "github_developer_workflow":
        return _gate(True, "GHArchive public event stream is usable with raw-payload minimization and repo-license caveats")
    if domain == "email_workflow":
        passed = sum(source_counts.values()) > 0
        return _gate(passed, "email license/privacy/PII manifest passed" if passed else "email license/privacy/PII manifest is missing")
    if domain in {"calendar_workflow", "docs_workflow", "chat_workflow", "browser_web_workflow"}:
        passed = sum(source_counts.values()) > 0
        return _gate(passed, "workflow license/privacy/PII manifest passed" if passed else "license/privacy/PII manifest is not available for this planned domain")
    return _gate(False, "license/privacy/PII manifest is not available for this planned domain")


def _adapter_gate(domain: str) -> dict[str, Any]:
    adapter_status = ADAPTER_STATUS.get(domain, "missing_domain_adapter")
    if adapter_status == "implemented":
        return _gate(True, "canonical source adapter is implemented")
    if adapter_status == "implemented_manifest_first":
        return _gate(True, "manifest-first canonical source adapter is implemented, but source manifest must pass before release")
    return _gate(False, "domain-specific canonical source adapter is not implemented")


def _domain_status(domain: str, ready: bool, taxonomy_status: str, source_counts: dict[str, int]) -> str:
    if ready:
        return "current_release_ready"
    if domain == "email_workflow" and sum(source_counts.values()) <= 0:
        return "blocked_license_privacy_manifest"
    if domain == "email_workflow" and sum(source_counts.values()) > 0 and taxonomy_status != "covered":
        return "source_manifest_ready_release_pipeline_missing"
    if domain in {"calendar_workflow", "docs_workflow", "chat_workflow", "browser_web_workflow"} and sum(source_counts.values()) > 0 and taxonomy_status != "covered":
        return "source_manifest_ready_release_pipeline_missing"
    if taxonomy_status == "covered":
        return "covered_but_release_gate_incomplete"
    return "planned_not_released"


def _load_workflow_manifest_preflights(
    report_paths: list[Path | str],
    root: Path,
    input_checks: dict[str, dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    preflights: dict[str, dict[str, Any]] = {}
    for index, raw_path in enumerate(report_paths):
        name = f"workflow_manifest_preflight_{index}"
        path = _resolve_path(Path(raw_path), root)
        if not path.exists():
            input_checks[name] = {"status": "warn", "path": str(path), "issues": ["report missing"]}
            _warn(warnings, "workflow_manifest_preflight_missing", "workflow manifest preflight report is missing", path)
            continue
        report = read_json(path)
        verification = verify_workflow_manifest_preflight_report(path, root=root)
        domain = str(report.get("domain") or "")
        passed = (
            report.get("passed") is True
            and int(report.get("summary", {}).get("issues", 0) or 0) == 0
            and verification.get("passed") is True
        )
        input_checks[name] = {
            "status": "pass" if passed else "warn",
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
            "summary": report.get("summary", {}),
            "verification_summary": verification.get("summary", {}),
            "domain": domain,
        }
        if not domain:
            _warn(warnings, "workflow_manifest_preflight_domain_missing", "workflow manifest preflight report has no domain", path)
            continue
        current = preflights.get(domain)
        record = {
            "path": str(path),
            "passed": passed,
            "bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
            "project_id": report.get("project_id"),
            "release_dir": report.get("release_dir"),
            "submission_input_dir": report.get("submission_input_dir"),
            "summary": report.get("summary", {}),
            "constraints": report.get("constraints", {}),
            "verification": verification.get("summary", {}),
        }
        if current is None or (record["passed"] and not current.get("passed")):
            preflights[domain] = record
        if not passed:
            _warn(
                warnings,
                "workflow_manifest_preflight_not_passed",
                "workflow manifest preflight report did not pass or its artifacts changed",
                path,
                domain=domain,
                verification_summary=verification.get("summary", {}),
            )
    return preflights


def _expand_workflow_manifest_preflight_batches(
    report_paths: list[Path | str],
    root: Path,
    input_checks: dict[str, dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> list[Path]:
    expanded: list[Path] = []
    for index, raw_path in enumerate(report_paths):
        name = f"workflow_manifest_preflight_batch_{index}"
        path = _resolve_path(Path(raw_path), root)
        if not path.exists():
            input_checks[name] = {"status": "warn", "path": str(path), "issues": ["report missing"]}
            _warn(warnings, "workflow_manifest_preflight_batch_missing", "workflow manifest preflight batch report is missing", path)
            continue
        report = read_json(path)
        verification = verify_workflow_manifest_preflight_batch_report(path, root=root)
        passed = report.get("passed") is True and int(report.get("summary", {}).get("issues", 0) or 0) == 0 and verification.get("passed") is True
        input_checks[name] = {
            "status": "pass" if passed else "warn",
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
            "summary": report.get("summary", {}),
            "verification_summary": verification.get("summary", {}),
        }
        if not passed:
            _warn(
                warnings,
                "workflow_manifest_preflight_batch_not_passed",
                "workflow manifest preflight batch report did not pass or referenced artifacts changed",
                path,
                verification_summary=verification.get("summary", {}),
            )
            continue
        for item in report.get("preflight_reports", []):
            if isinstance(item, dict) and item.get("report_path"):
                expanded.append(_resolve_path(Path(str(item["report_path"])), root))
    return expanded


def _roadmap_with_preflight(domain: str, roadmap: dict[str, Any], preflight: dict[str, Any]) -> dict[str, Any]:
    updated = dict(roadmap)
    updated["workflow_manifest_preflight"] = preflight
    updated["preflight_passed"] = bool(preflight.get("passed"))
    if preflight.get("passed"):
        updated["stage"] = (
            "workflow_manifest_preflight_passed_gate_integration_missing"
            if roadmap.get("stage") != "release_ready"
            else roadmap["stage"]
        )
        updated["offline_engineering_required"] = True
        blockers = list(updated.get("offline_engineering_blockers", []))
        blockers.append(
            {
                "gate": "readiness_and_artifact_gate",
                "kind": "benchmark_release_gate_integration",
                "message": f"{domain} manifest preflight passed, but benchmark release source audit, claim-boundary, readiness, and artifact gates are not integrated",
            }
        )
        updated["offline_engineering_blockers"] = _dedupe_blockers(blockers)
        stop_conditions = list(updated.get("stop_conditions", []))
        stop_conditions.append("Do not claim this preflighted workflow domain in the current benchmark release until release gates include it.")
        updated["stop_conditions"] = _dedupe(stop_conditions)
    return updated


def _gates_with_preflight(gates: dict[str, dict[str, Any]], preflight: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not preflight.get("passed"):
        return gates
    updated = {name: dict(gate) for name, gate in gates.items()}
    updates = {
        "reusable_trace_source": "verified workflow manifest preflight supplies reusable trace evidence",
        "license_privacy_pii_gate": "verified workflow manifest preflight includes a license/privacy/PII manifest",
        "verifier_checked_project_release": "workflow manifest preflight exported and verified a project release",
        "no_gold_submission_input": "workflow manifest preflight exported and verified no-gold submission input",
        "baseline_and_external_runner_contract": "workflow manifest preflight ran deterministic baselines",
        "taxonomy_and_claim_boundary": "workflow manifest preflight ran domain coverage for this workflow domain",
    }
    for gate_name, message in updates.items():
        updated[gate_name] = _gate(True, message)
    return updated


def _readiness_check_passed(checks: dict[str, Any], name: str, *, allow_warn: bool = False) -> bool:
    status = checks.get(name, {}).get("status")
    return status == "pass" or (allow_warn and status == "warn")


def _all_required_pass(gates: dict[str, dict[str, Any]]) -> bool:
    return all(gate.get("status") == "pass" for gate in gates.values())


def _blockers(gates: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "gate": name,
            "artifact": GATE_ARTIFACTS.get(name, name),
            "message": str(gate.get("message", "gate did not pass")),
        }
        for name, gate in gates.items()
        if gate.get("status") != "pass"
    ]


def _gate(passed: bool, message: str) -> dict[str, Any]:
    return {"status": "pass" if passed else "missing", "message": message}


def _domain_roadmap(domain: str, status: str, gates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing = _blockers(gates)
    external_blockers = _external_blockers(domain, gates)
    offline_engineering = _offline_engineering_blockers(domain, gates)
    release_gate_blockers = [item for item in missing if item["gate"] in DOWNSTREAM_RELEASE_GATES]
    stop_conditions = _stop_conditions(domain, external_blockers)
    stage = _roadmap_stage(status, external_blockers, offline_engineering, release_gate_blockers)
    return {
        "stage": stage,
        "required_artifacts": [
            {"gate": name, "artifact": artifact}
            for name, artifact in GATE_ARTIFACTS.items()
            if gates.get(name, {}).get("status") != "pass"
        ],
        "external_input_required_for_release": bool(external_blockers),
        "offline_engineering_required": bool(offline_engineering or release_gate_blockers),
        "external_blockers": external_blockers,
        "offline_engineering_blockers": offline_engineering,
        "release_gate_blockers": release_gate_blockers,
        "stop_conditions": stop_conditions,
    }


def _external_blockers(domain: str, gates: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    if gates["reusable_trace_source"]["status"] != "pass":
        if domain == "email_workflow":
            blockers.append(
                {
                    "gate": "reusable_trace_source",
                    "kind": "license_privacy_data",
                    "message": "approved Enron/Avocado-style or other email workflow manifest with reviewed records is missing",
                }
            )
        else:
            blockers.append(
                {
                    "gate": "reusable_trace_source",
                    "kind": "data_staging",
                    "message": "reusable longitudinal traces for this workflow domain are missing",
                }
            )
    if gates["license_privacy_pii_gate"]["status"] != "pass":
        blockers.append(
            {
                "gate": "license_privacy_pii_gate",
                "kind": "license_privacy",
                "message": gates["license_privacy_pii_gate"]["message"],
            }
        )
    return _dedupe_blockers(blockers)


def _offline_engineering_blockers(domain: str, gates: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    if gates["canonical_event_adapter"]["status"] != "pass":
        blockers.append(
            {
                "gate": "canonical_event_adapter",
                "kind": "adapter_engineering",
                "message": f"implement and test the canonical adapter for {domain}",
            }
        )
    for name in [
        "verifier_checked_project_release",
        "no_gold_submission_input",
        "baseline_and_external_runner_contract",
        "taxonomy_and_claim_boundary",
        "readiness_and_artifact_gate",
    ]:
        if gates[name]["status"] != "pass":
            blockers.append(
                {
                    "gate": name,
                    "kind": "release_pipeline_engineering",
                    "message": gates[name]["message"],
                }
            )
    return blockers


def _stop_conditions(domain: str, external_blockers: list[dict[str, str]]) -> list[str]:
    conditions = []
    if domain == "email_workflow" and external_blockers:
        conditions.append("Do not load raw email records until the manifest passes license/privacy/PII review.")
        conditions.append("Do not claim reviewed real email workflow coverage until the release pipeline also passes.")
    elif external_blockers:
        conditions.append("Do not claim this workflow domain as release-ready until reusable traces and license/privacy gates pass.")
    if domain != "github_developer_workflow":
        conditions.append("Do not spend LLM/API or human annotation budget for this domain until its source and stage-plan gates pass.")
    return conditions


def _roadmap_stage(
    status: str,
    external_blockers: list[dict[str, str]],
    offline_engineering: list[dict[str, str]],
    release_gate_blockers: list[dict[str, str]],
) -> str:
    if status == "current_release_ready":
        return "release_ready"
    if status == "blocked_license_privacy_manifest":
        return "blocked_on_license_privacy_manifest"
    if external_blockers and offline_engineering:
        return "blocked_on_data_with_offline_scaffolding_remaining"
    if external_blockers:
        return "blocked_on_external_input"
    if offline_engineering or release_gate_blockers:
        return "release_pipeline_engineering_missing"
    return "not_release_ready"


def _dedupe_blockers(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    output = []
    for item in items:
        key = (item.get("gate"), item.get("kind"), item.get("message"))
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _recommended_next_actions(domains: dict[str, dict[str, Any]], multi_domain_ready: bool) -> list[str]:
    actions = []
    if not multi_domain_ready:
        actions.append("Keep current paper/release language scoped to GHArchive/GitHub developer workflows.")
    email = domains.get("email_workflow", {})
    if email.get("status") == "blocked_license_privacy_manifest":
        actions.append("Prepare a reviewed EmailWorkflowAdapter manifest before loading Enron/Avocado-style email traces.")
    for domain in ["calendar_workflow", "docs_workflow", "chat_workflow", "browser_web_workflow"]:
        if domains.get(domain, {}).get("status") == "planned_not_released":
            actions.append(
                f"For {domain}, stage a reviewed manifest with records, memory_graph, and probes; then run "
                "preflight-workflow-manifest-release and verify-workflow-manifest-preflight before integrating it into benchmark release gates."
            )
    actions.append("After adding any new domain, rerun taxonomy coverage, claim-boundary audit, readiness, artifact verification, and benchmark release gate.")
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


def _warn(warnings: list[dict[str, Any]], code: str, message: str, path: Path | str | None = None, **extra: Any) -> None:
    item: dict[str, Any] = {"code": code, "message": message} | extra
    if path is not None:
        item["path"] = str(path)
    warnings.append(item)
