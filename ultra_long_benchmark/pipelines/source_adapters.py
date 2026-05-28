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
