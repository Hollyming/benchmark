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

        # A realistic benchmark should not present one clean event per session.
        # This smoke generator deliberately mixes relevant events with distractors,
        # deferred follow-ups, topic switches, contradictory updates, invalidated
        # evidence, procedural failures, and multi-role constraints so memory
        # systems are tested on experience modeling rather than raw recall only.
        sessions.append(_event_session(timeline.persona_id, 1, events[0], llm, topic_switch=True))
        sessions.append(_multi_event_session(timeline.persona_id, 2, [events[1], events[2]], llm))
        sessions.append(_distractor_session(timeline.persona_id, 3, events[1].timestamp))
        sessions.append(_callback_session(timeline.persona_id, 4, events[2], llm))
        sessions.append(_negative_evidence_session(timeline.persona_id, 5, events[3], llm))
        sessions.append(_contradictory_update_session(timeline.persona_id, 6, old_event=events[0], new_event=events[4], llm=llm))
        sessions.append(_failure_lesson_session(timeline.persona_id, 7, events[5], llm))
        sessions.append(_event_session(timeline.persona_id, 8, events[6], llm, topic_switch=True))
        sessions.append(_role_constraint_session(timeline.persona_id, 9, events[7], llm))
        sessions.append(_event_session(timeline.persona_id, 10, events[8], llm, topic_switch=False))
        sessions.append(_distractor_session(timeline.persona_id, 11, events[8].timestamp))

        trajectories.append(
            Trajectory(
                trajectory_id=f"{timeline.persona_id}_trajectory_001",
                persona_id=timeline.persona_id,
                sessions=sessions,
                metadata={
                    "construction": "deterministic_offline_compositional_experience",
                    "session_count": len(sessions),
                    "complexity_features": [
                        "distractor_sessions",
                        "multi_event_sessions",
                        "delayed_callbacks",
                        "topic_switching",
                        "contradictory_updates",
                        "negative_evidence",
                        "procedural_failure_lessons",
                        "multi_role_constraints",
                    ],
                    "experience_memory_components": [
                        "versioned_belief_state",
                        "provenance_graph",
                        "procedural_lessons",
                        "personalized_storage_policy",
                        "negative_evidence_suppression",
                    ],
                    "note": "Synthetic smoke data uses compact examples of paper-scale compositional experience memory stressors.",
                },
            )
        )
    write_jsonl(output_path, trajectories)
    return trajectories


def _event_session(persona_id: str, idx: int, event, llm, topic_switch: bool) -> Session:
    start_time = event.timestamp
    messages = [
        Message(
            message_id=f"{persona_id}_s{idx:03d}_m001",
            role="user",
            timestamp=start_time,
            content=f"Please remember this update for future help: {event.summary}",
            provenance=event.provenance,
            privacy_tags=event.privacy_tags,
        ),
        Message(
            message_id=f"{persona_id}_s{idx:03d}_m002",
            role="assistant",
            timestamp=start_time,
            content=llm.complete(f"Acknowledge and structure memory for event {event.event_id}: {event.summary}"),
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
                    content="Unrelated aside: also help me compare two noise-canceling headphones later, but don't treat this as a durable research memory.",
                ),
                Message(
                    message_id=f"{persona_id}_s{idx:03d}_m004",
                    role="assistant",
                    timestamp=start_time,
                    content="Noted as a short-lived side topic; I will keep it separate from durable project memory.",
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


def _multi_event_session(persona_id: str, idx: int, events: list, llm) -> Session:
    start_time = events[0].timestamp
    project, commitment = events
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
                    f"Two related updates in one meeting: {project.summary} "
                    f"Also, {commitment.summary}"
                ),
                provenance=project.provenance + commitment.provenance,
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m002",
                role="assistant",
                timestamp=start_time,
                content=llm.complete(
                    "Summarize the project memory and deferred commitment separately: "
                    f"{project.summary} {commitment.summary}"
                ),
                provenance=project.provenance + commitment.provenance,
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m003",
                role="user",
                timestamp=start_time,
                content="Quick topic switch: the literature review table should use color only for visual scanning, not as a memory signal.",
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
                content="Can you draft a lunch poll for Friday? It is unrelated to my long-term memory benchmark work.",
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m002",
                role="assistant",
                timestamp=anchor_time,
                content="Sure. I will treat this as a transient coordination request, not as a durable preference or project fact.",
            ),
        ],
    )


def _callback_session(persona_id: str, idx: int, event, llm) -> Session:
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
                content="Earlier I mentioned the benchmark draft deadline. Please keep that deferred callback active when planning my next steps.",
                provenance=event.provenance,
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m002",
                role="assistant",
                timestamp=start_time,
                content=llm.complete(f"Turn this delayed callback into a planning memory grounded in {event.event_id}: {event.summary}"),
                provenance=event.provenance,
            ),
        ],
    )


def _negative_evidence_session(persona_id: str, idx: int, event, llm) -> Session:
    start_time = event.timestamp
    return Session(
        session_id=f"{persona_id}_session_{idx:03d}",
        persona_id=persona_id,
        start_time=start_time,
        linked_event_ids=[event.event_id],
        messages=[
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m001",
                role="tool",
                timestamp=start_time,
                content=f"Experiment audit log: {event.summary}",
                provenance=event.provenance,
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m002",
                role="assistant",
                timestamp=start_time,
                content=llm.complete(f"Mark this as negative evidence that must suppress invalid citations: {event.summary}"),
                provenance=event.provenance,
            ),
        ],
    )


def _contradictory_update_session(persona_id: str, idx: int, old_event, new_event, llm) -> Session:
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
                    f"Correction to my earlier preference '{old_event.summary}' -- {new_event.summary} "
                    "Please use the newer instruction unless I explicitly ask for the old style."
                ),
                provenance=old_event.provenance + new_event.provenance,
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m002",
                role="assistant",
                timestamp=start_time,
                content=llm.complete(
                    f"Resolve the contradiction between {old_event.event_id} and {new_event.event_id}; newer preference wins."
                ),
                provenance=old_event.provenance + new_event.provenance,
            ),
        ],
    )


def _failure_lesson_session(persona_id: str, idx: int, event, llm) -> Session:
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
                content=f"Experiment failure and recovery: {event.summary}",
                provenance=event.provenance,
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m002",
                role="assistant",
                timestamp=start_time,
                content=llm.complete(f"Convert this into a reusable procedural failure lesson with validity scope: {event.summary}"),
                provenance=event.provenance,
            ),
        ],
    )


def _role_constraint_session(persona_id: str, idx: int, event, llm) -> Session:
    start_time = event.timestamp
    return Session(
        session_id=f"{persona_id}_session_{idx:03d}",
        persona_id=persona_id,
        start_time=start_time,
        linked_event_ids=[event.event_id],
        messages=[
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m001",
                role="collaborator",
                timestamp=start_time,
                content=f"Team update with multiple roles: {event.summary}",
                provenance=event.provenance,
            ),
            Message(
                message_id=f"{persona_id}_s{idx:03d}_m002",
                role="assistant",
                timestamp=start_time,
                content=llm.complete(f"Preserve role attribution and constraint priority for: {event.summary}"),
                provenance=event.provenance,
            ),
        ],
    )
