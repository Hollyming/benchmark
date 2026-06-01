#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
GENERATED_DIR="${GENERATED_DIR:-${ROOT}/examples/generated}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
RUN_ARTIFACT_BUNDLE="${RUN_ARTIFACT_BUNDLE:-1}"
RUN_CLAIM_BOUNDARY="${RUN_CLAIM_BOUNDARY:-1}"
RUN_CLAIM_LINT="${RUN_CLAIM_LINT:-1}"
RUN_BASELINE_BATCH="${RUN_BASELINE_BATCH:-1}"
RUN_BASELINE_CONFIG_VALIDATION="${RUN_BASELINE_CONFIG_VALIDATION:-1}"
RUN_DOMAIN_EXPANSION_READINESS="${RUN_DOMAIN_EXPANSION_READINESS:-1}"
RUN_GATE_REPORT="${RUN_GATE_REPORT:-1}"
WORKFLOW_MANIFEST_PREFLIGHTS="${WORKFLOW_MANIFEST_PREFLIGHTS:-}"
WORKFLOW_MANIFEST_PREFLIGHT_BATCHES="${WORKFLOW_MANIFEST_PREFLIGHT_BATCHES:-}"

cd "${ROOT}"
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate "${CONDA_ENV}"

CLAIM_BOUNDARY_AUDIT_PATH="${CLAIM_BOUNDARY_AUDIT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_claim_boundary_audit.json}"
CLAIM_BOUNDARY_VERIFICATION="${CLAIM_BOUNDARY_VERIFICATION:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_claim_boundary_verification.json}"
CLAIM_LINT="${CLAIM_LINT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_claim_lint.json}"
READINESS_OUTPUT="${OUTPUT:-${GENERATED_DIR}/readiness_report_gharchive_formal.json}"
GATE_REPORT="${GATE_REPORT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_gate_report.json}"
TAXONOMY_COVERAGE_AUDIT_PATH="${TAXONOMY_COVERAGE_AUDIT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_taxonomy_coverage_audit.json}"
WORKFLOW_SOURCE_AUDIT_PATH="${WORKFLOW_SOURCE_AUDIT:-${GENERATED_DIR}/workflow_data_source_audit.json}"
PROBE_LEAKAGE_AUDIT_PATH="${PROBE_LEAKAGE_AUDIT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_submission_inputs_hardened_probe_leakage_audit.json}"
REWRITE_HUMAN_AUDIT_PATH="${REWRITE_HUMAN_AUDIT:-${GENERATED_DIR}/annotation_packs/gharchive_formal_human_audit/audit_validation_report.json}"
BASELINE_BATCH_DIR_PATH="${BASELINE_BATCH_DIR:-${GENERATED_DIR}/evaluation_harness/baseline_batch_after_claim_boundary}"
BASELINE_BATCH_REPORT="${BASELINE_BATCH_REPORT:-${BASELINE_BATCH_DIR_PATH}/baseline_batch_report.json}"
BASELINE_BATCH_VERIFICATION="${BASELINE_BATCH_VERIFICATION:-${BASELINE_BATCH_DIR_PATH}/baseline_batch_verification.json}"
BASELINE_CONFIG_DIR="${BASELINE_CONFIG_DIR:-${ROOT}/configs/baselines}"
BASELINE_CONFIG_VALIDATION="${BASELINE_CONFIG_VALIDATION:-${GENERATED_DIR}/evaluation_harness/baseline_config_validation_after_artifact_bundle.json}"
EXTERNAL_RUNNER_REPORT_PATH="${EXTERNAL_RUNNER_REPORT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_echo_policy_runner_report.json}"
ARTIFACT_BUNDLE_MANIFEST_PATH="${ARTIFACT_BUNDLE_MANIFEST:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_artifact_bundle_manifest.json}"
ARTIFACT_BUNDLE_VERIFICATION_PATH="${ARTIFACT_BUNDLE_VERIFICATION:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_artifact_bundle_verification.json}"
DOMAIN_EXPANSION_READINESS="${DOMAIN_EXPANSION_READINESS:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_domain_expansion_readiness.json}"

run_claim_boundary() {
  python -m ultra_long_benchmark.cli audit-paper-claim-boundaries \
    --output "${CLAIM_BOUNDARY_AUDIT_PATH}" \
    --readiness-report "${READINESS_OUTPUT}" \
    --taxonomy-coverage "${TAXONOMY_COVERAGE_AUDIT_PATH}" \
    --workflow-source-audit "${WORKFLOW_SOURCE_AUDIT_PATH}" \
    --hardened-probe-leakage-audit "${PROBE_LEAKAGE_AUDIT_PATH}" \
    --human-audit-report "${REWRITE_HUMAN_AUDIT_PATH}" \
    --baseline-batch-report "${BASELINE_BATCH_REPORT}" \
    --external-runner-report "${EXTERNAL_RUNNER_REPORT_PATH}"
  python -m ultra_long_benchmark.cli verify-paper-claim-boundaries "${CLAIM_BOUNDARY_AUDIT_PATH}" \
    --output "${CLAIM_BOUNDARY_VERIFICATION}"
}

run_claim_lint() {
  python -m ultra_long_benchmark.cli lint-paper-claims \
    --output "${CLAIM_LINT}" \
    --root "${ROOT}"
}

run_baseline_batch() {
  ROOT="${ROOT}" \
  CONFIG_DIR="${BASELINE_CONFIG_DIR}" \
  OUTPUT_DIR="${BASELINE_BATCH_DIR_PATH}" \
  CONDA_ENV="${CONDA_ENV}" \
  DRY_RUN_EXTERNAL="${BASELINE_BATCH_DRY_RUN_EXTERNAL:-1}" \
  ALLOW_LLM_API="${BASELINE_BATCH_ALLOW_LLM_API:-0}" \
  ALLOW_EXTERNAL_RUNNER="${BASELINE_BATCH_ALLOW_EXTERNAL_RUNNER:-0}" \
  VERIFY="${BASELINE_BATCH_VERIFY:-1}" \
  VERIFY_OUTPUT="${BASELINE_BATCH_VERIFICATION}" \
  bash "${ROOT}/scripts/run_baseline_config_batch.sh"
}

run_artifact_bundle() {
  ROOT="${ROOT}" \
  GENERATED_DIR="${GENERATED_DIR}" \
  CONDA_ENV="${CONDA_ENV}" \
  OUTPUT="${ARTIFACT_BUNDLE_MANIFEST_PATH}" \
  VERIFY_OUTPUT="${ARTIFACT_BUNDLE_VERIFICATION_PATH}" \
  CLAIM_BOUNDARY_AUDIT="${CLAIM_BOUNDARY_AUDIT_PATH}" \
  CLAIM_BOUNDARY_VERIFICATION="${CLAIM_BOUNDARY_VERIFICATION}" \
  CLAIM_LINT="${CLAIM_LINT}" \
  TAXONOMY_COVERAGE_AUDIT="${TAXONOMY_COVERAGE_AUDIT_PATH}" \
  PUBLIC_DATA_DISCOVERY="${PUBLIC_DATA_DISCOVERY:-${GENERATED_DIR}/public_data_discovery_report.json}" \
  WORKFLOW_SOURCE_AUDIT="${WORKFLOW_SOURCE_AUDIT_PATH}" \
  GHARCHIVE_STAGE_PLAN="${GHARCHIVE_STAGE_PLAN:-${GENERATED_DIR}/gharchive_stage_plan.json}" \
  GHARCHIVE_WINDOW_REPORT="${WINDOW_REPORT:-${GENERATED_DIR}/gharchive_window_report.json}" \
  GHARCHIVE_SCALE_SUMMARY="${SCALE_SUMMARY:-${GENERATED_DIR}/gharchive_formal_scale_summary.json}" \
  PROBE_LEAKAGE_AUDIT="${PROBE_LEAKAGE_AUDIT_PATH}" \
  BASELINE_BATCH_DIR="${BASELINE_BATCH_DIR_PATH}" \
  BASELINE_BATCH_REPORT="${BASELINE_BATCH_REPORT}" \
  BASELINE_BATCH_VERIFICATION="${BASELINE_BATCH_VERIFICATION}" \
  BASELINE_CONFIG_VALIDATION="${BASELINE_CONFIG_VALIDATION}" \
  EXTERNAL_RUNNER_REPORT="${EXTERNAL_RUNNER_REPORT_PATH}" \
  bash "${ROOT}/scripts/run_artifact_bundle_audit.sh"
}

run_baseline_config_validation() {
  python -m ultra_long_benchmark.cli validate-baseline-config configs/baselines \
    --output "${BASELINE_CONFIG_VALIDATION}"
}

run_domain_expansion_readiness() {
  local preflight_args=()
  if [[ -n "${WORKFLOW_MANIFEST_PREFLIGHTS}" ]]; then
    read -r -a preflight_paths <<< "${WORKFLOW_MANIFEST_PREFLIGHTS}"
    for preflight_path in "${preflight_paths[@]}"; do
      preflight_args+=(--workflow-manifest-preflight "${preflight_path}")
    done
  fi
  if [[ -n "${WORKFLOW_MANIFEST_PREFLIGHT_BATCHES}" ]]; then
    read -r -a preflight_batch_paths <<< "${WORKFLOW_MANIFEST_PREFLIGHT_BATCHES}"
    for preflight_batch_path in "${preflight_batch_paths[@]}"; do
      preflight_args+=(--workflow-manifest-preflight-batch "${preflight_batch_path}")
    done
  fi
  python -m ultra_long_benchmark.cli audit-domain-expansion-readiness \
    --output "${DOMAIN_EXPANSION_READINESS}" \
    --root "${ROOT}" \
    --report "readiness_report=${READINESS_OUTPUT}" \
    --report "taxonomy_coverage_audit=${TAXONOMY_COVERAGE_AUDIT_PATH}" \
    --report "workflow_source_audit=${WORKFLOW_SOURCE_AUDIT_PATH}" \
    --report "public_data_discovery=${PUBLIC_DATA_DISCOVERY:-${GENERATED_DIR}/public_data_discovery_report.json}" \
    --report "claim_boundary_audit=${CLAIM_BOUNDARY_AUDIT_PATH}" \
    "${preflight_args[@]}"
}

run_readiness() {
  OUTPUT="${READINESS_OUTPUT}" \
  CONDA_ENV="${CONDA_ENV}" \
  PAPER_SCALE_PROFILE="${PAPER_SCALE_PROFILE:-paper}" \
  REQUIRE_PAPER_SCALE="${REQUIRE_PAPER_SCALE:-1}" \
  BASELINE_BATCH_DIR="${BASELINE_BATCH_DIR_PATH}" \
  ANNOTATION_RELEASE_DIR="${ANNOTATION_RELEASE_DIR:-${GENERATED_DIR}/release_packaging/gharchive_formal_annotation_pack}" \
  PROMPT_EXPORT_DIR="${PROMPT_EXPORT_DIR:-${GENERATED_DIR}/annotation_packs/gharchive_formal_prompt_exports}" \
  PUBLIC_DATA_DISCOVERY="${PUBLIC_DATA_DISCOVERY:-${GENERATED_DIR}/public_data_discovery_report.json}" \
  WORKFLOW_SOURCE_AUDIT="${WORKFLOW_SOURCE_AUDIT:-${GENERATED_DIR}/workflow_data_source_audit.json}" \
  BATCH_REWRITE_VALIDATION="${BATCH_REWRITE_VALIDATION:-${GENERATED_DIR}/annotation_packs/gharchive_formal_validation/batch_rewrite_validation_report.json}" \
  BATCH_REWRITE_PROJECTS="${BATCH_REWRITE_PROJECTS:-${GENERATED_DIR}/projects/gharchive_formal_batch/batch_rewrite_project_report.json}" \
  REWRITE_JOB_DIR="${REWRITE_JOB_DIR:-${GENERATED_DIR}/annotation_packs/gharchive_formal_rewrite_jobs}" \
  STAGED_SLICE_MANIFEST="${STAGED_SLICE_MANIFEST:-/home/jmzhang/Workspace/data/gharchive/longuserpolicy_2024_01_release_slice_manifest.json}" \
  PROJECT_RELEASE_DIR="${PROJECT_RELEASE_DIR:-${GENERATED_DIR}/release_packaging/gharchive_formal_project_benchmark}" \
  PROJECT_SUBMISSION_INPUT_DIR="${PROJECT_SUBMISSION_INPUT_DIR:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_submission_inputs_hardened}" \
  PROJECT_RELEASE_BASELINE="${PROJECT_RELEASE_BASELINE:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_project_release_baselines.json}" \
  PROJECT_RELEASE_PREDICTION="${PROJECT_RELEASE_PREDICTION:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_memory_profile_stub_hardened_score.json}" \
  PAPER_TABLE_DIR="${PAPER_TABLE_DIR:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_paper_tables}" \
  GHARCHIVE_STAGE_PLAN="${GHARCHIVE_STAGE_PLAN:-${GENERATED_DIR}/gharchive_stage_plan.json}" \
  SCALE_SUMMARY="${SCALE_SUMMARY:-${GENERATED_DIR}/gharchive_formal_scale_summary.json}" \
  WINDOW_REPORT="${WINDOW_REPORT:-${GENERATED_DIR}/gharchive_window_report.json}" \
  REWRITE_HUMAN_AUDIT="${REWRITE_HUMAN_AUDIT_PATH}" \
  PROBE_LEAKAGE_AUDIT="${PROBE_LEAKAGE_AUDIT_PATH}" \
  TAXONOMY_COVERAGE_AUDIT="${TAXONOMY_COVERAGE_AUDIT_PATH}" \
  CLAIM_BOUNDARY_AUDIT="${CLAIM_BOUNDARY_AUDIT_PATH}" \
  CLAIM_LINT="${CLAIM_LINT}" \
  ARTIFACT_BUNDLE_MANIFEST="${ARTIFACT_BUNDLE_MANIFEST_PATH}" \
  bash "${ROOT}/scripts/run_readiness_report.sh"
}

if [[ "${RUN_BASELINE_BATCH}" == "1" ]]; then
  run_baseline_batch
fi

if [[ "${RUN_BASELINE_CONFIG_VALIDATION}" == "1" ]]; then
  run_baseline_config_validation
fi

if [[ "${RUN_CLAIM_BOUNDARY}" == "1" ]]; then
  run_claim_boundary
fi
if [[ "${RUN_CLAIM_LINT}" == "1" ]]; then
  run_claim_lint
fi

if [[ "${RUN_ARTIFACT_BUNDLE}" == "1" ]]; then
  run_artifact_bundle
fi

run_readiness

if [[ "${RUN_CLAIM_BOUNDARY}" == "1" ]]; then
  run_claim_boundary
fi
if [[ "${RUN_CLAIM_LINT}" == "1" ]]; then
  run_claim_lint
fi
if [[ "${RUN_ARTIFACT_BUNDLE}" == "1" ]]; then
  run_artifact_bundle
fi

if [[ "${RUN_DOMAIN_EXPANSION_READINESS}" == "1" ]]; then
  run_domain_expansion_readiness
fi

run_readiness

if [[ "${RUN_DOMAIN_EXPANSION_READINESS}" == "1" ]]; then
  run_domain_expansion_readiness
fi

if [[ "${RUN_GATE_REPORT}" == "1" ]]; then
  gate_preflight_args=()
  if [[ -n "${WORKFLOW_MANIFEST_PREFLIGHTS}" ]]; then
    read -r -a gate_preflight_paths <<< "${WORKFLOW_MANIFEST_PREFLIGHTS}"
    for preflight_path in "${gate_preflight_paths[@]}"; do
      gate_preflight_args+=(--workflow-manifest-preflight "${preflight_path}")
    done
  fi
  if [[ -n "${WORKFLOW_MANIFEST_PREFLIGHT_BATCHES}" ]]; then
    read -r -a gate_preflight_batch_paths <<< "${WORKFLOW_MANIFEST_PREFLIGHT_BATCHES}"
    for preflight_batch_path in "${gate_preflight_batch_paths[@]}"; do
      gate_preflight_args+=(--workflow-manifest-preflight-batch "${preflight_batch_path}")
    done
  fi
  python -m ultra_long_benchmark.cli benchmark-release-gate-report \
    --output "${GATE_REPORT}" \
    --root "${ROOT}" \
    --report "readiness_report=${READINESS_OUTPUT}" \
    --report "claim_boundary_audit=${CLAIM_BOUNDARY_AUDIT_PATH}" \
    --report "claim_boundary_verification=${CLAIM_BOUNDARY_VERIFICATION}" \
    --report "claim_lint=${CLAIM_LINT}" \
    --report "artifact_bundle_manifest=${ARTIFACT_BUNDLE_MANIFEST_PATH}" \
    --report "artifact_bundle_verification=${ARTIFACT_BUNDLE_VERIFICATION_PATH}" \
    --report "taxonomy_coverage_audit=${TAXONOMY_COVERAGE_AUDIT_PATH}" \
    --report "domain_expansion_readiness=${DOMAIN_EXPANSION_READINESS}" \
    --report "baseline_config_validation=${BASELINE_CONFIG_VALIDATION}" \
    "${gate_preflight_args[@]}"
fi
