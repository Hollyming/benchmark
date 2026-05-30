from pathlib import Path
import gzip
import json

import pytest

from ultra_long_benchmark.models import CanonicalEvent, ProjectProfile, SourceArtifact
from ultra_long_benchmark.pipelines.grounded_pilot import DEFAULT_SEED_PATH
from ultra_long_benchmark.pipelines.source_adapters import AdapterResult, EmailWorkflowAdapter, ManualSeedAdapter, iter_gharchive_json_records
from ultra_long_benchmark.shared.io import read_json, write_json


def test_manual_seed_adapter_matches_adapter_contract():
    result = ManualSeedAdapter(DEFAULT_SEED_PATH).load()

    assert isinstance(result, AdapterResult)
    assert isinstance(result.project_profile, ProjectProfile)
    assert all(isinstance(artifact, SourceArtifact) for artifact in result.artifacts)
    assert all(isinstance(event, CanonicalEvent) for event in result.events)
    assert result.project_profile.project_id == "project_manual_001"
    assert len(result.artifacts) == 7
    assert len(result.events) == 7
    assert result.seed_path == DEFAULT_SEED_PATH


def test_manual_seed_adapter_preserves_project_binding():
    result = ManualSeedAdapter(DEFAULT_SEED_PATH).load()
    project_ids = {event.project_id for event in result.events}
    artifact_ids = {artifact.artifact_id for artifact in result.artifacts}

    assert project_ids == {result.project_profile.project_id}
    assert {artifact_id for event in result.events for artifact_id in event.artifacts} <= artifact_ids
    assert any(event.invalidates for event in result.events)


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
