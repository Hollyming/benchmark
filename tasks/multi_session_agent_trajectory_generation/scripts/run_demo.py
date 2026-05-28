from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ultra_long_benchmark.pipelines.trajectory import generate_trajectories


if __name__ == "__main__":
    trajectories = generate_trajectories(
        ROOT / "examples" / "generated" / "persona_life_event_simulation" / "personas.jsonl",
        ROOT / "examples" / "generated" / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
    )
    print(f"wrote {len(trajectories)} trajectories")

