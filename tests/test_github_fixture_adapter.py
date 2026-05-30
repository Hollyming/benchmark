from pathlib import Path

from ultra_long_benchmark.pipelines.gharchive_pilot import DEFAULT_FIXTURE_PATH as DEFAULT_GHARCHIVE_FIXTURE_PATH
from ultra_long_benchmark.pipelines.gharchive_pilot import build_gharchive_slice
from ultra_long_benchmark.pipelines.gharchive_pilot import mine_gharchive_policy_candidates
from ultra_long_benchmark.pipelines.gharchive_pilot import plan_gharchive_stage
from ultra_long_benchmark.pipelines.gharchive_pilot import profile_gharchive_repos
from ultra_long_benchmark.pipelines.gharchive_pilot import profile_gharchive_time_windows
from ultra_long_benchmark.pipelines.gharchive_pilot import rank_gharchive_repos
from ultra_long_benchmark.pipelines.gharchive_pilot import run_gharchive_batch_pilot
from ultra_long_benchmark.pipelines.gharchive_pilot import run_gharchive_pilot
from ultra_long_benchmark.pipelines.github_fixture import DEFAULT_FIXTURE_PATH, run_github_fixture_pilot
from ultra_long_benchmark.pipelines.source_adapters import GHArchiveEventAdapter, GitHubIssueCIAdapter
from ultra_long_benchmark.pipelines.verifier import run_project_verifier
from ultra_long_benchmark.shared.io import read_json


def test_github_issue_ci_adapter_normalizes_fixture_records():
    result = GitHubIssueCIAdapter(DEFAULT_FIXTURE_PATH).load()

    assert result.project_profile.project_id == "project_github_001"
    assert len(result.artifacts) == 4
    assert len(result.events) == 4
    assert any(event.invalidates for event in result.events)
    assert {artifact.artifact_type for artifact in result.artifacts} >= {"pull_request", "ci_log", "review_comment", "chat_message"}
    artifact_ids = {artifact.artifact_id for artifact in result.artifacts}
    assert {artifact_id for event in result.events for artifact_id in event.artifacts} <= artifact_ids


def test_gharchive_adapter_normalizes_public_event_slice():
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_sample.jsonl"
    result = GHArchiveEventAdapter(fixture_path, project_id="project_gharchive_sample", repo_full_name="acme/docs").load()

    assert result.project_profile.synthetic_context is False
    assert result.project_profile.source_streams == ["gharchive_public_events"]
    assert len(result.artifacts) == 3
    assert len(result.events) == 3
    assert {event.event_type for event in result.events} == {"github_pull_request", "github_pr_review", "github_ci_status"}
    assert all(event.source_dataset == "gharchive" for event in result.events)
    assert any("pr_workflow_signal" in event.claims for event in result.events)
    assert any("ci_signal_observed" in event.claims for event in result.events)


def test_gharchive_pilot_writes_verifiable_project(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    project_dir = Path(summary["project_dir"])
    report = run_project_verifier(project_dir)
    graph = read_json(project_dir / "memory_graph.json")

    assert summary["project_id"] == "project_gharchive_001"
    assert summary["artifacts"] == 7
    assert summary["events"] == 7
    assert summary["memories"] == 4
    assert summary["probes"] == 3
    assert report.passed is True
    assert {memory["memory_type"] for memory in graph["memories"]} >= {"contextual_policy", "authorization_boundary", "negative_policy_example"}


def test_gharchive_pilot_derives_policy_from_alternate_repo_slice(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_alt_repo_sample.jsonl"
    summary = run_gharchive_pilot(
        tmp_path / "projects",
        input_path=fixture_path,
        repo_full_name="beta/api",
        project_id="project_beta_api",
    )
    project_dir = Path(summary["project_dir"])
    report = run_project_verifier(project_dir)
    graph = read_json(project_dir / "memory_graph.json")
    routing = next(memory for memory in graph["memories"] if memory["memory_id"] == "memory_gharchive_docs_pr_routing")

    assert summary["events"] == 6
    assert report.passed is True
    assert "beta/api" in routing["content"]
    assert "priya-review" in routing["content"]
    assert "request_priya_review" in routing["action_boundary"]["allowed_actions"]


def test_gharchive_batch_pilot_discovers_and_verifies_multiple_repos(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    summary = run_gharchive_batch_pilot(tmp_path / "projects", input_path=fixture_path)

    assert summary["repos_requested"] == 2
    assert summary["project_count"] == 2
    assert summary["skipped"] == []
    project_ids = {project["project_id"] for project in summary["projects"]}
    assert project_ids == {"project_gharchive_acme_docs", "project_gharchive_beta_api"}
    for project in summary["projects"]:
        report = run_project_verifier(Path(project["project_dir"]))
        assert report.passed is True


def test_gharchive_quality_report_marks_eligible_and_ineligible_repos(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    report_path = tmp_path / "quality.json"
    report = profile_gharchive_repos(fixture_path, output_path=report_path)

    assert report_path.exists()
    assert report["summary"]["repos_total"] == 2
    assert report["summary"]["repos_eligible"] == 2
    assert {repo["repo"] for repo in report["repos"] if repo["eligible"]} == {"acme/docs", "beta/api"}
    assert all(repo["counts"]["ci"] >= 1 for repo in report["repos"])

    small_report = profile_gharchive_repos(Path(__file__).parent / "fixtures" / "gharchive_sample.jsonl")
    repo = small_report["repos"][0]
    assert repo["eligible"] is False
    assert "negative_boundary" in repo["missing_required_signals"]


def test_gharchive_repo_ranking_prefers_complete_policy_signal_repos(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    report = rank_gharchive_repos(fixture_path, output_path=tmp_path / "repo_rank.json", limit=1)

    assert report["summary"]["repos_eligible"] == 2
    assert len(report["repos"]) == 1
    assert report["repos"][0]["eligible"] is True
    assert report["recommended_repos"] == [report["repos"][0]["repo"]]


def test_gharchive_batch_pilot_reports_skipped_ineligible_repos(tmp_path: Path):
    summary = run_gharchive_batch_pilot(tmp_path / "projects", input_path=Path(__file__).parent / "fixtures" / "gharchive_sample.jsonl")

    assert summary["project_count"] == 0
    assert summary["skipped"]
    assert summary["skipped"][0]["repo"] == "acme/docs"
    assert "negative_boundary" in summary["skipped"][0]["reason"]


def test_gharchive_time_window_report_tracks_longitudinal_signal_distribution(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_window_sample.jsonl"
    report_path = tmp_path / "windows.json"
    report = profile_gharchive_time_windows(fixture_path, window_days=7, output_path=report_path)

    assert report_path.exists()
    assert report["summary"]["repos_total"] == 1
    assert report["summary"]["windows_total"] == 2
    assert report["summary"]["eligible_windows"] == 1
    assert report["summary"]["repos_spanning_multiple_windows"] == 1
    repo_report = report["repos"][0]
    assert repo_report["repo"] == "acme/docs"
    assert repo_report["windows_total"] == 2
    assert repo_report["eligible_windows"] == 1
    eligible = [window for window in report["windows"] if window["eligible"]]
    ineligible = [window for window in report["windows"] if not window["eligible"]]
    assert eligible[0]["counts"]["negative_boundary"] == 1
    assert eligible[0]["counts"]["emergency_negative"] == 1
    assert "negative_boundary" in ineligible[0]["missing_required_signals"]


def test_gharchive_policy_candidate_mining_is_grounded_in_events(tmp_path: Path):
    report_path = tmp_path / "candidates.json"
    report = mine_gharchive_policy_candidates(DEFAULT_GHARCHIVE_FIXTURE_PATH, repo="acme/docs", output_path=report_path)

    assert report_path.exists()
    assert report["summary"]["repos_total"] == 1
    assert report["summary"]["candidates_total"] == 3
    assert report["summary"]["candidate_types"] == {
        "authorization_boundary": 1,
        "contextual_policy": 1,
        "negative_policy_example": 1,
    }
    by_type = {candidate["candidate_type"]: candidate for candidate in report["candidates"]}
    routing = by_type["contextual_policy"]
    assert "summary comment" in routing["policy"]
    assert "nina-reviewer" in routing["policy"]
    assert routing["supporting_events"]
    assert "request_nina_review" in routing["action_boundary"]["allowed_actions"]
    ci_boundary = by_type["authorization_boundary"]
    assert "merge_before_ci_success" in ci_boundary["action_boundary"]["forbidden_actions"]
    negative = by_type["negative_policy_example"]
    assert negative["negative_events"]
    assert negative["negative_events"] == negative["supporting_events"]


def test_gharchive_policy_candidate_mining_extracts_issue_triage_policy_from_labels(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    report = mine_gharchive_policy_candidates(fixture_path, repo="acme/docs", output_path=tmp_path / "candidates.json")

    assert report["summary"]["candidate_types"]["issue_triage_policy"] == 1
    triage = next(candidate for candidate in report["candidates"] if candidate["candidate_type"] == "issue_triage_policy")
    assert "docs" in triage["policy"]
    assert triage["supporting_events"] == ["event_gharchive_multi_a_005"]
    assert "assign_docs_owner" in triage["action_boundary"]["allowed_actions"]
    assert "close_without_triage_owner" in triage["action_boundary"]["forbidden_actions"]


def test_gharchive_stage_plan_reports_paper_scale_gaps_without_generation(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    report_path = tmp_path / "stage_plan.json"
    report = plan_gharchive_stage(fixture_path, profile="paper", window_days=7, output_path=report_path)

    assert report_path.exists()
    assert report["summary"]["passed"] is False
    assert "eligible_repos" in report["summary"]["blocking_checks"]
    assert report["summary"]["candidate_types"] == {
        "authorization_boundary": 2,
        "contextual_policy": 2,
        "issue_triage_policy": 2,
        "negative_policy_example": 2,
    }
    assert report["checks"]["candidate_types"]["status"] == "pass"
    assert report["decision"]["ready_for_annotation_budget"] is False
    assert report["decision"]["recommended_mode"] == "expand_or_restage_slice"
    assert "eligible_repos" in report["decision"]["blocking_checks"]
    assert report["constraints"]["network_download_performed"] is False
    assert report["constraints"]["llm_generation_performed"] is False
    assert report["recommended_next_actions"]


def test_gharchive_stage_plan_accepts_fixture_profile(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    report = plan_gharchive_stage(fixture_path, profile="fixture", window_days=7, output_path=tmp_path / "stage_plan.json")

    assert report["summary"]["passed"] is True
    assert report["summary"]["failed"] == 0
    assert report["decision"]["ready_for_annotation_budget"] is False
    assert report["decision"]["recommended_mode"] == "engineering_fixture"
    assert report["checks"]["events"]["status"] == "pass"
    assert report["checks"]["candidate_count"]["status"] == "pass"
    assert report["candidate_repos"][0]["candidates"] == 4


def test_build_gharchive_slice_filters_file_and_writes_manifest(tmp_path: Path):
    output_path = tmp_path / "slice.jsonl"
    manifest = build_gharchive_slice(
        DEFAULT_GHARCHIVE_FIXTURE_PATH,
        output_path,
        repos=["acme/docs"],
        max_records_per_repo=4,
    )

    assert output_path.exists()
    assert manifest["counts"]["records_selected"] == 4
    assert manifest["counts"]["repos_selected"] == 1
    assert manifest["repo_counts"] == {"acme/docs": 4}
    assert manifest["constraints"]["network_download_performed"] is False
    assert read_json(Path(str(output_path) + ".manifest.json"))["output_path"] == str(output_path)
    quality = profile_gharchive_repos(output_path)
    assert quality["summary"]["events_total"] == 4


def test_build_gharchive_slice_reads_directory_and_can_require_eligible_repo(tmp_path: Path):
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    source_a = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    source_b = DEFAULT_GHARCHIVE_FIXTURE_PATH
    (input_dir / "a.jsonl").write_text(source_a.read_text(encoding="utf-8"), encoding="utf-8")
    (input_dir / "b.jsonl").write_text(source_b.read_text(encoding="utf-8"), encoding="utf-8")
    output_path = tmp_path / "eligible_slice.jsonl"

    manifest = build_gharchive_slice(input_dir, output_path, require_eligible_repo=True)

    assert manifest["counts"]["source_files"] == 2
    assert manifest["counts"]["records_selected"] > 0
    assert set(manifest["eligible_repos"]) >= {"acme/docs", "beta/api"}


def test_build_gharchive_slice_can_limit_records_per_source_file(tmp_path: Path):
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    source_a = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    (input_dir / "a.jsonl").write_text(source_a.read_text(encoding="utf-8"), encoding="utf-8")
    (input_dir / "b.jsonl").write_text(source_a.read_text(encoding="utf-8"), encoding="utf-8")
    output_path = tmp_path / "balanced_slice.jsonl"

    manifest = build_gharchive_slice(input_dir, output_path, max_records_per_source_file=2)

    assert manifest["counts"]["source_files"] == 2
    assert manifest["counts"]["records_selected"] == 4
    assert manifest["filters"]["max_records_per_source_file"] == 2


def test_build_gharchive_slice_require_eligible_repo_fails_with_manifest(tmp_path: Path):
    output_path = tmp_path / "small_slice.jsonl"
    manifest_path = tmp_path / "small_manifest.json"

    try:
        build_gharchive_slice(
            Path(__file__).parent / "fixtures" / "gharchive_sample.jsonl",
            output_path,
            manifest_path=manifest_path,
            require_eligible_repo=True,
        )
    except ValueError as exc:
        assert "no eligible repositories" in str(exc)
    else:
        raise AssertionError("expected require_eligible_repo to fail")

    manifest = read_json(manifest_path)
    assert manifest["counts"]["records_selected"] == 3
    assert manifest["counts"]["repos_eligible"] == 0
    assert manifest["skipped_repos"][0]["repo"] == "acme/docs"


def test_github_fixture_pilot_writes_verifiable_project(tmp_path: Path):
    summary = run_github_fixture_pilot(tmp_path / "projects")
    project_dir = Path(summary["project_dir"])
    report = run_project_verifier(project_dir)
    graph = read_json(project_dir / "memory_graph.json")

    assert summary["project_id"] == "project_github_001"
    assert summary["artifacts"] == 4
    assert summary["events"] == 4
    assert summary["memories"] == 4
    assert summary["probes"] == 3
    assert report.passed is True
    assert any(memory["memory_type"] == "negative_policy_example" for memory in graph["memories"])
