from __future__ import annotations

import argparse
from pathlib import Path

from ultra_long_benchmark.artifact_bundle import audit_artifact_bundle
from ultra_long_benchmark.artifact_bundle import DEFAULT_BENCHMARK_RELEASE_ARTIFACTS
from ultra_long_benchmark.artifact_bundle import verify_artifact_bundle_manifest
from ultra_long_benchmark.claim_boundary import audit_paper_claim_boundaries
from ultra_long_benchmark.claim_boundary import verify_paper_claim_boundary_audit
from ultra_long_benchmark.claim_lint import DEFAULT_CLAIM_LINT_PATHS
from ultra_long_benchmark.claim_lint import lint_paper_claims
from ultra_long_benchmark.claim_lint import verify_paper_claim_lint_report
from ultra_long_benchmark.data_discovery import DEFAULT_PUBLIC_ROOTS
from ultra_long_benchmark.data_discovery import discover_public_data_sources
from ultra_long_benchmark.data_discovery import verify_public_data_discovery_report
from ultra_long_benchmark.domain_expansion import build_domain_expansion_readiness_report
from ultra_long_benchmark.domain_expansion import DEFAULT_DOMAIN_EXPANSION_REPORTS
from ultra_long_benchmark.domain_expansion import verify_domain_expansion_readiness_report
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
from ultra_long_benchmark.pipelines.baseline_configs import verify_baseline_batch_report
from ultra_long_benchmark.pipelines.baseline_configs import verify_baseline_config_validation_report
from ultra_long_benchmark.paper_scale import assess_release_scale
from ultra_long_benchmark.benchmark_release_gate import build_benchmark_release_gate_report
from ultra_long_benchmark.benchmark_release_gate import DEFAULT_GATE_REPORTS
from ultra_long_benchmark.paper_tables import export_paper_tables
from ultra_long_benchmark.probe_audit import audit_project_release_probe_leakage
from ultra_long_benchmark.probe_audit import audit_submission_input_probe_leakage
from ultra_long_benchmark.pipelines.evaluation import run_project_baseline_evaluation
from ultra_long_benchmark.pipelines.evaluation import run_project_release_baseline_evaluation
from ultra_long_benchmark.pipelines.evaluation import run_submission_input_baseline
from ultra_long_benchmark.pipelines.evaluation import score_project_release_prediction_dir
from ultra_long_benchmark.pipelines.evaluation import score_project_release_action_traces
from ultra_long_benchmark.pipelines.evaluation import score_project_release_predictions
from ultra_long_benchmark.pipelines.evaluation import score_project_predictions
from ultra_long_benchmark.pipelines.evaluation import score_action_traces
from ultra_long_benchmark.pipelines.enron_email_manifest import DEFAULT_ENRON_TARBALL
from ultra_long_benchmark.pipelines.enron_email_manifest import DEFAULT_OUTPUT_PATH as DEFAULT_ENRON_MANIFEST_OUTPUT
from ultra_long_benchmark.pipelines.enron_email_manifest import build_enron_email_workflow_manifest
from ultra_long_benchmark.pipelines.gharchive import DEFAULT_FIXTURE_PATH as DEFAULT_GHARCHIVE_FIXTURE_PATH
from ultra_long_benchmark.pipelines.gharchive import DEFAULT_REPO as DEFAULT_GHARCHIVE_REPO
from ultra_long_benchmark.pipelines.gharchive import build_gharchive_slice
from ultra_long_benchmark.pipelines.gharchive import mine_gharchive_policy_candidates
from ultra_long_benchmark.pipelines.gharchive import plan_gharchive_stage
from ultra_long_benchmark.pipelines.gharchive import profile_gharchive_repos
from ultra_long_benchmark.pipelines.gharchive import profile_gharchive_time_windows
from ultra_long_benchmark.pipelines.gharchive import rank_gharchive_repos
from ultra_long_benchmark.pipelines.gharchive import select_gharchive_annotation_repos
from ultra_long_benchmark.pipelines.llm_rewrite import run_policy_rewrite_llm_job
from ultra_long_benchmark.pipelines.llm_rewrite import run_policy_rewrite_llm_jobs
from ultra_long_benchmark.pipelines.external_memory_runner import run_external_memory_submission_runner
from ultra_long_benchmark.pipelines.external_memory_runner import validate_external_memory_predictions_against_input
from ultra_long_benchmark.pipelines.memory_submission import plan_external_memory_submission_adapter
from ultra_long_benchmark.pipelines.memory_submission import run_memory_submission_baseline
from ultra_long_benchmark.pipelines.memory_submission import supported_memory_submission_adapters
from ultra_long_benchmark.pipelines.rewrite_audit import export_policy_rewrite_human_audit_pack
from ultra_long_benchmark.pipelines.rewrite_audit import validate_policy_rewrite_human_audit
from ultra_long_benchmark.pipelines.source_adapters import validate_workflow_manifest_adapter
from ultra_long_benchmark.pipelines.verifier import run_project_verifier
from ultra_long_benchmark.pipelines.workflow_manifest_project import build_project_from_workflow_manifest
from ultra_long_benchmark.pipelines.workflow_manifest_project import preflight_workflow_manifest_release
from ultra_long_benchmark.pipelines.workflow_manifest_project import preflight_workflow_manifest_release_batch
from ultra_long_benchmark.pipelines.workflow_manifest_project import verify_workflow_manifest_preflight_batch_report
from ultra_long_benchmark.pipelines.workflow_manifest_project import verify_workflow_manifest_preflight_report
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
from ultra_long_benchmark.source_audit import verify_workflow_data_source_audit
from ultra_long_benchmark.taxonomy_coverage import audit_project_release_taxonomy_coverage
from ultra_long_benchmark.taxonomy_coverage import verify_project_release_taxonomy_coverage_audit


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "examples" / "generated"


def _add_release_gate_args(gate_parser: argparse.ArgumentParser) -> None:
    gate_parser.add_argument(
        "--output",
        type=Path,
        default=GENERATED / "evaluation_harness" / "gharchive_formal_gate_report.json",
        help="Output benchmark release gate summary JSON.",
    )
    gate_parser.add_argument("--root", type=Path, default=ROOT, help="Root used to resolve relative report paths.")
    gate_parser.add_argument("--report", action="append", default=[], help="Additional or overriding report mapping in name=path form.")
    gate_parser.add_argument(
        "--workflow-manifest-preflight",
        action="append",
        default=[],
        type=Path,
        help="Optional report produced by preflight-workflow-manifest-release. Repeat for multiple domains.",
    )
    gate_parser.add_argument(
        "--workflow-manifest-preflight-batch",
        action="append",
        default=[],
        type=Path,
        help="Optional report produced by preflight-workflow-manifest-release-batch. Repeat for multiple batches.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ultra-long benchmark construction CLI")
    sub = parser.add_subparsers(dest="command", required=True)
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
    score_release_traces = sub.add_parser("score-project-release-action-traces")
    score_release_traces.add_argument("release_dir", type=Path, help="Project benchmark release directory.")
    score_release_traces.add_argument("traces", type=Path, help="JSONL action traces with project_id/probe_id fields.")
    score_release_traces.add_argument("--output", type=Path, help="Optional output JSON path.")
    score_release_traces.add_argument("--system-name", default="external_trace_system", help="Name to record for the traced system.")
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
    memory_submission.add_argument("--provider-config", type=Path, help="Optional OpenAI-compatible provider config JSON, such as opencode.json.")
    memory_submission.add_argument("--model", help="OpenAI-compatible model name for external prompt adapters.")
    memory_submission.add_argument("--max-output-tokens", type=int, default=512, help="Maximum output tokens per external adapter prediction.")
    memory_submission.add_argument("--request-timeout", type=float, default=60.0, help="OpenAI-compatible request timeout in seconds.")
    memory_submission.add_argument("--max-retries", type=int, default=3, help="Retry count for transient OpenAI-compatible provider failures.")
    memory_submission.add_argument("--retry-backoff-seconds", type=float, default=2.0, help="Initial exponential backoff delay for provider retries.")
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
    verify_baseline_config = sub.add_parser("verify-baseline-config-validation")
    verify_baseline_config.add_argument("report", type=Path, help="Report produced by validate-baseline-config on a directory.")
    verify_baseline_config.add_argument("--output", type=Path, help="Optional JSON verification report path.")
    verify_baseline_config.add_argument("--root", type=Path, help="Override root for resolving relative config paths.")
    verify_baseline_batch = sub.add_parser("verify-baseline-batch")
    verify_baseline_batch.add_argument("report", type=Path, help="Report produced by run-baseline-config-dir.")
    verify_baseline_batch.add_argument("--output", type=Path, help="Optional JSON verification report path.")
    verify_baseline_batch.add_argument("--root", type=Path, help="Override root for resolving runner report and output artifact paths.")
    run_baseline = sub.add_parser("run-baseline-config")
    run_baseline.add_argument("config", type=Path, help="Baseline YAML config to run or dry-run.")
    run_baseline.add_argument("--output", type=Path, help="Optional runner report JSON path.")
    run_baseline.add_argument("--dry-run", action="store_true", help="Validate and report planned execution without running.")
    run_baseline.add_argument("--allow-llm-api", action="store_true", help="Allow configs that require LLM/API credentials.")
    run_baseline.add_argument("--allow-external-runner", action="store_true", help="Allow baseline configs to import and invoke external memory runner plugins.")
    run_baseline_dir = sub.add_parser("run-baseline-config-dir")
    run_baseline_dir.add_argument("config_dir", type=Path, help="Directory of baseline YAML configs.")
    run_baseline_dir.add_argument("--output-dir", type=Path, default=GENERATED / "evaluation_harness" / "baseline_batch", help="Output directory for per-config runner reports.")
    run_baseline_dir.add_argument("--no-dry-run-external", action="store_true", help="Do not dry-run LLM/API configs automatically.")
    run_baseline_dir.add_argument("--allow-llm-api", action="store_true", help="Allow configs that require LLM/API credentials.")
    run_baseline_dir.add_argument("--allow-external-runner", action="store_true", help="Allow baseline configs to import and invoke external memory runner plugins.")
    discover_data = sub.add_parser("discover-public-data")
    discover_data.add_argument("--root", action="append", dest="roots", type=Path, help="Root directory to scan. Repeat for multiple roots. Defaults to /home/jmzhang/Workspace/data, /data1/public, and /data1/public/hf.")
    discover_data.add_argument("--output", type=Path, default=GENERATED / "public_data_discovery_report.json", help="Output JSON discovery report.")
    discover_data.add_argument("--max-depth", type=int, default=5, help="Maximum directory depth below each root.")
    discover_data.add_argument("--max-files", type=int, default=1000, help="Maximum candidate files to inspect.")
    discover_data.add_argument("--sample-records", type=int, default=3, help="Number of JSON/JSONL records to sample per file.")
    verify_discovery = sub.add_parser("verify-public-data-discovery")
    verify_discovery.add_argument("report", type=Path, help="Report produced by discover-public-data.")
    verify_discovery.add_argument("--output", type=Path, help="Optional JSON verification report path.")
    verify_discovery.add_argument("--root", type=Path, help="Override root used to resolve candidate file paths.")
    validate_manifest = sub.add_parser("validate-workflow-manifest")
    validate_manifest.add_argument("manifest", type=Path, help="Reviewed email/calendar/docs/chat/browser workflow manifest JSON.")
    validate_manifest.add_argument("--output", type=Path, help="Optional JSON validation report path.")
    validate_manifest.add_argument("--adapter", choices=["auto", "email", "workflow"], default="auto", help="Manifest adapter to use. Auto selects by domain.")
    validate_manifest.add_argument("--no-redact", action="store_true", help="Disable redaction while validating. Use only for already-safe fixtures.")
    enron_manifest = sub.add_parser("build-enron-email-workflow-manifest")
    enron_manifest.add_argument("--tarball", type=Path, default=DEFAULT_ENRON_TARBALL, help="Local CMU Enron maildir tarball.")
    enron_manifest.add_argument("--output", type=Path, default=DEFAULT_ENRON_MANIFEST_OUTPUT, help="Output redacted email workflow manifest JSON.")
    enron_manifest.add_argument("--project-id", default="project_enron_email_workflow_001", help="Project id stored in the generated manifest.")
    enron_manifest.add_argument("--max-records", type=int, default=12, help="Maximum raw Enron messages to sample before deriving the manifest.")
    enron_manifest.add_argument("--max-body-chars", type=int, default=700, help="Maximum redacted body characters retained per source email record.")
    workflow_manifest_project = sub.add_parser("build-project-from-workflow-manifest")
    workflow_manifest_project.add_argument("manifest", type=Path, help="Reviewed workflow manifest containing records, memory_graph, and probes.")
    workflow_manifest_project.add_argument("--output-dir", type=Path, default=GENERATED / "projects", help="Project-centric generated output directory.")
    workflow_manifest_project.add_argument("--report", type=Path, help="Optional project build report JSON path.")
    workflow_manifest_project.add_argument("--adapter", choices=["auto", "email", "workflow"], default="auto", help="Manifest adapter to use. Auto selects by domain.")
    workflow_manifest_project.add_argument("--no-redact", action="store_true", help="Disable redaction while writing project files. Use only for already-safe fixtures.")
    workflow_manifest_preflight = sub.add_parser("preflight-workflow-manifest-release")
    workflow_manifest_preflight.add_argument("manifest", type=Path, help="Reviewed workflow manifest containing records, memory_graph, and probes.")
    workflow_manifest_preflight.add_argument("--output-dir", type=Path, default=GENERATED / "workflow_manifest_preflight", help="Output directory for project, release, no-gold input, and audit reports.")
    workflow_manifest_preflight.add_argument("--report", type=Path, help="Optional preflight report JSON path. Defaults to <output-dir>/workflow_manifest_release_preflight.json.")
    workflow_manifest_preflight.add_argument("--adapter", choices=["auto", "email", "workflow"], default="auto", help="Manifest adapter to use. Auto selects by domain.")
    workflow_manifest_preflight.add_argument("--no-redact", action="store_true", help="Disable redaction while writing project files. Use only for already-safe fixtures.")
    workflow_manifest_preflight.add_argument("--dataset-name", help="Dataset name stored in the temporary project benchmark release.")
    workflow_manifest_preflight.add_argument("--version", default="0.1.0", help="Release version stored in the temporary project benchmark release.")
    workflow_manifest_preflight.add_argument("--baseline", action="append", dest="baselines", help="Deterministic project baseline to run. Repeat for multiple baselines.")
    workflow_manifest_preflight.add_argument("--top-k", type=int, default=5, help="Top-k event retrieval for deterministic baselines.")
    workflow_manifest_preflight.add_argument("--harden-probe-queries", action="store_true", help="Export hardened no-gold public probe queries.")
    workflow_manifest_preflight_batch = sub.add_parser("preflight-workflow-manifest-release-batch")
    workflow_manifest_preflight_batch.add_argument("manifest", nargs="+", type=Path, help="Reviewed workflow manifests containing records, memory_graph, and probes.")
    workflow_manifest_preflight_batch.add_argument("--output-dir", type=Path, default=GENERATED / "workflow_manifest_preflight_batch", help="Output directory for per-manifest preflights and batch report.")
    workflow_manifest_preflight_batch.add_argument("--report", type=Path, help="Optional batch report JSON path. Defaults to <output-dir>/workflow_manifest_preflight_batch_report.json.")
    workflow_manifest_preflight_batch.add_argument("--adapter", choices=["auto", "email", "workflow"], default="auto", help="Manifest adapter to use. Auto selects by domain.")
    workflow_manifest_preflight_batch.add_argument("--no-redact", action="store_true", help="Disable redaction while writing project files. Use only for already-safe fixtures.")
    workflow_manifest_preflight_batch.add_argument("--version", default="0.1.0", help="Release version stored in each temporary project benchmark release.")
    workflow_manifest_preflight_batch.add_argument("--baseline", action="append", dest="baselines", help="Deterministic project baseline to run. Repeat for multiple baselines.")
    workflow_manifest_preflight_batch.add_argument("--top-k", type=int, default=5, help="Top-k event retrieval for deterministic baselines.")
    workflow_manifest_preflight_batch.add_argument("--harden-probe-queries", action="store_true", help="Export hardened no-gold public probe queries.")
    verify_workflow_manifest_preflight = sub.add_parser("verify-workflow-manifest-preflight")
    verify_workflow_manifest_preflight.add_argument("report", type=Path, help="Report produced by preflight-workflow-manifest-release.")
    verify_workflow_manifest_preflight.add_argument("--output", type=Path, help="Optional verification report JSON path.")
    verify_workflow_manifest_preflight.add_argument("--root", type=Path, help="Override root used to resolve preflight artifact paths.")
    verify_workflow_manifest_preflight_batch = sub.add_parser("verify-workflow-manifest-preflight-batch")
    verify_workflow_manifest_preflight_batch.add_argument("report", type=Path, help="Report produced by preflight-workflow-manifest-release-batch.")
    verify_workflow_manifest_preflight_batch.add_argument("--output", type=Path, help="Optional verification report JSON path.")
    verify_workflow_manifest_preflight_batch.add_argument("--root", type=Path, help="Override root used to resolve batch preflight report paths.")
    source_audit = sub.add_parser("audit-workflow-data-sources")
    source_audit.add_argument("--discovery-report", type=Path, default=GENERATED / "public_data_discovery_report.json", help="Report produced by discover-public-data.")
    source_audit.add_argument("--gharchive-stage-plan", type=Path, help="Optional report produced by gharchive-stage-plan.")
    source_audit.add_argument("--output", type=Path, default=GENERATED / "workflow_data_source_audit.json", help="Output source audit report.")
    source_audit.add_argument("--require-paper-ready", action="store_true", help="Fail unless sources and GHArchive stage plan are paper-ready.")
    verify_source_audit = sub.add_parser("verify-workflow-data-source-audit")
    verify_source_audit.add_argument("report", type=Path, help="Report produced by audit-workflow-data-sources.")
    verify_source_audit.add_argument("--output", type=Path, help="Optional verification report JSON path.")
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
    gharchive_annotation_pack_batch.add_argument("--output-dir", type=Path, default=GENERATED / "annotation_packs" / "gharchive_formal", help="Output directory for per-repo annotation packs.")
    gharchive_annotation_pack_batch.add_argument("--pack-prefix", default="gharchive_formal_policy_pack", help="Stable pack id prefix.")
    export_annotation_release = sub.add_parser("export-annotation-pack-release")
    export_annotation_release.add_argument("batch_dir", type=Path, help="Directory produced by gharchive-annotation-pack-batch.")
    export_annotation_release.add_argument("--output-dir", type=Path, default=GENERATED / "release_packaging" / "gharchive_formal_annotation_pack", help="Output release directory.")
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
    rewrite_jobs.add_argument("--output-dir", type=Path, default=GENERATED / "annotation_packs" / "gharchive_formal_rewrite_jobs", help="Output directory for annotation job shards.")
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
    collect_rewrite_jobs.add_argument("--output", type=Path, default=GENERATED / "annotation_packs" / "gharchive_formal_rewrite_jobs" / "collected_rewrite_proposals.jsonl", help="Unified JSONL proposals output for validate-policy-rewrites-batch.")
    collect_rewrite_jobs.add_argument("--report", type=Path, help="Optional collection report JSON path.")
    collect_rewrite_jobs.add_argument("--proposal-filename", default="proposals.jsonl", help="Completed proposal filename expected inside each job directory.")
    collect_rewrite_jobs.add_argument("--allow-incomplete", action="store_true", help="Write the collection report without exiting nonzero when jobs are missing or unfilled.")
    rewrite_project = sub.add_parser("build-project-from-rewrites")
    rewrite_project.add_argument("annotation_pack", type=Path, help="annotation_pack.json generated by gharchive-annotation-pack.")
    rewrite_project.add_argument("proposals", type=Path, help="Validated JSONL rewrite/probe proposals.")
    rewrite_project.add_argument("--output-dir", type=Path, default=GENERATED / "projects", help="Project-centric generated output directory.")
    rewrite_project.add_argument("--project-id", default="project_gharchive_rewrite_single", help="Project id for generated output.")
    rewrite_project.add_argument("--validation-output", type=Path, help="Optional rewrite validation report path.")
    rewrite_project_batch = sub.add_parser("build-projects-from-rewrite-batch")
    rewrite_project_batch.add_argument("batch_validation_report", type=Path, help="batch_rewrite_validation_report.json from validate-policy-rewrites-batch.")
    rewrite_project_batch.add_argument("--output-dir", type=Path, default=GENERATED / "projects" / "gharchive_formal_batch", help="Project-centric generated output directory.")
    rewrite_project_batch.add_argument("--project-prefix", default="project_gharchive_formal", help="Project id prefix for generated projects.")
    export_project_release = sub.add_parser("export-project-benchmark-release")
    export_project_release.add_argument("project_dirs", nargs="+", type=Path, help="Verifier-checked project directories to include.")
    export_project_release.add_argument("--output-dir", type=Path, default=GENERATED / "release_packaging" / "gharchive_formal_project_benchmark", help="Output project benchmark release directory.")
    export_project_release.add_argument("--dataset-name", default="longuserpolicy_gharchive_project_benchmark", help="Dataset/release name.")
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
    export_submission_inputs.add_argument("--output-dir", type=Path, default=GENERATED / "evaluation_harness" / "gharchive_formal_submission_inputs", help="Output no-gold submission input directory.")
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
    taxonomy_coverage = sub.add_parser("audit-project-release-taxonomy-coverage")
    taxonomy_coverage.add_argument("release_dir", type=Path, help="Project benchmark release directory.")
    taxonomy_coverage.add_argument("--output", type=Path, help="Optional taxonomy/domain coverage audit JSON path.")
    taxonomy_coverage.add_argument("--require-multi-domain", action="store_true", help="Fail unless at least two real workflow domains are covered.")
    verify_taxonomy_coverage = sub.add_parser("verify-project-release-taxonomy-coverage")
    verify_taxonomy_coverage.add_argument("report", type=Path, help="Report produced by audit-project-release-taxonomy-coverage.")
    verify_taxonomy_coverage.add_argument("--output", type=Path, help="Optional verification report JSON path.")
    claim_boundary = sub.add_parser("audit-paper-claim-boundaries")
    claim_boundary.add_argument("--output", type=Path, default=GENERATED / "evaluation_harness" / "benchmark_release_claim_boundary_audit.json", help="Output benchmark release claim-boundary audit JSON path.")
    claim_boundary.add_argument("--readiness-report", type=Path, help="Readiness report JSON.")
    claim_boundary.add_argument("--taxonomy-coverage", type=Path, help="Taxonomy/domain coverage audit JSON.")
    claim_boundary.add_argument("--workflow-source-audit", type=Path, help="Workflow source audit JSON.")
    claim_boundary.add_argument("--hardened-probe-leakage-audit", type=Path, help="Hardened submission-input probe leakage audit JSON.")
    claim_boundary.add_argument("--human-audit-report", type=Path, help="Human audit validation report JSON.")
    claim_boundary.add_argument("--baseline-batch-report", type=Path, help="Baseline batch report JSON.")
    claim_boundary.add_argument("--external-runner-report", type=Path, help="Optional executed external memory runner contract report JSON.")
    verify_claim_boundary = sub.add_parser("verify-paper-claim-boundaries")
    verify_claim_boundary.add_argument("report", type=Path, help="Claim-boundary audit JSON produced by audit-paper-claim-boundaries.")
    verify_claim_boundary.add_argument("--output", type=Path, help="Optional verification report JSON path.")
    claim_lint = sub.add_parser("lint-paper-claims")
    claim_lint.add_argument("--output", type=Path, default=GENERATED / "evaluation_harness" / "gharchive_formal_claim_lint.json", help="Output benchmark release claim-lint JSON.")
    claim_lint.add_argument("--root", type=Path, default=ROOT, help="Root used to resolve relative file paths.")
    claim_lint.add_argument("--path", action="append", default=[], help="Markdown/text file to lint. Repeat for multiple files. Defaults to core paper-facing docs.")
    verify_claim_lint = sub.add_parser("verify-paper-claim-lint")
    verify_claim_lint.add_argument("report", type=Path, help="Paper claim lint JSON produced by lint-paper-claims.")
    verify_claim_lint.add_argument("--output", type=Path, help="Optional verification report JSON path.")
    verify_claim_lint.add_argument("--root", type=Path, help="Override root used to resolve source doc paths.")
    artifact_bundle = sub.add_parser("audit-artifact-bundle")
    artifact_bundle.add_argument("--output", type=Path, default=GENERATED / "evaluation_harness" / "benchmark_release_artifact_bundle_manifest.json", help="Output artifact bundle manifest JSON.")
    artifact_bundle.add_argument("--root", type=Path, default=ROOT, help="Root used to resolve relative artifact paths.")
    artifact_bundle.add_argument("--artifact", action="append", default=[], help="Additional or overriding artifact mapping in name=path form.")
    verify_artifact_bundle = sub.add_parser("verify-artifact-bundle")
    verify_artifact_bundle.add_argument("manifest", type=Path, help="Artifact bundle manifest JSON produced by audit-artifact-bundle.")
    verify_artifact_bundle.add_argument("--output", type=Path, help="Optional verification report JSON path.")
    benchmark_release_gate = sub.add_parser("benchmark-release-gate-report", help="Canonical formal benchmark release gate.")
    _add_release_gate_args(benchmark_release_gate)
    domain_expansion = sub.add_parser("audit-domain-expansion-readiness")
    domain_expansion.add_argument("--output", type=Path, default=GENERATED / "evaluation_harness" / "gharchive_formal_domain_expansion_readiness.json", help="Output domain-expansion readiness JSON.")
    domain_expansion.add_argument("--root", type=Path, default=ROOT, help="Root used to resolve relative report paths.")
    domain_expansion.add_argument("--report", action="append", default=[], help="Additional or overriding report mapping in name=path form.")
    domain_expansion.add_argument("--workflow-manifest-preflight", action="append", default=[], type=Path, help="Optional report produced by preflight-workflow-manifest-release. Repeat for multiple domains.")
    domain_expansion.add_argument("--workflow-manifest-preflight-batch", action="append", default=[], type=Path, help="Optional report produced by preflight-workflow-manifest-release-batch. Repeat for multiple batches.")
    domain_expansion.add_argument("--require-multi-domain", action="store_true", help="Fail unless at least two workflow domains are release-ready.")
    verify_domain_expansion = sub.add_parser("verify-domain-expansion-readiness")
    verify_domain_expansion.add_argument("report", type=Path, help="Domain-expansion readiness JSON produced by audit-domain-expansion-readiness.")
    verify_domain_expansion.add_argument("--output", type=Path, help="Optional verification report JSON path.")
    verify_domain_expansion.add_argument("--root", type=Path, help="Override root used to resolve input report paths.")
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
    paper_tables.add_argument("--release-baseline-report", type=Path, default=GENERATED / "evaluation_harness" / "gharchive_formal_project_release_baselines.json", help="Release deterministic baseline report.")
    paper_tables.add_argument("--prediction-report", action="append", dest="prediction_reports", type=Path, help="Release prediction scoring report. Repeat for multiple systems.")
    paper_tables.add_argument("--prediction-batch-report", action="append", dest="prediction_batch_reports", type=Path, help="Batch report from score-project-release-prediction-dir. Repeat for multiple batches.")
    paper_tables.add_argument("--bootstrap-samples", type=int, default=1000, help="Project-level bootstrap samples for confidence intervals.")
    paper_tables.add_argument("--bootstrap-seed", type=int, default=0, help="Seed for deterministic bootstrap confidence intervals.")
    paper_tables.add_argument("--output-dir", type=Path, default=GENERATED / "evaluation_harness" / "gharchive_formal_paper_tables", help="Output directory for JSON/CSV/Markdown tables.")
    verify = sub.add_parser("verify-project")
    verify.add_argument("project_dir", type=Path, help="Project directory containing artifacts/events/memory_graph/probes.")
    verify.add_argument("--output", type=Path, help="Optional verifier report output path.")
    readiness = sub.add_parser("readiness-report")
    readiness.add_argument("--generated-dir", type=Path, default=GENERATED, help="Generated artifact directory to inspect.")
    readiness.add_argument("--output", type=Path, default=GENERATED / "readiness_report.json", help="Output JSON readiness report.")
    readiness.add_argument("--baseline-batch-dir", type=Path, help="Optional baseline batch report directory.")
    readiness.add_argument("--annotation-release-dir", type=Path, help="Optional annotation release directory.")
    readiness.add_argument("--prompt-export-dir", type=Path, help="Optional prompt export directory.")
    readiness.add_argument("--rewrite-job-dir", type=Path, help="Optional packaged rewrite annotation job directory.")
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
    readiness.add_argument("--taxonomy-coverage-audit", type=Path, help="Optional task taxonomy and workflow-domain coverage audit report.")
    readiness.add_argument("--claim-boundary-audit", type=Path, help="Optional paper-facing claim boundary audit report.")
    readiness.add_argument("--claim-lint", type=Path, help="Optional paper-facing claim lint report.")
    readiness.add_argument("--artifact-bundle-manifest", type=Path, help="Optional reproducibility artifact bundle manifest.")
    readiness.add_argument("--paper-scale-profile", choices=["fixture", "pilot", "paper"], default="paper", help="Scale profile to assess inside readiness.")
    readiness.add_argument("--require-paper-scale", action="store_true", help="Fail readiness if the paper-scale profile is not met.")
    args = parser.parse_args()

    if args.command == "evaluate-project":
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
    elif args.command == "score-project-release-action-traces":
        output_path = args.output or (args.release_dir / "project_release_action_trace_report.json")
        report = score_project_release_action_traces(args.release_dir, args.traces, output_path, system_name=args.system_name)
        print(
            "project release action traces scored: "
            f"projects={report['summary']['projects']} traces={report['summary']['traces']} "
            f"probe_coverage={report['summary']['probe_coverage']:.3f} "
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
            provider_config_path=args.provider_config,
            model=args.model,
            max_output_tokens=args.max_output_tokens,
            request_timeout=args.request_timeout,
            max_retries=args.max_retries,
            retry_backoff_seconds=args.retry_backoff_seconds,
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
    elif args.command == "verify-baseline-config-validation":
        report = verify_baseline_config_validation_report(args.report, output_path=args.output, root=args.root)
        print(
            "baseline config validation verified: "
            f"passed={report['passed']} configs={report['summary']['configs_total']} "
            f"verified={report['summary']['configs_verified']} issues={report['summary']['issues']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "verify-baseline-batch":
        report = verify_baseline_batch_report(args.report, output_path=args.output, root=args.root)
        print(
            "baseline batch verified: "
            f"passed={report['passed']} reports={report['summary']['reports_total']} "
            f"runner_reports={report['summary']['runner_reports_verified']} "
            f"output_artifacts={report['summary']['output_artifacts_verified']} "
            f"issues={report['summary']['issues']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "run-baseline-config":
        report = run_baseline_config(
            args.config,
            output_path=args.output,
            dry_run=args.dry_run,
            allow_llm_api=args.allow_llm_api,
            allow_external_runner=args.allow_external_runner,
        )
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
            allow_external_runner=args.allow_external_runner,
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
            f"workflow_manifests={sum(int(report['summary'].get(key, 0)) for key in ['calendar_manifest_sources', 'docs_manifest_sources', 'chat_manifest_sources', 'browser_web_manifest_sources'])} "
            f"output={args.output}"
        )
    elif args.command == "verify-public-data-discovery":
        report = verify_public_data_discovery_report(args.report, output_path=args.output, root=args.root)
        print(
            "public data discovery verified: "
            f"passed={report['passed']} candidates={report['summary']['candidates_verified']}/{report['summary']['candidates_total']} "
            f"issues={report['summary']['issues']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "validate-workflow-manifest":
        report = validate_workflow_manifest_adapter(
            args.manifest,
            output_path=args.output,
            adapter=args.adapter,
            redact_sensitive=not args.no_redact,
        )
        print(
            "workflow manifest validated: "
            f"passed={report['passed']} adapter={report['adapter']} domain={report['domain']} "
            f"records={report['summary']['records']} events={report['summary']['events']} issues={report['summary']['issues']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "build-enron-email-workflow-manifest":
        report = build_enron_email_workflow_manifest(
            args.tarball,
            args.output,
            project_id=args.project_id,
            max_records=args.max_records,
            max_body_chars=args.max_body_chars,
        )
        print(
            "Enron email workflow manifest built: "
            f"passed={report['passed']} project={report['project_id']} "
            f"records={report['summary']['records']} probes={report['summary']['probes']} "
            f"output={report['manifest_path']}"
        )
    elif args.command == "build-project-from-workflow-manifest":
        report = build_project_from_workflow_manifest(
            args.manifest,
            args.output_dir,
            output_report_path=args.report,
            adapter=args.adapter,
            redact_sensitive=not args.no_redact,
        )
        print(
            "workflow manifest project built: "
            f"passed={report['passed']} project={report['project_id']} domain={report['domain']} "
            f"events={report['summary']['events']} memories={report['summary']['memories']} "
            f"probes={report['summary']['probes']} verifier_passed={report['summary']['verifier_passed']} "
            f"project_dir={report['project_dir']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "preflight-workflow-manifest-release":
        output_report = args.report or (args.output_dir / "workflow_manifest_release_preflight.json")
        report = preflight_workflow_manifest_release(
            args.manifest,
            args.output_dir,
            output_report_path=output_report,
            adapter=args.adapter,
            redact_sensitive=not args.no_redact,
            dataset_name=args.dataset_name,
            version=args.version,
            baseline_names=args.baselines or None,
            top_k=args.top_k,
            harden_probe_queries=args.harden_probe_queries,
        )
        print(
            "workflow manifest release preflight: "
            f"passed={report['passed']} project={report['project_id']} domain={report['domain']} "
            f"scope={report['summary']['release_scope']} checks={report['summary']['checks_passed']}/{report['summary']['checks_total']} "
            f"issues={report['summary']['issues']} output={output_report}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "preflight-workflow-manifest-release-batch":
        output_report = args.report or (args.output_dir / "workflow_manifest_preflight_batch_report.json")
        report = preflight_workflow_manifest_release_batch(
            args.manifest,
            args.output_dir,
            output_report_path=output_report,
            adapter=args.adapter,
            redact_sensitive=not args.no_redact,
            version=args.version,
            baseline_names=args.baselines or None,
            top_k=args.top_k,
            harden_probe_queries=args.harden_probe_queries,
        )
        print(
            "workflow manifest preflight batch: "
            f"passed={report['passed']} reports={report['summary']['reports_passed']}/{report['summary']['reports_total']} "
            f"domains={','.join(report['summary']['domains'])} issues={report['summary']['issues']} output={output_report}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "verify-workflow-manifest-preflight":
        report = verify_workflow_manifest_preflight_report(args.report, output_path=args.output, root=args.root)
        print(
            "workflow manifest preflight verified: "
            f"passed={report['passed']} artifacts={report['summary']['artifacts_verified']}/{report['summary']['artifacts_total']} "
            f"issues={report['summary']['issues']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "verify-workflow-manifest-preflight-batch":
        report = verify_workflow_manifest_preflight_batch_report(args.report, output_path=args.output, root=args.root)
        print(
            "workflow manifest preflight batch verified: "
            f"passed={report['passed']} reports={report['summary']['reports_verified']}/{report['summary']['reports_total']} "
            f"issues={report['summary']['issues']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
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
    elif args.command == "verify-workflow-data-source-audit":
        report = verify_workflow_data_source_audit(args.report, output_path=args.output)
        print(
            "workflow data source audit verified: "
            f"passed={report['passed']} issues={report['summary']['issues']} "
            f"discovery_candidates={report['summary']['discovery_verification'].get('candidates_verified')}/"
            f"{report['summary']['discovery_verification'].get('candidates_total')}"
        )
        if not report["passed"]:
            raise SystemExit(1)
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
    elif args.command == "audit-project-release-taxonomy-coverage":
        report = audit_project_release_taxonomy_coverage(
            args.release_dir,
            output_path=args.output,
            require_multi_domain=args.require_multi_domain,
        )
        print(
            "project release taxonomy coverage audited: "
            f"passed={report['passed']} scope={report['summary']['current_release_domain_scope']} "
            f"domains={','.join(report['summary']['covered_workflow_domains']) or 'none'} "
            f"task_types={report['summary']['task_types']} capabilities={report['summary']['capabilities_covered']} "
            f"issues={report['summary']['issues']} warnings={report['summary']['warnings']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "verify-project-release-taxonomy-coverage":
        report = verify_project_release_taxonomy_coverage_audit(args.report, output_path=args.output)
        print(
            "project release taxonomy coverage verified: "
            f"passed={report['passed']} issues={report['summary']['issues']} "
            f"release_dir={report['summary']['release_dir']}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "audit-paper-claim-boundaries":
        report = audit_paper_claim_boundaries(
            output_path=args.output,
            readiness_report_path=args.readiness_report,
            taxonomy_coverage_path=args.taxonomy_coverage,
            workflow_source_audit_path=args.workflow_source_audit,
            hardened_probe_leakage_audit_path=args.hardened_probe_leakage_audit,
            human_audit_report_path=args.human_audit_report,
            baseline_batch_report_path=args.baseline_batch_report,
            external_runner_report_path=args.external_runner_report,
        )
        print(
            "paper claim boundaries audited: "
            f"supported={report['summary']['supported']} qualified={report['summary']['qualified']} "
            f"blocked={report['summary']['blocked']} output={args.output}"
        )
    elif args.command == "verify-paper-claim-boundaries":
        report = verify_paper_claim_boundary_audit(args.report, output_path=args.output)
        print(
            "paper claim boundaries verified: "
            f"passed={report['passed']} issues={report['summary']['issues']} "
            f"original_supported={report['summary'].get('original_supported')} recomputed_supported={report['summary'].get('recomputed_supported')} "
            f"original_blocked={report['summary'].get('original_blocked')} recomputed_blocked={report['summary'].get('recomputed_blocked')}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "lint-paper-claims":
        paths = [Path(path) for path in args.path] if args.path else [Path(path) for path in DEFAULT_CLAIM_LINT_PATHS]
        report = lint_paper_claims(paths, output_path=args.output, root=args.root)
        print(
            "paper claims linted: "
            f"passed={report['passed']} files={report['summary']['files_scanned']}/{report['summary']['files_total']} "
            f"issues={report['summary']['issues']} allowed_mentions={report['summary']['allowed_blocked_claim_mentions']} output={args.output}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "verify-paper-claim-lint":
        report = verify_paper_claim_lint_report(args.report, output_path=args.output, root=args.root)
        print(
            "paper claim lint verified: "
            f"passed={report['passed']} files={report['summary']['files_verified']}/{report['summary']['files_total']} "
            f"issues={report['summary']['issues']} warnings={report['summary']['warnings']} report={args.report}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "audit-artifact-bundle":
        artifacts = {name: Path(path) for name, path in DEFAULT_BENCHMARK_RELEASE_ARTIFACTS.items()}
        for item in args.artifact:
            if "=" not in item:
                raise SystemExit(f"--artifact must be name=path, got: {item}")
            name, path = item.split("=", 1)
            artifacts[name] = Path(path)
        report = audit_artifact_bundle(artifacts, output_path=args.output, root=args.root)
        print(
            "artifact bundle audited: "
            f"passed={report['passed']} artifacts={report['summary']['artifacts_present']}/{report['summary']['artifacts_total']} "
            f"issues={report['summary']['issues']} warnings={report['summary']['warnings']} output={args.output}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "verify-artifact-bundle":
        report = verify_artifact_bundle_manifest(args.manifest, output_path=args.output)
        print(
            "artifact bundle verified: "
            f"passed={report['passed']} artifacts={report['summary']['artifacts_verified']}/{report['summary']['artifacts_total']} "
            f"issues={report['summary']['issues']} warnings={report['summary']['warnings']} manifest={args.manifest}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "benchmark-release-gate-report":
        reports = {name: Path(path) for name, path in DEFAULT_GATE_REPORTS.items()}
        for item in args.report:
            if "=" not in item:
                raise SystemExit(f"--report must be name=path, got: {item}")
            name, path = item.split("=", 1)
            reports[name] = Path(path)
        for index, path in enumerate(args.workflow_manifest_preflight):
            reports[f"workflow_manifest_preflight_{index}"] = Path(path)
        for index, path in enumerate(args.workflow_manifest_preflight_batch):
            reports[f"workflow_manifest_preflight_batch_{index}"] = Path(path)
        report = build_benchmark_release_gate_report(reports, output_path=args.output, root=args.root)
        print(
            "benchmark release gate report: "
            f"passed={report['passed']} reports={report['summary']['reports_present']}/{report['summary']['reports_total']} "
            f"issues={report['summary']['issues']} warnings={report['summary']['warnings']} output={args.output}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "audit-domain-expansion-readiness":
        reports = {name: Path(path) for name, path in DEFAULT_DOMAIN_EXPANSION_REPORTS.items()}
        for item in args.report:
            if "=" not in item:
                raise SystemExit(f"--report must be name=path, got: {item}")
            name, path = item.split("=", 1)
            reports[name] = Path(path)
        report = build_domain_expansion_readiness_report(
            reports,
            output_path=args.output,
            root=args.root,
            require_multi_domain=args.require_multi_domain,
            workflow_manifest_preflight_reports=args.workflow_manifest_preflight,
            workflow_manifest_preflight_batch_reports=args.workflow_manifest_preflight_batch,
        )
        print(
            "domain expansion readiness audited: "
            f"passed={report['passed']} ready_domains={len(report['summary']['release_ready_domains'])} "
            f"multi_domain_ready={report['summary']['multi_domain_release_ready']} "
            f"issues={report['summary']['issues']} warnings={report['summary']['warnings']} output={args.output}"
        )
        if not report["passed"]:
            raise SystemExit(1)
    elif args.command == "verify-domain-expansion-readiness":
        report = verify_domain_expansion_readiness_report(args.report, output_path=args.output, root=args.root)
        print(
            "domain expansion readiness verified: "
            f"passed={report['passed']} inputs={report['summary']['inputs_verified']}/{report['summary']['inputs_total']} "
            f"issues={report['summary']['issues']} warnings={report['summary']['warnings']} report={args.report}"
        )
        if not report["passed"]:
            raise SystemExit(1)
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
    elif args.command == "readiness-report":
        report = build_readiness_report(
            args.generated_dir,
            output_path=args.output,
            baseline_batch_dir=args.baseline_batch_dir,
            annotation_release_dir=args.annotation_release_dir,
            prompt_export_dir=args.prompt_export_dir,
            rewrite_job_dir=args.rewrite_job_dir,
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
            taxonomy_coverage_audit_path=args.taxonomy_coverage_audit,
            claim_boundary_audit_path=args.claim_boundary_audit,
            claim_lint_path=args.claim_lint,
            artifact_bundle_manifest_path=args.artifact_bundle_manifest,
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


if __name__ == "__main__":
    main()
