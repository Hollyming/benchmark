#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
INPUT="${INPUT:?Set INPUT to a local GHArchive .jsonl, .json, or .json.gz slice}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${ROOT}/examples/generated}"
SLICE_OUTPUT="${SLICE_OUTPUT:-}"
SLICE_MANIFEST="${SLICE_MANIFEST:-}"
WINDOW_DAYS="${WINDOW_DAYS:-7}"
STAGE_PLAN_PROFILE="${STAGE_PLAN_PROFILE:-paper}"
STAGE_PLAN_ALLOW_FAIL="${STAGE_PLAN_ALLOW_FAIL:-1}"
REQUIRE_READY_FOR_ANNOTATION="${REQUIRE_READY_FOR_ANNOTATION:-0}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
MAX_RECORDS="${MAX_RECORDS:-}"
MAX_RECORDS_PER_REPO="${MAX_RECORDS_PER_REPO:-}"
REQUIRE_ELIGIBLE_REPO="${REQUIRE_ELIGIBLE_REPO:-0}"

cd "${ROOT}"
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate "${CONDA_ENV}"

if [[ -n "${SLICE_OUTPUT}" ]]; then
  build_args=("${INPUT}" "--output" "${SLICE_OUTPUT}")
  if [[ -n "${SLICE_MANIFEST}" ]]; then
    build_args+=("--manifest" "${SLICE_MANIFEST}")
  fi
  if [[ -n "${MAX_RECORDS}" ]]; then
    build_args+=("--max-records" "${MAX_RECORDS}")
  fi
  if [[ -n "${MAX_RECORDS_PER_REPO}" ]]; then
    build_args+=("--max-records-per-repo" "${MAX_RECORDS_PER_REPO}")
  fi
  if [[ "${REQUIRE_ELIGIBLE_REPO}" == "1" ]]; then
    build_args+=("--require-eligible-repo")
  fi
  python -m ultra_long_benchmark.cli gharchive-build-slice "${build_args[@]}"
  INPUT="${SLICE_OUTPUT}"
fi

python -m ultra_long_benchmark.cli gharchive-quality-report \
  --input "${INPUT}" \
  --output "${OUTPUT_ROOT}/gharchive_quality_report.json"
python -m ultra_long_benchmark.cli gharchive-window-report \
  --input "${INPUT}" \
  --window-days "${WINDOW_DAYS}" \
  --output "${OUTPUT_ROOT}/gharchive_window_report.json"
python -m ultra_long_benchmark.cli gharchive-mine-candidates \
  --input "${INPUT}" \
  --output "${OUTPUT_ROOT}/gharchive_candidate_report.json"

stage_plan_args=(
  --input "${INPUT}"
  --profile "${STAGE_PLAN_PROFILE}"
  --window-days "${WINDOW_DAYS}"
  --output "${OUTPUT_ROOT}/gharchive_stage_plan.json"
)
if [[ "${STAGE_PLAN_ALLOW_FAIL}" == "1" ]]; then
  stage_plan_args+=(--allow-fail)
fi
if [[ "${REQUIRE_READY_FOR_ANNOTATION}" == "1" ]]; then
  stage_plan_args+=(--require-ready-for-annotation)
fi
python -m ultra_long_benchmark.cli gharchive-stage-plan "${stage_plan_args[@]}"
if [[ -f "${OUTPUT_ROOT}/public_data_discovery_report.json" ]]; then
  audit_args=(
    --discovery-report "${OUTPUT_ROOT}/public_data_discovery_report.json"
    --gharchive-stage-plan "${OUTPUT_ROOT}/gharchive_stage_plan.json"
    --output "${OUTPUT_ROOT}/workflow_data_source_audit.json"
  )
  if [[ "${REQUIRE_READY_FOR_ANNOTATION}" == "1" ]]; then
    audit_args+=(--require-paper-ready)
  fi
  python -m ultra_long_benchmark.cli audit-workflow-data-sources "${audit_args[@]}"
fi
