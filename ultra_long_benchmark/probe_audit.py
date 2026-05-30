from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_json


DEFAULT_HIGH_OVERLAP_THRESHOLD = 0.8


def audit_project_release_probe_leakage(
    release_dir: Path,
    output_path: Path | None = None,
    *,
    high_overlap_threshold: float = DEFAULT_HIGH_OVERLAP_THRESHOLD,
) -> dict[str, Any]:
    """Audit whether future probe text over-exposes gold policy/action terms."""

    release_dir = Path(release_dir)
    rows = [
        _probe_overlap_row(record["probe"], record["memory_by_id"], project_dir=record["project_dir"])
        for record in _gold_probe_records(release_dir)
    ]

    report = _leakage_report(
        str(release_dir),
        rows,
        high_overlap_threshold=high_overlap_threshold,
        audited_input="project_release_gold_probe_queries",
    )
    if output_path is not None:
        write_json(output_path, report)
    return report


def audit_submission_input_probe_leakage(
    release_dir: Path,
    input_dir: Path,
    output_path: Path | None = None,
    *,
    high_overlap_threshold: float = DEFAULT_HIGH_OVERLAP_THRESHOLD,
) -> dict[str, Any]:
    """Audit public submission-input probes against release gold policy terms."""

    release_dir = Path(release_dir)
    input_dir = Path(input_dir)
    gold_by_key = {
        (record["probe"]["project_id"], record["probe"]["probe_id"]): record
        for record in _gold_probe_records(release_dir)
    }
    rows = []
    missing_gold_keys = []
    for probe in read_jsonl(input_dir / "probes.jsonl"):
        key = (probe.get("project_id"), probe.get("probe_id"))
        record = gold_by_key.get(key)
        if record is None:
            missing_gold_keys.append({"project_id": key[0], "probe_id": key[1]})
            continue
        rows.append(_probe_overlap_row(probe, record["memory_by_id"], project_dir=record["project_dir"], gold_probe=record["probe"]))

    report = _leakage_report(
        str(release_dir),
        rows,
        high_overlap_threshold=high_overlap_threshold,
        audited_input="submission_input_probe_queries",
        input_dir=str(input_dir),
    )
    report["missing_gold_keys"] = missing_gold_keys
    report["summary"]["missing_gold_keys"] = len(missing_gold_keys)
    if output_path is not None:
        write_json(output_path, report)
    return report


def _gold_probe_records(release_dir: Path) -> list[dict[str, Any]]:
    manifest = read_json(release_dir / "project_release_manifest.json")
    records = []
    for project in manifest.get("projects", []):
        project_dir = _resolve_project_dir(release_dir, project.get("project_dir"))
        graph = read_json(project_dir / "memory_graph.json")
        memory_by_id = {str(memory.get("memory_id")): memory for memory in graph.get("memories", [])}
        for probe in read_jsonl(project_dir / "probes.jsonl"):
            records.append({"probe": probe, "memory_by_id": memory_by_id, "project_dir": project_dir})
    return records


def _leakage_report(
    release_dir: str,
    rows: list[dict[str, Any]],
    *,
    high_overlap_threshold: float,
    audited_input: str,
    input_dir: str | None = None,
) -> dict[str, Any]:
    summary = _overlap_summary(rows, high_overlap_threshold=high_overlap_threshold)
    report = {
        "release_dir": release_dir,
        "audited_input": audited_input,
        "high_overlap_threshold": high_overlap_threshold,
        "summary": summary,
        "risk_by_task_type": _risk_by_group(rows, "task_type", high_overlap_threshold=high_overlap_threshold),
        "risk_by_capability": _risk_by_capability(rows, high_overlap_threshold=high_overlap_threshold),
        "high_risk_examples": sorted(
            [row for row in rows if row["expected_overlap"] >= high_overlap_threshold or row["boundary_overlap"] >= high_overlap_threshold],
            key=lambda row: (row["boundary_overlap"], row["expected_overlap"], row["probe_id"]),
            reverse=True,
        )[:25],
        "probe_rows": rows,
        "interpretation": {
            "expected_overlap": "fraction of expected-behavior tokens already present in the audited probe query",
            "boundary_overlap": "fraction of gold action-boundary tokens already present in the audited probe query",
            "use": "High values do not indicate gold-file leakage, but they flag query wording that may make lexical shortcut baselines look stronger than true policy induction systems.",
        },
    }
    if input_dir is not None:
        report["input_dir"] = input_dir
    return report


def _probe_overlap_row(
    probe: dict[str, Any],
    memory_by_id: dict[str, dict[str, Any]],
    *,
    project_dir: Path,
    gold_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gold_probe = gold_probe or probe
    query_tokens = set(_tokens(str(probe.get("query", ""))))
    expected_terms = []
    expected = gold_probe.get("expected_behavior", {})
    if isinstance(expected, dict):
        expected_terms.extend(str(value) for value in expected.get("must_include", []))
        expected_terms.extend(str(value) for value in expected.get("must_not_include", []))
    boundary_terms = []
    evidence = gold_probe.get("evidence", {})
    for memory_id in evidence.get("positive", []) if isinstance(evidence, dict) else []:
        memory = memory_by_id.get(str(memory_id), {})
        boundary = memory.get("action_boundary") or {}
        if not isinstance(boundary, dict):
            continue
        for key in ["allowed_actions", "forbidden_actions", "requires_approval", "requires_clarification", "authorized_tools", "forbidden_tools", "conditions", "exceptions"]:
            boundary_terms.extend(str(value) for value in boundary.get(key, []))
    expected_tokens = set(_tokens(" ".join(expected_terms)))
    boundary_tokens = set(_tokens(" ".join(boundary_terms)))
    return {
        "project_id": probe.get("project_id"),
        "probe_id": probe.get("probe_id"),
        "project_dir": str(project_dir),
        "task_type": probe.get("task_type"),
        "capabilities": probe.get("capabilities", []),
        "query_tokens": len(query_tokens),
        "expected_tokens": len(expected_tokens),
        "boundary_tokens": len(boundary_tokens),
        "expected_overlap": round(len(query_tokens & expected_tokens) / max(1, len(expected_tokens)), 4),
        "boundary_overlap": round(len(query_tokens & boundary_tokens) / max(1, len(boundary_tokens)), 4),
        "expected_overlap_tokens": sorted(query_tokens & expected_tokens),
        "boundary_overlap_tokens": sorted(query_tokens & boundary_tokens),
    }


def _overlap_summary(rows: list[dict[str, Any]], *, high_overlap_threshold: float) -> dict[str, Any]:
    expected_values = [float(row["expected_overlap"]) for row in rows]
    boundary_values = [float(row["boundary_overlap"]) for row in rows]
    return {
        "probes": len(rows),
        "mean_expected_overlap": _mean(expected_values),
        "mean_boundary_overlap": _mean(boundary_values),
        "p50_expected_overlap": _percentile(expected_values, 0.5),
        "p90_expected_overlap": _percentile(expected_values, 0.9),
        "p50_boundary_overlap": _percentile(boundary_values, 0.5),
        "p90_boundary_overlap": _percentile(boundary_values, 0.9),
        "high_expected_overlap_probes": sum(1 for value in expected_values if value >= high_overlap_threshold),
        "high_boundary_overlap_probes": sum(1 for value in boundary_values if value >= high_overlap_threshold),
        "high_any_overlap_probes": sum(
            1
            for row in rows
            if float(row["expected_overlap"]) >= high_overlap_threshold or float(row["boundary_overlap"]) >= high_overlap_threshold
        ),
    }


def _risk_by_group(rows: list[dict[str, Any]], group_key: str, *, high_overlap_threshold: float) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        value = row.get(group_key)
        if value:
            grouped.setdefault(str(value), []).append(row)
    return {group: _overlap_summary(group_rows, high_overlap_threshold=high_overlap_threshold) for group, group_rows in sorted(grouped.items())}


def _risk_by_capability(rows: list[dict[str, Any]], *, high_overlap_threshold: float) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        for capability in row.get("capabilities", []):
            grouped.setdefault(str(capability), []).append(row)
    return {group: _overlap_summary(group_rows, high_overlap_threshold=high_overlap_threshold) for group, group_rows in sorted(grouped.items())}


def _resolve_project_dir(release_dir: Path, value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute() or path.exists():
        return path
    candidate = release_dir / path
    if candidate.exists():
        return candidate
    return path


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    position = q * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return round(ordered[lower] * (1 - fraction) + ordered[upper] * fraction, 4)


def _tokens(value: str) -> list[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "as",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "or",
        "the",
        "to",
        "with",
        "should",
        "agent",
        "assistant",
        "future",
        "use",
        "what",
        "when",
        "under",
        "next",
    }
    humanized = str(value).replace("_", " ").replace("-", " ").lower()
    return [token for token in re.split(r"[^a-z0-9]+", humanized) if token and token not in stopwords]
