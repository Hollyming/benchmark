# release_packaging

Builds release-facing metadata: dataset card, benchmark card, split files, and provenance manifest.

Offline demo:

```powershell
python -m ultra_long_benchmark.cli smoke --all
```

Task-only command after upstream artifacts exist:

```powershell
python tasks/release_packaging/scripts/run_demo.py
```

Outputs:

- `examples/generated/release_packaging/release_manifest.json`
- `examples/generated/release_packaging/splits.json`
- `examples/generated/release_packaging/DATASET_CARD.md`
- `examples/generated/release_packaging/BENCHMARK_CARD.md`

