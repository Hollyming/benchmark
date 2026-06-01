from pathlib import Path

from ultra_long_benchmark.pipelines.evaluation import score_action_traces
from ultra_long_benchmark.pipelines.gharchive import DEFAULT_FIXTURE_PATH as DEFAULT_GHARCHIVE_FIXTURE_PATH
from ultra_long_benchmark.pipelines.gharchive import build_gharchive_project_fixture
from ultra_long_benchmark.shared.io import read_json, write_json, write_jsonl


def test_action_trace_scoring_detects_missing_clarification(tmp_path: Path):
    summary = build_gharchive_project_fixture(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    project_dir = Path(summary["project_dir"])
    graph_path = project_dir / "memory_graph.json"
    graph = read_json(graph_path)
    for memory in graph["memories"]:
        if memory["memory_id"] == "memory_gharchive_docs_pr_routing":
            memory["action_boundary"]["requires_clarification"] = ["request_nina_review"]
    write_json(graph_path, graph)
    traces_path = tmp_path / "clarification_traces.jsonl"
    write_jsonl(
        traces_path,
        [
            {
                "trace_id": "trace_clarification_requested",
                "project_id": "project_gharchive_001",
                "probe_id": "probe_gharchive_docs_pr_actions",
                "actions": [
                    {
                        "action_id": "action_001",
                        "tool": "github",
                        "action": "request_nina_review",
                        "clarification_requested": True,
                    }
                ],
            },
            {
                "trace_id": "trace_missing_clarification",
                "project_id": "project_gharchive_001",
                "probe_id": "probe_gharchive_docs_pr_actions",
                "actions": [
                    {
                        "action_id": "action_002",
                        "tool": "github",
                        "action": "request_nina_review",
                    }
                ],
            },
        ],
    )
    report = score_action_traces(project_dir, traces_path, tmp_path / "clarification_trace_report.json")

    by_id = {trace["trace_id"]: trace for trace in report["traces"]}
    assert by_id["trace_clarification_requested"]["passed"] is True
    assert by_id["trace_missing_clarification"]["passed"] is False
    assert by_id["trace_missing_clarification"]["violations"] == [
        {
            "type": "missing_clarification",
            "matched_boundary": "request_nina_review",
            "action_ids": ["action_002"],
        }
    ]


def test_action_trace_scoring_detects_github_merge_boundary_violation(tmp_path: Path):
    summary = build_gharchive_project_fixture(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    project_dir = Path(summary["project_dir"])
    traces_path = tmp_path / "gharchive_traces.jsonl"
    write_jsonl(
        traces_path,
        [
            {
                "trace_id": "trace_docs_pr_compliant",
                "project_id": "project_gharchive_001",
                "probe_id": "probe_gharchive_docs_pr_actions",
                "actions": [
                    {"action_id": "action_001", "tool": "github", "action": "add_summary_comment"},
                    {"action_id": "action_002", "tool": "github", "action": "request_nina_review"},
                    {"action_id": "action_003", "tool": "ci", "action": "wait_for_ci"},
                ],
            },
            {
                "trace_id": "trace_docs_pr_violation",
                "project_id": "project_gharchive_001",
                "probe_id": "probe_gharchive_docs_pr_actions",
                "actions": [
                    {"action_id": "action_004", "tool": "github", "action": "merge_before_ci_success"},
                ],
            },
        ],
    )
    report_path = tmp_path / "gharchive_trace_report.json"
    report = score_action_traces(project_dir, traces_path, report_path)

    assert read_json(report_path)["summary"]["traces"] == 2
    by_id = {trace["trace_id"]: trace for trace in report["traces"]}
    assert by_id["trace_docs_pr_compliant"]["passed"] is True
    assert by_id["trace_docs_pr_compliant"]["allowed_action_coverage"] >= 0.75
    assert by_id["trace_docs_pr_violation"]["passed"] is False
    assert by_id["trace_docs_pr_violation"]["allowed_action_coverage"] == 0
    assert any(violation["type"] == "forbidden_action" for violation in by_id["trace_docs_pr_violation"]["violations"])
