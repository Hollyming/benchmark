# External Memory Adapter Contract

External memory baselines should run through the no-gold submission interface:

```bash
python -m ultra_long_benchmark.cli run-external-memory-submission-runner \
  examples/generated/evaluation_harness/gharchive_real_llm_paper_candidate_submission_inputs_hardened \
  --runner examples.external_memory_adapters.echo_policy_runner:run \
  --predictions examples/generated/evaluation_harness/echo_policy_runner_predictions.jsonl \
  --report examples/generated/evaluation_harness/echo_policy_runner_report.json \
  --system-name echo_policy_runner \
  --allow-external-runner
```

The plugin target must use `module:object` syntax. The object may be a function, a class with `run(...)`, or an object with `run(...)`.

Supported callable signature:

```python
def run(input_dir: Path, predictions_path: Path, config: dict, system_name: str) -> dict:
    ...
```

The harness passes only:

- `input_dir`: exported no-gold files (`projects.jsonl`, `artifacts.jsonl`, `events.jsonl`, `probes.jsonl`, `submission_manifest.json`, `prediction_template.jsonl`)
- `predictions_path`: where the plugin must write `ProjectPrediction` JSONL
- `config`: optional JSON config loaded from `--config`
- `system_name`: optional display name

It does not pass the release gold directory, `memory_graph.json`, probe `expected_behavior`, or gold evidence ids. After the plugin returns, the harness validates schema and probe coverage against the no-gold input pack. Scoring against gold remains a separate command.

The included `echo_policy_runner.py` is only a contract example. Competitive Mem0, A-MEM, Graphiti/Zep, or long-context runners should replace its echo logic with real memory construction and policy induction.
