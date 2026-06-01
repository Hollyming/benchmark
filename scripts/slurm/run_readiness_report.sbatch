#!/usr/bin/env bash
#SBATCH --job-name=longuserpolicy-readiness
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
GENERATED_DIR="${GENERATED_DIR:-${ROOT}/examples/generated}"
OUTPUT="${OUTPUT:-${GENERATED_DIR}/readiness_report.json}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
PAPER_SCALE_PROFILE="${PAPER_SCALE_PROFILE:-paper}"
REQUIRE_PAPER_SCALE="${REQUIRE_PAPER_SCALE:-0}"
BASELINE_BATCH_DIR="${BASELINE_BATCH_DIR:-${GENERATED_DIR}/evaluation_harness/baseline_batch_after_claim_boundary}"
ANNOTATION_RELEASE_DIR="${ANNOTATION_RELEASE_DIR:-${GENERATED_DIR}/release_packaging/gharchive_formal_annotation_pack}"
PROMPT_EXPORT_DIR="${PROMPT_EXPORT_DIR:-${GENERATED_DIR}/annotation_packs/gharchive_formal_prompt_exports}"
PUBLIC_DATA_DISCOVERY="${PUBLIC_DATA_DISCOVERY:-${GENERATED_DIR}/public_data_discovery_report.json}"
WORKFLOW_SOURCE_AUDIT="${WORKFLOW_SOURCE_AUDIT:-${GENERATED_DIR}/workflow_data_source_audit.json}"
BATCH_REWRITE_VALIDATION="${BATCH_REWRITE_VALIDATION:-${GENERATED_DIR}/annotation_packs/gharchive_formal_validation/batch_rewrite_validation_report.json}"
BATCH_REWRITE_PROJECTS="${BATCH_REWRITE_PROJECTS:-${GENERATED_DIR}/projects/gharchive_formal_batch/batch_rewrite_project_report.json}"
REWRITE_JOB_DIR="${REWRITE_JOB_DIR:-${GENERATED_DIR}/annotation_packs/gharchive_formal_rewrite_jobs}"
STAGED_SLICE_MANIFEST="${STAGED_SLICE_MANIFEST:-/home/jmzhang/Workspace/data/gharchive/longuserpolicy_2024_01_release_slice_manifest.json}"
PROJECT_RELEASE_DIR="${PROJECT_RELEASE_DIR:-${GENERATED_DIR}/release_packaging/gharchive_formal_project_benchmark}"
PROJECT_SUBMISSION_INPUT_DIR="${PROJECT_SUBMISSION_INPUT_DIR:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_submission_inputs_hardened}"
PROJECT_RELEASE_BASELINE="${PROJECT_RELEASE_BASELINE:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_project_release_baselines.json}"
PROJECT_RELEASE_PREDICTION="${PROJECT_RELEASE_PREDICTION:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_memory_profile_stub_hardened_score.json}"
PAPER_TABLE_DIR="${PAPER_TABLE_DIR:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_paper_tables}"
GHARCHIVE_STAGE_PLAN="${GHARCHIVE_STAGE_PLAN:-${GENERATED_DIR}/gharchive_stage_plan.json}"
SCALE_SUMMARY="${SCALE_SUMMARY:-${GENERATED_DIR}/gharchive_formal_scale_summary.json}"
WINDOW_REPORT="${WINDOW_REPORT:-${GENERATED_DIR}/gharchive_window_report.json}"
REWRITE_HUMAN_AUDIT="${REWRITE_HUMAN_AUDIT:-${GENERATED_DIR}/annotation_packs/gharchive_formal_human_audit/audit_validation_report.json}"
PROBE_LEAKAGE_AUDIT="${PROBE_LEAKAGE_AUDIT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_submission_inputs_hardened_probe_leakage_audit.json}"
TAXONOMY_COVERAGE_AUDIT="${TAXONOMY_COVERAGE_AUDIT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_taxonomy_coverage_audit.json}"
CLAIM_BOUNDARY_AUDIT="${CLAIM_BOUNDARY_AUDIT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_claim_boundary_audit.json}"
CLAIM_LINT="${CLAIM_LINT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_claim_lint.json}"
ARTIFACT_BUNDLE_MANIFEST="${ARTIFACT_BUNDLE_MANIFEST:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_artifact_bundle_manifest.json}"
export ROOT GENERATED_DIR OUTPUT CONDA_ENV PAPER_SCALE_PROFILE REQUIRE_PAPER_SCALE BASELINE_BATCH_DIR ANNOTATION_RELEASE_DIR PROMPT_EXPORT_DIR PUBLIC_DATA_DISCOVERY WORKFLOW_SOURCE_AUDIT BATCH_REWRITE_VALIDATION BATCH_REWRITE_PROJECTS REWRITE_JOB_DIR STAGED_SLICE_MANIFEST PROJECT_RELEASE_DIR PROJECT_SUBMISSION_INPUT_DIR PROJECT_RELEASE_BASELINE PROJECT_RELEASE_PREDICTION PAPER_TABLE_DIR GHARCHIVE_STAGE_PLAN SCALE_SUMMARY WINDOW_REPORT REWRITE_HUMAN_AUDIT PROBE_LEAKAGE_AUDIT TAXONOMY_COVERAGE_AUDIT CLAIM_BOUNDARY_AUDIT CLAIM_LINT ARTIFACT_BUNDLE_MANIFEST

cd "${ROOT}"
bash scripts/run_readiness_report.sh
