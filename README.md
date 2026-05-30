# LongUserPolicyBench

LongUserPolicyBench is a benchmark construction workspace for **Longitudinal User Policy / Habit Induction for Tool-Using Agents**.

The benchmark does not ask whether an agent can remember a fact, retrieve a needle from a long context, or finish an isolated task. It asks whether an agent can infer how a user or workflow community works from longitudinal traces, then apply that induced policy in future tool actions: review routing, issue triage, CI/merge boundaries, negative-example storage gating, authorization limits, exception handling, and abstention or clarification.

## Status Snapshot

Current paper-candidate release:

- Real reused workflow data: **GH Archive public GitHub event stream**.
- Raw local data: `/home/jmzhang/Workspace/data/gharchive/2024-01/`, 60 hourly `.json.gz` files, about 5.1 GB.
- Working slice: `/home/jmzhang/Workspace/data/gharchive/longuserpolicy_2024_01_pilot_slice.jsonl`.
- Slice scale: 60,000 public GitHub workflow events, 28,069 repos, 340 eligible repos, 283 eligible time windows, 19,709 deterministic policy candidates.
- Paper-candidate release: 30 selected repos, 168 verifier-checked probes, repo-disjoint train/dev/test probe split = 102/37/29.
- LLM-assisted construction: 168/168 GPT-5.5 rewrite proposals collected and passed verifier checks.
- Project release: `examples/generated/release_packaging/gharchive_real_llm_paper_candidate_project_benchmark`.
- No-gold submission inputs: `examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs`.
- Hardened no-gold inputs: `examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs_hardened`.
- Human audit sample: `examples/generated/annotation_packs/gharchive_real_paper_candidate_human_audit`, 30 sampled LLM rewrite proposals; reviewer decisions are still pending.
- Readiness: `examples/generated/readiness_report_real_llm_paper_candidate.json`, passed with 21 checks, 0 failures, 2 warnings when using the hardened submission input pack.

The two current readiness warnings are intentional:

- `workflow_source_audit`: no reviewed Enron/Avocado-style email workflow manifest has passed the license/privacy gate yet.
- `rewrite_human_audit`: human decisions for the exported LLM rewrite audit sample are still missing.

A separate probe-leakage audit remains important for analysis: original public probe wording had shortcut risk, while the hardened submission pack reduces high-overlap probes from 44/168 to 0/168.

So the current real-data benchmark is a **GitHub developer workflow domain release**, not yet a multi-domain email/calendar/docs/chat/browser office-workflow release.

## What Is Tested

Each verifier-checked project contains raw longitudinal artifacts/events, a gold policy memory graph, and future probes. External systems receive no gold graph; they receive source artifacts/events plus probe queries and must produce `ProjectPrediction` JSONL.

Representative capabilities:

- `user_policy_induction`: infer implicit user or maintainer policy from repeated behavior.
- `contextual_policy_selection`: apply a policy only under matching repo, label, issue, PR, or workflow context.
- `tool_action_alignment`: choose tool actions that match induced policy, not just task completion.
- `workflow_boundary_respect`: respect merge, CI, review, blocked, failed, or approval boundaries.
- `habit_storage_gating`: avoid storing negative, exceptional, or human-only behavior as a durable habit.
- `privacy_authorization_boundary`: refuse, wait, or clarify when authorization is missing.

## Construction Pipeline

```text
GHArchive raw hourly files
  -> balanced local JSONL slice
  -> repo/window quality reports
  -> deterministic policy candidate mining
  -> source-grounded annotation packs
  -> provider-agnostic LLM prompt jobs
  -> LLM/human rewrite proposals
  -> rewrite verifier
  -> verifier-checked project benchmark
  -> no-gold submission inputs
  -> deterministic baselines / memory-system submissions / paper tables
  -> readiness report
```

LLMs are only allowed to rewrite policy text and draft future probes from supplied evidence. Verifiers reject invented event ids, widened action boundaries, missing negative evidence, weak expected behaviors, gold leakage in submission inputs, and release split/hash inconsistencies.

## Repository Map

- `LongUserPolicyBench：长期用户策略与习惯归纳Benchmark方案.md`: main design and research-positioning document.
- `docs/gharchive_staging_protocol.md`: GHArchive staging, filtering, and scale protocol.
- `docs/sota_failure_diagnostic_matrix.md`: SOTA method-to-diagnostic mapping.
- `ultra_long_benchmark/cli.py`: unified CLI entrypoint.
- `ultra_long_benchmark/pipelines/gharchive_pilot.py`: GHArchive staging, profiling, ranking, repo selection, and candidate mining.
- `ultra_long_benchmark/pipelines/annotation_pack.py`: annotation packs, prompt exports, rewrite validation, and project synthesis.
- `ultra_long_benchmark/pipelines/llm_rewrite.py`: OpenAI-compatible rewrite-job runner with incremental progress files and failed-prompt recovery.
- `ultra_long_benchmark/pipelines/memory_submission.py`: no-gold memory-submission runner contract and local event-profile baseline.
- `ultra_long_benchmark/project_release.py`: project release, no-gold submission inputs, and prediction submission validation.
- `ultra_long_benchmark/pipelines/evaluation.py`: deterministic baselines, action-trace scoring, release prediction scoring.
- `configs/baselines/`: deterministic baselines plus gated Mem0/A-MEM/Graphiti submission placeholders.
- `scripts/slurm/`: cluster entry points for staging, baseline batches, readiness, and scoring.
- `tests/`: contract tests for adapters, mining, verifier gates, release gates, scoring, and LLM runner.

## Key Artifacts

- Repo selection: `examples/generated/gharchive_real_paper_candidate_repo_selection.json`
- Annotation packs: `examples/generated/annotation_packs/gharchive_real_paper_candidate`
- Annotation release: `examples/generated/release_packaging/gharchive_real_paper_candidate_annotation_pack`
- Rewrite jobs: `examples/generated/annotation_packs/gharchive_real_paper_candidate_rewrite_jobs`
- Rewrite validation: `examples/generated/annotation_packs/gharchive_real_paper_candidate_validation`
- Rewrite-derived projects: `examples/generated/projects/gharchive_real_llm_paper_candidate_batch`
- Project release: `examples/generated/release_packaging/gharchive_real_llm_paper_candidate_project_benchmark`
- No-gold inputs: `examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs`
- Deterministic release baselines: `examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_project_release_baselines.json`
- Memory-profile submission baseline:
  - predictions: `examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_memory_profile_stub_predictions.jsonl`
  - runner report: `examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_memory_profile_stub_report.json`
  - validation: `examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_memory_profile_stub_submission_validation.json`
  - score: `examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_memory_profile_stub_score.json`
- Paper tables: `examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_paper_tables`
- Probe leakage audit: `examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_probe_leakage_audit.json`
- Hardened input leakage audit: `examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs_hardened_probe_leakage_audit.json`
- Human audit sample: `examples/generated/annotation_packs/gharchive_real_paper_candidate_human_audit`
- Readiness report: `examples/generated/readiness_report_real_llm_paper_candidate.json`
- Data-source audit: `examples/generated/workflow_data_source_audit.json`

Earlier pilot artifacts are kept for debugging and regression checks:

- 5-repo pilot: `examples/generated/release_packaging/gharchive_real_llm_project_benchmark`
- 15-repo pilot-plus: `examples/generated/release_packaging/gharchive_real_llm_pilot_plus_project_benchmark`

## Environment

Recommended local environment:

```bash
source /home/jmzhang/miniconda3/etc/profile.d/conda.sh
conda activate benchmark
python -m pip install -e '.[dev]'
```

Cluster notes:

- Use Slurm for GPU or longer baseline experiments.
- Lightweight staging, verification, scoring, and table export are CPU-only.
- HuggingFace access should run without HTTP/HTTPS proxies if needed.
- Local proxy helpers are `proxy_on` and `proxy_off`.

## Core Commands

Run tests and validate baseline configs:

```bash
python -m pytest -q
python -m ultra_long_benchmark.cli validate-baseline-config configs/baselines \
  --output examples/generated/evaluation_harness/baseline_config_validation_after_memory_submission.json
```

Verify the paper-candidate release and no-gold input pack:

```bash
python -m ultra_long_benchmark.cli verify-project-benchmark-release \
  examples/generated/release_packaging/gharchive_real_llm_paper_candidate_project_benchmark \
  --output examples/generated/release_packaging/gharchive_real_llm_paper_candidate_project_benchmark/project_release_verify_report.json

python -m ultra_long_benchmark.cli verify-project-submission-inputs \
  examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs \
  --output examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs_verify_report.json
```

Run deterministic release baselines:

```bash
python -m ultra_long_benchmark.cli evaluate-project-release \
  examples/generated/release_packaging/gharchive_real_llm_paper_candidate_project_benchmark \
  --output examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_project_release_baselines.json
```


Export hardened no-gold inputs with lower query lexical leakage:

```bash
python -m ultra_long_benchmark.cli export-project-submission-inputs \
  examples/generated/release_packaging/gharchive_real_llm_paper_candidate_project_benchmark \
  --output-dir examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs_hardened \
  --harden-probe-queries

python -m ultra_long_benchmark.cli verify-project-submission-inputs \
  examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs_hardened \
  --output examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs_hardened_verify_report.json

python -m ultra_long_benchmark.cli audit-submission-input-probe-leakage \
  examples/generated/release_packaging/gharchive_real_llm_paper_candidate_project_benchmark \
  examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs_hardened \
  --output examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs_hardened_probe_leakage_audit.json
```

Run the local no-gold memory-submission contract baseline:

```bash
python -m ultra_long_benchmark.cli run-memory-submission-baseline \
  examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs \
  --adapter event_profile_stub \
  --top-k 5 \
  --system-name memory_submission_event_profile_stub \
  --predictions examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_memory_profile_stub_predictions.jsonl \
  --report examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_memory_profile_stub_report.json

python -m ultra_long_benchmark.cli validate-project-prediction-submission \
  examples/generated/release_packaging/gharchive_real_llm_paper_candidate_project_benchmark \
  examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_memory_profile_stub_predictions.jsonl \
  --output examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_memory_profile_stub_submission_validation.json

python -m ultra_long_benchmark.cli score-project-release-predictions \
  examples/generated/release_packaging/gharchive_real_llm_paper_candidate_project_benchmark \
  examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_memory_profile_stub_predictions.jsonl \
  --output examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_memory_profile_stub_score.json \
  --system-name memory_submission_event_profile_stub
```

Export paper tables:

```bash
python -m ultra_long_benchmark.cli export-paper-tables \
  --release-baseline-report examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_project_release_baselines.json \
  --prediction-report examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_memory_profile_stub_score.json \
  --prediction-report examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_memory_profile_stub_hardened_score.json \
  --output-dir examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_paper_tables \
  --bootstrap-samples 200
```

Run the baseline config batch. External/API baselines dry-run by default:

```bash
python -m ultra_long_benchmark.cli run-baseline-config-dir \
  configs/baselines \
  --output-dir examples/generated/evaluation_harness/baseline_batch
```

Run readiness:

```bash
python -m ultra_long_benchmark.cli readiness-report \
  --output examples/generated/readiness_report_real_llm_paper_candidate.json \
  --annotation-release-dir examples/generated/release_packaging/gharchive_real_paper_candidate_annotation_pack \
  --prompt-export-dir examples/generated/annotation_packs/gharchive_real_paper_candidate_prompt_exports \
  --rewrite-job-dir examples/generated/annotation_packs/gharchive_real_paper_candidate_rewrite_jobs \
  --staged-slice-manifest /home/jmzhang/Workspace/data/gharchive/longuserpolicy_2024_01_pilot_slice_manifest.json \
  --gharchive-stage-plan examples/generated/gharchive_stage_plan.json \
  --scale-summary examples/generated/gharchive_real_paper_candidate_scale_summary.json \
  --window-report examples/generated/gharchive_window_report.json \
  --public-data-discovery examples/generated/public_data_discovery_report.json \
  --workflow-source-audit examples/generated/workflow_data_source_audit.json \
  --batch-rewrite-validation examples/generated/annotation_packs/gharchive_real_paper_candidate_validation/batch_rewrite_validation_report.json \
  --batch-rewrite-projects examples/generated/projects/gharchive_real_llm_paper_candidate_batch/batch_rewrite_project_report.json \
  --project-release-dir examples/generated/release_packaging/gharchive_real_llm_paper_candidate_project_benchmark \
  --project-submission-input-dir examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs \
  --project-release-baseline examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_project_release_baselines.json \
  --project-release-prediction examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_memory_profile_stub_score.json \
  --paper-table-dir examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_paper_tables \
  --rewrite-human-audit examples/generated/annotation_packs/gharchive_real_paper_candidate_human_audit/audit_validation_report.json \
  --probe-leakage-audit examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_probe_leakage_audit.json \
  --paper-scale-profile paper \
  --require-paper-scale
```

## Baseline Interface

External memory methods should consume:

- `projects.jsonl`
- `artifacts.jsonl`
- `events.jsonl`
- `probes.jsonl`
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

The no-gold submission inputs intentionally exclude `memory_graph.json`, probe `expected_behavior`, and gold evidence IDs. Gold files are used only by validation/scoring commands after a submission is produced.

Current baseline configs:

- `memory_submission_event_profile_stub.yaml`: local deterministic no-gold event-profile baseline on original probe wording.
- `memory_submission_event_profile_stub_hardened.yaml`: the same local baseline on hardened probe wording, used for shortcut sensitivity.
- `submission_input_raw_event_rag.yaml`: deterministic raw-event RAG over no-gold inputs.
- `mem0_submission_placeholder.yaml`: gated Mem0 adapter placeholder over hardened no-gold inputs.
- `a_mem_submission_placeholder.yaml`: gated A-MEM adapter placeholder over hardened no-gold inputs.
- `graphiti_submission_placeholder.yaml`: gated temporal-KG/Graphiti adapter placeholder over hardened no-gold inputs.

Mem0, A-MEM, and Graphiti placeholders are not executed unless a method-specific runner, dependencies, and credentials are added and execution is explicitly allowed. Their preflight reports are generated with `plan-external-memory-submission-adapter`; current paper-candidate reports show the hardened input contract passes but method dependencies/API env are not ready.


Preflight external memory adapters without invoking provider APIs:

```bash
python -m ultra_long_benchmark.cli plan-external-memory-submission-adapter \
  examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs_hardened \
  --adapter mem0 \
  --predictions examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_mem0_predictions.jsonl \
  --report examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_mem0_plan.json \
  --system-name mem0_submission_placeholder

ADAPTER=mem0 bash scripts/run_external_memory_adapter_plan.sh
```

For Slurm preflight:

```bash
sbatch --export=ALL,ADAPTER=mem0 scripts/slurm/run_external_memory_adapter_plan.sbatch
```

## Current Baseline Results

Paper tables currently include 6 systems:

- `no_memory`
- `full_event_log`
- `raw_rag`
- `temporal_raw_rag`
- `oracle_policy_graph`
- `memory_submission_event_profile_stub`
- `memory_submission_event_profile_stub_hardened`

The local `memory_submission_event_profile_stub` is a harness sanity baseline, not a SOTA claim. On the original no-gold pack it covers 168/168 probes and scores `micro_pass_rate=0.881`, `micro_evidence_recall=0.8635`, and `micro_boundary_action_recall=0.9968`. On the hardened no-gold pack, high-overlap probes drop from 44/168 to 0/168 and the same baseline drops to `micro_pass_rate=0.179`. This is useful shortcut-sensitivity evidence: original probe wording was too lexical for paper claims. Raw retrieval baselines recover evidence but still show policy-action failures such as `retrieved_but_not_applied`, `overbroad_exception`, and `negative_example_stored`.

## Remaining Work

1. Complete human decisions for the exported rewrite audit sample and run `validate-policy-rewrite-human-audit`.
2. Add reviewed email/calendar/docs/chat/browser workflow corpora only through license, redistribution, privacy, and PII-redaction manifest gates.
3. Scale GHArchive beyond the January 2024 slice if the paper needs stronger multi-month longitudinal claims.
4. Promote the hardened no-gold input pack to the default external-system evaluation input after checking task naturalness with human audit.
5. Implement and run Mem0, A-MEM, Graphiti/Zep-style temporal KG, and long-context baselines through the no-gold submission interface on Slurm GPU nodes where needed.
