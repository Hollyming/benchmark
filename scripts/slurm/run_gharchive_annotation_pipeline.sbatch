#!/usr/bin/env bash
#SBATCH --job-name=longuserpolicy-gharchive
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
INPUT="${INPUT:-${ROOT}/tests/fixtures/gharchive_multi_repo_sample.jsonl}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${ROOT}/examples/generated}"
WINDOW_DAYS="${WINDOW_DAYS:-7}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
PROMPT_DIR="${PROMPT_DIR:-${OUTPUT_ROOT}/annotation_packs/gharchive_prompt_exports}"
INTEGRITY_PATH="${INTEGRITY_PATH:-${OUTPUT_ROOT}/release_integrity_report.json}"
PAPER_SCALE_PATH="${PAPER_SCALE_PATH:-${OUTPUT_ROOT}/paper_scale_assessment.json}"
PAPER_SCALE_PROFILE="${PAPER_SCALE_PROFILE:-paper}"
STAGE_PLAN_PATH="${STAGE_PLAN_PATH:-${OUTPUT_ROOT}/gharchive_stage_plan.json}"
STAGE_PLAN_ALLOW_FAIL="${STAGE_PLAN_ALLOW_FAIL:-1}"
REQUIRE_READY_FOR_ANNOTATION="${REQUIRE_READY_FOR_ANNOTATION:-0}"
REWRITE_PROPOSALS="${REWRITE_PROPOSALS:-}"
REWRITE_VALIDATION_DIR="${REWRITE_VALIDATION_DIR:-${OUTPUT_ROOT}/annotation_packs/gharchive_rewrite_validation_batch}"
REWRITE_PROJECT_OUTPUT_DIR="${REWRITE_PROJECT_OUTPUT_DIR:-${OUTPUT_ROOT}/projects}"
REWRITE_PROJECT_PREFIX="${REWRITE_PROJECT_PREFIX:-project_gharchive_rewrite_batch}"
PROJECT_RELEASE_DIR="${PROJECT_RELEASE_DIR:-${OUTPUT_ROOT}/release_packaging/project_benchmark}"
PROJECT_RELEASE_INTEGRITY_PATH="${PROJECT_RELEASE_INTEGRITY_PATH:-${OUTPUT_ROOT}/project_release_integrity_report.json}"
export ROOT INPUT OUTPUT_ROOT WINDOW_DAYS CONDA_ENV PROMPT_DIR INTEGRITY_PATH PAPER_SCALE_PATH PAPER_SCALE_PROFILE STAGE_PLAN_PATH STAGE_PLAN_ALLOW_FAIL REQUIRE_READY_FOR_ANNOTATION REWRITE_PROPOSALS REWRITE_VALIDATION_DIR REWRITE_PROJECT_OUTPUT_DIR REWRITE_PROJECT_PREFIX PROJECT_RELEASE_DIR PROJECT_RELEASE_INTEGRITY_PATH

cd "${ROOT}"
bash scripts/run_gharchive_annotation_pipeline.sh
