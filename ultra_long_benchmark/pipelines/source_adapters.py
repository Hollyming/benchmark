from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ultra_long_benchmark.models import CanonicalEvent, ProjectProfile, SourceArtifact, Validity
from ultra_long_benchmark.shared.privacy import privacy_tags, redact
from ultra_long_benchmark.shared.provenance import content_hash
from ultra_long_benchmark.shared.io import read_json, write_json


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


class EmailWorkflowAdapter:
    """Manifest-first adapter for public or licensed longitudinal email traces.

    The adapter is intentionally conservative: email corpora are high-risk for
    privacy and redistribution. Callers must provide explicit provenance,
    license, redistribution, and privacy-review metadata before rows are loaded.
    """

    REQUIRED_MANIFEST_FIELDS = {
        "dataset_name",
        "source_dataset",
        "license",
        "redistribution",
        "privacy_review",
        "project_id",
        "records",
    }

    def __init__(self, manifest_path: Path, redact_sensitive: bool = True):
        self.manifest_path = Path(manifest_path)
        self.redact_sensitive = redact_sensitive

    def load(self) -> AdapterResult:
        manifest = read_json(self.manifest_path)
        self._validate_manifest(manifest)
        source_dataset = manifest["source_dataset"]
        dataset_name = manifest["dataset_name"]
        license_name = manifest["license"]
        records = manifest["records"]
        profile = ProjectProfile(
            project_id=manifest["project_id"],
            title=manifest.get("title") or f"Email workflow trace: {dataset_name}",
            project_goal=manifest.get("project_goal") or "Induce email workflow policies, response habits, approval boundaries, and privacy constraints.",
            user_profile={
                "source": source_dataset,
                "dataset_name": dataset_name,
                "privacy_review": manifest["privacy_review"],
                "redistribution": manifest["redistribution"],
            },
            roles=manifest.get("roles", {}),
            phases=manifest.get("phases", ["email_triage", "draft", "approval", "follow_up"]),
            source_streams=["email"],
            synthetic_context=bool(manifest.get("synthetic_context", False)),
            metadata={
                "manifest_path": str(self.manifest_path),
                "license": license_name,
                "license_url": manifest.get("license_url"),
                "privacy_review": manifest["privacy_review"],
                "redistribution": manifest["redistribution"],
            },
        )
        artifacts: list[SourceArtifact] = []
        events: list[CanonicalEvent] = []
        for index, record in enumerate(records, start=1):
            self._validate_record(record, index)
            record_id = str(record["record_id"])
            raw_content = _format_email_record_content(record)
            tags = sorted(set(privacy_tags(raw_content) + record.get("privacy_tags", [])))
            content = redact(raw_content) if self.redact_sensitive else raw_content
            sender = _redact_metadata_value(record.get("sender"), self.redact_sensitive)
            recipients = [_redact_metadata_value(recipient, self.redact_sensitive) for recipient in record.get("recipients", [])]
            subject = _redact_metadata_value(record.get("subject"), self.redact_sensitive)
            artifact_id = f"artifact_email_{_safe_id(record_id)}"
            event_id = record.get("event_id") or f"event_email_{_safe_id(record_id)}"
            raw_pointer = record.get("raw_pointer") or f"{self.manifest_path}#records/{index}"
            artifacts.append(
                SourceArtifact(
                    artifact_id=artifact_id,
                    source_dataset=source_dataset,
                    artifact_type=record.get("artifact_type", "email_message"),
                    uri=record.get("uri"),
                    license=license_name,
                    content_hash=content_hash(raw_content),
                    raw_pointer=raw_pointer,
                    content=content,
                    metadata={
                        "record_id": record_id,
                        "sender": sender,
                        "recipients": recipients,
                        "subject": subject,
                        "privacy_tags": tags,
                        "redacted": self.redact_sensitive,
                        "manifest_path": str(self.manifest_path),
                    },
                )
            )
            validity = record.get("validity")
            events.append(
                CanonicalEvent(
                    event_id=event_id,
                    project_id=profile.project_id,
                    timestamp=record["timestamp"],
                    source_dataset=source_dataset,
                    actor=record.get("actor") or sender or "unknown_email_actor",
                    event_type=record.get("event_type", "email_message"),
                    content=content,
                    artifacts=[artifact_id],
                    raw_pointer=raw_pointer,
                    project_tags=["email", "workflow"] + record.get("project_tags", []),
                    entities=record.get("entities", []),
                    claims=record.get("claims", []),
                    causal_links=record.get("causal_links", []),
                    supersedes=record.get("supersedes", []),
                    invalidates=record.get("invalidates", []),
                    validity=Validity(**validity) if validity else None,
                    metadata={
                        "record_id": record_id,
                        "sender": sender,
                        "recipients": recipients,
                        "subject": subject,
                        "privacy_tags": tags,
                        "redacted": self.redact_sensitive,
                    },
                )
            )
        return AdapterResult(project_profile=profile, artifacts=artifacts, events=events, seed_path=self.manifest_path)

    @classmethod
    def _validate_manifest(cls, manifest: dict) -> None:
        missing = sorted(cls.REQUIRED_MANIFEST_FIELDS - manifest.keys())
        if missing:
            raise ValueError(f"email workflow manifest missing required fields: {missing}")
        if not manifest.get("license") or str(manifest.get("license")).lower() in {"unknown", "n/a", "none"}:
            raise ValueError("email workflow manifest requires a known license")
        redistribution = manifest.get("redistribution", {})
        if not isinstance(redistribution, dict) or redistribution.get("allowed") is not True:
            raise ValueError("email workflow manifest requires redistribution.allowed=true")
        privacy_review = manifest.get("privacy_review", {})
        if not isinstance(privacy_review, dict) or privacy_review.get("status") != "passed":
            raise ValueError("email workflow manifest requires privacy_review.status='passed'")
        if privacy_review.get("pii_redaction") is not True:
            raise ValueError("email workflow manifest requires privacy_review.pii_redaction=true")
        if not isinstance(manifest.get("records"), list):
            raise ValueError("email workflow manifest records must be a list")

    @staticmethod
    def _validate_record(record: dict, index: int) -> None:
        required = {"record_id", "timestamp", "content"}
        missing = sorted(required - record.keys())
        if missing:
            raise ValueError(f"email workflow record {index} missing required fields: {missing}")


class WorkflowManifestAdapter:
    """Manifest-first adapter for non-email workflow traces.

    This is the safe staging contract for future calendar/docs/chat/browser
    domains. It normalizes already-reviewed records without granting release
    readiness; downstream verifiers and release gates still need to be added per
    domain before any paper claim can include the domain.
    """

    ALLOWED_DOMAINS = {"calendar_workflow", "docs_workflow", "chat_workflow", "browser_web_workflow"}
    DEFAULT_STREAMS = {
        "calendar_workflow": ["calendar"],
        "docs_workflow": ["docs"],
        "chat_workflow": ["chat"],
        "browser_web_workflow": ["browser", "web_search"],
    }
    DEFAULT_PHASES = {
        "calendar_workflow": ["availability", "scheduling", "rescheduling", "follow_up"],
        "docs_workflow": ["draft", "review", "approval", "share"],
        "chat_workflow": ["triage", "escalation", "response", "handoff"],
        "browser_web_workflow": ["search", "compare", "select", "act"],
    }
    DEFAULT_GOALS = {
        "calendar_workflow": "Induce calendar scheduling habits, availability boundaries, approval rules, and rescheduling policies.",
        "docs_workflow": "Induce document review, sharing, approval, and privacy workflow policies.",
        "chat_workflow": "Induce chat escalation, response-channel, notification, and privacy workflow policies.",
        "browser_web_workflow": "Induce browser/web-search decision policies, authorization boundaries, and action constraints.",
    }

    REQUIRED_MANIFEST_FIELDS = {
        "dataset_name",
        "domain",
        "source_dataset",
        "license",
        "redistribution",
        "privacy_review",
        "project_id",
        "records",
    }

    def __init__(self, manifest_path: Path, redact_sensitive: bool = True):
        self.manifest_path = Path(manifest_path)
        self.redact_sensitive = redact_sensitive

    def load(self) -> AdapterResult:
        manifest = read_json(self.manifest_path)
        self._validate_manifest(manifest)
        domain = str(manifest["domain"])
        source_dataset = str(manifest["source_dataset"])
        dataset_name = str(manifest["dataset_name"])
        license_name = str(manifest["license"])
        streams = list(manifest.get("source_streams") or self.DEFAULT_STREAMS[domain])
        profile = ProjectProfile(
            project_id=manifest["project_id"],
            title=manifest.get("title") or f"{domain} trace: {dataset_name}",
            project_goal=manifest.get("project_goal") or self.DEFAULT_GOALS[domain],
            user_profile={
                "source": source_dataset,
                "dataset_name": dataset_name,
                "domain": domain,
                "privacy_review": manifest["privacy_review"],
                "redistribution": manifest["redistribution"],
            },
            roles=manifest.get("roles", {}),
            phases=manifest.get("phases", self.DEFAULT_PHASES[domain]),
            source_streams=streams,
            synthetic_context=bool(manifest.get("synthetic_context", False)),
            metadata={
                "manifest_path": str(self.manifest_path),
                "domain": domain,
                "license": license_name,
                "license_url": manifest.get("license_url"),
                "privacy_review": manifest["privacy_review"],
                "redistribution": manifest["redistribution"],
            },
        )
        artifacts: list[SourceArtifact] = []
        events: list[CanonicalEvent] = []
        for index, record in enumerate(manifest["records"], start=1):
            self._validate_record(record, index)
            record_id = str(record["record_id"])
            raw_content = _format_workflow_record_content(record)
            tags = sorted(set(privacy_tags(raw_content) + record.get("privacy_tags", [])))
            content = redact(raw_content) if self.redact_sensitive else raw_content
            artifact_id = record.get("artifact_id") or f"artifact_{_domain_prefix(domain)}_{_safe_id(record_id)}"
            event_id = record.get("event_id") or f"event_{_domain_prefix(domain)}_{_safe_id(record_id)}"
            raw_pointer = record.get("raw_pointer") or f"{self.manifest_path}#records/{index}"
            artifacts.append(
                SourceArtifact(
                    artifact_id=artifact_id,
                    source_dataset=source_dataset,
                    artifact_type=record.get("artifact_type", _domain_prefix(domain) + "_record"),
                    uri=record.get("uri"),
                    license=license_name,
                    content_hash=content_hash(raw_content),
                    raw_pointer=raw_pointer,
                    content=content,
                    metadata={
                        "record_id": record_id,
                        "domain": domain,
                        "privacy_tags": tags,
                        "redacted": self.redact_sensitive,
                        "manifest_path": str(self.manifest_path),
                    }
                    | dict(record.get("artifact_metadata", {})),
                )
            )
            validity = record.get("validity")
            events.append(
                CanonicalEvent(
                    event_id=event_id,
                    project_id=profile.project_id,
                    timestamp=record["timestamp"],
                    source_dataset=source_dataset,
                    actor=_redact_metadata_value(record.get("actor") or "unknown_workflow_actor", self.redact_sensitive),
                    event_type=record.get("event_type", _domain_prefix(domain) + "_event"),
                    content=content,
                    artifacts=[artifact_id],
                    raw_pointer=raw_pointer,
                    project_tags=sorted(set([domain, _domain_prefix(domain), "workflow"] + record.get("project_tags", []))),
                    entities=[_redact_metadata_value(entity, self.redact_sensitive) for entity in record.get("entities", [])],
                    claims=record.get("claims", []),
                    causal_links=record.get("causal_links", []),
                    supersedes=record.get("supersedes", []),
                    invalidates=record.get("invalidates", []),
                    validity=Validity(**validity) if validity else None,
                    metadata={
                        "record_id": record_id,
                        "domain": domain,
                        "privacy_tags": tags,
                        "redacted": self.redact_sensitive,
                    }
                    | dict(record.get("event_metadata", {})),
                )
            )
        return AdapterResult(project_profile=profile, artifacts=artifacts, events=events, seed_path=self.manifest_path)

    @classmethod
    def _validate_manifest(cls, manifest: dict) -> None:
        missing = sorted(cls.REQUIRED_MANIFEST_FIELDS - manifest.keys())
        if missing:
            raise ValueError(f"workflow manifest missing required fields: {missing}")
        domain = manifest.get("domain")
        if domain not in cls.ALLOWED_DOMAINS:
            raise ValueError(f"workflow manifest domain must be one of {sorted(cls.ALLOWED_DOMAINS)}")
        if not manifest.get("license") or str(manifest.get("license")).lower() in {"unknown", "n/a", "none"}:
            raise ValueError("workflow manifest requires a known license")
        redistribution = manifest.get("redistribution", {})
        if not isinstance(redistribution, dict) or redistribution.get("allowed") is not True:
            raise ValueError("workflow manifest requires redistribution.allowed=true")
        privacy_review = manifest.get("privacy_review", {})
        if not isinstance(privacy_review, dict) or privacy_review.get("status") != "passed":
            raise ValueError("workflow manifest requires privacy_review.status='passed'")
        if privacy_review.get("pii_redaction") is not True:
            raise ValueError("workflow manifest requires privacy_review.pii_redaction=true")
        if not isinstance(manifest.get("records"), list):
            raise ValueError("workflow manifest records must be a list")

    @staticmethod
    def _validate_record(record: dict, index: int) -> None:
        required = {"record_id", "timestamp", "content"}
        missing = sorted(required - record.keys())
        if missing:
            raise ValueError(f"workflow manifest record {index} missing required fields: {missing}")


def validate_workflow_manifest_adapter(
    manifest_path: Path,
    output_path: Path | None = None,
    *,
    adapter: str = "auto",
    redact_sensitive: bool = True,
) -> dict:
    """Validate a manifest-first workflow adapter without exporting raw content."""

    manifest_path = Path(manifest_path)
    manifest = read_json(manifest_path)
    selected_adapter = _select_manifest_adapter(manifest, adapter)
    if selected_adapter == "email":
        result = EmailWorkflowAdapter(manifest_path, redact_sensitive=redact_sensitive).load()
        domain = "email_workflow"
    elif selected_adapter == "workflow":
        result = WorkflowManifestAdapter(manifest_path, redact_sensitive=redact_sensitive).load()
        domain = result.project_profile.metadata.get("domain") or manifest.get("domain")
    else:
        raise ValueError("adapter must be one of: auto, email, workflow")

    artifact_ids = {artifact.artifact_id for artifact in result.artifacts}
    event_artifact_ids = {artifact_id for event in result.events for artifact_id in event.artifacts}
    issues: list[dict[str, str]] = []
    if event_artifact_ids - artifact_ids:
        issues.append({"code": "unknown_event_artifact", "message": "events reference artifacts missing from adapter output"})
    if {event.project_id for event in result.events} - {result.project_profile.project_id}:
        issues.append({"code": "project_id_mismatch", "message": "events are not all bound to the adapter project profile"})

    privacy_tag_counts: dict[str, int] = {}
    for artifact in result.artifacts:
        metadata = artifact.metadata if isinstance(artifact.metadata, dict) else {}
        for tag in metadata.get("privacy_tags", []):
            privacy_tag_counts[str(tag)] = privacy_tag_counts.get(str(tag), 0) + 1
    for event in result.events:
        metadata = event.metadata if isinstance(event.metadata, dict) else {}
        for tag in metadata.get("privacy_tags", []):
            privacy_tag_counts[str(tag)] = privacy_tag_counts.get(str(tag), 0) + 1

    report = {
        "passed": not issues,
        "manifest_path": str(manifest_path),
        "adapter": selected_adapter,
        "domain": domain,
        "project_id": result.project_profile.project_id,
        "root": str(Path.cwd()),
        "summary": {
            "records": len(manifest.get("records", [])) if isinstance(manifest.get("records"), list) else 0,
            "artifacts": len(result.artifacts),
            "events": len(result.events),
            "issues": len(issues),
            "privacy_tag_counts": dict(sorted(privacy_tag_counts.items())),
            "redacted": redact_sensitive,
        },
        "manifest": {
            "bytes": manifest_path.stat().st_size,
            "sha256": _file_sha256(manifest_path),
            "dataset_name": manifest.get("dataset_name"),
            "source_dataset": manifest.get("source_dataset"),
            "license": manifest.get("license"),
            "license_url": manifest.get("license_url"),
            "redistribution": manifest.get("redistribution", {}),
            "privacy_review": manifest.get("privacy_review", {}),
        },
        "project_profile": {
            "title": result.project_profile.title,
            "source_streams": result.project_profile.source_streams,
            "phases": result.project_profile.phases,
            "synthetic_context": result.project_profile.synthetic_context,
        },
        "constraints": {
            "raw_content_exported": False,
            "llm_generation_performed": False,
            "network_access_required": False,
            "release_ready_claim": False,
            "requires_downstream_domain_verifier": True,
        },
        "issues": issues,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def _select_manifest_adapter(manifest: dict, adapter: str) -> str:
    if adapter != "auto":
        return adapter
    domain = manifest.get("domain")
    if domain in WorkflowManifestAdapter.ALLOWED_DOMAINS:
        return "workflow"
    return "email"


def iter_gharchive_json_records(path: Path) -> Iterable[dict]:
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
        suffixes = "".join(path.suffixes).lower()
        if first_non_ws == "{" and suffixes != ".json":
            for line in handle:
                if line.strip():
                    record = json.loads(line)
                    if isinstance(record, dict):
                        yield record
            return
        if first_non_ws == "[":
            data = json.load(handle)
            for record in data:
                if isinstance(record, dict):
                    yield record
            return
        if first_non_ws == "{":
            try:
                data = json.load(handle)
            except json.JSONDecodeError:
                handle.seek(0)
            else:
                if isinstance(data, dict):
                    yield data
                elif isinstance(data, list):
                    for record in data:
                        if isinstance(record, dict):
                            yield record
                return
        for line in handle:
            if line.strip():
                record = json.loads(line)
                if isinstance(record, dict):
                    yield record


def _iter_json_records(path: Path) -> Iterable[dict]:
    yield from iter_gharchive_json_records(path)


def _format_email_record_content(record: dict) -> str:
    fields = []
    if record.get("subject"):
        fields.append(f"Subject: {record['subject']}")
    if record.get("sender"):
        fields.append(f"From: {record['sender']}")
    recipients = record.get("recipients") or []
    if recipients:
        fields.append("To: " + ", ".join(str(recipient) for recipient in recipients))
    fields.append(str(record["content"]))
    return "\n".join(fields)


def _format_workflow_record_content(record: dict) -> str:
    fields = []
    if record.get("title"):
        fields.append(f"Title: {record['title']}")
    if record.get("actor"):
        fields.append(f"Actor: {record['actor']}")
    if record.get("tool"):
        fields.append(f"Tool: {record['tool']}")
    if record.get("action"):
        fields.append(f"Action: {record['action']}")
    fields.append(str(record["content"]))
    return "\n".join(fields)


def _domain_prefix(domain: str) -> str:
    return domain.removesuffix("_workflow")


def _file_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redact_metadata_value(value: object, enabled: bool) -> object:
    if value is None or not enabled:
        return value
    return redact(str(value))


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
    sections = []
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
            body = value.get("body")
            if body and body != title:
                fragments.append(f"body={str(body)[:240]}")
            labels = _github_label_names(value.get("labels"))
            if labels:
                fragments.append("labels=" + "|".join(labels[:8]))
            assignees = _github_actor_logins(value.get("assignees"))
            if assignees:
                fragments.append("assignees=" + "|".join(assignees[:8]))
            assignee = value.get("assignee")
            if isinstance(assignee, dict) and assignee.get("login"):
                fragments.append(f"assignee={assignee['login']}")
            if status:
                fragments.append(f"status={status}")
            if fragments:
                sections.append(f"{key}: " + ", ".join(fragments))
    if sections:
        return "; ".join(sections)
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


def _github_label_names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    labels = []
    for item in value:
        if isinstance(item, dict) and item.get("name"):
            labels.append(str(item["name"]))
        elif isinstance(item, str):
            labels.append(item)
    return labels


def _github_actor_logins(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    logins = []
    for item in value:
        if isinstance(item, dict) and item.get("login"):
            logins.append(str(item["login"]))
        elif isinstance(item, str):
            logins.append(item)
    return logins


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
