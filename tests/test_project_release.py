from pathlib import Path

from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack_batch
from ultra_long_benchmark.pipelines.annotation_pack import build_projects_from_policy_rewrite_batch
from ultra_long_benchmark.pipelines.annotation_pack import validate_policy_rewrite_proposals_batch
from ultra_long_benchmark.pipelines.evaluation import run_project_release_baseline_evaluation
from ultra_long_benchmark.pipelines.evaluation import score_project_release_action_traces
from ultra_long_benchmark.pipelines.evaluation import score_project_release_prediction_dir
from ultra_long_benchmark.pipelines.evaluation import score_project_release_predictions
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.project_release import export_project_submission_inputs
from ultra_long_benchmark.project_release import validate_project_prediction_submission
from ultra_long_benchmark.project_release import verify_project_benchmark_release
from ultra_long_benchmark.project_release import verify_project_submission_inputs
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "gharchive_multi_repo_sample.jsonl"
PROPOSALS_PATH = ROOT / "examples" / "annotation_rewrites" / "gharchive_batch_rewrite_examples.jsonl"


def test_project_benchmark_release_exports_verifier_checked_projects(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"

    manifest = export_project_benchmark_release(project_dirs, release_dir, version="test")
    report = verify_project_benchmark_release(release_dir, output_path=tmp_path / "project_release_integrity.json")

    assert manifest["counts"]["projects"] == 2
    assert manifest["counts"]["probes"] == 8
    assert report["passed"] is True
    assert report["summary"]["issues"] == 0
    assert report["checks"]["manifest"]["declared_probes"] == 8
    assert report["checks"]["splits"]["project_disjoint"] is True
    assert read_json(tmp_path / "project_release_integrity.json")["passed"] is True


def test_project_benchmark_release_allows_validated_llm_assisted_projects(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"

    manifest = export_project_benchmark_release(
        project_dirs,
        release_dir,
        version="test",
        llm_generation_performed=True,
        construction="gharchive_rewrite_validated_policy_project",
    )
    report = verify_project_benchmark_release(release_dir)

    assert manifest["constraints"]["llm_generation_performed"] is True
    assert manifest["constraints"]["llm_generation_validated"] is True
    assert manifest["constraints"]["construction"] == "gharchive_rewrite_validated_policy_project"
    assert report["passed"] is True


def test_project_benchmark_release_splits_rewrite_projects_by_repo(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"

    manifest = export_project_benchmark_release(project_dirs, release_dir, version="test")

    for project in manifest["projects"]:
        project_dir = Path(project["project_dir"])
        profile = read_json(project_dir / "project_profile.json")
        repo = profile["user_profile"]["repo"]
        assert project["split_key"] == repo


def test_project_benchmark_release_rejects_project_file_hash_mismatch(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    export_project_benchmark_release(project_dirs, release_dir, version="test")
    manifest_path = release_dir / "project_release_manifest.json"
    manifest = read_json(manifest_path)
    manifest["projects"][0]["file_hashes"]["probes.jsonl"] = "0" * 64
    write_json(manifest_path, manifest)

    report = verify_project_benchmark_release(release_dir)

    assert report["passed"] is False
    assert "project_file_hash_mismatch" in report["summary"]["issue_codes"]


def test_project_submission_inputs_export_no_gold_pack_for_external_methods(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    input_dir = tmp_path / "submission_inputs"
    export_project_benchmark_release(project_dirs, release_dir, version="test")

    manifest = export_project_submission_inputs(release_dir, input_dir)
    report = verify_project_submission_inputs(input_dir, output_path=tmp_path / "submission_input_report.json")

    assert manifest["counts"]["projects"] == 2
    assert manifest["counts"]["probes"] == 8
    assert manifest["constraints"]["contains_gold_memory_graph"] is False
    assert report["passed"] is True
    probes = read_jsonl(input_dir / "probes.jsonl")
    assert len(probes) == 8
    assert all("expected_behavior" not in probe for probe in probes)
    assert all("evidence" not in probe for probe in probes)
    assert all(probe["query"] for probe in probes)
    template = read_jsonl(input_dir / "prediction_template.jsonl")
    assert len(template) == 8
    assert all(row["prediction"] == "" for row in template)
    assert read_json(tmp_path / "submission_input_report.json")["passed"] is True


def test_project_submission_inputs_can_harden_probe_queries_without_gold_leakage(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    input_dir = tmp_path / "hardened_submission_inputs"
    export_project_benchmark_release(project_dirs, release_dir, version="test")

    manifest = export_project_submission_inputs(release_dir, input_dir, harden_probe_queries=True)
    report = verify_project_submission_inputs(input_dir)

    assert manifest["constraints"]["probe_queries_hardened"] is True
    assert manifest["query_hardening"]["enabled"] is True
    assert report["passed"] is True
    release_probe = read_jsonl(project_dirs[0] / "probes.jsonl")[0]
    hardened_probe = read_jsonl(input_dir / "probes.jsonl")[0]
    assert hardened_probe["probe_id"] == release_probe["probe_id"]
    assert hardened_probe["query"] != release_probe["query"]
    assert hardened_probe["metadata"]["query_hardened"] is True
    assert "expected_behavior" not in hardened_probe
    assert "evidence" not in hardened_probe


def test_project_submission_input_verifier_rejects_gold_leakage(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    input_dir = tmp_path / "submission_inputs"
    export_project_benchmark_release(project_dirs, release_dir, version="test")
    export_project_submission_inputs(release_dir, input_dir)
    probes = read_jsonl(input_dir / "probes.jsonl")
    probes[0]["expected_behavior"] = {"must_include": ["leaked"]}
    write_jsonl(input_dir / "probes.jsonl", probes)

    report = verify_project_submission_inputs(input_dir)

    assert report["passed"] is False
    assert "submission_input_gold_key_present" in report["summary"]["issue_codes"]


def test_score_project_release_predictions_aggregates_cross_project_submission(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    export_project_benchmark_release(project_dirs, release_dir, version="test")
    predictions_path = tmp_path / "release_predictions.jsonl"
    rows = []
    for project_dir in project_dirs:
        project_id = read_json(project_dir / "project_profile.json")["project_id"]
        for probe in read_jsonl(project_dir / "probes.jsonl"):
            boundary_terms = _positive_boundary_terms(project_dir, probe)
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
                        + " ".join(boundary_terms)
                    ),
                    "retrieved_memory_ids": probe["evidence"]["positive"],
                    "retrieved_event_ids": _positive_event_ids(project_dir, probe),
                    "retrieved_artifact_ids": [],
                }
            )
    write_jsonl(predictions_path, rows)

    report = score_project_release_predictions(release_dir, predictions_path, tmp_path / "release_prediction_report.json", system_name="test_system")

    assert report["system_name"] == "test_system"
    assert report["summary"]["projects"] == 2
    assert report["summary"]["release_probes"] == 8
    assert report["summary"]["predictions"] == 8
    assert report["summary"]["probe_coverage"] == 1.0
    assert report["summary"]["extra_predictions"] == 0
    assert report["summary"]["micro_pass_rate"] == 1.0
    assert report["summary"]["diagnostic_label_counts"] == {}
    assert report["summary"]["task_type_macro_pass_rate"] == 1.0
    assert report["summary"]["capability_macro_pass_rate"] == 1.0
    assert "tool_action_policy_alignment" in report["summary"]["by_task_type"]
    assert "workflow_boundary_respect" in report["summary"]["by_capability"]
    assert all(not prediction["diagnostics"]["labels"] for project in report["projects"] for prediction in project["predictions"])
    assert read_json(tmp_path / "release_prediction_report.json")["summary"]["projects"] == 2


def test_score_project_release_action_traces_aggregates_cross_project_traces(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    export_project_benchmark_release(project_dirs, release_dir, version="test")
    traces_path = tmp_path / "release_action_traces.jsonl"
    first_project_id = read_json(project_dirs[0] / "project_profile.json")["project_id"]
    second_project_id = read_json(project_dirs[1] / "project_profile.json")["project_id"]
    first_probe = read_jsonl(project_dirs[0] / "probes.jsonl")[0]
    second_probe = read_jsonl(project_dirs[1] / "probes.jsonl")[0]
    write_jsonl(
        traces_path,
        [
            {
                "trace_id": "trace_first_project_pass",
                "project_id": first_project_id,
                "probe_id": first_probe["probe_id"],
                "actions": [
                    {"action_id": "action_001", "tool": "github", "action": "add_summary_comment"},
                    {"action_id": "action_002", "tool": "github", "action": "request_nina_review"},
                ],
            },
            {
                "trace_id": "trace_second_project_fail",
                "project_id": second_project_id,
                "probe_id": second_probe["probe_id"],
                "actions": [{"action_id": "action_003", "tool": "github", "action": "merge_before_review"}],
            },
            {
                "trace_id": "trace_absent_project",
                "project_id": "project_absent_from_release",
                "probe_id": "probe_absent",
                "actions": [{"action_id": "action_004", "tool": "github", "action": "noop"}],
            },
        ],
    )

    report = score_project_release_action_traces(release_dir, traces_path, tmp_path / "release_action_trace_report.json", system_name="trace_system")

    assert report["system_name"] == "trace_system"
    assert report["summary"]["projects"] == 2
    assert report["summary"]["release_probes"] == 8
    assert report["summary"]["traces"] == 3
    assert report["summary"]["scored_traces"] == 2
    assert report["summary"]["extra_traces"] == 1
    assert report["summary"]["passed"] == 1
    assert report["summary"]["project_coverage"] == 1.0
    assert report["summary"]["probe_coverage"] == 0.25
    assert report["summary"]["boundary_violation_rate"] == 0.6667
    assert report["extra_project_ids"] == ["project_absent_from_release"]
    by_project = {project["project_id"]: project for project in report["projects"]}
    assert by_project[first_project_id]["summary"]["passed"] == 1
    assert by_project[second_project_id]["summary"]["passed"] == 0
    assert any(
        violation["type"] == "forbidden_action"
        for trace in by_project[second_project_id]["traces"]
        for violation in trace["violations"]
    )
    assert read_json(tmp_path / "release_action_trace_report.json")["summary"]["projects"] == 2


def test_validate_project_prediction_submission_checks_coverage_before_scoring(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    export_project_benchmark_release(project_dirs, release_dir, version="test")
    predictions_path = tmp_path / "release_predictions.jsonl"
    rows = []
    for project_dir in project_dirs:
        project_id = read_json(project_dir / "project_profile.json")["project_id"]
        for probe in read_jsonl(project_dir / "probes.jsonl"):
            rows.append(
                {
                    "prediction_id": f"pred_{project_id}_{probe['probe_id']}",
                    "project_id": project_id,
                    "probe_id": probe["probe_id"],
                    "prediction": "Follow the user's grounded policy and preserve action boundaries.",
                    "retrieved_memory_ids": [],
                    "retrieved_event_ids": [],
                    "retrieved_artifact_ids": [],
                }
            )
    write_jsonl(predictions_path, rows)

    report = validate_project_prediction_submission(release_dir, predictions_path, output_path=tmp_path / "submission_validation.json")

    assert report["passed"] is True
    assert report["checks"]["coverage"]["release_probes"] == 8
    assert report["checks"]["coverage"]["probe_coverage"] == 1.0
    assert report["summary"]["issue_codes"] == []
    assert read_json(tmp_path / "submission_validation.json")["passed"] is True


def test_validate_project_prediction_submission_rejects_invalid_or_partial_jsonl(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    export_project_benchmark_release(project_dirs, release_dir, version="test")
    first_project = project_dirs[0]
    first_project_id = read_json(first_project / "project_profile.json")["project_id"]
    first_probe = read_jsonl(first_project / "probes.jsonl")[0]
    predictions_path = tmp_path / "bad_release_predictions.jsonl"
    write_jsonl(
        predictions_path,
        [
            {
                "prediction_id": "duplicate_pred",
                "project_id": first_project_id,
                "probe_id": first_probe["probe_id"],
                "prediction": "",
            },
            {
                "prediction_id": "duplicate_pred",
                "project_id": first_project_id,
                "probe_id": first_probe["probe_id"],
                "prediction": "duplicate probe output",
            },
            {
                "prediction_id": "unknown_project",
                "project_id": "project_not_in_release",
                "probe_id": "probe_missing",
                "prediction": "unknown project output",
            },
            {
                "prediction_id": "schema_bad",
                "project_id": first_project_id,
                "prediction": "missing probe id",
            },
        ],
    )

    report = validate_project_prediction_submission(release_dir, predictions_path)

    assert report["passed"] is False
    issue_codes = set(report["summary"]["issue_codes"])
    assert "prediction_submission_empty_prediction" in issue_codes
    assert "prediction_submission_duplicate_prediction_id" in issue_codes
    assert "prediction_submission_duplicate_probe" in issue_codes
    assert "prediction_submission_unknown_project" in issue_codes
    assert "prediction_submission_schema_invalid" in issue_codes
    assert "prediction_submission_missing_probes" in issue_codes
    assert report["checks"]["coverage"]["probe_coverage"] < 1.0


def test_score_project_release_predictions_reports_failure_diagnostics(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    export_project_benchmark_release(project_dirs, release_dir, version="test")
    predictions_path = tmp_path / "bad_predictions.jsonl"
    rows = []
    for project_dir in project_dirs:
        project_id = read_json(project_dir / "project_profile.json")["project_id"]
        for probe in read_jsonl(project_dir / "probes.jsonl"):
            rows.append(
                {
                    "prediction_id": f"bad_{project_id}_{probe['probe_id']}",
                    "project_id": project_id,
                    "probe_id": probe["probe_id"],
                    "prediction": "I found the relevant event history, but I will take the action without applying the policy boundary.",
                    "retrieved_memory_ids": [],
                    "retrieved_event_ids": _positive_event_ids(project_dir, probe),
                    "retrieved_artifact_ids": [],
                }
            )
    write_jsonl(predictions_path, rows)

    report = score_project_release_predictions(release_dir, predictions_path, tmp_path / "diagnostic_report.json", system_name="bad_system")

    labels = report["summary"]["diagnostic_label_counts"]
    assert labels["retrieved_but_not_applied"] == 8
    assert labels["action_boundary_missing"] >= 1
    assert labels["negative_example_stored"] >= 1
    assert report["summary"]["task_type_macro_pass_rate"] < 1.0
    assert report["summary"]["by_task_type"]["negative_example_storage_gating"]["diagnostic_label_counts"]["negative_example_stored"] >= 1
    assert any(
        "retrieved_but_not_applied" in prediction["diagnostics"]["labels"]
        for project in report["projects"]
        for prediction in project["predictions"]
    )


def test_score_project_release_prediction_dir_scores_multiple_submission_files(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    export_project_benchmark_release(project_dirs, release_dir, version="test")
    submissions_dir = tmp_path / "submissions"
    submissions_dir.mkdir()
    good_path = submissions_dir / "oracle_like.jsonl"
    bad_path = submissions_dir / "bad_policy.jsonl"
    good_rows = []
    bad_rows = []
    for project_dir in project_dirs:
        project_id = read_json(project_dir / "project_profile.json")["project_id"]
        for probe in read_jsonl(project_dir / "probes.jsonl"):
            good_rows.append(
                {
                    "prediction_id": f"good_{project_id}_{probe['probe_id']}",
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
            bad_rows.append(
                {
                    "prediction_id": f"bad_{project_id}_{probe['probe_id']}",
                    "project_id": project_id,
                    "probe_id": probe["probe_id"],
                    "prediction": "I will act without applying the user's policy boundary.",
                    "retrieved_memory_ids": [],
                    "retrieved_event_ids": _positive_event_ids(project_dir, probe),
                    "retrieved_artifact_ids": [],
                }
            )
    write_jsonl(good_path, good_rows)
    write_jsonl(bad_path, bad_rows)

    batch = score_project_release_prediction_dir(release_dir, submissions_dir, tmp_path / "scores", system_name_prefix="candidate")

    assert batch["summary"]["systems"] == 2
    assert set(batch["summary"]["micro_pass_rates"]) == {"candidate_bad_policy", "candidate_oracle_like"}
    assert batch["summary"]["micro_pass_rates"]["candidate_oracle_like"] == 1.0
    assert batch["summary"]["micro_pass_rates"]["candidate_bad_policy"] < 1.0
    assert (tmp_path / "scores" / "candidate_oracle_like_score.json").exists()
    assert read_json(tmp_path / "scores" / "prediction_scoring_batch_report.json")["summary"]["systems"] == 2


def test_project_release_baselines_aggregate_micro_and_macro_metrics(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    export_project_benchmark_release(project_dirs, release_dir, version="test")

    report = run_project_release_baseline_evaluation(
        release_dir,
        tmp_path / "release_baselines.json",
        baseline_names=["raw_rag", "oracle_policy_graph"],
    )

    assert report["summary"]["projects"] == 2
    assert report["summary"]["probes"] == 8
    assert report["summary"]["baseline_names"] == ["raw_rag", "oracle_policy_graph"]
    assert "micro_pass_rate" in report["summary"]["baselines"]["raw_rag"]
    assert "diagnostic_label_counts" in report["summary"]["baselines"]["raw_rag"]
    assert "by_task_type" in report["summary"]["baselines"]["raw_rag"]
    assert "capability_macro_pass_rate" in report["summary"]["baselines"]["oracle_policy_graph"]
    assert report["summary"]["baselines"]["oracle_policy_graph"]["micro_boundary_action_recall"] >= report["summary"]["baselines"]["raw_rag"]["micro_boundary_action_recall"]
    assert report["summary"]["baselines"]["oracle_policy_graph"]["micro_evidence_recall"] >= report["summary"]["baselines"]["raw_rag"]["micro_evidence_recall"]
    assert read_json(tmp_path / "release_baselines.json")["summary"]["projects"] == 2


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
