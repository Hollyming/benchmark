#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
CONFIG_DIR="${CONFIG_DIR:-${ROOT}/configs/baselines}"
OUTPUT_DIR="${OUTPUT_DIR:-${ROOT}/examples/generated/evaluation_harness/baseline_batch}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
ALLOW_LLM_API="${ALLOW_LLM_API:-0}"
DRY_RUN_EXTERNAL="${DRY_RUN_EXTERNAL:-1}"

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

python -m ultra_long_benchmark.cli run-baseline-config-dir "${args[@]}"
