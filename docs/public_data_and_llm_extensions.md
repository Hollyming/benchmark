# Public Data and LLM Extensions

The offline smoke path is intentionally self-contained. To extend it:

1. Stage reviewed public data in `data/raw/`.
2. Convert each item into JSONL rows with `doc_id`, `title`, `text`, `created_at`, `origin`, `uri`, and `license`.
3. Run the ingestion stage and inspect `metadata.privacy_tags`.
4. Set `.env` keys only for non-smoke generation.
5. Use provider calls to diversify dialogue wording, then re-run QC and schema validation.

Never commit API keys, raw restricted corpora, or unreviewed personal data.

