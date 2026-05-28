from pathlib import Path

from ultra_long_benchmark.models import CanonicalEvent, MemoryGraph, Probe, ProjectProfile, SourceArtifact, VerifierReport
from ultra_long_benchmark.pipelines.grounded_pilot import run_manual_grounded_pilot
from ultra_long_benchmark.pipelines.verifier import run_project_verifier
from ultra_long_benchmark.shared.io import read_json, read_jsonl
from ultra_long_benchmark.validation import validate_jsonl


def test_manual_grounded_pilot_builds_project_centric_artifacts(tmp_path: Path):
    summary = run_manual_grounded_pilot(tmp_path / "projects")
    project_dir = Path(summary["project_dir"])

    assert summary["artifacts"] == 6
    assert summary["events"] == 6
    assert summary["memories"] == 5
    assert summary["probes"] == 4
    assert (project_dir / "project_profile.json").exists()
    assert (project_dir / "source_manifest.json").exists()
    assert (project_dir / "memory_graph.json").exists()

    assert validate_jsonl(project_dir / "artifacts.jsonl", SourceArtifact) == 6
    assert validate_jsonl(project_dir / "events.jsonl", CanonicalEvent) == 6
    assert validate_jsonl(project_dir / "probes.jsonl", Probe) == 4
    ProjectProfile.model_validate(read_json(project_dir / "project_profile.json")) if hasattr(ProjectProfile, "model_validate") else ProjectProfile.parse_obj(read_json(project_dir / "project_profile.json"))
    MemoryGraph.model_validate(read_json(project_dir / "memory_graph.json")) if hasattr(MemoryGraph, "model_validate") else MemoryGraph.parse_obj(read_json(project_dir / "memory_graph.json"))


def test_project_verifier_checks_grounding_and_probe_evidence(tmp_path: Path):
    summary = run_manual_grounded_pilot(tmp_path / "projects")
    report = run_project_verifier(Path(summary["project_dir"]))

    assert isinstance(report, VerifierReport)
    assert report.passed is True
    assert report.checks["provenance_completeness"] is True
    assert report.checks["memory_graph_grounding"] is True
    assert report.checks["negative_evidence_present"] is True
    assert report.checks["distractor_evidence_present"] is True
    assert report.counts["probe_task_types"] >= 3


def test_grounded_probes_bind_to_memory_graph_not_template_events(tmp_path: Path):
    summary = run_manual_grounded_pilot(tmp_path / "projects")
    project_dir = Path(summary["project_dir"])
    graph = read_json(project_dir / "memory_graph.json")
    probes = read_jsonl(project_dir / "probes.jsonl")
    memory_ids = {memory["memory_id"] for memory in graph["memories"]}

    assert any(probe["evidence"]["negative"] for probe in probes)
    assert any(probe["evidence"]["distractor"] for probe in probes)
    for probe in probes:
        evidence = probe["evidence"]
        referenced = evidence.get("positive", []) + evidence.get("negative", []) + evidence.get("obsolete", []) + evidence.get("distractor", [])
        assert referenced
        assert set(referenced) <= memory_ids
