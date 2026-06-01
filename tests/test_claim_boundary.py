from pathlib import Path

from ultra_long_benchmark.claim_boundary import audit_paper_claim_boundaries
from ultra_long_benchmark.claim_boundary import verify_paper_claim_boundary_audit
from ultra_long_benchmark.shared.io import read_json, write_json


def test_paper_claim_boundary_audit_blocks_overclaims(tmp_path: Path):
    taxonomy_path = tmp_path / "taxonomy.json"
    source_path = tmp_path / "source.json"
    leakage_path = tmp_path / "leakage.json"
    readiness_path = tmp_path / "readiness.json"
    baseline_path = tmp_path / "baseline_batch.json"
    output_path = tmp_path / "claim_boundary.json"
    write_json(
        taxonomy_path,
        {
            "summary": {
                "current_release_domain_scope": "github_developer_workflow_only",
                "covered_workflow_domains": ["github_developer_workflow"],
                "multi_domain_release_ready": False,
            },
            "checks": {
                "core_task_taxonomy": {
                    "short_name": "longitudinal_user_policy_habit_induction",
                    "name": "Longitudinal User Policy / Habit Induction for Tool-Using Agents",
                },
                "workflow_domain_coverage": {
                    "github_developer_workflow": {"status": "covered"},
                    "email_workflow": {"status": "blocked_license_privacy_manifest"},
                },
            },
        },
    )
    write_json(
        source_path,
        {
            "annotation_budget_ready": True,
            "paper_ready": True,
            "summary": {"gharchive_sources": 1, "email_manifest_sources": 0},
        },
    )
    write_json(leakage_path, {"summary": {"high_any_overlap_probes": 0, "missing_gold_keys": 0}})
    write_json(
        readiness_path,
        {
            "summary": {"failed": 0},
            "checks": {
                "project_submission_inputs": {"status": "pass"},
                "rewrite_human_audit": {"status": "warn"},
            },
        },
    )
    write_json(
        baseline_path,
        {
            "reports": [
                {"baseline_name": "memory_submission_event_profile_stub", "status": "completed"},
                {"baseline_name": "memory_submission_event_profile_stub_hardened", "status": "completed"},
                {"baseline_name": "external_memory_runner_echo_contract", "status": "dry_run_ok"},
                {"baseline_name": "mem0_submission_placeholder", "status": "dry_run_requires_llm_api"},
                {"baseline_name": "a_mem_submission_placeholder", "status": "dry_run_requires_llm_api"},
                {"baseline_name": "graphiti_submission_placeholder", "status": "dry_run_requires_llm_api"},
            ]
        },
    )

    report = audit_paper_claim_boundaries(
        output_path=output_path,
        readiness_report_path=readiness_path,
        taxonomy_coverage_path=taxonomy_path,
        workflow_source_audit_path=source_path,
        hardened_probe_leakage_audit_path=leakage_path,
        baseline_batch_report_path=baseline_path,
    )

    assert report["claims"]["core_task_taxonomy"]["status"] == "supported"
    assert report["inputs"]["taxonomy_coverage_path"]["sha256"]
    assert report["inputs"]["baseline_batch_report_path"]["status"] == "present"
    assert report["claims"]["github_developer_workflow_release"]["status"] == "supported"
    assert report["claims"]["source_grounded_gharchive"]["status"] == "supported"
    assert report["claims"]["no_gold_hardened_submission_input"]["status"] == "supported"
    assert report["claims"]["memory_submission_contract_ready"]["status"] == "supported"
    assert report["claims"]["external_memory_runner_contract_ready"]["status"] == "qualified"
    assert report["claims"]["multi_domain_office_release"]["status"] == "blocked"
    assert report["claims"]["reviewed_real_email_workflow_release"]["status"] == "blocked"
    assert report["claims"]["human_audited_rewrite_quality"]["status"] == "blocked"
    assert report["claims"]["executed_sota_memory_baselines"]["status"] == "blocked"
    assert report["claims"]["original_query_scores_as_sota"]["status"] == "blocked"
    assert "Add at least one non-GitHub real workflow domain with reusable traces." in report["claims"]["multi_domain_office_release"]["unlock_requirements"]
    assert "Document redistribution license, privacy review, and PII redaction policy." in report["claims"]["reviewed_real_email_workflow_release"]["unlock_requirements"]
    assert "Do not describe the current release as a multi-domain email/calendar/docs/chat/browser/web-search workflow benchmark." in report["recommended_language"]["blocked"]
    assert read_json(output_path)["summary"]["blocked"] == 5


def test_paper_claim_boundary_supports_executed_external_runner_contract(tmp_path: Path):
    baseline_path = tmp_path / "baseline_batch.json"
    runner_path = tmp_path / "external_runner.json"
    write_json(
        baseline_path,
        {
            "reports": [
                {"baseline_name": "external_memory_runner_echo_contract", "status": "dry_run_ok"},
                {"baseline_name": "mem0_submission_placeholder", "status": "dry_run_requires_llm_api"},
                {"baseline_name": "a_mem_submission_placeholder", "status": "dry_run_requires_llm_api"},
                {"baseline_name": "graphiti_submission_placeholder", "status": "dry_run_requires_llm_api"},
            ]
        },
    )
    write_json(
        runner_path,
        {
            "status": "completed",
            "executed": True,
            "summary": {
                "probes": 168,
                "predictions": 168,
                "output_validation_passed": True,
            },
        },
    )

    report = audit_paper_claim_boundaries(
        baseline_batch_report_path=baseline_path,
        external_runner_report_path=runner_path,
    )

    claim = report["claims"]["external_memory_runner_contract_ready"]
    assert claim["status"] == "supported"
    assert "runner_status=completed" in claim["evidence"]
    assert "runner_predictions=168" in claim["evidence"]
    assert "external_memory_runner_contract_ready" in report["summary"]["supported_claims"]
    assert "Say that the external memory runner plugin contract executes end-to-end on hardened no-gold inputs." in report["recommended_language"]["supported"]


def test_paper_claim_boundary_marks_missing_evidence_as_qualified_or_blocked(tmp_path: Path):
    report = audit_paper_claim_boundaries(output_path=tmp_path / "claim_boundary.json")

    assert report["claims"]["core_task_taxonomy"]["status"] == "qualified"
    assert report["claims"]["source_grounded_gharchive"]["status"] == "qualified"
    assert report["claims"]["multi_domain_office_release"]["status"] == "blocked"
    assert report["claims"]["executed_sota_memory_baselines"]["status"] == "blocked"
    assert report["summary"]["blocked"] >= 1


def test_verify_paper_claim_boundary_audit_passes_when_inputs_are_unchanged(tmp_path: Path):
    taxonomy_path = tmp_path / "taxonomy.json"
    output_path = tmp_path / "claim_boundary.json"
    write_json(
        taxonomy_path,
        {
            "summary": {
                "current_release_domain_scope": "github_developer_workflow_only",
                "covered_workflow_domains": ["github_developer_workflow"],
                "multi_domain_release_ready": False,
            },
            "checks": {
                "core_task_taxonomy": {
                    "short_name": "longitudinal_user_policy_habit_induction",
                    "name": "Longitudinal User Policy / Habit Induction for Tool-Using Agents",
                }
            },
        },
    )
    audit_paper_claim_boundaries(output_path=output_path, taxonomy_coverage_path=taxonomy_path)

    report = verify_paper_claim_boundary_audit(output_path)

    assert report["passed"] is True
    assert report["summary"]["issues"] == 0
    assert report["summary"]["original_supported"] == report["summary"]["recomputed_supported"]
    assert report["summary"]["original_blocked"] == report["summary"]["recomputed_blocked"]


def test_verify_paper_claim_boundary_audit_fails_when_inputs_drift(tmp_path: Path):
    taxonomy_path = tmp_path / "taxonomy.json"
    output_path = tmp_path / "claim_boundary.json"
    write_json(
        taxonomy_path,
        {
            "summary": {
                "current_release_domain_scope": "github_developer_workflow_only",
                "covered_workflow_domains": ["github_developer_workflow"],
                "multi_domain_release_ready": False,
            },
            "checks": {
                "core_task_taxonomy": {
                    "short_name": "longitudinal_user_policy_habit_induction",
                    "name": "Longitudinal User Policy / Habit Induction for Tool-Using Agents",
                }
            },
        },
    )
    audit_paper_claim_boundaries(output_path=output_path, taxonomy_coverage_path=taxonomy_path)
    write_json(taxonomy_path, {"summary": {}, "checks": {"core_task_taxonomy": {"short_name": "unexpected"}}})

    report = verify_paper_claim_boundary_audit(output_path)

    assert report["passed"] is False
    assert "claim_boundary_summary_mismatch" in report["summary"]["issue_codes"]
    assert "claim_boundary_claims_mismatch" in report["summary"]["issue_codes"]
    assert "claim_boundary_input_sha256_mismatch" in report["summary"]["issue_codes"]
