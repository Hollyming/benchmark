from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Type

from pydantic import BaseModel

from ultra_long_benchmark.models import MemoryChallengeQuery, PersonaTimeline, SourceDocument, Trajectory, model_validate
from ultra_long_benchmark.shared.io import read_json, read_jsonl


ARTIFACTS: dict[str, tuple[Path, Type[BaseModel]]] = {
    "source_documents": (Path("seed_corpora_ingestion/source_documents.jsonl"), SourceDocument),
    "personas": (Path("persona_life_event_simulation/personas.jsonl"), PersonaTimeline),
    "trajectories": (Path("multi_session_agent_trajectory_generation/trajectories.jsonl"), Trajectory),
    "queries": (Path("memory_challenge_query_generation/queries.jsonl"), MemoryChallengeQuery),
}


def audit_generated(generated_dir: Path) -> dict[str, Any]:
    """Return counts plus schema and QC status for generated benchmark artifacts."""
    generated_dir = Path(generated_dir)
    rows_by_artifact: dict[str, list[dict[str, Any]]] = {}
    schema_status: dict[str, dict[str, Any]] = {}

    for name, (relative_path, model_cls) in ARTIFACTS.items():
        path = generated_dir / relative_path
        rows, status = _load_and_validate_jsonl(path, model_cls)
        rows_by_artifact[name] = rows
        schema_status[name] = status

    counts = _count_artifacts(rows_by_artifact)
    qc_status = _read_qc_status(generated_dir / "annotation_and_quality_control" / "qc_report.json")
    overall_passed = all(status["valid"] for status in schema_status.values()) and qc_status["passed"] is True

    return {
        "generated_dir": str(generated_dir),
        "counts": counts,
        "schema": schema_status,
        "qc": qc_status,
        "passed": overall_passed,
    }


def format_audit_text(report: dict[str, Any]) -> str:
    counts = report["counts"]
    lines = [
        "Generated artifact audit",
        f"generated_dir: {report['generated_dir']}",
        f"passed: {report['passed']}",
        "",
        "Counts:",
    ]
    for key in sorted(counts):
        value = counts[key]
        if isinstance(value, dict):
            rendered = ", ".join(f"{inner_key}={inner_value}" for inner_key, inner_value in sorted(value.items()))
            lines.append(f"- {key}: {rendered}")
        else:
            lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("Schema:")
    for name, status in report["schema"].items():
        detail = "ok" if status["valid"] else "; ".join(status["errors"])
        lines.append(f"- {name}: valid={status['valid']} rows={status['rows']} path={status['path']} {detail}")

    qc = report["qc"]
    lines.append("")
    lines.append(f"QC: present={qc['present']} passed={qc['passed']} issues={len(qc['issues'])}")
    for issue in qc["issues"]:
        lines.append(f"- {issue}")
    return "\n".join(lines)


def _load_and_validate_jsonl(path: Path, model_cls: Type[BaseModel]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    errors: list[str] = []
    try:
        rows = read_jsonl(path)
    except Exception as exc:
        return [], {"path": str(path), "rows": 0, "valid": False, "errors": [f"read failed: {exc}"]}

    if not path.exists():
        errors.append("missing file")

    for index, row in enumerate(rows, start=1):
        try:
            model_validate(model_cls, row)
        except Exception as exc:
            errors.append(f"row {index}: {exc}")

    return rows, {"path": str(path), "rows": len(rows), "valid": not errors, "errors": errors}


def _count_artifacts(rows_by_artifact: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    personas = rows_by_artifact["personas"]
    trajectories = rows_by_artifact["trajectories"]
    queries = rows_by_artifact["queries"]

    events = [event for persona in personas for event in persona.get("events", [])]
    sessions = [session for trajectory in trajectories for session in trajectory.get("sessions", [])]
    messages = [message for session in sessions for message in session.get("messages", [])]
    capability_counts = Counter(query.get("capability", "missing") for query in queries)
    memory_task_counts = Counter(query.get("memory_task", "missing") for query in queries)
    complexity_counts = Counter(feature for trajectory in trajectories for feature in trajectory.get("metadata", {}).get("complexity_features", []))
    experience_component_counts = Counter(feature for trajectory in trajectories for feature in trajectory.get("metadata", {}).get("experience_memory_components", []))

    return {
        "source_documents": len(rows_by_artifact["source_documents"]),
        "personas": len(personas),
        "events": len(events),
        "trajectories": len(trajectories),
        "sessions": len(sessions),
        "messages": len(messages),
        "queries": len(queries),
        "privacy_sensitive_queries": sum(1 for query in queries if query.get("privacy_sensitive")),
        "queries_with_negative_evidence": sum(1 for query in queries if query.get("negative_evidence_event_ids")),
        "queries_with_obsolete_evidence": sum(1 for query in queries if query.get("obsolete_evidence_event_ids")),
        "queries_with_distractors": sum(1 for query in queries if query.get("distractor_event_ids")),
        "capabilities": dict(sorted(capability_counts.items())),
        "memory_tasks": dict(sorted(memory_task_counts.items())),
        "trajectory_complexity_features": dict(sorted(complexity_counts.items())),
        "experience_memory_components": dict(sorted(experience_component_counts.items())),
    }


def _read_qc_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "present": False, "passed": None, "issues": ["missing qc_report.json"]}
    try:
        report = read_json(path)
    except Exception as exc:
        return {"path": str(path), "present": True, "passed": False, "issues": [f"read failed: {exc}"]}

    issues = report.get("issues", [])
    if not isinstance(issues, list):
        issues = ["qc issues field is not a list"]
    return {
        "path": str(path),
        "present": True,
        "passed": report.get("passed") is True,
        "issues": issues,
        "counts": report.get("counts", {}),
        "generated_at": report.get("generated_at"),
    }
