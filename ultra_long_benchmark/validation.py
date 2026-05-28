from __future__ import annotations

from pathlib import Path
from typing import Iterable, Type

from pydantic import BaseModel

from ultra_long_benchmark.models import model_validate
from ultra_long_benchmark.shared.io import read_json, read_jsonl


def validate_jsonl(path: Path, model_cls: Type[BaseModel]) -> int:
    rows = read_jsonl(path)
    for row in rows:
        model_validate(model_cls, row)
    return len(rows)


def validate_json_list(path: Path, model_cls: Type[BaseModel]) -> int:
    payload = read_json(path)
    if isinstance(payload, dict):
        payload = payload.get("items", [])
    for row in payload:
        model_validate(model_cls, row)
    return len(payload)


def require_unique(values: Iterable[str], label: str) -> list[str]:
    seen: set[str] = set()
    issues: list[str] = []
    for value in values:
        if value in seen:
            issues.append(f"duplicate {label}: {value}")
        seen.add(value)
    return issues

