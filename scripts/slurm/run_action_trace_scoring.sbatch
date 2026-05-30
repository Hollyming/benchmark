#!/usr/bin/env bash
#SBATCH --job-name=longuserpolicy-trace-score
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
PROJECT_DIR="${PROJECT_DIR:-${ROOT}/examples/generated/projects/project_gharchive_001}"
TRACES="${TRACES:-${ROOT}/examples/action_traces/gharchive_trace_examples.jsonl}"
OUTPUT_PATH="${OUTPUT_PATH:-${ROOT}/examples/generated/evaluation_harness/gharchive_action_trace_report.json}"

cd "${ROOT}"
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate "${CONDA_ENV:-benchmark}"

python -m ultra_long_benchmark.cli score-action-traces "${PROJECT_DIR}" "${TRACES}" --output "${OUTPUT_PATH}"
