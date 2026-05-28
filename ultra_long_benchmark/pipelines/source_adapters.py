from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ultra_long_benchmark.models import CanonicalEvent, ProjectProfile, SourceArtifact, Validity
from ultra_long_benchmark.shared.io import read_json


@dataclass(frozen=True)
class AdapterResult:
    """Normalized output of a source dataset adapter.

    Future adapters for SWE-bench, GitHub issues, arXiv revisions, OpenReview
    reviews, or web search traces should convert their raw records into this
    contract. Downstream grounded construction stages should not care whether
    records came from a manual seed file or a real public dataset.
    """

    project_profile: ProjectProfile
    artifacts: list[SourceArtifact]
    events: list[CanonicalEvent]
    seed_path: Path | None = None


class GitHubIssueCIAdapter:
    """Offline fixture adapter shaped like a GitHub issue/CI dataset adapter.

    This adapter reads checked-in fixture records that mimic GitHub issues,
    CI logs, patch diffs, and review comments. It deliberately avoids network
    access while exercising the same normalization contract a future real
    GitHub/SWE-bench adapter should implement.
    """

    def __init__(self, fixture_path: Path):
        self.fixture_path = Path(fixture_path)

    def load(self) -> AdapterResult:
        fixture = read_json(self.fixture_path)
        profile = ProjectProfile(**fixture["project_profile"])
        event_id_map = fixture.get("event_id_map", {})
        artifacts: list[SourceArtifact] = []
        events: list[CanonicalEvent] = []
        for record in fixture["raw_records"]:
            artifact_id = f"artifact_{record['record_id']}"
            artifacts.append(
                SourceArtifact(
                    artifact_id=artifact_id,
                    source_dataset=record["source_dataset"],
                    artifact_type=record["artifact_type"],
                    uri=record.get("uri"),
                    license=record.get("license"),
                    content_hash=record.get("content_hash") or f"fixture_hash_{record['record_id']}",
                    raw_pointer=record["raw_pointer"],
                    content=record["content"],
                    metadata={"record_id": record["record_id"], "fixture_path": str(self.fixture_path)},
                )
            )
            event_id = event_id_map.get(record["record_id"], f"event_{record['record_id']}")
            validity = record.get("validity")
            events.append(
                CanonicalEvent(
                    event_id=event_id,
                    project_id=profile.project_id,
                    timestamp=record["timestamp"],
                    source_dataset=record["source_dataset"],
                    actor=record["actor"],
                    event_type=record["event_type"],
                    content=record["content"],
                    artifacts=[artifact_id],
                    raw_pointer=record["raw_pointer"],
                    project_tags=record.get("project_tags", []),
                    entities=record.get("entities", []),
                    claims=record.get("claims", []),
                    causal_links=record.get("causal_links", []),
                    supersedes=record.get("supersedes", []),
                    invalidates=record.get("invalidates", []),
                    validity=Validity(**validity) if validity else None,
                    metadata={"record_id": record["record_id"], "artifact_type": record["artifact_type"]},
                )
            )
        return AdapterResult(project_profile=profile, artifacts=artifacts, events=events, seed_path=self.fixture_path)


class ManualSeedAdapter:
    """Offline adapter for the checked-in manual grounded seed JSON.

    The adapter intentionally performs no network access. It exists as the
    smallest reference implementation of the adapter contract that real dataset
    adapters can mirror: read raw/source records, normalize them into
    SourceArtifact objects, and emit CanonicalEvent records bound to a project.
    """

    def __init__(self, seed_path: Path):
        self.seed_path = Path(seed_path)

    def load(self) -> AdapterResult:
        seed = read_json(self.seed_path)
        profile = ProjectProfile(**seed["project_profile"])
        artifacts = [SourceArtifact(**artifact) for artifact in seed["artifacts"]]
        events = [self._event_from_seed(spec, profile.project_id) for spec in seed["event_specs"]]
        return AdapterResult(project_profile=profile, artifacts=artifacts, events=events, seed_path=self.seed_path)

    @staticmethod
    def _event_from_seed(spec: dict, project_id: str) -> CanonicalEvent:
        data = dict(spec)
        data["project_id"] = project_id
        if data.get("validity") is not None:
            data["validity"] = Validity(**data["validity"])
        return CanonicalEvent(**data)
