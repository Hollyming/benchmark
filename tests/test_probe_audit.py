from pathlib import Path

from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack_batch
from ultra_long_benchmark.pipelines.annotation_pack import build_projects_from_policy_rewrite_batch
from ultra_long_benchmark.pipelines.annotation_pack import validate_policy_rewrite_proposals_batch
from ultra_long_benchmark.probe_audit import audit_project_release_probe_leakage
from ultra_long_benchmark.probe_audit import audit_submission_input_probe_leakage
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.project_release import export_project_submission_inputs
from ultra_long_benchmark.shared.io import read_json


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "gharchive_multi_repo_sample.jsonl"
PROPOSALS_PATH = ROOT / "examples" / "annotation_rewrites" / "gharchive_batch_rewrite_examples.jsonl"


def test_project_release_probe_leakage_audit_reports_overlap_risk(tmp_path: Path):
    batch_dir = tmp_path / "annotation_packs"
    validation_dir = tmp_path / "validation"
    project_batch_dir = tmp_path / "projects"
    release_dir = tmp_path / "release"
    build_gharchive_annotation_pack_batch(FIXTURE_PATH, output_dir=batch_dir, repos=["acme/docs", "acme/api"], pack_prefix="test_pack")
    validation = validate_policy_rewrite_proposals_batch(batch_dir, PROPOSALS_PATH, validation_dir)
    project_report = build_projects_from_policy_rewrite_batch(
        validation_dir / "batch_rewrite_validation_report.json",
        project_batch_dir,
        project_prefix="project_probe_audit",
    )
    export_project_benchmark_release([Path(project["project_dir"]) for project in project_report["projects"]], release_dir)

    report = audit_project_release_probe_leakage(release_dir, output_path=tmp_path / "probe_leakage.json")

    assert report["summary"]["probes"] == validation["summary"]["proposals_total"]
    assert "mean_expected_overlap" in report["summary"]
    assert "risk_by_task_type" in report
    assert read_json(tmp_path / "probe_leakage.json")["summary"]["probes"] == validation["summary"]["proposals_total"]


def test_submission_input_probe_leakage_audit_uses_release_gold_without_exposing_it(tmp_path: Path):
    batch_dir = tmp_path / "annotation_packs"
    validation_dir = tmp_path / "validation"
    project_batch_dir = tmp_path / "projects"
    release_dir = tmp_path / "release"
    input_dir = tmp_path / "hardened_inputs"
    build_gharchive_annotation_pack_batch(FIXTURE_PATH, output_dir=batch_dir, repos=["acme/docs", "acme/api"], pack_prefix="test_pack")
    validation = validate_policy_rewrite_proposals_batch(batch_dir, PROPOSALS_PATH, validation_dir)
    project_report = build_projects_from_policy_rewrite_batch(
        validation_dir / "batch_rewrite_validation_report.json",
        project_batch_dir,
        project_prefix="project_probe_audit",
    )
    export_project_benchmark_release([Path(project["project_dir"]) for project in project_report["projects"]], release_dir)
    export_project_submission_inputs(release_dir, input_dir, harden_probe_queries=True)

    report = audit_submission_input_probe_leakage(release_dir, input_dir, output_path=tmp_path / "hardened_probe_leakage.json")

    assert report["audited_input"] == "submission_input_probe_queries"
    assert report["summary"]["probes"] == validation["summary"]["proposals_total"]
    assert report["summary"]["missing_gold_keys"] == 0
    assert "risk_by_capability" in report
    assert read_json(tmp_path / "hardened_probe_leakage.json")["input_dir"] == str(input_dir)
