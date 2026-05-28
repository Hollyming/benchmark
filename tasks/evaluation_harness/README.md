# evaluation_harness

Skeleton harness for evaluating memory-enabled agents and baselines. The smoke baseline answers gold strings directly and refuses privacy-sensitive queries, which verifies metric plumbing.

Offline demo:

```powershell
python -m ultra_long_benchmark.cli smoke --all
```

Task-only command after queries exist:

```powershell
python tasks/evaluation_harness/scripts/run_demo.py
```

Recommended future metrics: per-capability accuracy, evidence citation F1, refusal accuracy, abstention calibration, latency, storage budget, and degradation as session count increases.

