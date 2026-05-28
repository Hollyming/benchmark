from __future__ import annotations

import hashlib

from ultra_long_benchmark.models import Provenance


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def provenance_for_text(source_id: str, origin: str, text: str, uri: str | None = None, license: str | None = None) -> Provenance:
    return Provenance(
        source_id=source_id,
        origin=origin,
        uri=uri,
        license=license,
        content_hash=content_hash(text),
    )

