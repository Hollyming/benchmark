#!/usr/bin/env bash
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

cd "${ROOT}"
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate "${CONDA_ENV}"

READINESS_ARGS=(
  --generated-dir "${GENERATED_DIR}"
  --output "${OUTPUT}"
  --paper-scale-profile "${PAPER_SCALE_PROFILE}"
)
append_arg() {
  local flag="$1"
  local value="$2"
  if [[ -n "${value}" ]]; then
    READINESS_ARGS+=("${flag}" "${value}")
  fi
}

append_arg --baseline-batch-dir "${BASELINE_BATCH_DIR}"
append_arg --annotation-release-dir "${ANNOTATION_RELEASE_DIR}"
append_arg --prompt-export-dir "${PROMPT_EXPORT_DIR}"
append_arg --rewrite-job-dir "${REWRITE_JOB_DIR}"
append_arg --staged-slice-manifest "${STAGED_SLICE_MANIFEST}"
append_arg --gharchive-stage-plan "${GHARCHIVE_STAGE_PLAN}"
append_arg --scale-summary "${SCALE_SUMMARY}"
append_arg --window-report "${WINDOW_REPORT}"
append_arg --public-data-discovery "${PUBLIC_DATA_DISCOVERY}"
append_arg --workflow-source-audit "${WORKFLOW_SOURCE_AUDIT}"
append_arg --batch-rewrite-validation "${BATCH_REWRITE_VALIDATION}"
append_arg --batch-rewrite-projects "${BATCH_REWRITE_PROJECTS}"
append_arg --project-release-dir "${PROJECT_RELEASE_DIR}"
append_arg --project-submission-input-dir "${PROJECT_SUBMISSION_INPUT_DIR}"
append_arg --project-release-baseline "${PROJECT_RELEASE_BASELINE}"
append_arg --project-release-prediction "${PROJECT_RELEASE_PREDICTION}"
append_arg --paper-table-dir "${PAPER_TABLE_DIR}"
append_arg --rewrite-human-audit "${REWRITE_HUMAN_AUDIT}"
append_arg --probe-leakage-audit "${PROBE_LEAKAGE_AUDIT}"
append_arg --taxonomy-coverage-audit "${TAXONOMY_COVERAGE_AUDIT}"
append_arg --claim-boundary-audit "${CLAIM_BOUNDARY_AUDIT}"
append_arg --claim-lint "${CLAIM_LINT}"
append_arg --artifact-bundle-manifest "${ARTIFACT_BUNDLE_MANIFEST}"

if [[ "${REQUIRE_PAPER_SCALE}" == "1" ]]; then
  READINESS_ARGS+=(--require-paper-scale)
fi

python -m ultra_long_benchmark.cli readiness-report "${READINESS_ARGS[@]}"
