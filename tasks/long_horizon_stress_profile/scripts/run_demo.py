from pathlib import Path

from ultra_long_benchmark.cli import GENERATED
from ultra_long_benchmark.pipelines.stress import compute_stress_profiles


compute_stress_profiles(
    GENERATED / "persona_life_event_simulation" / "personas.jsonl",
    GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
    GENERATED / "memory_challenge_query_generation" / "queries.jsonl",
    GENERATED / "evaluation_harness" / "stress_profile.json",
)
print("wrote stress profile")
