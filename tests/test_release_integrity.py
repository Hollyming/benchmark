from pathlib import Path

from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack_batch
from ultra_long_benchmark.pipelines.annotation_pack import export_annotation_pack_release
from ultra_long_benchmark.pipelines.annotation_pack import export_policy_rewrite_prompts_batch
from ultra_long_benchmark.release_integrity import verify_annotation_release_integrity
from ultra_long_benchmark.shared.io import read_json, write_json


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "gharchive_multi_repo_sample.jsonl"


def test_release_integrity_verifies_hashes_splits_and_prompt_coverage(tmp_path: Path):
    release_dir, prompt_dir = _build_release_with_prompts(tmp_path)

    report = verify_annotation_release_integrity(release_dir, prompt_export_dir=prompt_dir, output_path=tmp_path / "integrity.json")

    assert report["passed"] is True
    assert report["summary"]["issues"] == 0
    assert report["summary"]["warning_codes"] == ["empty_split"]
    assert report["checks"]["manifest"]["declared_tasks"] == 8
    assert report["checks"]["prompt_exports"]["prompts"] == 8
    assert report["checks"]["splits"]["repo_disjoint"] is True
    assert read_json(tmp_path / "integrity.json")["passed"] is True


def test_release_integrity_rejects_pack_hash_mismatch(tmp_path: Path):
    release_dir, prompt_dir = _build_release_with_prompts(tmp_path)
    manifest_path = release_dir / "release_manifest.json"
    manifest = read_json(manifest_path)
    manifest["packs"][0]["content_hash"] = "0" * 64
    write_json(manifest_path, manifest)

    report = verify_annotation_release_integrity(release_dir, prompt_export_dir=prompt_dir)

    assert report["passed"] is False
    assert "pack_content_hash_mismatch" in report["summary"]["issue_codes"]


def test_release_integrity_rejects_missing_prompt_export_for_release_pack(tmp_path: Path):
    release_dir, prompt_dir = _build_release_with_prompts(tmp_path)
    report_path = prompt_dir / "rewrite_prompt_batch_report.json"
    report_json = read_json(report_path)
    removed = report_json["exports"].pop()
    report_json["summary"]["packs_total"] -= 1
    report_json["summary"]["prompts_total"] -= removed["prompts"]
    write_json(report_path, report_json)

    report = verify_annotation_release_integrity(release_dir, prompt_export_dir=prompt_dir)

    assert report["passed"] is False
    assert "prompt_export_missing_release_pack" in report["summary"]["issue_codes"]


def _build_release_with_prompts(tmp_path: Path) -> tuple[Path, Path]:
    batch_dir = tmp_path / "packs"
    release_dir = tmp_path / "release"
    prompt_dir = tmp_path / "prompt_exports"
    build_gharchive_annotation_pack_batch(FIXTURE_PATH, output_dir=batch_dir)
    export_annotation_pack_release(batch_dir, release_dir, version="test")
    export_policy_rewrite_prompts_batch(batch_dir, prompt_dir, prompt_version="test-v1")
    return release_dir, prompt_dir
