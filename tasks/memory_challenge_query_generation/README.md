# memory_challenge_query_generation

Generates future tool-policy probes from longitudinal user workflow histories. Probes test implicit policy induction, habit generalization, routine ordering, tool-action boundaries, policy exceptions, negative examples, privacy/authorization boundaries, and clarification when authorization is missing.

Offline demo:

```powershell
python -m ultra_long_benchmark.cli smoke --all
```

Task-only command after timelines and trajectories exist:

```powershell
python tasks/memory_challenge_query_generation/scripts/run_demo.py
```

Outputs:

- `examples/generated/memory_challenge_query_generation/queries.jsonl`
