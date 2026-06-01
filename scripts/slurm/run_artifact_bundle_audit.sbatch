#!/usr/bin/env bash
#SBATCH --job-name=longuserpolicy-artifact-bundle
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=logs/slurm/%x-%j.out
#SBATCH --error=logs/slurm/%x-%j.err

set -euo pipefail

ROOT="${ROOT:-/home/jmzhang/Workspace/benchmark}"
GENERATED_DIR="${GENERATED_DIR:-${ROOT}/examples/generated}"
CONDA_ENV="${CONDA_ENV:-benchmark}"
OUTPUT="${OUTPUT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_artifact_bundle_manifest.json}"
VERIFY_OUTPUT="${VERIFY_OUTPUT:-${GENERATED_DIR}/evaluation_harness/gharchive_formal_artifact_bundle_verification.json}"
VERIFY="${VERIFY:-1}"
PUBLIC_DATA_DISCOVERY="${PUBLIC_DATA_DISCOVERY:-${GENERATED_DIR}/public_data_discovery_report.json}"
GHARCHIVE_STAGE_PLAN="${GHARCHIVE_STAGE_PLAN:-${GENERATED_DIR}/gharchive_stage_plan.json}"
GHARCHIVE_WINDOW_REPORT="${GHARCHIVE_WINDOW_REPORT:-${GENERATED_DIR}/gharchive_window_report.json}"
GHARCHIVE_SCALE_SUMMARY="${GHARCHIVE_SCALE_SUMMARY:-${GENERATED_DIR}/gharchive_formal_scale_summary.json}"
BASELINE_CONFIG_VALIDATION="${BASELINE_CONFIG_VALIDATION:-${GENERATED_DIR}/evaluation_harness/baseline_config_validation_after_artifact_bundle.json}"
export ROOT GENERATED_DIR CONDA_ENV OUTPUT VERIFY_OUTPUT VERIFY PUBLIC_DATA_DISCOVERY GHARCHIVE_STAGE_PLAN GHARCHIVE_WINDOW_REPORT GHARCHIVE_SCALE_SUMMARY BASELINE_CONFIG_VALIDATION

cd "${ROOT}"
bash scripts/run_artifact_bundle_audit.sh
