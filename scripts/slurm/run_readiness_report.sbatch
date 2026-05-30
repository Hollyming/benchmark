#!/usr/bin/env bash
#SBATCH --job-name=longuserpolicy-readiness
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
GENERATED_DIR="${GENERATED_DIR:-${ROOT}/examples/generated}"
OUTPUT="${OUTPUT:-${GENERATED_DIR}/readiness_report.json}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
PAPER_SCALE_PROFILE="${PAPER_SCALE_PROFILE:-paper}"
REQUIRE_PAPER_SCALE="${REQUIRE_PAPER_SCALE:-0}"
PUBLIC_DATA_DISCOVERY="${PUBLIC_DATA_DISCOVERY:-${GENERATED_DIR}/public_data_discovery_report.json}"
BATCH_REWRITE_VALIDATION="${BATCH_REWRITE_VALIDATION:-${GENERATED_DIR}/annotation_packs/gharchive_rewrite_validation_batch/batch_rewrite_validation_report.json}"
BATCH_REWRITE_PROJECTS="${BATCH_REWRITE_PROJECTS:-${GENERATED_DIR}/projects/batch_rewrite_project_report.json}"
REWRITE_JOB_DIR="${REWRITE_JOB_DIR:-${GENERATED_DIR}/annotation_packs/rewrite_jobs}"
PROJECT_RELEASE_DIR="${PROJECT_RELEASE_DIR:-${GENERATED_DIR}/release_packaging/project_benchmark}"
PROJECT_SUBMISSION_INPUT_DIR="${PROJECT_SUBMISSION_INPUT_DIR:-${GENERATED_DIR}/evaluation_harness/project_submission_inputs}"
PROJECT_RELEASE_BASELINE="${PROJECT_RELEASE_BASELINE:-${GENERATED_DIR}/evaluation_harness/project_release_baselines.json}"
PROJECT_RELEASE_PREDICTION="${PROJECT_RELEASE_PREDICTION:-${GENERATED_DIR}/evaluation_harness/project_release_prediction_report.json}"
PAPER_TABLE_DIR="${PAPER_TABLE_DIR:-${GENERATED_DIR}/evaluation_harness/paper_tables}"
GHARCHIVE_STAGE_PLAN="${GHARCHIVE_STAGE_PLAN:-${GENERATED_DIR}/gharchive_stage_plan.json}"
export ROOT GENERATED_DIR OUTPUT CONDA_ENV PAPER_SCALE_PROFILE REQUIRE_PAPER_SCALE PUBLIC_DATA_DISCOVERY BATCH_REWRITE_VALIDATION BATCH_REWRITE_PROJECTS REWRITE_JOB_DIR PROJECT_RELEASE_DIR PROJECT_SUBMISSION_INPUT_DIR PROJECT_RELEASE_BASELINE PROJECT_RELEASE_PREDICTION PAPER_TABLE_DIR GHARCHIVE_STAGE_PLAN

cd "${ROOT}"
bash scripts/run_readiness_report.sh
