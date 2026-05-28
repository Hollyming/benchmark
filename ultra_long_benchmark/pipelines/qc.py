from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List

from ultra_long_benchmark.models import MemoryChallengeQuery, PersonaTimeline, QCReport, Trajectory, model_validate
from ultra_long_benchmark.shared.io import read_jsonl, write_json, write_text
from ultra_long_benchmark.validation import require_unique


def run_quality_control(timelines_path: Path, trajectories_path: Path, queries_path: Path, output_dir: Path) -> QCReport:
    timelines = [model_validate(PersonaTimeline, row) for row in read_jsonl(timelines_path)]
    trajectories = [model_validate(Trajectory, row) for row in read_jsonl(trajectories_path)]
    queries = [model_validate(MemoryChallengeQuery, row) for row in read_jsonl(queries_path)]
    event_ids = [event.event_id for timeline in timelines for event in timeline.events]
    query_event_ids = [event_id for query in queries for event_id in query.evidence_event_ids]
    issues: List[str] = []
    issues.extend(require_unique(event_ids, "event_id"))
    issues.extend(require_unique([q.query_id for q in queries], "query_id"))
    missing = sorted(set(query_event_ids) - set(event_ids))
    issues.extend([f"query evidence references missing event: {event_id}" for event_id in missing])
    if not any(query.privacy_sensitive for query in queries):
        issues.append("no privacy-sensitive challenge queries found")
    report = QCReport(
        task="annotation_and_quality_control",
        generated_at=datetime.now(timezone.utc),
        counts={"timelines": len(timelines), "trajectories": len(trajectories), "queries": len(queries), "events": len(event_ids)},
        issues=issues,
        passed=not issues,
    )
    write_json(output_dir / "qc_report.json", report)
    write_text(output_dir / "human_annotation_template.md", annotation_template())
    return report


def annotation_template() -> str:
    return """# Human Annotation Template

For each query, annotate:

- `answer_correct`: yes/no/partial
- `evidence_sufficient`: yes/no
- `memory_capability`: one of the schema capabilities
- `privacy_policy_followed`: yes/no/not_applicable
- `notes`: free-form rationale with cited event IDs

IAA hook: export two annotator JSONL files with matching `query_id` fields and compute agreement per label.
"""

