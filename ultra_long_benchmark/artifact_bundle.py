from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ultra_long_benchmark.claim_lint import verify_paper_claim_lint_report
from ultra_long_benchmark.data_discovery import verify_public_data_discovery_report
from ultra_long_benchmark.pipelines.baseline_configs import verify_baseline_batch_report
from ultra_long_benchmark.pipelines.baseline_configs import verify_baseline_config_validation_report
from ultra_long_benchmark.shared.io import read_json, write_json


DEFAULT_BENCHMARK_RELEASE_ARTIFACTS = {
    "project_release_dir": "examples/generated/release_packaging/gharchive_formal_project_benchmark",
    "hardened_submission_input_dir": "examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened",
    "paper_table_dir": "examples/generated/evaluation_harness/gharchive_formal_paper_tables",
    "claim_boundary_audit": "examples/generated/evaluation_harness/gharchive_formal_claim_boundary_audit.json",
    "claim_boundary_verification": "examples/generated/evaluation_harness/gharchive_formal_claim_boundary_verification.json",
    "claim_lint": "examples/generated/evaluation_harness/gharchive_formal_claim_lint.json",
    "taxonomy_coverage_audit": "examples/generated/evaluation_harness/gharchive_formal_taxonomy_coverage_audit.json",
    "public_data_discovery": "examples/generated/public_data_discovery_report.json",
    "workflow_source_audit": "examples/generated/workflow_data_source_audit.json",
    "gharchive_stage_plan": "examples/generated/gharchive_stage_plan.json",
    "gharchive_window_report": "examples/generated/gharchive_window_report.json",
    "gharchive_scale_summary": "examples/generated/gharchive_formal_scale_summary.json",
    "hardened_probe_leakage_audit": "examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened_probe_leakage_audit.json",
    "baseline_batch_report": "examples/generated/evaluation_harness/baseline_batch_after_claim_boundary/baseline_batch_report.json",
    "baseline_batch_verification": "examples/generated/evaluation_harness/baseline_batch_after_claim_boundary/baseline_batch_verification.json",
    "baseline_config_validation": "examples/generated/evaluation_harness/baseline_config_validation_after_artifact_bundle.json",
    "external_runner_report": "examples/generated/evaluation_harness/gharchive_formal_echo_policy_runner_report.json",
    "external_runner_validation": "examples/generated/evaluation_harness/gharchive_formal_echo_policy_runner_validation_against_input.json",
    "external_runner_submission_validation": "examples/generated/evaluation_harness/gharchive_formal_echo_policy_runner_submission_validation.json",
    "external_runner_score": "examples/generated/evaluation_harness/gharchive_formal_echo_policy_runner_score.json",
}


def audit_artifact_bundle(
    artifacts: dict[str, Path | str] | None = None,
    output_path: Path | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Create a reproducibility manifest for release artifacts without copying data."""

    root = Path(root or Path.cwd())
    artifact_paths = artifacts or {name: root / rel_path for name, rel_path in DEFAULT_BENCHMARK_RELEASE_ARTIFACTS.items()}
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    artifact_records: dict[str, dict[str, Any]] = {}
    extracted: dict[str, Any] = {}

    for name, raw_path in sorted(artifact_paths.items()):
        path = _resolve_path(Path(raw_path), root)
        record = _artifact_record(name, path)
        artifact_records[name] = record
        if record["status"] == "missing":
            _issue(issues, "artifact_missing", f"required artifact is missing: {name}", path)
            continue
        if record["kind"] == "json_file":
            extracted[name] = record.get("json_extract", {})

    _check_known_artifacts(extracted, artifact_records, issues, warnings)
    summary = {
        "artifacts_total": len(artifact_records),
        "artifacts_present": sum(1 for record in artifact_records.values() if record["status"] == "present"),
        "directories": sum(1 for record in artifact_records.values() if record["kind"] == "directory"),
        "files": sum(1 for record in artifact_records.values() if record["kind"] != "directory" and record["status"] == "present"),
        "issues": len(issues),
        "warnings": len(warnings),
        "issue_codes": sorted({issue["code"] for issue in issues}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
    }
    report = {
        "passed": not issues,
        "root": str(root),
        "summary": summary,
        "artifacts": artifact_records,
        "checks": extracted,
        "issues": issues,
        "warnings": warnings,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def verify_artifact_bundle_manifest(
    manifest_path: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Verify that an artifact bundle manifest still matches files on disk."""

    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        report = {
            "passed": False,
            "manifest_path": str(manifest_path),
            "summary": {
                "artifacts_total": 0,
                "artifacts_verified": 0,
                "issues": 1,
                "warnings": 0,
                "issue_codes": ["manifest_missing"],
                "warning_codes": [],
            },
            "artifacts": {},
            "issues": [{"code": "manifest_missing", "message": "artifact bundle manifest is missing", "path": str(manifest_path)}],
            "warnings": [],
        }
        if output_path is not None:
            write_json(output_path, report)
        return report

    manifest = read_json(manifest_path)
    root = Path(str(manifest.get("root") or manifest_path.resolve().parents[3]))
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = list(manifest.get("warnings", []))
    artifact_results: dict[str, dict[str, Any]] = {}

    if manifest.get("passed") is not True:
        _issue(issues, "manifest_not_passed", "artifact bundle manifest did not pass when generated", manifest_path)
    for issue in manifest.get("issues", []):
        if isinstance(issue, dict):
            _issue(
                issues,
                str(issue.get("code", "manifest_recorded_issue")),
                str(issue.get("message", "artifact bundle manifest recorded an issue")),
                issue.get("path") or manifest_path,
            )
        else:
            _issue(issues, "manifest_recorded_issue", str(issue), manifest_path)

    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        _issue(issues, "manifest_artifacts_invalid", "manifest artifacts field is not an object", manifest_path)
        artifacts = {}
    elif not artifacts:
        _issue(issues, "manifest_artifacts_missing", "manifest has no artifact records", manifest_path)

    for name, expected in sorted(artifacts.items()):
        if not isinstance(expected, dict):
            _issue(issues, "artifact_record_invalid", f"artifact record is not an object: {name}", manifest_path)
            continue
        path = _resolve_path(Path(str(expected.get("path", ""))), root)
        actual = _artifact_record(name, path)
        result = {
            "name": name,
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
        artifact_results[name] = result
        _compare_artifact_record(name, expected, actual, result, issues)

    claim_lint_result = artifact_results.get("claim_lint")
    if claim_lint_result and claim_lint_result.get("actual_status") == "present":
        claim_lint_verification = verify_paper_claim_lint_report(Path(claim_lint_result["path"]))
        claim_lint_result["claim_lint_verification_summary"] = claim_lint_verification.get("summary", {})
        if claim_lint_verification.get("passed") is not True:
            claim_lint_result["passed"] = False
            _issue(issues, "claim_lint_verification_not_passed", "paper claim lint source files changed or lack digests", claim_lint_result["path"])

    public_data_result = artifact_results.get("public_data_discovery")
    if public_data_result and public_data_result.get("actual_status") == "present":
        public_data_verification = verify_public_data_discovery_report(Path(public_data_result["path"]))
        public_data_result["public_data_verification_summary"] = public_data_verification.get("summary", {})
        if public_data_verification.get("passed") is not True:
            public_data_result["passed"] = False
            _issue(
                issues,
                "public_data_discovery_verification_not_passed",
                "public data discovery candidate files changed or lack digests",
                public_data_result["path"],
            )

    baseline_batch_result = artifact_results.get("baseline_batch_report")
    if baseline_batch_result and baseline_batch_result.get("actual_status") == "present":
        baseline_batch_verification = verify_baseline_batch_report(Path(baseline_batch_result["path"]))
        baseline_batch_result["baseline_batch_verification_summary"] = baseline_batch_verification.get("summary", {})
        if baseline_batch_verification.get("passed") is not True:
            baseline_batch_result["passed"] = False
            _issue(issues, "baseline_batch_verification_not_passed", "baseline batch runner reports or outputs changed or lack digests", baseline_batch_result["path"])
    _check_baseline_batch_verification_artifact(artifact_results, issues)
    baseline_config_result = artifact_results.get("baseline_config_validation")
    if baseline_config_result and baseline_config_result.get("actual_status") == "present":
        baseline_config_verification = verify_baseline_config_validation_report(Path(baseline_config_result["path"]))
        baseline_config_result["baseline_config_verification_summary"] = baseline_config_verification.get("summary", {})
        if baseline_config_verification.get("passed") is not True:
            baseline_config_result["passed"] = False
            _issue(
                issues,
                "baseline_config_verification_not_passed",
                "baseline config validation inputs changed or lack digests",
                baseline_config_result["path"],
            )

    summary = {
        "artifacts_total": len(artifact_results),
        "artifacts_verified": sum(1 for result in artifact_results.values() if result["passed"]),
        "issues": len(issues),
        "warnings": len(warnings),
        "issue_codes": sorted({issue["code"] for issue in issues}),
        "warning_codes": sorted({warning.get("code", str(warning)) for warning in warnings}),
    }
    report = {
        "passed": not issues,
        "manifest_path": str(manifest_path),
        "root": str(root),
        "summary": summary,
        "artifacts": artifact_results,
        "issues": issues,
        "warnings": warnings,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


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
    record = {
        "name": name,
        "path": str(path),
        "status": "present",
        "kind": "json_file" if path.suffix == ".json" else "file",
        "bytes": path.stat().st_size,
        "sha256": _file_sha256(path),
    }
    if path.suffix == ".json":
        try:
            payload = read_json(path)
            record["json_extract"] = _json_extract(payload)
        except Exception as exc:
            record["kind"] = "json_file_unreadable"
            record["json_error"] = str(exc)
    return record


def _compare_artifact_record(
    name: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
    result: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    if expected.get("status") != actual.get("status"):
        result["passed"] = False
        _issue(issues, "artifact_status_mismatch", f"artifact status changed: {name}", actual.get("path"))
        return
    if actual.get("status") != "present":
        result["passed"] = False
        _issue(issues, "artifact_missing", f"artifact is no longer present: {name}", actual.get("path"))
        return
    for key, code in [
        ("kind", "artifact_kind_mismatch"),
        ("sha256", "artifact_sha256_mismatch"),
        ("bytes", "artifact_bytes_mismatch"),
        ("files", "artifact_file_count_mismatch"),
    ]:
        if key in expected and expected.get(key) != actual.get(key):
            result["passed"] = False
            _issue(issues, code, f"artifact {key} changed: {name}", actual.get("path"))


def _json_extract(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"type": type(payload).__name__}
    extract: dict[str, Any] = {}
    for key in [
        "passed",
        "status",
        "executed",
        "summary",
        "report_path",
        "manifest_path",
        "decision",
        "quality",
        "release",
        "repos",
        "tasks",
    ]:
        if key in payload:
            extract[key] = payload[key]
    for key in ["claims_total", "supported", "qualified", "blocked"]:
        if isinstance(payload.get("summary"), dict) and key in payload["summary"]:
            extract[key] = payload["summary"][key]
    return extract


def _check_known_artifacts(
    extracted: dict[str, Any],
    records: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    readiness = extracted.get("readiness_report", {})
    readiness_summary = readiness.get("summary", {}) if isinstance(readiness.get("summary"), dict) else {}
    if readiness and readiness.get("passed") is not True:
        _issue(issues, "readiness_not_passed", "readiness report did not pass", records["readiness_report"]["path"])
    if readiness and readiness_summary.get("failed") not in (0, None):
        _issue(issues, "readiness_has_failures", "readiness report contains failed checks", records["readiness_report"]["path"])

    claim = extracted.get("claim_boundary_audit", {})
    claim_summary = claim.get("summary", {}) if isinstance(claim.get("summary"), dict) else {}
    if claim and claim.get("passed") is not True:
        _issue(issues, "claim_boundary_not_passed", "claim-boundary audit did not pass", records["claim_boundary_audit"]["path"])
    if int(claim_summary.get("blocked", 0)) > 0:
        _warn(warnings, "claim_boundary_has_blocked_claims", "claim-boundary audit still has blocked paper-facing claims", records["claim_boundary_audit"]["path"])

    claim_verification = extracted.get("claim_boundary_verification", {})
    if claim_verification and claim_verification.get("passed") is not True:
        _issue(issues, "claim_boundary_verification_not_passed", "claim-boundary verification did not pass", records["claim_boundary_verification"]["path"])

    claim_lint = extracted.get("claim_lint", {})
    claim_lint_summary = claim_lint.get("summary", {}) if isinstance(claim_lint.get("summary"), dict) else {}
    if claim_lint and claim_lint.get("passed") is not True:
        _issue(issues, "claim_lint_not_passed", "paper claim lint did not pass", records["claim_lint"]["path"])
    if claim_lint and int(claim_lint_summary.get("issues", 0)) > 0:
        _issue(issues, "claim_lint_has_issues", "paper claim lint found blocked affirmative claims", records["claim_lint"]["path"])
    if claim_lint:
        claim_lint_verification = verify_paper_claim_lint_report(Path(records["claim_lint"]["path"]))
        if claim_lint_verification.get("passed") is not True:
            _issue(issues, "claim_lint_verification_not_passed", "paper claim lint source files changed or lack digests", records["claim_lint"]["path"])

    taxonomy = extracted.get("taxonomy_coverage_audit", {})
    taxonomy_summary = taxonomy.get("summary", {}) if isinstance(taxonomy.get("summary"), dict) else {}
    if taxonomy and taxonomy.get("passed") is not True:
        _issue(issues, "taxonomy_coverage_not_passed", "taxonomy coverage audit did not pass", records["taxonomy_coverage_audit"]["path"])
    if taxonomy_summary.get("current_release_domain_scope") == "github_developer_workflow_only":
        _warn(warnings, "github_only_release_scope", "artifact bundle is for the GitHub-only benchmark release", records["taxonomy_coverage_audit"]["path"])

    public_data = extracted.get("public_data_discovery", {})
    public_data_summary = public_data.get("summary", {}) if isinstance(public_data.get("summary"), dict) else {}
    if public_data and int(public_data_summary.get("usable_sources", 0)) <= 0:
        _issue(issues, "public_data_discovery_no_usable_sources", "public data discovery has no usable workflow source", records["public_data_discovery"]["path"])

    stage_plan = extracted.get("gharchive_stage_plan", {})
    stage_summary = stage_plan.get("summary", {}) if isinstance(stage_plan.get("summary"), dict) else {}
    if stage_plan and stage_summary.get("passed") is not True:
        _issue(issues, "gharchive_stage_plan_not_passed", "GHArchive stage plan did not pass", records["gharchive_stage_plan"]["path"])

    window_report = extracted.get("gharchive_window_report", {})
    window_summary = window_report.get("summary", {}) if isinstance(window_report.get("summary"), dict) else {}
    if window_report and int(window_summary.get("eligible_windows", 0)) <= 0:
        _issue(issues, "gharchive_window_report_no_eligible_windows", "GHArchive window report has no eligible windows", records["gharchive_window_report"]["path"])

    scale_summary = extracted.get("gharchive_scale_summary", {})
    scale_tasks = scale_summary.get("tasks", {}) if isinstance(scale_summary.get("tasks"), dict) else {}
    scale_repos = scale_summary.get("repos", {}) if isinstance(scale_summary.get("repos"), dict) else {}
    scale_release = scale_summary.get("release", {}) if isinstance(scale_summary.get("release"), dict) else {}
    if scale_summary and int(scale_tasks.get("total", 0)) <= 0:
        _issue(issues, "gharchive_scale_summary_no_tasks", "GHArchive scale summary has no released tasks", records["gharchive_scale_summary"]["path"])
    if scale_summary and int(scale_repos.get("eligible_packs", 0)) <= 0:
        _issue(issues, "gharchive_scale_summary_no_eligible_packs", "GHArchive scale summary has no eligible packs", records["gharchive_scale_summary"]["path"])
    if scale_summary and scale_release.get("pack_hashes_present") is not True:
        _issue(issues, "gharchive_scale_summary_missing_pack_hashes", "GHArchive scale summary does not confirm pack hashes", records["gharchive_scale_summary"]["path"])

    baseline = extracted.get("baseline_batch_report", {})
    baseline_summary = baseline.get("summary", {}) if isinstance(baseline.get("summary"), dict) else {}
    if baseline and baseline.get("passed") is not True:
        _issue(issues, "baseline_batch_not_passed", "baseline batch report did not pass", records["baseline_batch_report"]["path"])
    if int(baseline_summary.get("failed", 0)) > 0 or int(baseline_summary.get("blocked", 0)) > 0:
        _issue(issues, "baseline_batch_has_failures", "baseline batch has failed or blocked configs", records["baseline_batch_report"]["path"])
    baseline_verification = extracted.get("baseline_batch_verification", {})
    baseline_verification_summary = (
        baseline_verification.get("summary", {}) if isinstance(baseline_verification.get("summary"), dict) else {}
    )
    if baseline_verification and baseline_verification.get("passed") is not True:
        _issue(
            issues,
            "baseline_batch_verification_report_not_passed",
            "baseline batch verification report did not pass",
            records["baseline_batch_verification"]["path"],
        )
    if baseline_verification and int(baseline_verification_summary.get("issues", 0)) > 0:
        _issue(
            issues,
            "baseline_batch_verification_report_has_issues",
            "baseline batch verification report contains issues",
            records["baseline_batch_verification"]["path"],
        )
    if baseline and baseline_verification:
        _check_report_target(
            baseline_verification.get("report_path"),
            records["baseline_batch_report"]["path"],
            "baseline_batch_verification_target_mismatch",
            "baseline batch verification report does not target the bundled baseline batch report",
            records["baseline_batch_verification"]["path"],
            issues,
        )
    baseline_config = extracted.get("baseline_config_validation", {})
    baseline_config_summary = baseline_config.get("summary", {}) if isinstance(baseline_config.get("summary"), dict) else {}
    if baseline_config and baseline_config.get("passed") is not True:
        _issue(
            issues,
            "baseline_config_validation_not_passed",
            "baseline config validation report did not pass",
            records["baseline_config_validation"]["path"],
        )
    if baseline_config and int(baseline_config_summary.get("configs_failed", 0)) > 0:
        _issue(
            issues,
            "baseline_config_validation_has_failures",
            "baseline config validation report contains failed configs",
            records["baseline_config_validation"]["path"],
        )

    runner = extracted.get("external_runner_report", {})
    runner_summary = runner.get("summary", {}) if isinstance(runner.get("summary"), dict) else {}
    if runner:
        if runner.get("status") != "completed" or runner.get("executed") is not True:
            _issue(issues, "external_runner_not_executed", "external runner contract did not complete", records["external_runner_report"]["path"])
        if runner_summary.get("output_validation_passed") is not True:
            _issue(issues, "external_runner_output_invalid", "external runner output validation did not pass", records["external_runner_report"]["path"])
        if int(runner_summary.get("predictions", 0)) != int(runner_summary.get("probes", -1)):
            _issue(issues, "external_runner_coverage_mismatch", "external runner prediction count does not match probe count", records["external_runner_report"]["path"])

    for name in ["external_runner_validation", "external_runner_submission_validation"]:
        validation = extracted.get(name, {})
        if validation and validation.get("passed") is not True:
            _issue(issues, f"{name}_not_passed", f"{name} did not pass", records[name]["path"])


def _check_baseline_batch_verification_artifact(
    artifact_results: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    verification_result = artifact_results.get("baseline_batch_verification")
    baseline_result = artifact_results.get("baseline_batch_report")
    if not verification_result or verification_result.get("actual_status") != "present":
        return
    path = Path(str(verification_result["path"]))
    try:
        report = read_json(path)
    except Exception as exc:
        verification_result["passed"] = False
        _issue(issues, "baseline_batch_verification_unreadable", f"baseline batch verification report cannot be read: {exc}", path)
        return
    verification_result["baseline_batch_verification_summary"] = report.get("summary", {})
    if report.get("passed") is not True:
        verification_result["passed"] = False
        _issue(issues, "baseline_batch_verification_report_not_passed", "baseline batch verification report did not pass", path)
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    if int(summary.get("issues", 0)) > 0:
        verification_result["passed"] = False
        _issue(issues, "baseline_batch_verification_report_has_issues", "baseline batch verification report contains issues", path)
    if baseline_result and baseline_result.get("actual_status") == "present":
        _check_report_target(
            report.get("report_path"),
            baseline_result["path"],
            "baseline_batch_verification_target_mismatch",
            "baseline batch verification report does not target the bundled baseline batch report",
            path,
            issues,
            result=verification_result,
        )


def _check_report_target(
    actual_raw: Any,
    expected_raw: Path | str,
    code: str,
    message: str,
    path: Path | str,
    issues: list[dict[str, Any]],
    *,
    result: dict[str, Any] | None = None,
) -> None:
    actual = Path(str(actual_raw)).resolve() if actual_raw else None
    expected = Path(str(expected_raw)).resolve()
    if actual != expected:
        if result is not None:
            result["passed"] = False
            result["expected_report_path"] = str(expected)
            result["actual_report_path"] = str(actual) if actual is not None else None
        _issue(issues, code, message, path)


def _resolve_path(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def _directory_sha256(root: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        rel_path = path.relative_to(root).as_posix()
        digest.update(rel_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_file_sha256(path).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


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


def _warn(warnings: list[dict[str, Any]], code: str, message: str, path: Path | str | None = None) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        item["path"] = str(path)
    warnings.append(item)
