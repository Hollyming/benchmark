from pathlib import Path

from ultra_long_benchmark.pipelines.github_fixture import DEFAULT_FIXTURE_PATH, run_github_fixture_pilot
from ultra_long_benchmark.pipelines.source_adapters import GitHubIssueCIAdapter
from ultra_long_benchmark.pipelines.verifier import run_project_verifier
from ultra_long_benchmark.shared.io import read_json


def test_github_issue_ci_adapter_normalizes_fixture_records():
    result = GitHubIssueCIAdapter(DEFAULT_FIXTURE_PATH).load()

    assert result.project_profile.project_id == "project_github_001"
    assert len(result.artifacts) == 4
    assert len(result.events) == 4
    assert any(event.invalidates for event in result.events)
    assert {artifact.artifact_type for artifact in result.artifacts} >= {"github_issue", "ci_log", "patch_diff", "review_comment"}
    artifact_ids = {artifact.artifact_id for artifact in result.artifacts}
    assert {artifact_id for event in result.events for artifact_id in event.artifacts} <= artifact_ids


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
    assert any(memory["memory_type"] == "negative_evidence" for memory in graph["memories"])
