from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ultra_long_benchmark.pipelines.persona import simulate_personas


if __name__ == "__main__":
    personas = simulate_personas(
        ROOT / "configs" / "persona_simulation.yaml",
        ROOT / "examples" / "generated" / "persona_life_event_simulation" / "personas.jsonl",
    )
    print(f"wrote {len(personas)} persona timelines")

