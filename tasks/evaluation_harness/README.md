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

Recommended future metrics: policy-action accuracy, boundary violation rate, exception-scope accuracy, negative-example suppression, clarification accuracy, evidence recall, latency, storage budget, and degradation as trajectory length grows.
