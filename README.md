# LongUserPolicyBench

LongUserPolicyBench is a benchmark construction workspace for **Longitudinal User Policy / Habit Induction for Tool-Using Agents**. It evaluates whether a system can infer durable workflow policy from longitudinal traces and apply it to future tool decisions, including review routing, CI/merge boundaries, negative-example storage gating, authorization limits, exception scope, and clarification.

## Current Release

The first formal release-ready domain is **GHArchive public GitHub developer workflow data**.

- raw local data: `/home/jmzhang/Workspace/data/gharchive/2024-01/`, 60 hourly `.json.gz` files, about 5.1 GB
- staged slice: `/home/jmzhang/Workspace/data/gharchive/longuserpolicy_2024_01_release_slice.jsonl`
- slice scale: 60,000 events, 28,069 repos, 340 eligible repos, 283 eligible windows, 19,709 candidates
- benchmark release: 30 repos, 168 verifier-checked probes, train/dev/test = 102/37/29
- release scope: `github_developer_workflow_only`
- current task coverage: 4 task types and 5 capability enum values
- LLM-assisted construction: 168/168 GPT-5.5 rewrite proposals passed verifier checks

Key paths:

- project release: `examples/generated/release_packaging/gharchive_formal_project_benchmark`
- no-gold inputs: `examples/generated/evaluation_harness/gharchive_formal_submission_inputs`
- hardened no-gold inputs: `examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened`
- release baselines: `examples/generated/evaluation_harness/gharchive_formal_project_release_baselines.json`
- hardened memory-stub score: `examples/generated/evaluation_harness/gharchive_formal_memory_profile_stub_hardened_score.json`
- paper tables: `examples/generated/evaluation_harness/gharchive_formal_paper_tables`
- readiness report: `examples/generated/readiness_report_gharchive_formal.json`
- artifact bundle: `examples/generated/evaluation_harness/gharchive_formal_artifact_bundle_manifest.json`
- benchmark gate report: `examples/generated/evaluation_harness/gharchive_formal_gate_report.json`

Current readiness is GitHub-only. Enron/email has a redacted preflight, and calendar/docs/chat/browser-web have manifest-first fixture/preflight contracts, but none of those domains are release claims until they pass the same source, verifier, no-gold, baseline, readiness, artifact, and claim-boundary gates.

## Repository Map

- `LongUserPolicyBench：长期用户策略与习惯归纳Benchmark方案.md`: main design document.
- `tasks/`: formal task taxonomy folders.
- `docs/evaluation_protocol.md`: formal evaluation protocol.
- `docs/gharchive_staging_protocol.md`: GHArchive staging and scale protocol.
- `docs/public_data_and_llm_extensions.md`: safe public-data and future-domain extension path.
- `docs/sota_failure_diagnostic_matrix.md`: method-to-diagnostic mapping.
- `ultra_long_benchmark/cli.py`: CLI entrypoint.
- `ultra_long_benchmark/pipelines/gharchive.py`: GHArchive staging, profiling, ranking, selection, and candidate mining.
- `ultra_long_benchmark/pipelines/annotation_pack.py`: annotation packs, prompt exports, rewrite validation, and project synthesis.
- `ultra_long_benchmark/pipelines/memory_submission.py`: no-gold memory-submission contract and local event-profile baseline.
- `ultra_long_benchmark/pipelines/external_memory_runner.py`: external runner contract over no-gold inputs.
- `ultra_long_benchmark/project_release.py`: project release, no-gold inputs, and prediction validation.
- `configs/baselines/`: current baseline configs.
- `scripts/` and `scripts/slurm/`: local and cluster entrypoints.

## Environment

```bash
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate benchmark
python -m pip install -e '.[dev]'
```

Cluster notes:

- Use Slurm for GPU or long external-method experiments.
- Lightweight staging, verification, scoring, and table export are CPU-only.
- HuggingFace access should run without HTTP/HTTPS proxies.
- Local proxy helpers are `proxy_on` and `proxy_off`.

## Core Commands

Run tests and validate current baseline configs:

```bash
python -m pytest -q
python -m ultra_long_benchmark.cli validate-baseline-config configs/baselines \
  --output examples/generated/evaluation_harness/baseline_config_validation_after_artifact_bundle.json
python -m ultra_long_benchmark.cli verify-baseline-config-validation \
  examples/generated/evaluation_harness/baseline_config_validation_after_artifact_bundle.json
```

Verify release and hardened no-gold inputs:

```bash
python -m ultra_long_benchmark.cli verify-project-benchmark-release \
  examples/generated/release_packaging/gharchive_formal_project_benchmark \
  --output examples/generated/release_packaging/gharchive_formal_project_benchmark/project_release_verify_report.json

python -m ultra_long_benchmark.cli verify-project-submission-inputs \
  examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened \
  --output examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened_verify_report.json
```

Run deterministic release baselines:

```bash
python -m ultra_long_benchmark.cli evaluate-project-release \
  examples/generated/release_packaging/gharchive_formal_project_benchmark \
  --output examples/generated/evaluation_harness/gharchive_formal_project_release_baselines.json
```

Run the local no-gold memory-submission contract baseline:

```bash
python -m ultra_long_benchmark.cli run-memory-submission-baseline \
  examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened \
  --adapter event_profile_stub \
  --top-k 5 \
  --system-name memory_submission_event_profile_stub_hardened \
  --predictions examples/generated/evaluation_harness/gharchive_formal_memory_profile_stub_hardened_predictions.jsonl \
  --report examples/generated/evaluation_harness/gharchive_formal_memory_profile_stub_hardened_report.json
```

Validate and score a submission:

```bash
python -m ultra_long_benchmark.cli validate-project-prediction-submission \
  examples/generated/release_packaging/gharchive_formal_project_benchmark \
  examples/generated/evaluation_harness/gharchive_formal_memory_profile_stub_hardened_predictions.jsonl \
  --output examples/generated/evaluation_harness/gharchive_formal_memory_profile_stub_hardened_submission_validation.json

python -m ultra_long_benchmark.cli score-project-release-predictions \
  examples/generated/release_packaging/gharchive_formal_project_benchmark \
  examples/generated/evaluation_harness/gharchive_formal_memory_profile_stub_hardened_predictions.jsonl \
  --output examples/generated/evaluation_harness/gharchive_formal_memory_profile_stub_hardened_score.json \
  --system-name memory_submission_event_profile_stub_hardened
```

Run the baseline config batch. External/API baselines dry-run by default:

```bash
python -m ultra_long_benchmark.cli run-baseline-config-dir \
  configs/baselines \
  --output-dir examples/generated/evaluation_harness/baseline_batch_after_claim_boundary
python -m ultra_long_benchmark.cli verify-baseline-batch \
  examples/generated/evaluation_harness/baseline_batch_after_claim_boundary/baseline_batch_report.json
```

Run the complete formal gate:

```bash
bash scripts/run_benchmark_release_gate.sh
```

## Baseline Interface

External memory methods consume:

- `projects.jsonl`
- `artifacts.jsonl`
- `events.jsonl`
- `probes.jsonl`
- `prediction_template.jsonl`
- `submission_manifest.json`

They must output `ProjectPrediction` JSONL:

```json
{
  "prediction_id": "pred_<project_id>_<probe_id>",
  "project_id": "...",
  "probe_id": "...",
  "prediction": "policy/action decision text",
  "retrieved_memory_ids": [],
  "retrieved_event_ids": ["..."],
  "retrieved_artifact_ids": [],
  "metadata": {"system": "..."}
}
```

The no-gold inputs exclude `memory_graph.json`, probe `expected_behavior`, and gold evidence IDs. Gold files are used only by validation and scoring after a submission is produced.

Current checked-in baseline configs:

- `memory_submission_event_profile_stub.yaml`
- `memory_submission_event_profile_stub_hardened.yaml`
- `external_memory_runner_echo_contract.yaml`
- `mem0_submission_placeholder.yaml`
- `a_mem_submission_placeholder.yaml`
- `graphiti_submission_placeholder.yaml`

Mem0, A-MEM, and Graphiti configs dry-run by default. With `--allow-llm-api`, they run in-repo OpenAI-compatible prompt adapters against hardened no-gold inputs. These are not upstream package executions; official upstream baselines still require method-specific runners, dependencies, storage/provider configuration, and Slurm resource profiles.

## Current Results

| Dataset / input | System | Probes | Micro pass | Evidence recall | Boundary-action recall | Must-include recall | Must-not violation |
|---|---:|---:|---:|---:|---:|---:|---:|
| GHArchive release | `no_memory` | 168 | 0.0000 | 0.0000 | 0.0000 | 0.0246 | 0.0049 |
| GHArchive release | `full_event_log` | 168 | 0.0357 | 1.0000 | 0.5317 | 0.5317 | 0.0669 |
| GHArchive release | `raw_rag` | 168 | 0.0000 | 0.8718 | 0.3799 | 0.4991 | 0.0550 |
| GHArchive release | `temporal_raw_rag` | 168 | 0.0179 | 0.7821 | 0.4870 | 0.5019 | 0.0650 |
| GHArchive release | `oracle_policy_graph` | 168 | 0.9940 | 1.0000 | 1.0000 | 0.9980 | 0.0000 |
| GHArchive no-gold | `memory_submission_event_profile_stub` | 168 | 0.8810 | 0.8635 | 0.9968 | 0.9942 | 0.0685 |
| GHArchive hardened no-gold | `memory_submission_event_profile_stub_hardened` | 168 | 0.1786 | 0.4384 | 0.5918 | 0.6186 | 0.1333 |
| GHArchive hardened no-gold | `external_echo_runner_contract` | 168 | 0.0000 | 0.2376 | 0.0000 | 0.0339 | 0.0034 |
| GHArchive hardened no-gold | `a_mem_gpt54mini_prompt_adapter` | 168 | 0.0000 | 0.7117 | 0.4841 | 0.6143 | 0.0187 |
| GHArchive hardened no-gold | `mem0_gpt54mini_prompt_adapter` | 168 | 0.0060 | 0.7117 | 0.5125 | 0.6381 | 0.0485 |
| GHArchive hardened no-gold | `graphiti_gpt54mini_prompt_adapter` | 168 | 0.0000 | 0.7117 | 0.4981 | 0.6235 | 0.0423 |

The local event-profile stub is a harness sanity baseline, not a SOTA claim. The A-MEM/Mem0/Graphiti rows are OpenAI-compatible method-style prompt adapters using `gpt-5.4-mini`; they prove the no-gold submission/scoring path runs end to end.

## Remaining Work

1. Complete human decisions for the exported rewrite audit sample.
2. Promote the Enron/email preflight only after privacy review and full release-gate integration.
3. Scale GHArchive beyond the January 2024 slice if stronger multi-month claims are needed.
4. Implement upstream package runners for Mem0, A-MEM, Graphiti/Zep-style temporal KG, and long-context baselines.
