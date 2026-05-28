# annotation_and_quality_control

Runs automatic quality checks and emits a human annotation template with IAA hooks.

Offline demo:

```powershell
python -m ultra_long_benchmark.cli smoke --all
```

Task-only command after upstream artifacts exist:

```powershell
python tasks/annotation_and_quality_control/scripts/run_demo.py
```

Checks include unique IDs, evidence references, typed schema parsing, and the presence of privacy-sensitive refusal examples.

