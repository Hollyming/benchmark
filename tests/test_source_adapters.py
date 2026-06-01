from pathlib import Path
import gzip
import json
import subprocess
import sys

import pytest

from ultra_long_benchmark.models import CanonicalEvent, ProjectProfile, SourceArtifact
from ultra_long_benchmark.pipelines.gharchive import DEFAULT_FIXTURE_PATH as DEFAULT_GHARCHIVE_FIXTURE_PATH
from ultra_long_benchmark.pipelines.source_adapters import AdapterResult, EmailWorkflowAdapter, GHArchiveEventAdapter, WorkflowManifestAdapter, iter_gharchive_json_records
from ultra_long_benchmark.pipelines.source_adapters import validate_workflow_manifest_adapter
from ultra_long_benchmark.shared.io import read_json, write_json


def test_gharchive_adapter_matches_adapter_contract():
    result = GHArchiveEventAdapter(
        DEFAULT_GHARCHIVE_FIXTURE_PATH,
        project_id="project_gharchive_001",
        repo_full_name="acme/docs",
    ).load()

    assert isinstance(result, AdapterResult)
    assert isinstance(result.project_profile, ProjectProfile)
    assert all(isinstance(artifact, SourceArtifact) for artifact in result.artifacts)
    assert all(isinstance(event, CanonicalEvent) for event in result.events)
    assert result.project_profile.project_id == "project_gharchive_001"
    assert len(result.artifacts) >= 6
    assert len(result.events) >= 6
    assert result.seed_path == DEFAULT_GHARCHIVE_FIXTURE_PATH


def test_gharchive_adapter_preserves_project_binding():
    result = GHArchiveEventAdapter(
        DEFAULT_GHARCHIVE_FIXTURE_PATH,
        project_id="project_gharchive_001",
        repo_full_name="acme/docs",
    ).load()
    project_ids = {event.project_id for event in result.events}
    artifact_ids = {artifact.artifact_id for artifact in result.artifacts}

    assert project_ids == {result.project_profile.project_id}
    assert {artifact_id for event in result.events for artifact_id in event.artifacts} <= artifact_ids
    assert result.project_profile.synthetic_context is False
    assert result.project_profile.user_profile["source"] == "gharchive"
    assert "gharchive_public_events" in result.project_profile.source_streams


def test_email_workflow_adapter_requires_reviewed_manifest_and_redacts_pii():
    manifest_path = Path(__file__).parent / "fixtures" / "email_workflow_manifest.json"
    result = EmailWorkflowAdapter(manifest_path).load()

    assert isinstance(result, AdapterResult)
    assert result.project_profile.project_id == "project_email_fixture_001"
    assert result.project_profile.synthetic_context is False
    assert len(result.artifacts) == 2
    assert len(result.events) == 2
    assert all(artifact.license == "CC-BY-4.0 fixture" for artifact in result.artifacts)
    assert all(artifact.metadata["redacted"] is True for artifact in result.artifacts)
    assert all("[REDACTED_EMAIL]" in artifact.content for artifact in result.artifacts)
    assert all(event.metadata["privacy_tags"] == ["email"] for event in result.events)


def test_email_workflow_adapter_rejects_unreviewed_or_nonredistributable_data(tmp_path: Path):
    manifest = read_json(Path(__file__).parent / "fixtures" / "email_workflow_manifest.json")

    manifest["redistribution"] = {"allowed": False}
    blocked_path = tmp_path / "blocked_email_manifest.json"
    write_json(blocked_path, manifest)
    with pytest.raises(ValueError, match="redistribution.allowed=true"):
        EmailWorkflowAdapter(blocked_path).load()

    manifest = read_json(Path(__file__).parent / "fixtures" / "email_workflow_manifest.json")
    manifest["privacy_review"] = {"status": "pending", "pii_redaction": False}
    pending_path = tmp_path / "pending_email_manifest.json"
    write_json(pending_path, manifest)
    with pytest.raises(ValueError, match="privacy_review.status='passed'"):
        EmailWorkflowAdapter(pending_path).load()


def test_validate_workflow_manifest_adapter_reports_email_without_content_export(tmp_path: Path):
    manifest_path = Path(__file__).parent / "fixtures" / "email_workflow_manifest.json"
    output_path = tmp_path / "email_manifest_validation.json"

    report = validate_workflow_manifest_adapter(manifest_path, output_path=output_path)

    assert report["passed"] is True
    assert report["adapter"] == "email"
    assert report["domain"] == "email_workflow"
    assert report["summary"]["records"] == 2
    assert report["summary"]["events"] == 2
    assert report["manifest"]["sha256"]
    assert report["constraints"]["raw_content_exported"] is False
    assert "content" not in read_json(output_path)


def test_workflow_manifest_adapter_accepts_reviewed_calendar_manifest(tmp_path: Path):
    manifest_path = tmp_path / "calendar_manifest.json"
    write_json(
        manifest_path,
        {
            "dataset_name": "reviewed_calendar_fixture",
            "domain": "calendar_workflow",
            "source_dataset": "calendar_reviewed_fixture",
            "license": "CC-BY-4.0 fixture",
            "redistribution": {"allowed": True},
            "privacy_review": {"status": "passed", "pii_redaction": True},
            "project_id": "project_calendar_fixture_001",
            "records": [
                {
                    "record_id": "calendar_001",
                    "timestamp": "2026-05-01T09:00:00Z",
                    "actor": "assistant@example.com",
                    "title": "Deep work block",
                    "tool": "calendar",
                    "action": "schedule_meeting",
                    "content": "User prefers deep-work blocks before 10:30 and asks to avoid scheduling over them.",
                    "event_type": "calendar_preference",
                    "claims": ["avoid_deep_work_conflict"],
                    "entities": ["assistant@example.com"],
                }
            ],
        },
    )

    result = WorkflowManifestAdapter(manifest_path).load()

    assert isinstance(result, AdapterResult)
    assert result.project_profile.project_id == "project_calendar_fixture_001"
    assert result.project_profile.source_streams == ["calendar"]
    assert result.project_profile.metadata["domain"] == "calendar_workflow"
    assert len(result.artifacts) == 1
    assert len(result.events) == 1
    assert result.events[0].event_type == "calendar_preference"
    assert "calendar_workflow" in result.events[0].project_tags
    assert "[REDACTED_EMAIL]" in result.events[0].actor
    assert "[REDACTED_EMAIL]" in result.events[0].entities[0]
    assert result.artifacts[0].metadata["redacted"] is True


def test_validate_workflow_manifest_adapter_reports_calendar_domain(tmp_path: Path):
    manifest_path = _write_calendar_manifest(tmp_path / "calendar_manifest.json")

    report = validate_workflow_manifest_adapter(manifest_path, output_path=tmp_path / "calendar_validation.json")

    assert report["passed"] is True
    assert report["adapter"] == "workflow"
    assert report["domain"] == "calendar_workflow"
    assert report["summary"]["artifacts"] == 1
    assert report["summary"]["events"] == 1
    assert report["constraints"]["release_ready_claim"] is False
    assert read_json(tmp_path / "calendar_validation.json")["manifest"]["dataset_name"] == "reviewed_calendar_fixture"


def test_validate_workflow_manifest_cli_writes_report(tmp_path: Path):
    manifest_path = _write_calendar_manifest(tmp_path / "calendar_manifest.json")
    output_path = tmp_path / "calendar_validation_cli.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ultra_long_benchmark.cli",
            "validate-workflow-manifest",
            str(manifest_path),
            "--output",
            str(output_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "workflow manifest validated" in completed.stdout
    report = read_json(output_path)
    assert report["passed"] is True
    assert report["domain"] == "calendar_workflow"


def test_workflow_manifest_adapter_rejects_unknown_or_unreviewed_domain(tmp_path: Path):
    manifest = {
        "dataset_name": "bad_fixture",
        "domain": "files_workflow",
        "source_dataset": "files_fixture",
        "license": "CC-BY-4.0 fixture",
        "redistribution": {"allowed": True},
        "privacy_review": {"status": "passed", "pii_redaction": True},
        "project_id": "project_bad_fixture",
        "records": [{"record_id": "row_1", "timestamp": "2026-05-01T00:00:00Z", "content": "x"}],
    }
    unknown_path = tmp_path / "unknown_manifest.json"
    write_json(unknown_path, manifest)
    with pytest.raises(ValueError, match="domain must be one of"):
        WorkflowManifestAdapter(unknown_path).load()

    manifest["domain"] = "chat_workflow"
    manifest["privacy_review"] = {"status": "pending", "pii_redaction": True}
    pending_path = tmp_path / "pending_manifest.json"
    write_json(pending_path, manifest)
    with pytest.raises(ValueError, match="privacy_review.status='passed'"):
        WorkflowManifestAdapter(pending_path).load()


def test_validate_workflow_manifest_adapter_rejects_unreviewed_manifest(tmp_path: Path):
    manifest_path = _write_calendar_manifest(tmp_path / "calendar_manifest.json")
    manifest = read_json(manifest_path)
    manifest["privacy_review"] = {"status": "pending", "pii_redaction": True}
    write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="privacy_review.status='passed'"):
        validate_workflow_manifest_adapter(manifest_path)


def test_iter_gharchive_json_records_streams_jsonl_gzip(tmp_path: Path):
    path = tmp_path / "2024-01-01-0.json.gz"
    rows = [
        {"id": "evt_1", "type": "PullRequestEvent", "repo": {"name": "acme/docs"}},
        {"id": "evt_2", "type": "StatusEvent", "repo": {"name": "acme/docs"}},
    ]
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")

    assert [record["id"] for record in iter_gharchive_json_records(path)] == ["evt_1", "evt_2"]


def _write_calendar_manifest(path: Path) -> Path:
    write_json(
        path,
        {
            "dataset_name": "reviewed_calendar_fixture",
            "domain": "calendar_workflow",
            "source_dataset": "calendar_reviewed_fixture",
            "license": "CC-BY-4.0 fixture",
            "redistribution": {"allowed": True},
            "privacy_review": {"status": "passed", "pii_redaction": True},
            "project_id": "project_calendar_fixture_001",
            "records": [
                {
                    "record_id": "calendar_001",
                    "timestamp": "2026-05-01T09:00:00Z",
                    "actor": "assistant@example.com",
                    "title": "Deep work block",
                    "tool": "calendar",
                    "action": "schedule_meeting",
                    "content": "User prefers deep-work blocks before 10:30 and asks to avoid scheduling over them.",
                    "event_type": "calendar_preference",
                    "claims": ["avoid_deep_work_conflict"],
                    "entities": ["assistant@example.com"],
                }
            ],
        },
    )
    return path
