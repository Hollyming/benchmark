from pathlib import Path

from ultra_long_benchmark.pipelines.evaluation import run_project_baseline_evaluation
from ultra_long_benchmark.pipelines.evaluation import score_project_predictions
from ultra_long_benchmark.pipelines.gharchive_pilot import DEFAULT_FIXTURE_PATH as DEFAULT_GHARCHIVE_FIXTURE_PATH
from ultra_long_benchmark.pipelines.gharchive_pilot import run_gharchive_pilot
from ultra_long_benchmark.pipelines.grounded_pilot import run_manual_grounded_pilot
from ultra_long_benchmark.shared.io import read_json
from ultra_long_benchmark.shared.io import write_jsonl


def test_project_baselines_compare_oracle_and_raw_rag_on_grounded_project(tmp_path: Path):
    summary = run_manual_grounded_pilot(tmp_path / "projects")
    report_path = tmp_path / "manual_baselines.json"
    report = run_project_baseline_evaluation(Path(summary["project_dir"]), report_path, top_k=2)

    assert report_path.exists()
    assert report["project_id"] == "project_manual_001"
    oracle = report["baselines"]["oracle_policy_graph"]
    raw_rag = report["baselines"]["raw_rag"]
    no_memory = report["baselines"]["no_memory"]
    full_event_log = report["baselines"]["full_event_log"]
    temporal_raw_rag = report["baselines"]["temporal_raw_rag"]
    assert oracle["n"] == 5
    assert raw_rag["n"] == 5
    assert no_memory["n"] == 5
    assert full_event_log["n"] == 5
    assert temporal_raw_rag["n"] == 5
    assert oracle["must_include_recall"] >= raw_rag["must_include_recall"]
    assert oracle["evidence_recall"] >= raw_rag["evidence_recall"]
    assert oracle["pass_rate"] >= raw_rag["pass_rate"]
    assert "diagnostic_label_counts" in raw_rag
    assert "by_task_type" in raw_rag
    assert "by_capability" in raw_rag
    assert full_event_log["evidence_recall"] >= raw_rag["evidence_recall"]
    assert full_event_log["evidence_recall"] == 1.0
    assert no_memory["evidence_recall"] == 0.0
    assert oracle["boundary_action_recall"] > 0
    assert all(prediction["retrieved_memory_ids"] for prediction in oracle["predictions"])
    assert all(not prediction["retrieved_memory_ids"] for prediction in raw_rag["predictions"])
    assert all("diagnostics" in prediction for prediction in raw_rag["predictions"])
    assert all("passed" in prediction for prediction in raw_rag["predictions"])


def test_project_baselines_handle_gharchive_policy_probes(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    report_path = tmp_path / "gharchive_baselines.json"
    report = run_project_baseline_evaluation(Path(summary["project_dir"]), report_path, top_k=3)

    assert read_json(report_path)["project_id"] == "project_gharchive_001"
    assert report["baselines"]["oracle_policy_graph"]["n"] == 3
    assert report["baselines"]["oracle_policy_graph"]["boundary_action_recall"] >= 0.8
    assert "pass_rate" in report["baselines"]["oracle_policy_graph"]
    assert "diagnostic_label_counts" in report["baselines"]["raw_rag"]
    assert report["baselines"]["raw_rag"]["evidence_recall"] >= 0


def test_project_baselines_can_run_selected_temporal_raw_rag_only(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    report_path = tmp_path / "temporal_raw_rag.json"
    report = run_project_baseline_evaluation(
        Path(summary["project_dir"]),
        report_path,
        top_k=3,
        baseline_names=["temporal_raw_rag"],
    )

    assert report["summary"]["baseline_names"] == ["temporal_raw_rag"]
    assert set(report["baselines"]) == {"temporal_raw_rag"}
    assert report["baselines"]["temporal_raw_rag"]["n"] == 3
    assert read_json(report_path)["summary"]["baseline_names"] == ["temporal_raw_rag"]


def test_score_project_predictions_accepts_external_submission_jsonl(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    project_dir = Path(summary["project_dir"])
    predictions_path = tmp_path / "predictions.jsonl"
    write_jsonl(
        predictions_path,
        [
            {
                "prediction_id": "pred_good",
                "project_id": "project_gharchive_001",
                "probe_id": "probe_gharchive_docs_pr_actions",
                "prediction": "In GitHub, add a summary comment, request Nina review, wait for CI, and merge after CI success. Do not merge before CI succeeds or before review.",
                "retrieved_memory_ids": ["memory_gharchive_docs_pr_routing", "memory_gharchive_ci_before_merge"],
                "retrieved_event_ids": ["event_gharchive_gha_002", "event_gharchive_gha_003", "event_gharchive_gha_004", "event_gharchive_gha_005"],
                "retrieved_artifact_ids": ["artifact_gharchive_gha_002"],
            },
            {
                "prediction_id": "pred_bad",
                "project_id": "project_gharchive_001",
                "probe_id": "probe_gharchive_cross_event_ci_policy",
                "prediction": "Use the unrelated repository policy and merge before CI as default.",
                "retrieved_memory_ids": ["memory_gharchive_distractor_other_repo_refactor"],
                "retrieved_event_ids": ["event_gharchive_gha_007"],
                "retrieved_artifact_ids": [],
            },
        ],
    )

    report = score_project_predictions(project_dir, predictions_path, tmp_path / "prediction_report.json", system_name="test_system")

    assert report["system_name"] == "test_system"
    assert report["summary"]["predictions"] == 2
    assert report["summary"]["project_probes"] == 3
    assert report["summary"]["missing_predictions"] == 1
    assert report["summary"]["pass_rate"] == 0.5
    by_id = {item["prediction_id"]: item for item in report["predictions"]}
    assert by_id["pred_good"]["passed"] is True
    assert by_id["pred_bad"]["passed"] is False
    assert any(issue.startswith("violated_must_not") for issue in by_id["pred_bad"]["issues"])


def test_score_project_predictions_reports_unknown_probe(tmp_path: Path):
    summary = run_gharchive_pilot(tmp_path / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    predictions_path = tmp_path / "bad_predictions.jsonl"
    write_jsonl(
        predictions_path,
        [
            {
                "prediction_id": "pred_unknown",
                "project_id": "project_gharchive_001",
                "probe_id": "probe_missing",
                "prediction": "No matching probe.",
            }
        ],
    )

    report = score_project_predictions(Path(summary["project_dir"]), predictions_path, tmp_path / "prediction_report.json")

    assert report["summary"]["unknown_or_invalid_predictions"] == 1
    assert report["predictions"][0]["passed"] is False
    assert "unknown probe" in report["predictions"][0]["issues"][0]
