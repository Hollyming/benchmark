from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ultra_long_benchmark.shared.io import read_json, write_json


CLAIMS = {
    "core_task_taxonomy": {
        "label": "Core benchmark task taxonomy is Longitudinal User Policy / Habit Induction for Tool-Using Agents.",
        "kind": "core_claim",
        "unlock_requirements": [],
    },
    "github_developer_workflow_release": {
        "label": "Current benchmark release is a GitHub developer workflow domain release.",
        "kind": "domain_claim",
        "unlock_requirements": [],
    },
    "source_grounded_gharchive": {
        "label": "Current release is grounded in reused GH Archive public workflow events.",
        "kind": "source_claim",
        "unlock_requirements": ["Stage a reusable GHArchive workflow-event slice and pass workflow source audit."],
    },
    "no_gold_hardened_submission_input": {
        "label": "External systems are evaluated through hardened no-gold submission inputs.",
        "kind": "evaluation_claim",
        "unlock_requirements": ["Export no-gold submission inputs and pass hardened probe leakage audit with no gold-key leakage."],
    },
    "memory_submission_contract_ready": {
        "label": "No-gold memory-system submission contract and scoring harness are ready.",
        "kind": "baseline_claim",
        "unlock_requirements": ["Run no-gold memory submission contract baselines and validate ProjectPrediction coverage."],
    },
    "external_memory_runner_contract_ready": {
        "label": "External memory runner plugin contract is executable but method-specific baselines are not yet executed.",
        "kind": "baseline_claim",
        "unlock_requirements": [
            "Implement method-specific runner plugins.",
            "Install dependencies and configure credentials.",
            "Run plugins through hardened no-gold inputs with explicit allow flags.",
        ],
    },
    "multi_domain_office_release": {
        "label": "Current release covers email/calendar/docs/chat/browser/web-search office workflows.",
        "kind": "blocked_claim",
        "unlock_requirements": [
            "Add at least one non-GitHub real workflow domain with reusable traces.",
            "Pass license/privacy/PII gates for each added domain.",
            "Build verifier-checked projects, no-gold inputs, baselines, taxonomy coverage, and readiness for the combined release.",
        ],
    },
    "reviewed_real_email_workflow_release": {
        "label": "Current release includes reviewed real email workflow data.",
        "kind": "blocked_claim",
        "unlock_requirements": [
            "Provide an Enron/Avocado-style or equivalent email workflow manifest.",
            "Document redistribution license, privacy review, and PII redaction policy.",
            "Ingest email threads into canonical artifacts/events and pass verifier/release gates.",
        ],
    },
    "human_audited_rewrite_quality": {
        "label": "LLM rewrite quality has passed human audit.",
        "kind": "blocked_claim",
        "unlock_requirements": [
            "Fill audit_decisions.jsonl for the exported human audit sample.",
            "Run validate-policy-rewrite-human-audit and pass accept-rate/blocking-issue gates.",
        ],
    },
    "executed_sota_memory_baselines": {
        "label": "Mem0/A-MEM/Graphiti or other SOTA memory baselines have been executed on the release.",
        "kind": "blocked_claim",
        "unlock_requirements": [
            "Install method-specific Mem0/A-MEM/Graphiti dependencies.",
            "Configure required API/model/database credentials.",
            "Run external memory plugins on Slurm where needed and score their ProjectPrediction outputs.",
        ],
    },
    "original_query_scores_as_sota": {
        "label": "High original-query memory-profile score is a SOTA capability result.",
        "kind": "blocked_claim",
        "unlock_requirements": [
            "Use hardened no-gold inputs for external-system claims.",
            "Report original-vs-hardened sensitivity rather than treating original lexical-shortcut score as SOTA evidence.",
        ],
    },
}


def audit_paper_claim_boundaries(
    output_path: Path | None = None,
    *,
    readiness_report_path: Path | None = None,
    taxonomy_coverage_path: Path | None = None,
    workflow_source_audit_path: Path | None = None,
    hardened_probe_leakage_audit_path: Path | None = None,
    human_audit_report_path: Path | None = None,
    baseline_batch_report_path: Path | None = None,
    external_runner_report_path: Path | None = None,
) -> dict[str, Any]:
    """Classify paper-facing claims as supported, qualified, or blocked."""

    input_paths = {
        "readiness_report_path": readiness_report_path,
        "taxonomy_coverage_path": taxonomy_coverage_path,
        "workflow_source_audit_path": workflow_source_audit_path,
        "hardened_probe_leakage_audit_path": hardened_probe_leakage_audit_path,
        "human_audit_report_path": human_audit_report_path,
        "baseline_batch_report_path": baseline_batch_report_path,
        "external_runner_report_path": external_runner_report_path,
    }
    readiness = _read_optional(readiness_report_path)
    taxonomy = _read_optional(taxonomy_coverage_path)
    source_audit = _read_optional(workflow_source_audit_path)
    leakage = _read_optional(hardened_probe_leakage_audit_path)
    human_audit = _read_optional(human_audit_report_path)
    baseline_batch = _read_optional(baseline_batch_report_path)
    external_runner = _read_optional(external_runner_report_path)

    claim_reports = {
        "core_task_taxonomy": _core_task_taxonomy_claim(taxonomy),
        "github_developer_workflow_release": _github_release_claim(taxonomy, readiness),
        "source_grounded_gharchive": _source_grounded_gharchive_claim(source_audit),
        "no_gold_hardened_submission_input": _hardened_submission_claim(leakage, readiness),
        "memory_submission_contract_ready": _memory_submission_contract_claim(baseline_batch),
        "external_memory_runner_contract_ready": _external_runner_contract_claim(baseline_batch, external_runner),
        "multi_domain_office_release": _multi_domain_office_claim(taxonomy),
        "reviewed_real_email_workflow_release": _email_release_claim(taxonomy, source_audit),
        "human_audited_rewrite_quality": _human_audit_claim(human_audit, readiness),
        "executed_sota_memory_baselines": _executed_sota_claim(baseline_batch),
        "original_query_scores_as_sota": _original_query_sota_claim(leakage),
    }
    supported = [name for name, claim in claim_reports.items() if claim["status"] == "supported"]
    qualified = [name for name, claim in claim_reports.items() if claim["status"] == "qualified"]
    blocked = [name for name, claim in claim_reports.items() if claim["status"] == "blocked"]
    report = {
        "inputs": _input_records(input_paths),
        "claims": claim_reports,
        "summary": {
            "claims_total": len(claim_reports),
            "supported": len(supported),
            "qualified": len(qualified),
            "blocked": len(blocked),
            "supported_claims": supported,
            "qualified_claims": qualified,
            "blocked_claims": blocked,
        },
        "passed": True,
        "recommended_language": _recommended_language(claim_reports),
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def verify_paper_claim_boundary_audit(
    report_path: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Recompute a claim-boundary audit from its recorded inputs and compare it."""

    report_path = Path(report_path)
    if not report_path.exists():
        report = {
            "passed": False,
            "report_path": str(report_path),
            "summary": {"issues": 1, "warnings": 0, "issue_codes": ["claim_boundary_report_missing"], "warning_codes": []},
            "issues": [
                {
                    "code": "claim_boundary_report_missing",
                    "message": "claim-boundary audit report is missing",
                    "path": str(report_path),
                }
            ],
            "warnings": [],
        }
        if output_path is not None:
            write_json(output_path, report)
        return report

    original = read_json(report_path)
    inputs = original.get("inputs", {})
    if not isinstance(inputs, dict):
        inputs = {}
    recomputed = audit_paper_claim_boundaries(
        readiness_report_path=_optional_path(inputs.get("readiness_report_path")),
        taxonomy_coverage_path=_optional_path(inputs.get("taxonomy_coverage_path")),
        workflow_source_audit_path=_optional_path(inputs.get("workflow_source_audit_path")),
        hardened_probe_leakage_audit_path=_optional_path(inputs.get("hardened_probe_leakage_audit_path")),
        human_audit_report_path=_optional_path(inputs.get("human_audit_report_path")),
        baseline_batch_report_path=_optional_path(inputs.get("baseline_batch_report_path")),
        external_runner_report_path=_optional_path(inputs.get("external_runner_report_path")),
    )
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for key in ("summary", "claims", "recommended_language"):
        if original.get(key) != recomputed.get(key):
            _verification_issue(issues, f"claim_boundary_{key}_mismatch", f"claim-boundary {key} changed", report_path)
    if original.get("passed") != recomputed.get("passed"):
        _verification_issue(issues, "claim_boundary_passed_mismatch", "claim-boundary passed flag changed", report_path)

    recomputed_inputs = recomputed.get("inputs", {})
    for key, value in inputs.items():
        recomputed_value = recomputed_inputs.get(key)
        if isinstance(value, dict) and isinstance(recomputed_value, dict):
            for field in ("status", "path"):
                if recomputed_value.get(field) != value.get(field):
                    _verification_issue(issues, "claim_boundary_inputs_mismatch", f"claim-boundary input {field} changed: {key}", report_path)
            continue
        normalized_value = str(value) if value is not None else None
        if recomputed_value != normalized_value:
            _verification_issue(issues, "claim_boundary_inputs_mismatch", f"claim-boundary input changed: {key}", report_path)

    for key, record in inputs.items():
        if not isinstance(record, dict):
            continue
        path = _optional_path(record.get("path"))
        if record.get("status") == "missing":
            if path is not None and path.exists():
                _verification_issue(issues, "claim_boundary_input_appeared", f"claim-boundary input appeared after audit: {key}", report_path)
            continue
        if path is None:
            continue
        if not path.exists():
            _verification_issue(issues, "claim_boundary_input_missing", f"claim-boundary input report is missing: {key}", report_path)
            continue
        if not record.get("sha256"):
            _verification_issue(issues, "claim_boundary_input_digest_missing", f"claim-boundary input lacks a source digest: {key}", report_path)
            continue
        if record.get("sha256") != _file_sha256(path):
            _verification_issue(issues, "claim_boundary_input_sha256_mismatch", f"claim-boundary input report changed: {key}", report_path)
        if record.get("bytes") is not None and record.get("bytes") != path.stat().st_size:
            _verification_issue(issues, "claim_boundary_input_bytes_mismatch", f"claim-boundary input report size changed: {key}", report_path)

    summary = {
        "issues": len(issues),
        "warnings": len(warnings),
        "issue_codes": sorted({issue["code"] for issue in issues}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
        "original_supported": original.get("summary", {}).get("supported"),
        "recomputed_supported": recomputed.get("summary", {}).get("supported"),
        "original_blocked": original.get("summary", {}).get("blocked"),
        "recomputed_blocked": recomputed.get("summary", {}).get("blocked"),
    }
    report = {
        "passed": not issues,
        "report_path": str(report_path),
        "summary": summary,
        "issues": issues,
        "warnings": warnings,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def _core_task_taxonomy_claim(taxonomy: dict[str, Any] | None) -> dict[str, Any]:
    if not taxonomy:
        return _claim("core_task_taxonomy", "qualified", ["taxonomy coverage audit is missing"])
    core = taxonomy.get("checks", {}).get("core_task_taxonomy", {})
    if core.get("short_name") == "longitudinal_user_policy_habit_induction":
        return _claim("core_task_taxonomy", "supported", [f"taxonomy={core.get('name')}"])
    return _claim("core_task_taxonomy", "qualified", [f"unexpected taxonomy={core.get('short_name')}"])


def _github_release_claim(taxonomy: dict[str, Any] | None, readiness: dict[str, Any] | None) -> dict[str, Any]:
    if not taxonomy:
        return _claim("github_developer_workflow_release", "qualified", ["taxonomy coverage audit is missing"])
    scope = taxonomy.get("summary", {}).get("current_release_domain_scope")
    domains = taxonomy.get("summary", {}).get("covered_workflow_domains", [])
    evidence = [f"scope={scope}", f"domains={domains}"]
    if readiness:
        evidence.append(f"readiness_failed={readiness.get('summary', {}).get('failed')}")
    if scope == "github_developer_workflow_only" and "github_developer_workflow" in domains:
        return _claim("github_developer_workflow_release", "supported", evidence)
    return _claim("github_developer_workflow_release", "qualified", evidence)


def _source_grounded_gharchive_claim(source_audit: dict[str, Any] | None) -> dict[str, Any]:
    if not source_audit:
        return _claim("source_grounded_gharchive", "qualified", ["workflow source audit is missing"])
    summary = source_audit.get("summary", {})
    evidence = [
        f"gharchive_sources={summary.get('gharchive_sources')}",
        f"annotation_budget_ready={source_audit.get('annotation_budget_ready')}",
        f"paper_ready={source_audit.get('paper_ready')}",
    ]
    if int(summary.get("gharchive_sources", 0)) > 0 and source_audit.get("annotation_budget_ready") is True:
        return _claim("source_grounded_gharchive", "supported", evidence)
    if int(summary.get("gharchive_sources", 0)) > 0:
        return _claim("source_grounded_gharchive", "qualified", evidence)
    return _claim("source_grounded_gharchive", "blocked", evidence)


def _hardened_submission_claim(leakage: dict[str, Any] | None, readiness: dict[str, Any] | None) -> dict[str, Any]:
    if not leakage:
        return _claim("no_gold_hardened_submission_input", "qualified", ["hardened probe leakage audit is missing"])
    summary = leakage.get("summary", {})
    evidence = [
        f"high_any_overlap_probes={summary.get('high_any_overlap_probes')}",
        f"missing_gold_keys={summary.get('missing_gold_keys')}",
    ]
    readiness_check = (readiness or {}).get("checks", {}).get("project_submission_inputs", {})
    if readiness_check:
        evidence.append(f"submission_input_status={readiness_check.get('status')}")
    if int(summary.get("high_any_overlap_probes", 0)) == 0 and int(summary.get("missing_gold_keys", 0)) == 0:
        return _claim("no_gold_hardened_submission_input", "supported", evidence)
    return _claim("no_gold_hardened_submission_input", "qualified", evidence)


def _memory_submission_contract_claim(baseline_batch: dict[str, Any] | None) -> dict[str, Any]:
    if not baseline_batch:
        return _claim("memory_submission_contract_ready", "qualified", ["baseline batch report is missing"])
    statuses = _baseline_statuses(baseline_batch)
    evidence = [
        f"memory_stub={statuses.get('memory_submission_event_profile_stub')}",
        f"memory_stub_hardened={statuses.get('memory_submission_event_profile_stub_hardened')}",
    ]
    if statuses.get("memory_submission_event_profile_stub") == "completed" and statuses.get("memory_submission_event_profile_stub_hardened") == "completed":
        return _claim("memory_submission_contract_ready", "supported", evidence)
    return _claim("memory_submission_contract_ready", "qualified", evidence)


def _external_runner_contract_claim(
    baseline_batch: dict[str, Any] | None,
    external_runner: dict[str, Any] | None,
) -> dict[str, Any]:
    if not baseline_batch:
        return _claim("external_memory_runner_contract_ready", "qualified", ["baseline batch report is missing"])
    statuses = _baseline_statuses(baseline_batch)
    evidence = [
        f"echo_contract={statuses.get('external_memory_runner_echo_contract')}",
        f"mem0_submission={statuses.get('mem0_submission_placeholder')}",
        f"a_mem_submission={statuses.get('a_mem_submission_placeholder')}",
        f"graphiti_submission={statuses.get('graphiti_submission_placeholder')}",
    ]
    if external_runner:
        summary = external_runner.get("summary", {})
        evidence.extend(
            [
                f"runner_status={external_runner.get('status')}",
                f"runner_executed={external_runner.get('executed')}",
                f"runner_predictions={summary.get('predictions')}",
                f"runner_probes={summary.get('probes')}",
                f"output_validation_passed={summary.get('output_validation_passed')}",
            ]
        )
        if (
            external_runner.get("status") == "completed"
            and external_runner.get("executed") is True
            and summary.get("output_validation_passed") is True
            and int(summary.get("predictions", 0)) == int(summary.get("probes", -1))
        ):
            return _claim("external_memory_runner_contract_ready", "supported", evidence)
    if statuses.get("external_memory_runner_echo_contract") in {"dry_run_ok", "completed"}:
        return _claim("external_memory_runner_contract_ready", "qualified", evidence)
    return _claim("external_memory_runner_contract_ready", "blocked", evidence)


def _multi_domain_office_claim(taxonomy: dict[str, Any] | None) -> dict[str, Any]:
    if not taxonomy:
        return _claim("multi_domain_office_release", "blocked", ["taxonomy coverage audit is missing"])
    summary = taxonomy.get("summary", {})
    evidence = [
        f"scope={summary.get('current_release_domain_scope')}",
        f"domains={summary.get('covered_workflow_domains')}",
        f"multi_domain_ready={summary.get('multi_domain_release_ready')}",
    ]
    if summary.get("multi_domain_release_ready") is True:
        return _claim("multi_domain_office_release", "supported", evidence)
    return _claim("multi_domain_office_release", "blocked", evidence)


def _email_release_claim(taxonomy: dict[str, Any] | None, source_audit: dict[str, Any] | None) -> dict[str, Any]:
    domain = (taxonomy or {}).get("checks", {}).get("workflow_domain_coverage", {}).get("email_workflow", {})
    summary = (source_audit or {}).get("summary", {})
    evidence = [
        f"email_domain_status={domain.get('status')}",
        f"email_manifest_sources={summary.get('email_manifest_sources')}",
    ]
    if domain.get("status") == "covered" and int(summary.get("email_manifest_sources", 0)) > 0:
        return _claim("reviewed_real_email_workflow_release", "supported", evidence)
    return _claim("reviewed_real_email_workflow_release", "blocked", evidence)


def _human_audit_claim(human_audit: dict[str, Any] | None, readiness: dict[str, Any] | None) -> dict[str, Any]:
    evidence = []
    if human_audit:
        evidence.append(f"human_audit_passed={human_audit.get('passed')}")
        evidence.append(f"reviewed={human_audit.get('summary', {}).get('reviewed')}")
    readiness_check = (readiness or {}).get("checks", {}).get("rewrite_human_audit", {})
    if readiness_check:
        evidence.append(f"readiness_status={readiness_check.get('status')}")
    if human_audit and human_audit.get("passed") is True:
        return _claim("human_audited_rewrite_quality", "supported", evidence)
    return _claim("human_audited_rewrite_quality", "blocked", evidence or ["human audit validation report is missing"])


def _executed_sota_claim(baseline_batch: dict[str, Any] | None) -> dict[str, Any]:
    if not baseline_batch:
        return _claim("executed_sota_memory_baselines", "blocked", ["baseline batch report is missing"])
    statuses = _baseline_statuses(baseline_batch)
    external_statuses = {
        name: statuses.get(name)
        for name in ["mem0_submission_placeholder", "a_mem_submission_placeholder", "graphiti_submission_placeholder"]
    }
    if all(status == "completed" for status in external_statuses.values()):
        return _claim("executed_sota_memory_baselines", "supported", [str(external_statuses)])
    return _claim("executed_sota_memory_baselines", "blocked", [str(external_statuses)])


def _original_query_sota_claim(leakage: dict[str, Any] | None) -> dict[str, Any]:
    evidence = ["original public query wording has documented lexical shortcut risk"]
    if leakage:
        summary = leakage.get("summary", {})
        evidence.append(f"hardened_high_any_overlap_probes={summary.get('high_any_overlap_probes')}")
    return _claim("original_query_scores_as_sota", "blocked", evidence)


def _claim(name: str, status: str, evidence: list[str]) -> dict[str, Any]:
    return {
        "claim_id": name,
        "label": CLAIMS[name]["label"],
        "kind": CLAIMS[name]["kind"],
        "status": status,
        "evidence": evidence,
        "unlock_requirements": list(CLAIMS[name]["unlock_requirements"]),
    }


def _baseline_statuses(baseline_batch: dict[str, Any]) -> dict[str, str]:
    return {
        str(report.get("baseline_name")): str(report.get("status"))
        for report in baseline_batch.get("reports", [])
        if report.get("baseline_name")
    }


def _recommended_language(claims: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    supported = []
    qualified = []
    blocked = []
    if claims["core_task_taxonomy"]["status"] == "supported":
        supported.append("Use Longitudinal User Policy / Habit Induction for Tool-Using Agents as the core task taxonomy.")
    if claims["github_developer_workflow_release"]["status"] == "supported":
        supported.append("Describe the current benchmark release as a GitHub developer workflow domain release.")
    if claims["source_grounded_gharchive"]["status"] == "supported":
        supported.append("State that the current release reuses GH Archive public workflow events as authoritative source traces.")
    if claims["external_memory_runner_contract_ready"]["status"] == "supported":
        supported.append("Say that the external memory runner plugin contract executes end-to-end on hardened no-gold inputs.")
    if claims["external_memory_runner_contract_ready"]["status"] == "qualified":
        qualified.append("Say that external memory runner contracts are ready, while real Mem0/A-MEM/Graphiti executions still require dependencies, credentials, and explicit allow flags.")
    if claims["multi_domain_office_release"]["status"] == "blocked":
        blocked.append("Do not describe the current release as a multi-domain email/calendar/docs/chat/browser/web-search workflow benchmark.")
    if claims["reviewed_real_email_workflow_release"]["status"] == "blocked":
        blocked.append("Do not claim reviewed real email workflow coverage until a license/privacy/PII manifest gate passes.")
    if claims["human_audited_rewrite_quality"]["status"] == "blocked":
        blocked.append("Do not claim human-audited LLM rewrite quality until audit decisions are filled and validated.")
    if claims["executed_sota_memory_baselines"]["status"] == "blocked":
        blocked.append("Do not claim Mem0/A-MEM/Graphiti SOTA baseline results until method-specific runners execute and score.")
    if claims["original_query_scores_as_sota"]["status"] == "blocked":
        blocked.append("Do not present the original-query memory-profile score as a SOTA result; use it only as shortcut-sensitivity evidence.")
    return {"supported": supported, "qualified": qualified, "blocked": blocked}


def _read_optional(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    path = Path(path)
    if not path.exists():
        return None
    return read_json(path)


def _input_records(paths: dict[str, Path | None]) -> dict[str, dict[str, Any]]:
    records = {}
    for key, raw_path in paths.items():
        if raw_path is None:
            records[key] = {"status": "not_provided", "path": None}
            continue
        path = Path(raw_path)
        if not path.exists():
            records[key] = {"status": "missing", "path": str(path)}
            continue
        records[key] = {
            "status": "present",
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
        }
    return records


def _optional_path(value: Any) -> Path | None:
    if isinstance(value, dict):
        value = value.get("path")
    if value is None or value == "":
        return None
    return Path(str(value))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verification_issue(issues: list[dict[str, Any]], code: str, message: str, path: Path) -> None:
    issues.append({"code": code, "message": message, "path": str(path)})
