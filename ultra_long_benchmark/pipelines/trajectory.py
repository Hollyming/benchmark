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
        sessions: list[Session] = []
        for idx, event in enumerate(timeline.events, start=1):
            start_time = event.timestamp
            user = Message(
                message_id=f"{event.event_id}_user",
                role="user",
                timestamp=start_time,
                content=f"Please remember this update: {event.summary}",
                provenance=event.provenance,
                privacy_tags=event.privacy_tags,
            )
            assistant = Message(
                message_id=f"{event.event_id}_assistant",
                role="assistant",
                timestamp=start_time,
                content=llm.complete(f"Acknowledge and structure memory for event {event.event_id}: {event.summary}"),
                provenance=event.provenance,
            )
            sessions.append(
                Session(
                    session_id=f"{timeline.persona_id}_session_{idx:03d}",
                    persona_id=timeline.persona_id,
                    start_time=start_time,
                    messages=[user, assistant],
                    linked_event_ids=[event.event_id],
                )
            )
        trajectories.append(
            Trajectory(
                trajectory_id=f"{timeline.persona_id}_trajectory_001",
                persona_id=timeline.persona_id,
                sessions=sessions,
                metadata={"construction": "deterministic_offline", "session_count": len(sessions)},
            )
        )
    write_jsonl(output_path, trajectories)
    return trajectories

