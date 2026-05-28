# memory_challenge_query_generation

Generates benchmark questions that require memory use: direct recall, temporal reasoning, preference drift, contradiction handling, provenance-aware answering, planning, privacy-sensitive refusal, and abstention-ready behavior.

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

