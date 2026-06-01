from pathlib import Path

from ultra_long_benchmark.pipelines.gharchive import select_gharchive_annotation_repos
from ultra_long_benchmark.shared.io import read_json


def test_select_gharchive_annotation_repos_balances_splits(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"

    report = select_gharchive_annotation_repos(
        fixture_path,
        output_path=tmp_path / "selection.json",
        target_repos=2,
        min_per_split=0,
    )

    assert report["passed"] is True
    assert report["summary"]["selected_repos"] == 2
    assert sum(report["summary"]["split_counts"].values()) == 2
    assert report["summary"]["candidate_count_total"] >= 2
    assert report["constraints"]["ready_for_annotation_pack_batch"] is True
    assert read_json(tmp_path / "selection.json")["summary"]["selected_repos"] == 2


def test_select_gharchive_annotation_repos_reports_split_shortfall(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"

    report = select_gharchive_annotation_repos(
        fixture_path,
        output_path=tmp_path / "selection.json",
        target_repos=2,
        min_per_split=1,
    )

    assert report["passed"] is False
    assert report["summary"]["selected_repos"] == 2
    assert any(value > 0 for value in report["summary"]["split_shortfalls"].values())
    assert read_json(tmp_path / "selection.json")["passed"] is False
