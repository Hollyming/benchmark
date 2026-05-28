from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ultra_long_benchmark.pipelines.release import package_release


if __name__ == "__main__":
    manifest = package_release(
        ROOT / "examples" / "generated" / "persona_life_event_simulation" / "personas.jsonl",
        ROOT / "examples" / "generated" / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
        ROOT / "examples" / "generated" / "memory_challenge_query_generation" / "queries.jsonl",
        ROOT / "examples" / "generated" / "release_packaging",
    )
    print(f"packaged release with {manifest['counts']['queries']} queries")

