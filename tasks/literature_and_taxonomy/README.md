# literature_and_taxonomy

Maintains seed paper metadata and emits a capability taxonomy for ultra-long memory evaluation.

Offline demo:

```powershell
python tasks/literature_and_taxonomy/scripts/run_demo.py
```

Inputs:

- `configs/paper_seeds.yaml`

Outputs:

- `examples/generated/literature_and_taxonomy/literature_map.json`
- `examples/generated/literature_and_taxonomy/taxonomy.md`

Extension path: replace placeholder seed rows with reviewed paper metadata, then add evidence notes for benchmark capability coverage.

