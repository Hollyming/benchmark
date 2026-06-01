from pathlib import Path

from ultra_long_benchmark.domain_expansion import build_domain_expansion_readiness_report
from ultra_long_benchmark.domain_expansion import verify_domain_expansion_readiness_report
from ultra_long_benchmark.pipelines.workflow_manifest_project import preflight_workflow_manifest_release
from ultra_long_benchmark.pipelines.workflow_manifest_project import preflight_workflow_manifest_release_batch
from ultra_long_benchmark.shared.io import read_json, write_json
from tests.test_workflow_manifest_project import WORKFLOW_PROJECT_MANIFEST_FIXTURES
from tests.test_workflow_manifest_project import _write_calendar_project_manifest


def test_domain_expansion_readiness_records_github_only_release(tmp_path: Path):
    reports = _write_reports(tmp_path)
    output = tmp_path / "domain_expansion.json"

    report = build_domain_expansion_readiness_report(reports, output_path=output, root=tmp_path)

    assert report["passed"] is True
    assert report["summary"]["release_ready_domains"] == ["github_developer_workflow"]
    assert report["summary"]["multi_domain_release_ready"] is False
    assert report["domains"]["github_developer_workflow"]["status"] == "current_release_ready"
    assert report["domains"]["email_workflow"]["status"] == "blocked_license_privacy_manifest"
    assert "license_privacy_pii_gate" in {item["gate"] for item in report["domains"]["email_workflow"]["blockers"]}
    assert report["domains"]["email_workflow"]["roadmap"]["stage"] == "blocked_on_license_privacy_manifest"
    assert report["domains"]["email_workflow"]["roadmap"]["external_input_required_for_release"] is True
    assert report["domains"]["email_workflow"]["roadmap"]["offline_engineering_required"] is True
    assert any("Do not load raw email records" in item for item in report["domains"]["email_workflow"]["roadmap"]["stop_conditions"])
    assert report["domains"]["calendar_workflow"]["roadmap"]["stage"] == "blocked_on_data_with_offline_scaffolding_remaining"
    assert report["domains"]["calendar_workflow"]["adapter_status"] == "implemented_manifest_first"
    assert report["domains"]["calendar_workflow"]["gates"]["canonical_event_adapter"]["status"] == "pass"
    assert report["domains"]["calendar_workflow"]["roadmap"]["external_input_required_for_release"] is True
    assert report["domains"]["calendar_workflow"]["roadmap"]["offline_engineering_required"] is True
    assert "canonical_event_adapter" not in {item["gate"] for item in report["domains"]["calendar_workflow"]["roadmap"]["offline_engineering_blockers"]}
    assert "calendar_workflow" in report["summary"]["external_input_blocked_domains"]
    assert "calendar_workflow" in report["summary"]["offline_engineering_blocked_domains"]
    assert "github_developer_workflow" not in report["summary"]["external_input_blocked_domains"]
    assert "multi_domain_expansion_not_ready" in report["summary"]["warning_codes"]
    assert report["inputs"]["taxonomy_coverage_audit"]["sha256"]
    assert read_json(output)["summary"]["release_ready_domains"] == ["github_developer_workflow"]
    assert verify_domain_expansion_readiness_report(output)["passed"] is True


def test_domain_expansion_readiness_can_require_multi_domain(tmp_path: Path):
    reports = _write_reports(tmp_path)

    report = build_domain_expansion_readiness_report(reports, root=tmp_path, require_multi_domain=True)

    assert report["passed"] is False
    assert "multi_domain_expansion_required" in report["summary"]["issue_codes"]


def test_domain_expansion_readiness_marks_email_manifest_without_release_pipeline(tmp_path: Path):
    reports = _write_reports(tmp_path)
    source = read_json(reports["workflow_source_audit"])
    source["summary"]["email_manifest_sources"] = 1
    write_json(reports["workflow_source_audit"], source)
    discovery = read_json(reports["public_data_discovery"])
    discovery["summary"]["email_manifest_sources"] = 1
    write_json(reports["public_data_discovery"], discovery)

    report = build_domain_expansion_readiness_report(reports, root=tmp_path)

    email = report["domains"]["email_workflow"]
    assert email["status"] == "source_manifest_ready_release_pipeline_missing"
    assert email["gates"]["license_privacy_pii_gate"]["status"] == "pass"
    assert email["gates"]["verifier_checked_project_release"]["status"] == "missing"
    assert email["roadmap"]["stage"] == "release_pipeline_engineering_missing"
    assert email["roadmap"]["external_input_required_for_release"] is False
    assert email["roadmap"]["offline_engineering_required"] is True
    assert "domain_release_pipeline_missing" in report["summary"]["warning_codes"]


def test_domain_expansion_readiness_marks_calendar_manifest_without_release_pipeline(tmp_path: Path):
    reports = _write_reports(tmp_path)
    source = read_json(reports["workflow_source_audit"])
    source["summary"]["calendar_manifest_sources"] = 1
    write_json(reports["workflow_source_audit"], source)
    discovery = read_json(reports["public_data_discovery"])
    discovery["summary"]["calendar_manifest_sources"] = 1
    write_json(reports["public_data_discovery"], discovery)

    report = build_domain_expansion_readiness_report(reports, root=tmp_path)

    calendar = report["domains"]["calendar_workflow"]
    assert calendar["status"] == "source_manifest_ready_release_pipeline_missing"
    assert calendar["gates"]["reusable_trace_source"]["status"] == "pass"
    assert calendar["gates"]["license_privacy_pii_gate"]["status"] == "pass"
    assert calendar["roadmap"]["stage"] == "release_pipeline_engineering_missing"
    assert calendar["roadmap"]["external_input_required_for_release"] is False
    assert calendar["roadmap"]["offline_engineering_required"] is True


def test_domain_expansion_readiness_records_workflow_manifest_preflight_without_release_claim(tmp_path: Path):
    reports = _write_reports(tmp_path)
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    preflight_path = tmp_path / "preflight" / "workflow_manifest_release_preflight.json"
    preflight_workflow_manifest_release(
        manifest_path,
        tmp_path / "preflight",
        output_report_path=preflight_path,
    )

    report = build_domain_expansion_readiness_report(
        reports,
        root=tmp_path,
        workflow_manifest_preflight_reports=[preflight_path],
    )

    calendar = report["domains"]["calendar_workflow"]
    assert report["summary"]["release_ready_domains"] == ["github_developer_workflow"]
    assert report["summary"]["preflight_ready_domains"] == ["calendar_workflow"]
    assert calendar["ready_for_current_release"] is False
    assert calendar["status"] == "source_manifest_ready_release_pipeline_missing"
    assert calendar["roadmap"]["preflight_passed"] is True
    assert calendar["roadmap"]["stage"] == "workflow_manifest_preflight_passed_gate_integration_missing"
    assert calendar["roadmap"]["external_input_required_for_release"] is False
    assert calendar["roadmap"]["offline_engineering_required"] is True
    assert calendar["roadmap"]["workflow_manifest_preflight"]["project_id"] == "project_calendar_fixture_001"
    assert any(item["kind"] == "benchmark_release_gate_integration" for item in calendar["roadmap"]["offline_engineering_blockers"])
    assert report["inputs"]["workflow_manifest_preflight_0"]["sha256"]
    assert verify_domain_expansion_readiness_report(
        _write_domain_expansion_report(tmp_path, report),
    )["passed"] is True


def test_domain_expansion_readiness_expands_workflow_manifest_preflight_batch(tmp_path: Path):
    reports = _write_reports(tmp_path)
    batch_path = tmp_path / "preflight_batch" / "workflow_manifest_preflight_batch_report.json"
    preflight_workflow_manifest_release_batch(
        [fixture[0] for fixture in WORKFLOW_PROJECT_MANIFEST_FIXTURES],
        tmp_path / "preflight_batch",
        output_report_path=batch_path,
        baseline_names=["oracle_policy_graph"],
    )

    report = build_domain_expansion_readiness_report(
        reports,
        root=tmp_path,
        workflow_manifest_preflight_batch_reports=[batch_path],
    )

    assert report["summary"]["release_ready_domains"] == ["github_developer_workflow"]
    assert report["summary"]["preflight_ready_domains"] == [
        "calendar_workflow",
        "docs_workflow",
        "chat_workflow",
        "browser_web_workflow",
    ]
    assert report["inputs"]["workflow_manifest_preflight_batch_0"]["status"] == "pass"
    assert report["inputs"]["workflow_manifest_preflight_batch_0"]["verification_summary"]["reports_verified"] == 4
    assert report["inputs"]["workflow_manifest_preflight_0"]["status"] == "pass"
    assert report["domains"]["docs_workflow"]["roadmap"]["preflight_passed"] is True
    assert verify_domain_expansion_readiness_report(
        _write_domain_expansion_report(tmp_path, report),
    )["passed"] is True


def test_verify_domain_expansion_readiness_fails_when_preflight_artifact_changes(tmp_path: Path):
    reports = _write_reports(tmp_path)
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    preflight_path = tmp_path / "preflight" / "workflow_manifest_release_preflight.json"
    preflight = preflight_workflow_manifest_release(
        manifest_path,
        tmp_path / "preflight",
        output_report_path=preflight_path,
    )
    domain_expansion_path = tmp_path / "domain_expansion.json"
    build_domain_expansion_readiness_report(
        reports,
        output_path=domain_expansion_path,
        root=tmp_path,
        workflow_manifest_preflight_reports=[preflight_path],
    )
    profile_path = Path(preflight["artifacts"]["project_dir"]) / "project_profile.json"
    profile = read_json(profile_path)
    profile["title"] = profile["title"] + " drift"
    write_json(profile_path, profile)

    report = verify_domain_expansion_readiness_report(domain_expansion_path)

    assert report["passed"] is False
    assert "domain_expansion_preflight_verification_not_passed" in report["summary"]["issue_codes"]
    assert report["inputs"]["workflow_manifest_preflight_0"]["passed"] is False
    assert "workflow_manifest_preflight_artifact_sha256_mismatch" in report["inputs"]["workflow_manifest_preflight_0"]["verification_summary"]["issue_codes"]


def test_verify_domain_expansion_readiness_fails_when_batch_preflight_artifact_changes(tmp_path: Path):
    reports = _write_reports(tmp_path)
    batch_path = tmp_path / "preflight_batch" / "workflow_manifest_preflight_batch_report.json"
    batch = preflight_workflow_manifest_release_batch(
        [fixture[0] for fixture in WORKFLOW_PROJECT_MANIFEST_FIXTURES],
        tmp_path / "preflight_batch",
        output_report_path=batch_path,
        baseline_names=["oracle_policy_graph"],
    )
    domain_expansion_path = tmp_path / "domain_expansion.json"
    build_domain_expansion_readiness_report(
        reports,
        output_path=domain_expansion_path,
        root=tmp_path,
        workflow_manifest_preflight_batch_reports=[batch_path],
    )
    first_preflight_path = Path(batch["preflight_reports"][0]["report_path"])
    first_preflight = read_json(first_preflight_path)
    profile_path = Path(first_preflight["artifacts"]["project_dir"]) / "project_profile.json"
    profile = read_json(profile_path)
    profile["title"] = profile["title"] + " drift"
    write_json(profile_path, profile)

    report = verify_domain_expansion_readiness_report(domain_expansion_path)

    assert report["passed"] is False
    assert "domain_expansion_preflight_batch_verification_not_passed" in report["summary"]["issue_codes"]
    assert "domain_expansion_preflight_verification_not_passed" in report["summary"]["issue_codes"]
    assert report["inputs"]["workflow_manifest_preflight_batch_0"]["passed"] is False
    assert "workflow_manifest_preflight_batch_item_verification_not_passed" in report["inputs"]["workflow_manifest_preflight_batch_0"]["verification_summary"]["issue_codes"]


def test_domain_expansion_readiness_blocks_drifted_workflow_manifest_preflight(tmp_path: Path):
    reports = _write_reports(tmp_path)
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    preflight_path = tmp_path / "preflight" / "workflow_manifest_release_preflight.json"
    preflight = preflight_workflow_manifest_release(
        manifest_path,
        tmp_path / "preflight",
        output_report_path=preflight_path,
    )
    profile_path = Path(preflight["artifacts"]["project_dir"]) / "project_profile.json"
    profile = read_json(profile_path)
    profile["title"] = profile["title"] + " drift"
    write_json(profile_path, profile)

    report = build_domain_expansion_readiness_report(
        reports,
        root=tmp_path,
        workflow_manifest_preflight_reports=[preflight_path],
    )

    assert report["summary"]["preflight_ready_domains"] == []
    assert "workflow_manifest_preflight_not_passed" in report["summary"]["warning_codes"]
    assert report["inputs"]["workflow_manifest_preflight_0"]["status"] == "warn"
    assert "workflow_manifest_preflight_artifact_sha256_mismatch" in report["inputs"]["workflow_manifest_preflight_0"]["verification_summary"]["issue_codes"]
    assert report["domains"]["calendar_workflow"]["roadmap"].get("preflight_passed") is not True


def test_verify_domain_expansion_readiness_fails_when_input_changes(tmp_path: Path):
    reports = _write_reports(tmp_path)
    output = tmp_path / "domain_expansion.json"
    build_domain_expansion_readiness_report(reports, output_path=output, root=tmp_path)
    taxonomy = read_json(reports["taxonomy_coverage_audit"])
    taxonomy["summary"]["multi_domain_release_ready"] = True
    write_json(reports["taxonomy_coverage_audit"], taxonomy)

    report = verify_domain_expansion_readiness_report(output)

    assert report["passed"] is False
    assert "domain_expansion_input_sha256_mismatch" in report["summary"]["issue_codes"]
    assert report["inputs"]["taxonomy_coverage_audit"]["passed"] is False


def _write_domain_expansion_report(tmp_path: Path, report: dict) -> Path:
    path = tmp_path / "domain_expansion_with_preflight.json"
    write_json(path, report)
    return path


def _write_reports(tmp_path: Path) -> dict[str, Path]:
    reports = {
        "readiness_report": tmp_path / "readiness.json",
        "taxonomy_coverage_audit": tmp_path / "taxonomy.json",
        "workflow_source_audit": tmp_path / "source_audit.json",
        "public_data_discovery": tmp_path / "discovery.json",
        "claim_boundary_audit": tmp_path / "claim.json",
    }
    write_json(
        reports["readiness_report"],
        {
            "passed": True,
            "summary": {"failed": 0},
            "checks": {
                "project_benchmark_release": {"status": "pass"},
                "project_submission_inputs": {"status": "pass"},
                "project_release_baselines": {"status": "pass"},
                "baseline_batch": {"status": "pass"},
                "taxonomy_coverage_audit": {"status": "warn"},
                "claim_boundary_audit": {"status": "warn"},
                "artifact_bundle_manifest": {"status": "warn"},
            },
        },
    )
    write_json(
        reports["taxonomy_coverage_audit"],
        {
            "passed": True,
            "summary": {
                "current_release_domain_scope": "github_developer_workflow_only",
                "covered_workflow_domains": ["github_developer_workflow"],
            },
            "checks": {
                "workflow_domain_coverage": {
                    "github_developer_workflow": {
                        "status": "covered",
                        "matched_event_source_datasets": {"gharchive": 10},
                        "matched_source_streams": {"gharchive": 2},
                        "evidence_count": 10,
                    },
                    "email_workflow": {"status": "blocked_license_privacy_manifest", "matched_event_source_datasets": {}, "matched_source_streams": {}, "evidence_count": 0},
                    "calendar_workflow": {"status": "planned_not_released", "matched_event_source_datasets": {}, "matched_source_streams": {}, "evidence_count": 0},
                    "docs_workflow": {"status": "planned_not_released", "matched_event_source_datasets": {}, "matched_source_streams": {}, "evidence_count": 0},
                    "chat_workflow": {"status": "planned_not_released", "matched_event_source_datasets": {}, "matched_source_streams": {}, "evidence_count": 0},
                    "browser_web_workflow": {"status": "planned_not_released", "matched_event_source_datasets": {}, "matched_source_streams": {}, "evidence_count": 0},
                }
            },
        },
    )
    write_json(
        reports["workflow_source_audit"],
        {"passed": True, "summary": {"gharchive_sources": 1, "email_manifest_sources": 0}},
    )
    write_json(
        reports["public_data_discovery"],
        {"summary": {"gharchive_event_sources": 1, "email_manifest_sources": 0}},
    )
    write_json(
        reports["claim_boundary_audit"],
        {
            "passed": True,
            "summary": {
                "supported_claims": ["github_developer_workflow_release"],
                "blocked_claims": ["multi_domain_office_release", "reviewed_real_email_workflow_release"],
            },
        },
    )
    return reports
