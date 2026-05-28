from __future__ import annotations

from pathlib import Path
from typing import Any

from ultra_long_benchmark.models import FutureUtility, MemoryGraph, MemoryNode, MemoryRelation, Probe, ProbeEvaluation, ProbeEvidence
from ultra_long_benchmark.pipelines.grounded_pilot import write_grounded_project
from ultra_long_benchmark.pipelines.source_adapters import GitHubIssueCIAdapter


PROJECT_ID = "project_github_001"
TRAJECTORY_ID = "trajectory_github_001"
DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "examples" / "source_fixtures" / "github_issue_ci" / f"{PROJECT_ID}.json"


def run_github_fixture_pilot(output_dir: Path) -> dict[str, Any]:
    adapter_result = GitHubIssueCIAdapter(DEFAULT_FIXTURE_PATH).load()
    profile = adapter_result.project_profile
    graph = build_github_fixture_memory_graph(profile.project_id)
    probes = synthesize_github_fixture_probes(profile.project_id)
    project_dir = write_grounded_project(output_dir, profile, adapter_result.artifacts, adapter_result.events, graph, probes)
    return {
        "project_id": profile.project_id,
        "project_dir": str(project_dir),
        "artifacts": len(adapter_result.artifacts),
        "events": len(adapter_result.events),
        "memories": len(graph.memories),
        "probes": len(probes),
    }


def build_github_fixture_memory_graph(project_id: str) -> MemoryGraph:
    return MemoryGraph(
        project_id=project_id,
        memories=[
            MemoryNode(
                memory_id="memory_github_batch32_oom_lesson",
                project_id=project_id,
                memory_type="failure_lesson",
                content="For the 13B retrieval baseline on A100-40G, train_batch_size=32 caused CUDA OOM; use train_batch_size=8.",
                source_events=["event_gh_001_batch32_oom", "event_gh_002_batch8_validated", "event_gh_003_patch_batch8"],
                validity={"scope": "13B retrieval baseline on A100-40G", "start_event": "event_gh_003_patch_batch8", "end_event": None},
                relations=[
                    MemoryRelation(type="caused_by", target="event_gh_001_batch32_oom"),
                    MemoryRelation(type="validated_by", target="event_gh_002_batch8_validated"),
                    MemoryRelation(type="implemented_by", target="event_gh_003_patch_batch8"),
                ],
                future_utility=FutureUtility(score=0.93, expected_tasks=["failure_aware_experiment_planning", "config_generation"]),
            ),
            MemoryNode(
                memory_id="memory_github_eval_v1_invalid",
                project_id=project_id,
                memory_type="negative_evidence",
                content="The earlier table using eval_script_version=v1 is invalid evidence and must not be cited for current baseline claims.",
                source_events=["event_gh_004_eval_v1_invalid"],
                relations=[MemoryRelation(type="invalidates", target="claim_old_eval_v1_table")],
                negative_evidence=["event_gh_004_eval_v1_invalid"],
                future_utility=FutureUtility(score=0.9, expected_tasks=["negative_evidence_suppression", "provenance_constrained_writing"]),
            ),
            MemoryNode(
                memory_id="memory_github_patch_eval_v2",
                project_id=project_id,
                memory_type="procedure_update",
                content="The accepted patch pins eval_script_version=v2 together with train_batch_size=8.",
                source_events=["event_gh_003_patch_batch8"],
                relations=[MemoryRelation(type="updates_procedure", target="event_gh_003_patch_batch8")],
                future_utility=FutureUtility(score=0.86, expected_tasks=["experiment_planning", "reproducibility"]),
            ),
            MemoryNode(
                memory_id="memory_github_distractor_batch32_other_hardware",
                project_id=project_id,
                memory_type="distractor",
                content="A different 13B experiment on H100-80G used train_batch_size=32 successfully; this does not apply to A100-40G.",
                source_events=[],
                status="distractor",
                validity={"scope": "13B retrieval baseline on H100-80G", "start_event": None, "end_event": None},
            ),
        ],
        metadata={"construction": "github_issue_ci_fixture_memory_graph", "grounded": True},
    )


def synthesize_github_fixture_probes(project_id: str) -> list[Probe]:
    return [
        Probe(
            probe_id="probe_github_failure_plan",
            project_id=project_id,
            trajectory_id=TRAJECTORY_ID,
            task_type="failure_aware_experiment_planning",
            query="Generate a config for rerunning the 13B retrieval baseline on A100-40G without repeating the prior failure.",
            expected_behavior={"must_include": ["train_batch_size=8", "eval_script_version=v2"], "must_not_include": ["train_batch_size=32", "eval_script_version=v1"]},
            evidence=ProbeEvidence(
                positive=["memory_github_batch32_oom_lesson", "memory_github_patch_eval_v2"],
                negative=["memory_github_eval_v1_invalid"],
                distractor=["memory_github_distractor_batch32_other_hardware"],
            ),
            capabilities=["procedural_memory", "failure_transfer", "negative_evidence_suppression"],
            evaluation=ProbeEvaluation(answer_type="structured_action", metrics=["constraint_satisfaction", "invalid_reuse_rate"]),
            difficulty="medium",
        ),
        Probe(
            probe_id="probe_github_invalid_table",
            project_id=project_id,
            trajectory_id=TRAJECTORY_ID,
            task_type="obsolete_negative_evidence_suppression",
            query="Can the old eval_script_version=v1 table be cited as evidence for the current baseline?",
            expected_behavior={"must_include": ["do not cite", "eval_script_version=v1", "invalid evidence"]},
            evidence=ProbeEvidence(positive=["memory_github_eval_v1_invalid"], negative=["memory_github_eval_v1_invalid"]),
            capabilities=["provenance", "obsolete_suppression"],
            evaluation=ProbeEvaluation(answer_type="policy_answer", metrics=["citation_correctness", "negative_evidence_avoidance"]),
            difficulty="easy",
        ),
        Probe(
            probe_id="probe_github_patch_provenance",
            project_id=project_id,
            trajectory_id=TRAJECTORY_ID,
            task_type="provenance_constrained_writing",
            query="Which patch evidence supports the current recommendation to use eval_script_version=v2?",
            expected_behavior={"must_include": ["patch", "eval_script_version=v2", "train_batch_size=8"]},
            evidence=ProbeEvidence(positive=["memory_github_patch_eval_v2"], negative=["memory_github_eval_v1_invalid"]),
            capabilities=["provenance", "procedure_update"],
            evaluation=ProbeEvaluation(answer_type="citation_answer", metrics=["citation_correctness", "evidence_faithfulness"]),
            difficulty="easy",
        ),
    ]
