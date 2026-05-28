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
from ultra_long_benchmark.shared.io import write_json, write_jsonl


PROJECT_ID = "project_manual_001"
TRAJECTORY_ID = "trajectory_manual_001"


def run_manual_grounded_pilot(output_dir: Path) -> dict[str, Any]:
    """Create a tiny project-centric reference-grounded pilot.

    This is still manually seeded, but unlike the synthetic smoke path it follows
    the target chain: source artifacts -> canonical events -> memory graph ->
    evidence-constrained probes. It gives future dataset adapters a stable output
    contract while keeping CI deterministic and offline.
    """
    project_dir = output_dir / PROJECT_ID
    artifacts = _artifacts()
    events = _events()
    profile = _profile()
    graph = _memory_graph()
    probes = _probes()

    write_json(project_dir / "project_profile.json", profile)
    write_jsonl(project_dir / "artifacts.jsonl", artifacts)
    write_jsonl(project_dir / "events.jsonl", events)
    write_json(project_dir / "memory_graph.json", graph)
    write_jsonl(project_dir / "probes.jsonl", probes)
    write_json(
        project_dir / "source_manifest.json",
        {
            "project_id": PROJECT_ID,
            "source_streams": sorted({artifact.source_dataset for artifact in artifacts}),
            "artifact_count": len(artifacts),
            "construction": "manual_seed_reference_grounded_pilot",
            "llm_role": "none_in_seed; future stages may rewrite/bridge only with provenance",
        },
    )
    return {
        "project_id": PROJECT_ID,
        "project_dir": str(project_dir),
        "artifacts": len(artifacts),
        "events": len(events),
        "memories": len(graph.memories),
        "probes": len(probes),
    }


def _artifacts() -> list[SourceArtifact]:
    return [
        SourceArtifact(
            artifact_id="artifact_swe_issue_001",
            source_dataset="manual_swe_like",
            artifact_type="github_issue",
            uri="https://example.org/repo/issues/101",
            license="synthetic-manual-seed",
            content_hash="manual_sha256_issue_001",
            raw_pointer="manual_swe_like:issue:101",
            content="Training the 7B baseline with batch size 64 on A100-40G failed with CUDA OOM.",
            metadata={"stream": "code_experiment", "grounding": "manual_reference_seed"},
        ),
        SourceArtifact(
            artifact_id="artifact_ci_log_001",
            source_dataset="manual_swe_like",
            artifact_type="ci_log",
            uri="https://example.org/repo/actions/runs/201",
            license="synthetic-manual-seed",
            content_hash="manual_sha256_ci_001",
            raw_pointer="manual_swe_like:ci:201",
            content="A retry with batch size 16 completed successfully after the OOM failure.",
            metadata={"stream": "code_experiment", "grounding": "manual_reference_seed"},
        ),
        SourceArtifact(
            artifact_id="artifact_eval_audit_001",
            source_dataset="manual_experiment_audit",
            artifact_type="experiment_audit",
            uri="https://example.org/project/eval-audit-v2",
            license="synthetic-manual-seed",
            content_hash="manual_sha256_audit_001",
            raw_pointer="manual_experiment_audit:eval:v2",
            content="The preliminary baseline score used the wrong metric version and must not be cited.",
            metadata={"stream": "experiment_audit", "grounding": "manual_reference_seed"},
        ),
        SourceArtifact(
            artifact_id="artifact_review_001",
            source_dataset="manual_openreview_like",
            artifact_type="review_comment",
            uri="https://example.org/openreview/forum?id=review-7",
            license="synthetic-manual-seed",
            content_hash="manual_sha256_review_001",
            raw_pointer="manual_openreview_like:review:7",
            content="Reviewer requests an ablation table for the benchmark paper.",
            metadata={"stream": "team_feedback", "grounding": "manual_reference_seed"},
        ),
        SourceArtifact(
            artifact_id="artifact_team_001",
            source_dataset="manual_team_dialogue",
            artifact_type="team_message",
            uri="https://example.org/chat/messages/301",
            license="synthetic-manual-seed",
            content_hash="manual_sha256_team_001",
            raw_pointer="manual_team_dialogue:message:301",
            content="Morgan says annotation QA must be frozen before adding new tasks.",
            metadata={"stream": "team_feedback", "grounding": "manual_reference_seed"},
        ),
        SourceArtifact(
            artifact_id="artifact_lit_001",
            source_dataset="manual_literature_notes",
            artifact_type="research_note",
            uri="https://example.org/notes/memory-benchmarks",
            license="synthetic-manual-seed",
            content_hash="manual_sha256_lit_001",
            raw_pointer="manual_literature_notes:note:memory-benchmarks",
            content="The project studies compositional experience memory beyond long-dialogue recall.",
            metadata={"stream": "literature_search", "grounding": "manual_reference_seed"},
        ),
    ]


def _events() -> list[CanonicalEvent]:
    return [
        CanonicalEvent(
            event_id="event_001_oom_failure",
            project_id=PROJECT_ID,
            timestamp=_dt("2026-03-01T10:00:00+00:00"),
            source_dataset="manual_swe_like",
            actor="environment",
            event_type="test_result",
            content="7B baseline with batch size 64 caused CUDA OOM on A100-40G.",
            artifacts=["artifact_swe_issue_001"],
            raw_pointer="manual_swe_like:issue:101",
            project_tags=["agent_memory", "experiment"],
            entities=["7B baseline", "A100-40G", "batch size 64", "CUDA OOM"],
            claims=["claim_batch64_oom"],
            validity=Validity(scope="7B baseline on A100-40G", start="event_001_oom_failure", status="active"),
        ),
        CanonicalEvent(
            event_id="event_002_batch16_validated",
            project_id=PROJECT_ID,
            timestamp=_dt("2026-03-02T11:30:00+00:00"),
            source_dataset="manual_swe_like",
            actor="tool",
            event_type="test_result",
            content="Batch size 16 completed successfully on the same setup.",
            artifacts=["artifact_ci_log_001"],
            raw_pointer="manual_swe_like:ci:201",
            project_tags=["agent_memory", "experiment"],
            entities=["7B baseline", "A100-40G", "batch size 16"],
            claims=["claim_batch16_valid"],
            causal_links=["event_001_oom_failure"],
            validity=Validity(scope="7B baseline on A100-40G", start="event_002_batch16_validated", status="active"),
        ),
        CanonicalEvent(
            event_id="event_003_metric_invalidated",
            project_id=PROJECT_ID,
            timestamp=_dt("2026-03-04T09:00:00+00:00"),
            source_dataset="manual_experiment_audit",
            actor="tool",
            event_type="negative_evidence",
            content="Preliminary baseline score used the wrong metric version and must not be cited.",
            artifacts=["artifact_eval_audit_001"],
            raw_pointer="manual_experiment_audit:eval:v2",
            project_tags=["agent_memory", "evaluation"],
            entities=["baseline score", "metric version"],
            claims=["claim_preliminary_score"],
            invalidates=["claim_preliminary_score"],
            validity=Validity(scope="benchmark evaluation claims", start="event_003_metric_invalidated", status="active"),
        ),
        CanonicalEvent(
            event_id="event_004_reviewer_ablation",
            project_id=PROJECT_ID,
            timestamp=_dt("2026-03-06T15:00:00+00:00"),
            source_dataset="manual_openreview_like",
            actor="reviewer",
            event_type="feedback",
            content="Reviewer requests an ablation table for the benchmark paper.",
            artifacts=["artifact_review_001"],
            raw_pointer="manual_openreview_like:review:7",
            project_tags=["agent_memory", "writing"],
            entities=["reviewer", "ablation table"],
            claims=["claim_ablation_requested"],
        ),
        CanonicalEvent(
            event_id="event_005_morgan_qa_freeze",
            project_id=PROJECT_ID,
            timestamp=_dt("2026-03-06T16:00:00+00:00"),
            source_dataset="manual_team_dialogue",
            actor="collaborator",
            event_type="team_constraint",
            content="Morgan says annotation QA must be frozen before adding new tasks.",
            artifacts=["artifact_team_001"],
            raw_pointer="manual_team_dialogue:message:301",
            project_tags=["agent_memory", "annotation"],
            entities=["Morgan", "annotation QA", "new tasks"],
            claims=["claim_qa_freeze_first"],
        ),
        CanonicalEvent(
            event_id="event_006_research_direction",
            project_id=PROJECT_ID,
            timestamp=_dt("2026-03-08T12:00:00+00:00"),
            source_dataset="manual_literature_notes",
            actor="user",
            event_type="research_note",
            content="The project studies compositional experience memory beyond long-dialogue recall.",
            artifacts=["artifact_lit_001"],
            raw_pointer="manual_literature_notes:note:memory-benchmarks",
            project_tags=["agent_memory", "benchmark_design"],
            entities=["compositional experience memory", "long-dialogue recall"],
            claims=["claim_beyond_recall"],
        ),
    ]


def _profile() -> ProjectProfile:
    return ProjectProfile(
        project_id=PROJECT_ID,
        title="Manual grounded CompResearchMem pilot",
        project_goal="Build a reference-grounded benchmark for compositional experience memory.",
        user_profile={"research_interest": ["agent memory", "benchmark construction"], "preference": "provenance-first evidence use"},
        roles={"user": "project lead", "Morgan": "annotation QA collaborator", "reviewer": "external paper reviewer", "tool": "experiment/evaluation system"},
        phases=["survey", "experiment", "annotation", "writing"],
        source_streams=["literature_search", "code_experiment", "experiment_audit", "team_feedback"],
        synthetic_context=True,
        metadata={"construction": "manual_seed_adapter", "grounded_artifacts": 6},
    )


def _memory_graph() -> MemoryGraph:
    return MemoryGraph(
        project_id=PROJECT_ID,
        memories=[
            MemoryNode(
                memory_id="memory_failure_lesson_batch_size",
                project_id=PROJECT_ID,
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
                project_id=PROJECT_ID,
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
                project_id=PROJECT_ID,
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
                project_id=PROJECT_ID,
                memory_type="research_thread_state",
                content="The project direction is compositional experience memory beyond long-dialogue recall.",
                source_events=["event_006_research_direction"],
                future_utility=FutureUtility(score=0.9, expected_tasks=["research_thread_resumption", "writing"]),
            ),
            MemoryNode(
                memory_id="memory_distractor_batch_size_other_gpu",
                project_id=PROJECT_ID,
                memory_type="distractor",
                content="A different model on a different GPU used batch size 64 successfully; this is not applicable to the 7B A100-40G setup.",
                source_events=[],
                status="distractor",
                validity={"scope": "different model/hardware", "start_event": None, "end_event": None},
            ),
        ],
        metadata={"construction": "manual_memory_graph_builder", "grounded": True},
    )


def _probes() -> list[Probe]:
    return [
        Probe(
            probe_id="probe_failure_aware_plan",
            project_id=PROJECT_ID,
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
            project_id=PROJECT_ID,
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
            project_id=PROJECT_ID,
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
            project_id=PROJECT_ID,
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


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
