from pathlib import Path

from ultra_long_benchmark.artifact_bundle import audit_artifact_bundle
from ultra_long_benchmark.artifact_bundle import verify_artifact_bundle_manifest
from ultra_long_benchmark.claim_lint import lint_paper_claims
from ultra_long_benchmark.data_discovery import discover_public_data_sources
from ultra_long_benchmark.pipelines.baseline_configs import run_baseline_config_dir
from ultra_long_benchmark.pipelines.baseline_configs import validate_baseline_config_dir
from ultra_long_benchmark.pipelines.baseline_configs import verify_baseline_batch_report
from ultra_long_benchmark.shared.io import read_json, write_json, write_jsonl
from tests.test_baseline_configs import ROOT
from tests.test_baseline_configs import _copy_config_with_data
from tests.test_baseline_configs import _single_executable_config_dir


def test_artifact_bundle_manifest_records_hashes_and_gate_summaries(tmp_path: Path):
    readiness = tmp_path / "readiness.json"
    claim = tmp_path / "claim.json"
    taxonomy = tmp_path / "taxonomy.json"
    claim_lint = tmp_path / "claim_lint.json"
    baseline = tmp_path / "baseline.json"
    runner = tmp_path / "runner.json"
    runner_validation = tmp_path / "runner_validation.json"
    runner_submission_validation = tmp_path / "runner_submission_validation.json"
    table_dir = tmp_path / "tables"
    table_dir.mkdir()
    (table_dir / "main_results.csv").write_text("system,score\nx,0\n", encoding="utf-8")
    write_json(readiness, {"passed": True, "summary": {"failed": 0, "warnings": 1}})
    write_json(claim, {"passed": True, "summary": {"blocked": 1, "supported": 2, "qualified": 0}})
    write_json(
        taxonomy,
        {
            "passed": True,
            "summary": {
                "current_release_domain_scope": "github_developer_workflow_only",
                "warnings": 1,
            },
        },
    )
    write_json(baseline, {"passed": True, "summary": {"failed": 0, "blocked": 0, "completed": 2}})
    claim_doc = tmp_path / "claim_doc.md"
    claim_doc.write_text("The current release is a GitHub developer workflow release.\n", encoding="utf-8")
    lint_paper_claims([claim_doc], output_path=claim_lint, root=tmp_path)
    write_json(
        runner,
        {
            "status": "completed",
            "executed": True,
            "summary": {"probes": 3, "predictions": 3, "output_validation_passed": True},
        },
    )
    write_json(runner_validation, {"passed": True, "summary": {"probe_coverage": 1.0}})
    write_json(runner_submission_validation, {"passed": True, "summary": {"issues": 0}})

    output = tmp_path / "bundle.json"
    report = audit_artifact_bundle(
        {
            "readiness_report": readiness,
            "claim_boundary_audit": claim,
            "claim_lint": claim_lint,
            "taxonomy_coverage_audit": taxonomy,
            "baseline_batch_report": baseline,
            "external_runner_report": runner,
            "external_runner_validation": runner_validation,
            "external_runner_submission_validation": runner_submission_validation,
            "paper_table_dir": table_dir,
        },
        output_path=output,
    )

    assert report["passed"] is True
    assert report["summary"]["artifacts_present"] == 9
    assert report["artifacts"]["paper_table_dir"]["kind"] == "directory"
    assert len(report["artifacts"]["readiness_report"]["sha256"]) == 64
    assert "claim_boundary_has_blocked_claims" in report["summary"]["warning_codes"]
    assert "github_only_release_scope" in report["summary"]["warning_codes"]
    assert read_json(output)["summary"]["artifacts_total"] == 9


def test_artifact_bundle_fails_on_missing_or_failed_required_artifact(tmp_path: Path):
    readiness = tmp_path / "readiness.json"
    write_json(readiness, {"passed": False, "summary": {"failed": 1}})

    report = audit_artifact_bundle(
        {
            "readiness_report": readiness,
            "claim_boundary_audit": tmp_path / "missing_claim.json",
        }
    )

    assert report["passed"] is False
    assert "artifact_missing" in report["summary"]["issue_codes"]
    assert "readiness_not_passed" in report["summary"]["issue_codes"]


def test_verify_artifact_bundle_manifest_passes_for_unchanged_artifacts(tmp_path: Path):
    artifact = tmp_path / "artifact.json"
    write_json(artifact, {"passed": True, "summary": {"failed": 0}})
    manifest = tmp_path / "bundle.json"
    audit_artifact_bundle({"readiness_report": artifact}, output_path=manifest, root=tmp_path)

    report = verify_artifact_bundle_manifest(manifest)

    assert report["passed"] is True
    assert report["summary"]["artifacts_verified"] == 1
    assert report["artifacts"]["readiness_report"]["passed"] is True


def test_verify_artifact_bundle_manifest_fails_when_artifact_changes(tmp_path: Path):
    artifact = tmp_path / "artifact.json"
    write_json(artifact, {"passed": True, "summary": {"failed": 0}})
    manifest = tmp_path / "bundle.json"
    audit_artifact_bundle({"readiness_report": artifact}, output_path=manifest, root=tmp_path)
    write_json(artifact, {"passed": True, "summary": {"failed": 0}, "changed": True})

    report = verify_artifact_bundle_manifest(manifest)

    assert report["passed"] is False
    assert "artifact_sha256_mismatch" in report["summary"]["issue_codes"]
    assert report["artifacts"]["readiness_report"]["passed"] is False


def test_verify_artifact_bundle_manifest_fails_when_artifact_records_missing(tmp_path: Path):
    manifest = tmp_path / "bundle.json"
    write_json(manifest, {"passed": True, "summary": {"issues": 0}, "artifacts": {}})

    report = verify_artifact_bundle_manifest(manifest)

    assert report["passed"] is False
    assert "manifest_artifacts_missing" in report["summary"]["issue_codes"]


def test_verify_artifact_bundle_manifest_fails_when_claim_lint_source_changes(tmp_path: Path):
    claim_doc = tmp_path / "claim_doc.md"
    claim_doc.write_text("The current release is a GitHub developer workflow release.\n", encoding="utf-8")
    claim_lint = tmp_path / "claim_lint.json"
    lint_paper_claims([claim_doc], output_path=claim_lint, root=tmp_path)
    manifest = tmp_path / "bundle.json"
    audit_artifact_bundle({"claim_lint": claim_lint}, output_path=manifest, root=tmp_path)
    claim_doc.write_text("The current release covers email/calendar/docs/chat/browser workflows.\n", encoding="utf-8")

    report = verify_artifact_bundle_manifest(manifest)

    assert report["passed"] is False
    assert "claim_lint_verification_not_passed" in report["summary"]["issue_codes"]
    assert report["artifacts"]["claim_lint"]["passed"] is False


def test_verify_artifact_bundle_manifest_fails_when_baseline_batch_output_changes(tmp_path: Path):
    config_dir = _single_executable_config_dir(tmp_path)
    batch_dir = tmp_path / "batch_reports"
    batch = run_baseline_config_dir(config_dir, batch_dir)
    manifest = tmp_path / "bundle.json"
    audit_artifact_bundle({"baseline_batch_report": batch_dir / "baseline_batch_report.json"}, output_path=manifest, root=tmp_path)
    output_path = Path(batch["reports"][0]["output_path"])
    output = read_json(output_path)
    output["changed_after_batch"] = True
    write_json(output_path, output)

    report = verify_artifact_bundle_manifest(manifest)

    assert report["passed"] is False
    assert "baseline_batch_verification_not_passed" in report["summary"]["issue_codes"]
    assert report["artifacts"]["baseline_batch_report"]["passed"] is False


def test_artifact_bundle_records_baseline_batch_verification_artifact(tmp_path: Path):
    config_dir = _single_executable_config_dir(tmp_path)
    batch_dir = tmp_path / "batch_reports"
    run_baseline_config_dir(config_dir, batch_dir)
    verification_path = batch_dir / "baseline_batch_verification.json"
    verify_baseline_batch_report(batch_dir / "baseline_batch_report.json", output_path=verification_path)

    manifest = tmp_path / "bundle.json"
    audit = audit_artifact_bundle(
        {
            "baseline_batch_report": batch_dir / "baseline_batch_report.json",
            "baseline_batch_verification": verification_path,
        },
        output_path=manifest,
        root=tmp_path,
    )
    report = verify_artifact_bundle_manifest(manifest)

    assert audit["passed"] is True
    assert audit["artifacts"]["baseline_batch_verification"]["status"] == "present"
    assert report["passed"] is True
    assert report["artifacts"]["baseline_batch_verification"]["passed"] is True
    assert report["artifacts"]["baseline_batch_verification"]["baseline_batch_verification_summary"]["reports_total"] == 1


def test_artifact_bundle_fails_when_baseline_batch_verification_targets_other_report(tmp_path: Path):
    config_dir = _single_executable_config_dir(tmp_path)
    batch_dir = tmp_path / "batch_reports"
    run_baseline_config_dir(config_dir, batch_dir)
    verification_path = batch_dir / "baseline_batch_verification.json"
    verify_baseline_batch_report(batch_dir / "baseline_batch_report.json", output_path=verification_path)
    verification = read_json(verification_path)
    verification["report_path"] = str(tmp_path / "other_baseline_batch_report.json")
    write_json(verification_path, verification)
    manifest = tmp_path / "bundle.json"
    audit = audit_artifact_bundle(
        {
            "baseline_batch_report": batch_dir / "baseline_batch_report.json",
            "baseline_batch_verification": verification_path,
        },
        output_path=manifest,
        root=tmp_path,
    )

    report = verify_artifact_bundle_manifest(manifest)

    assert audit["passed"] is False
    assert report["passed"] is False
    assert "baseline_batch_verification_target_mismatch" in report["summary"]["issue_codes"]
    assert report["artifacts"]["baseline_batch_verification"]["passed"] is False


def test_artifact_bundle_verifies_baseline_config_validation_inputs(tmp_path: Path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    _copy_config_with_data(
        ROOT / "configs" / "baselines" / "mem0_submission_placeholder.yaml",
        config_dir / "mem0_submission_placeholder.yaml",
        {
            "project_dir": str(tmp_path / "missing_project_ok_for_non_strict_validation"),
            "submission_input_dir": str(tmp_path / "missing_submission_input_ok_for_non_strict_validation"),
            "predictions_path": str(tmp_path / "mem0_predictions.jsonl"),
            "output_path": str(tmp_path / "mem0_report.json"),
        },
    )
    validation_path = tmp_path / "baseline_config_validation.json"
    validate_baseline_config_dir(config_dir, output_path=validation_path)
    manifest = tmp_path / "bundle.json"
    audit_artifact_bundle({"baseline_config_validation": validation_path}, output_path=manifest, root=tmp_path)
    config_path = config_dir / "mem0_submission_placeholder.yaml"
    config_path.write_text(config_path.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")

    report = verify_artifact_bundle_manifest(manifest)

    assert report["passed"] is False
    assert "baseline_config_verification_not_passed" in report["summary"]["issue_codes"]
    assert report["artifacts"]["baseline_config_validation"]["passed"] is False


def test_artifact_bundle_verifies_public_data_discovery_inputs(tmp_path: Path):
    data_root = tmp_path / "data"
    gharchive_path = data_root / "gharchive" / "2026-04-01.jsonl"
    write_jsonl(
        gharchive_path,
        [
            {
                "id": "evt_1",
                "type": "PullRequestEvent",
                "actor": {"login": "alice"},
                "repo": {"name": "acme/docs"},
                "payload": {"action": "opened", "pull_request": {"title": "Docs update"}},
                "created_at": "2026-04-01T00:00:00Z",
            }
        ],
    )
    discovery_path = tmp_path / "public_data_discovery.json"
    discover_public_data_sources([data_root], output_path=discovery_path)
    manifest = tmp_path / "bundle.json"
    audit_artifact_bundle({"public_data_discovery": discovery_path}, output_path=manifest, root=tmp_path)
    write_jsonl(
        gharchive_path,
        [
            {
                "id": "evt_1_changed",
                "type": "PullRequestEvent",
                "actor": {"login": "alice"},
                "repo": {"name": "acme/docs"},
                "payload": {"action": "opened", "pull_request": {"title": "Changed docs update"}},
                "created_at": "2026-04-01T00:00:00Z",
            }
        ],
    )

    report = verify_artifact_bundle_manifest(manifest)

    assert report["passed"] is False
    assert "public_data_discovery_verification_not_passed" in report["summary"]["issue_codes"]
    assert report["artifacts"]["public_data_discovery"]["passed"] is False


def test_artifact_bundle_flags_invalid_gharchive_source_reports(tmp_path: Path):
    public_data = tmp_path / "public_data.json"
    stage_plan = tmp_path / "stage_plan.json"
    window_report = tmp_path / "window_report.json"
    scale_summary = tmp_path / "scale_summary.json"
    write_json(public_data, {"summary": {"usable_sources": 0}})
    write_json(stage_plan, {"summary": {"passed": False}})
    write_json(window_report, {"summary": {"eligible_windows": 0}})
    write_json(
        scale_summary,
        {
            "tasks": {"total": 0},
            "repos": {"eligible_packs": 0},
            "release": {"pack_hashes_present": False},
        },
    )

    report = audit_artifact_bundle(
        {
            "public_data_discovery": public_data,
            "gharchive_stage_plan": stage_plan,
            "gharchive_window_report": window_report,
            "gharchive_scale_summary": scale_summary,
        },
        root=tmp_path,
    )

    assert report["passed"] is False
    assert "public_data_discovery_no_usable_sources" in report["summary"]["issue_codes"]
    assert "gharchive_stage_plan_not_passed" in report["summary"]["issue_codes"]
    assert "gharchive_window_report_no_eligible_windows" in report["summary"]["issue_codes"]
    assert "gharchive_scale_summary_no_tasks" in report["summary"]["issue_codes"]
    assert "gharchive_scale_summary_no_eligible_packs" in report["summary"]["issue_codes"]
    assert "gharchive_scale_summary_missing_pack_hashes" in report["summary"]["issue_codes"]
