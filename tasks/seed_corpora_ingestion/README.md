# seed_corpora_ingestion

Normalizes local or public seed materials into `SourceDocument` JSONL with provenance and privacy tags.

Offline demo:

```powershell
python tasks/seed_corpora_ingestion/scripts/run_demo.py
```

Inputs:

- `examples/seed_documents.jsonl`
- `configs/ingestion.yaml`

Outputs:

- `examples/generated/seed_corpora_ingestion/source_documents.jsonl`

Optional public-data workflow:

1. Review dataset license and terms.
2. Stage raw files under `data/raw/`.
3. Convert to the seed JSONL fields documented in `configs/ingestion.yaml`.
4. Run ingestion and inspect privacy tags before release.

