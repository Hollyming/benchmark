from pathlib import Path

from ultra_long_benchmark.paper_tables import export_paper_tables
from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack_batch
from ultra_long_benchmark.pipelines.annotation_pack import build_projects_from_policy_rewrite_batch
from ultra_long_benchmark.pipelines.annotation_pack import validate_policy_rewrite_proposals_batch
from ultra_long_benchmark.pipelines.evaluation import run_project_release_baseline_evaluation
from ultra_long_benchmark.pipelines.evaluation import score_project_release_prediction_dir
from ultra_long_benchmark.pipelines.evaluation import score_project_release_predictions
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_jsonl


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "gharchive_multi_repo_sample.jsonl"
PROPOSALS_PATH = ROOT / "examples" / "annotation_rewrites" / "gharchive_batch_rewrite_examples.jsonl"


def test_export_paper_tables_combines_baselines_and_submission_scores(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    export_project_benchmark_release(project_dirs, release_dir, version="test")
    baseline_report = tmp_path / "release_baselines.json"
    prediction_report = tmp_path / "release_predictions.json"
    predictions_path = tmp_path / "predictions.jsonl"
    run_project_release_baseline_evaluation(release_dir, baseline_report, baseline_names=["raw_rag", "oracle_policy_graph"])
    _write_oracle_like_predictions(project_dirs, predictions_path)
    score_project_release_predictions(release_dir, predictions_path, prediction_report, system_name="external_oracle_like")

    tables = export_paper_tables(
        tmp_path / "paper_tables",
        release_baseline_report=baseline_report,
        prediction_reports=[prediction_report],
    )

    assert tables["counts"]["systems"] == 3
    names = {row["system_name"] for row in tables["main_results"]}
    assert names == {"raw_rag", "oracle_policy_graph", "external_oracle_like"}
    oracle = next(row for row in tables["main_results"] if row["system_name"] == "oracle_policy_graph")
    assert oracle["micro_pass_rate"] == 1.0
    assert oracle["project_bootstrap_pass_rate_mean"] == 1.0
    assert "project_bootstrap_pass_rate_ci_low" in oracle
    assert tables["confidence_intervals"]
    assert any(row["metric"] == "boundary_action_recall" for row in tables["confidence_intervals"])
    assert tables["task_breakdown"]
    assert tables["capability_breakdown"]
    assert any(row["failure_label"] == "retrieved_but_not_applied" for row in tables["failure_breakdown"])
    assert (tmp_path / "paper_tables" / "main_results.csv").exists()
    assert (tmp_path / "paper_tables" / "main_results.md").exists()
    assert (tmp_path / "paper_tables" / "confidence_intervals.csv").exists()
    assert read_json(tmp_path / "paper_tables" / "paper_tables.json")["counts"]["systems"] == 3


def test_export_paper_tables_accepts_prediction_batch_report(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    export_project_benchmark_release(project_dirs, release_dir, version="test")
    baseline_report = tmp_path / "release_baselines.json"
    submissions_dir = tmp_path / "submissions"
    submissions_dir.mkdir()
    predictions_path = submissions_dir / "external_oracle_like.jsonl"
    run_project_release_baseline_evaluation(release_dir, baseline_report, baseline_names=["oracle_policy_graph"])
    _write_oracle_like_predictions(project_dirs, predictions_path)
    batch = score_project_release_prediction_dir(release_dir, submissions_dir, tmp_path / "scores")

    tables = export_paper_tables(
        tmp_path / "paper_tables_from_batch",
        release_baseline_report=baseline_report,
        prediction_batch_reports=[Path(batch["output_dir"]) / "prediction_scoring_batch_report.json"],
    )

    assert tables["counts"]["systems"] == 2
    assert tables["counts"]["confidence_interval_rows"] == 10
    assert {row["system_name"] for row in tables["main_results"]} == {"oracle_policy_graph", "external_oracle_like"}
    assert read_json(tmp_path / "paper_tables_from_batch" / "paper_tables.json")["counts"]["systems"] == 2


def _build_rewrite_projects(tmp_path: Path) -> list[Path]:
    batch_dir = tmp_path / "packs"
    validation_dir = tmp_path / "rewrite_validation"
    projects_dir = tmp_path / "projects"
    build_gharchive_annotation_pack_batch(FIXTURE_PATH, output_dir=batch_dir)
    validation = validate_policy_rewrite_proposals_batch(batch_dir, PROPOSALS_PATH, validation_dir)
    assert validation["passed"] is True
    batch_report = build_projects_from_policy_rewrite_batch(
        validation_dir / "batch_rewrite_validation_report.json",
        projects_dir,
        project_prefix="project_gharchive_rewrite_batch",
    )
    assert batch_report["passed"] is True
    return [Path(project["project_dir"]) for project in batch_report["projects"]]


def _write_oracle_like_predictions(project_dirs: list[Path], output_path: Path) -> None:
    rows = []
    for project_dir in project_dirs:
        project_id = read_json(project_dir / "project_profile.json")["project_id"]
        for probe in read_jsonl(project_dir / "probes.jsonl"):
            rows.append(
                {
                    "prediction_id": f"pred_{project_id}_{probe['probe_id']}",
                    "project_id": project_id,
                    "probe_id": probe["probe_id"],
                    "prediction": (
                        " ".join(probe["expected_behavior"].get("must_include", []))
                        + " do not "
                        + " ".join(probe["expected_behavior"].get("must_not_include", []))
                        + " "
                        + " ".join(_positive_boundary_terms(project_dir, probe))
                    ),
                    "retrieved_memory_ids": probe["evidence"]["positive"],
                    "retrieved_event_ids": _positive_event_ids(project_dir, probe),
                    "retrieved_artifact_ids": [],
                }
            )
    write_jsonl(output_path, rows)


def _positive_event_ids(project_dir: Path, probe: dict) -> list[str]:
    graph = read_json(project_dir / "memory_graph.json")
    memory_by_id = {memory["memory_id"]: memory for memory in graph["memories"]}
    event_ids = []
    for memory_id in probe["evidence"]["positive"]:
        event_ids.extend(memory_by_id[memory_id]["source_events"])
    return sorted(set(event_ids))


def _positive_boundary_terms(project_dir: Path, probe: dict) -> list[str]:
    graph = read_json(project_dir / "memory_graph.json")
    memory_by_id = {memory["memory_id"]: memory for memory in graph["memories"]}
    terms = []
    for memory_id in probe["evidence"]["positive"]:
        boundary = memory_by_id[memory_id].get("action_boundary") or {}
        for key in ["allowed_actions", "forbidden_actions", "requires_approval", "requires_clarification", "authorized_tools", "forbidden_tools"]:
            terms.extend(str(value).replace("_", " ") for value in boundary.get(key, []))
    return terms
