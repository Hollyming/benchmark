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
OUTPUT_DIR="${OUTPUT_DIR:-${ROOT}/examples/generated/evaluation_harness/baseline_batch}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
ALLOW_LLM_API="${ALLOW_LLM_API:-0}"
DRY_RUN_EXTERNAL="${DRY_RUN_EXTERNAL:-1}"
export ROOT CONFIG_DIR OUTPUT_DIR CONDA_ENV ALLOW_LLM_API DRY_RUN_EXTERNAL

cd "${ROOT}"
bash scripts/run_baseline_config_batch.sh
