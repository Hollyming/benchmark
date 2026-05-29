from pathlib import Path

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
