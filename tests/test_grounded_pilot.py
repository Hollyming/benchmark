from pathlib import Path

from ultra_long_benchmark.models import CanonicalEvent, MemoryGraph, Probe, ProjectProfile, SourceArtifact, VerifierReport
from ultra_long_benchmark.pipelines.grounded_pilot import DEFAULT_SEED_PATH, build_source_artifacts, load_manual_seed, run_manual_grounded_pilot
from ultra_long_benchmark.pipelines.verifier import run_project_verifier
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_jsonl
from ultra_long_benchmark.validation import validate_jsonl


def test_manual_seed_adapter_loads_reference_artifacts():
    seed = load_manual_seed(DEFAULT_SEED_PATH)
    artifacts = build_source_artifacts(seed)

    assert seed["project_profile"]["project_id"] == "project_manual_001"
    assert len(artifacts) == 6
    assert {artifact.source_dataset for artifact in artifacts} >= {"manual_swe_like", "manual_experiment_audit"}


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
    assert report.checks["invalidation_targets_known"] is True
    assert report.checks["negative_evidence_links_valid"] is True
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


def test_verifier_fails_when_negative_probe_references_non_negative_memory(tmp_path: Path):
    summary = run_manual_grounded_pilot(tmp_path / "projects")
    project_dir = Path(summary["project_dir"])
    probes = read_jsonl(project_dir / "probes.jsonl")
    probes[0]["evidence"]["negative"] = ["memory_failure_lesson_batch_size"]
    write_jsonl(project_dir / "probes.jsonl", probes)

    report = run_project_verifier(project_dir)

    assert report.passed is False
    assert report.checks["negative_evidence_links_valid"] is False
    assert any("is not a negative-evidence memory" in issue for issue in report.issues)


def test_verifier_fails_when_reference_event_has_no_artifact(tmp_path: Path):
    summary = run_manual_grounded_pilot(tmp_path / "projects")
    project_dir = Path(summary["project_dir"])
    events = read_jsonl(project_dir / "events.jsonl")
    events[0]["artifacts"] = []
    write_jsonl(project_dir / "events.jsonl", events)

    report = run_project_verifier(project_dir)

    assert report.passed is False
    assert report.checks["provenance_completeness"] is False
    assert any("has no artifacts" in issue for issue in report.issues)
