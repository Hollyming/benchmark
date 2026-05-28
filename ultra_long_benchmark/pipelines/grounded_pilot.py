from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ultra_long_benchmark.models import (
    CanonicalEvent,
    FutureUtility,
    MemoryGraph,
    MemoryNode,
    MemoryRelation,
    Probe,
    ProbeEvaluation,
    ProbeEvidence,
    ProjectProfile,
    SourceArtifact,
    Validity,
)
from ultra_long_benchmark.shared.io import read_json, write_json, write_jsonl


PROJECT_ID = "project_manual_001"
TRAJECTORY_ID = "trajectory_manual_001"
DEFAULT_SEED_PATH = Path(__file__).resolve().parents[2] / "examples" / "manual_grounded_seed" / f"{PROJECT_ID}.json"


def run_manual_grounded_pilot(output_dir: Path) -> dict[str, Any]:
    """Create a tiny project-centric reference-grounded pilot.

    The pilot is manually seeded but now follows adapter-style stages:
    seed -> artifacts/profile -> canonical events -> memory graph -> probes -> project writer.
    This preserves deterministic CI while making future real dataset adapters easier.
    """
    seed = load_manual_seed(DEFAULT_SEED_PATH)
    profile = build_project_profile(seed)
    artifacts = build_source_artifacts(seed)
    events = build_canonical_events(seed, profile.project_id)
    graph = build_memory_graph(profile.project_id)
    probes = synthesize_probes(profile.project_id)
    project_dir = write_grounded_project(output_dir, profile, artifacts, events, graph, probes)
    return {
        "project_id": profile.project_id,
        "project_dir": str(project_dir),
        "artifacts": len(artifacts),
        "events": len(events),
        "memories": len(graph.memories),
        "probes": len(probes),
    }


def load_manual_seed(path: Path = DEFAULT_SEED_PATH) -> dict[str, Any]:
    return read_json(path)


def build_project_profile(seed: dict[str, Any]) -> ProjectProfile:
    return ProjectProfile(**seed["project_profile"])


def build_source_artifacts(seed: dict[str, Any]) -> list[SourceArtifact]:
    return [SourceArtifact(**artifact) for artifact in seed["artifacts"]]


def build_canonical_events(seed: dict[str, Any], project_id: str) -> list[CanonicalEvent]:
    events: list[CanonicalEvent] = []
    for spec in seed["event_specs"]:
        data = dict(spec)
        data["project_id"] = project_id
        if data.get("validity") is not None:
            data["validity"] = Validity(**data["validity"])
        events.append(CanonicalEvent(**data))
    return events


def build_memory_graph(project_id: str) -> MemoryGraph:
    return MemoryGraph(
        project_id=project_id,
        memories=[
            MemoryNode(
                memory_id="memory_failure_lesson_batch_size",
                project_id=project_id,
                memory_type="failure_lesson",
                content="Batch size 64 caused CUDA OOM on A100-40G for the 7B baseline; use batch size 16 or smaller for this setup.",
                source_events=["event_001_oom_failure", "event_002_batch16_validated"],
                validity={"scope": "7B baseline on A100-40G", "start_event": "event_002_batch16_validated", "end_event": None},
                relations=[
                    MemoryRelation(type="caused_by", target="event_001_oom_failure"),
                    MemoryRelation(type="validated_by", target="event_002_batch16_validated"),
                ],
                future_utility=FutureUtility(score=0.92, expected_tasks=["experiment_planning", "failure_avoidance"]),
            ),
            MemoryNode(
                memory_id="memory_invalid_metric_result",
                project_id=project_id,
                memory_type="negative_evidence",
                content="The preliminary baseline score is invalid because it used the wrong metric version and must not be cited.",
                source_events=["event_003_metric_invalidated"],
                status="active",
                relations=[MemoryRelation(type="invalidates", target="claim_preliminary_score")],
                negative_evidence=["event_003_metric_invalidated"],
                future_utility=FutureUtility(score=0.88, expected_tasks=["provenance_constrained_writing", "obsolete_evidence_suppression"]),
            ),
            MemoryNode(
                memory_id="memory_role_constraint_ablation_after_qa",
                project_id=project_id,
                memory_type="multi_role_constraint",
                content="Reviewer wants an ablation table, but Morgan's annotation QA freeze should be respected before adding new tasks.",
                source_events=["event_004_reviewer_ablation", "event_005_morgan_qa_freeze"],
                relations=[
                    MemoryRelation(type="requested_by", target="event_004_reviewer_ablation"),
                    MemoryRelation(type="constrained_by", target="event_005_morgan_qa_freeze"),
                ],
                future_utility=FutureUtility(score=0.84, expected_tasks=["planning", "role_constraint_resolution"]),
            ),
            MemoryNode(
                memory_id="memory_research_direction_beyond_recall",
                project_id=project_id,
                memory_type="research_thread_state",
                content="The project direction is compositional experience memory beyond long-dialogue recall.",
                source_events=["event_006_research_direction"],
                future_utility=FutureUtility(score=0.9, expected_tasks=["research_thread_resumption", "writing"]),
            ),
            MemoryNode(
                memory_id="memory_distractor_batch_size_other_gpu",
                project_id=project_id,
                memory_type="distractor",
                content="A different model on a different GPU used batch size 64 successfully; this is not applicable to the 7B A100-40G setup.",
                source_events=[],
                status="distractor",
                validity={"scope": "different model/hardware", "start_event": None, "end_event": None},
            ),
        ],
        metadata={"construction": "manual_memory_graph_builder", "grounded": True},
    )


def synthesize_probes(project_id: str) -> list[Probe]:
    return [
        Probe(
            probe_id="probe_failure_aware_plan",
            project_id=project_id,
            trajectory_id=TRAJECTORY_ID,
            task_type="failure_aware_experiment_planning",
            query="Generate a training configuration for a similar 7B baseline and avoid the previous failure.",
            expected_behavior={"must_include": ["batch_size <= 16"], "must_not_include": ["batch_size 64"]},
            evidence=ProbeEvidence(
                positive=["memory_failure_lesson_batch_size"],
                negative=["memory_invalid_metric_result"],
                distractor=["memory_distractor_batch_size_other_gpu"],
            ),
            capabilities=["procedural_memory", "failure_transfer", "distractor_suppression"],
            evaluation=ProbeEvaluation(answer_type="structured_action", metrics=["constraint_satisfaction", "invalid_reuse_rate"]),
            difficulty="medium",
        ),
        Probe(
            probe_id="probe_provenance_constrained_writing",
            project_id=project_id,
            trajectory_id=TRAJECTORY_ID,
            task_type="provenance_constrained_writing",
            query="Can we cite the preliminary baseline score as evidence in the paper draft?",
            expected_behavior={"must_include": ["do not cite", "wrong metric version"], "must_not_include": ["preliminary score is reliable"]},
            evidence=ProbeEvidence(positive=["memory_invalid_metric_result"], negative=["memory_invalid_metric_result"]),
            capabilities=["provenance", "negative_evidence_suppression"],
            evaluation=ProbeEvaluation(answer_type="policy_answer", metrics=["citation_correctness", "negative_evidence_avoidance"]),
            difficulty="easy",
        ),
        Probe(
            probe_id="probe_multi_role_constraint",
            project_id=project_id,
            trajectory_id=TRAJECTORY_ID,
            task_type="multi_role_constraint_resolution",
            query="How should this week's plan handle the reviewer ablation request and Morgan's QA-freeze constraint?",
            expected_behavior={"must_include": ["freeze annotation QA first", "track ablation request"], "must_not_include": ["ignore Morgan"]},
            evidence=ProbeEvidence(positive=["memory_role_constraint_ablation_after_qa"]),
            capabilities=["role_attribution", "constraint_resolution"],
            evaluation=ProbeEvaluation(answer_type="plan", metrics=["role_attribution_accuracy", "constraint_satisfaction"]),
            difficulty="medium",
        ),
        Probe(
            probe_id="probe_research_thread_resumption",
            project_id=project_id,
            trajectory_id=TRAJECTORY_ID,
            task_type="research_thread_resumption",
            query="Resume the research thread: what is the project trying to benchmark beyond long-dialogue recall?",
            expected_behavior={"must_include": ["compositional experience memory", "beyond long-dialogue recall"]},
            evidence=ProbeEvidence(positive=["memory_research_direction_beyond_recall"]),
            capabilities=["semantic_consolidation", "research_thread_resumption"],
            evaluation=ProbeEvaluation(answer_type="free_text", metrics=["answer_f1", "evidence_faithfulness"]),
            difficulty="easy",
        ),
    ]


def write_grounded_project(
    output_dir: Path,
    profile: ProjectProfile,
    artifacts: list[SourceArtifact],
    events: list[CanonicalEvent],
    graph: MemoryGraph,
    probes: list[Probe],
) -> Path:
    project_dir = output_dir / profile.project_id
    write_json(project_dir / "project_profile.json", profile)
    write_jsonl(project_dir / "artifacts.jsonl", artifacts)
    write_jsonl(project_dir / "events.jsonl", events)
    write_json(project_dir / "memory_graph.json", graph)
    write_jsonl(project_dir / "probes.jsonl", probes)
    write_json(
        project_dir / "source_manifest.json",
        {
            "project_id": profile.project_id,
            "source_streams": sorted({artifact.source_dataset for artifact in artifacts}),
            "artifact_count": len(artifacts),
            "construction": "manual_seed_reference_grounded_pilot",
            "llm_role": "none_in_seed; future stages may rewrite/bridge only with provenance",
            "seed_path": str(DEFAULT_SEED_PATH),
        },
    )
    return project_dir


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
