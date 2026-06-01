#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
ADAPTER="${ADAPTER:?Set ADAPTER to mem0, a_mem, or graphiti}"
SYSTEM_NAME="${SYSTEM_NAME:-${ADAPTER}_submission_placeholder}"
INPUT_DIR="${INPUT_DIR:-${ROOT}/examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened}"
PREDICTIONS="${PREDICTIONS:-${ROOT}/examples/generated/evaluation_harness/gharchive_formal_${ADAPTER}_predictions.jsonl}"
REPORT="${REPORT:-${ROOT}/examples/generated/evaluation_harness/gharchive_formal_${ADAPTER}_plan.json}"

cd "${ROOT}"
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate "${CONDA_ENV}"

python -m ultra_long_benchmark.cli plan-external-memory-submission-adapter \
  "${INPUT_DIR}" \
  --adapter "${ADAPTER}" \
  --predictions "${PREDICTIONS}" \
  --report "${REPORT}" \
  --system-name "${SYSTEM_NAME}"
