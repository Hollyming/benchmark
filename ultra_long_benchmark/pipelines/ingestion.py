from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable, List

from ultra_long_benchmark.models import SourceDocument
from ultra_long_benchmark.shared.io import read_jsonl, write_jsonl
from ultra_long_benchmark.shared.privacy import privacy_tags, redact
from ultra_long_benchmark.shared.provenance import provenance_for_text


def ingest_seed_documents(input_path: Path, output_path: Path, redact_private: bool = True) -> List[SourceDocument]:
    rows = read_jsonl(input_path)
    documents: list[SourceDocument] = []
    for idx, row in enumerate(rows, start=1):
        text = str(row["text"])
        if redact_private:
            text = redact(text)
        doc_id = row.get("doc_id", f"doc_{idx:04d}")
        prov = provenance_for_text(
            source_id=doc_id,
            origin=row.get("origin", "local_seed"),
            text=text,
            uri=row.get("uri"),
            license=row.get("license", "synthetic"),
        )
        documents.append(
            SourceDocument(
                doc_id=doc_id,
                title=row.get("title", f"Seed document {idx}"),
                text=text,
                created_at=date.fromisoformat(row.get("created_at", "2024-01-01")),
                provenance=prov,
                metadata={"privacy_tags": privacy_tags(str(row["text"])), **row.get("metadata", {})},
            )
        )
    write_jsonl(output_path, documents)
    return documents


def docs_to_lookup(documents: Iterable[SourceDocument]) -> dict[str, SourceDocument]:
    return {doc.doc_id: doc for doc in documents}

