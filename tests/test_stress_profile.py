from pathlib import Path

from ultra_long_benchmark.cli import run_smoke_all
from ultra_long_benchmark.pipelines.stress import compute_stress_profiles
from ultra_long_benchmark.shared.io import read_json


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "examples" / "generated"


def test_stress_profile_reports_long_horizon_statistics():
    run_smoke_all()
    report_path = GENERATED / "evaluation_harness" / "stress_profile.json"
    report = compute_stress_profiles(
        GENERATED / "persona_life_event_simulation" / "personas.jsonl",
        GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
        GENERATED / "memory_challenge_query_generation" / "queries.jsonl",
        report_path,
    )
    assert report["summary"]["max_horizon_days"] >= 400
    assert report["summary"]["queries"] == 24
    assert report["summary"]["capability_counts"]["preference_learning"] == 2
    assert report["summary"]["capability_counts"]["semantic_consolidation"] == 2
    assert report["summary"]["capability_counts"]["abstention"] == 2
    assert report["summary"]["trajectory_stressor_counts"]["distractor_sessions"] == 4
    assert report["summary"]["trajectory_stressor_counts"]["multi_event_sessions"] == 4
    assert report["summary"]["trajectory_stressor_counts"]["negative_evidence_mentions"] >= 2
    assert report["summary"]["trajectory_stressor_counts"]["procedural_failure_lessons"] >= 2
    assert report["summary"]["trajectory_stressor_counts"]["multi_role_constraints"] >= 2
    assert report["summary"]["trajectory_stressor_counts"]["delayed_callbacks"] >= 2
    assert report["summary"]["complexity_feature_counts"]["contradictory_updates"] == 2
    assert report["summary"]["experience_memory_component_counts"]["provenance_graph"] == 2
    assert report["summary"]["memory_task_counts"]["failure_aware_experiment_planning"] == 2
    assert "long_3_5_events_back" in report["summary"]["evidence_hop_histogram"]
    persisted = read_json(report_path)
    assert persisted["summary"]["trajectories"] == 2
