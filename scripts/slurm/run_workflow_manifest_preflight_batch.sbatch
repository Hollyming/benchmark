#!/usr/bin/env bash
#SBATCH --job-name=longuserpolicy-workflow-preflight
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

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
export ROOT CONDA_ENV OUTPUT_DIR REPORT VERIFY_OUTPUT MANIFESTS BASELINES TOP_K HARDEN_PROBE_QUERIES NO_REDACT

cd "${ROOT}"
bash scripts/run_workflow_manifest_preflight_batch.sh
