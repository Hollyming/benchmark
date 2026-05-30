#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
INPUT="${INPUT:-${ROOT}/tests/fixtures/gharchive_multi_repo_sample.jsonl}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${ROOT}/examples/generated}"
PACK_DIR="${PACK_DIR:-${OUTPUT_ROOT}/annotation_packs/gharchive_batch}"
RELEASE_DIR="${RELEASE_DIR:-${OUTPUT_ROOT}/release_packaging/gharchive_annotation_pack}"
PROMPT_DIR="${PROMPT_DIR:-${OUTPUT_ROOT}/annotation_packs/gharchive_prompt_exports}"
REWRITE_JOB_DIR="${REWRITE_JOB_DIR:-${OUTPUT_ROOT}/annotation_packs/rewrite_jobs}"
REWRITE_JOB_MAX_PROMPTS="${REWRITE_JOB_MAX_PROMPTS:-100}"
REWRITE_JOB_MAX_TOKENS="${REWRITE_JOB_MAX_TOKENS:-120000}"
REWRITE_PROPOSALS="${REWRITE_PROPOSALS:-}"
COLLECT_REWRITE_JOBS="${COLLECT_REWRITE_JOBS:-0}"
COLLECTED_REWRITE_PROPOSALS="${COLLECTED_REWRITE_PROPOSALS:-${REWRITE_JOB_DIR}/collected_rewrite_proposals.jsonl}"
REWRITE_JOB_COLLECTION_REPORT="${REWRITE_JOB_COLLECTION_REPORT:-${REWRITE_JOB_DIR}/rewrite_job_collection_report.json}"
REWRITE_VALIDATION_DIR="${REWRITE_VALIDATION_DIR:-${OUTPUT_ROOT}/annotation_packs/gharchive_rewrite_validation_batch}"
REWRITE_PROJECT_OUTPUT_DIR="${REWRITE_PROJECT_OUTPUT_DIR:-${OUTPUT_ROOT}/projects}"
REWRITE_PROJECT_PREFIX="${REWRITE_PROJECT_PREFIX:-project_gharchive_rewrite_batch}"
PROJECT_RELEASE_DIR="${PROJECT_RELEASE_DIR:-${OUTPUT_ROOT}/release_packaging/project_benchmark}"
PROJECT_RELEASE_INTEGRITY_PATH="${PROJECT_RELEASE_INTEGRITY_PATH:-${OUTPUT_ROOT}/project_release_integrity_report.json}"
SUMMARY_PATH="${SUMMARY_PATH:-${OUTPUT_ROOT}/gharchive_scale_summary.json}"
INTEGRITY_PATH="${INTEGRITY_PATH:-${OUTPUT_ROOT}/release_integrity_report.json}"
PAPER_SCALE_PATH="${PAPER_SCALE_PATH:-${OUTPUT_ROOT}/paper_scale_assessment.json}"
PAPER_SCALE_PROFILE="${PAPER_SCALE_PROFILE:-paper}"
WINDOW_DAYS="${WINDOW_DAYS:-7}"
STAGE_PLAN_PATH="${STAGE_PLAN_PATH:-${OUTPUT_ROOT}/gharchive_stage_plan.json}"
STAGE_PLAN_ALLOW_FAIL="${STAGE_PLAN_ALLOW_FAIL:-1}"
REQUIRE_READY_FOR_ANNOTATION="${REQUIRE_READY_FOR_ANNOTATION:-0}"
CONDA_ENV="${CONDA_ENV:-benchmark}"

cd "${ROOT}"
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate "${CONDA_ENV}"

python -m ultra_long_benchmark.cli gharchive-quality-report \
  --input "${INPUT}" \
  --output "${OUTPUT_ROOT}/gharchive_quality_report.json"
python -m ultra_long_benchmark.cli gharchive-window-report \
  --input "${INPUT}" \
  --window-days "${WINDOW_DAYS}" \
  --output "${OUTPUT_ROOT}/gharchive_window_report.json"
stage_plan_args=(
  --input "${INPUT}"
  --profile "${PAPER_SCALE_PROFILE}"
  --window-days "${WINDOW_DAYS}"
  --output "${STAGE_PLAN_PATH}"
)
if [[ "${STAGE_PLAN_ALLOW_FAIL}" == "1" ]]; then
  stage_plan_args+=(--allow-fail)
fi
if [[ "${REQUIRE_READY_FOR_ANNOTATION}" == "1" ]]; then
  stage_plan_args+=(--require-ready-for-annotation)
fi
python -m ultra_long_benchmark.cli gharchive-stage-plan "${stage_plan_args[@]}"
python -m ultra_long_benchmark.cli gharchive-annotation-pack-batch \
  --input "${INPUT}" \
  --output-dir "${PACK_DIR}"
python -m ultra_long_benchmark.cli export-annotation-pack-release \
  "${PACK_DIR}" \
  --output-dir "${RELEASE_DIR}"
python -m ultra_long_benchmark.cli gharchive-scale-summary \
  "${PACK_DIR}" \
  --release-dir "${RELEASE_DIR}" \
  --output "${SUMMARY_PATH}"
python -m ultra_long_benchmark.cli export-policy-rewrite-prompts-batch \
  "${PACK_DIR}" \
  --output-dir "${PROMPT_DIR}"
python -m ultra_long_benchmark.cli package-policy-rewrite-jobs \
  "${PROMPT_DIR}" \
  --output-dir "${REWRITE_JOB_DIR}" \
  --max-prompts-per-job "${REWRITE_JOB_MAX_PROMPTS}" \
  --max-estimated-tokens-per-job "${REWRITE_JOB_MAX_TOKENS}"
if [[ "${COLLECT_REWRITE_JOBS}" == "1" ]]; then
  python -m ultra_long_benchmark.cli collect-policy-rewrite-job-outputs \
    "${REWRITE_JOB_DIR}" \
    --output "${COLLECTED_REWRITE_PROPOSALS}" \
    --report "${REWRITE_JOB_COLLECTION_REPORT}"
  REWRITE_PROPOSALS="${COLLECTED_REWRITE_PROPOSALS}"
fi
if [[ -n "${REWRITE_PROPOSALS}" ]]; then
  python -m ultra_long_benchmark.cli validate-policy-rewrites-batch \
    "${PACK_DIR}" \
    "${REWRITE_PROPOSALS}" \
    --output-dir "${REWRITE_VALIDATION_DIR}"
  python -m ultra_long_benchmark.cli build-projects-from-rewrite-batch \
    "${REWRITE_VALIDATION_DIR}/batch_rewrite_validation_report.json" \
    --output-dir "${REWRITE_PROJECT_OUTPUT_DIR}" \
    --project-prefix "${REWRITE_PROJECT_PREFIX}"
  PROJECT_DIRS=("${REWRITE_PROJECT_OUTPUT_DIR}"/"${REWRITE_PROJECT_PREFIX}"_*)
  python -m ultra_long_benchmark.cli export-project-benchmark-release \
    "${PROJECT_DIRS[@]}" \
    --output-dir "${PROJECT_RELEASE_DIR}"
  python -m ultra_long_benchmark.cli verify-project-benchmark-release \
    "${PROJECT_RELEASE_DIR}" \
    --output "${PROJECT_RELEASE_INTEGRITY_PATH}"
fi
python -m ultra_long_benchmark.cli verify-release-integrity \
  "${RELEASE_DIR}" \
  --prompt-export-dir "${PROMPT_DIR}" \
  --output "${INTEGRITY_PATH}"
python -m ultra_long_benchmark.cli assess-paper-scale \
  "${RELEASE_DIR}" \
  --profile "${PAPER_SCALE_PROFILE}" \
  --scale-summary "${SUMMARY_PATH}" \
  --window-report "${OUTPUT_ROOT}/gharchive_window_report.json" \
  --release-integrity-report "${INTEGRITY_PATH}" \
  --output "${PAPER_SCALE_PATH}" \
  --allow-fail
