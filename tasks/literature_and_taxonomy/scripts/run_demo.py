from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ultra_long_benchmark.pipelines.literature import build_literature_map


if __name__ == "__main__":
    result = build_literature_map(
        ROOT / "tasks" / "literature_and_taxonomy" / "configs" / "paper_seeds.yaml",
        ROOT / "examples" / "generated" / "literature_and_taxonomy",
    )
    print(f"wrote {len(result['papers'])} paper seeds")

