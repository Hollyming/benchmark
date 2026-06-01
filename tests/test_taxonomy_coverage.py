from pathlib import Path

from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack_batch
from ultra_long_benchmark.pipelines.annotation_pack import build_projects_from_policy_rewrite_batch
from ultra_long_benchmark.pipelines.annotation_pack import validate_policy_rewrite_proposals_batch
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.shared.io import read_json, write_json
from ultra_long_benchmark.taxonomy_coverage import audit_project_release_taxonomy_coverage
from ultra_long_benchmark.taxonomy_coverage import verify_project_release_taxonomy_coverage_audit


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "gharchive_multi_repo_sample.jsonl"
PROPOSALS_PATH = ROOT / "examples" / "annotation_rewrites" / "gharchive_batch_rewrite_examples.jsonl"


def test_project_release_taxonomy_coverage_reports_github_only_scope(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    export_project_benchmark_release(project_dirs, release_dir, version="test")

    report = audit_project_release_taxonomy_coverage(release_dir, output_path=tmp_path / "taxonomy_coverage.json")

    assert report["passed"] is True
    assert report["summary"]["current_release_domain_scope"] == "github_developer_workflow_only"
    assert report["summary"]["covered_workflow_domains"] == ["github_developer_workflow"]
    assert report["checks"]["workflow_domain_coverage"]["github_developer_workflow"]["status"] == "covered"
    assert report["checks"]["workflow_domain_coverage"]["email_workflow"]["status"] == "blocked_license_privacy_manifest"
    assert report["checks"]["claim_boundary"]["multi_domain_release_ready"] is False
    assert "multi_domain_email_calendar_docs_chat_browser_office_workflow_release" in report["checks"]["claim_boundary"]["unsupported_claims_for_current_release"]
    assert "browser_web_search_workflow_release" in report["checks"]["claim_boundary"]["unsupported_claims_for_current_release"]
    assert report["checks"]["task_taxonomy_coverage"]["task_types"]
    assert read_json(tmp_path / "taxonomy_coverage.json")["summary"]["current_release_domain_scope"] == "github_developer_workflow_only"
    assert verify_project_release_taxonomy_coverage_audit(tmp_path / "taxonomy_coverage.json")["passed"] is True


def test_project_release_taxonomy_coverage_verifier_fails_when_release_changes(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    export_project_benchmark_release(project_dirs, release_dir, version="test")
    report_path = tmp_path / "taxonomy_coverage.json"
    audit_project_release_taxonomy_coverage(release_dir, output_path=report_path)
    manifest_path = release_dir / "project_release_manifest.json"
    manifest = read_json(manifest_path)
    manifest["projects"] = []
    write_json(manifest_path, manifest)

    report = verify_project_release_taxonomy_coverage_audit(report_path)

    assert report["passed"] is False
    assert "taxonomy_coverage_summary_mismatch" in report["summary"]["issue_codes"]


def test_project_release_taxonomy_coverage_can_require_multi_domain(tmp_path: Path):
    project_dirs = _build_rewrite_projects(tmp_path)
    release_dir = tmp_path / "project_release"
    export_project_benchmark_release(project_dirs, release_dir, version="test")

    report = audit_project_release_taxonomy_coverage(release_dir, require_multi_domain=True)

    assert report["passed"] is False
    assert "multi_domain_release_required" in report["summary"]["issue_codes"]
    assert report["summary"]["current_release_domain_scope"] == "github_developer_workflow_only"


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
