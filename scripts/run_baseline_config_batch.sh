#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
CONFIG_DIR="${CONFIG_DIR:-${ROOT}/configs/baselines}"
OUTPUT_DIR="${OUTPUT_DIR:-${ROOT}/examples/generated/evaluation_harness/baseline_batch_after_claim_boundary}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
ALLOW_LLM_API="${ALLOW_LLM_API:-0}"
ALLOW_EXTERNAL_RUNNER="${ALLOW_EXTERNAL_RUNNER:-0}"
DRY_RUN_EXTERNAL="${DRY_RUN_EXTERNAL:-1}"
VERIFY="${VERIFY:-1}"
VERIFY_OUTPUT="${VERIFY_OUTPUT:-${OUTPUT_DIR}/baseline_batch_verification.json}"

cd "${ROOT}"
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate "${CONDA_ENV}"

args=("${CONFIG_DIR}" "--output-dir" "${OUTPUT_DIR}")
if [[ "${DRY_RUN_EXTERNAL}" == "0" ]]; then
  args+=("--no-dry-run-external")
fi
if [[ "${ALLOW_LLM_API}" == "1" ]]; then
  args+=("--allow-llm-api")
fi
if [[ "${ALLOW_EXTERNAL_RUNNER}" == "1" ]]; then
  args+=("--allow-external-runner")
fi

python -m ultra_long_benchmark.cli run-baseline-config-dir "${args[@]}"

if [[ "${VERIFY}" == "1" ]]; then
  python -m ultra_long_benchmark.cli verify-baseline-batch \
    "${OUTPUT_DIR}/baseline_batch_report.json" \
    --output "${VERIFY_OUTPUT}"
fi
