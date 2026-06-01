from __future__ import annotations

from pathlib import Path
from typing import Any

from ultra_long_benchmark.models import CanonicalEvent, MemoryGraph, Probe, ProjectProfile, SourceArtifact
from ultra_long_benchmark.shared.io import write_json, write_jsonl


def write_project(
    output_dir: Path,
    profile: ProjectProfile,
    artifacts: list[SourceArtifact],
    events: list[CanonicalEvent],
    graph: MemoryGraph,
    probes: list[Probe],
    *,
    construction: str,
    seed_path: str | None = None,
    extra_manifest: dict[str, Any] | None = None,
) -> Path:
    project_dir = Path(output_dir) / profile.project_id
    write_json(project_dir / "project_profile.json", profile)
    write_jsonl(project_dir / "artifacts.jsonl", artifacts)
    write_jsonl(project_dir / "events.jsonl", events)
    write_json(project_dir / "memory_graph.json", graph)
    write_jsonl(project_dir / "probes.jsonl", probes)
    manifest = {
        "project_id": profile.project_id,
        "source_streams": sorted({artifact.source_dataset for artifact in artifacts}),
        "artifact_count": len(artifacts),
        "construction": construction,
        "llm_role": "none_in_source_data; generated rewrites must pass verifier gates before release",
        "seed_path": seed_path,
    }
    if extra_manifest:
        manifest.update(extra_manifest)
    write_json(project_dir / "source_manifest.json", manifest)
    return project_dir
