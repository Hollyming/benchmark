from __future__ import annotations

import argparse
from pathlib import Path

from ultra_long_benchmark.audit import audit_generated, format_audit_text
from ultra_long_benchmark.data_discovery import DEFAULT_PUBLIC_ROOTS
from ultra_long_benchmark.data_discovery import discover_public_data_sources
from ultra_long_benchmark.pipelines.annotation_pack import build_project_from_policy_rewrites
from ultra_long_benchmark.pipelines.annotation_pack import build_projects_from_policy_rewrite_batch
from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack
from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack_batch
from ultra_long_benchmark.pipelines.annotation_pack import collect_policy_rewrite_job_outputs
from ultra_long_benchmark.pipelines.annotation_pack import export_annotation_pack_release
from ultra_long_benchmark.pipelines.annotation_pack import export_policy_rewrite_prompts
from ultra_long_benchmark.pipelines.annotation_pack import export_policy_rewrite_prompts_batch
from ultra_long_benchmark.pipelines.annotation_pack import package_policy_rewrite_jobs
from ultra_long_benchmark.pipelines.annotation_pack import summarize_gharchive_annotation_scale
from ultra_long_benchmark.pipelines.annotation_pack import validate_policy_rewrite_proposals
from ultra_long_benchmark.pipelines.annotation_pack import validate_policy_rewrite_proposals_batch
from ultra_long_benchmark.pipelines.baseline_configs import run_baseline_config
from ultra_long_benchmark.pipelines.baseline_configs import run_baseline_config_dir
from ultra_long_benchmark.pipelines.baseline_configs import validate_baseline_config
from ultra_long_benchmark.pipelines.baseline_configs import validate_baseline_config_dir
from ultra_long_benchmark.paper_scale import assess_release_scale
from ultra_long_benchmark.paper_tables import export_paper_tables
from ultra_long_benchmark.probe_audit import audit_project_release_probe_leakage
from ultra_long_benchmark.probe_audit import audit_submission_input_probe_leakage
from ultra_long_benchmark.pipelines.evaluation import run_baseline_evaluation
from ultra_long_benchmark.pipelines.evaluation import run_project_baseline_evaluation
from ultra_long_benchmark.pipelines.evaluation import run_project_release_baseline_evaluation
from ultra_long_benchmark.pipelines.evaluation import run_submission_input_baseline
from ultra_long_benchmark.pipelines.evaluation import score_project_release_prediction_dir
from ultra_long_benchmark.pipelines.evaluation import score_project_release_predictions
from ultra_long_benchmark.pipelines.evaluation import score_project_predictions
from ultra_long_benchmark.pipelines.evaluation import score_action_traces
from ultra_long_benchmark.pipelines.gharchive_pilot import DEFAULT_FIXTURE_PATH as DEFAULT_GHARCHIVE_FIXTURE_PATH
from ultra_long_benchmark.pipelines.gharchive_pilot import DEFAULT_REPO as DEFAULT_GHARCHIVE_REPO
from ultra_long_benchmark.pipelines.gharchive_pilot import build_gharchive_slice
from ultra_long_benchmark.pipelines.gharchive_pilot import mine_gharchive_policy_candidates
from ultra_long_benchmark.pipelines.gharchive_pilot import plan_gharchive_stage
from ultra_long_benchmark.pipelines.gharchive_pilot import profile_gharchive_repos
from ultra_long_benchmark.pipelines.gharchive_pilot import profile_gharchive_time_windows
from ultra_long_benchmark.pipelines.gharchive_pilot import rank_gharchive_repos
from ultra_long_benchmark.pipelines.gharchive_pilot import run_gharchive_batch_pilot
from ultra_long_benchmark.pipelines.gharchive_pilot import run_gharchive_pilot
from ultra_long_benchmark.pipelines.gharchive_pilot import select_gharchive_annotation_repos
from ultra_long_benchmark.pipelines.grounded_pilot import run_manual_grounded_pilot
from ultra_long_benchmark.pipelines.github_fixture import run_github_fixture_pilot
from ultra_long_benchmark.pipelines.ingestion import ingest_seed_documents
from ultra_long_benchmark.pipelines.literature import build_literature_map
from ultra_long_benchmark.pipelines.llm_rewrite import run_policy_rewrite_llm_job
from ultra_long_benchmark.pipelines.llm_rewrite import run_policy_rewrite_llm_jobs
from ultra_long_benchmark.pipelines.external_memory_runner import run_external_memory_submission_runner
from ultra_long_benchmark.pipelines.external_memory_runner import validate_external_memory_predictions_against_input
from ultra_long_benchmark.pipelines.memory_submission import plan_external_memory_submission_adapter
from ultra_long_benchmark.pipelines.memory_submission import run_memory_submission_baseline
from ultra_long_benchmark.pipelines.memory_submission import supported_memory_submission_adapters
from ultra_long_benchmark.pipelines.persona import simulate_personas
from ultra_long_benchmark.pipelines.qc import run_quality_control
from ultra_long_benchmark.pipelines.query import generate_queries
from ultra_long_benchmark.pipelines.release import package_release
from ultra_long_benchmark.pipelines.rewrite_audit import export_policy_rewrite_human_audit_pack
from ultra_long_benchmark.pipelines.rewrite_audit import validate_policy_rewrite_human_audit
from ultra_long_benchmark.pipelines.stress import compute_stress_profiles
from ultra_long_benchmark.pipelines.trajectory import generate_trajectories
from ultra_long_benchmark.pipelines.verifier import run_project_verifier
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.project_release import export_project_submission_inputs
from ultra_long_benchmark.project_release import validate_project_prediction_submission
from ultra_long_benchmark.project_release import verify_project_benchmark_release
from ultra_long_benchmark.project_release import verify_project_submission_inputs
from ultra_long_benchmark.readiness import build_readiness_report
from ultra_long_benchmark.release_integrity import verify_annotation_release_integrity
from ultra_long_benchmark.shared.io import read_json
from ultra_long_benchmark.shared.io import write_json
from ultra_long_benchmark.source_audit import audit_workflow_data_sources


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
    evaluate_project = sub.add_parser("evaluate-project")
    evaluate_project.add_argument("project_dir", type=Path, help="Project directory containing memory_graph.json and probes.jsonl.")
    evaluate_project.add_argument("--output", type=Path, help="Optional output JSON path.")
    evaluate_project.add_argument("--top-k", type=int, default=5, help="Raw-RAG top-k event retrieval.")
    evaluate_project.add_argument(
        "--baseline",
        action="append",
        dest="baselines",
        help="Project baseline to run. Repeat for multiple baselines. Defaults to all deterministic project baselines.",
    )
    evaluate_project_release = sub.add_parser("evaluate-project-release")
    evaluate_project_release.add_argument("release_dir", type=Path, help="Project benchmark release directory.")
    evaluate_project_release.add_argument("--output", type=Path, help="Optional output JSON path.")
    evaluate_project_release.add_argument("--top-k", type=int, default=5, help="Raw-RAG top-k event retrieval.")
    evaluate_project_release.add_argument(
        "--baseline",
        action="append",
        dest="baselines",
        help="Project baseline to run. Repeat for multiple baselines. Defaults to all deterministic project baselines.",
    )
    score_traces = sub.add_parser("score-action-traces")
    score_traces.add_argument("project_dir", type=Path, help="Project directory containing memory_graph.json and probes.jsonl.")
    score_traces.add_argument("traces", type=Path, help="JSONL action traces to score.")
    score_traces.add_argument("--output", type=Path, help="Optional output JSON path.")
    score_predictions = sub.add_parser("score-project-predictions")
    score_predictions.add_argument("project_dir", type=Path, help="Project directory containing memory_graph.json and probes.jsonl.")
    score_predictions.add_argument("predictions", type=Path, help="JSONL project predictions to score.")
    score_predictions.add_argument("--output", type=Path, help="Optional output JSON path.")
    score_predictions.add_argument("--system-name", default="external_system", help="Name of the evaluated system.")
    score_release_predictions = sub.add_parser("score-project-release-predictions")
    score_release_predictions.add_argument("release_dir", type=Path, help="Project benchmark release directory.")
    score_release_predictions.add_argument("predictions", type=Path, help="JSONL predictions spanning one or more release projects.")
    score_release_predictions.add_argument("--output", type=Path, help="Optional output JSON path.")
    score_release_predictions.add_argument("--system-name", default="external_system", help="Name of the evaluated system.")
    score_release_prediction_dir = sub.add_parser("score-project-release-prediction-dir")
    score_release_prediction_dir.add_argument("release_dir", type=Path, help="Project benchmark release directory.")
    score_release_prediction_dir.add_argument("predictions_dir", type=Path, help="Directory of ProjectPrediction JSONL submissions.")
    score_release_prediction_dir.add_argument("--output-dir", type=Path, default=GENERATED / "evaluation_harness" / "prediction_scoring_batch", help="Output directory for per-system scoring reports.")
    score_release_prediction_dir.add_argument("--system-name-prefix", help="Optional prefix for system names derived from filenames.")
    submission_baseline = sub.add_parser("run-submission-input-baseline")
    submission_baseline.add_argument("input_dir", type=Path, help="Directory produced by export-project-submission-inputs.")
    submission_baseline.add_argument("--predictions", type=Path, default=GENERATED / "evaluation_harness" / "submission_input_predictions.jsonl", help="Output ProjectPrediction JSONL path.")
    submission_baseline.add_argument("--report", type=Path, help="Optional runner report JSON path.")
    submission_baseline.add_argument("--baseline", default="raw_event_rag_input", choices=["no_memory_input", "raw_event_rag_input", "temporal_event_rag_input"], help="No-gold submission-input baseline to run.")
    submission_baseline.add_argument("--top-k", type=int, default=5, help="Top-k event retrieval for RAG baselines.")
    memory_submission = sub.add_parser("run-memory-submission-baseline")
    memory_submission.add_argument("input_dir", type=Path, help="Directory produced by export-project-submission-inputs.")
    memory_submission.add_argument("--predictions", type=Path, default=GENERATED / "evaluation_harness" / "memory_submission_predictions.jsonl", help="Output ProjectPrediction JSONL path.")
    memory_submission.add_argument("--report", type=Path, help="Optional runner report JSON path.")
    memory_submission.add_argument("--adapter", default="event_profile_stub", choices=list(supported_memory_submission_adapters()), help="Memory-system adapter to run.")
    memory_submission.add_argument("--top-k", type=int, default=5, help="Top-k event retrieval for local no-gold adapters.")
    memory_submission.add_argument("--system-name", help="Name stored in prediction metadata and runner report.")
    memory_submission.add_argument("--allow-external", action="store_true", help="Allow method-specific external adapters after dependencies/API credentials are configured.")
    external_memory_plan = sub.add_parser("plan-external-memory-submission-adapter")
    external_memory_plan.add_argument("input_dir", type=Path, help="Directory produced by export-project-submission-inputs.")
    external_memory_plan.add_argument("--adapter", required=True, choices=["mem0", "a_mem", "graphiti"], help="External memory-system adapter to preflight.")
    external_memory_plan.add_argument("--predictions", type=Path, default=GENERATED / "evaluation_harness" / "external_memory_predictions.jsonl", help="Planned ProjectPrediction JSONL path.")
    external_memory_plan.add_argument("--report", type=Path, help="Optional preflight report JSON path.")
    external_memory_plan.add_argument("--system-name", help="System name for the planned baseline.")
    external_memory_runner = sub.add_parser("run-external-memory-submission-runner")
    external_memory_runner.add_argument("input_dir", type=Path, help="Directory produced by export-project-submission-inputs.")
    external_memory_runner.add_argument("--runner", required=True, help="Dotted plugin target in module:object syntax.")
    external_memory_runner.add_argument("--predictions", type=Path, default=GENERATED / "evaluation_harness" / "external_memory_runner_predictions.jsonl", help="Output ProjectPrediction JSONL path.")
    external_memory_runner.add_argument("--report", type=Path, help="Optional runner report JSON path.")
    external_memory_runner.add_argument("--system-name", help="Name stored in runner report; plugins may also use it in metadata.")
    external_memory_runner.add_argument("--config", type=Path, help="Optional JSON config passed to the plugin.")
    external_memory_runner.add_argument("--allow-external-runner", action="store_true", help="Actually import and invoke the external plugin.")
    external_memory_runner.add_argument("--allow-partial", action="store_true", help="Allow plugin output that does not cover every input probe.")
    validate_external_memory_output = sub.add_parser("validate-external-memory-predictions")
    validate_external_memory_output.add_argument("input_dir", type=Path, help="Directory produced by export-project-submission-inputs.")
    validate_external_memory_output.add_argument("predictions", type=Path, help="ProjectPrediction JSONL emitted by an external memory runner.")
    validate_external_memory_output.add_argument("--output", type=Path, help="Optional validation report JSON path.")
    validate_external_memory_output.add_argument("--allow-partial", action="store_true", help="Allow outputs that do not cover every input probe.")
    baseline_config = sub.add_parser("validate-baseline-config")
    baseline_config.add_argument("path", type=Path, help="Baseline YAML config file or directory.")
    baseline_config.add_argument("--output", type=Path, help="Optional JSON report path.")
    baseline_config.add_argument("--strict-paths", action="store_true", help="Require referenced project/data paths to exist.")
    run_baseline = sub.add_parser("run-baseline-config")
    run_baseline.add_argument("config", type=Path, help="Baseline YAML config to run or dry-run.")
    run_baseline.add_argument("--output", type=Path, help="Optional runner report JSON path.")
    run_baseline.add_argument("--dry-run", action="store_true", help="Validate and report planned execution without running.")
    run_baseline.add_argument("--allow-llm-api", action="store_true", help="Allow configs that require LLM/API credentials.")
    run_baseline_dir = sub.add_parser("run-baseline-config-dir")
    run_baseline_dir.add_argument("config_dir", type=Path, help="Directory of baseline YAML configs.")
    run_baseline_dir.add_argument("--output-dir", type=Path, default=GENERATED / "evaluation_harness" / "baseline_batch", help="Output directory for per-config runner reports.")
    run_baseline_dir.add_argument("--no-dry-run-external", action="store_true", help="Do not dry-run LLM/API configs automatically.")
    run_baseline_dir.add_argument("--allow-llm-api", action="store_true", help="Allow configs that require LLM/API credentials.")
    discover_data = sub.add_parser("discover-public-data")
    discover_data.add_argument("--root", action="append", dest="roots", type=Path, help="Root directory to scan. Repeat for multiple roots. Defaults to /home/jmzhang/Workspace/data, /data1/public, and /data1/public/hf.")
    discover_data.add_argument("--output", type=Path, default=GENERATED / "public_data_discovery_report.json", help="Output JSON discovery report.")
    discover_data.add_argument("--max-depth", type=int, default=5, help="Maximum directory depth below each root.")
    discover_data.add_argument("--max-files", type=int, default=1000, help="Maximum candidate files to inspect.")
    discover_data.add_argument("--sample-records", type=int, default=3, help="Number of JSON/JSONL records to sample per file.")
    source_audit = sub.add_parser("audit-workflow-data-sources")
    source_audit.add_argument("--discovery-report", type=Path, default=GENERATED / "public_data_discovery_report.json", help="Report produced by discover-public-data.")
    source_audit.add_argument("--gharchive-stage-plan", type=Path, help="Optional report produced by gharchive-stage-plan.")
    source_audit.add_argument("--output", type=Path, default=GENERATED / "workflow_data_source_audit.json", help="Output source audit report.")
    source_audit.add_argument("--require-paper-ready", action="store_true", help="Fail unless sources and GHArchive stage plan are paper-ready.")
    sub.add_parser("release")
    sub.add_parser("stress")
    grounded = sub.add_parser("grounded-pilot")
    grounded.add_argument("--output-dir", type=Path, default=GENERATED / "projects", help="Project-centric generated output directory.")
    github_fixture = sub.add_parser("github-fixture-pilot")
    github_fixture.add_argument("--output-dir", type=Path, default=GENERATED / "projects", help="Project-centric generated output directory.")
    gharchive = sub.add_parser("gharchive-pilot")
    gharchive.add_argument("--input", type=Path, default=DEFAULT_GHARCHIVE_FIXTURE_PATH, help="Local GHArchive JSON/JSONL/GZ event slice.")
    gharchive.add_argument("--repo", default=DEFAULT_GHARCHIVE_REPO, help="Optional repository full name filter, e.g. owner/repo.")
    gharchive.add_argument("--project-id", default="project_gharchive_001", help="Project id for generated output.")
    gharchive.add_argument("--max-records", type=int, help="Optional maximum accepted GHArchive records.")
    gharchive.add_argument("--output-dir", type=Path, default=GENERATED / "projects", help="Project-centric generated output directory.")
    gharchive_batch = sub.add_parser("gharchive-batch-pilot")
    gharchive_batch.add_argument("--input", type=Path, default=DEFAULT_GHARCHIVE_FIXTURE_PATH, help="Local GHArchive JSON/JSONL/GZ event slice.")
    gharchive_batch.add_argument("--repo", action="append", dest="repos", help="Repository full name to include. Repeat for multiple repos. Defaults to discovery.")
    gharchive_batch.add_argument("--project-prefix", default="project_gharchive", help="Project id prefix for generated outputs.")
    gharchive_batch.add_argument("--max-records-per-repo", type=int, help="Optional maximum accepted records per repo.")
    gharchive_batch.add_argument("--output-dir", type=Path, default=GENERATED / "projects", help="Project-centric generated output directory.")
    gharchive_build_slice = sub.add_parser("gharchive-build-slice")
    gharchive_build_slice.add_argument("input", type=Path, help="Local GHArchive file or directory containing JSON/JSONL/GZ event rows.")
    gharchive_build_slice.add_argument("--output", type=Path, required=True, help="Output JSONL slice path.")
    gharchive_build_slice.add_argument("--manifest", type=Path, help="Optional manifest JSON path. Defaults to <output>.manifest.json.")
    gharchive_build_slice.add_argument("--repo", action="append", dest="repos", help="Repository full name to include. Repeat for multiple repos.")
    gharchive_build_slice.add_argument("--max-records", type=int, help="Optional maximum selected records across the slice.")
    gharchive_build_slice.add_argument("--max-records-per-repo", type=int, help="Optional maximum selected records per repository.")
    gharchive_build_slice.add_argument("--max-records-per-source-file", type=int, help="Optional maximum selected records per source file, useful for balanced hourly GHArchive samples.")
    gharchive_build_slice.add_argument("--require-eligible-repo", action="store_true", help="Fail if the output slice has no repo passing the policy quality gate.")
    gharchive_quality = sub.add_parser("gharchive-quality-report")
    gharchive_quality.add_argument("--input", type=Path, default=DEFAULT_GHARCHIVE_FIXTURE_PATH, help="Local GHArchive JSON/JSONL/GZ event slice.")
    gharchive_quality.add_argument("--output", type=Path, help="Optional JSON report path.")
    gharchive_rank = sub.add_parser("gharchive-rank-repos")
    gharchive_rank.add_argument("--input", type=Path, default=DEFAULT_GHARCHIVE_FIXTURE_PATH, help="Local GHArchive JSON/JSONL/GZ event slice or raw hourly directory.")
    gharchive_rank.add_argument("--output", type=Path, help="Optional JSON report path.")
    gharchive_rank.add_argument("--limit", type=int, default=100, help="Maximum ranked repos to include.")
    gharchive_rank.add_argument("--min-events", type=int, default=1, help="Minimum accepted events per repo before ranking.")
    gharchive_select = sub.add_parser("gharchive-select-annotation-repos")
    gharchive_select.add_argument("--input", type=Path, default=DEFAULT_GHARCHIVE_FIXTURE_PATH, help="Local GHArchive JSON/JSONL/GZ event slice.")
    gharchive_select.add_argument("--output", type=Path, help="Optional JSON selection report path.")
    gharchive_select.add_argument("--target-repos", type=int, default=30, help="Total eligible repos to select.")
    gharchive_select.add_argument("--min-per-split", type=int, default=3, help="Minimum repos to force into each project split when available.")
    gharchive_select.add_argument("--max-candidates-per-repo", type=int, help="Optional cap used for candidate-count scoring.")
    gharchive_windows = sub.add_parser("gharchive-window-report")
    gharchive_windows.add_argument("--input", type=Path, default=DEFAULT_GHARCHIVE_FIXTURE_PATH, help="Local GHArchive JSON/JSONL/GZ event slice.")
    gharchive_windows.add_argument("--window-days", type=int, default=7, help="Repository-local time window size in days.")
    gharchive_windows.add_argument("--repo", help="Optional repository full name filter, e.g. owner/repo.")
    gharchive_windows.add_argument("--output", type=Path, help="Optional JSON report path.")
    gharchive_candidates = sub.add_parser("gharchive-mine-candidates")
    gharchive_candidates.add_argument("--input", type=Path, default=DEFAULT_GHARCHIVE_FIXTURE_PATH, help="Local GHArchive JSON/JSONL/GZ event slice.")
    gharchive_candidates.add_argument("--repo", help="Optional repository full name filter, e.g. owner/repo.")
    gharchive_candidates.add_argument("--output", type=Path, help="Optional JSON report path.")
    gharchive_stage_plan = sub.add_parser("gharchive-stage-plan")
    gharchive_stage_plan.add_argument("--input", type=Path, default=DEFAULT_GHARCHIVE_FIXTURE_PATH, help="Local GHArchive JSON/JSONL/GZ event slice.")
    gharchive_stage_plan.add_argument("--profile", choices=["fixture", "pilot", "paper"], default="paper", help="Scale target to preflight.")
    gharchive_stage_plan.add_argument("--window-days", type=int, default=7, help="Repository-local time window size in days.")
    gharchive_stage_plan.add_argument("--output", type=Path, help="Optional JSON stage plan path.")
    gharchive_stage_plan.add_argument("--allow-fail", action="store_true", help="Write/report the stage plan without exiting nonzero when thresholds are not met.")
    gharchive_stage_plan.add_argument("--require-ready-for-annotation", action="store_true", help="Exit nonzero unless the stage-plan decision allows annotation budget.")
    gharchive_annotation_pack = sub.add_parser("gharchive-annotation-pack")
    gharchive_annotation_pack.add_argument("--input", type=Path, default=DEFAULT_GHARCHIVE_FIXTURE_PATH, help="Local GHArchive JSON/JSONL/GZ event slice.")
    gharchive_annotation_pack.add_argument("--repo", default=DEFAULT_GHARCHIVE_REPO, help="Optional repository full name filter, e.g. owner/repo.")
    gharchive_annotation_pack.add_argument("--output-dir", type=Path, default=GENERATED / "annotation_packs" / "gharchive_policy", help="Output directory for annotation pack JSON/JSONL.")
    gharchive_annotation_pack.add_argument("--pack-id", default="gharchive_policy_annotation_pack_001", help="Stable annotation pack id.")
    gharchive_annotation_pack_batch = sub.add_parser("gharchive-annotation-pack-batch")
    gharchive_annotation_pack_batch.add_argument("--input", type=Path, default=DEFAULT_GHARCHIVE_FIXTURE_PATH, help="Local GHArchive JSON/JSONL/GZ event slice.")
    gharchive_annotation_pack_batch.add_argument("--repo", action="append", dest="repos", help="Repository full name to include. Repeat for multiple repos. Defaults to eligible repo discovery.")
    gharchive_annotation_pack_batch.add_argument("--output-dir", type=Path, default=GENERATED / "annotation_packs" / "gharchive_batch", help="Output directory for per-repo annotation packs.")
    gharchive_annotation_pack_batch.add_argument("--pack-prefix", default="gharchive_policy_pack", help="Stable pack id prefix.")
    export_annotation_release = sub.add_parser("export-annotation-pack-release")
    export_annotation_release.add_argument("batch_dir", type=Path, help="Directory produced by gharchive-annotation-pack-batch.")
    export_annotation_release.add_argument("--output-dir", type=Path, default=GENERATED / "release_packaging" / "gharchive_annotation_pack", help="Output release directory.")
    export_annotation_release.add_argument("--dataset-name", default="gharchive_longuserpolicy_annotation_pack", help="Dataset/release name.")
    export_annotation_release.add_argument("--version", default="0.1.0", help="Release version.")
    gharchive_scale_summary = sub.add_parser("gharchive-scale-summary")
    gharchive_scale_summary.add_argument("batch_dir", type=Path, help="Directory produced by gharchive-annotation-pack-batch.")
    gharchive_scale_summary.add_argument("--release-dir", type=Path, help="Optional release directory produced by export-annotation-pack-release.")
    gharchive_scale_summary.add_argument("--output", type=Path, help="Optional JSON summary path.")
    validate_rewrites = sub.add_parser("validate-policy-rewrites")
    validate_rewrites.add_argument("annotation_pack", type=Path, help="annotation_pack.json generated by gharchive-annotation-pack.")
    validate_rewrites.add_argument("proposals", type=Path, help="JSONL rewrite/probe proposals to validate.")
    validate_rewrites.add_argument("--output", type=Path, help="Optional validation report path.")
    validate_rewrites.add_argument("--allow-partial", action="store_true", help="Allow validating a partial proposal batch.")
    validate_rewrites_batch = sub.add_parser("validate-policy-rewrites-batch")
    validate_rewrites_batch.add_argument("batch_dir", type=Path, help="Directory produced by gharchive-annotation-pack-batch.")
    validate_rewrites_batch.add_argument("proposals", type=Path, help="Unified JSONL proposals file or directory of per-pack proposal JSONL files.")
    validate_rewrites_batch.add_argument("--output-dir", type=Path, required=True, help="Output directory for per-pack and batch validation reports.")
    validate_rewrites_batch.add_argument("--allow-partial", action="store_true", help="Allow validating partial proposal batches.")
    export_rewrite_audit = sub.add_parser("export-policy-rewrite-human-audit")
    export_rewrite_audit.add_argument("batch_validation_report", type=Path, help="batch_rewrite_validation_report.json produced by validate-policy-rewrites-batch.")
    export_rewrite_audit.add_argument("--output-dir", type=Path, required=True, help="Output directory for human audit items and decision template.")
    export_rewrite_audit.add_argument("--sample-size", type=int, default=30, help="Number of validated proposals to sample.")
    export_rewrite_audit.add_argument("--min-per-candidate-type", type=int, default=1, help="Minimum sampled proposals per candidate type when available.")
    export_rewrite_audit.add_argument("--seed", type=int, default=0, help="Deterministic sample seed.")
    validate_rewrite_audit = sub.add_parser("validate-policy-rewrite-human-audit")
    validate_rewrite_audit.add_argument("audit_pack_dir", type=Path, help="Directory produced by export-policy-rewrite-human-audit.")
    validate_rewrite_audit.add_argument("decisions", type=Path, help="Completed audit decisions JSONL.")
    validate_rewrite_audit.add_argument("--output", type=Path, help="Optional audit validation report JSON path.")
    validate_rewrite_audit.add_argument("--min-accept-rate", type=float, default=0.95, help="Minimum accepted decision rate for the audited sample.")
    validate_rewrite_audit.add_argument("--allow-partial", action="store_true", help="Allow decisions that do not cover every sampled item.")
    validate_rewrite_audit.add_argument("--allow-needs-revision", action="store_true", help="Treat needs_revision as non-blocking.")
    rewrite_prompts = sub.add_parser("export-policy-rewrite-prompts")
    rewrite_prompts.add_argument("annotation_pack", type=Path, help="annotation_pack.json generated by gharchive-annotation-pack.")
    rewrite_prompts.add_argument("--output", type=Path, required=True, help="Output JSONL prompt records.")
    rewrite_prompts.add_argument("--prompt-version", default="v1", help="Prompt template version tag.")
    rewrite_prompts_batch = sub.add_parser("export-policy-rewrite-prompts-batch")
    rewrite_prompts_batch.add_argument("batch_dir", type=Path, help="Directory produced by gharchive-annotation-pack-batch.")
    rewrite_prompts_batch.add_argument("--output-dir", type=Path, required=True, help="Output directory for per-pack prompt JSONL files and batch report.")
    rewrite_prompts_batch.add_argument("--prompt-version", default="v1", help="Prompt template version tag.")
    rewrite_jobs = sub.add_parser("package-policy-rewrite-jobs")
    rewrite_jobs.add_argument("prompt_export_dir", type=Path, help="Directory produced by export-policy-rewrite-prompts-batch.")
    rewrite_jobs.add_argument("--output-dir", type=Path, default=GENERATED / "annotation_packs" / "rewrite_jobs", help="Output directory for annotation job shards.")
    rewrite_jobs.add_argument("--max-prompts-per-job", type=int, default=100, help="Maximum prompt records per job shard.")
    rewrite_jobs.add_argument("--max-estimated-tokens-per-job", type=int, default=120000, help="Approximate max prompt tokens per job shard.")
    rewrite_llm_job = sub.add_parser("run-policy-rewrite-llm-job")
    rewrite_llm_job.add_argument("job_dir", type=Path, help="Single rewrite_job_XXXX directory produced by package-policy-rewrite-jobs.")
    rewrite_llm_job.add_argument("--output-filename", default="proposals.jsonl", help="Output proposal filename inside the job directory.")
    rewrite_llm_job.add_argument("--report", type=Path, help="Optional generation report JSON path.")
    rewrite_llm_job.add_argument("--model", default="gpt-5.5", help="OpenAI-compatible model name.")
    rewrite_llm_job.add_argument("--base-url", help="OpenAI-compatible base URL. Defaults to ULB_OPENAI_BASE_URL/OPENAI_BASE_URL.")
    rewrite_llm_job.add_argument("--reasoning-effort", default="xhigh", help="Reasoning effort field to send, or empty string to omit.")
    rewrite_llm_job.add_argument("--max-prompts", type=int, help="Optional prompt limit for small-batch testing.")
    rewrite_llm_job.add_argument("--start-index", type=int, default=0, help="Prompt offset within the job.")
    rewrite_llm_job.add_argument("--timeout-seconds", type=int, default=180, help="HTTP timeout per prompt.")
    rewrite_llm_job.add_argument("--max-output-tokens", type=int, default=1600, help="Max tokens for each proposal JSON object.")
    rewrite_llm_job.add_argument("--retries", type=int, default=2, help="Retries per prompt.")
    rewrite_llm_job.add_argument("--retry-sleep-seconds", type=float, default=2.0, help="Base retry sleep.")
    rewrite_llm_job.add_argument("--temperature", type=float, help="Optional sampling temperature.")
    rewrite_llm_job.add_argument("--no-json-response-format", action="store_true", help="Do not send response_format={type:json_object}.")
    rewrite_llm_job.add_argument("--no-overwrite", action="store_true", help="Fail if the output proposal file already exists.")
    rewrite_llm_job.add_argument("--merge-existing", action="store_true", help="Merge newly generated rows with an existing proposal file by annotation_id.")
    rewrite_llm_batch = sub.add_parser("run-policy-rewrite-llm-jobs")
    rewrite_llm_batch.add_argument("rewrite_job_dir", type=Path, help="Directory produced by package-policy-rewrite-jobs.")
    rewrite_llm_batch.add_argument("--output-filename", default="proposals.jsonl", help="Output proposal filename inside each job directory.")
    rewrite_llm_batch.add_argument("--report", type=Path, help="Optional generation report JSON path.")
    rewrite_llm_batch.add_argument("--model", default="gpt-5.5", help="OpenAI-compatible model name.")
    rewrite_llm_batch.add_argument("--base-url", help="OpenAI-compatible base URL. Defaults to ULB_OPENAI_BASE_URL/OPENAI_BASE_URL.")
    rewrite_llm_batch.add_argument("--reasoning-effort", default="xhigh", help="Reasoning effort field to send, or empty string to omit.")
    rewrite_llm_batch.add_argument("--max-jobs", type=int, help="Optional job limit for small-batch testing.")
    rewrite_llm_batch.add_argument("--max-prompts-per-job", type=int, help="Optional prompt limit per job for small-batch testing.")
    rewrite_llm_batch.add_argument("--timeout-seconds", type=int, default=180, help="HTTP timeout per prompt.")
    rewrite_llm_batch.add_argument("--max-output-tokens", type=int, default=1600, help="Max tokens for each proposal JSON object.")
    rewrite_llm_batch.add_argument("--retries", type=int, default=2, help="Retries per prompt.")
    rewrite_llm_batch.add_argument("--retry-sleep-seconds", type=float, default=2.0, help="Base retry sleep.")
    rewrite_llm_batch.add_argument("--temperature", type=float, help="Optional sampling temperature.")
    rewrite_llm_batch.add_argument("--no-json-response-format", action="store_true", help="Do not send response_format={type:json_object}.")
    rewrite_llm_batch.add_argument("--no-overwrite", action="store_true", help="Fail if output proposal files already exist.")
    rewrite_llm_batch.add_argument("--merge-existing", action="store_true", help="Merge newly generated rows with existing proposal files by annotation_id.")
    collect_rewrite_jobs = sub.add_parser("collect-policy-rewrite-job-outputs")
    collect_rewrite_jobs.add_argument("rewrite_job_dir", type=Path, help="Directory produced by package-policy-rewrite-jobs.")
    collect_rewrite_jobs.add_argument("--output", type=Path, default=GENERATED / "annotation_packs" / "rewrite_jobs" / "collected_rewrite_proposals.jsonl", help="Unified JSONL proposals output for validate-policy-rewrites-batch.")
    collect_rewrite_jobs.add_argument("--report", type=Path, help="Optional collection report JSON path.")
    collect_rewrite_jobs.add_argument("--proposal-filename", default="proposals.jsonl", help="Completed proposal filename expected inside each job directory.")
    collect_rewrite_jobs.add_argument("--allow-incomplete", action="store_true", help="Write the collection report without exiting nonzero when jobs are missing or unfilled.")
    rewrite_project = sub.add_parser("build-project-from-rewrites")
    rewrite_project.add_argument("annotation_pack", type=Path, help="annotation_pack.json generated by gharchive-annotation-pack.")
    rewrite_project.add_argument("proposals", type=Path, help="Validated JSONL rewrite/probe proposals.")
    rewrite_project.add_argument("--output-dir", type=Path, default=GENERATED / "projects", help="Project-centric generated output directory.")
    rewrite_project.add_argument("--project-id", default="project_gharchive_rewrite_001", help="Project id for generated output.")
    rewrite_project.add_argument("--validation-output", type=Path, help="Optional rewrite validation report path.")
    rewrite_project_batch = sub.add_parser("build-projects-from-rewrite-batch")
    rewrite_project_batch.add_argument("batch_validation_report", type=Path, help="batch_rewrite_validation_report.json from validate-policy-rewrites-batch.")
    rewrite_project_batch.add_argument("--output-dir", type=Path, default=GENERATED / "projects", help="Project-centric generated output directory.")
    rewrite_project_batch.add_argument("--project-prefix", default="project_gharchive_rewrite", help="Project id prefix for generated projects.")
    export_project_release = sub.add_parser("export-project-benchmark-release")
    export_project_release.add_argument("project_dirs", nargs="+", type=Path, help="Verifier-checked project directories to include.")
    export_project_release.add_argument("--output-dir", type=Path, default=GENERATED / "release_packaging" / "project_benchmark", help="Output project benchmark release directory.")
    export_project_release.add_argument("--dataset-name", default="longuserpolicy_project_benchmark", help="Dataset/release name.")
    export_project_release.add_argument("--version", default="0.1.0", help="Release version.")
    export_project_release.add_argument("--copy-projects", action="store_true", help="Copy project files into the release directory instead of referencing existing project dirs.")
    export_project_release.add_argument("--allow-unverified", action="store_true", help="Allow projects whose verifier report does not pass.")
    export_project_release.add_argument("--llm-generated", action="store_true", help="Mark the release as LLM-assisted after rewrite/project verifiers have passed.")
    export_project_release.add_argument("--construction", default="deterministic_or_human_verified", help="Short construction label stored in the release constraints.")
    verify_project_release = sub.add_parser("verify-project-benchmark-release")
    verify_project_release.add_argument("release_dir", type=Path, help="Directory produced by export-project-benchmark-release.")
    verify_project_release.add_argument("--output", type=Path, help="Optional project release integrity report JSON path.")
    export_submission_inputs = sub.add_parser("export-project-submission-inputs")
    export_submission_inputs.add_argument("release_dir", type=Path, help="Project benchmark release directory.")
    export_submission_inputs.add_argument("--output-dir", type=Path, default=GENERATED / "evaluation_harness" / "project_submission_inputs", help="Output no-gold submission input directory.")
    export_submission_inputs.add_argument("--split", action="append", dest="splits", choices=["train", "dev", "test"], help="Release split to include. Repeat for multiple splits. Defaults to all splits.")
    export_submission_inputs.add_argument("--no-artifacts", action="store_true", help="Omit artifact rows from the input pack.")
    export_submission_inputs.add_argument("--no-events", action="store_true", help="Omit event rows from the input pack.")
    export_submission_inputs.add_argument("--harden-probe-queries", action="store_true", help="Replace public probe queries with lower-leakage task templates while preserving probe ids for scoring.")
    verify_submission_inputs = sub.add_parser("verify-project-submission-inputs")
    verify_submission_inputs.add_argument("input_dir", type=Path, help="Directory produced by export-project-submission-inputs.")
    verify_submission_inputs.add_argument("--output", type=Path, help="Optional submission input verification report JSON path.")
    validate_prediction_submission = sub.add_parser("validate-project-prediction-submission")
    validate_prediction_submission.add_argument("release_dir", type=Path, help="Project benchmark release directory.")
    validate_prediction_submission.add_argument("predictions", type=Path, help="ProjectPrediction JSONL submission.")
    validate_prediction_submission.add_argument("--output", type=Path, help="Optional validation report JSON path.")
    validate_prediction_submission.add_argument("--allow-partial", action="store_true", help="Allow submissions that do not cover every release probe.")
    probe_leakage = sub.add_parser("audit-project-release-probe-leakage")
    probe_leakage.add_argument("release_dir", type=Path, help="Project benchmark release directory.")
    probe_leakage.add_argument("--output", type=Path, help="Optional probe leakage audit JSON path.")
    probe_leakage.add_argument("--high-overlap-threshold", type=float, default=0.8, help="Overlap threshold used to count high-risk probe wording.")
    submission_probe_leakage = sub.add_parser("audit-submission-input-probe-leakage")
    submission_probe_leakage.add_argument("release_dir", type=Path, help="Project benchmark release directory with gold probes/memory graph.")
    submission_probe_leakage.add_argument("input_dir", type=Path, help="No-gold submission input directory to audit.")
    submission_probe_leakage.add_argument("--output", type=Path, help="Optional probe leakage audit JSON path.")
    submission_probe_leakage.add_argument("--high-overlap-threshold", type=float, default=0.8, help="Overlap threshold used to count high-risk probe wording.")
    release_integrity = sub.add_parser("verify-release-integrity")
    release_integrity.add_argument("release_dir", type=Path, help="Directory produced by export-annotation-pack-release.")
    release_integrity.add_argument("--prompt-export-dir", type=Path, help="Optional directory produced by export-policy-rewrite-prompts-batch.")
    release_integrity.add_argument("--output", type=Path, help="Optional integrity report JSON path.")
    paper_scale = sub.add_parser("assess-paper-scale")
    paper_scale.add_argument("release_dir", type=Path, help="Directory produced by export-annotation-pack-release.")
    paper_scale.add_argument("--profile", choices=["fixture", "pilot", "paper"], default="paper", help="Scale threshold profile.")
    paper_scale.add_argument("--scale-summary", type=Path, help="Path produced by gharchive-scale-summary.")
    paper_scale.add_argument("--window-report", type=Path, help="Path produced by gharchive-window-report.")
    paper_scale.add_argument("--release-integrity-report", type=Path, help="Path produced by verify-release-integrity.")
    paper_scale.add_argument("--prompt-export-dir", type=Path, help="Compute release integrity from prompt exports if no integrity report is supplied.")
    paper_scale.add_argument("--output", type=Path, help="Optional paper-scale assessment JSON path.")
    paper_scale.add_argument("--allow-fail", action="store_true", help="Write/report the assessment without exiting nonzero when profile thresholds are not met.")
    paper_tables = sub.add_parser("export-paper-tables")
    paper_tables.add_argument("--release-baseline-report", type=Path, default=GENERATED / "evaluation_harness" / "project_release_baselines.json", help="Release deterministic baseline report.")
    paper_tables.add_argument("--prediction-report", action="append", dest="prediction_reports", type=Path, help="Release prediction scoring report. Repeat for multiple systems.")
    paper_tables.add_argument("--prediction-batch-report", action="append", dest="prediction_batch_reports", type=Path, help="Batch report from score-project-release-prediction-dir. Repeat for multiple batches.")
    paper_tables.add_argument("--bootstrap-samples", type=int, default=1000, help="Project-level bootstrap samples for confidence intervals.")
    paper_tables.add_argument("--bootstrap-seed", type=int, default=0, help="Seed for deterministic bootstrap confidence intervals.")
    paper_tables.add_argument("--output-dir", type=Path, default=GENERATED / "evaluation_harness" / "paper_tables", help="Output directory for JSON/CSV/Markdown tables.")
    verify = sub.add_parser("verify-project")
    verify.add_argument("project_dir", type=Path, help="Project directory containing artifacts/events/memory_graph/probes.")
    verify.add_argument("--output", type=Path, help="Optional verifier report output path.")
    audit = sub.add_parser("audit")
    audit.add_argument("--generated-dir", type=Path, default=GENERATED, help="Generated artifact directory to audit.")
    audit.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    audit.add_argument("--output", type=Path, help="Optional path for the JSON audit report.")
    readiness = sub.add_parser("readiness-report")
    readiness.add_argument("--generated-dir", type=Path, default=GENERATED, help="Generated artifact directory to inspect.")
    readiness.add_argument("--output", type=Path, default=GENERATED / "readiness_report.json", help="Output JSON readiness report.")
    readiness.add_argument("--baseline-batch-dir", type=Path, help="Optional baseline batch report directory.")
    readiness.add_argument("--annotation-release-dir", type=Path, help="Optional annotation release directory.")
    readiness.add_argument("--prompt-export-dir", type=Path, help="Optional prompt export directory.")
    readiness.add_argument("--rewrite-job-dir", type=Path, help="Optional packaged rewrite annotation job directory.")
    readiness.add_argument("--rewrite-project-dir", type=Path, help="Optional rewrite-derived project directory.")
    readiness.add_argument("--staged-slice-manifest", type=Path, help="Optional GHArchive staged slice manifest.")
    readiness.add_argument("--gharchive-stage-plan", type=Path, help="Optional GHArchive raw-slice stage-plan report.")
    readiness.add_argument("--scale-summary", type=Path, help="Optional GHArchive annotation scale summary.")
    readiness.add_argument("--window-report", type=Path, help="Optional GHArchive window report.")
    readiness.add_argument("--public-data-discovery", type=Path, help="Optional public data discovery report.")
    readiness.add_argument("--workflow-source-audit", type=Path, help="Optional workflow data source audit report.")
    readiness.add_argument("--batch-rewrite-validation", type=Path, help="Optional batch rewrite validation report.")
    readiness.add_argument("--batch-rewrite-projects", type=Path, help="Optional batch rewrite project synthesis report.")
    readiness.add_argument("--project-release-dir", type=Path, help="Optional project benchmark release directory.")
    readiness.add_argument("--project-submission-input-dir", type=Path, help="Optional no-gold project submission input directory.")
    readiness.add_argument("--project-release-baseline", type=Path, help="Optional project release baseline report.")
    readiness.add_argument("--project-release-prediction", type=Path, help="Optional project release prediction scoring report.")
    readiness.add_argument("--paper-table-dir", type=Path, help="Optional paper-ready result table directory.")
    readiness.add_argument("--rewrite-human-audit", type=Path, help="Optional human audit validation report for LLM rewrite proposals.")
    readiness.add_argument("--probe-leakage-audit", type=Path, help="Optional probe-query lexical leakage audit report.")
    readiness.add_argument("--paper-scale-profile", choices=["fixture", "pilot", "paper"], default="paper", help="Scale profile to assess inside readiness.")
    readiness.add_argument("--require-paper-scale", action="store_true", help="Fail readiness if the paper-scale profile is not met.")
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
    elif args.command == "evaluate-project":
        output_path = args.output or (args.project_dir / "baseline_report.json")
        report = run_project_baseline_evaluation(args.project_dir, output_path, top_k=args.top_k, baseline_names=args.baselines)
        names = report["summary"]["baseline_names"]
        first = report["baselines"][names[0]]
        last = report["baselines"][names[-1]]
        print(
            "project baselines evaluated: "
            f"project={report['project_id']} probes={report['summary']['probes']} "
            f"baselines={','.join(names)} "
            f"first_must_include={first['must_include_recall']:.3f} last_must_include={last['must_include_recall']:.3f}"
        )
    elif args.command == "evaluate-project-release":
        output_path = args.output or (args.release_dir / "project_release_baseline_report.json")
        report = run_project_release_baseline_evaluation(args.release_dir, output_path, top_k=args.top_k, baseline_names=args.baselines)
        names = report["summary"]["baseline_names"]
        first = report["summary"]["baselines"][names[0]]
        last = report["summary"]["baselines"][names[-1]]
        print(
            "project release baselines evaluated: "
            f"projects={report['summary']['projects']} probes={report['summary']['probes']} "
            f"baselines={','.join(names)} "
            f"first_boundary={first['micro_boundary_action_recall']:.3f} last_boundary={last['micro_boundary_action_recall']:.3f}"
        )
    elif args.command == "score-action-traces":
        output_path = args.output or (args.project_dir / "action_trace_report.json")
        report = score_action_traces(args.project_dir, args.traces, output_path)
        print(
            "action traces scored: "
            f"project={report['project_id']} traces={report['summary']['traces']} "
            f"pass_rate={report['summary']['pass_rate']:.3f} "
            f"boundary_violation_rate={report['summary']['boundary_violation_rate']:.3f}"
        )
    elif args.command == "score-project-predictions":
        output_path = args.output or (args.project_dir / "project_prediction_report.json")
        report = score_project_predictions(args.project_dir, args.predictions, output_path, system_name=args.system_name)
        print(
            "project predictions scored: "
            f"project={report['project_id']} system={report['system_name']} predictions={report['summary']['predictions']} "
            f"pass_rate={report['summary']['pass_rate']:.3f} evidence_recall={report['summary']['evidence_recall']:.3f}"
        )
    elif args.command == "score-project-release-predictions":
        output_path = args.output or (args.release_dir / "project_release_prediction_report.json")
        report = score_project_release_predictions(args.release_dir, args.predictions, output_path, system_name=args.system_name)
        print(
            "project release predictions scored: "
            f"projects={report['summary']['projects']} system={report['system_name']} predictions={report['summary']['predictions']} "
            f"probe_coverage={report['summary']['probe_coverage']:.3f} micro_pass_rate={report['summary']['micro_pass_rate']:.3f}"
        )
    elif args.command == "score-project-release-prediction-dir":
        report = score_project_release_prediction_dir(
            args.release_dir,
            args.predictions_dir,
            args.output_dir,
            system_name_prefix=args.system_name_prefix,
        )
        print(
            "project release prediction directory scored: "
            f"systems={report['summary']['systems']} prediction_files={report['summary']['prediction_files']} output_dir={args.output_dir}"
        )
    elif args.command == "run-submission-input-baseline":
        report = run_submission_input_baseline(
            args.input_dir,
            args.predictions,
            baseline_name=args.baseline,
            top_k=args.top_k,
            report_path=args.report,
        )
        print(
            "submission input baseline predictions written: "
            f"baseline={report['baseline_name']} probes={report['summary']['probes']} "
            f"predictions={report['summary']['predictions']} output={args.predictions}"
        )
    elif args.command == "run-memory-submission-baseline":
        report = run_memory_submission_baseline(
            args.input_dir,
            args.predictions,
            adapter=args.adapter,
            top_k=args.top_k,
            report_path=args.report,
            allow_external=args.allow_external,
            system_name=args.system_name,
        )
        print(
            "memory submission baseline runner: "
            f"adapter={report['adapter']} status={report['status']} executed={report['executed']} "
            f"probes={report['summary']['probes']} predictions={report['summary']['predictions']} output={args.predictions}"
        )
        if report["status"] != "completed":
            raise SystemExit(1)
    elif args.command == "plan-external-memory-submission-adapter":
        report = plan_external_memory_submission_adapter(
            args.input_dir,
            args.predictions,
            adapter=args.adapter,
            report_path=args.report,
            system_name=args.system_name,
        )
        print(
            "external memory submission adapter plan: "
            f"adapter={report['adapter']} status={report['status']} "
            f"input_contract={report['checks']['input_contract_passed']} "
            f"deps_ready={report['checks']['dependencies']['ready_for_external_execution']} "
            f"probes={report['summary']['probes']}"
        )
    elif args.command == "run-external-memory-submission-runner":
        runner_config = read_json(args.config) if args.config else {}
        report = run_external_memory_submission_runner(
            args.input_dir,
            args.predictions,
            runner=args.runner,
            report_path=args.report,
            runner_config=runner_config,
            allow_external_runner=args.allow_external_runner,
            system_name=args.system_name,
            require_complete=not args.allow_partial,
        )
        print(
            "external memory submission runner: "
            f"runner={report['runner']} status={report['status']} executed={report['executed']} "
            f"probes={report['summary']['probes']} predictions={report['summary']['predictions']} output={args.predictions}"
        )
        if report["status"] != "completed":
            raise SystemExit(1)
    elif args.command == "validate-external-memory-predictions":
        report = validate_external_memory_predictions_against_input(
            args.input_dir,
            args.predictions,
            require_complete=not args.allow_partial,
        )
        if args.output is not None:
            write_json(args.output, report)
        print(
            "external memory predictions validated against no-gold input: "
            f"passed={report['passed']} coverage={report['checks']['coverage']['probe_coverage']} "
            f"issues={report['summary']['issues']} warnings={report['summary']['warnings']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "validate-baseline-config":
        if args.path.is_dir():
            report = validate_baseline_config_dir(args.path, args.output, strict_paths=args.strict_paths)
            print(
                "baseline configs validated: "
                f"configs={report['summary']['configs_total']} passed={report['summary']['configs_passed']} "
                f"failed={report['summary']['configs_failed']}"
            )
        else:
            report = validate_baseline_config(args.path, args.output, strict_paths=args.strict_paths)
            print(f"baseline config validated: name={report['baseline_name']} passed={report['passed']} issues={len(report['issues'])}")
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "run-baseline-config":
        report = run_baseline_config(args.config, output_path=args.output, dry_run=args.dry_run, allow_llm_api=args.allow_llm_api)
        print(
            "baseline config runner: "
            f"name={report['baseline_name']} status={report['status']} executed={report['executed']} issues={len(report['issues'])}"
        )
        if report["status"] not in {"completed", "dry_run_ok", "dry_run_requires_llm_api"}:
            raise SystemExit(1)
    elif args.command == "run-baseline-config-dir":
        report = run_baseline_config_dir(
            args.config_dir,
            args.output_dir,
            dry_run_external=not args.no_dry_run_external,
            allow_llm_api=args.allow_llm_api,
        )
        print(
            "baseline config batch runner: "
            f"configs={report['summary']['configs_total']} completed={report['summary']['completed']} "
            f"dry_run={report['summary']['dry_run']} blocked={report['summary']['blocked']} failed={report['summary']['failed']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "discover-public-data":
        roots = args.roots or DEFAULT_PUBLIC_ROOTS
        report = discover_public_data_sources(
            roots,
            output_path=args.output,
            max_depth=args.max_depth,
            max_files=args.max_files,
            sample_records=args.sample_records,
        )
        print(
            "public data discovery: "
            f"candidates={report['summary']['candidates_total']} usable={report['summary']['usable_sources']} "
            f"gharchive={report['summary']['gharchive_event_sources']} email_manifests={report['summary']['email_manifest_sources']} "
            f"output={args.output}"
        )
    elif args.command == "audit-workflow-data-sources":
        report = audit_workflow_data_sources(
            args.discovery_report,
            output_path=args.output,
            gharchive_stage_plan_path=args.gharchive_stage_plan,
            require_paper_ready=args.require_paper_ready,
        )
        print(
            "workflow data sources audited: "
            f"passed={report['passed']} annotation_ready={report['annotation_budget_ready']} "
            f"paper_ready={report['paper_ready']} issues={report['summary']['issues']} warnings={report['summary']['warnings']} "
            f"output={args.output}"
        )
        if not report["passed"]:
            raise SystemExit(1)
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
    elif args.command == "grounded-pilot":
        summary = run_manual_grounded_pilot(args.output_dir)
        report = run_project_verifier(Path(summary["project_dir"]))
        print(f"grounded pilot written: project={summary['project_id']} probes={summary['probes']} verifier_passed={report.passed}")
        if not report.passed:
            raise SystemExit(f"grounded pilot verifier failed: {report.issues}")
    elif args.command == "github-fixture-pilot":
        summary = run_github_fixture_pilot(args.output_dir)
        report = run_project_verifier(Path(summary["project_dir"]))
        print(f"github fixture pilot written: project={summary['project_id']} probes={summary['probes']} verifier_passed={report.passed}")
        if not report.passed:
            raise SystemExit(f"github fixture verifier failed: {report.issues}")
    elif args.command == "gharchive-pilot":
        summary = run_gharchive_pilot(
            args.output_dir,
            input_path=args.input,
            repo_full_name=args.repo,
            project_id=args.project_id,
            max_records=args.max_records,
        )
        report = run_project_verifier(Path(summary["project_dir"]))
        print(f"gharchive pilot written: project={summary['project_id']} events={summary['events']} probes={summary['probes']} verifier_passed={report.passed}")
        if not report.passed:
            raise SystemExit(f"gharchive verifier failed: {report.issues}")
    elif args.command == "gharchive-batch-pilot":
        summary = run_gharchive_batch_pilot(
            args.output_dir,
            input_path=args.input,
            repos=args.repos,
            project_prefix=args.project_prefix,
            max_records_per_repo=args.max_records_per_repo,
        )
        failed = []
        for project in summary["projects"]:
            report = run_project_verifier(Path(project["project_dir"]))
            if not report.passed:
                failed.append({"project_id": project["project_id"], "issues": report.issues})
        print(
            "gharchive batch pilot written: "
            f"projects={summary['project_count']} skipped={len(summary['skipped'])} verifier_failed={len(failed)}"
        )
        if summary["project_count"] == 0:
            raise SystemExit(f"gharchive batch produced no eligible projects; skipped={summary['skipped']}")
        if failed:
            raise SystemExit(f"gharchive batch verifier failed: {failed}")
    elif args.command == "gharchive-build-slice":
        manifest = build_gharchive_slice(
            args.input,
            args.output,
            manifest_path=args.manifest,
            repos=args.repos,
            max_records=args.max_records,
            max_records_per_repo=args.max_records_per_repo,
            max_records_per_source_file=args.max_records_per_source_file,
            require_eligible_repo=args.require_eligible_repo,
        )
        print(
            "gharchive slice built: "
            f"records={manifest['counts']['records_selected']} repos={manifest['counts']['repos_selected']} "
            f"eligible={manifest['counts']['repos_eligible']} output={manifest['output_path']}"
        )
    elif args.command == "gharchive-quality-report":
        report = profile_gharchive_repos(args.input, args.output)
        print(
            "gharchive quality report: "
            f"repos={report['summary']['repos_total']} eligible={report['summary']['repos_eligible']} events={report['summary']['events_total']}"
        )
    elif args.command == "gharchive-rank-repos":
        report = rank_gharchive_repos(args.input, output_path=args.output, limit=args.limit, min_events=args.min_events)
        top = report["repos"][0]["repo"] if report["repos"] else "none"
        print(
            "gharchive repo ranking: "
            f"repos={report['summary']['repos_total']} ranked={report['summary']['repos_ranked']} "
            f"eligible={report['summary']['repos_eligible']} top={top}"
        )
    elif args.command == "gharchive-select-annotation-repos":
        report = select_gharchive_annotation_repos(
            args.input,
            output_path=args.output,
            target_repos=args.target_repos,
            min_per_split=args.min_per_split,
            max_candidates_per_repo=args.max_candidates_per_repo,
        )
        print(
            "gharchive annotation repos selected: "
            f"selected={report['summary']['selected_repos']} splits={report['summary']['split_counts']} "
            f"candidate_types={report['summary']['candidate_types']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "gharchive-window-report":
        report = profile_gharchive_time_windows(args.input, window_days=args.window_days, repo=args.repo, output_path=args.output)
        print(
            "gharchive window report: "
            f"repos={report['summary']['repos_total']} windows={report['summary']['windows_total']} "
            f"eligible_windows={report['summary']['eligible_windows']} window_days={report['window_days']}"
        )
    elif args.command == "gharchive-mine-candidates":
        report = mine_gharchive_policy_candidates(args.input, repo=args.repo, output_path=args.output)
        print(
            "gharchive candidate mining: "
            f"repos={report['summary']['repos_total']} candidates={report['summary']['candidates_total']} "
            f"types={report['summary']['candidate_types']}"
        )
    elif args.command == "gharchive-stage-plan":
        report = plan_gharchive_stage(args.input, profile=args.profile, window_days=args.window_days, output_path=args.output)
        print(
            "gharchive stage plan: "
            f"profile={report['profile']} passed={report['summary']['passed']} "
            f"eligible_repos={report['summary']['eligible_repos']} candidates={report['candidate_summary']['candidates_total']} "
            f"eligible_windows={report['summary']['eligible_windows']} failed={report['summary']['failed']} "
            f"mode={report['decision']['recommended_mode']} ready_for_annotation={report['decision']['ready_for_annotation_budget']}"
        )
        if not report["summary"]["passed"] and not args.allow_fail:
            raise SystemExit(1)
        if args.require_ready_for_annotation and not report["decision"]["ready_for_annotation_budget"]:
            raise SystemExit(1)
    elif args.command == "gharchive-annotation-pack":
        report = build_gharchive_annotation_pack(args.input, repo=args.repo, output_dir=args.output_dir, pack_id=args.pack_id)
        print(
            "gharchive annotation pack written: "
            f"pack={report['pack_id']} tasks={report['summary']['tasks_total']} issues={report['summary']['issues_total']}"
        )
        if report["summary"]["issues_total"]:
            raise SystemExit(1)
    elif args.command == "gharchive-annotation-pack-batch":
        report = build_gharchive_annotation_pack_batch(args.input, output_dir=args.output_dir, repos=args.repos, pack_prefix=args.pack_prefix)
        print(
            "gharchive annotation pack batch written: "
            f"packs={report['summary']['packs_total']} skipped={report['summary']['skipped_total']} "
            f"tasks={report['summary']['tasks_total']}"
        )
        if report["summary"]["packs_total"] == 0:
            raise SystemExit(f"gharchive annotation pack batch produced no packs; skipped={report['skipped']}")
    elif args.command == "export-annotation-pack-release":
        manifest = export_annotation_pack_release(args.batch_dir, args.output_dir, dataset_name=args.dataset_name, version=args.version)
        print(
            "annotation pack release exported: "
            f"dataset={manifest['dataset_name']} packs={manifest['counts']['packs']} tasks={manifest['counts']['tasks']} "
            f"splits={manifest['splits']}"
        )
        if manifest["counts"]["packs"] == 0 or manifest["counts"]["tasks"] == 0:
            raise SystemExit("annotation pack release is empty")
    elif args.command == "gharchive-scale-summary":
        summary = summarize_gharchive_annotation_scale(args.batch_dir, release_dir=args.release_dir, output_path=args.output)
        print(
            "gharchive scale summary: "
            f"packs={summary['repos']['eligible_packs']} skipped={summary['repos']['skipped']} "
            f"tasks={summary['tasks']['total']} candidate_types={summary['candidate_types']}"
        )
    elif args.command == "validate-policy-rewrites":
        report = validate_policy_rewrite_proposals(args.annotation_pack, args.proposals, args.output, require_complete=not args.allow_partial)
        print(
            "policy rewrites validated: "
            f"proposals={report['summary']['proposals_total']} passed={report['summary']['proposals_passed']} "
            f"failed={report['summary']['proposals_failed']} missing={len(report['summary']['missing_annotation_outputs'])}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "validate-policy-rewrites-batch":
        report = validate_policy_rewrite_proposals_batch(
            args.batch_dir,
            args.proposals,
            args.output_dir,
            require_complete=not args.allow_partial,
        )
        print(
            "policy rewrite batch validated: "
            f"packs={report['summary']['packs_total']} passed={report['summary']['packs_passed']} "
            f"failed={report['summary']['packs_failed']} proposals={report['summary']['proposals_total']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "export-policy-rewrite-human-audit":
        manifest = export_policy_rewrite_human_audit_pack(
            args.batch_validation_report,
            args.output_dir,
            sample_size=args.sample_size,
            min_per_candidate_type=args.min_per_candidate_type,
            seed=args.seed,
        )
        print(
            "policy rewrite human audit pack exported: "
            f"items={manifest['sample']['sample_size']} population={manifest['sample']['population_size']} "
            f"output_dir={manifest['output_dir']}"
        )
    elif args.command == "validate-policy-rewrite-human-audit":
        report = validate_policy_rewrite_human_audit(
            args.audit_pack_dir,
            args.decisions,
            output_path=args.output,
            min_accept_rate=args.min_accept_rate,
            require_complete=not args.allow_partial,
            allow_needs_revision=args.allow_needs_revision,
        )
        print(
            "policy rewrite human audit validated: "
            f"passed={report['passed']} reviewed={report['summary']['reviewed']} "
            f"accepted={report['summary']['accepted']} accept_rate={report['summary']['accept_rate']} "
            f"issues={len(report['issues'])}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "export-policy-rewrite-prompts":
        summary = export_policy_rewrite_prompts(args.annotation_pack, args.output, prompt_version=args.prompt_version)
        print(
            "policy rewrite prompts exported: "
            f"pack={summary['pack_id']} prompts={summary['prompts_total']} output={summary['output_path']}"
        )
    elif args.command == "export-policy-rewrite-prompts-batch":
        report = export_policy_rewrite_prompts_batch(args.batch_dir, args.output_dir, prompt_version=args.prompt_version)
        print(
            "policy rewrite prompt batch exported: "
            f"packs={report['summary']['packs_total']} prompts={report['summary']['prompts_total']} "
            f"output_dir={report['output_dir']}"
        )
    elif args.command == "package-policy-rewrite-jobs":
        manifest = package_policy_rewrite_jobs(
            args.prompt_export_dir,
            args.output_dir,
            max_prompts_per_job=args.max_prompts_per_job,
            max_estimated_tokens_per_job=args.max_estimated_tokens_per_job,
        )
        print(
            "policy rewrite jobs packaged: "
            f"jobs={manifest['summary']['jobs_total']} prompts={manifest['summary']['prompts_total']} "
            f"estimated_tokens={manifest['summary']['estimated_tokens_total']} output_dir={manifest['output_dir']}"
        )
    elif args.command == "run-policy-rewrite-llm-job":
        report = run_policy_rewrite_llm_job(
            args.job_dir,
            output_filename=args.output_filename,
            report_path=args.report,
            model=args.model,
            base_url=args.base_url,
            reasoning_effort=args.reasoning_effort or None,
            max_prompts=args.max_prompts,
            start_index=args.start_index,
            timeout_seconds=args.timeout_seconds,
            max_output_tokens=args.max_output_tokens,
            retries=args.retries,
            retry_sleep_seconds=args.retry_sleep_seconds,
            use_json_response_format=not args.no_json_response_format,
            temperature=args.temperature,
            overwrite=not args.no_overwrite,
            merge_existing=args.merge_existing,
        )
        print(
            "policy rewrite LLM job generated: "
            f"job={report['job_id']} proposals={report['summary']['proposals_written']} "
            f"failed={report['summary']['failed']} output={report['output_path']}"
        )
    elif args.command == "run-policy-rewrite-llm-jobs":
        report = run_policy_rewrite_llm_jobs(
            args.rewrite_job_dir,
            output_filename=args.output_filename,
            report_path=args.report,
            model=args.model,
            base_url=args.base_url,
            reasoning_effort=args.reasoning_effort or None,
            max_jobs=args.max_jobs,
            max_prompts_per_job=args.max_prompts_per_job,
            timeout_seconds=args.timeout_seconds,
            max_output_tokens=args.max_output_tokens,
            retries=args.retries,
            retry_sleep_seconds=args.retry_sleep_seconds,
            use_json_response_format=not args.no_json_response_format,
            temperature=args.temperature,
            overwrite=not args.no_overwrite,
            merge_existing=args.merge_existing,
        )
        print(
            "policy rewrite LLM batch generated: "
            f"jobs={report['summary']['jobs_completed']} proposals={report['summary']['proposals_written']} "
            f"failed_jobs={report['summary']['jobs_failed']} output_filename={report['output_filename']}"
        )
    elif args.command == "collect-policy-rewrite-job-outputs":
        report = collect_policy_rewrite_job_outputs(
            args.rewrite_job_dir,
            args.output,
            report_path=args.report,
            proposal_filename=args.proposal_filename,
        )
        print(
            "policy rewrite job outputs collected: "
            f"jobs={report['summary']['jobs_total']} passed={report['summary']['jobs_passed']} "
            f"failed={report['summary']['jobs_failed']} proposals={report['summary']['proposals_collected']} "
            f"issues={report['summary']['issue_counts']}"
        )
        if not report["passed"] and not args.allow_incomplete:
            raise SystemExit(1)
    elif args.command == "build-project-from-rewrites":
        summary = build_project_from_policy_rewrites(
            args.annotation_pack,
            args.proposals,
            args.output_dir,
            project_id=args.project_id,
            validation_output_path=args.validation_output,
        )
        report = run_project_verifier(Path(summary["project_dir"]))
        print(
            "rewrite-derived project written: "
            f"project={summary['project_id']} memories={summary['memories']} probes={summary['probes']} "
            f"verifier_passed={report.passed}"
        )
        if not report.passed:
            raise SystemExit(f"rewrite-derived project verifier failed: {report.issues}")
    elif args.command == "build-projects-from-rewrite-batch":
        report = build_projects_from_policy_rewrite_batch(
            args.batch_validation_report,
            args.output_dir,
            project_prefix=args.project_prefix,
        )
        print(
            "rewrite-derived project batch written: "
            f"projects={report['summary']['projects_total']} passed={report['summary']['projects_passed']} "
            f"failed={report['summary']['projects_failed']} output_dir={report['output_dir']}"
        )
    elif args.command == "export-project-benchmark-release":
        manifest = export_project_benchmark_release(
            args.project_dirs,
            args.output_dir,
            dataset_name=args.dataset_name,
            version=args.version,
            copy_projects=args.copy_projects,
            require_verifier_passed=not args.allow_unverified,
            llm_generation_performed=args.llm_generated,
            construction=args.construction,
        )
        print(
            "project benchmark release exported: "
            f"dataset={manifest['dataset_name']} projects={manifest['counts']['projects']} "
            f"probes={manifest['counts']['probes']} splits={manifest['splits']}"
        )
        if manifest["counts"]["projects"] == 0 or manifest["counts"]["probes"] == 0:
            raise SystemExit("project benchmark release is empty")
    elif args.command == "verify-project-benchmark-release":
        report = verify_project_benchmark_release(args.release_dir, output_path=args.output)
        print(
            "project benchmark release verified: "
            f"passed={report['passed']} issues={report['summary']['issues']} "
            f"warnings={report['summary']['warnings']} release={args.release_dir}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "export-project-submission-inputs":
        manifest = export_project_submission_inputs(
            args.release_dir,
            args.output_dir,
            include_splits=args.splits,
            include_artifacts=not args.no_artifacts,
            include_events=not args.no_events,
            harden_probe_queries=args.harden_probe_queries,
        )
        print(
            "project submission inputs exported: "
            f"projects={manifest['counts']['projects']} probes={manifest['counts']['probes']} "
            f"events={manifest['counts']['events']} output_dir={args.output_dir}"
        )
    elif args.command == "verify-project-submission-inputs":
        report = verify_project_submission_inputs(args.input_dir, output_path=args.output)
        print(
            "project submission inputs verified: "
            f"passed={report['passed']} issues={report['summary']['issues']} warnings={report['summary']['warnings']} input_dir={args.input_dir}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "validate-project-prediction-submission":
        report = validate_project_prediction_submission(
            args.release_dir,
            args.predictions,
            output_path=args.output,
            require_complete=not args.allow_partial,
        )
        print(
            "project prediction submission validated: "
            f"passed={report['passed']} coverage={report['checks'].get('coverage', {}).get('probe_coverage', 0.0)} "
            f"issues={report['summary']['issues']} warnings={report['summary']['warnings']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "audit-project-release-probe-leakage":
        report = audit_project_release_probe_leakage(
            args.release_dir,
            output_path=args.output,
            high_overlap_threshold=args.high_overlap_threshold,
        )
        print(
            "project release probe leakage audited: "
            f"probes={report['summary']['probes']} "
            f"mean_expected_overlap={report['summary']['mean_expected_overlap']:.3f} "
            f"mean_boundary_overlap={report['summary']['mean_boundary_overlap']:.3f} "
            f"high_any={report['summary']['high_any_overlap_probes']}"
        )
    elif args.command == "audit-submission-input-probe-leakage":
        report = audit_submission_input_probe_leakage(
            args.release_dir,
            args.input_dir,
            output_path=args.output,
            high_overlap_threshold=args.high_overlap_threshold,
        )
        print(
            "submission input probe leakage audited: "
            f"probes={report['summary']['probes']} "
            f"mean_expected_overlap={report['summary']['mean_expected_overlap']:.3f} "
            f"mean_boundary_overlap={report['summary']['mean_boundary_overlap']:.3f} "
            f"high_any={report['summary']['high_any_overlap_probes']} "
            f"missing_gold_keys={report['summary'].get('missing_gold_keys', 0)}"
        )
    elif args.command == "verify-release-integrity":
        report = verify_annotation_release_integrity(args.release_dir, prompt_export_dir=args.prompt_export_dir, output_path=args.output)
        print(
            "release integrity verified: "
            f"passed={report['passed']} issues={report['summary']['issues']} "
            f"warnings={report['summary']['warnings']} release={args.release_dir}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "assess-paper-scale":
        report = assess_release_scale(
            args.release_dir,
            profile=args.profile,
            scale_summary_path=args.scale_summary,
            window_report_path=args.window_report,
            release_integrity_report_path=args.release_integrity_report,
            prompt_export_dir=args.prompt_export_dir,
            output_path=args.output,
        )
        print(
            "paper-scale assessment: "
            f"profile={report['profile']} passed={report['passed']} "
            f"issues={report['summary']['issues']} warnings={report['summary']['warnings']} release={args.release_dir}"
        )
        if not report["passed"] and not args.allow_fail:
            raise SystemExit(1)
    elif args.command == "export-paper-tables":
        tables = export_paper_tables(
            args.output_dir,
            release_baseline_report=args.release_baseline_report,
            prediction_reports=args.prediction_reports or [],
            prediction_batch_reports=args.prediction_batch_reports or [],
            bootstrap_samples=args.bootstrap_samples,
            bootstrap_seed=args.bootstrap_seed,
        )
        print(
            "paper tables exported: "
            f"systems={tables['counts']['systems']} task_rows={tables['counts']['task_rows']} "
            f"capability_rows={tables['counts']['capability_rows']} output_dir={args.output_dir}"
        )
    elif args.command == "verify-project":
        report = run_project_verifier(args.project_dir, args.output)
        print(f"verified project={report.project_id} passed={report.passed} issues={len(report.issues)}")
        if not report.passed:
            raise SystemExit(1)
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
    elif args.command == "readiness-report":
        report = build_readiness_report(
            args.generated_dir,
            output_path=args.output,
            baseline_batch_dir=args.baseline_batch_dir,
            annotation_release_dir=args.annotation_release_dir,
            prompt_export_dir=args.prompt_export_dir,
            rewrite_job_dir=args.rewrite_job_dir,
            rewrite_project_dir=args.rewrite_project_dir,
            staged_slice_manifest=args.staged_slice_manifest,
            gharchive_stage_plan_path=args.gharchive_stage_plan,
            scale_summary_path=args.scale_summary,
            window_report_path=args.window_report,
            public_data_discovery_path=args.public_data_discovery,
            workflow_source_audit_path=args.workflow_source_audit,
            batch_rewrite_validation_path=args.batch_rewrite_validation,
            batch_rewrite_projects_path=args.batch_rewrite_projects,
            project_release_dir=args.project_release_dir,
            project_submission_input_dir=args.project_submission_input_dir,
            project_release_baseline_path=args.project_release_baseline,
            project_release_prediction_path=args.project_release_prediction,
            paper_table_dir=args.paper_table_dir,
            rewrite_human_audit_path=args.rewrite_human_audit,
            probe_leakage_audit_path=args.probe_leakage_audit,
            paper_scale_profile=args.paper_scale_profile,
            require_paper_scale=args.require_paper_scale,
        )
        print(
            "readiness report: "
            f"passed={report['passed']} checks={report['summary']['checks_total']} "
            f"failed={report['summary']['failed']} warnings={report['summary']['warnings']} output={args.output}"
        )
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
