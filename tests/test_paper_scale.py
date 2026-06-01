from pathlib import Path

from ultra_long_benchmark.paper_scale import assess_release_scale
from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack_batch
from ultra_long_benchmark.pipelines.annotation_pack import export_annotation_pack_release
from ultra_long_benchmark.pipelines.annotation_pack import export_policy_rewrite_prompts_batch
from ultra_long_benchmark.pipelines.annotation_pack import summarize_gharchive_annotation_scale
from ultra_long_benchmark.pipelines.gharchive import profile_gharchive_time_windows
from ultra_long_benchmark.release_integrity import verify_annotation_release_integrity
from ultra_long_benchmark.shared.io import read_json


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "gharchive_multi_repo_sample.jsonl"


def test_paper_scale_gate_marks_small_fixture_as_not_paper_ready(tmp_path: Path):
    release_dir, prompt_dir, scale_summary, window_report, integrity_report = _build_reports(tmp_path)

    report = assess_release_scale(
        release_dir,
        profile="paper",
        scale_summary_path=scale_summary,
        window_report_path=window_report,
        release_integrity_report_path=integrity_report,
        output_path=tmp_path / "paper_scale.json",
    )

    assert report["passed"] is False
    assert "min_repos_not_met" in report["summary"]["issue_codes"]
    assert "required_candidate_types_missing" not in report["summary"]["issue_codes"]
    assert report["checks"]["release"]["candidate_types"]["contextual_policy"] == 2
    assert "release_integrity_empty_split" in report["summary"]["issue_codes"]
    assert report["checks"]["release"]["repos"] == 2
    assert read_json(tmp_path / "paper_scale.json")["passed"] is False


def test_fixture_scale_profile_accepts_small_engineering_fixture(tmp_path: Path):
    release_dir, _prompt_dir, scale_summary, window_report, integrity_report = _build_reports(tmp_path)

    report = assess_release_scale(
        release_dir,
        profile="fixture",
        scale_summary_path=scale_summary,
        window_report_path=window_report,
        release_integrity_report_path=integrity_report,
    )

    assert report["passed"] is True
    assert report["summary"]["issues"] == 0
    assert "release_integrity_warning_empty_split" in report["summary"]["warning_codes"]


def _build_reports(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    batch_dir = tmp_path / "packs"
    release_dir = tmp_path / "release"
    prompt_dir = tmp_path / "prompt_exports"
    scale_summary = tmp_path / "scale_summary.json"
    window_report = tmp_path / "window_report.json"
    integrity_report = tmp_path / "integrity.json"
    build_gharchive_annotation_pack_batch(FIXTURE_PATH, output_dir=batch_dir)
    export_annotation_pack_release(batch_dir, release_dir, version="test")
    export_policy_rewrite_prompts_batch(batch_dir, prompt_dir, prompt_version="test-v1")
    summarize_gharchive_annotation_scale(batch_dir, release_dir=release_dir, output_path=scale_summary)
    profile_gharchive_time_windows(FIXTURE_PATH, window_days=7, output_path=window_report)
    verify_annotation_release_integrity(release_dir, prompt_export_dir=prompt_dir, output_path=integrity_report)
    return release_dir, prompt_dir, scale_summary, window_report, integrity_report
