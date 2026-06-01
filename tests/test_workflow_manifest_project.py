from pathlib import Path
import subprocess
import sys

import pytest

from ultra_long_benchmark.pipelines.evaluation import run_project_release_baseline_evaluation
from ultra_long_benchmark.pipelines.enron_email_manifest import build_enron_email_workflow_manifest
from ultra_long_benchmark.pipelines.workflow_manifest_project import build_project_from_workflow_manifest
from ultra_long_benchmark.pipelines.workflow_manifest_project import preflight_workflow_manifest_release
from ultra_long_benchmark.pipelines.workflow_manifest_project import preflight_workflow_manifest_release_batch
from ultra_long_benchmark.pipelines.workflow_manifest_project import verify_workflow_manifest_preflight_batch_report
from ultra_long_benchmark.pipelines.workflow_manifest_project import verify_workflow_manifest_preflight_report
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.project_release import export_project_submission_inputs
from ultra_long_benchmark.project_release import verify_project_benchmark_release
from ultra_long_benchmark.project_release import verify_project_submission_inputs
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_json

CALENDAR_PROJECT_MANIFEST_FIXTURE = Path("tests/fixtures/calendar_workflow_project_manifest.json")
EMAIL_WORKFLOW_MANIFEST_FIXTURE = Path("tests/fixtures/email_workflow_project_manifest.json")
WORKFLOW_PROJECT_MANIFEST_FIXTURES = [
    (CALENDAR_PROJECT_MANIFEST_FIXTURE, "calendar_workflow", "calendar_workflow_only", "project_calendar_fixture_001"),
    (Path("tests/fixtures/docs_workflow_project_manifest.json"), "docs_workflow", "docs_workflow_only", "project_docs_fixture_001"),
    (Path("tests/fixtures/chat_workflow_project_manifest.json"), "chat_workflow", "chat_workflow_only", "project_chat_fixture_001"),
    (Path("tests/fixtures/browser_web_workflow_project_manifest.json"), "browser_web_workflow", "browser_web_workflow_only", "project_browser_web_fixture_001"),
]


def test_build_project_from_workflow_manifest_writes_verifier_checked_project_and_release(tmp_path: Path):
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    report_path = tmp_path / "calendar_project_report.json"

    report = build_project_from_workflow_manifest(manifest_path, tmp_path / "projects", output_report_path=report_path)

    project_dir = Path(report["project_dir"])
    assert report["passed"] is True
    assert report["domain"] == "calendar_workflow"
    assert report["summary"]["verifier_passed"] is True
    assert report["summary"]["probes"] == 3
    assert report["constraints"]["llm_generation_performed"] is False
    assert report["constraints"]["release_ready_claim"] is False
    assert read_json(report_path)["passed"] is True
    assert read_json(project_dir / "source_manifest.json")["construction"] == "manifest_first_reviewed_workflow_project"
    assert "[REDACTED_EMAIL]" in (project_dir / "events.jsonl").read_text(encoding="utf-8")
    assert "assistant@example.com" not in (project_dir / "events.jsonl").read_text(encoding="utf-8")

    release_dir = tmp_path / "release"
    export_project_benchmark_release(
        [project_dir],
        release_dir,
        dataset_name="calendar_workflow_fixture_release",
        construction="manifest_first_reviewed_workflow_project",
    )
    release_report = verify_project_benchmark_release(release_dir)
    assert release_report["passed"] is True

    input_dir = tmp_path / "submission_inputs"
    input_manifest = export_project_submission_inputs(release_dir, input_dir)
    input_report = verify_project_submission_inputs(input_dir)
    assert input_manifest["constraints"]["contains_gold_memory_graph"] is False
    assert input_report["passed"] is True
    assert all("expected_behavior" not in probe for probe in read_jsonl(input_dir / "probes.jsonl"))

    baseline_report = run_project_release_baseline_evaluation(
        release_dir,
        tmp_path / "calendar_release_baselines.json",
        baseline_names=["raw_rag", "oracle_policy_graph"],
    )
    assert baseline_report["summary"]["projects"] == 1
    assert baseline_report["summary"]["probes"] == 3


def test_email_workflow_project_fixture_preflight_builds_non_github_domain(tmp_path: Path):
    report_path = tmp_path / "email_preflight" / "workflow_manifest_release_preflight.json"

    report = preflight_workflow_manifest_release(
        EMAIL_WORKFLOW_MANIFEST_FIXTURE,
        tmp_path / "email_preflight",
        output_report_path=report_path,
        harden_probe_queries=True,
    )

    assert report["passed"] is True
    assert report["domain"] == "email_workflow"
    assert report["summary"]["release_scope"] == "email_workflow_only"
    assert report["summary"]["covered_workflow_domains"] == ["email_workflow"]
    assert report["summary"]["probes"] == 3
    assert verify_workflow_manifest_preflight_report(report_path)["passed"] is True


def test_build_enron_email_manifest_from_tiny_tarball_and_preflight(tmp_path: Path):
    tarball_path = tmp_path / "enron_tiny.tar.gz"
    _write_tiny_enron_tarball(tarball_path)
    manifest_path = tmp_path / "enron_email_manifest.json"

    build_report = build_enron_email_workflow_manifest(
        tarball_path,
        manifest_path,
        max_records=6,
        max_body_chars=500,
    )
    preflight_report = preflight_workflow_manifest_release(
        manifest_path,
        tmp_path / "enron_preflight",
        output_report_path=tmp_path / "enron_preflight" / "workflow_manifest_release_preflight.json",
        harden_probe_queries=True,
    )

    manifest = read_json(manifest_path)
    assert build_report["passed"] is True
    assert manifest["source_dataset"] == "cmu_enron_email_dataset_redacted_slice"
    assert manifest["synthetic_context"] is False
    assert len(manifest["records"]) == 3
    assert preflight_report["passed"] is True
    assert preflight_report["domain"] == "email_workflow"
    assert preflight_report["summary"]["release_scope"] == "email_workflow_only"
    assert preflight_report["summary"]["probes"] == 3


def test_build_project_from_workflow_manifest_cli(tmp_path: Path):
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    report_path = tmp_path / "calendar_project_report.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ultra_long_benchmark.cli",
            "build-project-from-workflow-manifest",
            str(manifest_path),
            "--output-dir",
            str(tmp_path / "projects"),
            "--report",
            str(report_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "workflow manifest project built" in completed.stdout
    assert read_json(report_path)["passed"] is True


def test_preflight_workflow_manifest_release_runs_offline_release_checks(tmp_path: Path):
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    report_path = tmp_path / "preflight" / "workflow_manifest_release_preflight.json"

    report = preflight_workflow_manifest_release(
        manifest_path,
        tmp_path / "preflight",
        output_report_path=report_path,
        harden_probe_queries=True,
    )

    assert report["passed"] is True
    assert report["domain"] == "calendar_workflow"
    assert report["summary"]["release_scope"] == "calendar_workflow_only"
    assert report["summary"]["covered_workflow_domains"] == ["calendar_workflow"]
    assert report["summary"]["baselines"] == ["raw_rag", "oracle_policy_graph"]
    assert report["constraints"]["llm_generation_performed"] is False
    assert report["constraints"]["release_ready_claim"] is False
    assert report["checks"]["project_release"]["status"] == "pass"
    assert report["checks"]["submission_inputs"]["status"] == "pass"
    assert report["checks"]["taxonomy_coverage"]["status"] == "pass"
    assert Path(report["artifacts"]["release_dir"]).exists()
    assert Path(report["artifacts"]["submission_input_dir"]).exists()
    assert read_json(report_path)["passed"] is True
    assert read_json(Path(report["artifacts"]["submission_input_dir"]) / "submission_manifest.json")["constraints"]["probe_queries_hardened"] is True
    assert report["artifact_records"]["release_dir"]["sha256"]
    assert verify_workflow_manifest_preflight_report(report_path)["passed"] is True


def test_preflight_workflow_manifest_release_cli(tmp_path: Path):
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    report_path = tmp_path / "preflight_report.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ultra_long_benchmark.cli",
            "preflight-workflow-manifest-release",
            str(manifest_path),
            "--output-dir",
            str(tmp_path / "preflight"),
            "--report",
            str(report_path),
            "--baseline",
            "oracle_policy_graph",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "workflow manifest release preflight" in completed.stdout
    report = read_json(report_path)
    assert report["passed"] is True
    assert report["summary"]["baselines"] == ["oracle_policy_graph"]


@pytest.mark.parametrize(("fixture_path", "domain", "release_scope", "project_id"), WORKFLOW_PROJECT_MANIFEST_FIXTURES)
def test_preflight_workflow_manifest_release_cli_with_checked_in_fixtures(
    tmp_path: Path,
    fixture_path: Path,
    domain: str,
    release_scope: str,
    project_id: str,
):
    report_path = tmp_path / f"{domain}_preflight_report.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ultra_long_benchmark.cli",
            "preflight-workflow-manifest-release",
            str(fixture_path),
            "--output-dir",
            str(tmp_path / domain / "preflight"),
            "--report",
            str(report_path),
            "--harden-probe-queries",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "workflow manifest release preflight" in completed.stdout
    report = read_json(report_path)
    assert report["passed"] is True
    assert report["project_id"] == project_id
    assert report["domain"] == domain
    assert report["summary"]["release_scope"] == release_scope
    assert report["summary"]["covered_workflow_domains"] == [domain]
    assert report["constraints"]["release_ready_claim"] is False
    assert report["constraints"]["llm_generation_performed"] is False
    assert read_json(Path(report["submission_input_dir"]) / "submission_manifest.json")["constraints"]["probe_queries_hardened"] is True
    assert verify_workflow_manifest_preflight_report(report_path)["passed"] is True


def test_verify_workflow_manifest_preflight_cli(tmp_path: Path):
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    report_path = tmp_path / "preflight" / "workflow_manifest_release_preflight.json"
    verify_path = tmp_path / "preflight_verify.json"
    preflight_workflow_manifest_release(manifest_path, tmp_path / "preflight", output_report_path=report_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ultra_long_benchmark.cli",
            "verify-workflow-manifest-preflight",
            str(report_path),
            "--output",
            str(verify_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "workflow manifest preflight verified" in completed.stdout
    assert read_json(verify_path)["passed"] is True


def test_verify_workflow_manifest_preflight_fails_when_artifact_changes(tmp_path: Path):
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    report_path = tmp_path / "preflight" / "workflow_manifest_release_preflight.json"
    report = preflight_workflow_manifest_release(manifest_path, tmp_path / "preflight", output_report_path=report_path)
    project_profile = Path(report["artifacts"]["project_dir"]) / "project_profile.json"
    profile = read_json(project_profile)
    profile["title"] = profile["title"] + " drift"
    write_json(project_profile, profile)

    verification = verify_workflow_manifest_preflight_report(report_path)

    assert verification["passed"] is False
    assert "workflow_manifest_preflight_artifact_sha256_mismatch" in verification["summary"]["issue_codes"]
    assert verification["artifacts"]["project_dir"]["passed"] is False


def test_preflight_workflow_manifest_release_batch_runs_and_verifies_all_fixtures(tmp_path: Path):
    manifest_paths = [fixture[0] for fixture in WORKFLOW_PROJECT_MANIFEST_FIXTURES]
    report_path = tmp_path / "batch" / "workflow_manifest_preflight_batch_report.json"

    report = preflight_workflow_manifest_release_batch(
        manifest_paths,
        tmp_path / "batch",
        output_report_path=report_path,
        baseline_names=["oracle_policy_graph"],
        harden_probe_queries=True,
    )

    assert report["passed"] is True
    assert report["summary"]["reports_passed"] == 4
    assert report["summary"]["domains"] == [
        "browser_web_workflow",
        "calendar_workflow",
        "chat_workflow",
        "docs_workflow",
    ]
    assert all(item["sha256"] for item in report["preflight_reports"])
    verification = verify_workflow_manifest_preflight_batch_report(report_path)
    assert verification["passed"] is True
    assert verification["summary"]["reports_verified"] == 4


def test_preflight_workflow_manifest_release_batch_cli(tmp_path: Path):
    report_path = tmp_path / "batch_report.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ultra_long_benchmark.cli",
            "preflight-workflow-manifest-release-batch",
            *[str(fixture[0]) for fixture in WORKFLOW_PROJECT_MANIFEST_FIXTURES],
            "--output-dir",
            str(tmp_path / "batch"),
            "--report",
            str(report_path),
            "--baseline",
            "oracle_policy_graph",
            "--harden-probe-queries",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "workflow manifest preflight batch" in completed.stdout
    assert read_json(report_path)["passed"] is True


def test_verify_workflow_manifest_preflight_batch_cli(tmp_path: Path):
    report_path = tmp_path / "batch" / "workflow_manifest_preflight_batch_report.json"
    verify_path = tmp_path / "batch_verify.json"
    preflight_workflow_manifest_release_batch(
        [fixture[0] for fixture in WORKFLOW_PROJECT_MANIFEST_FIXTURES],
        tmp_path / "batch",
        output_report_path=report_path,
        baseline_names=["oracle_policy_graph"],
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ultra_long_benchmark.cli",
            "verify-workflow-manifest-preflight-batch",
            str(report_path),
            "--output",
            str(verify_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "workflow manifest preflight batch verified" in completed.stdout
    assert read_json(verify_path)["passed"] is True


def test_verify_workflow_manifest_preflight_batch_fails_when_item_report_changes(tmp_path: Path):
    report_path = tmp_path / "batch" / "workflow_manifest_preflight_batch_report.json"
    batch = preflight_workflow_manifest_release_batch(
        [fixture[0] for fixture in WORKFLOW_PROJECT_MANIFEST_FIXTURES[:2]],
        tmp_path / "batch",
        output_report_path=report_path,
        baseline_names=["oracle_policy_graph"],
    )
    first_report_path = Path(batch["preflight_reports"][0]["report_path"])
    first_report = read_json(first_report_path)
    first_report["summary"]["probes"] = 999
    write_json(first_report_path, first_report)

    verification = verify_workflow_manifest_preflight_batch_report(report_path)

    assert verification["passed"] is False
    assert "workflow_manifest_preflight_batch_item_sha256_mismatch" in verification["summary"]["issue_codes"]
    assert verification["preflight_reports"]["workflow_manifest_preflight_0"]["passed"] is False


def test_build_project_from_workflow_manifest_requires_manifest_supplied_gold(tmp_path: Path):
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    manifest = read_json(manifest_path)
    del manifest["memory_graph"]
    write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="memory_graph"):
        build_project_from_workflow_manifest(manifest_path, tmp_path / "projects")


def test_build_project_from_workflow_manifest_rejects_project_id_mismatch(tmp_path: Path):
    manifest_path = _write_calendar_project_manifest(tmp_path / "calendar_project_manifest.json")
    manifest = read_json(manifest_path)
    manifest["probes"][0]["project_id"] = "project_other"
    write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="probe project_id"):
        build_project_from_workflow_manifest(manifest_path, tmp_path / "projects")


def _write_calendar_project_manifest(path: Path) -> Path:
    write_json(path, read_json(CALENDAR_PROJECT_MANIFEST_FIXTURE))
    return path


def _write_tiny_enron_tarball(path: Path) -> None:
    import io
    import tarfile

    messages = [
        (
            "maildir/allen-p/sent/1.",
            "From: sender1@enron.com\nTo: partner1@example.com\nDate: Mon, 1 Jan 2001 09:00:00 -0800\nSubject: External contract review\n\nPlease draft the external partner note, but it needs review before anyone sends it outside Enron.",
        ),
        (
            "maildir/allen-p/sent/2.",
            "From: sender2@enron.com\nTo: schedule@example.com\nDate: Tue, 2 Jan 2001 10:00:00 -0800\nSubject: Meeting schedule\n\nThis routine scheduling reply can be prepared after checking the thread context, but unrelated outside mail still needs review.",
        ),
        (
            "maildir/allen-p/sent/3.",
            "From: sender3@enron.com\nTo: team@example.com\nDate: Wed, 3 Jan 2001 11:00:00 -0800\nSubject: Forward confidential summary\n\nForward only a redacted summary of the sensitive email and ask clarification before sharing details externally.",
        ),
        (
            "maildir/allen-p/sent/4.",
            "From: sender4@enron.com\nTo: desk@example.com\nDate: Thu, 4 Jan 2001 12:00:00 -0800\nSubject: Desk update\n\nThe desk update includes operational context for the email workflow and enough body words for deterministic sampling.",
        ),
    ]
    with tarfile.open(path, "w:gz") as archive:
        for name, text in messages:
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
