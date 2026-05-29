from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ultra_long_benchmark.models import CanonicalEvent, ProjectProfile, SourceArtifact, Validity
from ultra_long_benchmark.shared.provenance import content_hash
from ultra_long_benchmark.shared.io import read_json


@dataclass(frozen=True)
class AdapterResult:
    """Normalized output of a source dataset adapter.

    Future adapters for SWE-bench, GitHub issues, arXiv revisions, OpenReview
    reviews, or web search traces should convert their raw records into this
    contract. Downstream grounded construction stages should not care whether
    records came from a manual seed file or a real public dataset.
    """

    project_profile: ProjectProfile
    artifacts: list[SourceArtifact]
    events: list[CanonicalEvent]
    seed_path: Path | None = None


class GitHubIssueCIAdapter:
    """Offline fixture adapter shaped like a GitHub issue/CI dataset adapter.

    This adapter reads checked-in fixture records that mimic GitHub issues,
    CI logs, patch diffs, and review comments. It deliberately avoids network
    access while exercising the same normalization contract a future real
    GitHub/SWE-bench adapter should implement.
    """

    def __init__(self, fixture_path: Path):
        self.fixture_path = Path(fixture_path)

    def load(self) -> AdapterResult:
        fixture = read_json(self.fixture_path)
        profile = ProjectProfile(**fixture["project_profile"])
        event_id_map = fixture.get("event_id_map", {})
        artifacts: list[SourceArtifact] = []
        events: list[CanonicalEvent] = []
        for record in fixture["raw_records"]:
            artifact_id = f"artifact_{record['record_id']}"
            artifacts.append(
                SourceArtifact(
                    artifact_id=artifact_id,
                    source_dataset=record["source_dataset"],
                    artifact_type=record["artifact_type"],
                    uri=record.get("uri"),
                    license=record.get("license"),
                    content_hash=record.get("content_hash") or f"fixture_hash_{record['record_id']}",
                    raw_pointer=record["raw_pointer"],
                    content=record["content"],
                    metadata={"record_id": record["record_id"], "fixture_path": str(self.fixture_path)},
                )
            )
            event_id = event_id_map.get(record["record_id"], f"event_{record['record_id']}")
            validity = record.get("validity")
            events.append(
                CanonicalEvent(
                    event_id=event_id,
                    project_id=profile.project_id,
                    timestamp=record["timestamp"],
                    source_dataset=record["source_dataset"],
                    actor=record["actor"],
                    event_type=record["event_type"],
                    content=record["content"],
                    artifacts=[artifact_id],
                    raw_pointer=record["raw_pointer"],
                    project_tags=record.get("project_tags", []),
                    entities=record.get("entities", []),
                    claims=record.get("claims", []),
                    causal_links=record.get("causal_links", []),
                    supersedes=record.get("supersedes", []),
                    invalidates=record.get("invalidates", []),
                    validity=Validity(**validity) if validity else None,
                    metadata={"record_id": record["record_id"], "artifact_type": record["artifact_type"]},
                )
            )
        return AdapterResult(project_profile=profile, artifacts=artifacts, events=events, seed_path=self.fixture_path)


class GHArchiveEventAdapter:
    """Adapter for locally downloaded GHArchive public GitHub event slices.

    GHArchive publishes hourly JSONL gzip archives of public GitHub events.
    This adapter keeps ingestion offline and deterministic: callers download or
    mount archives separately, then normalize selected records into the common
    artifact/event contract used by grounded benchmark construction.
    """

    def __init__(
        self,
        archive_paths: Path | Iterable[Path],
        project_id: str,
        repo_full_name: str | None = None,
        actor_login: str | None = None,
        max_records: int | None = None,
    ):
        if isinstance(archive_paths, (str, Path)):
            self.archive_paths = [Path(archive_paths)]
        else:
            self.archive_paths = [Path(path) for path in archive_paths]
        self.project_id = project_id
        self.repo_full_name = repo_full_name
        self.actor_login = actor_login
        self.max_records = max_records

    def load(self) -> AdapterResult:
        artifacts: list[SourceArtifact] = []
        events: list[CanonicalEvent] = []
        for path in self.archive_paths:
            for row_number, record in enumerate(_iter_json_records(path), start=1):
                if not self._accepts(record):
                    continue
                artifact_id = f"artifact_gharchive_{_safe_id(str(record.get('id') or f'{path.stem}_{row_number}'))}"
                event_id = f"event_gharchive_{_safe_id(str(record.get('id') or f'{path.stem}_{row_number}'))}"
                content = _summarize_gharchive_event(record)
                normalized_type = _normalize_gharchive_event_type(record)
                raw_pointer = f"{path}#{row_number}"
                artifacts.append(
                    SourceArtifact(
                        artifact_id=artifact_id,
                        source_dataset="gharchive",
                        artifact_type=normalized_type,
                        uri=_event_uri(record),
                        license="GitHub public event stream; repository licenses vary",
                        content_hash=content_hash(json.dumps(record, sort_keys=True)),
                        raw_pointer=raw_pointer,
                        content=content,
                        metadata={
                            "gharchive_event_id": record.get("id"),
                            "github_event_type": record.get("type"),
                            "action": record.get("payload", {}).get("action"),
                            "repo": record.get("repo", {}).get("name"),
                            "actor": record.get("actor", {}).get("login"),
                        },
                    )
                )
                events.append(
                    CanonicalEvent(
                        event_id=event_id,
                        project_id=self.project_id,
                        timestamp=record["created_at"],
                        source_dataset="gharchive",
                        actor=record.get("actor", {}).get("login") or "unknown_github_actor",
                        event_type=normalized_type,
                        content=content,
                        artifacts=[artifact_id],
                        raw_pointer=raw_pointer,
                        project_tags=["github", "public_workflow", normalized_type],
                        entities=_gharchive_entities(record),
                        claims=_gharchive_claims(record),
                        metadata={
                            "gharchive_event_id": record.get("id"),
                            "github_event_type": record.get("type"),
                            "repo": record.get("repo", {}).get("name"),
                        },
                    )
                )
                if self.max_records and len(events) >= self.max_records:
                    return self._result(artifacts, events)
        return self._result(artifacts, events)

    def _accepts(self, record: dict) -> bool:
        if self.repo_full_name and record.get("repo", {}).get("name") != self.repo_full_name:
            return False
        if self.actor_login and record.get("actor", {}).get("login") != self.actor_login:
            return False
        return record.get("type") in {
            "PullRequestEvent",
            "PullRequestReviewEvent",
            "PullRequestReviewCommentEvent",
            "IssueCommentEvent",
            "IssuesEvent",
            "CheckRunEvent",
            "CheckSuiteEvent",
            "StatusEvent",
            "WorkflowRunEvent",
            "PushEvent",
            "CommitCommentEvent",
        }

    def _result(self, artifacts: list[SourceArtifact], events: list[CanonicalEvent]) -> AdapterResult:
        repo_name = self.repo_full_name or "mixed GitHub repositories"
        profile = ProjectProfile(
            project_id=self.project_id,
            title=f"GHArchive workflow slice: {repo_name}",
            project_goal="Induce developer workflow habits, review policies, and CI/merge boundaries from public GitHub event traces.",
            user_profile={"source": "gharchive", "actor_filter": self.actor_login, "repo_filter": self.repo_full_name},
            roles={self.actor_login: "github_actor"} if self.actor_login else {},
            phases=["issue_triage", "review", "ci", "merge"],
            source_streams=["gharchive_public_events"],
            synthetic_context=False,
            metadata={"archive_paths": [str(path) for path in self.archive_paths]},
        )
        seed_path = self.archive_paths[0] if len(self.archive_paths) == 1 else None
        return AdapterResult(project_profile=profile, artifacts=artifacts, events=events, seed_path=seed_path)


class ManualSeedAdapter:
    """Offline adapter for the checked-in manual grounded seed JSON.

    The adapter intentionally performs no network access. It exists as the
    smallest reference implementation of the adapter contract that real dataset
    adapters can mirror: read raw/source records, normalize them into
    SourceArtifact objects, and emit CanonicalEvent records bound to a project.
    """

    def __init__(self, seed_path: Path):
        self.seed_path = Path(seed_path)

    def load(self) -> AdapterResult:
        seed = read_json(self.seed_path)
        profile = ProjectProfile(**seed["project_profile"])
        artifacts = [SourceArtifact(**artifact) for artifact in seed["artifacts"]]
        events = [self._event_from_seed(spec, profile.project_id) for spec in seed["event_specs"]]
        return AdapterResult(project_profile=profile, artifacts=artifacts, events=events, seed_path=self.seed_path)

    @staticmethod
    def _event_from_seed(spec: dict, project_id: str) -> CanonicalEvent:
        data = dict(spec)
        data["project_id"] = project_id
        if data.get("validity") is not None:
            data["validity"] = Validity(**data["validity"])
        return CanonicalEvent(**data)


def _iter_json_records(path: Path) -> Iterable[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        first_non_ws = ""
        while not first_non_ws:
            char = handle.read(1)
            if not char:
                return
            if not char.isspace():
                first_non_ws = char
        handle.seek(0)
        if first_non_ws == "[":
            data = json.load(handle)
            for record in data:
                if isinstance(record, dict):
                    yield record
            return
        for line in handle:
            if line.strip():
                record = json.loads(line)
                if isinstance(record, dict):
                    yield record


def _normalize_gharchive_event_type(record: dict) -> str:
    mapping = {
        "PullRequestEvent": "github_pull_request",
        "PullRequestReviewEvent": "github_pr_review",
        "PullRequestReviewCommentEvent": "github_pr_review_comment",
        "IssueCommentEvent": "github_issue_comment",
        "IssuesEvent": "github_issue",
        "CheckRunEvent": "github_ci_status",
        "CheckSuiteEvent": "github_ci_status",
        "StatusEvent": "github_ci_status",
        "WorkflowRunEvent": "github_ci_status",
        "PushEvent": "github_push",
        "CommitCommentEvent": "github_commit_comment",
    }
    return mapping.get(record.get("type"), "github_event")


def _summarize_gharchive_event(record: dict) -> str:
    payload = record.get("payload", {})
    actor = record.get("actor", {}).get("login") or "unknown actor"
    repo = record.get("repo", {}).get("name") or "unknown repo"
    action = payload.get("action")
    subject = _payload_subject(payload)
    parts = [f"{actor} {record.get('type')}"]
    if action:
        parts.append(f"action={action}")
    parts.append(f"repo={repo}")
    if subject:
        parts.append(subject)
    return "; ".join(parts)


def _payload_subject(payload: dict) -> str:
    for key in ("pull_request", "issue", "review", "comment", "check_run", "check_suite", "workflow_run"):
        value = payload.get(key)
        if isinstance(value, dict):
            title = value.get("title") or value.get("name") or value.get("body") or value.get("state")
            number = value.get("number")
            status = value.get("conclusion") or value.get("status")
            fragments = []
            if number is not None:
                fragments.append(f"number={number}")
            if title:
                fragments.append(f"title={str(title)[:240]}")
            if status:
                fragments.append(f"status={status}")
            if fragments:
                return f"{key}: " + ", ".join(fragments)
    if payload.get("ref"):
        return f"ref={payload['ref']}"
    return ""


def _gharchive_entities(record: dict) -> list[str]:
    payload = record.get("payload", {})
    entities = [value for value in [record.get("repo", {}).get("name"), record.get("actor", {}).get("login")] if value]
    for key in ("pull_request", "issue", "review", "comment", "check_run", "check_suite", "workflow_run"):
        value = payload.get(key)
        if isinstance(value, dict):
            for candidate in (value.get("user", {}), value.get("author_association"), value.get("state"), value.get("conclusion")):
                if isinstance(candidate, dict) and candidate.get("login"):
                    entities.append(candidate["login"])
                elif isinstance(candidate, str):
                    entities.append(candidate)
    return sorted(set(entities))


def _gharchive_claims(record: dict) -> list[str]:
    normalized_type = _normalize_gharchive_event_type(record)
    claims = [normalized_type]
    action = record.get("payload", {}).get("action")
    if action:
        claims.append(f"{normalized_type}_{action}")
    if normalized_type == "github_ci_status":
        claims.append("ci_signal_observed")
    if normalized_type in {"github_pull_request", "github_pr_review", "github_pr_review_comment"}:
        claims.append("pr_workflow_signal")
    return claims


def _event_uri(record: dict) -> str | None:
    payload = record.get("payload", {})
    for key in ("pull_request", "issue", "review", "comment", "check_run", "check_suite", "workflow_run"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value.get("html_url") or value.get("url")
    return None


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_") or "unknown"
