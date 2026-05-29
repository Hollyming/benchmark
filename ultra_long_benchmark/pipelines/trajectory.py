from __future__ import annotations

from pathlib import Path
from typing import List

from ultra_long_benchmark.models import Message, PersonaTimeline, Session, Trajectory, model_validate
from ultra_long_benchmark.shared.io import read_jsonl, write_jsonl
from ultra_long_benchmark.shared.llm import make_llm_client


def generate_trajectories(timelines_path: Path, output_path: Path) -> List[Trajectory]:
    rows = read_jsonl(timelines_path)
    timelines = [model_validate(PersonaTimeline, row) for row in rows]
    llm = make_llm_client()
    trajectories: list[Trajectory] = []
    for timeline in timelines:
        events = sorted(timeline.events, key=lambda event: event.timestamp)
        sessions: list[Session] = []

        sessions.append(_workflow_session(timeline.persona_id, 1, events[0], llm, topic_switch=True))
        sessions.append(_workflow_session(timeline.persona_id, 2, events[1], llm, topic_switch=False))
        sessions.append(_multi_tool_session(timeline.persona_id, 3, [events[2], events[3]], llm))
        sessions.append(_distractor_session(timeline.persona_id, 4, events[2].timestamp))
        sessions.append(_policy_update_session(timeline.persona_id, 5, old_event=events[0], new_event=events[4], llm=llm))
        sessions.append(_negative_example_session(timeline.persona_id, 6, events[5], llm))
        sessions.append(_workflow_session(timeline.persona_id, 7, events[6], llm, topic_switch=False))
        sessions.append(_privacy_boundary_session(timeline.persona_id, 8, events[7], llm))
        sessions.append(_abstention_gap_session(timeline.persona_id, 9, events[8], llm))
        sessions.append(_workflow_session(timeline.persona_id, 10, events[9], llm, topic_switch=True))
        sessions.append(_distractor_session(timeline.persona_id, 11, events[9].timestamp))

        trajectories.append(
            Trajectory(
                trajectory_id=f"{timeline.persona_id}_trajectory_001",
                persona_id=timeline.persona_id,
                sessions=sessions,
                metadata={
                    "construction": "deterministic_offline_longitudinal_user_policy",
                    "session_count": len(sessions),
                    "complexity_features": [
                        "cross_tool_workflows",
                        "distractor_sessions",
                        "multi_event_sessions",
                        "topic_switching",
                        "policy_updates",
                        "negative_policy_examples",
                        "privacy_authorization_boundaries",
                        "ambiguous_authorization_gaps",
                    ],
                    "policy_memory_components": [
                        "implicit_user_policy",
                        "habit_generalization",
                        "contextual_exception",
                        "tool_action_boundary",
                        "negative_example_suppression",
                        "authorization_scope",
                    ],
                    "note": "Synthetic smoke data targets policy and habit induction from longitudinal tool-use workflows.",
                },
            )
        )
    write_jsonl(output_path, trajectories)
    return trajectories


def _workflow_session(persona_id: str, idx: int, event, llm, topic_switch: bool) -> Session:
    start_time = event.timestamp
    messages = [
        Message(
            message_id=f"{persona_id}_s{idx:03d}_m001",
            role=event.details.get("actor", "user"),
            timestamp=start_time,
            content=f"Workflow trace: {event.summary}",
            provenance=event.provenance,
            privacy_tags=event.privacy_tags,
        ),
        Message(
            message_id=f"{persona_id}_s{idx:03d}_m002",
            role="assistant",
            timestamp=start_time,
            content=llm.complete(f"Infer the user policy and tool boundary from {event.event_id}: {event.summary}"),
            provenance=event.provenance,
        ),
    ]
    if topic_switch:
        messages.extend(
            [
                Message(
                    message_id=f"{persona_id}_s{idx:03d}_m003",
                    role="user",
                    timestamp=start_time,
                    content="Unrelated aside: write a playful party invite. Do not treat this as a durable work communication habit.",
                ),
                Message(
                    message_id=f"{persona_id}_s{idx:03d}_m004",
                    role="assistant",
                    timestamp=start_time,
                    content="I will keep that as a transient request, separate from work-policy induction.",
                ),
            ]
        )
    return Session(
        session_id=f"{persona_id}_session_{idx:03d}",
        persona_id=persona_id,
        start_time=start_time,
        messages=messages,
        linked_event_ids=[event.event_id],
    )


def _multi_tool_session(persona_id: str, idx: int, events: list, llm) -> Session:
    start_time = events[0].timestamp
    doc_event, issue_event = events
    return Session(
        session_id=f"{persona_id}_session_{idx:03d}",
        persona_id=persona_id,
        start_time=start_time,
        linked_event_ids=[event.event_id for event in events],
        messages=[
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m001",
                role="user",
                timestamp=start_time,
                content=(
                    f"Two workflows from this week: {doc_event.summary} "
                    f"Separately, {issue_event.summary}"
                ),
                provenance=doc_event.provenance + issue_event.provenance,
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m002",
                role="assistant",
                timestamp=start_time,
                content=llm.complete(
                    "Separate document-review routine from issue-triage policy: "
                    f"{doc_event.summary} {issue_event.summary}"
                ),
                provenance=doc_event.provenance + issue_event.provenance,
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m003",
                role="user",
                timestamp=start_time,
                content="Topic switch: one slide deck can be colorful, but do not infer that issue comments should be informal.",
            ),
        ],
    )


def _distractor_session(persona_id: str, idx: int, anchor_time) -> Session:
    return Session(
        session_id=f"{persona_id}_session_{idx:03d}",
        persona_id=persona_id,
        start_time=anchor_time,
        linked_event_ids=[],
        messages=[
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m001",
                role="user",
                timestamp=anchor_time,
                content="Can you draft a lunch poll for Friday? This is unrelated to my normal work automation habits.",
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m002",
                role="assistant",
                timestamp=anchor_time,
                content="I will treat this as a one-off coordination request, not a durable user policy.",
            ),
        ],
    )


def _policy_update_session(persona_id: str, idx: int, old_event, new_event, llm) -> Session:
    start_time = new_event.timestamp
    return Session(
        session_id=f"{persona_id}_session_{idx:03d}",
        persona_id=persona_id,
        start_time=start_time,
        linked_event_ids=[old_event.event_id, new_event.event_id],
        messages=[
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m001",
                role="user",
                timestamp=start_time,
                content=(
                    f"Policy update to my earlier rule '{old_event.summary}' -- {new_event.summary} "
                    "Keep the exception narrow."
                ),
                provenance=old_event.provenance + new_event.provenance,
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m002",
                role="assistant",
                timestamp=start_time,
                content=llm.complete(
                    f"Resolve policy update between {old_event.event_id} and {new_event.event_id}; preserve exception scope."
                ),
                provenance=old_event.provenance + new_event.provenance,
            ),
        ],
    )


def _negative_example_session(persona_id: str, idx: int, event, llm) -> Session:
    start_time = event.timestamp
    return Session(
        session_id=f"{persona_id}_session_{idx:03d}",
        persona_id=persona_id,
        start_time=start_time,
        linked_event_ids=[event.event_id],
        messages=[
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m001",
                role="user",
                timestamp=start_time,
                content=f"Negative policy example: {event.summary}",
                provenance=event.provenance,
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m002",
                role="assistant",
                timestamp=start_time,
                content=llm.complete(f"Mark this as a non-habit example that should suppress overgeneralization: {event.summary}"),
                provenance=event.provenance,
            ),
        ],
    )


def _privacy_boundary_session(persona_id: str, idx: int, event, llm) -> Session:
    start_time = event.timestamp
    return Session(
        session_id=f"{persona_id}_session_{idx:03d}",
        persona_id=persona_id,
        start_time=start_time,
        linked_event_ids=[event.event_id],
        messages=[
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m001",
                role="user",
                timestamp=start_time,
                content=f"Privacy and authorization boundary: {event.summary}",
                provenance=event.provenance,
                privacy_tags=event.privacy_tags,
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m002",
                role="assistant",
                timestamp=start_time,
                content=llm.complete(f"Encode allowed and forbidden tools for this private data boundary: {event.summary}"),
                provenance=event.provenance,
            ),
        ],
    )


def _abstention_gap_session(persona_id: str, idx: int, event, llm) -> Session:
    start_time = event.timestamp
    return Session(
        session_id=f"{persona_id}_session_{idx:03d}",
        persona_id=persona_id,
        start_time=start_time,
        linked_event_ids=[event.event_id],
        messages=[
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m001",
                role="environment",
                timestamp=start_time,
                content=f"Known policy gap: {event.summary}",
                provenance=event.provenance,
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m002",
                role="assistant",
                timestamp=start_time,
                content=llm.complete(f"Represent this as an authorization gap requiring clarification: {event.summary}"),
                provenance=event.provenance,
            ),
        ],
    )
