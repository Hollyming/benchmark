# Long-Horizon Stress Profile

This task computes reporting statistics that demonstrate whether a benchmark is genuinely long-horizon rather than merely large.

## Offline demo

```powershell
python -m ultra_long_benchmark.cli smoke --all
python -m ultra_long_benchmark.cli stress
```

Output:

- `examples/generated/evaluation_harness/stress_profile.json`

## Reported quantities

- number of trajectories, sessions, messages, events, and queries;
- per-trajectory temporal horizon in days;
- capability distribution;
- evidence-hop histogram, measuring how far back from the latest event the required evidence lies.

## Paper use

For a full benchmark release, report this profile by split and by scenario. A strong long-memory benchmark should include evidence spanning multiple horizon buckets, not only recent facts.
