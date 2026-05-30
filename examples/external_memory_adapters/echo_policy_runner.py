from __future__ import annotations

from pathlib import Path
from typing import Any

from ultra_long_benchmark.shared.io import read_jsonl, write_jsonl


def run(input_dir: Path, predictions_path: Path, config: dict[str, Any] | None = None, system_name: str = "echo_policy_runner") -> dict[str, Any]:
    """Minimal no-gold external runner example.

    This is a contract fixture, not a competitive baseline. Real Mem0/A-MEM/KG
    adapters should replace the simple event echo with their own memory write,
    retrieval, consolidation, and policy induction logic.
    """

    config = config or {}
    max_events = int(config.get("max_events", 3))
    events = read_jsonl(Path(input_dir) / "events.jsonl")
    probes = read_jsonl(Path(input_dir) / "probes.jsonl")
    events_by_project: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        events_by_project.setdefault(str(event.get("project_id")), []).append(event)

    rows = []
    for probe in probes:
        project_events = events_by_project.get(str(probe.get("project_id")), [])[:max_events]
        event_ids = [str(event.get("event_id")) for event in project_events if event.get("event_id")]
        rows.append(
            {
                "prediction_id": f"pred_{probe['project_id']}_{probe['probe_id']}",
                "project_id": probe["project_id"],
                "probe_id": probe["probe_id"],
                "prediction": (
                    "External runner contract example. Infer the user's workflow policy from the provided no-gold events, "
                    "then choose a conservative tool action that respects routing, approval, and negative-example boundaries."
                ),
                "retrieved_memory_ids": [],
                "retrieved_event_ids": event_ids,
                "retrieved_artifact_ids": [],
                "metadata": {"system": system_name, "example_runner": True, "no_gold_submission_input": True},
            }
        )
    write_jsonl(predictions_path, rows)
    return {"rows_written": len(rows), "max_events": max_events}
