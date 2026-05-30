#!/usr/bin/env bash
#SBATCH --job-name=longuserpolicy-baseline
#SBATCH --partition=RTX4090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
PROJECT_DIR="${PROJECT_DIR:-${ROOT}/examples/generated/projects/project_gharchive_001}"
OUTPUT_PATH="${OUTPUT_PATH:-${ROOT}/examples/generated/evaluation_harness/project_gharchive_baselines.json}"
TOP_K="${TOP_K:-3}"

cd "${ROOT}"
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate "${CONDA_ENV:-benchmark}"

python -m ultra_long_benchmark.cli evaluate-project "${PROJECT_DIR}" --output "${OUTPUT_PATH}" --top-k "${TOP_K}"
