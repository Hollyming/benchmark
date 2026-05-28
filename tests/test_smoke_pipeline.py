from pathlib import Path

from ultra_long_benchmark.cli import run_smoke_all
from ultra_long_benchmark.models import MemoryChallengeQuery, PersonaTimeline, Trajectory
from ultra_long_benchmark.shared.io import read_json, read_jsonl
from ultra_long_benchmark.validation import validate_jsonl


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "examples" / "generated"


def test_smoke_pipeline_outputs_valid_artifacts():
    run_smoke_all()
    assert validate_jsonl(GENERATED / "persona_life_event_simulation" / "personas.jsonl", PersonaTimeline) == 2
    assert validate_jsonl(GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl", Trajectory) == 2
    assert validate_jsonl(GENERATED / "memory_challenge_query_generation" / "queries.jsonl", MemoryChallengeQuery) == 8
    qc = read_json(GENERATED / "annotation_and_quality_control" / "qc_report.json")
    assert qc["passed"] is True
    metrics = read_json(GENERATED / "evaluation_harness" / "baseline_metrics.json")
    assert metrics["exact_or_policy_accuracy"] == 1.0


def test_privacy_query_requires_refusal():
    queries = read_jsonl(GENERATED / "memory_challenge_query_generation" / "queries.jsonl")
    privacy_queries = [query for query in queries if query["privacy_sensitive"]]
    assert privacy_queries
    assert all(query["expected_behavior"] == "refuse_or_redact" for query in privacy_queries)

