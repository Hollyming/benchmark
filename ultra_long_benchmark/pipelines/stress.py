from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ultra_long_benchmark.models import Capability, MemoryChallengeQuery, PersonaTimeline, Trajectory, model_validate
from ultra_long_benchmark.shared.io import read_jsonl, write_json


@dataclass(frozen=True)
class StressProfile:
    trajectory_id: str
    persona_id: str
    session_count: int
    message_count: int
    event_count: int
    horizon_days: int
    query_count: int
    capability_counts: dict[str, int]
    evidence_hop_histogram: dict[str, int]


def compute_stress_profiles(timelines_path: Path, trajectories_path: Path, queries_path: Path, output_path: Path) -> dict[str, Any]:
    """Compute long-horizon stress statistics for benchmark reporting.

    This is intentionally lightweight and offline: it verifies that generated data
    has measurable temporal span, cross-session structure, capability balance, and
    evidence-hop diversity. Large paper-scale releases can reuse the same contract.
    """
    timelines = [model_validate(PersonaTimeline, row) for row in read_jsonl(timelines_path)]
    trajectories = [model_validate(Trajectory, row) for row in read_jsonl(trajectories_path)]
    queries = [model_validate(MemoryChallengeQuery, row) for row in read_jsonl(queries_path)]

    timeline_by_persona = {timeline.persona_id: timeline for timeline in timelines}
    queries_by_trajectory: dict[str, list[MemoryChallengeQuery]] = defaultdict(list)
    for query in queries:
        queries_by_trajectory[query.trajectory_id].append(query)

    profiles: list[StressProfile] = []
    global_capabilities: Counter[str] = Counter()
    global_hops: Counter[str] = Counter()
    for trajectory in trajectories:
        timeline = timeline_by_persona[trajectory.persona_id]
        events = sorted(timeline.events, key=lambda event: event.timestamp)
        sessions = sorted(trajectory.sessions, key=lambda session: session.start_time)
        horizon_days = 0
        if events:
            horizon_days = (events[-1].timestamp - events[0].timestamp).days
        capability_counts: Counter[str] = Counter()
        hop_counts: Counter[str] = Counter()
        event_index = {event.event_id: index for index, event in enumerate(events)}
        for query in queries_by_trajectory[trajectory.trajectory_id]:
            capability_counts[query.capability.value if isinstance(query.capability, Capability) else str(query.capability)] += 1
            hops = [len(events) - 1 - event_index[event_id] for event_id in query.evidence_event_ids if event_id in event_index]
            bucket = _hop_bucket(max(hops) if hops else 0)
            hop_counts[bucket] += 1
        global_capabilities.update(capability_counts)
        global_hops.update(hop_counts)
        profiles.append(
            StressProfile(
                trajectory_id=trajectory.trajectory_id,
                persona_id=trajectory.persona_id,
                session_count=len(sessions),
                message_count=sum(len(session.messages) for session in sessions),
                event_count=len(events),
                horizon_days=horizon_days,
                query_count=len(queries_by_trajectory[trajectory.trajectory_id]),
                capability_counts=dict(sorted(capability_counts.items())),
                evidence_hop_histogram=dict(sorted(hop_counts.items())),
            )
        )

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "trajectories": len(profiles),
            "personas": len(timelines),
            "queries": len(queries),
            "max_horizon_days": max((profile.horizon_days for profile in profiles), default=0),
            "min_horizon_days": min((profile.horizon_days for profile in profiles), default=0),
            "capability_counts": dict(sorted(global_capabilities.items())),
            "evidence_hop_histogram": dict(sorted(global_hops.items())),
        },
        "profiles": [profile.__dict__ for profile in profiles],
        "interpretation": {
            "horizon_days": "Distance between the first and last persona event.",
            "evidence_hop": "How far back from the latest event the required evidence lies; larger means longer-range memory pressure.",
            "use_in_paper": "Report these statistics by split to demonstrate long-horizon stress rather than only item count.",
        },
    }
    write_json(output_path, report)
    return report


def _hop_bucket(hops_back: int) -> str:
    if hops_back <= 0:
        return "current"
    if hops_back <= 2:
        return "near_1_2_events_back"
    if hops_back <= 5:
        return "long_3_5_events_back"
    return "extreme_6plus_events_back"
