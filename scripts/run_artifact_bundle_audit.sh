#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
GENERATED_DIR="${GENERATED_DIR:-${ROOT}/examples/generated}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
OUTPUT="${OUTPUT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_artifact_bundle_manifest.json}"
VERIFY_OUTPUT="${VERIFY_OUTPUT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_artifact_bundle_verification.json}"
VERIFY="${VERIFY:-1}"

PROJECT_RELEASE_DIR="${PROJECT_RELEASE_DIR:-${GENERATED_DIR}/release_packaging/gharchive_formal_project_benchmark}"
PROJECT_SUBMISSION_INPUT_DIR="${PROJECT_SUBMISSION_INPUT_DIR:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_submission_inputs_hardened}"
PAPER_TABLE_DIR="${PAPER_TABLE_DIR:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_paper_tables}"
CLAIM_BOUNDARY_AUDIT="${CLAIM_BOUNDARY_AUDIT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_claim_boundary_audit.json}"
CLAIM_BOUNDARY_VERIFICATION="${CLAIM_BOUNDARY_VERIFICATION:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_claim_boundary_verification.json}"
CLAIM_LINT="${CLAIM_LINT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_claim_lint.json}"
TAXONOMY_COVERAGE_AUDIT="${TAXONOMY_COVERAGE_AUDIT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_taxonomy_coverage_audit.json}"
PUBLIC_DATA_DISCOVERY="${PUBLIC_DATA_DISCOVERY:-${GENERATED_DIR}/public_data_discovery_report.json}"
WORKFLOW_SOURCE_AUDIT="${WORKFLOW_SOURCE_AUDIT:-${GENERATED_DIR}/workflow_data_source_audit.json}"
GHARCHIVE_STAGE_PLAN="${GHARCHIVE_STAGE_PLAN:-${GENERATED_DIR}/gharchive_stage_plan.json}"
GHARCHIVE_WINDOW_REPORT="${GHARCHIVE_WINDOW_REPORT:-${GENERATED_DIR}/gharchive_window_report.json}"
GHARCHIVE_SCALE_SUMMARY="${GHARCHIVE_SCALE_SUMMARY:-${GENERATED_DIR}/gharchive_formal_scale_summary.json}"
PROBE_LEAKAGE_AUDIT="${PROBE_LEAKAGE_AUDIT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_submission_inputs_hardened_probe_leakage_audit.json}"
BASELINE_BATCH_DIR="${BASELINE_BATCH_DIR:-${GENERATED_DIR}/evaluation_harness/baseline_batch_after_claim_boundary}"
BASELINE_BATCH_REPORT="${BASELINE_BATCH_REPORT:-${BASELINE_BATCH_DIR}/baseline_batch_report.json}"
BASELINE_BATCH_VERIFICATION="${BASELINE_BATCH_VERIFICATION:-${BASELINE_BATCH_DIR}/baseline_batch_verification.json}"
BASELINE_CONFIG_VALIDATION="${BASELINE_CONFIG_VALIDATION:-${GENERATED_DIR}/evaluation_harness/baseline_config_validation_after_artifact_bundle.json}"
EXTERNAL_RUNNER_REPORT="${EXTERNAL_RUNNER_REPORT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_echo_policy_runner_report.json}"
EXTERNAL_RUNNER_VALIDATION="${EXTERNAL_RUNNER_VALIDATION:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_echo_policy_runner_validation_against_input.json}"
EXTERNAL_RUNNER_SUBMISSION_VALIDATION="${EXTERNAL_RUNNER_SUBMISSION_VALIDATION:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_echo_policy_runner_submission_validation.json}"
EXTERNAL_RUNNER_SCORE="${EXTERNAL_RUNNER_SCORE:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_echo_policy_runner_score.json}"

cd "${ROOT}"
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate "${CONDA_ENV}"

ARTIFACT_ARGS=(
  --artifact "project_release_dir=${PROJECT_RELEASE_DIR}"
  --artifact "hardened_submission_input_dir=${PROJECT_SUBMISSION_INPUT_DIR}"
  --artifact "paper_table_dir=${PAPER_TABLE_DIR}"
  --artifact "claim_boundary_audit=${CLAIM_BOUNDARY_AUDIT}"
  --artifact "claim_boundary_verification=${CLAIM_BOUNDARY_VERIFICATION}"
  --artifact "claim_lint=${CLAIM_LINT}"
  --artifact "taxonomy_coverage_audit=${TAXONOMY_COVERAGE_AUDIT}"
  --artifact "public_data_discovery=${PUBLIC_DATA_DISCOVERY}"
  --artifact "workflow_source_audit=${WORKFLOW_SOURCE_AUDIT}"
  --artifact "gharchive_stage_plan=${GHARCHIVE_STAGE_PLAN}"
  --artifact "gharchive_window_report=${GHARCHIVE_WINDOW_REPORT}"
  --artifact "gharchive_scale_summary=${GHARCHIVE_SCALE_SUMMARY}"
  --artifact "hardened_probe_leakage_audit=${PROBE_LEAKAGE_AUDIT}"
  --artifact "baseline_batch_report=${BASELINE_BATCH_REPORT}"
  --artifact "baseline_batch_verification=${BASELINE_BATCH_VERIFICATION}"
  --artifact "baseline_config_validation=${BASELINE_CONFIG_VALIDATION}"
  --artifact "external_runner_report=${EXTERNAL_RUNNER_REPORT}"
  --artifact "external_runner_validation=${EXTERNAL_RUNNER_VALIDATION}"
  --artifact "external_runner_submission_validation=${EXTERNAL_RUNNER_SUBMISSION_VALIDATION}"
  --artifact "external_runner_score=${EXTERNAL_RUNNER_SCORE}"
)

python -m ultra_long_benchmark.cli audit-artifact-bundle \
  --output "${OUTPUT}" \
  --root "${ROOT}" \
  "${ARTIFACT_ARGS[@]}"

if [[ "${VERIFY}" == "1" ]]; then
  python -m ultra_long_benchmark.cli verify-artifact-bundle "${OUTPUT}" \
    --output "${VERIFY_OUTPUT}"
fi
