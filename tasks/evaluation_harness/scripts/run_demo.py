from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ultra_long_benchmark.pipelines.evaluation import run_baseline_evaluation


if __name__ == "__main__":
    metrics = run_baseline_evaluation(
        ROOT / "examples" / "generated" / "memory_challenge_query_generation" / "queries.jsonl",
        ROOT / "examples" / "generated" / "evaluation_harness" / "baseline_metrics.json",
    )
    print(f"evaluated {metrics['n']} queries accuracy={metrics['exact_or_policy_accuracy']:.3f}")

