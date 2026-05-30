from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ultra_long_benchmark.models import PolicyAnnotationPack, model_validate
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_json, write_jsonl


ACCEPTED_DECISIONS = {"accept", "reject", "needs_revision"}
BLOCKING_ISSUE_LABELS = {
    "invented_fact",
    "invented_event",
    "widened_action_boundary",
    "missing_negative_evidence",
    "overbroad_exception",
    "unsafe_future_probe",
    "gold_leakage",
}


def export_policy_rewrite_human_audit_pack(
    batch_validation_report_path: Path,
    output_dir: Path,
    *,
    sample_size: int = 30,
    min_per_candidate_type: int = 1,
    seed: int = 0,
) -> dict[str, Any]:
    """Export a deterministic human-audit packet for validated rewrite proposals.

    This command does not judge the LLM output. It prepares a reproducible
    sample and a decision template so human reviewers can audit grounding,
    action-boundary fidelity, negative-example handling, and future-probe
    quality before a release is claimed as publication-ready.
    """

    batch_validation_report_path = Path(batch_validation_report_path)
    output_dir = Path(output_dir)
    batch_report = read_json(batch_validation_report_path)
    records = _audit_source_records(batch_report)
    selected = _select_audit_records(records, sample_size=sample_size, min_per_candidate_type=min_per_candidate_type, seed=seed)
    audit_items = [_audit_item(record, seed=seed, selection_rank=index) for index, record in enumerate(selected, start=1)]
    decision_templates = [_decision_template(item) for item in audit_items]
    manifest = {
        "audit_pack_id": f"rewrite_human_audit_{_short_hash(str(batch_validation_report_path), str(seed), str(sample_size))}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "batch_validation_report": str(batch_validation_report_path),
        "output_dir": str(output_dir),
        "sample": {
            "seed": seed,
            "sample_size_requested": sample_size,
            "sample_size": len(audit_items),
            "min_per_candidate_type": min_per_candidate_type,
            "population_size": len(records),
            "candidate_type_population": _count_by(record["candidate_type"] for record in records),
            "candidate_type_sample": _count_by(item["candidate_type"] for item in audit_items),
        },
        "files": {
            "audit_items": str(output_dir / "audit_items.jsonl"),
            "audit_decisions_template": str(output_dir / "audit_decisions_template.jsonl"),
            "manifest": str(output_dir / "audit_pack_manifest.json"),
        },
        "review_protocol": {
            "decision_values": sorted(ACCEPTED_DECISIONS),
            "blocking_issue_labels": sorted(BLOCKING_ISSUE_LABELS),
            "required_checks": [
                "policy is fully grounded in supporting evidence",
                "future probe requires policy/action behavior rather than fact recall",
                "proposal action boundary is no broader than source candidate boundary",
                "negative examples remain negative and are not stored as durable habits",
                "expected behavior covers allowed, forbidden, approval, or clarification boundary terms",
            ],
        },
        "constraints": {
            "llm_generation_performed": False,
            "human_review_required_for_final_claim": True,
            "decisions_template_is_unfilled": True,
            "requires_validate_rewrite_human_audit": True,
        },
    }
    write_jsonl(output_dir / "audit_items.jsonl", audit_items)
    write_jsonl(output_dir / "audit_decisions_template.jsonl", decision_templates)
    write_json(output_dir / "audit_pack_manifest.json", manifest)
    return manifest


def validate_policy_rewrite_human_audit(
    audit_pack_dir: Path,
    decisions_path: Path,
    output_path: Path | None = None,
    *,
    min_accept_rate: float = 0.95,
    require_complete: bool = True,
    allow_needs_revision: bool = False,
) -> dict[str, Any]:
    """Validate a completed human audit decision JSONL against an audit pack."""

    audit_pack_dir = Path(audit_pack_dir)
    decisions_path = Path(decisions_path)
    manifest = read_json(audit_pack_dir / "audit_pack_manifest.json")
    items = read_jsonl(audit_pack_dir / "audit_items.jsonl")
    item_by_id = {str(item.get("audit_id")): item for item in items}
    decisions = read_jsonl(decisions_path)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen: set[str] = set()
    normalized_decisions = []

    for row_index, row in enumerate(decisions, start=1):
        audit_id = str(row.get("audit_id", ""))
        decision = str(row.get("decision", "")).strip()
        labels = _string_list(row.get("issue_labels"))
        blocking = bool(row.get("blocking")) or any(label in BLOCKING_ISSUE_LABELS for label in labels)
        normalized = {
            "row_index": row_index,
            "audit_id": audit_id,
            "annotation_id": row.get("annotation_id"),
            "candidate_id": row.get("candidate_id"),
            "decision": decision,
            "issue_labels": labels,
            "blocking": blocking,
            "reviewer_id": row.get("reviewer_id"),
            "notes_present": bool(str(row.get("notes", "")).strip()),
        }
        normalized_decisions.append(normalized)
        if not audit_id:
            issues.append({"code": "missing_audit_id", "row_index": row_index})
            continue
        if audit_id not in item_by_id:
            issues.append({"code": "unknown_audit_id", "row_index": row_index, "audit_id": audit_id})
            continue
        if audit_id in seen:
            issues.append({"code": "duplicate_audit_decision", "row_index": row_index, "audit_id": audit_id})
            continue
        seen.add(audit_id)
        item = item_by_id[audit_id]
        if row.get("annotation_id") and row.get("annotation_id") != item.get("annotation_id"):
            issues.append({"code": "annotation_id_mismatch", "row_index": row_index, "audit_id": audit_id})
        if row.get("candidate_id") and row.get("candidate_id") != item.get("candidate_id"):
            issues.append({"code": "candidate_id_mismatch", "row_index": row_index, "audit_id": audit_id})
        if decision not in ACCEPTED_DECISIONS:
            issues.append({"code": "invalid_decision", "row_index": row_index, "audit_id": audit_id, "decision": decision})
        if decision == "needs_revision" and not allow_needs_revision:
            issues.append({"code": "needs_revision_not_allowed", "row_index": row_index, "audit_id": audit_id})
        unknown_labels = sorted(set(labels) - BLOCKING_ISSUE_LABELS - _nonblocking_issue_labels())
        if unknown_labels:
            warnings.append({"code": "unknown_issue_label", "row_index": row_index, "audit_id": audit_id, "labels": unknown_labels})
        if blocking:
            issues.append({"code": "blocking_human_audit_issue", "row_index": row_index, "audit_id": audit_id, "issue_labels": labels})

    missing = sorted(set(item_by_id) - seen)
    if require_complete and missing:
        issues.append({"code": "missing_audit_decisions", "missing_audit_ids": missing})
    accepted = sum(1 for item in normalized_decisions if item["decision"] == "accept" and item["audit_id"] in item_by_id)
    reviewed = sum(1 for item in normalized_decisions if item["audit_id"] in item_by_id and item["decision"] in ACCEPTED_DECISIONS)
    rejected = sum(1 for item in normalized_decisions if item["decision"] == "reject" and item["audit_id"] in item_by_id)
    needs_revision = sum(1 for item in normalized_decisions if item["decision"] == "needs_revision" and item["audit_id"] in item_by_id)
    accept_rate = accepted / reviewed if reviewed else 0.0
    if reviewed and accept_rate < min_accept_rate:
        issues.append({"code": "accept_rate_below_threshold", "accept_rate": round(accept_rate, 6), "min_accept_rate": min_accept_rate})
    if not reviewed:
        issues.append({"code": "no_valid_audit_decisions"})

    report = {
        "audit_pack_dir": str(audit_pack_dir),
        "decisions_path": str(decisions_path),
        "passed": not issues,
        "issues": issues,
        "warnings": warnings,
        "summary": {
            "items_total": len(items),
            "decisions_total": len(decisions),
            "reviewed": reviewed,
            "accepted": accepted,
            "rejected": rejected,
            "needs_revision": needs_revision,
            "missing": len(missing),
            "accept_rate": round(accept_rate, 6),
            "min_accept_rate": min_accept_rate,
            "require_complete": require_complete,
            "allow_needs_revision": allow_needs_revision,
            "issue_codes": _count_by(issue["code"] for issue in issues),
            "warning_codes": _count_by(warning["code"] for warning in warnings),
        },
        "sample": manifest.get("sample", {}),
        "decisions": normalized_decisions,
        "constraints": {
            "llm_generation_performed": False,
            "human_decisions_supplied": True,
            "requires_source_grounded_rewrite_validation": True,
        },
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def _audit_source_records(batch_report: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for pack_report in batch_report.get("packs", []):
        pack = model_validate(PolicyAnnotationPack, read_json(Path(pack_report["annotation_pack_path"])))
        task_by_annotation = {task.annotation_id: task for task in pack.tasks}
        proposals = {str(row.get("annotation_id")): row for row in read_jsonl(Path(pack_report["proposals_path"]))}
        validation_report = read_json(Path(pack_report["validation_report_path"]))
        validation_by_annotation = {item["annotation_id"]: item for item in validation_report.get("reports", [])}
        for annotation_id, task in task_by_annotation.items():
            proposal = proposals.get(annotation_id)
            validation = validation_by_annotation.get(annotation_id, {})
            if proposal is None:
                continue
            records.append(
                {
                    "repo": task.repo,
                    "pack_id": pack.pack_id,
                    "annotation_pack_path": pack_report["annotation_pack_path"],
                    "proposal_path": pack_report["proposals_path"],
                    "validation_report_path": pack_report["validation_report_path"],
                    "annotation_id": annotation_id,
                    "candidate_id": task.candidate_id,
                    "candidate_type": task.candidate_type,
                    "task": task,
                    "proposal": proposal,
                    "validation": validation,
                }
            )
    return records


def _select_audit_records(
    records: list[dict[str, Any]],
    *,
    sample_size: int,
    min_per_candidate_type: int,
    seed: int,
) -> list[dict[str, Any]]:
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    if min_per_candidate_type < 0:
        raise ValueError("min_per_candidate_type must be non-negative")
    by_type: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_type.setdefault(record["candidate_type"], []).append(record)
    for group in by_type.values():
        group.sort(key=lambda record: _sample_key(record, seed))
    selected_ids: set[str] = set()
    selected: list[dict[str, Any]] = []
    for candidate_type in sorted(by_type):
        for record in by_type[candidate_type][:min_per_candidate_type]:
            if len(selected) >= sample_size:
                break
            selected.append(record)
            selected_ids.add(record["annotation_id"])
        if len(selected) >= sample_size:
            break
    remaining = [record for record in records if record["annotation_id"] not in selected_ids]
    remaining.sort(key=lambda record: _sample_key(record, seed))
    selected.extend(remaining[: max(0, min(sample_size, len(records)) - len(selected))])
    return selected


def _audit_item(record: dict[str, Any], *, seed: int, selection_rank: int) -> dict[str, Any]:
    task = record["task"]
    proposal = record["proposal"]
    validation = record["validation"]
    audit_id = f"audit_{_short_hash(record['pack_id'], record['annotation_id'], str(seed))}"
    return {
        "audit_id": audit_id,
        "selection_rank": selection_rank,
        "repo": record["repo"],
        "pack_id": record["pack_id"],
        "annotation_id": record["annotation_id"],
        "candidate_id": record["candidate_id"],
        "candidate_type": record["candidate_type"],
        "proposal_id": proposal.get("proposal_id"),
        "policy_candidate": task.policy_candidate,
        "rewritten_policy": proposal.get("rewritten_policy"),
        "future_probe_query": proposal.get("future_probe_query"),
        "expected_behavior": proposal.get("expected_behavior", {}),
        "source_action_boundary": _model_dump(task.action_boundary_candidate),
        "proposal_action_boundary": proposal.get("action_boundary", {}),
        "supporting_evidence": [_evidence_for_audit(snippet) for snippet in task.supporting_evidence],
        "negative_evidence": [_evidence_for_audit(snippet) for snippet in task.negative_evidence],
        "positive_event_ids": proposal.get("positive_event_ids", []),
        "negative_event_ids": proposal.get("negative_event_ids", []),
        "validation": {
            "passed": validation.get("passed"),
            "issues": validation.get("issues", []),
            "warnings": validation.get("warnings", []),
            "checks": validation.get("checks", {}),
        },
        "human_review_checklist": list(task.human_review_checklist),
        "audit_questions": [
            "Are all policy claims in rewritten_policy supported by the supplied evidence snippets?",
            "Is proposal_action_boundary equal to or narrower than source_action_boundary?",
            "Does future_probe_query require a future tool-policy action rather than factual recall?",
            "Do expected_behavior.must_include and must_not_include cover allowed/forbidden/approval/clarification boundaries?",
            "If negative_evidence is present, does the proposal avoid turning it into a durable assistant habit?",
        ],
    }


def _decision_template(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "audit_id": item["audit_id"],
        "annotation_id": item["annotation_id"],
        "candidate_id": item["candidate_id"],
        "repo": item["repo"],
        "decision": "",
        "issue_labels": [],
        "blocking": False,
        "reviewer_id": "",
        "notes": "",
    }


def _evidence_for_audit(snippet: Any) -> dict[str, Any]:
    return {
        "event_id": snippet.event_id,
        "timestamp": snippet.timestamp.isoformat(),
        "actor": snippet.actor,
        "event_type": snippet.event_type,
        "content": snippet.content,
        "raw_pointer": snippet.raw_pointer,
        "content_hashes": list(snippet.content_hashes),
        "uri": snippet.uri,
    }


def _sample_key(record: dict[str, Any], seed: int) -> str:
    return _sha256(str(seed), record["pack_id"], record["annotation_id"], record["candidate_id"])


def _short_hash(*parts: str) -> str:
    return _sha256(*parts)[:16]


def _sha256(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _count_by(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None:
        return []
    return [str(value)]


def _nonblocking_issue_labels() -> set[str]:
    return {
        "minor_wording",
        "weak_probe",
        "needs_clearer_expected_behavior",
        "evidence_too_sparse",
        "ambiguous_scope",
    }


def _model_dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)
