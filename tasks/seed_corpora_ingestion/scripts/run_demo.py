from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ultra_long_benchmark.pipelines.ingestion import ingest_seed_documents


if __name__ == "__main__":
    docs = ingest_seed_documents(
        ROOT / "examples" / "seed_documents.jsonl",
        ROOT / "examples" / "generated" / "seed_corpora_ingestion" / "source_documents.jsonl",
    )
    print(f"wrote {len(docs)} source documents")

