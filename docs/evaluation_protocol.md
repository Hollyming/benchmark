# Evaluation Protocol

This protocol describes the formal LongUserPolicyBench evaluation surface. The current release-ready dataset is the GHArchive developer-workflow release:

- release: `examples/generated/release_packaging/gharchive_formal_project_benchmark`
- hardened no-gold inputs: `examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened`
- deterministic release baselines: `examples/generated/evaluation_harness/gharchive_formal_project_release_baselines.json`
- main prediction score used in tables: `examples/generated/evaluation_harness/gharchive_formal_memory_profile_stub_hardened_score.json`
- paper tables: `examples/generated/evaluation_harness/gharchive_formal_paper_tables`

## Baseline Families

A credible comparison should cover:

1. no-memory / clarification lower bound;
2. full-event-log context;
3. raw-event retrieval;
4. temporal raw-event retrieval;
5. oracle policy graph upper bound;
6. memory-system submissions over the no-gold input contract.

The deterministic release evaluator emits `no_memory`, `full_event_log`, `raw_rag`, `temporal_raw_rag`, and `oracle_policy_graph` rows:

```bash
python -m ultra_long_benchmark.cli evaluate-project-release \
  examples/generated/release_packaging/gharchive_formal_project_benchmark \
  --output examples/generated/evaluation_harness/gharchive_formal_project_release_baselines.json
```

External and memory-system methods must consume the no-gold input pack and emit `ProjectPrediction` JSONL. The pack includes `projects.jsonl`, `artifacts.jsonl`, `events.jsonl`, `probes.jsonl`, `prediction_template.jsonl`, and `submission_manifest.json`. It excludes the gold memory graph, probe expected behavior, and gold evidence IDs.

## Submission Flow

Run or validate the local no-gold contract baseline:

```bash
python -m ultra_long_benchmark.cli run-memory-submission-baseline \
  examples/generated/evaluation_harness/gharchive_formal_submission_inputs_hardened \
  --adapter event_profile_stub \
  --top-k 5 \
  --system-name memory_submission_event_profile_stub_hardened \
  --predictions examples/generated/evaluation_harness/gharchive_formal_memory_profile_stub_hardened_predictions.jsonl \
  --report examples/generated/evaluation_harness/gharchive_formal_memory_profile_stub_hardened_report.json

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

Checked-in baseline configs now represent the formal no-gold submission contract plus gated memory-method adapters:

```bash
python -m ultra_long_benchmark.cli validate-baseline-config configs/baselines \
  --output examples/generated/evaluation_harness/baseline_config_validation_after_artifact_bundle.json
python -m ultra_long_benchmark.cli run-baseline-config-dir configs/baselines \
  --output-dir examples/generated/evaluation_harness/baseline_batch_after_claim_boundary
python -m ultra_long_benchmark.cli verify-baseline-batch \
  examples/generated/evaluation_harness/baseline_batch_after_claim_boundary/baseline_batch_report.json
```

Mem0, A-MEM, and Graphiti configs dry-run unless `--allow-llm-api` is explicitly passed. The in-repo rows are OpenAI-compatible prompt adapters over hardened no-gold inputs, not upstream package executions.

## Metrics

Chapter 9 of the main document defines the two-layer metric design:

- Layer 1: final policy/action correctness, including pass rate, must-include recall, must-not violation rate, evidence recall, and boundary-action recall.
- Layer 2: diagnostic decomposition by task type, capability, and failure label, including retrieval miss, retrieved-but-not-applied, stale policy, overbroad exception, negative-example storage, approval/clarification omission, and boundary violation.

All release-level deterministic baselines and external submissions use the same verifier-backed scoring contract, so table rows are comparable.

## Release Gate

Before reporting a result, run the full benchmark gate:

```bash
bash scripts/run_benchmark_release_gate.sh
```

The gate verifies baseline config hashes, baseline batch outputs, claim-boundary and claim-lint reports, artifact bundle hashes, taxonomy coverage, domain-expansion status, no-gold input checks, and readiness evidence. The current release remains GitHub-only; email/calendar/docs/chat/browser-web reports are preflight or roadmap artifacts until they pass the same release/no-gold/baseline/readiness/artifact gates.
