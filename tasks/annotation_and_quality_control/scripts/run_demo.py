from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ultra_long_benchmark.pipelines.qc import run_quality_control


if __name__ == "__main__":
    report = run_quality_control(
        ROOT / "examples" / "generated" / "persona_life_event_simulation" / "personas.jsonl",
        ROOT / "examples" / "generated" / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
        ROOT / "examples" / "generated" / "memory_challenge_query_generation" / "queries.jsonl",
        ROOT / "examples" / "generated" / "annotation_and_quality_control",
    )
    print(f"qc passed={report.passed} issues={len(report.issues)}")

