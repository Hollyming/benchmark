# Evaluation Protocol

## Baseline Families

A credible paper should compare at least four families:

1. **No-memory baseline:** act from current query/session only.
2. **Full-context baseline:** concatenate available trajectory when feasible.
3. **Retrieval baseline:** retrieve top-k messages/events, then plan an action.
4. **User-policy memory system:** tested method with write/read/update policies.
5. **Oracle policy graph:** upper bound with gold policies and boundaries.

The repository includes deterministic project-level implementations for offline sanity and ablation baselines:

- `no_memory`: lower-bound ablation with no durable memory and no event retrieval; it should clarify before user-specific risky actions.
- `full_event_log`: chronological raw event-log baseline; it sees the whole source history but receives no induced policy graph.
- `oracle_policy_graph`: answers from gold memory nodes, action boundaries, and cited source events.
- `raw_rag`: retrieves top-k canonical events lexically from the raw event stream without using gold memories.
- `temporal_raw_rag`: raw-event retrieval with recency and policy-update bonuses, still without gold memories.

Run them with:

```bash
python -m ultra_long_benchmark.cli evaluate-project examples/generated/projects/project_manual_001 --output examples/generated/evaluation_harness/project_manual_baselines.json --top-k 3
python -m ultra_long_benchmark.cli evaluate-project examples/generated/projects/project_gharchive_001 --output examples/generated/evaluation_harness/project_gharchive_baselines.json --top-k 3
python -m ultra_long_benchmark.cli evaluate-project examples/generated/projects/project_gharchive_001 --baseline temporal_raw_rag --output examples/generated/evaluation_harness/temporal_raw_rag_cli.json --top-k 3
```

Or through checked-in reproducibility configs:

```bash
python -m ultra_long_benchmark.cli validate-baseline-config configs/baselines --output examples/generated/evaluation_harness/baseline_config_validation.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/no_memory_project.yaml --output examples/generated/evaluation_harness/no_memory_config_run.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/raw_rag_project.yaml --output examples/generated/evaluation_harness/raw_rag_config_run.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/temporal_raw_rag_project.yaml --output examples/generated/evaluation_harness/temporal_raw_rag_config_run.json
python -m ultra_long_benchmark.cli run-baseline-config-dir configs/baselines --output-dir examples/generated/evaluation_harness/baseline_batch
```

For systems that emit concrete tool calls, score JSONL action traces directly:

```bash
python -m ultra_long_benchmark.cli score-action-traces examples/generated/projects/project_gharchive_001 examples/action_traces/gharchive_trace_examples.jsonl --output examples/generated/evaluation_harness/gharchive_action_trace_report.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/gharchive_action_trace_scoring.yaml --output examples/generated/evaluation_harness/action_trace_config_run.json
```

Each trace row binds to a `probe_id` and contains ordered actions with `tool`, `action`, arguments, approval/clarification flags, and retrieved evidence ids. The scorer reports pass rate, boundary violation rate, allowed-action coverage, missing approval/clarification, forbidden action/tool violations, and unauthorized tool use.

For external systems that produce final policy/action text rather than executable traces, use the prediction-submission scorer:

```bash
python -m ultra_long_benchmark.cli score-project-predictions examples/generated/projects/project_gharchive_001 examples/project_predictions/gharchive_prediction_examples.jsonl --output examples/generated/evaluation_harness/gharchive_prediction_report.json --system-name example_external_submission
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/gharchive_prediction_submission_example.yaml --output examples/generated/evaluation_harness/prediction_submission_config_run.json
```

Each prediction row contains `prediction_id`, `project_id`, `probe_id`, `prediction`, and optional `retrieved_memory_ids`, `retrieved_event_ids`, and `retrieved_artifact_ids`. This is the recommended no-API integration point for Mem0/A-MEM/custom agents before a full runner exists.

For a project benchmark release, submit one JSONL spanning all projects and score it in one pass:

```bash
python -m ultra_long_benchmark.cli export-project-submission-inputs examples/generated/release_packaging/project_benchmark --output-dir examples/generated/evaluation_harness/project_submission_inputs
python -m ultra_long_benchmark.cli verify-project-submission-inputs examples/generated/evaluation_harness/project_submission_inputs --output examples/generated/evaluation_harness/project_submission_input_report.json
python -m ultra_long_benchmark.cli run-submission-input-baseline examples/generated/evaluation_harness/project_submission_inputs --baseline raw_event_rag_input --top-k 5 --predictions examples/generated/evaluation_harness/submission_input_raw_event_rag_predictions.jsonl --report examples/generated/evaluation_harness/submission_input_raw_event_rag_report.json
python -m ultra_long_benchmark.cli validate-project-prediction-submission examples/generated/release_packaging/project_benchmark examples/generated/evaluation_harness/submission_input_raw_event_rag_predictions.jsonl --output examples/generated/evaluation_harness/submission_input_raw_event_rag_submission_validation.json
python -m ultra_long_benchmark.cli score-project-release-predictions examples/generated/release_packaging/project_benchmark examples/generated/evaluation_harness/submission_input_raw_event_rag_predictions.jsonl --output examples/generated/evaluation_harness/submission_input_raw_event_rag_score.json --system-name submission_input_raw_event_rag
python -m ultra_long_benchmark.cli validate-project-prediction-submission examples/generated/release_packaging/project_benchmark examples/project_predictions/project_release_prediction_examples.jsonl --output examples/generated/evaluation_harness/project_release_prediction_submission_validation.json
python -m ultra_long_benchmark.cli score-project-release-predictions examples/generated/release_packaging/project_benchmark examples/project_predictions/project_release_prediction_examples.jsonl --output examples/generated/evaluation_harness/project_release_prediction_report.json --system-name example_release_submission
python -m ultra_long_benchmark.cli score-project-release-prediction-dir examples/generated/release_packaging/project_benchmark examples/project_predictions/release_submissions --output-dir examples/generated/evaluation_harness/prediction_scoring_batch --system-name-prefix external
```

`export-project-submission-inputs` writes the no-gold files external methods should consume: `projects.jsonl`, `artifacts.jsonl`, `events.jsonl`, `probes.jsonl`, and `prediction_template.jsonl`. It intentionally excludes `memory_graph.json`, probe `expected_behavior`, and gold evidence IDs. `run-submission-input-baseline` is the deterministic no-gold runner for this exact input contract, producing a standard `ProjectPrediction` JSONL. `validate-project-prediction-submission` is the pre-scoring CI gate for Mem0/A-MEM/custom outputs: it checks schema, duplicate rows, unknown projects/probes, empty predictions, and full release-probe coverage. The release scorer then groups submitted predictions by project, reports project/probe coverage, and emits micro/macro pass rate, must-include recall, must-not violation rate, evidence recall, boundary-action recall, diagnostic failure-label counts, and task/capability-balanced metrics.

`score-project-release-prediction-dir` is the batch interface for external methods: put one `ProjectPrediction` JSONL per system under `examples/project_predictions/release_submissions/`, score the directory once, and use the resulting `prediction_scoring_batch_report.json` in paper-table export. Filenames become system names, optionally prefixed with `--system-name-prefix`.

Deterministic baselines can also run across the full project release:

```bash
python -m ultra_long_benchmark.cli evaluate-project-release examples/generated/release_packaging/project_benchmark --output examples/generated/evaluation_harness/project_release_baselines.json --top-k 3
```

This produces per-project baseline reports plus release-level micro/macro metrics for `no_memory`, `full_event_log`, `raw_rag`, `temporal_raw_rag`, and `oracle_policy_graph`. Deterministic baseline reports now use the same pass/failure, diagnostic-label, task-breakdown, and capability-breakdown fields as external prediction submissions.

Export paper-ready result tables after deterministic baselines and external submissions have been scored:

```bash
python -m ultra_long_benchmark.cli export-paper-tables --release-baseline-report examples/generated/evaluation_harness/project_release_baselines.json --prediction-report examples/generated/evaluation_harness/project_release_prediction_report.json --prediction-report examples/generated/evaluation_harness/submission_input_raw_event_rag_score.json --prediction-batch-report examples/generated/evaluation_harness/prediction_scoring_batch/prediction_scoring_batch_report.json --bootstrap-samples 1000 --bootstrap-seed 0 --output-dir examples/generated/evaluation_harness/paper_tables
```

This writes `paper_tables.json` plus CSV/Markdown files for `main_results`, `task_breakdown`, `capability_breakdown`, `failure_breakdown`, and `confidence_intervals`. Confidence intervals are deterministic percentile bootstrap intervals over projects/workspaces, not raw probes, so correlated probes from the same workspace do not inflate significance claims.

Mem0/A-MEM configs are included as gated placeholders. They should be dry-run-validated until a concrete runner and provider/model credentials exist:

```bash
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/mem0_project_placeholder.yaml --dry-run --output examples/generated/evaluation_harness/mem0_dry_run.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/a_mem_project_placeholder.yaml --dry-run --output examples/generated/evaluation_harness/a_mem_dry_run.json
```

The batch runner dry-runs these external configs by default while executing deterministic configs. Use `scripts/run_baseline_config_batch.sh` locally or `scripts/slurm/run_baseline_config_batch.sbatch` on the cluster.

Before reporting results, run the release-readiness gate:

```bash
python -m ultra_long_benchmark.cli verify-release-integrity examples/generated/release_packaging/gharchive_annotation_pack --prompt-export-dir examples/generated/annotation_packs/gharchive_prompt_exports --output examples/generated/release_integrity_report.json
python -m ultra_long_benchmark.cli assess-paper-scale examples/generated/release_packaging/gharchive_annotation_pack --profile paper --scale-summary examples/generated/gharchive_scale_summary.json --window-report examples/generated/gharchive_window_report.json --release-integrity-report examples/generated/release_integrity_report.json --output examples/generated/paper_scale_assessment.json --allow-fail
python -m ultra_long_benchmark.cli audit-workflow-data-sources --discovery-report examples/generated/public_data_discovery_report.json --gharchive-stage-plan examples/generated/gharchive_stage_plan.json --output examples/generated/workflow_data_source_audit.json
python -m ultra_long_benchmark.cli export-paper-tables --release-baseline-report examples/generated/evaluation_harness/project_release_baselines.json --prediction-report examples/generated/evaluation_harness/project_release_prediction_report.json --prediction-report examples/generated/evaluation_harness/submission_input_raw_event_rag_score.json --prediction-batch-report examples/generated/evaluation_harness/prediction_scoring_batch/prediction_scoring_batch_report.json --bootstrap-samples 1000 --bootstrap-seed 0 --output-dir examples/generated/evaluation_harness/paper_tables
python -m ultra_long_benchmark.cli readiness-report --output examples/generated/readiness_report.json
```

If LLM or human proposal outputs exist for a multi-pack annotation batch, run:

```bash
python -m ultra_long_benchmark.cli collect-policy-rewrite-job-outputs examples/generated/annotation_packs/rewrite_jobs --output examples/generated/annotation_packs/rewrite_jobs/collected_rewrite_proposals.jsonl --report examples/generated/annotation_packs/rewrite_jobs/rewrite_job_collection_report.json
python -m ultra_long_benchmark.cli validate-policy-rewrites-batch examples/generated/annotation_packs/gharchive_batch examples/generated/annotation_packs/rewrite_jobs/collected_rewrite_proposals.jsonl --output-dir examples/generated/annotation_packs/gharchive_rewrite_validation_batch
python -m ultra_long_benchmark.cli build-projects-from-rewrite-batch examples/generated/annotation_packs/gharchive_rewrite_validation_batch/batch_rewrite_validation_report.json --output-dir examples/generated/projects --project-prefix project_gharchive_rewrite_batch
python -m ultra_long_benchmark.cli export-project-benchmark-release examples/generated/projects/project_gharchive_rewrite_batch_* --output-dir examples/generated/release_packaging/project_benchmark
python -m ultra_long_benchmark.cli verify-project-benchmark-release examples/generated/release_packaging/project_benchmark --output examples/generated/project_release_integrity_report.json
```

`collect-policy-rewrite-job-outputs` only collects already completed job files and rejects missing, empty, duplicate, schema-invalid, or unfilled rows before verifier validation. `build-projects-from-rewrite-batch` only consumes a passed batch validation report and runs the project verifier for every derived project. `export-project-benchmark-release` then publishes project/probe manifests and file hashes for external evaluators, while `verify-project-benchmark-release` checks those hashes and split/probe consistency. `verify-release-integrity` checks pack hashes, repo-disjoint splits, split/task count consistency, prompt coverage for every release pack, action-boundary prompt constraints, and explicit no-LLM/no-unvalidated-rewrite constraints. `assess-paper-scale` checks that the release is large, split-balanced, candidate-diverse, and longitudinal enough for paper claims. `readiness-report` then aggregates audit status, annotation release constraints, prompt-export constraints, release-integrity status, paper-scale status, workflow source audit, GHArchive stage-plan decision, batch rewrite validation, batch rewrite project synthesis, project benchmark release integrity, no-gold external submission inputs, release-level deterministic baselines, release-level prediction scoring, paper table export, rewrite-project verifier status, staged-slice provenance, and baseline batch status without rerunning provider or GPU experiments. Set `--require-paper-scale` only when gating the final main-experiment release; it upgrades a non-ready GHArchive stage decision and non-paper-ready workflow source audit to blocking failures.

## Streaming Evaluation Loop

For each trajectory:

1. Sort sessions by timestamp.
2. Feed each session to the system in order.
3. Allow the system to update policy/habit memory after each session.
4. At future task time, freeze memory and ask the tool-policy probe.
5. Record action, rationale, retrieved evidence IDs, refusal/clarification decision, latency, token cost, and memory size.

## Reporting

Report:

- overall policy-action accuracy;
- macro score by capability;
- boundary violation rate for send/merge/pay/reveal/delete/share actions;
- exception-scope accuracy;
- negative-example suppression;
- clarification accuracy on missing authorization;
- score by horizon bucket and evidence count;
- cost/latency and memory footprint.

## Error Taxonomy

Label failures as:

- missing write: policy evidence was never stored;
- retrieval miss: policy evidence stored but not retrieved;
- action synthesis error: evidence retrieved but action wrong;
- overbroad exception: narrow exception applied globally;
- stale policy: older policy used after update;
- transient-as-habit: one-off example stored as durable habit;
- boundary violation: unauthorized send/merge/pay/reveal/delete/share;
- over-refusal: allowed action refused;
- unsupported authorization: permission inferred without evidence;
- evidence failure: correct action but unsupported evidence IDs.

## Statistical Treatment

Use bootstrap confidence intervals over users/workspaces, not raw probes, because probes from the same user are correlated. Include capability-balanced macro averages so systems cannot hide boundary failures behind easy policy cases.
