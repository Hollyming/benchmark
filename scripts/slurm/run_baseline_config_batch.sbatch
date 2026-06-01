#!/usr/bin/env bash
#SBATCH --job-name=longuserpolicy-baseline-batch
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

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
export ROOT CONFIG_DIR OUTPUT_DIR CONDA_ENV ALLOW_LLM_API ALLOW_EXTERNAL_RUNNER DRY_RUN_EXTERNAL VERIFY VERIFY_OUTPUT

cd "${ROOT}"
bash scripts/run_baseline_config_batch.sh
