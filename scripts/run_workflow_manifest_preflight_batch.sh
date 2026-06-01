#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
OUTPUT_DIR="${OUTPUT_DIR:-${ROOT}/examples/generated/workflow_manifest_preflight_batch}"
REPORT="${REPORT:-${OUTPUT_DIR}/workflow_manifest_preflight_batch_report.json}"
VERIFY_OUTPUT="${VERIFY_OUTPUT:-${OUTPUT_DIR}/workflow_manifest_preflight_batch_verification.json}"
MANIFESTS="${MANIFESTS:-}"
BASELINES="${BASELINES:-raw_rag oracle_policy_graph}"
TOP_K="${TOP_K:-5}"
HARDEN_PROBE_QUERIES="${HARDEN_PROBE_QUERIES:-1}"
NO_REDACT="${NO_REDACT:-0}"

if [[ -z "${MANIFESTS}" ]]; then
  MANIFESTS="tests/fixtures/calendar_workflow_project_manifest.json tests/fixtures/docs_workflow_project_manifest.json tests/fixtures/chat_workflow_project_manifest.json tests/fixtures/browser_web_workflow_project_manifest.json"
fi

cd "${ROOT}"
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate "${CONDA_ENV}"

read -r -a manifest_args <<< "${MANIFESTS}"
read -r -a baseline_args <<< "${BASELINES}"

args=("${manifest_args[@]}" --output-dir "${OUTPUT_DIR}" --report "${REPORT}" --top-k "${TOP_K}")
for baseline in "${baseline_args[@]}"; do
  args+=(--baseline "${baseline}")
done
if [[ "${HARDEN_PROBE_QUERIES}" == "1" ]]; then
  args+=(--harden-probe-queries)
fi
if [[ "${NO_REDACT}" == "1" ]]; then
  args+=(--no-redact)
fi

python -m ultra_long_benchmark.cli preflight-workflow-manifest-release-batch "${args[@]}"
python -m ultra_long_benchmark.cli verify-workflow-manifest-preflight-batch "${REPORT}" --output "${VERIFY_OUTPUT}"
