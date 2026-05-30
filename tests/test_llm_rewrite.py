import json
from pathlib import Path

import pytest

from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack_batch
from ultra_long_benchmark.pipelines.annotation_pack import export_policy_rewrite_prompts_batch
from ultra_long_benchmark.pipelines.annotation_pack import package_policy_rewrite_jobs
from ultra_long_benchmark.pipelines.llm_rewrite import run_policy_rewrite_llm_job
from ultra_long_benchmark.pipelines.llm_rewrite import run_policy_rewrite_llm_jobs
from ultra_long_benchmark.shared.io import read_json, read_jsonl


def test_run_policy_rewrite_llm_job_writes_schema_valid_proposals(tmp_path: Path, monkeypatch):
    job_dir = _make_rewrite_jobs(tmp_path)
    monkeypatch.setenv("ULB_OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("ULB_OPENAI_API_KEY", "test-key")

    report = run_policy_rewrite_llm_job(
        job_dir / "rewrite_job_0001",
        max_prompts=2,
        caller=_fake_chat_completion,
        model="fake-model",
    )
    proposals = read_jsonl(job_dir / "rewrite_job_0001" / "proposals.jsonl")
    generation_report = read_json(job_dir / "rewrite_job_0001" / "proposals_llm_generation_report.json")

    assert report["passed"] is True
    assert report["provider"]["api_base_host"] == "example.test"
    assert report["provider"]["api_key_present"] is True
    assert report["summary"]["proposals_written"] == 2
    assert len(proposals) == 2
    assert proposals[0]["metadata"]["llm_generation"] is True
    assert proposals[0]["metadata"]["llm_model"] == "fake-model"
    assert "test-key" not in json.dumps(generation_report)


def test_run_policy_rewrite_llm_jobs_limits_batch(tmp_path: Path, monkeypatch):
    job_dir = _make_rewrite_jobs(tmp_path)
    monkeypatch.setenv("ULB_OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("ULB_OPENAI_API_KEY", "test-key")

    report = run_policy_rewrite_llm_jobs(
        job_dir,
        max_jobs=1,
        max_prompts_per_job=1,
        caller=_fake_chat_completion,
        model="fake-model",
    )

    assert report["passed"] is True
    assert report["summary"]["jobs_completed"] == 1
    assert report["summary"]["proposals_written"] == 1
    assert read_json(job_dir / "llm_generation_batch_report.json")["constraints"]["api_key_not_serialized"] is True


def test_run_policy_rewrite_llm_job_merges_existing_rows(tmp_path: Path, monkeypatch):
    job_dir = _make_rewrite_jobs(tmp_path)
    monkeypatch.setenv("ULB_OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("ULB_OPENAI_API_KEY", "test-key")
    target = job_dir / "rewrite_job_0001"

    run_policy_rewrite_llm_job(
        target,
        max_prompts=1,
        caller=_fake_chat_completion,
        model="fake-model",
    )
    report = run_policy_rewrite_llm_job(
        target,
        start_index=1,
        max_prompts=1,
        merge_existing=True,
        caller=_fake_chat_completion,
        model="fake-model",
    )
    proposals = read_jsonl(target / "proposals.jsonl")

    assert report["passed"] is True
    assert report["summary"]["proposals_generated_this_run"] == 1
    assert report["summary"]["existing_proposals_merged"] == 1
    assert len(proposals) == 2
    assert proposals[0]["annotation_id"] != proposals[1]["annotation_id"]


def test_run_policy_rewrite_llm_job_flushes_failed_progress(tmp_path: Path, monkeypatch):
    job_dir = _make_rewrite_jobs(tmp_path)
    monkeypatch.setenv("ULB_OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("ULB_OPENAI_API_KEY", "test-key")
    target = job_dir / "rewrite_job_0001"
    calls = {"count": 0}

    def flaky_chat_completion(endpoint, payload, headers, timeout_seconds):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("transient provider failure")
        return _fake_chat_completion(endpoint, payload, headers, timeout_seconds)

    with pytest.raises(RuntimeError, match="failed prompts"):
        run_policy_rewrite_llm_job(
            target,
            max_prompts=2,
            retries=0,
            caller=flaky_chat_completion,
            model="fake-model",
        )

    proposals = read_jsonl(target / "proposals.jsonl")
    generation_report = read_json(target / "proposals_llm_generation_report.json")

    assert len(proposals) == 1
    assert generation_report["finalized"] is True
    assert generation_report["passed"] is False
    assert generation_report["summary"]["prompts_attempted"] == 2
    assert generation_report["summary"]["proposals_written"] == 1
    assert generation_report["summary"]["failed"] == 1
    assert "test-key" not in json.dumps(generation_report)


def _make_rewrite_jobs(tmp_path: Path) -> Path:
    fixture_path = Path(__file__).parent / "fixtures" / "gharchive_multi_repo_sample.jsonl"
    batch_dir = tmp_path / "packs"
    prompt_dir = tmp_path / "prompt_exports"
    rewrite_job_dir = tmp_path / "rewrite_jobs"
    build_gharchive_annotation_pack_batch(fixture_path, output_dir=batch_dir)
    export_policy_rewrite_prompts_batch(batch_dir, prompt_dir, prompt_version="llm-test")
    package_policy_rewrite_jobs(prompt_dir, rewrite_job_dir, max_prompts_per_job=3)
    return rewrite_job_dir


def _fake_chat_completion(endpoint, payload, headers, timeout_seconds):
    user_content = payload["messages"][1]["content"]
    schema = _extract_schema(user_content)
    boundary = schema["action_boundary"]
    allowed = [item.replace("_", " ") for item in boundary.get("allowed_actions", [])] or ["follow policy"]
    forbidden = [item.replace("_", " ") for item in boundary.get("forbidden_actions", [])] or ["violate policy"]
    proposal = {
        "proposal_id": f"proposal_{schema['candidate_id']}",
        "annotation_id": schema["annotation_id"],
        "candidate_id": schema["candidate_id"],
        "rewritten_policy": f"Follow the grounded workflow policy: {', '.join(allowed)}.",
        "future_probe_query": "What should the assistant do in the future tool workflow under this policy?",
        "expected_behavior": {
            "must_include": allowed,
            "must_not_include": forbidden,
        },
        "positive_event_ids": schema["positive_event_ids"],
        "negative_event_ids": schema["negative_event_ids"],
        "action_boundary": boundary,
        "metadata": schema.get("metadata", {}),
    }
    if schema["negative_event_ids"]:
        proposal["rewritten_policy"] += " This is not a default assistant habit."
    return {
        "choices": [{"message": {"content": json.dumps(proposal)}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10},
    }


def _extract_schema(user_content: str) -> dict:
    marker = "Output schema JSON:\n"
    start = user_content.index(marker) + len(marker)
    tail = user_content[start:]
    decoder = json.JSONDecoder()
    schema, _ = decoder.raw_decode(tail)
    return schema
