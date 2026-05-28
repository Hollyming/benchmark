from __future__ import annotations

import argparse
from pathlib import Path

from ultra_long_benchmark.audit import audit_generated, format_audit_text
from ultra_long_benchmark.pipelines.evaluation import run_baseline_evaluation
from ultra_long_benchmark.pipelines.ingestion import ingest_seed_documents
from ultra_long_benchmark.pipelines.literature import build_literature_map
from ultra_long_benchmark.pipelines.persona import simulate_personas
from ultra_long_benchmark.pipelines.qc import run_quality_control
from ultra_long_benchmark.pipelines.query import generate_queries
from ultra_long_benchmark.pipelines.release import package_release
from ultra_long_benchmark.pipelines.stress import compute_stress_profiles
from ultra_long_benchmark.pipelines.trajectory import generate_trajectories
from ultra_long_benchmark.shared.io import write_json


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "examples" / "generated"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ultra-long benchmark construction CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("smoke").add_argument("--all", action="store_true", help="Run all offline demo stages.")
    sub.add_parser("literature")
    sub.add_parser("ingest")
    sub.add_parser("simulate")
    sub.add_parser("trajectories")
    sub.add_parser("queries")
    sub.add_parser("qc")
    sub.add_parser("evaluate")
    sub.add_parser("release")
    sub.add_parser("stress")
    audit = sub.add_parser("audit")
    audit.add_argument("--generated-dir", type=Path, default=GENERATED, help="Generated artifact directory to audit.")
    audit.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    audit.add_argument("--output", type=Path, help="Optional path for the JSON audit report.")
    sub.add_parser("validate")
    args = parser.parse_args()

    if args.command == "smoke":
        run_smoke_all()
    elif args.command == "literature":
        build_literature_map(ROOT / "tasks" / "literature_and_taxonomy" / "configs" / "paper_seeds.yaml", GENERATED / "literature_and_taxonomy")
    elif args.command == "ingest":
        ingest_seed_documents(ROOT / "examples" / "seed_documents.jsonl", GENERATED / "seed_corpora_ingestion" / "source_documents.jsonl")
    elif args.command == "simulate":
        simulate_personas(ROOT / "configs" / "persona_simulation.yaml", GENERATED / "persona_life_event_simulation" / "personas.jsonl")
    elif args.command == "trajectories":
        generate_trajectories(GENERATED / "persona_life_event_simulation" / "personas.jsonl", GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl")
    elif args.command == "queries":
        generate_queries(
            GENERATED / "persona_life_event_simulation" / "personas.jsonl",
            GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
            GENERATED / "memory_challenge_query_generation" / "queries.jsonl",
        )
    elif args.command == "qc":
        run_quality_control(
            GENERATED / "persona_life_event_simulation" / "personas.jsonl",
            GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
            GENERATED / "memory_challenge_query_generation" / "queries.jsonl",
            GENERATED / "annotation_and_quality_control",
        )
    elif args.command == "evaluate":
        run_baseline_evaluation(GENERATED / "memory_challenge_query_generation" / "queries.jsonl", GENERATED / "evaluation_harness" / "baseline_metrics.json")
    elif args.command == "release":
        package_release(
            GENERATED / "persona_life_event_simulation" / "personas.jsonl",
            GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
            GENERATED / "memory_challenge_query_generation" / "queries.jsonl",
            GENERATED / "release_packaging",
        )
    elif args.command == "stress":
        report = compute_stress_profiles(
            GENERATED / "persona_life_event_simulation" / "personas.jsonl",
            GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
            GENERATED / "memory_challenge_query_generation" / "queries.jsonl",
            GENERATED / "evaluation_harness" / "stress_profile.json",
        )
        print(f"stress profiles written: trajectories={report['summary']['trajectories']} max_horizon_days={report['summary']['max_horizon_days']}")
    elif args.command == "validate":
        validate_generated()
    elif args.command == "audit":
        report = audit_generated(args.generated_dir)
        if args.output:
            write_json(args.output, report)
        if args.json:
            import json

            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(format_audit_text(report))
        if not report["passed"]:
            raise SystemExit(1)


def run_smoke_all() -> None:
    build_literature_map(ROOT / "tasks" / "literature_and_taxonomy" / "configs" / "paper_seeds.yaml", GENERATED / "literature_and_taxonomy")
    ingest_seed_documents(ROOT / "examples" / "seed_documents.jsonl", GENERATED / "seed_corpora_ingestion" / "source_documents.jsonl")
    simulate_personas(ROOT / "configs" / "persona_simulation.yaml", GENERATED / "persona_life_event_simulation" / "personas.jsonl")
    generate_trajectories(GENERATED / "persona_life_event_simulation" / "personas.jsonl", GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl")
    generate_queries(
        GENERATED / "persona_life_event_simulation" / "personas.jsonl",
        GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
        GENERATED / "memory_challenge_query_generation" / "queries.jsonl",
    )
    report = run_quality_control(
        GENERATED / "persona_life_event_simulation" / "personas.jsonl",
        GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
        GENERATED / "memory_challenge_query_generation" / "queries.jsonl",
        GENERATED / "annotation_and_quality_control",
    )
    run_baseline_evaluation(GENERATED / "memory_challenge_query_generation" / "queries.jsonl", GENERATED / "evaluation_harness" / "baseline_metrics.json")
    compute_stress_profiles(
        GENERATED / "persona_life_event_simulation" / "personas.jsonl",
        GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
        GENERATED / "memory_challenge_query_generation" / "queries.jsonl",
        GENERATED / "evaluation_harness" / "stress_profile.json",
    )
    package_release(
        GENERATED / "persona_life_event_simulation" / "personas.jsonl",
        GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
        GENERATED / "memory_challenge_query_generation" / "queries.jsonl",
        GENERATED / "release_packaging",
    )
    if not report.passed:
        raise SystemExit(f"QC failed: {report.issues}")
    print("offline smoke pipeline completed")


def validate_generated() -> None:
    from ultra_long_benchmark.models import MemoryChallengeQuery, PersonaTimeline, SourceDocument, Trajectory
    from ultra_long_benchmark.validation import validate_jsonl

    checks = {
        "source_documents": validate_jsonl(GENERATED / "seed_corpora_ingestion" / "source_documents.jsonl", SourceDocument),
        "personas": validate_jsonl(GENERATED / "persona_life_event_simulation" / "personas.jsonl", PersonaTimeline),
        "trajectories": validate_jsonl(GENERATED / "multi_session_agent_trajectory_generation" / "trajectories.jsonl", Trajectory),
        "queries": validate_jsonl(GENERATED / "memory_challenge_query_generation" / "queries.jsonl", MemoryChallengeQuery),
    }
    print("validated " + ", ".join(f"{key}={value}" for key, value in checks.items()))


if __name__ == "__main__":
    main()
