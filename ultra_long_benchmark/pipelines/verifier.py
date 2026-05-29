from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ultra_long_benchmark.models import (
    CanonicalEvent,
    MemoryGraph,
    Probe,
    ProjectProfile,
    SourceArtifact,
    VerifierReport,
    model_validate,
)
from ultra_long_benchmark.pipelines.capability_contracts import TASK_CONTRACTS
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_json


def run_project_verifier(project_dir: Path, output_path: Path | None = None) -> VerifierReport:
    project_dir = Path(project_dir)
    profile = model_validate(ProjectProfile, read_json(project_dir / "project_profile.json"))
    artifacts = [model_validate(SourceArtifact, row) for row in read_jsonl(project_dir / "artifacts.jsonl")]
    events = [model_validate(CanonicalEvent, row) for row in read_jsonl(project_dir / "events.jsonl")]
    graph = model_validate(MemoryGraph, read_json(project_dir / "memory_graph.json"))
    probes = [model_validate(Probe, row) for row in read_jsonl(project_dir / "probes.jsonl")]

    issues: list[str] = []
    artifact_ids = {artifact.artifact_id for artifact in artifacts}
    event_ids = {event.event_id for event in events}
    claim_ids = {claim for event in events for claim in event.claims}
    invalidation_targets = event_ids | claim_ids
    memory_by_id = {memory.memory_id: memory for memory in graph.memories}
    memory_ids = set(memory_by_id)
    event_by_id = {event.event_id: event for event in events}
    artifact_by_id = {artifact.artifact_id: artifact for artifact in artifacts}

    if profile.project_id != graph.project_id:
        issues.append("project profile and memory graph project_id mismatch")
    if not artifacts:
        issues.append("no source artifacts found")
    if not events:
        issues.append("no canonical events found")
    if not graph.memories:
        issues.append("no memory graph nodes found")
    if not probes:
        issues.append("no probes found")

    for event in events:
        missing_artifacts = sorted(set(event.artifacts) - artifact_ids)
        for artifact_id in missing_artifacts:
            issues.append(f"event {event.event_id} references missing artifact {artifact_id}")
        if not event.raw_pointer:
            issues.append(f"event {event.event_id} missing raw_pointer")
        if event.source_dataset != "synthetic_bridge" and not event.artifacts:
            issues.append(f"reference-grounded event {event.event_id} has no artifacts")
        for target in event.invalidates:
            if target not in invalidation_targets:
                issues.append(f"event {event.event_id} invalidates unknown target {target}")
        for relation_name, targets in [("causal_links", event.causal_links), ("supersedes", event.supersedes)]:
            for target in targets:
                target_event = event_by_id.get(target)
                if target_event is None:
                    issues.append(f"event {event.event_id} {relation_name} references missing event {target}")
                elif target_event.timestamp > event.timestamp:
                    issues.append(f"event {event.event_id} {relation_name} points to later event {target}")

    for memory in graph.memories:
        missing_events = sorted(set(memory.source_events) - event_ids)
        for event_id in missing_events:
            issues.append(f"memory {memory.memory_id} references missing source event {event_id}")
        if memory.status == "active" and not memory.source_events:
            issues.append(f"active memory {memory.memory_id} has no source events")
        if memory.status != "distractor" and memory.memory_type != "distractor" and not memory.source_events:
            issues.append(f"non-distractor memory {memory.memory_id} has no source events")
        if _requires_action_boundary(memory) and not _has_action_boundary(memory):
            issues.append(f"policy memory {memory.memory_id} missing action boundary")

    for probe in probes:
        evidence_ids = probe.evidence.positive + probe.evidence.negative + probe.evidence.obsolete + probe.evidence.distractor
        if not probe.evidence.positive:
            issues.append(f"probe {probe.probe_id} has no positive evidence")
        for memory_id in sorted(set(evidence_ids) - memory_ids):
            issues.append(f"probe {probe.probe_id} references missing memory {memory_id}")
        for memory_id in probe.evidence.negative:
            memory = memory_by_id.get(memory_id)
            if memory and memory.memory_type != "negative_evidence" and not memory.negative_evidence:
                issues.append(f"probe {probe.probe_id} negative evidence {memory_id} is not a negative-evidence memory")
        if _requires_multi_actor_policy(probe):
            actors = _actors_for_positive_evidence(probe, memory_by_id, event_by_id)
            if len(actors) < 2:
                issues.append(f"probe {probe.probe_id} multi-actor policy evidence has fewer than two actors")
        if not probe.expected_behavior:
            issues.append(f"probe {probe.probe_id} missing expected_behavior")
        issues.extend(_contract_issues(probe, memory_by_id, event_by_id, artifact_by_id))

    checks = {
        "schema_validity": True,
        "provenance_completeness": not any("missing artifact" in issue or "missing raw_pointer" in issue or "has no artifacts" in issue for issue in issues),
        "invalidation_targets_known": not any("invalidates unknown target" in issue for issue in issues),
        "temporal_relations_valid": not any("causal_links references missing event" in issue or "supersedes references missing event" in issue or "points to later event" in issue for issue in issues),
        "memory_graph_grounding": not any("source event" in issue or "no source events" in issue for issue in issues),
        "negative_evidence_links_valid": not any("is not a negative-evidence memory" in issue for issue in issues),
        "multi_actor_policy_coverage": not any("multi-actor policy evidence has fewer than two actors" in issue for issue in issues),
        "action_boundaries_present": not any("missing action boundary" in issue for issue in issues),
        "evidence_sufficiency": not any("no positive evidence" in issue or "missing memory" in issue for issue in issues),
        "task_contracts_valid": not any("violates task contract" in issue for issue in issues),
        "negative_evidence_present": any(probe.evidence.negative for probe in probes),
        "distractor_evidence_present": any(probe.evidence.distractor for probe in probes),
        "multi_task_coverage": len({probe.task_type for probe in probes}) >= 3,
    }
    if not checks["negative_evidence_present"]:
        issues.append("no probe contains negative evidence")
    if not checks["distractor_evidence_present"]:
        issues.append("no probe contains distractor evidence")
    if not checks["multi_task_coverage"]:
        issues.append("fewer than three probe task types")

    report = VerifierReport(
        project_id=profile.project_id,
        generated_at=datetime.now(timezone.utc),
        checks=checks,
        counts={
            "artifacts": len(artifacts),
            "events": len(events),
            "memories": len(graph.memories),
            "probes": len(probes),
            "probe_task_types": len({probe.task_type for probe in probes}),
        },
        issues=issues,
        passed=not issues and all(checks.values()),
    )
    if output_path is None:
        output_path = project_dir / "verifier_report.json"
    write_json(output_path, report)
    return report


def _requires_multi_actor_policy(probe: Probe) -> bool:
    tokens = [probe.task_type, *probe.capabilities]
    joined = " ".join(tokens).lower()
    return any(marker in joined for marker in ["cross_tool_boundary", "routine_step_ordering"])


def _requires_action_boundary(memory: Any) -> bool:
    return memory.memory_type in {
        "user_policy",
        "work_habit",
        "workflow_routine",
        "contextual_policy",
        "policy_exception",
        "negative_policy_example",
        "authorization_boundary",
        "authorization_gap",
    }


def _has_action_boundary(memory: Any) -> bool:
    boundary = getattr(memory, "action_boundary", None)
    if boundary is None:
        return False
    fields = [
        boundary.allowed_actions,
        boundary.forbidden_actions,
        boundary.requires_approval,
        boundary.requires_clarification,
        boundary.authorized_tools,
        boundary.forbidden_tools,
    ]
    return any(fields)


def _actors_for_positive_evidence(probe: Probe, memory_by_id: dict[str, Any], event_by_id: dict[str, CanonicalEvent]) -> set[str]:
    actors: set[str] = set()
    for memory_id in probe.evidence.positive:
        memory = memory_by_id.get(memory_id)
        if not memory:
            continue
        for event_id in memory.source_events:
            event = event_by_id.get(event_id)
            if event:
                actors.add(event.actor)
    return actors


def _contract_issues(
    probe: Probe,
    memory_by_id: dict[str, Any],
    event_by_id: dict[str, CanonicalEvent],
    artifact_by_id: dict[str, SourceArtifact],
) -> list[str]:
    contract = TASK_CONTRACTS.get(probe.task_type)
    if contract is None:
        return []
    issues: list[str] = []
    positive_memories = [memory_by_id[memory_id] for memory_id in probe.evidence.positive if memory_id in memory_by_id]
    evidence_memories = [
        memory_by_id[memory_id]
        for memory_id in probe.evidence.positive + probe.evidence.negative + probe.evidence.obsolete + probe.evidence.distractor
        if memory_id in memory_by_id
    ]

    if len(positive_memories) < contract.min_positive_memories:
        issues.append(_contract_issue(probe, f"requires at least {contract.min_positive_memories} positive memories"))
    positive_types = {memory.memory_type for memory in positive_memories}
    all_types = {memory.memory_type for memory in evidence_memories}
    missing_positive_types = sorted(contract.required_positive_memory_types - positive_types)
    if missing_positive_types:
        issues.append(_contract_issue(probe, f"missing positive memory types {missing_positive_types}"))
    missing_any_types = sorted(contract.required_any_memory_types - all_types)
    if missing_any_types:
        issues.append(_contract_issue(probe, f"missing evidence memory types {missing_any_types}"))
    if contract.require_negative_evidence and not probe.evidence.negative:
        issues.append(_contract_issue(probe, "requires negative evidence"))
    if contract.require_distractor_evidence and not probe.evidence.distractor:
        issues.append(_contract_issue(probe, "requires distractor evidence"))
    if contract.require_future_utility and not any(memory.future_utility is not None for memory in positive_memories):
        issues.append(_contract_issue(probe, "requires future utility labels on positive evidence"))
    if contract.require_invalidating_event and not _has_invalidating_event(evidence_memories, event_by_id):
        issues.append(_contract_issue(probe, "requires evidence grounded in an invalidating event"))

    artifact_types, source_datasets = _supporting_artifact_coverage(positive_memories, event_by_id, artifact_by_id)
    if len(artifact_types) < contract.min_supporting_artifact_types:
        issues.append(_contract_issue(probe, f"requires at least {contract.min_supporting_artifact_types} supporting artifact types"))
    if len(source_datasets) < contract.min_supporting_source_datasets:
        issues.append(_contract_issue(probe, f"requires at least {contract.min_supporting_source_datasets} supporting source datasets"))
    return issues


def _contract_issue(probe: Probe, reason: str) -> str:
    return f"probe {probe.probe_id} violates task contract for {probe.task_type}: {reason}"


def _has_invalidating_event(memories: list[Any], event_by_id: dict[str, CanonicalEvent]) -> bool:
    for memory in memories:
        if memory.negative_evidence:
            return True
        if any(relation.type in {"invalidates", "supersedes", "obsolete"} for relation in memory.relations):
            return True
        for event_id in memory.source_events:
            event = event_by_id.get(event_id)
            if event and (event.invalidates or event.supersedes or event.event_type in {"negative_evidence", "invalidation", "correction"}):
                return True
    return False


def _supporting_artifact_coverage(
    memories: list[Any],
    event_by_id: dict[str, CanonicalEvent],
    artifact_by_id: dict[str, SourceArtifact],
) -> tuple[set[str], set[str]]:
    artifact_types: set[str] = set()
    source_datasets: set[str] = set()
    for memory in memories:
        for event_id in memory.source_events:
            event = event_by_id.get(event_id)
            if not event:
                continue
            source_datasets.add(event.source_dataset)
            for artifact_id in event.artifacts:
                artifact = artifact_by_id.get(artifact_id)
                if artifact:
                    artifact_types.add(artifact.artifact_type)
                    source_datasets.add(artifact.source_dataset)
    return artifact_types, source_datasets


def verify_grounded_projects(projects_dir: Path) -> dict[str, Any]:
    reports = []
    for project_dir in sorted(path for path in Path(projects_dir).iterdir() if path.is_dir()):
        reports.append(run_project_verifier(project_dir))
    return {
        "projects": len(reports),
        "passed": all(report.passed for report in reports),
        "reports": [report.model_dump(mode="json") if hasattr(report, "model_dump") else report.dict() for report in reports],
    }
