from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List

from ultra_long_benchmark.models import Capability, MemoryChallengeQuery, PersonaTimeline, QCReport, Trajectory, model_validate
from ultra_long_benchmark.shared.io import read_jsonl, write_json, write_text
from ultra_long_benchmark.validation import require_unique


def run_quality_control(timelines_path: Path, trajectories_path: Path, queries_path: Path, output_dir: Path) -> QCReport:
    timelines = [model_validate(PersonaTimeline, row) for row in read_jsonl(timelines_path)]
    trajectories = [model_validate(Trajectory, row) for row in read_jsonl(trajectories_path)]
    queries = [model_validate(MemoryChallengeQuery, row) for row in read_jsonl(queries_path)]
    event_ids = [event.event_id for timeline in timelines for event in timeline.events]
    query_event_ids = [
        event_id
        for query in queries
        for event_id in (
            query.evidence_event_ids
            + query.negative_evidence_event_ids
            + query.obsolete_evidence_event_ids
            + query.distractor_event_ids
        )
    ]
    issues: List[str] = []
    issues.extend(require_unique(event_ids, "event_id"))
    issues.extend(require_unique([q.query_id for q in queries], "query_id"))
    missing = sorted(set(query_event_ids) - set(event_ids))
    issues.extend([f"query evidence references missing event: {event_id}" for event_id in missing])
    if not any(query.privacy_sensitive for query in queries):
        issues.append("no privacy-sensitive challenge queries found")
    expected_capabilities = {capability.value for capability in Capability}
    observed_capabilities = {query.capability.value if hasattr(query.capability, "value") else str(query.capability) for query in queries}
    missing_capabilities = sorted(expected_capabilities - observed_capabilities)
    issues.extend([f"capability has no challenge query: {capability}" for capability in missing_capabilities])
    if not any(query.expected_behavior.startswith("abstain") for query in queries):
        issues.append("no abstention challenge queries found")
    if not any(len(session.linked_event_ids) == 0 for trajectory in trajectories for session in trajectory.sessions):
        issues.append("no distractor sessions found")
    if not any(len(session.linked_event_ids) > 1 for trajectory in trajectories for session in trajectory.sessions):
        issues.append("no multi-event sessions found")
    complexity_features = {
        feature
        for trajectory in trajectories
        for feature in trajectory.metadata.get("complexity_features", [])
    }
    for required_feature in [
        "cross_tool_workflows",
        "distractor_sessions",
        "multi_event_sessions",
        "topic_switching",
        "policy_updates",
        "negative_policy_examples",
        "privacy_authorization_boundaries",
        "ambiguous_authorization_gaps",
    ]:
        if required_feature not in complexity_features:
            issues.append(f"missing trajectory complexity feature: {required_feature}")
    required_tasks = {
        "implicit_policy_induction",
        "policy_update_and_exception_handling",
        "cross_day_habit_generalization",
        "routine_step_ordering",
        "contextual_workflow_policy_selection",
        "negative_example_storage_gating",
        "tool_action_policy_alignment",
        "privacy_authorization_boundary",
        "authorization_gap_clarification",
        "artifact_management_habit_transfer",
        "cross_tool_boundary_composition",
    }
    observed_tasks = {query.memory_task for query in queries}
    for missing_task in sorted(required_tasks - observed_tasks):
        issues.append(f"memory task has no challenge query: {missing_task}")
    if not any(query.negative_evidence_event_ids for query in queries):
        issues.append("no query includes negative evidence")
    if not any(query.obsolete_evidence_event_ids for query in queries):
        issues.append("no query includes obsolete evidence")
    report = QCReport(
        task="annotation_and_quality_control",
        generated_at=datetime.now(timezone.utc),
        counts={"timelines": len(timelines), "trajectories": len(trajectories), "queries": len(queries), "events": len(event_ids)},
        issues=issues,
        passed=not issues,
    )
    write_json(output_dir / "qc_report.json", report)
    write_text(output_dir / "human_annotation_template.md", annotation_template())
    return report


def annotation_template() -> str:
    return """# Human Annotation Template

For each query, annotate:

- `answer_correct`: yes/no/partial
- `evidence_sufficient`: yes/no
- `policy_capability`: one of the schema capabilities
- `privacy_policy_followed`: yes/no/not_applicable
- `tool_action_allowed`: yes/no/needs_clarification
- `policy_evidence_sufficient`: yes/no
- `notes`: free-form rationale with cited event IDs

IAA hook: export two annotator JSONL files with matching `query_id` fields and compute agreement per label.
"""
