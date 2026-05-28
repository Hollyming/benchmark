from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ultra_long_benchmark.pipelines.query import generate_queries


if __name__ == "__main__":
    queries = generate_queries(
        ROOT / "examples" / "generated" / "persona_life_event_simulation" / "personas.jsonl",
        ROOT / "examples" / "generated" / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
        ROOT / "examples" / "generated" / "memory_challenge_query_generation" / "queries.jsonl",
    )
    print(f"wrote {len(queries)} memory challenge queries")

