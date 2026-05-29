from pathlib import Path

from ultra_long_benchmark.models import CanonicalEvent, ProjectProfile, SourceArtifact
from ultra_long_benchmark.pipelines.grounded_pilot import DEFAULT_SEED_PATH
from ultra_long_benchmark.pipelines.source_adapters import AdapterResult, ManualSeedAdapter


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
