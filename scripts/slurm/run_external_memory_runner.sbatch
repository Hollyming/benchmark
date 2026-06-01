#!/usr/bin/env bash
#SBATCH --job-name=longuserpolicy-memory-runner
#SBATCH --partition=RTX4090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

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
export ROOT CONDA_ENV RUNNER SYSTEM_NAME INPUT_DIR PREDICTIONS REPORT CONFIG ALLOW_EXTERNAL_RUNNER ALLOW_PARTIAL

cd "${ROOT}"
bash scripts/run_external_memory_runner.sh
