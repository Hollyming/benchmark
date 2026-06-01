from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from ultra_long_benchmark.models import MemoryGraph, Probe, ProjectProfile, model_to_dict, model_validate
from ultra_long_benchmark.pipelines.evaluation import run_project_release_baseline_evaluation
from ultra_long_benchmark.pipelines.source_adapters import EmailWorkflowAdapter, WorkflowManifestAdapter, validate_workflow_manifest_adapter
from ultra_long_benchmark.pipelines.verifier import run_project_verifier
from ultra_long_benchmark.probe_audit import audit_project_release_probe_leakage
from ultra_long_benchmark.probe_audit import audit_submission_input_probe_leakage
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.project_release import export_project_submission_inputs
from ultra_long_benchmark.project_release import verify_project_benchmark_release
from ultra_long_benchmark.project_release import verify_project_submission_inputs
from ultra_long_benchmark.shared.io import read_json, write_json, write_jsonl
from ultra_long_benchmark.shared.privacy import privacy_tags, redact
from ultra_long_benchmark.taxonomy_coverage import audit_project_release_taxonomy_coverage

T = TypeVar("T")
DEFAULT_PREFLIGHT_BASELINES = ("raw_rag", "oracle_policy_graph")


def build_project_from_workflow_manifest(
    manifest_path: Path,
    output_dir: Path,
    output_report_path: Path | None = None,
    *,
    adapter: str = "auto",
    redact_sensitive: bool = True,
) -> dict[str, Any]:
    """Build a verifier-checked project from a reviewed workflow manifest.

    This is deliberately not a task-generation pipeline. The manifest must
    already contain reviewed `memory_graph` and `probes` records; the function
    only normalizes source records through the manifest-first adapters, writes
    project files, and runs the standard verifier.
    """

    manifest_path = Path(manifest_path)
    output_dir = Path(output_dir)
    manifest = read_json(manifest_path)
    _validate_project_manifest_fields(manifest)
    selected_adapter = _select_adapter(manifest, adapter)
    validation_report = validate_workflow_manifest_adapter(
        manifest_path,
        adapter=selected_adapter,
        redact_sensitive=redact_sensitive,
    )
    if selected_adapter == "email":
        adapter_result = EmailWorkflowAdapter(manifest_path, redact_sensitive=redact_sensitive).load()
        domain = "email_workflow"
    else:
        adapter_result = WorkflowManifestAdapter(manifest_path, redact_sensitive=redact_sensitive).load()
        domain = str(adapter_result.project_profile.metadata.get("domain") or manifest.get("domain"))

    profile = _redacted_model(adapter_result.project_profile, ProjectProfile, redact_sensitive)
    artifacts = [_redact_value(model_to_dict(artifact), redact_sensitive) for artifact in adapter_result.artifacts]
    events = [_redact_value(model_to_dict(event), redact_sensitive) for event in adapter_result.events]
    graph = _redacted_model(model_validate(MemoryGraph, manifest["memory_graph"]), MemoryGraph, redact_sensitive)
    probes = [_redacted_model(model_validate(Probe, row), Probe, redact_sensitive) for row in manifest["probes"]]
    _validate_project_binding(profile.project_id, graph, probes)

    project_dir = output_dir / profile.project_id
    write_json(project_dir / "project_profile.json", profile)
    write_jsonl(project_dir / "artifacts.jsonl", artifacts)
    write_jsonl(project_dir / "events.jsonl", events)
    write_json(project_dir / "memory_graph.json", graph)
    write_jsonl(project_dir / "probes.jsonl", probes)
    source_manifest = _source_manifest(
        manifest_path=manifest_path,
        profile=profile,
        domain=domain,
        adapter=selected_adapter,
        artifact_count=len(artifacts),
        event_count=len(events),
        memory_count=len(graph.memories),
        probe_count=len(probes),
        redact_sensitive=redact_sensitive,
    )
    write_json(project_dir / "source_manifest.json", source_manifest)
    verifier_report = run_project_verifier(project_dir)
    leakage = _privacy_leakage(project_dir) if redact_sensitive else {}
    issues = []
    if leakage:
        issues.append(
            {
                "code": "workflow_manifest_project_privacy_leakage",
                "message": "redacted workflow project still contains email/phone/secret-like strings",
                "files": leakage,
            }
        )

    report = {
        "passed": verifier_report.passed and not issues,
        "project_id": profile.project_id,
        "project_dir": str(project_dir),
        "manifest_path": str(manifest_path),
        "adapter": selected_adapter,
        "domain": domain,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "records": validation_report["summary"]["records"],
            "artifacts": len(artifacts),
            "events": len(events),
            "memories": len(graph.memories),
            "probes": len(probes),
            "verifier_passed": verifier_report.passed,
            "issues": len(issues) + len(verifier_report.issues),
        },
        "manifest": validation_report["manifest"],
        "constraints": {
            "manifest_first": True,
            "requires_reviewed_manifest": True,
            "requires_manifest_memory_graph": True,
            "requires_manifest_probes": True,
            "llm_generation_performed": False,
            "network_access_required": False,
            "redacted": redact_sensitive,
            "release_ready_claim": False,
            "requires_release_export_and_domain_gates": True,
        },
        "verifier": model_to_dict(verifier_report),
        "privacy_leakage": leakage,
        "issues": issues,
    }
    if output_report_path is not None:
        write_json(output_report_path, report)
    return report


def preflight_workflow_manifest_release(
    manifest_path: Path,
    output_dir: Path,
    output_report_path: Path | None = None,
    *,
    adapter: str = "auto",
    redact_sensitive: bool = True,
    dataset_name: str | None = None,
    version: str = "0.1.0",
    baseline_names: list[str] | tuple[str, ...] | None = DEFAULT_PREFLIGHT_BASELINES,
    top_k: int = 5,
    harden_probe_queries: bool = False,
) -> dict[str, Any]:
    """Run the offline release preflight for one reviewed workflow manifest."""

    output_dir = Path(output_dir)
    build_report = build_project_from_workflow_manifest(
        manifest_path,
        output_dir / "projects",
        output_report_path=output_dir / "workflow_manifest_project_report.json",
        adapter=adapter,
        redact_sensitive=redact_sensitive,
    )
    project_dir = Path(build_report["project_dir"])
    domain = str(build_report["domain"])
    release_dir = output_dir / "release_packaging" / "workflow_manifest_project_benchmark"
    input_dir = output_dir / "evaluation_harness" / "workflow_manifest_submission_inputs"
    baseline_report_path = output_dir / "evaluation_harness" / "workflow_manifest_project_release_baselines.json"
    release_dataset_name = dataset_name or f"{domain}_manifest_preflight_project_benchmark"
    requested_baselines = list(baseline_names or DEFAULT_PREFLIGHT_BASELINES)

    release_manifest = export_project_benchmark_release(
        [project_dir],
        release_dir,
        dataset_name=release_dataset_name,
        version=version,
        construction="manifest_first_reviewed_workflow_project",
    )
    release_verification = verify_project_benchmark_release(
        release_dir,
        output_path=output_dir / "evaluation_harness" / "project_release_verification.json",
    )
    submission_manifest = export_project_submission_inputs(
        release_dir,
        input_dir,
        harden_probe_queries=harden_probe_queries,
    )
    submission_verification = verify_project_submission_inputs(
        input_dir,
        output_path=output_dir / "evaluation_harness" / "workflow_manifest_submission_inputs_verification.json",
    )
    baseline_report = run_project_release_baseline_evaluation(
        release_dir,
        baseline_report_path,
        top_k=top_k,
        baseline_names=requested_baselines,
    )
    taxonomy_report = audit_project_release_taxonomy_coverage(
        release_dir,
        output_path=output_dir / "evaluation_harness" / "project_release_taxonomy_coverage.json",
    )
    release_leakage = audit_project_release_probe_leakage(
        release_dir,
        output_path=output_dir / "evaluation_harness" / "project_release_probe_leakage.json",
    )
    submission_leakage = audit_submission_input_probe_leakage(
        release_dir,
        input_dir,
        output_path=output_dir / "evaluation_harness" / "project_submission_input_probe_leakage.json",
    )

    checks = {
        "project_build": _preflight_check(
            build_report["passed"],
            "manifest project build and verifier passed",
            build_report["summary"],
        ),
        "project_release": _preflight_check(
            release_verification["passed"],
            "project release exported and verified",
            release_verification["summary"],
        ),
        "submission_inputs": _preflight_check(
            submission_verification["passed"],
            "no-gold submission input exported and verified",
            submission_verification["summary"],
        ),
        "baseline_report": _preflight_check(
            _baseline_report_passed(baseline_report, requested_baselines),
            "deterministic release baselines executed",
            baseline_report["summary"],
        ),
        "taxonomy_coverage": _preflight_check(
            taxonomy_report["passed"],
            "taxonomy/domain coverage audit passed for this manifest release",
            taxonomy_report["summary"],
        ),
        "release_probe_leakage": _preflight_check(
            True,
            "gold probe wording leakage audited",
            release_leakage["summary"],
        ),
        "submission_probe_leakage": _preflight_check(
            True,
            "public submission-input probe wording leakage audited",
            submission_leakage["summary"],
        ),
    }
    required = ["project_build", "project_release", "submission_inputs", "baseline_report", "taxonomy_coverage"]
    issues = [
        {"code": f"workflow_manifest_preflight_{name}_failed", "message": checks[name]["message"]}
        for name in required
        if checks[name]["status"] != "pass"
    ]
    report = {
        "passed": not issues,
        "root": str(Path.cwd()),
        "manifest_path": str(manifest_path),
        "output_dir": str(output_dir),
        "project_id": build_report["project_id"],
        "domain": domain,
        "release_dir": str(release_dir),
        "submission_input_dir": str(input_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "checks_total": len(checks),
            "checks_passed": sum(1 for check in checks.values() if check["status"] == "pass"),
            "required_checks_failed": len(issues),
            "release_scope": taxonomy_report["summary"]["current_release_domain_scope"],
            "covered_workflow_domains": taxonomy_report["summary"]["covered_workflow_domains"],
            "projects": release_manifest["counts"]["projects"],
            "probes": release_manifest["counts"]["probes"],
            "baselines": list(baseline_report["summary"]["baseline_names"]),
            "issues": len(issues),
            "issue_codes": sorted({issue["code"] for issue in issues}),
        },
        "checks": checks,
        "artifacts": {
            "project_build_report": str(output_dir / "workflow_manifest_project_report.json"),
            "project_dir": str(project_dir),
            "release_dir": str(release_dir),
            "release_verification": str(output_dir / "evaluation_harness" / "project_release_verification.json"),
            "submission_input_dir": str(input_dir),
            "submission_input_verification": str(output_dir / "evaluation_harness" / "workflow_manifest_submission_inputs_verification.json"),
            "baseline_report": str(baseline_report_path),
            "taxonomy_coverage": str(output_dir / "evaluation_harness" / "project_release_taxonomy_coverage.json"),
            "release_probe_leakage": str(output_dir / "evaluation_harness" / "project_release_probe_leakage.json"),
            "submission_probe_leakage": str(output_dir / "evaluation_harness" / "project_submission_input_probe_leakage.json"),
        },
        "constraints": {
            "manifest_first": True,
            "requires_reviewed_manifest": True,
            "llm_generation_performed": False,
            "network_access_required": False,
            "release_ready_claim": False,
            "benchmark_release_gate_integration_required": True,
        },
        "issues": issues,
    }
    report["artifact_records"] = {
        name: _artifact_record(name, Path(path))
        for name, path in sorted(report["artifacts"].items())
    }
    if output_report_path is not None:
        write_json(output_report_path, report)
    return report


def preflight_workflow_manifest_release_batch(
    manifest_paths: list[Path] | tuple[Path, ...],
    output_dir: Path,
    output_report_path: Path | None = None,
    *,
    adapter: str = "auto",
    redact_sensitive: bool = True,
    version: str = "0.1.0",
    baseline_names: list[str] | tuple[str, ...] | None = DEFAULT_PREFLIGHT_BASELINES,
    top_k: int = 5,
    harden_probe_queries: bool = False,
) -> dict[str, Any]:
    """Run offline release preflights for multiple reviewed workflow manifests."""

    output_dir = Path(output_dir)
    reports = []
    issues = []
    for index, manifest_path in enumerate(manifest_paths):
        manifest_path = Path(manifest_path)
        manifest = read_json(manifest_path)
        domain = str(manifest.get("domain") or "email_workflow")
        project_id = str(manifest.get("project_id") or manifest_path.stem)
        item_dir = output_dir / f"{index:02d}_{_safe_path_id(domain)}_{_safe_path_id(project_id)}"
        report_path = item_dir / "workflow_manifest_release_preflight.json"
        try:
            item_report = preflight_workflow_manifest_release(
                manifest_path,
                item_dir,
                output_report_path=report_path,
                adapter=adapter,
                redact_sensitive=redact_sensitive,
                version=version,
                baseline_names=baseline_names,
                top_k=top_k,
                harden_probe_queries=harden_probe_queries,
            )
        except Exception as exc:
            issue = {
                "code": "workflow_manifest_batch_preflight_failed",
                "message": f"workflow manifest preflight failed for {manifest_path}: {exc}",
                "path": str(manifest_path),
            }
            issues.append(issue)
            reports.append(
                {
                    "status": "fail",
                    "manifest_path": str(manifest_path),
                    "report_path": str(report_path),
                    "domain": domain,
                    "project_id": project_id,
                    "issues": [issue],
                }
            )
            continue
        record = {
            "status": "pass" if item_report.get("passed") is True else "fail",
            "manifest_path": str(manifest_path),
            "report_path": str(report_path),
            "domain": item_report.get("domain"),
            "project_id": item_report.get("project_id"),
            "summary": item_report.get("summary", {}),
            "constraints": item_report.get("constraints", {}),
            "bytes": report_path.stat().st_size if report_path.exists() else None,
            "sha256": _file_sha256(report_path) if report_path.exists() else None,
        }
        reports.append(record)
        if item_report.get("passed") is not True:
            issues.append(
                {
                    "code": "workflow_manifest_batch_item_not_passed",
                    "message": f"workflow manifest preflight report did not pass: {manifest_path}",
                    "path": str(report_path),
                }
            )

    domains = sorted({str(report.get("domain")) for report in reports if report.get("status") == "pass" and report.get("domain")})
    report = {
        "passed": not issues,
        "root": str(Path.cwd()),
        "output_dir": str(output_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "manifests_total": len(manifest_paths),
            "reports_total": len(reports),
            "reports_passed": sum(1 for item in reports if item.get("status") == "pass"),
            "domains": domains,
            "issues": len(issues),
            "issue_codes": sorted({issue["code"] for issue in issues}),
        },
        "constraints": {
            "manifest_first": True,
            "requires_reviewed_manifest": True,
            "llm_generation_performed": False,
            "network_access_required": False,
            "release_ready_claim": False,
            "benchmark_release_gate_integration_required": True,
        },
        "preflight_reports": reports,
        "issues": issues,
    }
    if output_report_path is not None:
        write_json(output_report_path, report)
    return report


def verify_workflow_manifest_preflight_report(
    report_path: Path,
    output_path: Path | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Verify that a workflow-manifest preflight report still matches disk artifacts."""

    report_path = Path(report_path)
    issues: list[dict[str, Any]] = []
    artifact_results: dict[str, dict[str, Any]] = {}
    if not report_path.exists():
        report = {
            "passed": False,
            "report_path": str(report_path),
            "summary": {
                "artifacts_total": 0,
                "artifacts_verified": 0,
                "issues": 1,
                "issue_codes": ["workflow_manifest_preflight_report_missing"],
            },
            "artifacts": {},
            "issues": [
                {
                    "code": "workflow_manifest_preflight_report_missing",
                    "message": "workflow manifest preflight report is missing",
                    "path": str(report_path),
                }
            ],
        }
        if output_path is not None:
            write_json(output_path, report)
        return report

    source = read_json(report_path)
    source_root = Path(root or source.get("root") or report_path.resolve().parent)
    if source.get("passed") is not True or int(source.get("summary", {}).get("issues", 0) or 0) > 0:
        _issue(issues, "workflow_manifest_preflight_not_passed", "workflow manifest preflight report did not pass", report_path)
    constraints = source.get("constraints", {}) if isinstance(source.get("constraints"), dict) else {}
    if constraints.get("llm_generation_performed") is not False:
        _issue(issues, "workflow_manifest_preflight_llm_generation_ambiguous", "preflight must record llm_generation_performed=false", report_path)
    if constraints.get("release_ready_claim") is not False:
        _issue(issues, "workflow_manifest_preflight_release_claim_ambiguous", "preflight must record release_ready_claim=false", report_path)

    expected_records = source.get("artifact_records")
    if not isinstance(expected_records, dict) or not expected_records:
        _issue(issues, "workflow_manifest_preflight_artifact_records_missing", "preflight report has no artifact_records", report_path)
        expected_records = {}

    for name, expected in sorted(expected_records.items()):
        if not isinstance(expected, dict):
            _issue(issues, "workflow_manifest_preflight_artifact_record_invalid", f"artifact record is not an object: {name}", report_path)
            continue
        path = _resolve_path(Path(str(expected.get("path", ""))), source_root)
        actual = _artifact_record(str(name), path)
        result = {
            "path": str(path),
            "expected_status": expected.get("status"),
            "actual_status": actual.get("status"),
            "expected_kind": expected.get("kind"),
            "actual_kind": actual.get("kind"),
            "expected_sha256": expected.get("sha256"),
            "actual_sha256": actual.get("sha256"),
            "expected_bytes": expected.get("bytes"),
            "actual_bytes": actual.get("bytes"),
            "expected_files": expected.get("files"),
            "actual_files": actual.get("files"),
            "passed": True,
        }
        artifact_results[str(name)] = result
        _compare_artifact_record(str(name), expected, actual, result, issues)

    summary = {
        "artifacts_total": len(artifact_results),
        "artifacts_verified": sum(1 for result in artifact_results.values() if result["passed"]),
        "issues": len(issues),
        "issue_codes": sorted({issue["code"] for issue in issues}),
    }
    report = {
        "passed": not issues,
        "report_path": str(report_path),
        "root": str(source_root),
        "source_summary": source.get("summary", {}),
        "summary": summary,
        "artifacts": artifact_results,
        "issues": issues,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def verify_workflow_manifest_preflight_batch_report(
    report_path: Path,
    output_path: Path | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Verify a batch report and every referenced workflow-manifest preflight."""

    report_path = Path(report_path)
    issues: list[dict[str, Any]] = []
    report_results: dict[str, dict[str, Any]] = {}
    if not report_path.exists():
        report = {
            "passed": False,
            "report_path": str(report_path),
            "summary": {
                "reports_total": 0,
                "reports_verified": 0,
                "issues": 1,
                "issue_codes": ["workflow_manifest_preflight_batch_report_missing"],
            },
            "preflight_reports": {},
            "issues": [
                {
                    "code": "workflow_manifest_preflight_batch_report_missing",
                    "message": "workflow manifest preflight batch report is missing",
                    "path": str(report_path),
                }
            ],
        }
        if output_path is not None:
            write_json(output_path, report)
        return report

    source = read_json(report_path)
    source_root = Path(root or source.get("root") or report_path.resolve().parent)
    source_summary = source.get("summary", {}) if isinstance(source.get("summary"), dict) else {}
    if source.get("passed") is not True or int(source_summary.get("issues", 0) or 0) > 0:
        _issue(issues, "workflow_manifest_preflight_batch_not_passed", "workflow manifest preflight batch report did not pass", report_path)
    constraints = source.get("constraints", {}) if isinstance(source.get("constraints"), dict) else {}
    if constraints.get("llm_generation_performed") is not False:
        _issue(issues, "workflow_manifest_preflight_batch_llm_generation_ambiguous", "batch report must record llm_generation_performed=false", report_path)
    if constraints.get("release_ready_claim") is not False:
        _issue(issues, "workflow_manifest_preflight_batch_release_claim_ambiguous", "batch report must record release_ready_claim=false", report_path)

    preflight_reports = source.get("preflight_reports")
    if not isinstance(preflight_reports, list) or not preflight_reports:
        _issue(issues, "workflow_manifest_preflight_batch_reports_missing", "batch report has no preflight report records", report_path)
        preflight_reports = []

    for index, expected in enumerate(preflight_reports):
        name = f"workflow_manifest_preflight_{index}"
        if not isinstance(expected, dict):
            _issue(issues, "workflow_manifest_preflight_batch_record_invalid", f"batch preflight record is not an object: {index}", report_path)
            continue
        path = _resolve_path(Path(str(expected.get("report_path", ""))), source_root)
        result = {
            "path": str(path),
            "expected_status": expected.get("status"),
            "expected_sha256": expected.get("sha256"),
            "expected_bytes": expected.get("bytes"),
            "actual_sha256": None,
            "actual_bytes": None,
            "verification_summary": {},
            "passed": True,
            "domain": expected.get("domain"),
            "project_id": expected.get("project_id"),
        }
        report_results[name] = result
        if expected.get("status") != "pass":
            result["passed"] = False
            _issue(issues, "workflow_manifest_preflight_batch_item_not_passed", f"batch item was not passed when generated: {index}", path)
            continue
        if not path.exists():
            result["passed"] = False
            _issue(issues, "workflow_manifest_preflight_batch_item_missing", f"preflight report is missing: {index}", path)
            continue
        actual_sha256 = _file_sha256(path)
        actual_bytes = path.stat().st_size
        result["actual_sha256"] = actual_sha256
        result["actual_bytes"] = actual_bytes
        if expected.get("sha256") != actual_sha256:
            result["passed"] = False
            _issue(issues, "workflow_manifest_preflight_batch_item_sha256_mismatch", f"preflight report changed: {index}", path)
        if expected.get("bytes") is not None and expected.get("bytes") != actual_bytes:
            result["passed"] = False
            _issue(issues, "workflow_manifest_preflight_batch_item_bytes_mismatch", f"preflight report size changed: {index}", path)
        verification = verify_workflow_manifest_preflight_report(path, root=source_root)
        result["verification_summary"] = verification.get("summary", {})
        if verification.get("passed") is not True:
            result["passed"] = False
            _issue(issues, "workflow_manifest_preflight_batch_item_verification_not_passed", f"preflight report artifacts changed: {index}", path)

    summary = {
        "reports_total": len(report_results),
        "reports_verified": sum(1 for result in report_results.values() if result["passed"]),
        "source_issues": int(source_summary.get("issues", 0) or 0),
        "domains": sorted({str(result.get("domain")) for result in report_results.values() if result["passed"] and result.get("domain")}),
        "issues": len(issues),
        "issue_codes": sorted({issue["code"] for issue in issues}),
    }
    report = {
        "passed": not issues,
        "report_path": str(report_path),
        "root": str(source_root),
        "source_summary": source_summary,
        "summary": summary,
        "preflight_reports": report_results,
        "issues": issues,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def _validate_project_manifest_fields(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest.get("memory_graph"), dict):
        raise ValueError("workflow project manifest requires memory_graph object")
    probes = manifest.get("probes")
    if not isinstance(probes, list) or not probes:
        raise ValueError("workflow project manifest requires a non-empty probes list")


def _preflight_check(passed: bool, message: str, summary: dict[str, Any]) -> dict[str, Any]:
    return {"status": "pass" if passed else "fail", "message": message, "summary": summary}


def _baseline_report_passed(report: dict[str, Any], expected_baselines: list[str] | tuple[str, ...]) -> bool:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    names = set(summary.get("baseline_names", []))
    return (
        int(summary.get("projects", 0) or 0) > 0
        and int(summary.get("probes", 0) or 0) > 0
        and set(expected_baselines) <= names
    )


def _artifact_record(name: str, path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "name": name,
            "path": str(path),
            "status": "missing",
            "kind": "missing",
        }
    if path.is_dir():
        files = sorted(item for item in path.rglob("*") if item.is_file())
        return {
            "name": name,
            "path": str(path),
            "status": "present",
            "kind": "directory",
            "files": len(files),
            "bytes": sum(item.stat().st_size for item in files),
            "sha256": _directory_sha256(path, files),
        }
    return {
        "name": name,
        "path": str(path),
        "status": "present",
        "kind": "file",
        "bytes": path.stat().st_size,
        "sha256": _file_sha256(path),
    }


def _compare_artifact_record(
    name: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
    result: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    if expected.get("status") != actual.get("status"):
        result["passed"] = False
        _issue(issues, "workflow_manifest_preflight_artifact_status_mismatch", f"artifact {name} status changed", actual.get("path"))
        return
    if actual.get("status") != "present":
        result["passed"] = False
        _issue(issues, "workflow_manifest_preflight_artifact_missing", f"artifact {name} is missing", actual.get("path"))
        return
    for field, code in [
        ("kind", "workflow_manifest_preflight_artifact_kind_mismatch"),
        ("sha256", "workflow_manifest_preflight_artifact_sha256_mismatch"),
        ("bytes", "workflow_manifest_preflight_artifact_bytes_mismatch"),
        ("files", "workflow_manifest_preflight_artifact_files_mismatch"),
    ]:
        if expected.get(field) != actual.get(field):
            result["passed"] = False
            _issue(issues, code, f"artifact {name} {field} changed", actual.get("path"))


def _directory_sha256(root: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _resolve_path(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def _safe_path_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe.strip("._-") or "workflow_manifest"


def _issue(issues: list[dict[str, Any]], code: str, message: str, path: Path | str | None = None) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        item["path"] = str(path)
    issues.append(item)


def _select_adapter(manifest: dict[str, Any], adapter: str) -> str:
    if adapter not in {"auto", "email", "workflow"}:
        raise ValueError("adapter must be one of: auto, email, workflow")
    if adapter != "auto":
        return adapter
    if manifest.get("domain") in WorkflowManifestAdapter.ALLOWED_DOMAINS:
        return "workflow"
    return "email"


def _validate_project_binding(project_id: str, graph: MemoryGraph, probes: list[Probe]) -> None:
    issues = []
    if graph.project_id != project_id:
        issues.append(f"memory_graph.project_id must match manifest project_id: {graph.project_id} != {project_id}")
    mismatched_probes = sorted(probe.probe_id for probe in probes if probe.project_id != project_id)
    if mismatched_probes:
        issues.append(f"probe project_id must match manifest project_id: {mismatched_probes}")
    if issues:
        raise ValueError("; ".join(issues))


def _redacted_model(model: T, cls: type[T], enabled: bool) -> T:
    if not enabled:
        return model
    return model_validate(cls, _redact_value(model_to_dict(model), enabled))


def _redact_value(value: Any, enabled: bool) -> Any:
    if not enabled:
        return value
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_redact_value(item, enabled) for item in value]
    if isinstance(value, dict):
        return {
            redact(str(key)) if isinstance(key, str) else key: _redact_value(item, enabled)
            for key, item in value.items()
        }
    return value


def _source_manifest(
    *,
    manifest_path: Path,
    profile: ProjectProfile,
    domain: str,
    adapter: str,
    artifact_count: int,
    event_count: int,
    memory_count: int,
    probe_count: int,
    redact_sensitive: bool,
) -> dict[str, Any]:
    return {
        "project_id": profile.project_id,
        "source_streams": profile.source_streams,
        "artifact_count": artifact_count,
        "event_count": event_count,
        "memory_count": memory_count,
        "probe_count": probe_count,
        "construction": "manifest_first_reviewed_workflow_project",
        "manifest_path": str(manifest_path),
        "manifest_bytes": manifest_path.stat().st_size,
        "manifest_sha256": _file_sha256(manifest_path),
        "adapter": adapter,
        "domain": domain,
        "llm_role": "none; memory_graph and probes must be supplied by a reviewed manifest",
        "constraints": {
            "manifest_first": True,
            "reviewed_manifest_required": True,
            "raw_unredacted_content_exported": not redact_sensitive,
            "llm_generation_performed": False,
            "release_ready_claim": False,
        },
    }


def _privacy_leakage(project_dir: Path) -> dict[str, list[str]]:
    leakage: dict[str, list[str]] = {}
    for filename in ["project_profile.json", "artifacts.jsonl", "events.jsonl", "memory_graph.json", "probes.jsonl", "source_manifest.json"]:
        path = project_dir / filename
        tags = privacy_tags(path.read_text(encoding="utf-8"))
        if tags:
            leakage[filename] = sorted(set(tags))
    return leakage


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
