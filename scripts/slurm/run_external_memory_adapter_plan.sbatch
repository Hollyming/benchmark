#!/usr/bin/env bash
#SBATCH --job-name=longuserpolicy-memory-plan
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
ADAPTER="${ADAPTER:?Set ADAPTER to mem0, a_mem, or graphiti}"
SYSTEM_NAME="${SYSTEM_NAME:-${ADAPTER}_submission_placeholder}"
INPUT_DIR="${INPUT_DIR:-${ROOT}/examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened}"
PREDICTIONS="${PREDICTIONS:-${ROOT}/examples/generated/evaluation_harness/gharchive_formal_${ADAPTER}_predictions.jsonl}"
REPORT="${REPORT:-${ROOT}/examples/generated/evaluation_harness/gharchive_formal_${ADAPTER}_plan.json}"
export ROOT CONDA_ENV ADAPTER SYSTEM_NAME INPUT_DIR PREDICTIONS REPORT

cd "${ROOT}"
bash scripts/run_external_memory_adapter_plan.sh
