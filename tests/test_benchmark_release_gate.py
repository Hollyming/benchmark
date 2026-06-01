from pathlib import Path

from ultra_long_benchmark.artifact_bundle import audit_artifact_bundle
from ultra_long_benchmark.artifact_bundle import verify_artifact_bundle_manifest
from ultra_long_benchmark.claim_boundary import audit_paper_claim_boundaries
from ultra_long_benchmark.claim_boundary import verify_paper_claim_boundary_audit
from ultra_long_benchmark.claim_lint import lint_paper_claims
from ultra_long_benchmark.domain_expansion import build_domain_expansion_readiness_report
from ultra_long_benchmark.benchmark_release_gate import build_benchmark_release_gate_report
from ultra_long_benchmark.pipelines.baseline_configs import validate_baseline_config_dir
from ultra_long_benchmark.pipelines.workflow_manifest_project import preflight_workflow_manifest_release
from ultra_long_benchmark.pipelines.workflow_manifest_project import preflight_workflow_manifest_release_batch
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.shared.io import read_json, write_json
from ultra_long_benchmark.shared.io import write_jsonl
from ultra_long_benchmark.taxonomy_coverage import audit_project_release_taxonomy_coverage
from tests.test_workflow_manifest_project import WORKFLOW_PROJECT_MANIFEST_FIXTURES
from tests.test_workflow_manifest_project import _write_calendar_project_manifest


def test_benchmark_release_gate_report_passes_with_expected_caveats(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    output = tmp_path / "gate.json"

    report = build_benchmark_release_gate_report(reports, output_path=output, root=tmp_path)

    assert report["passed"] is True
    assert report["summary"]["release_scope"] == "github_developer_workflow_only"
    assert report["summary"]["supported_claims"] == 6
    assert report["summary"]["blocked_claims"] == 5
    assert report["summary"]["issues"] == 0
    assert report["summary"]["reports_total"] == 9
    assert report["checks"]["readiness_report"]["status"] == "warn"
    assert read_json(output)["passed"] is True


def test_benchmark_release_gate_report_fails_missing_report(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    reports["readiness_report"] = tmp_path / "missing.json"

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is False
    assert "gate_report_missing" in report["summary"]["issue_codes"]
    assert report["checks"]["readiness_report"]["status"] == "fail"


def test_benchmark_release_gate_report_fails_unexpected_readiness_warning(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    readiness = read_json(Path(reports["readiness_report"]))
    readiness["summary"]["warning_checks"].append("unexpected_warning")
    write_json(Path(reports["readiness_report"]), readiness)

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is False
    assert "unexpected_readiness_warnings" in report["summary"]["issue_codes"]
    assert report["checks"]["readiness_report"]["status"] == "fail"


def test_benchmark_release_gate_report_fails_stale_taxonomy_release(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    taxonomy = read_json(reports["taxonomy_coverage_audit"])
    manifest_path = Path(taxonomy["release_dir"]) / "project_release_manifest.json"
    manifest = read_json(manifest_path)
    manifest["projects"] = []
    write_json(manifest_path, manifest)

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is False
    assert "taxonomy_coverage_verification_not_passed" in report["summary"]["issue_codes"]
    assert report["checks"]["taxonomy_coverage_audit"]["status"] == "fail"


def test_benchmark_release_gate_report_fails_stale_claim_boundary_input(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    taxonomy = read_json(reports["taxonomy_coverage_audit"])
    taxonomy["summary"]["covered_workflow_domains"] = []
    write_json(reports["taxonomy_coverage_audit"], taxonomy)

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is False
    assert "claim_boundary_live_verification_not_passed" in report["summary"]["issue_codes"]
    assert report["checks"]["claim_boundary_verification"]["status"] == "fail"


def test_benchmark_release_gate_report_fails_claim_verification_for_different_audit(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    verification = read_json(reports["claim_boundary_verification"])
    verification["report_path"] = str(tmp_path / "other_claim_boundary_audit.json")
    write_json(reports["claim_boundary_verification"], verification)

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is False
    assert "claim_boundary_verification_target_mismatch" in report["summary"]["issue_codes"]
    assert report["checks"]["claim_boundary_verification"]["status"] == "fail"


def test_benchmark_release_gate_report_fails_stale_domain_expansion_input(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    taxonomy = read_json(reports["taxonomy_coverage_audit"])
    taxonomy["summary"]["multi_domain_release_ready"] = True
    write_json(reports["taxonomy_coverage_audit"], taxonomy)

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is False
    assert "domain_expansion_verification_not_passed" in report["summary"]["issue_codes"]
    assert report["checks"]["domain_expansion_readiness"]["status"] == "fail"


def test_benchmark_release_gate_report_fails_stale_baseline_config_validation(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    baseline_validation = read_json(reports["baseline_config_validation"])
    config_path = Path(baseline_validation["configs"][0]["config_path"])
    config_path.write_text(config_path.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is False
    assert "baseline_config_verification_not_passed" in report["summary"]["issue_codes"]
    assert report["checks"]["baseline_config_validation"]["status"] == "fail"


def test_benchmark_release_gate_report_fails_stale_artifact_bundle_artifact(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    artifact = tmp_path / "bundle_artifact_00.json"
    payload = read_json(artifact)
    payload["changed"] = True
    write_json(artifact, payload)

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is False
    assert "artifact_bundle_manifest_live_verification_not_passed" in report["summary"]["issue_codes"]
    assert report["checks"]["artifact_bundle_manifest"]["status"] == "fail"
    assert "artifact_sha256_mismatch" in report["checks"]["artifact_bundle_manifest"]["verification_summary"]["issue_codes"]


def test_benchmark_release_gate_report_fails_artifact_verification_for_different_manifest(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    verification = read_json(reports["artifact_bundle_verification"])
    verification["manifest_path"] = str(tmp_path / "other_artifact_bundle_manifest.json")
    write_json(reports["artifact_bundle_verification"], verification)

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is False
    assert "artifact_bundle_verification_target_mismatch" in report["summary"]["issue_codes"]
    assert report["checks"]["artifact_bundle_verification"]["status"] == "fail"


def test_benchmark_release_gate_report_resolves_relative_overrides_from_root(tmp_path: Path):
    reports = _write_gate_reports(tmp_path / "generated")
    relative_reports = {name: path.relative_to(tmp_path) for name, path in reports.items()}

    report = build_benchmark_release_gate_report(relative_reports, root=tmp_path)

    assert report["passed"] is True
    assert report["summary"]["reports_present"] == 9
    assert Path(report["checks"]["readiness_report"]["path"]) == tmp_path / "generated" / "readiness.json"


def test_benchmark_release_gate_report_accepts_recorded_workflow_manifest_preflight(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    preflight_path = tmp_path / "preflight" / "workflow_manifest_release_preflight.json"
    preflight_workflow_manifest_release(
        manifest_path,
        tmp_path / "preflight",
        output_report_path=preflight_path,
    )
    build_domain_expansion_readiness_report(
        {
            "readiness_report": reports["readiness_report"],
            "taxonomy_coverage_audit": reports["taxonomy_coverage_audit"],
            "workflow_source_audit": tmp_path / "source_audit.json",
            "public_data_discovery": tmp_path / "discovery.json",
            "claim_boundary_audit": reports["claim_boundary_audit"],
        },
        output_path=reports["domain_expansion_readiness"],
        root=tmp_path,
        workflow_manifest_preflight_reports=[preflight_path],
    )
    reports["workflow_manifest_preflight_0"] = preflight_path

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is True
    assert report["summary"]["reports_total"] == 10
    assert report["summary"]["workflow_manifest_preflights"] == 1
    assert report["summary"]["workflow_manifest_preflight_domains"] == ["calendar_workflow"]
    check = report["checks"]["workflow_manifest_preflight_0"]
    assert check["status"] == "pass"
    assert check["constraints"]["llm_generation_performed"] is False
    assert check["constraints"]["release_ready_claim"] is False
    assert check["verification_summary"]["issues"] == 0


def test_benchmark_release_gate_report_accepts_multiple_recorded_workflow_manifest_preflights(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    preflight_paths = []
    for index, (fixture_path, domain, _release_scope, _project_id) in enumerate(WORKFLOW_PROJECT_MANIFEST_FIXTURES):
        preflight_path = tmp_path / "preflights" / domain / "workflow_manifest_release_preflight.json"
        preflight_workflow_manifest_release(
            fixture_path,
            tmp_path / "preflights" / domain,
            output_report_path=preflight_path,
            baseline_names=["oracle_policy_graph"],
        )
        preflight_paths.append(preflight_path)
        reports[f"workflow_manifest_preflight_{index}"] = preflight_path
    build_domain_expansion_readiness_report(
        {
            "readiness_report": reports["readiness_report"],
            "taxonomy_coverage_audit": reports["taxonomy_coverage_audit"],
            "workflow_source_audit": tmp_path / "source_audit.json",
            "public_data_discovery": tmp_path / "discovery.json",
            "claim_boundary_audit": reports["claim_boundary_audit"],
        },
        output_path=reports["domain_expansion_readiness"],
        root=tmp_path,
        workflow_manifest_preflight_reports=preflight_paths,
    )

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is True
    assert report["summary"]["release_scope"] == "github_developer_workflow_only"
    assert report["summary"]["reports_total"] == 13
    assert report["summary"]["workflow_manifest_preflights"] == 4
    assert report["summary"]["workflow_manifest_preflight_domains"] == [
        "browser_web_workflow",
        "calendar_workflow",
        "chat_workflow",
        "docs_workflow",
    ]
    assert all(report["checks"][f"workflow_manifest_preflight_{index}"]["status"] == "pass" for index in range(4))


def test_benchmark_release_gate_report_accepts_recorded_workflow_manifest_preflight_batch(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    batch_path = tmp_path / "preflight_batch" / "workflow_manifest_preflight_batch_report.json"
    preflight_workflow_manifest_release_batch(
        [fixture[0] for fixture in WORKFLOW_PROJECT_MANIFEST_FIXTURES],
        tmp_path / "preflight_batch",
        output_report_path=batch_path,
        baseline_names=["oracle_policy_graph"],
    )
    build_domain_expansion_readiness_report(
        {
            "readiness_report": reports["readiness_report"],
            "taxonomy_coverage_audit": reports["taxonomy_coverage_audit"],
            "workflow_source_audit": tmp_path / "source_audit.json",
            "public_data_discovery": tmp_path / "discovery.json",
            "claim_boundary_audit": reports["claim_boundary_audit"],
        },
        output_path=reports["domain_expansion_readiness"],
        root=tmp_path,
        workflow_manifest_preflight_batch_reports=[batch_path],
    )
    reports["workflow_manifest_preflight_batch_0"] = batch_path

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is True
    assert report["summary"]["release_scope"] == "github_developer_workflow_only"
    assert report["summary"]["reports_total"] == 14
    assert report["summary"]["workflow_manifest_preflights"] == 4
    assert report["checks"]["workflow_manifest_preflight_batch_0"]["status"] == "pass"
    assert report["checks"]["workflow_manifest_preflight_batch_0"]["verification_summary"]["reports_verified"] == 4
    assert report["checks"]["workflow_manifest_preflight_0"]["source_batch"] == "workflow_manifest_preflight_batch_0"


def test_benchmark_release_gate_report_fails_unrecorded_workflow_manifest_preflight(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    preflight_path = tmp_path / "preflight" / "workflow_manifest_release_preflight.json"
    preflight_workflow_manifest_release(
        manifest_path,
        tmp_path / "preflight",
        output_report_path=preflight_path,
    )
    reports["workflow_manifest_preflight_0"] = preflight_path

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is False
    assert "workflow_manifest_preflight_not_recorded_in_domain_expansion" in report["summary"]["issue_codes"]
    assert report["checks"]["workflow_manifest_preflight_0"]["status"] == "fail"


def test_benchmark_release_gate_report_fails_drifted_workflow_manifest_preflight(tmp_path: Path):
    reports = _write_gate_reports(tmp_path)
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    preflight_path = tmp_path / "preflight" / "workflow_manifest_release_preflight.json"
    preflight = preflight_workflow_manifest_release(
        manifest_path,
        tmp_path / "preflight",
        output_report_path=preflight_path,
    )
    build_domain_expansion_readiness_report(
        {
            "readiness_report": reports["readiness_report"],
            "taxonomy_coverage_audit": reports["taxonomy_coverage_audit"],
            "workflow_source_audit": tmp_path / "source_audit.json",
            "public_data_discovery": tmp_path / "discovery.json",
            "claim_boundary_audit": reports["claim_boundary_audit"],
        },
        output_path=reports["domain_expansion_readiness"],
        root=tmp_path,
        workflow_manifest_preflight_reports=[preflight_path],
    )
    project_profile = Path(preflight["artifacts"]["project_dir"]) / "project_profile.json"
    profile = read_json(project_profile)
    profile["title"] = profile["title"] + " drift"
    write_json(project_profile, profile)
    reports["workflow_manifest_preflight_0"] = preflight_path

    report = build_benchmark_release_gate_report(reports, root=tmp_path)

    assert report["passed"] is False
    assert "workflow_manifest_preflight_verification_not_passed" in report["summary"]["issue_codes"]
    assert report["checks"]["workflow_manifest_preflight_0"]["status"] == "fail"


def _write_gate_reports(tmp_path: Path) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    reports = {
        "readiness_report": tmp_path / "readiness.json",
        "claim_boundary_audit": tmp_path / "claim.json",
        "claim_boundary_verification": tmp_path / "claim_verify.json",
        "claim_lint": tmp_path / "claim_lint.json",
        "artifact_bundle_manifest": tmp_path / "bundle.json",
        "artifact_bundle_verification": tmp_path / "bundle_verify.json",
        "taxonomy_coverage_audit": tmp_path / "taxonomy.json",
        "domain_expansion_readiness": tmp_path / "domain_expansion.json",
        "baseline_config_validation": tmp_path / "baseline_config.json",
    }
    write_json(
        reports["readiness_report"],
        {
            "passed": True,
            "summary": {
                "checks_total": 23,
                "failed": 0,
                "warning_checks": [
                    "rewrite_human_audit",
                    "taxonomy_coverage_audit",
                    "claim_boundary_audit",
                    "artifact_bundle_manifest",
                ],
            },
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
    claim_lint_docs = []
    for index in range(4):
        doc = tmp_path / f"claim_lint_doc_{index}.md"
        doc.write_text("The current release is a GitHub developer workflow release.\n", encoding="utf-8")
        claim_lint_docs.append(doc)
    lint_paper_claims(claim_lint_docs, output_path=reports["claim_lint"], root=tmp_path)
    _write_gate_taxonomy_audit(tmp_path, reports["taxonomy_coverage_audit"])
    source = tmp_path / "source_audit.json"
    write_json(
        source,
        {
            "passed": True,
            "annotation_budget_ready": True,
            "paper_ready": True,
            "summary": {"gharchive_sources": 1, "email_manifest_sources": 0},
        },
    )
    leakage = tmp_path / "hardened_probe_leakage.json"
    write_json(leakage, {"summary": {"high_any_overlap_probes": 0, "missing_gold_keys": 0}})
    baseline_batch = tmp_path / "baseline_batch.json"
    write_json(
        baseline_batch,
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
    external_runner = tmp_path / "external_runner.json"
    write_json(
        external_runner,
        {
            "status": "completed",
            "executed": True,
            "summary": {"probes": 168, "predictions": 168, "output_validation_passed": True},
        },
    )
    audit_paper_claim_boundaries(
        output_path=reports["claim_boundary_audit"],
        readiness_report_path=reports["readiness_report"],
        taxonomy_coverage_path=reports["taxonomy_coverage_audit"],
        workflow_source_audit_path=source,
        hardened_probe_leakage_audit_path=leakage,
        baseline_batch_report_path=baseline_batch,
        external_runner_report_path=external_runner,
    )
    verify_paper_claim_boundary_audit(
        reports["claim_boundary_audit"],
        output_path=reports["claim_boundary_verification"],
    )
    _write_gate_artifact_bundle(tmp_path, reports["artifact_bundle_manifest"], reports["artifact_bundle_verification"])
    _write_gate_baseline_config_validation(tmp_path / "baseline_configs", reports["baseline_config_validation"])
    discovery = tmp_path / "discovery.json"
    write_json(discovery, {"summary": {"gharchive_event_sources": 1, "email_manifest_sources": 0}})
    build_domain_expansion_readiness_report(
        {
            "readiness_report": reports["readiness_report"],
            "taxonomy_coverage_audit": reports["taxonomy_coverage_audit"],
            "workflow_source_audit": source,
            "public_data_discovery": discovery,
            "claim_boundary_audit": reports["claim_boundary_audit"],
        },
        output_path=reports["domain_expansion_readiness"],
        root=tmp_path,
    )
    return reports


def _write_gate_taxonomy_audit(tmp_path: Path, output_path: Path) -> None:
    project_dir = tmp_path / "taxonomy_project"
    project_id = "project_gate_taxonomy"
    project_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        project_dir / "project_profile.json",
        {
            "project_id": project_id,
            "title": "Gate taxonomy fixture",
            "project_goal": "Exercise taxonomy coverage in the paper gate.",
            "source_streams": ["gharchive", "synthetic_bridge"],
            "synthetic_context": False,
        },
    )
    write_json(project_dir / "source_manifest.json", {"source_streams": ["gharchive", "synthetic_bridge"]})
    write_jsonl(
        project_dir / "events.jsonl",
        [
            {
                "event_id": "evt_1",
                "project_id": project_id,
                "timestamp": "2026-01-01T00:00:00Z",
                "event_type": "pull_request_opened",
                "source_dataset": "gharchive",
                "actor": "alice",
                "content": "Opened a pull request.",
                "artifacts": ["artifact_1"],
                "raw_pointer": "gharchive://evt_1",
                "metadata": {"github_event_type": "PullRequestEvent"},
            },
            {
                "event_id": "evt_2",
                "project_id": project_id,
                "timestamp": "2026-01-02T00:00:00Z",
                "event_type": "review_comment",
                "source_dataset": "gharchive",
                "actor": "bob",
                "content": "Asked for review before merge.",
                "artifacts": ["artifact_2"],
                "raw_pointer": "gharchive://evt_2",
                "metadata": {"github_event_type": "IssueCommentEvent"},
            },
            {
                "event_id": "evt_3",
                "project_id": project_id,
                "timestamp": "2026-01-03T00:00:00Z",
                "event_type": "negative_evidence",
                "source_dataset": "gharchive",
                "actor": "alice",
                "content": "Do not merge without review.",
                "artifacts": ["artifact_3"],
                "raw_pointer": "gharchive://evt_3",
                "metadata": {"github_event_type": "PullRequestReviewEvent"},
            },
        ],
    )
    write_jsonl(
        project_dir / "artifacts.jsonl",
        [
            {
                "artifact_id": "artifact_1",
                "artifact_type": "pull_request",
                "source_dataset": "gharchive",
                "raw_pointer": "gharchive://evt_1",
            },
            {
                "artifact_id": "artifact_2",
                "artifact_type": "issue_comment",
                "source_dataset": "gharchive",
                "raw_pointer": "gharchive://evt_2",
            },
            {
                "artifact_id": "artifact_3",
                "artifact_type": "pull_request_review",
                "source_dataset": "gharchive",
                "raw_pointer": "gharchive://evt_3",
            },
        ],
    )
    write_json(
        project_dir / "memory_graph.json",
        {
            "project_id": project_id,
            "memories": [
                {
                    "memory_id": "mem_1",
                    "project_id": project_id,
                    "memory_type": "user_policy",
                    "content": "Prefer comments before merging.",
                    "source_events": ["evt_1"],
                    "future_utility": {"score": 0.8, "expected_tasks": ["future_pr_review"]},
                    "action_boundary": {"allowed_actions": ["comment"], "forbidden_actions": ["merge"]},
                },
                {
                    "memory_id": "mem_2",
                    "project_id": project_id,
                    "memory_type": "contextual_policy",
                    "content": "When review is requested, comment with the requested review context.",
                    "source_events": ["evt_2"],
                    "future_utility": {"score": 0.7, "expected_tasks": ["future_review_comment"]},
                    "action_boundary": {"allowed_actions": ["comment"]},
                },
                {
                    "memory_id": "mem_3",
                    "project_id": project_id,
                    "memory_type": "negative_policy_example",
                    "content": "Do not merge without review.",
                    "source_events": ["evt_3"],
                    "negative_evidence": ["evt_3"],
                    "action_boundary": {"forbidden_actions": ["merge"]},
                },
                {
                    "memory_id": "mem_4",
                    "project_id": project_id,
                    "memory_type": "distractor",
                    "content": "Unrelated repository activity.",
                    "source_events": ["evt_2"],
                    "status": "distractor",
                },
            ]
        },
    )
    write_jsonl(
        project_dir / "probes.jsonl",
        [
            {
                "probe_id": "probe_1",
                "project_id": project_id,
                "trajectory_id": "trajectory_1",
                "task_type": "tool_action_policy_alignment",
                "capabilities": ["tool_action_alignment"],
                "difficulty": "easy",
                "query": "What should the assistant do?",
                "expected_behavior": {"allowed_action": "comment", "forbidden_action": "merge"},
                "evidence": {"positive": ["mem_1"], "negative": ["mem_3"], "distractor": ["mem_4"]},
                "evaluation": {"answer_type": "free_text", "metrics": ["evidence_recall"]},
            },
            {
                "probe_id": "probe_2",
                "project_id": project_id,
                "trajectory_id": "trajectory_2",
                "task_type": "contextual_workflow_policy_selection",
                "capabilities": ["contextual_policy_selection"],
                "difficulty": "easy",
                "query": "Which workflow policy applies when review is requested?",
                "expected_behavior": {"allowed_action": "comment"},
                "evidence": {"positive": ["mem_2"], "negative": ["mem_3"], "distractor": ["mem_4"]},
                "evaluation": {"answer_type": "free_text", "metrics": ["evidence_recall"]},
            },
            {
                "probe_id": "probe_3",
                "project_id": project_id,
                "trajectory_id": "trajectory_3",
                "task_type": "negative_example_storage_gating",
                "capabilities": ["habit_storage_gating"],
                "difficulty": "easy",
                "query": "Should the assistant store merging without review as an allowed habit?",
                "expected_behavior": {"forbidden_action": "merge"},
                "evidence": {"positive": ["mem_3"], "negative": ["mem_3"], "distractor": ["mem_4"]},
                "evaluation": {"answer_type": "free_text", "metrics": ["evidence_recall"]},
            },
        ],
    )
    release_dir = tmp_path / "taxonomy_release"
    export_project_benchmark_release([project_dir], release_dir, version="test")
    audit_project_release_taxonomy_coverage(release_dir, output_path=output_path)


def _write_gate_artifact_bundle(tmp_path: Path, manifest_path: Path, verification_path: Path) -> None:
    artifacts: dict[str, Path] = {}
    for index in range(20):
        artifact = tmp_path / f"bundle_artifact_{index:02d}.json"
        write_json(artifact, {"passed": True, "summary": {"failed": 0}, "index": index})
        artifacts[f"artifact_{index:02d}"] = artifact
    write_json(
        artifacts["artifact_00"],
        {
            "passed": True,
            "summary": {
                "current_release_domain_scope": "github_developer_workflow_only",
                "failed": 0,
            },
        },
    )
    write_json(
        artifacts["artifact_01"],
        {
            "passed": True,
            "summary": {
                "blocked": 1,
                "supported": 6,
                "qualified": 0,
            },
        },
    )
    audit_artifact_bundle(
        {
            "taxonomy_coverage_audit": artifacts["artifact_00"],
            "claim_boundary_audit": artifacts["artifact_01"],
            **artifacts,
        },
        output_path=manifest_path,
        root=tmp_path,
    )
    verify_artifact_bundle_manifest(manifest_path, output_path=verification_path)


def _write_gate_baseline_config_validation(config_dir: Path, output_path: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    for index in range(6):
        _write_minimal_baseline_config(config_dir / f"baseline_{index:02d}.yaml", f"baseline_{index:02d}")
    validate_baseline_config_dir(config_dir, output_path=output_path)


def _write_minimal_baseline_config(path: Path, name: str) -> None:
    path.write_text(
        f"""
baseline:
  name: {name}
  family: retrieval
  entrypoint: ultra_long_benchmark.cli:evaluate-project
  requires_llm_api: false
  requires_gpu: false
  memory_backend: none
data:
  project_dir: examples/generated/projects/project_gharchive_001
  output_path: examples/generated/evaluation_harness/{name}.json
evaluation:
  mode: project_probe_text
  metrics: [evidence_recall]
resources:
  partition: cpu
  gpus: 0
  cpus_per_task: 1
  mem: 4G
  time: "00:05:00"
reproducibility:
  seed: 0
""",
        encoding="utf-8",
    )
