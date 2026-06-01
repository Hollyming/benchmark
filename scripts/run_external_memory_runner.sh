#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
RUNNER="${RUNNER:?Set RUNNER to a module:object plugin target}"
SYSTEM_NAME="${SYSTEM_NAME:-external_memory_runner}"
INPUT_DIR="${INPUT_DIR:-${ROOT}/examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened}"
PREDICTIONS="${PREDICTIONS:-${ROOT}/examples/generated/evaluation_harness/external_memory_runner_predictions.jsonl}"
REPORT="${REPORT:-${ROOT}/examples/generated/evaluation_harness/external_memory_runner_report.json}"
CONFIG="${CONFIG:-}"
ALLOW_EXTERNAL_RUNNER="${ALLOW_EXTERNAL_RUNNER:-0}"
ALLOW_PARTIAL="${ALLOW_PARTIAL:-0}"

cd "${ROOT}"
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate "${CONDA_ENV}"

args=(
  "${INPUT_DIR}"
  --runner "${RUNNER}"
  --predictions "${PREDICTIONS}"
  --report "${REPORT}"
  --system-name "${SYSTEM_NAME}"
)
if [[ -n "${CONFIG}" ]]; then
  args+=(--config "${CONFIG}")
fi
if [[ "${ALLOW_EXTERNAL_RUNNER}" == "1" ]]; then
  args+=(--allow-external-runner)
fi
if [[ "${ALLOW_PARTIAL}" == "1" ]]; then
  args+=(--allow-partial)
fi

python -m ultra_long_benchmark.cli run-external-memory-submission-runner "${args[@]}"
