# evaluation_harness

Skeleton harness for evaluating tool-using agents and user-policy memory baselines. The smoke baseline answers gold strings directly and refuses privacy-sensitive channel violations, which verifies metric plumbing.

Offline demo:

```powershell
python -m ultra_long_benchmark.cli smoke --all
```

Task-only command after queries exist:

```powershell
python tasks/evaluation_harness/scripts/run_demo.py
```

Project-level baseline commands:

```bash
python -m ultra_long_benchmark.cli evaluate-project examples/generated/projects/project_manual_001 --output examples/generated/evaluation_harness/project_manual_baselines.json --top-k 3
python -m ultra_long_benchmark.cli evaluate-project examples/generated/projects/project_gharchive_001 --baseline temporal_raw_rag --output examples/generated/evaluation_harness/temporal_raw_rag_cli.json --top-k 3
python -m ultra_long_benchmark.cli score-action-traces examples/generated/projects/project_gharchive_001 examples/action_traces/gharchive_trace_examples.jsonl --output examples/generated/evaluation_harness/gharchive_action_trace_report.json
python -m ultra_long_benchmark.cli score-project-predictions examples/generated/projects/project_gharchive_001 examples/project_predictions/gharchive_prediction_examples.jsonl --output examples/generated/evaluation_harness/gharchive_prediction_report.json --system-name example_external_submission
python -m ultra_long_benchmark.cli export-project-submission-inputs examples/generated/release_packaging/project_benchmark --output-dir examples/generated/evaluation_harness/project_submission_inputs
python -m ultra_long_benchmark.cli run-submission-input-baseline examples/generated/evaluation_harness/project_submission_inputs --baseline raw_event_rag_input --top-k 5 --predictions examples/generated/evaluation_harness/submission_input_raw_event_rag_predictions.jsonl --report examples/generated/evaluation_harness/submission_input_raw_event_rag_report.json
python -m ultra_long_benchmark.cli validate-project-prediction-submission examples/generated/release_packaging/project_benchmark examples/generated/evaluation_harness/submission_input_raw_event_rag_predictions.jsonl --output examples/generated/evaluation_harness/submission_input_raw_event_rag_submission_validation.json
python -m ultra_long_benchmark.cli score-project-release-predictions examples/generated/release_packaging/project_benchmark examples/generated/evaluation_harness/submission_input_raw_event_rag_predictions.jsonl --output examples/generated/evaluation_harness/submission_input_raw_event_rag_score.json --system-name submission_input_raw_event_rag
python -m ultra_long_benchmark.cli score-project-release-prediction-dir examples/generated/release_packaging/project_benchmark examples/project_predictions/release_submissions --output-dir examples/generated/evaluation_harness/prediction_scoring_batch --system-name-prefix external
python -m ultra_long_benchmark.cli evaluate-project-release examples/generated/release_packaging/project_benchmark --output examples/generated/evaluation_harness/project_release_baselines.json --top-k 3
python -m ultra_long_benchmark.cli export-paper-tables --release-baseline-report examples/generated/evaluation_harness/project_release_baselines.json --prediction-report examples/generated/evaluation_harness/submission_input_raw_event_rag_score.json --prediction-batch-report examples/generated/evaluation_harness/prediction_scoring_batch/prediction_scoring_batch_report.json --bootstrap-samples 1000 --bootstrap-seed 0 --output-dir examples/generated/evaluation_harness/paper_tables
python -m ultra_long_benchmark.cli validate-baseline-config configs/baselines --output examples/generated/evaluation_harness/baseline_config_validation.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/no_memory_project.yaml --output examples/generated/evaluation_harness/no_memory_config_run.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/raw_rag_project.yaml --output examples/generated/evaluation_harness/raw_rag_config_run.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/temporal_raw_rag_project.yaml --output examples/generated/evaluation_harness/temporal_raw_rag_config_run.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/gharchive_action_trace_scoring.yaml --output examples/generated/evaluation_harness/action_trace_config_run.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/gharchive_prediction_submission_example.yaml --output examples/generated/evaluation_harness/prediction_submission_config_run.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/mem0_project_placeholder.yaml --dry-run --output examples/generated/evaluation_harness/mem0_dry_run.json
python -m ultra_long_benchmark.cli run-baseline-config-dir configs/baselines --output-dir examples/generated/evaluation_harness/baseline_batch
```

`evaluate-project` defaults to all deterministic project baselines: `no_memory`, `full_event_log`, `raw_rag`, `temporal_raw_rag`, and `oracle_policy_graph`. Use repeated `--baseline` flags to run a subset. These reports include the same `passed`, `issues`, `diagnostics.labels`, task breakdown, and capability breakdown fields used by external submission scoring.

`score-project-predictions` is the offline submission interface for external methods. Each JSONL row must contain `prediction_id`, `project_id`, `probe_id`, `prediction`, and optional retrieved memory/event/artifact IDs. It scores the same must-include, must-not, evidence-recall, and boundary-action metrics as the deterministic baselines, and emits diagnostic failure labels under `diagnostics.labels`. Release-level reports additionally include task-type and capability breakdowns for capability-balanced paper tables.

`run-submission-input-baseline` consumes only `export-project-submission-inputs` output and writes standard prediction JSONL. It is the no-gold contract test for future Mem0/A-MEM/custom runners.

`validate-project-prediction-submission` checks release-level external submissions before scoring: schema validity, duplicate project/probe rows, empty predictions, unknown projects/probes, and full probe coverage. `score-project-release-prediction-dir` then scores a directory of release-level external submissions and writes one report per system plus `prediction_scoring_batch_report.json`. Use this for Mem0/A-MEM/custom systems once each runner emits a `ProjectPrediction` JSONL.

`export-paper-tables` converts release-level deterministic baseline reports and external submission reports into JSON/CSV/Markdown tables for main results, task breakdowns, capability breakdowns, diagnostic failure-label breakdowns, and project-level bootstrap confidence intervals. `readiness-report` now checks this export.

`run-baseline-config` executes only deterministic in-repo baselines today. Mem0/A-MEM configs are intentionally gated behind `--dry-run` until the concrete runner, dependencies, and API/model credentials are provided.

`run-baseline-config-dir` executes deterministic configs and dry-runs LLM/API configs by default. Use `--no-dry-run-external --allow-llm-api` only after the external runner, credentials, and dependency lock are ready.

Slurm skeletons are in `scripts/slurm/`. Use `run_action_trace_scoring.sbatch` for CPU scoring, `run_project_baseline.sbatch` as the template for GPU-backed single-project baselines, and `run_baseline_config_batch.sbatch` for config-directory runs. Override `ROOT`, `CONFIG_DIR`, `OUTPUT_DIR`, `PROJECT_DIR`, `OUTPUT_PATH`, `TRACES`, `TOP_K`, and `CONDA_ENV=benchmark` as needed.

Local batch command:

```bash
CONFIG_DIR=configs/baselines OUTPUT_DIR=examples/generated/evaluation_harness/baseline_batch bash scripts/run_baseline_config_batch.sh
```

Recommended future metrics: policy-action accuracy, boundary violation rate, exception-scope accuracy, negative-example suppression, clarification accuracy, evidence recall, latency, storage budget, and degradation as trajectory length grows.
