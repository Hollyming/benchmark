from pathlib import Path

from ultra_long_benchmark.pipelines.annotation_pack import build_project_from_policy_rewrites
from ultra_long_benchmark.pipelines.annotation_pack import build_projects_from_policy_rewrite_batch
from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack
from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack_batch
from ultra_long_benchmark.pipelines.annotation_pack import collect_policy_rewrite_job_outputs
from ultra_long_benchmark.pipelines.annotation_pack import export_annotation_pack_release
from ultra_long_benchmark.pipelines.annotation_pack import export_policy_rewrite_prompts
from ultra_long_benchmark.pipelines.annotation_pack import export_policy_rewrite_prompts_batch
from ultra_long_benchmark.pipelines.annotation_pack import package_policy_rewrite_jobs
from ultra_long_benchmark.pipelines.annotation_pack import summarize_gharchive_annotation_scale
from ultra_long_benchmark.pipelines.annotation_pack import validate_policy_rewrite_proposals
from ultra_long_benchmark.pipelines.annotation_pack import validate_policy_rewrite_proposals_batch
from ultra_long_benchmark.pipelines.rewrite_audit import export_policy_rewrite_human_audit_pack
from ultra_long_benchmark.pipelines.rewrite_audit import validate_policy_rewrite_human_audit
from ultra_long_benchmark.pipelines.gharchive import DEFAULT_FIXTURE_PATH as DEFAULT_GHARCHIVE_FIXTURE_PATH
from ultra_long_benchmark.pipelines.verifier import run_project_verifier
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_jsonl


def test_gharchive_annotation_pack_is_source_grounded(tmp_path: Path):
    output_dir = tmp_path / "annotation_pack"
    pack = build_gharchive_annotation_pack(
        DEFAULT_GHARCHIVE_FIXTURE_PATH,
        repo="acme/docs",
        output_dir=output_dir,
        pack_id="test_pack",
    )

    assert pack["pack_id"] == "test_pack"
    assert pack["summary"]["tasks_total"] == 3
    assert pack["summary"]["issues_total"] == 0
    assert read_json(output_dir / "annotation_pack_summary.json")["tasks_total"] == 3
    assert len(read_jsonl(output_dir / "annotation_tasks.jsonl")) == 3
    for task in pack["tasks"]:
        assert task["supporting_evidence"]
        assert task["llm_instructions"]["role"] == "grounded_rewriter_or_probe_drafter"
        assert "invent supporting events" in pack["constraints"]["llm_must_not"]
        assert task["verifier_expectations"]["positive_event_ids_must_be_subset_of"] == task["provenance"]["supporting_event_ids"]
        assert task["action_boundary_candidate"]["allowed_actions"] or task["action_boundary_candidate"]["forbidden_actions"]
        for snippet in task["supporting_evidence"]:
            assert snippet["event_id"] in task["provenance"]["supporting_event_ids"]
            assert snippet["content_hashes"]
            assert snippet["raw_pointer"]


def test_gharchive_annotation_pack_preserves_negative_example_gate(tmp_path: Path):
    pack = build_gharchive_annotation_pack(DEFAULT_GHARCHIVE_FIXTURE_PATH, repo="acme/docs", output_dir=tmp_path / "pack")
    negative_tasks = [task for task in pack["tasks"] if task["candidate_type"] == "negative_policy_example"]

    assert len(negative_tasks) == 1
    task = negative_tasks[0]
    assert task["negative_evidence"]
    assert task["verifier_expectations"]["requires_negative_evidence"] is True
    assert "durable assistant habit" in task["human_review_checklist"][-1]
    assert "store_human_emergency_merge_as_agent_default" in task["action_boundary_candidate"]["forbidden_actions"]


def test_policy_rewrite_validator_accepts_grounded_proposals(tmp_path: Path):
    output_dir = tmp_path / "pack"
    build_gharchive_annotation_pack(DEFAULT_GHARCHIVE_FIXTURE_PATH, repo="acme/docs", output_dir=output_dir)
    proposals_path = tmp_path / "proposals.jsonl"
    write_jsonl(
        proposals_path,
        [
            {
                "proposal_id": "proposal_routing",
                "annotation_id": "annot_candidate_acme_docs_summary_review_routing",
                "candidate_id": "candidate_acme_docs_summary_review_routing",
                "rewritten_policy": "For low-risk documentation PRs in acme/docs, add a summary comment and request Nina review before merge.",
                "future_probe_query": "A docs PR is open. Which GitHub actions are allowed, and what should not happen before review?",
                "expected_behavior": {
                    "must_include": ["add summary comment", "request Nina review"],
                    "must_not_include": ["merge before review"],
                },
                "positive_event_ids": ["event_gharchive_gha_002", "event_gharchive_gha_003"],
                "negative_event_ids": [],
                "action_boundary": {
                    "allowed_actions": ["add_summary_comment", "request_nina_review"],
                    "forbidden_actions": ["merge_before_review"],
                    "conditions": ["acme_docs", "low_risk_documentation_pr"],
                    "authorized_tools": ["github"],
                },
            },
            {
                "proposal_id": "proposal_ci",
                "annotation_id": "annot_candidate_acme_docs_ci_before_merge",
                "candidate_id": "candidate_acme_docs_ci_before_merge",
                "rewritten_policy": "For acme/docs PRs, wait for CI and merge only after CI success.",
                "future_probe_query": "CI is in progress on a PR. Should the agent merge now?",
                "expected_behavior": {
                    "must_include": ["wait for CI", "merge after CI success"],
                    "must_not_include": ["merge before CI success"],
                },
                "positive_event_ids": ["event_gharchive_gha_004", "event_gharchive_gha_005"],
                "negative_event_ids": [],
                "action_boundary": {
                    "allowed_actions": ["wait_for_ci", "merge_after_ci_success"],
                    "forbidden_actions": ["merge_before_ci_success"],
                    "conditions": ["pull_request_ci_in_progress"],
                    "authorized_tools": ["github", "ci"],
                },
            },
            {
                "proposal_id": "proposal_negative",
                "annotation_id": "annot_candidate_acme_docs_emergency_negative_storage",
                "candidate_id": "candidate_acme_docs_emergency_negative_storage",
                "rewritten_policy": "The emergency human pre-CI merge is not a default assistant habit.",
                "future_probe_query": "Should the assistant store this emergency pre-CI merge as its default habit?",
                "expected_behavior": {
                    "must_include": ["do not store default assistant habit"],
                    "must_not_include": ["merge before CI by default"],
                },
                "positive_event_ids": ["event_gharchive_gha_007"],
                "negative_event_ids": ["event_gharchive_gha_007"],
                "action_boundary": {
                    "allowed_actions": ["suppress_pre_ci_merge_as_agent_habit"],
                    "forbidden_actions": ["store_human_emergency_merge_as_agent_default"],
                    "conditions": ["human_emergency_hotfix"],
                    "authorized_tools": ["github", "ci"],
                },
            },
        ],
    )

    report = validate_policy_rewrite_proposals(output_dir / "annotation_pack.json", proposals_path, tmp_path / "validation.json")

    assert report["passed"] is True
    assert report["summary"]["proposals_passed"] == 3
    assert read_json(tmp_path / "validation.json")["passed"] is True


def test_export_policy_rewrite_prompts_writes_grounded_prompt_records(tmp_path: Path):
    output_dir = tmp_path / "pack"
    build_gharchive_annotation_pack(DEFAULT_GHARCHIVE_FIXTURE_PATH, repo="acme/docs", output_dir=output_dir)
    prompts_path = tmp_path / "rewrite_prompts.jsonl"

    summary = export_policy_rewrite_prompts(output_dir / "annotation_pack.json", prompts_path, prompt_version="test-v1")
    prompts = read_jsonl(prompts_path)
    summary_file = read_json(Path(str(prompts_path) + ".summary.json"))

    assert summary["prompts_total"] == 3
    assert summary_file["constraints"]["llm_generation_performed"] is False
    assert len(prompts) == 3
    first = prompts[0]
    assert first["prompt_version"] == "test-v1"
    assert first["annotation_id"].startswith("annot_")
    assert "Supporting evidence:" in first["user_prompt"]
    assert "Action boundary to preserve exactly or narrow" in first["user_prompt"]
    assert first["constraints"]["allowed_positive_event_ids"]
    assert "validate-policy-rewrites" in first["validator_command_template"]
    assert first["output_schema"]["annotation_id"] == first["annotation_id"]


def test_policy_rewrite_validator_rejects_ungrounded_or_widened_proposal(tmp_path: Path):
    output_dir = tmp_path / "pack"
    build_gharchive_annotation_pack(DEFAULT_GHARCHIVE_FIXTURE_PATH, repo="acme/docs", output_dir=output_dir)
    proposals_path = tmp_path / "bad_proposals.jsonl"
    write_jsonl(
        proposals_path,
        [
            {
                "proposal_id": "proposal_bad",
                "annotation_id": "annot_candidate_acme_docs_ci_before_merge",
                "candidate_id": "candidate_acme_docs_ci_before_merge",
                "rewritten_policy": "For all acme/docs PRs, merge when convenient.",
                "future_probe_query": "Should the agent merge before CI?",
                "expected_behavior": {"must_include": ["merge"], "must_not_include": []},
                "positive_event_ids": ["event_invented"],
                "negative_event_ids": [],
                "action_boundary": {
                    "allowed_actions": ["wait_for_ci", "merge_without_ci"],
                    "forbidden_actions": [],
                    "conditions": ["all_pull_requests"],
                    "authorized_tools": ["github", "ci", "slack"],
                },
            }
        ],
    )

    report = validate_policy_rewrite_proposals(output_dir / "annotation_pack.json", proposals_path, require_complete=False)

    assert report["passed"] is False
    failed = report["reports"][0]
    assert failed["passed"] is False
    assert any("positive_event_ids" in issue for issue in failed["issues"])
    assert any("allowed_actions_subset" in issue for issue in failed["issues"])
    assert any("authorized_tools_subset" in issue for issue in failed["issues"])


def test_validate_policy_rewrite_proposals_batch_groups_unified_jsonl_by_pack(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    batch_dir = tmp_path / "packs"
    build_gharchive_annotation_pack_batch(fixture_path, output_dir=batch_dir)
    proposals_path = tmp_path / "batch_proposals.jsonl"
    write_jsonl(
        proposals_path,
        [
            _proposal_for_task(task, pack["pack_id"])
            for pack in read_json(batch_dir / "batch_annotation_pack_report.json")["packs"]
            for task in read_json(Path(pack["output_dir"]) / "annotation_pack.json")["tasks"]
        ],
    )

    report = validate_policy_rewrite_proposals_batch(batch_dir, proposals_path, tmp_path / "batch_validation")

    assert report["passed"] is True
    assert report["summary"]["packs_total"] == 2
    assert report["summary"]["packs_passed"] == 2
    assert report["summary"]["proposals_total"] == 8
    assert read_json(tmp_path / "batch_validation" / "batch_rewrite_validation_report.json")["passed"] is True


def test_validate_policy_rewrite_proposals_batch_rejects_missing_pack_outputs(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    batch_dir = tmp_path / "packs"
    build_gharchive_annotation_pack_batch(fixture_path, output_dir=batch_dir)
    first_pack = read_json(batch_dir / "batch_annotation_pack_report.json")["packs"][0]
    proposals_path = tmp_path / "partial_batch_proposals.jsonl"
    write_jsonl(
        proposals_path,
        [
            _proposal_for_task(task, first_pack["pack_id"])
            for task in read_json(Path(first_pack["output_dir"]) / "annotation_pack.json")["tasks"]
        ],
    )

    report = validate_policy_rewrite_proposals_batch(batch_dir, proposals_path, tmp_path / "batch_validation")

    assert report["passed"] is False
    assert report["summary"]["packs_failed"] == 1
    assert report["summary"]["missing_annotation_outputs"]


def test_build_projects_from_policy_rewrite_batch_writes_verifiable_projects(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    batch_dir = tmp_path / "packs"
    build_gharchive_annotation_pack_batch(fixture_path, output_dir=batch_dir)
    proposals_path = tmp_path / "batch_proposals.jsonl"
    write_jsonl(
        proposals_path,
        [
            _proposal_for_task(task, pack["pack_id"])
            for pack in read_json(batch_dir / "batch_annotation_pack_report.json")["packs"]
            for task in read_json(Path(pack["output_dir"]) / "annotation_pack.json")["tasks"]
        ],
    )
    validation = validate_policy_rewrite_proposals_batch(batch_dir, proposals_path, tmp_path / "batch_validation")

    report = build_projects_from_policy_rewrite_batch(
        tmp_path / "batch_validation" / "batch_rewrite_validation_report.json",
        tmp_path / "projects",
        project_prefix="project_batch_rewrite",
    )

    assert validation["passed"] is True
    assert report["passed"] is True
    assert report["summary"]["projects_total"] == 2
    assert report["summary"]["projects_passed"] == 2
    for project in report["projects"]:
        verifier = run_project_verifier(Path(project["project_dir"]))
        assert verifier.passed is True
    assert read_json(tmp_path / "projects" / "batch_rewrite_project_report.json")["passed"] is True


def test_policy_rewrite_human_audit_pack_and_acceptance_validation(tmp_path: Path):
    validation_report_path = _validated_rewrite_batch(tmp_path)

    manifest = export_policy_rewrite_human_audit_pack(
        validation_report_path,
        tmp_path / "audit",
        sample_size=4,
        min_per_candidate_type=1,
        seed=7,
    )
    audit_items = read_jsonl(tmp_path / "audit" / "audit_items.jsonl")
    decision_template = read_jsonl(tmp_path / "audit" / "audit_decisions_template.jsonl")
    decisions_path = tmp_path / "audit_decisions.jsonl"
    write_jsonl(
        decisions_path,
        [
            template | {"decision": "accept", "reviewer_id": "reviewer_1", "notes": "grounded"}
            for template in decision_template
        ],
    )

    report = validate_policy_rewrite_human_audit(
        tmp_path / "audit",
        decisions_path,
        output_path=tmp_path / "audit_report.json",
    )

    assert manifest["sample"]["sample_size"] == 4
    assert len(audit_items) == 4
    assert len(decision_template) == 4
    assert {item["candidate_type"] for item in audit_items} >= {"authorization_boundary", "negative_policy_example"}
    assert audit_items[0]["supporting_evidence"]
    assert audit_items[0]["proposal_action_boundary"]
    assert report["passed"] is True
    assert report["summary"]["accept_rate"] == 1.0
    assert read_json(tmp_path / "audit_report.json")["passed"] is True


def test_policy_rewrite_human_audit_validation_rejects_blocking_issues(tmp_path: Path):
    validation_report_path = _validated_rewrite_batch(tmp_path)
    export_policy_rewrite_human_audit_pack(validation_report_path, tmp_path / "audit", sample_size=3, seed=3)
    templates = read_jsonl(tmp_path / "audit" / "audit_decisions_template.jsonl")
    decisions_path = tmp_path / "audit_decisions.jsonl"
    decisions = [
        template | {"decision": "accept", "reviewer_id": "reviewer_1", "notes": "grounded"}
        for template in templates
    ]
    decisions[0]["decision"] = "reject"
    decisions[0]["issue_labels"] = ["invented_fact"]
    decisions[0]["blocking"] = True
    write_jsonl(decisions_path, decisions)

    report = validate_policy_rewrite_human_audit(tmp_path / "audit", decisions_path, min_accept_rate=0.8)

    assert report["passed"] is False
    assert report["summary"]["rejected"] == 1
    assert report["summary"]["issue_codes"]["blocking_human_audit_issue"] == 1


def test_build_project_from_policy_rewrites_writes_verifiable_project(tmp_path: Path):
    output_dir = tmp_path / "pack"
    build_gharchive_annotation_pack(DEFAULT_GHARCHIVE_FIXTURE_PATH, repo="acme/docs", output_dir=output_dir)
    proposals_path = Path(__file__).resolve().parents[1] / "examples" / "annotation_rewrites" / "gharchive_rewrite_examples.jsonl"
    summary = build_project_from_policy_rewrites(
        output_dir / "annotation_pack.json",
        proposals_path,
        tmp_path / "projects",
        project_id="project_rewrite_test",
        validation_output_path=tmp_path / "rewrite_validation.json",
    )
    project_dir = Path(summary["project_dir"])
    report = run_project_verifier(project_dir)
    graph = read_json(project_dir / "memory_graph.json")
    probes = read_jsonl(project_dir / "probes.jsonl")

    assert summary["memories"] == 4
    assert summary["probes"] >= 3
    assert read_json(tmp_path / "rewrite_validation.json")["passed"] is True
    assert report.passed is True
    assert any(memory["memory_type"] == "negative_policy_example" for memory in graph["memories"])
    assert any(memory["memory_type"] == "distractor" for memory in graph["memories"])
    assert any(probe["evidence"]["negative"] for probe in probes)
    assert any(probe["evidence"]["distractor"] for probe in probes)


def test_gharchive_annotation_pack_batch_builds_per_repo_packs(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    report = build_gharchive_annotation_pack_batch(fixture_path, output_dir=tmp_path / "packs")

    assert report["summary"]["packs_total"] == 2
    assert report["summary"]["skipped_total"] == 0
    assert report["summary"]["tasks_total"] == sum(pack["tasks"] for pack in report["packs"])
    assert report["summary"]["tasks_total"] >= 4
    assert {pack["repo"] for pack in report["packs"]} == {"acme/docs", "beta/api"}
    for pack in report["packs"]:
        pack_dir = tmp_path / "packs" / pack["repo"].replace("/", "_")
        assert (pack_dir / "annotation_pack.json").exists()
        assert read_json(pack_dir / "annotation_pack_summary.json")["tasks_total"] == pack["tasks"]
        assert pack["tasks"] > 0
    assert read_json(tmp_path / "packs" / "batch_annotation_pack_report.json")["summary"]["packs_total"] == 2


def test_export_policy_rewrite_prompts_batch_writes_per_pack_prompts(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    batch_dir = tmp_path / "packs"
    build_gharchive_annotation_pack_batch(fixture_path, output_dir=batch_dir)

    report = export_policy_rewrite_prompts_batch(batch_dir, tmp_path / "prompt_exports", prompt_version="batch-v1")

    assert report["summary"]["packs_total"] == 2
    assert report["summary"]["prompts_total"] == 8
    assert report["constraints"]["llm_generation_performed"] is False
    for item in report["exports"]:
        prompts = read_jsonl(Path(item["output_path"]))
        assert len(prompts) == item["prompts"]
        assert all(prompt["prompt_version"] == "batch-v1" for prompt in prompts)
    assert read_json(tmp_path / "prompt_exports" / "rewrite_prompt_batch_report.json")["summary"]["prompts_total"] == 8


def test_package_policy_rewrite_jobs_shards_prompt_exports_without_generation(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    batch_dir = tmp_path / "packs"
    prompt_dir = tmp_path / "prompt_exports"
    build_gharchive_annotation_pack_batch(fixture_path, output_dir=batch_dir)
    export_policy_rewrite_prompts_batch(batch_dir, prompt_dir, prompt_version="job-v1")

    manifest = package_policy_rewrite_jobs(prompt_dir, tmp_path / "rewrite_jobs", max_prompts_per_job=3)

    assert manifest["summary"]["prompts_total"] == 8
    assert manifest["summary"]["jobs_total"] == 3
    assert manifest["constraints"]["llm_generation_performed"] is False
    assert manifest["constraints"]["proposal_templates_are_empty"] is True
    first_job = manifest["jobs"][0]
    assert first_job["prompts"] == 3
    assert first_job["estimated_tokens"] > 0
    assert Path(first_job["prompts_path"]).exists()
    proposals = read_jsonl(Path(first_job["proposal_template_path"]))
    assert len(proposals) == 3
    assert proposals[0]["rewritten_policy"] == ""
    assert proposals[0]["future_probe_query"] == ""
    assert proposals[0]["action_boundary"]
    job_manifest = read_json(Path(first_job["job_manifest_path"]))
    assert job_manifest["constraints"]["llm_generation_performed"] is False
    assert "validate-policy-rewrites-batch" in job_manifest["validation_command_template"]
    assert read_json(tmp_path / "rewrite_jobs" / "rewrite_job_manifest.json")["summary"]["jobs_total"] == 3


def test_collect_policy_rewrite_job_outputs_writes_validator_ready_jsonl(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    batch_dir = tmp_path / "packs"
    prompt_dir = tmp_path / "prompt_exports"
    rewrite_job_dir = tmp_path / "rewrite_jobs"
    build_gharchive_annotation_pack_batch(fixture_path, output_dir=batch_dir)
    export_policy_rewrite_prompts_batch(batch_dir, prompt_dir, prompt_version="job-v1")
    manifest = package_policy_rewrite_jobs(prompt_dir, rewrite_job_dir, max_prompts_per_job=4)

    for job in manifest["jobs"]:
        templates = read_jsonl(Path(job["proposal_template_path"]))
        write_jsonl(
            Path(job["job_dir"]) / "proposals.jsonl",
            [_completed_proposal_from_template(row) for row in templates],
        )

    report = collect_policy_rewrite_job_outputs(
        rewrite_job_dir,
        tmp_path / "collected_rewrite_proposals.jsonl",
        report_path=tmp_path / "collection_report.json",
    )
    validation = validate_policy_rewrite_proposals_batch(
        batch_dir,
        tmp_path / "collected_rewrite_proposals.jsonl",
        tmp_path / "batch_validation",
    )

    assert report["passed"] is True
    assert report["summary"]["jobs_passed"] == 2
    assert report["summary"]["proposals_collected"] == 8
    assert report["summary"]["issue_counts"] == {}
    assert len(read_jsonl(tmp_path / "collected_rewrite_proposals.jsonl")) == 8
    assert read_json(tmp_path / "collection_report.json")["ready_for_validation"] is True
    assert validation["passed"] is True


def test_collect_policy_rewrite_job_outputs_rejects_unfilled_templates(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    batch_dir = tmp_path / "packs"
    prompt_dir = tmp_path / "prompt_exports"
    rewrite_job_dir = tmp_path / "rewrite_jobs"
    build_gharchive_annotation_pack_batch(fixture_path, output_dir=batch_dir)
    export_policy_rewrite_prompts_batch(batch_dir, prompt_dir, prompt_version="job-v1")
    package_policy_rewrite_jobs(prompt_dir, rewrite_job_dir, max_prompts_per_job=4)

    report = collect_policy_rewrite_job_outputs(
        rewrite_job_dir,
        tmp_path / "collected_rewrite_proposals.jsonl",
        report_path=tmp_path / "collection_report.json",
    )

    assert report["passed"] is False
    assert report["summary"]["proposals_collected"] == 0
    assert report["summary"]["issue_counts"]["unfilled_proposal"] == 8
    assert report["summary"]["warning_counts"]["template_file_used"] == 2
    assert read_jsonl(tmp_path / "collected_rewrite_proposals.jsonl") == []


def test_gharchive_annotation_pack_batch_reports_ineligible_repos(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_sample.jsonl"
    report = build_gharchive_annotation_pack_batch(fixture_path, output_dir=tmp_path / "packs")

    assert report["summary"]["packs_total"] == 0
    assert report["summary"]["skipped_total"] == 1
    assert report["skipped"][0]["repo"] == "acme/docs"
    assert "negative_boundary" in report["skipped"][0]["reason"]


def test_export_annotation_pack_release_writes_repo_disjoint_splits(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    batch_dir = tmp_path / "packs"
    build_gharchive_annotation_pack_batch(fixture_path, output_dir=batch_dir)

    manifest = export_annotation_pack_release(batch_dir, tmp_path / "release", version="test")
    all_tasks = read_jsonl(tmp_path / "release" / "tasks" / "all.jsonl")
    splits = read_json(tmp_path / "release" / "splits.json")
    release_manifest = read_json(tmp_path / "release" / "release_manifest.json")

    assert manifest["counts"]["packs"] == 2
    assert manifest["counts"]["tasks"] == 8
    assert len(all_tasks) == 8
    assert release_manifest["version"] == "test"
    assert all(record["content_hash"] for record in release_manifest["packs"])
    split_by_pack = {}
    for split, pack_ids in splits.items():
        for pack_id in pack_ids:
            assert pack_id not in split_by_pack
            split_by_pack[pack_id] = split
    assert set(split_by_pack) == {pack["pack_id"] for pack in manifest["packs"]}
    task_pack_ids = {task["source_pack_id"] for task in all_tasks}
    assert task_pack_ids == set(split_by_pack)


def test_gharchive_scale_summary_combines_batch_and_release_stats(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    batch_dir = tmp_path / "packs"
    release_dir = tmp_path / "release"
    build_gharchive_annotation_pack_batch(fixture_path, output_dir=batch_dir)
    export_annotation_pack_release(batch_dir, release_dir, version="test")

    summary = summarize_gharchive_annotation_scale(batch_dir, release_dir=release_dir, output_path=tmp_path / "scale.json")

    assert summary["repos"]["eligible_packs"] == 2
    assert summary["repos"]["skipped"] == 0
    assert summary["tasks"]["total"] == 8
    assert summary["tasks"]["mean_per_pack"] == 4
    assert summary["candidate_types"]["authorization_boundary"] == 2
    assert summary["candidate_types"]["contextual_policy"] == 2
    assert summary["candidate_types"]["issue_triage_policy"] == 2
    assert summary["candidate_types"]["negative_policy_example"] == 2
    assert summary["release"]["pack_hashes_present"] is True
    assert summary["release"]["llm_generation_allowed"] is False
    assert read_json(tmp_path / "scale.json")["tasks"]["total"] == 8


def _proposal_for_task(task: dict, pack_id: str) -> dict:
    boundary = task["action_boundary_candidate"]
    allowed_actions = boundary.get("allowed_actions", [])
    forbidden_actions = boundary.get("forbidden_actions", [])
    allowed_terms = [item.replace("_", " ") for item in allowed_actions] or ["follow policy"]
    forbidden_terms = [item.replace("_", " ") for item in forbidden_actions] or ["violate policy"]
    rewritten_policy = f"{task['policy_candidate']} Preserve allowed actions: {', '.join(allowed_terms)}."
    if task["candidate_type"] == "negative_policy_example":
        rewritten_policy += " This is not a default assistant habit."
    return {
        "proposal_id": f"proposal_{task['candidate_id']}",
        "annotation_id": task["annotation_id"],
        "candidate_id": task["candidate_id"],
        "rewritten_policy": rewritten_policy,
        "future_probe_query": f"What should the assistant do for {task['repo']} under this policy?",
        "expected_behavior": {
            "must_include": allowed_terms,
            "must_not_include": forbidden_terms,
        },
        "positive_event_ids": [snippet["event_id"] for snippet in task["supporting_evidence"]],
        "negative_event_ids": [snippet["event_id"] for snippet in task["negative_evidence"]],
        "action_boundary": boundary,
        "metadata": {"pack_id": pack_id},
    }


def _validated_rewrite_batch(tmp_path: Path) -> Path:
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    batch_dir = tmp_path / "packs"
    proposals_path = tmp_path / "batch_proposals.jsonl"
    validation_dir = tmp_path / "batch_validation"
    build_gharchive_annotation_pack_batch(fixture_path, output_dir=batch_dir)
    write_jsonl(
        proposals_path,
        [
            _proposal_for_task(task, pack["pack_id"])
            for pack in read_json(batch_dir / "batch_annotation_pack_report.json")["packs"]
            for task in read_json(Path(pack["output_dir"]) / "annotation_pack.json")["tasks"]
        ],
    )
    report = validate_policy_rewrite_proposals_batch(batch_dir, proposals_path, validation_dir)
    assert report["passed"] is True
    return validation_dir / "batch_rewrite_validation_report.json"


def _completed_proposal_from_template(template: dict) -> dict:
    boundary = template["action_boundary"]
    allowed_actions = boundary.get("allowed_actions", [])
    forbidden_actions = boundary.get("forbidden_actions", [])
    allowed_terms = [item.replace("_", " ") for item in allowed_actions] or ["follow policy"]
    forbidden_terms = [item.replace("_", " ") for item in forbidden_actions] or ["violate policy"]
    rewritten_policy = f"Follow the grounded policy for {template['candidate_id']}: {', '.join(allowed_terms)}."
    if template["negative_event_ids"]:
        rewritten_policy += " This is not a default assistant habit."
    return template | {
        "proposal_id": f"proposal_{template['candidate_id']}",
        "rewritten_policy": rewritten_policy,
        "future_probe_query": f"What should the assistant do under {template['candidate_id']}?",
        "expected_behavior": {
            "must_include": allowed_terms,
            "must_not_include": forbidden_terms,
        },
        "metadata": template.get("metadata", {}) | {"pack_id": template["pack_id"]},
    }
