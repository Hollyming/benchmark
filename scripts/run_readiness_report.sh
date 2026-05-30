#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
GENERATED_DIR="${GENERATED_DIR:-${ROOT}/examples/generated}"
OUTPUT="${OUTPUT:-${GENERATED_DIR}/readiness_report.json}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
PAPER_SCALE_PROFILE="${PAPER_SCALE_PROFILE:-paper}"
REQUIRE_PAPER_SCALE="${REQUIRE_PAPER_SCALE:-0}"
PUBLIC_DATA_DISCOVERY="${PUBLIC_DATA_DISCOVERY:-${GENERATED_DIR}/public_data_discovery_report.json}"
BATCH_REWRITE_VALIDATION="${BATCH_REWRITE_VALIDATION:-${GENERATED_DIR}/annotation_packs/gharchive_rewrite_validation_batch/batch_rewrite_validation_report.json}"
BATCH_REWRITE_PROJECTS="${BATCH_REWRITE_PROJECTS:-${GENERATED_DIR}/projects/batch_rewrite_project_report.json}"
REWRITE_JOB_DIR="${REWRITE_JOB_DIR:-${GENERATED_DIR}/annotation_packs/rewrite_jobs}"
PROJECT_RELEASE_DIR="${PROJECT_RELEASE_DIR:-${GENERATED_DIR}/release_packaging/project_benchmark}"
PROJECT_SUBMISSION_INPUT_DIR="${PROJECT_SUBMISSION_INPUT_DIR:-${GENERATED_DIR}/evaluation_harness/project_submission_inputs}"
PROJECT_RELEASE_BASELINE="${PROJECT_RELEASE_BASELINE:-${GENERATED_DIR}/evaluation_harness/project_release_baselines.json}"
PROJECT_RELEASE_PREDICTION="${PROJECT_RELEASE_PREDICTION:-${GENERATED_DIR}/evaluation_harness/project_release_prediction_report.json}"
PAPER_TABLE_DIR="${PAPER_TABLE_DIR:-${GENERATED_DIR}/evaluation_harness/paper_tables}"
GHARCHIVE_STAGE_PLAN="${GHARCHIVE_STAGE_PLAN:-${GENERATED_DIR}/gharchive_stage_plan.json}"

cd "${ROOT}"
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate "${CONDA_ENV}"

READINESS_ARGS=(
  --generated-dir "${GENERATED_DIR}"
  --output "${OUTPUT}"
  --paper-scale-profile "${PAPER_SCALE_PROFILE}"
  --gharchive-stage-plan "${GHARCHIVE_STAGE_PLAN}"
  --public-data-discovery "${PUBLIC_DATA_DISCOVERY}"
  --batch-rewrite-validation "${BATCH_REWRITE_VALIDATION}"
  --batch-rewrite-projects "${BATCH_REWRITE_PROJECTS}"
  --rewrite-job-dir "${REWRITE_JOB_DIR}"
  --project-release-dir "${PROJECT_RELEASE_DIR}"
  --project-submission-input-dir "${PROJECT_SUBMISSION_INPUT_DIR}"
  --project-release-baseline "${PROJECT_RELEASE_BASELINE}"
  --project-release-prediction "${PROJECT_RELEASE_PREDICTION}"
  --paper-table-dir "${PAPER_TABLE_DIR}"
)
if [[ "${REQUIRE_PAPER_SCALE}" == "1" ]]; then
  READINESS_ARGS+=(--require-paper-scale)
fi

python -m ultra_long_benchmark.cli readiness-report "${READINESS_ARGS[@]}"
