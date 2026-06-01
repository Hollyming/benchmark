from pathlib import Path

from ultra_long_benchmark.data_discovery import discover_public_data_sources
from ultra_long_benchmark.data_discovery import verify_public_data_discovery_report
from ultra_long_benchmark.source_audit import audit_workflow_data_sources
from ultra_long_benchmark.source_audit import verify_workflow_data_source_audit
from ultra_long_benchmark.shared.io import read_json, write_json, write_jsonl


def test_public_data_discovery_accepts_gharchive_event_source(tmp_path: Path):
    gharchive_path = tmp_path / "gharchive" / "2026-04-01.jsonl"
    write_jsonl(
        gharchive_path,
        [
            {
                "id": "evt_1",
                "type": "PullRequestEvent",
                "actor": {"login": "alice"},
                "repo": {"name": "acme/docs"},
                "payload": {"action": "opened", "pull_request": {"title": "Docs update"}},
                "created_at": "2026-04-01T00:00:00Z",
            }
        ],
    )

    report = discover_public_data_sources([tmp_path], output_path=tmp_path / "discovery.json")

    assert report["summary"]["usable_sources"] == 1
    assert report["summary"]["gharchive_event_sources"] == 1
    assert report["usable_sources"][0]["dataset_kind"] == "gharchive_public_events"
    assert report["usable_sources"][0]["sha256"]
    assert report["usable_sources"][0]["bytes"] > 0
    assert report["authoritative_source_plan"][0]["source"] == "GHArchive"
    assert report["authoritative_source_plan"][0]["current_local_status"] == "usable"
    assert read_json(tmp_path / "discovery.json")["summary"]["usable_sources"] == 1
    assert verify_public_data_discovery_report(tmp_path / "discovery.json")["passed"] is True


def test_public_data_discovery_rejects_github_code_as_workflow_source(tmp_path: Path):
    code_path = tmp_path / "github_sample.jsonl"
    write_jsonl(
        code_path,
        [
            {
                "text": "def add(a, b):\n    return a + b\n",
                "meta": {"source": "github"},
            }
        ],
    )

    report = discover_public_data_sources([tmp_path])

    assert report["summary"]["usable_sources"] == 0
    assert report["summary"]["github_code_only_sources"] == 1
    assert report["candidates"][0]["dataset_kind"] == "github_code_corpus_not_workflow"
    assert any(item["source"] == "AppWorld" for item in report["authoritative_source_plan"])


def test_public_data_discovery_accepts_reviewed_email_manifest(tmp_path: Path):
    manifest_path = tmp_path / "email" / "enron_manifest.json"
    write_json(
        manifest_path,
        {
            "dataset_name": "reviewed_email_fixture",
            "source_dataset": "email_fixture",
            "license": "research redistribution allowed",
            "redistribution": {"allowed": True},
            "privacy_review": {"status": "passed", "pii_redaction": True},
            "project_id": "project_email_fixture",
            "records": [{"record_id": "email_1", "timestamp": "2026-01-01T00:00:00Z", "content": "Please review before sending."}],
        },
    )

    report = discover_public_data_sources([tmp_path])

    assert report["summary"]["usable_sources"] == 1
    assert report["summary"]["email_manifest_sources"] == 1
    assert report["usable_sources"][0]["dataset_kind"] == "email_workflow_manifest"
    email_plan = next(item for item in report["authoritative_source_plan"] if item["source"] == "Enron-style public email corpora")
    assert email_plan["current_local_status"] == "usable_manifest_found"


def test_public_data_discovery_accepts_reviewed_workflow_manifest(tmp_path: Path):
    manifest_path = tmp_path / "calendar" / "calendar_manifest.json"
    write_json(
        manifest_path,
        {
            "dataset_name": "reviewed_calendar_fixture",
            "domain": "calendar_workflow",
            "source_dataset": "calendar_fixture",
            "license": "research redistribution allowed",
            "redistribution": {"allowed": True},
            "privacy_review": {"status": "passed", "pii_redaction": True},
            "project_id": "project_calendar_fixture",
            "records": [{"record_id": "calendar_1", "timestamp": "2026-01-01T00:00:00Z", "content": "Keep deep work blocks clear."}],
        },
    )

    report = discover_public_data_sources([tmp_path])

    assert report["summary"]["usable_sources"] == 1
    assert report["summary"]["calendar_manifest_sources"] == 1
    assert report["usable_sources"][0]["dataset_kind"] == "calendar_workflow_manifest"
    manifest_plan = next(item for item in report["authoritative_source_plan"] if item["source"] == "Manifest-first calendar/docs/chat/browser traces")
    assert manifest_plan["current_local_status"] == "usable_manifest_found"


def test_public_data_discovery_verification_fails_when_candidate_changes(tmp_path: Path):
    gharchive_path = tmp_path / "gharchive" / "2026-04-01.jsonl"
    write_jsonl(
        gharchive_path,
        [
            {
                "id": "evt_1",
                "type": "PullRequestEvent",
                "actor": {"login": "alice"},
                "repo": {"name": "acme/docs"},
                "payload": {"action": "opened", "pull_request": {"title": "Docs update"}},
                "created_at": "2026-04-01T00:00:00Z",
            }
        ],
    )
    discover_public_data_sources([tmp_path], output_path=tmp_path / "discovery.json")
    write_jsonl(
        gharchive_path,
        [
            {
                "id": "evt_2",
                "type": "PullRequestEvent",
                "actor": {"login": "bob"},
                "repo": {"name": "acme/docs"},
                "payload": {"action": "closed", "pull_request": {"title": "Docs update"}},
                "created_at": "2026-04-02T00:00:00Z",
            }
        ],
    )

    report = verify_public_data_discovery_report(tmp_path / "discovery.json")

    assert report["passed"] is False
    assert "public_data_candidate_sha256_mismatch" in report["summary"]["issue_codes"]
    assert report["summary"]["candidates_verified"] == 0


def test_public_data_discovery_verification_fails_when_summary_counts_drift(tmp_path: Path):
    gharchive_path = tmp_path / "gharchive" / "2026-04-01.jsonl"
    write_jsonl(
        gharchive_path,
        [
            {
                "id": "evt_1",
                "type": "PullRequestEvent",
                "actor": {"login": "alice"},
                "repo": {"name": "acme/docs"},
                "payload": {"action": "opened", "pull_request": {"title": "Docs update"}},
                "created_at": "2026-04-01T00:00:00Z",
            }
        ],
    )
    discover_public_data_sources([tmp_path], output_path=tmp_path / "discovery.json")
    discovery = read_json(tmp_path / "discovery.json")
    discovery["summary"]["usable_sources"] = 0
    write_json(tmp_path / "discovery.json", discovery)

    report = verify_public_data_discovery_report(tmp_path / "discovery.json")

    assert report["passed"] is False
    assert "public_data_discovery_summary_usable_sources_mismatch" in report["summary"]["issue_codes"]


def test_public_data_discovery_verification_fails_when_usable_list_drifts(tmp_path: Path):
    gharchive_path = tmp_path / "gharchive" / "2026-04-01.jsonl"
    write_jsonl(
        gharchive_path,
        [
            {
                "id": "evt_1",
                "type": "PullRequestEvent",
                "actor": {"login": "alice"},
                "repo": {"name": "acme/docs"},
                "payload": {"action": "opened", "pull_request": {"title": "Docs update"}},
                "created_at": "2026-04-01T00:00:00Z",
            }
        ],
    )
    discover_public_data_sources([tmp_path], output_path=tmp_path / "discovery.json")
    discovery = read_json(tmp_path / "discovery.json")
    discovery["usable_sources"] = []
    write_json(tmp_path / "discovery.json", discovery)

    report = verify_public_data_discovery_report(tmp_path / "discovery.json")

    assert report["passed"] is False
    assert "public_data_discovery_usable_sources_mismatch" in report["summary"]["issue_codes"]


def test_workflow_data_source_audit_blocks_without_usable_workflow_sources(tmp_path: Path):
    code_path = tmp_path / "github_sample.jsonl"
    write_jsonl(code_path, [{"text": "def add(a, b): return a + b", "meta": {"source": "github"}}])
    discovery = discover_public_data_sources([tmp_path], output_path=tmp_path / "discovery.json")

    report = audit_workflow_data_sources(tmp_path / "discovery.json", output_path=tmp_path / "source_audit.json")

    assert discovery["summary"]["usable_sources"] == 0
    assert report["passed"] is False
    assert "gharchive_source_missing" in report["summary"]["issue_codes"]
    assert "github_code_corpus_not_workflow" in report["summary"]["warning_codes"]
    assert read_json(tmp_path / "source_audit.json")["passed"] is False


def test_workflow_data_source_audit_accepts_usable_gharchive_with_ready_stage_plan(tmp_path: Path):
    gharchive_path = tmp_path / "gharchive" / "2026-04-01.jsonl"
    write_jsonl(
        gharchive_path,
        [
            {
                "id": "evt_1",
                "type": "PullRequestEvent",
                "actor": {"login": "alice"},
                "repo": {"name": "acme/docs"},
                "payload": {"action": "opened", "pull_request": {"title": "Docs update"}},
                "created_at": "2026-04-01T00:00:00Z",
            }
        ],
    )
    discover_public_data_sources([tmp_path], output_path=tmp_path / "discovery.json")
    write_json(
        tmp_path / "stage_plan.json",
        {
            "profile": "paper",
            "decision": {
                "ready_for_annotation_budget": True,
                "recommended_mode": "paper_scale_annotation",
                "blocking_checks": [],
                "rationale": "ready",
            },
            "recommended_next_actions": [],
        },
    )

    report = audit_workflow_data_sources(
        tmp_path / "discovery.json",
        output_path=tmp_path / "source_audit.json",
        gharchive_stage_plan_path=tmp_path / "stage_plan.json",
        require_paper_ready=True,
    )

    assert report["passed"] is True
    assert report["annotation_budget_ready"] is True
    assert report["paper_ready"] is True
    assert report["summary"]["gharchive_sources"] == 1
    assert verify_workflow_data_source_audit(tmp_path / "source_audit.json")["passed"] is True


def test_verify_workflow_data_source_audit_fails_when_discovery_changes(tmp_path: Path):
    gharchive_path = tmp_path / "gharchive" / "2026-04-01.jsonl"
    write_jsonl(
        gharchive_path,
        [
            {
                "id": "evt_1",
                "type": "PullRequestEvent",
                "actor": {"login": "alice"},
                "repo": {"name": "acme/docs"},
                "payload": {"action": "opened", "pull_request": {"title": "Docs update"}},
                "created_at": "2026-04-01T00:00:00Z",
            }
        ],
    )
    discover_public_data_sources([tmp_path], output_path=tmp_path / "discovery.json")
    audit_workflow_data_sources(tmp_path / "discovery.json", output_path=tmp_path / "source_audit.json")
    discovery = read_json(tmp_path / "discovery.json")
    discovery["summary"]["usable_sources"] = 0
    write_json(tmp_path / "discovery.json", discovery)

    report = verify_workflow_data_source_audit(tmp_path / "source_audit.json")

    assert report["passed"] is False
    assert "workflow_source_audit_discovery_verification_not_passed" in report["summary"]["issue_codes"]


def test_verify_workflow_data_source_audit_fails_when_stage_plan_changes(tmp_path: Path):
    gharchive_path = tmp_path / "gharchive" / "2026-04-01.jsonl"
    write_jsonl(
        gharchive_path,
        [
            {
                "id": "evt_1",
                "type": "PullRequestEvent",
                "actor": {"login": "alice"},
                "repo": {"name": "acme/docs"},
                "payload": {"action": "opened", "pull_request": {"title": "Docs update"}},
                "created_at": "2026-04-01T00:00:00Z",
            }
        ],
    )
    discover_public_data_sources([tmp_path], output_path=tmp_path / "discovery.json")
    write_json(
        tmp_path / "stage_plan.json",
        {
            "profile": "paper",
            "decision": {
                "ready_for_annotation_budget": True,
                "recommended_mode": "paper_scale_annotation",
                "blocking_checks": [],
                "rationale": "ready",
            },
            "recommended_next_actions": [],
        },
    )
    audit_workflow_data_sources(
        tmp_path / "discovery.json",
        output_path=tmp_path / "source_audit.json",
        gharchive_stage_plan_path=tmp_path / "stage_plan.json",
        require_paper_ready=True,
    )
    stage_plan = read_json(tmp_path / "stage_plan.json")
    stage_plan["decision"]["ready_for_annotation_budget"] = False
    stage_plan["decision"]["blocking_checks"] = ["events"]
    write_json(tmp_path / "stage_plan.json", stage_plan)

    report = verify_workflow_data_source_audit(tmp_path / "source_audit.json")

    assert report["passed"] is False
    assert "workflow_source_audit_summary_mismatch" in report["summary"]["issue_codes"]


def test_workflow_data_source_audit_counts_non_github_manifests(tmp_path: Path):
    write_json(
        tmp_path / "calendar_manifest.json",
        {
            "dataset_name": "reviewed_calendar_fixture",
            "domain": "calendar_workflow",
            "source_dataset": "calendar_fixture",
            "license": "research redistribution allowed",
            "redistribution": {"allowed": True},
            "privacy_review": {"status": "passed", "pii_redaction": True},
            "project_id": "project_calendar_fixture",
            "records": [{"record_id": "calendar_1", "timestamp": "2026-01-01T00:00:00Z", "content": "Keep deep work blocks clear."}],
        },
    )
    discover_public_data_sources([tmp_path], output_path=tmp_path / "discovery.json")

    report = audit_workflow_data_sources(tmp_path / "discovery.json")

    assert report["summary"]["calendar_manifest_sources"] == 1
    assert report["constraints"]["non_github_domains_require_manifest_first_adapter"] is True


def test_workflow_data_source_audit_blocks_paper_ready_when_stage_plan_not_ready(tmp_path: Path):
    gharchive_path = tmp_path / "gharchive" / "2026-04-01.jsonl"
    write_jsonl(
        gharchive_path,
        [
            {
                "id": "evt_1",
                "type": "PullRequestEvent",
                "actor": {"login": "alice"},
                "repo": {"name": "acme/docs"},
                "payload": {"action": "opened", "pull_request": {"title": "Docs update"}},
                "created_at": "2026-04-01T00:00:00Z",
            }
        ],
    )
    discover_public_data_sources([tmp_path], output_path=tmp_path / "discovery.json")
    write_json(
        tmp_path / "stage_plan.json",
        {
            "profile": "paper",
            "decision": {
                "ready_for_annotation_budget": False,
                "recommended_mode": "expand_or_restage_slice",
                "blocking_checks": ["events"],
                "rationale": "not ready",
            },
            "recommended_next_actions": ["Stage more GHArchive data."],
        },
    )

    report = audit_workflow_data_sources(
        tmp_path / "discovery.json",
        gharchive_stage_plan_path=tmp_path / "stage_plan.json",
        require_paper_ready=True,
    )

    assert report["passed"] is False
    assert report["annotation_budget_ready"] is False
    assert report["paper_ready"] is False
    assert "gharchive_stage_not_ready_for_annotation" in report["summary"]["issue_codes"]
