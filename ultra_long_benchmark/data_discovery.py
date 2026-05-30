from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
from typing import Any, Iterable

from ultra_long_benchmark.shared.io import write_json


DEFAULT_PUBLIC_ROOTS = [Path("/home/jmzhang/Workspace/data"), Path("/data1/public"), Path("/data1/public/hf")]
HIGH_VALUE_NAME_MARKERS = (
    "gharchive",
    "gh_archive",
    "githubarchive",
    "github_archive",
    "github",
    "enron",
    "avocado",
    "email",
)


def discover_public_data_sources(
    roots: Iterable[Path] | None = None,
    *,
    output_path: Path | None = None,
    max_depth: int = 5,
    max_files: int = 1000,
    sample_records: int = 3,
) -> dict[str, Any]:
    """Discover local public-data candidates for LongUserPolicyBench.

    The scanner is intentionally conservative. It reports GHArchive-compatible
    workflow event files as directly usable, marks code-only GitHub corpora as
    not sufficient for user-policy trajectories, and treats email corpora as
    gated unless they provide the manifest required by EmailWorkflowAdapter.
    """

    root_paths = [Path(root) for root in (roots or DEFAULT_PUBLIC_ROOTS)]
    existing_roots = []
    missing_roots = []
    candidates = []
    scanned_files = 0
    skipped_files = 0
    seen_paths: set[Path] = set()

    for root in root_paths:
        if not root.exists():
            missing_roots.append(str(root))
            continue
        existing_roots.append(str(root))
        for path in _iter_candidate_files(root, max_depth=max_depth):
            resolved = path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            if scanned_files >= max_files:
                skipped_files += 1
                break
            scanned_files += 1
            candidate = _classify_candidate(path, sample_records=sample_records)
            if candidate is not None:
                candidates.append(candidate)

    summary = _summary(candidates)
    report = {
        "roots_requested": [str(root) for root in root_paths],
        "roots_existing": existing_roots,
        "roots_missing": missing_roots,
        "scan_limits": {"max_depth": max_depth, "max_files": max_files, "sample_records": sample_records},
        "summary": summary | {"files_scanned": scanned_files, "files_skipped_after_limit": skipped_files},
        "candidates": sorted(candidates, key=lambda item: (-float(item["confidence"]), item["path"])),
        "usable_sources": [item for item in candidates if item["usable_for_longuserpolicy"] is True],
        "non_usable_but_relevant": [item for item in candidates if item["usable_for_longuserpolicy"] is False],
        "authoritative_source_plan": _authoritative_source_plan(summary),
        "recommended_next_actions": _recommended_next_actions(summary, candidates),
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def _iter_candidate_files(root: Path, *, max_depth: int) -> Iterable[Path]:
    root = root.resolve()
    for current, dirs, files in os.walk(root, topdown=True):
        current_path = Path(current)
        try:
            depth = len(current_path.relative_to(root).parts)
        except ValueError:
            continue
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = sorted(dirs)
        for filename in sorted(files):
            path = current_path / filename
            if path.suffix.lower() in {".lock", ".metadata"}:
                continue
            if any(marker in str(path).lower() for marker in HIGH_VALUE_NAME_MARKERS):
                yield path


def _classify_candidate(path: Path, *, sample_records: int) -> dict[str, Any] | None:
    lowered = str(path).lower()
    evidence: list[str] = []
    samples = _sample_json_records(path, sample_records=sample_records)
    sample_kinds = [_record_kind(record) for record in samples]

    if any(kind == "gharchive_event" for kind in sample_kinds):
        evidence.append("sample record has GHArchive event keys: type/actor/repo/payload/created_at")
        return _candidate(
            path,
            dataset_kind="gharchive_public_events",
            confidence=0.95,
            usable=True,
            evidence=evidence,
            recommended_action="Run gharchive-quality-report, gharchive-window-report, then the GHArchive annotation pipeline.",
            constraints=["public GitHub event stream; repository licenses vary", "do not republish unnecessary raw payloads"],
        )

    if any(kind == "email_workflow_manifest" for kind in sample_kinds):
        evidence.append("manifest matches EmailWorkflowAdapter license/privacy/redistribution gate")
        return _candidate(
            path,
            dataset_kind="email_workflow_manifest",
            confidence=0.9,
            usable=True,
            evidence=evidence,
            recommended_action="Load with EmailWorkflowAdapter and keep privacy/redaction logs with the release.",
            constraints=["requires manifest-declared redistribution", "requires privacy_review.status=passed", "requires pii_redaction=true"],
        )

    if "gharchive" in lowered or "gh_archive" in lowered or "githubarchive" in lowered:
        evidence.append("path name suggests GHArchive but sampled records did not match event schema")
        return _candidate(
            path,
            dataset_kind="possible_gharchive_unverified",
            confidence=0.4,
            usable=False,
            evidence=evidence,
            recommended_action="Inspect file format manually or convert to GHArchive JSONL event rows before use.",
            constraints=["not accepted by current adapter without conversion"],
        )

    if any(marker in lowered for marker in ("enron", "avocado", "email")):
        evidence.append("path name suggests an email corpus but no approved manifest was detected")
        return _candidate(
            path,
            dataset_kind="email_corpus_requires_manifest",
            confidence=0.35,
            usable=False,
            evidence=evidence,
            recommended_action="Create a reviewed EmailWorkflowAdapter manifest with license, redistribution, privacy review, and PII redaction.",
            constraints=["do not load raw email without manifest", "license/privacy review required"],
        )

    if any(kind == "github_code_corpus" for kind in sample_kinds) or "github_sample" in lowered:
        evidence.append("sample/path suggests GitHub code text, not workflow event timeline")
        return _candidate(
            path,
            dataset_kind="github_code_corpus_not_workflow",
            confidence=0.75,
            usable=False,
            evidence=evidence,
            recommended_action="Do not use as a substitute for longitudinal user workflow traces; reserve for unrelated code-context experiments.",
            constraints=["lacks PR/review/CI/user-action timeline"],
        )

    return None


def _sample_json_records(path: Path, *, sample_records: int) -> list[dict[str, Any]]:
    if sample_records <= 0:
        return []
    if path.suffix.lower() not in {".json", ".jsonl", ".gz"} and "".join(path.suffixes[-2:]).lower() not in {".json.gz", ".jsonl.gz"}:
        return []
    opener = gzip.open if path.suffix.lower() == ".gz" else open
    records: list[dict[str, Any]] = []
    try:
        with opener(path, "rt", encoding="utf-8") as handle:
            first = _first_non_whitespace(handle)
            if first is None:
                return []
            handle.seek(0)
            suffixes = "".join(path.suffixes).lower()
            if first == "{" and suffixes != ".json":
                for line in handle:
                    if len(records) >= sample_records:
                        break
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(item, dict):
                        records.append(item)
                return records
            if first == "[":
                data = json.load(handle)
                for item in data[:sample_records] if isinstance(data, list) else []:
                    if isinstance(item, dict):
                        records.append(item)
                return records
            if first == "{":
                try:
                    data = json.load(handle)
                except json.JSONDecodeError:
                    handle.seek(0)
                else:
                    if isinstance(data, dict):
                        return [data]
                    return []
            for line in handle:
                if len(records) >= sample_records:
                    break
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    records.append(item)
    except (UnicodeDecodeError, OSError, EOFError, json.JSONDecodeError):
        return []
    return records


def _first_non_whitespace(handle: Any) -> str | None:
    while True:
        char = handle.read(1)
        if not char:
            return None
        if not char.isspace():
            return char


def _record_kind(record: dict[str, Any]) -> str:
    if _is_gharchive_event_record(record):
        return "gharchive_event"
    if _is_email_workflow_manifest(record):
        return "email_workflow_manifest"
    if _is_github_code_record(record):
        return "github_code_corpus"
    return "unknown"


def _is_gharchive_event_record(record: dict[str, Any]) -> bool:
    return (
        isinstance(record.get("type"), str)
        and isinstance(record.get("actor"), dict)
        and isinstance(record.get("repo"), dict)
        and isinstance(record.get("payload"), dict)
        and isinstance(record.get("created_at"), str)
    )


def _is_email_workflow_manifest(record: dict[str, Any]) -> bool:
    redistribution = record.get("redistribution", {})
    privacy = record.get("privacy_review", {})
    return (
        isinstance(record.get("records"), list)
        and bool(record.get("license"))
        and isinstance(redistribution, dict)
        and redistribution.get("allowed") is True
        and isinstance(privacy, dict)
        and privacy.get("status") == "passed"
        and privacy.get("pii_redaction") is True
    )


def _is_github_code_record(record: dict[str, Any]) -> bool:
    text = record.get("text") or record.get("content") or record.get("code")
    metadata = record.get("meta") or record.get("metadata")
    metadata_text = json.dumps(metadata, sort_keys=True).lower() if isinstance(metadata, dict) else ""
    return isinstance(text, str) and ("github" in metadata_text or "def " in text or "class " in text or "#include" in text)


def _candidate(
    path: Path,
    *,
    dataset_kind: str,
    confidence: float,
    usable: bool,
    evidence: list[str],
    recommended_action: str,
    constraints: list[str],
) -> dict[str, Any]:
    return {
        "path": str(path),
        "dataset_kind": dataset_kind,
        "confidence": confidence,
        "usable_for_longuserpolicy": usable,
        "evidence": evidence,
        "recommended_action": recommended_action,
        "constraints": constraints,
    }


def _summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    for candidate in candidates:
        kind = str(candidate["dataset_kind"])
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {
        "candidates_total": len(candidates),
        "usable_sources": sum(1 for item in candidates if item["usable_for_longuserpolicy"] is True),
        "gharchive_event_sources": by_kind.get("gharchive_public_events", 0),
        "email_manifest_sources": by_kind.get("email_workflow_manifest", 0),
        "github_code_only_sources": by_kind.get("github_code_corpus_not_workflow", 0),
        "by_kind": dict(sorted(by_kind.items())),
    }


def _recommended_next_actions(summary: dict[str, Any], candidates: list[dict[str, Any]]) -> list[str]:
    actions = []
    if summary.get("gharchive_event_sources", 0) <= 0:
        actions.append("No local GHArchive workflow event source was found; stage GHArchive hourly JSON/JSONL/GZ files or BigQuery exports before paper-scale runs.")
    if summary.get("email_manifest_sources", 0) <= 0:
        actions.append("No approved email workflow manifest was found; do not ingest Enron/Avocado-style email until license/privacy manifests are prepared.")
    if summary.get("github_code_only_sources", 0) > 0:
        actions.append("GitHub code corpora were found, but they are not substitutes for longitudinal workflow trajectories.")
    if any(item["dataset_kind"] == "possible_gharchive_unverified" for item in candidates):
        actions.append("Some GHArchive-like paths were unverified; inspect or convert them to standard GHArchive event JSONL before use.")
    return actions


def _authoritative_source_plan(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Curated public/authoritative sources and how the benchmark may use them."""

    return [
        {
            "source": "GHArchive",
            "domain": "GitHub issue/PR/review/CI/release public event stream",
            "reuse_role": "primary reference-grounded workflow timeline for open-source coding and project-maintenance habits",
            "current_local_status": "usable" if int(summary.get("gharchive_event_sources", 0)) > 0 else "not_found_locally",
            "pipeline_entry": "gharchive-build-slice -> gharchive-stage-plan -> gharchive-annotation-pack-batch",
            "license_privacy_notes": "Public event payloads; repository licenses and user privacy vary, so releases should cite event ids and minimize raw payload redistribution.",
        },
        {
            "source": "Enron-style public email corpora",
            "domain": "email communication and thread workflows",
            "reuse_role": "secondary source after license/privacy manifest and redaction review",
            "current_local_status": "usable_manifest_found" if int(summary.get("email_manifest_sources", 0)) > 0 else "manifest_required",
            "pipeline_entry": "EmailWorkflowAdapter manifest -> policy candidate mining",
            "license_privacy_notes": "Do not ingest raw email directly; require redistribution permission, privacy review, and PII redaction manifest.",
        },
        {
            "source": "Avocado/LDC-style enterprise email collections",
            "domain": "enterprise email, attachments, folders, and calendar-like workflow traces",
            "reuse_role": "possible secondary source only if institutional license permits benchmark construction",
            "current_local_status": "license_required",
            "pipeline_entry": "EmailWorkflowAdapter manifest -> policy candidate mining",
            "license_privacy_notes": "Likely license-gated; stop for user approval/license confirmation before use.",
        },
        {
            "source": "AppWorld",
            "domain": "executable personal-app API tasks",
            "reuse_role": "future tool-task substrate for state-based checks after policies are induced from longitudinal traces",
            "current_local_status": "not_integrated",
            "pipeline_entry": "no-gold submission input -> external runner/action trace scorer",
            "license_privacy_notes": "Use as an environment or task substrate; do not replace longitudinal user-history evidence with task-local instructions.",
        },
        {
            "source": "WorkArena / tau-bench style environments",
            "domain": "enterprise web/API workflow execution and policy compliance",
            "reuse_role": "future execution substrate for high-stakes workflow boundary probes",
            "current_local_status": "not_integrated",
            "pipeline_entry": "release probes -> environment runner -> action/state verifier",
            "license_privacy_notes": "Rules are often explicit; LongUserPolicyBench should hide user-specific policies in prior traces instead of task prompts.",
        },
    ]
