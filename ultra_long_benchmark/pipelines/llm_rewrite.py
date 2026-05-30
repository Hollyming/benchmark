from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from ultra_long_benchmark.models import PolicyRewriteProposal, model_validate
from ultra_long_benchmark.pipelines.annotation_pack import json_dumps_compact
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_json, write_jsonl


DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "xhigh"


ChatCompletionCaller = Callable[[str, dict[str, Any], dict[str, str], int], dict[str, Any]]


def run_policy_rewrite_llm_job(
    job_dir: Path,
    *,
    output_filename: str = "proposals.jsonl",
    report_path: Path | None = None,
    model: str = DEFAULT_MODEL,
    base_url: str | None = None,
    api_key: str | None = None,
    reasoning_effort: str | None = DEFAULT_REASONING_EFFORT,
    max_prompts: int | None = None,
    start_index: int = 0,
    timeout_seconds: int = 180,
    max_output_tokens: int = 1600,
    retries: int = 2,
    retry_sleep_seconds: float = 2.0,
    use_json_response_format: bool = True,
    temperature: float | None = None,
    overwrite: bool = True,
    merge_existing: bool = False,
    caller: ChatCompletionCaller | None = None,
) -> dict[str, Any]:
    """Run an OpenAI-compatible LLM over one rewrite job shard.

    The runner only fills proposal JSONL rows. It does not mark proposals as
    accepted; downstream `collect-policy-rewrite-job-outputs` and
    `validate-policy-rewrites-batch` remain the release gate.
    """

    job_dir = Path(job_dir)
    job_manifest = read_json(job_dir / "job_manifest.json")
    prompts_path = _resolve_job_file(job_dir, job_manifest.get("prompts_path"), "prompts.jsonl")
    prompts = read_jsonl(prompts_path)
    selected_prompts = prompts[start_index:]
    if max_prompts is not None:
        selected_prompts = selected_prompts[:max_prompts]
    if start_index < 0:
        raise ValueError("start_index must be non-negative")

    output_path = job_dir / output_filename
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"proposal output already exists: {output_path}")
    if not selected_prompts:
        raise ValueError(f"no prompts selected from {prompts_path}")
    report_output_path = report_path or (job_dir / f"{Path(output_filename).stem}_llm_generation_report.json")

    base_url = _resolve_base_url(base_url)
    api_key = _resolve_api_key(api_key)
    endpoint = _chat_completion_endpoint(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "curl/8.5.0",
    }

    rows: list[dict[str, Any]] = []
    prompt_reports: list[dict[str, Any]] = []
    existing_rows = read_jsonl(output_path) if merge_existing and output_path.exists() else []
    used_caller = caller or _call_chat_completion

    def flush_progress(*, finalized: bool) -> dict[str, Any]:
        output_rows = _merge_proposal_rows_by_prompt_order(prompts, existing_rows, rows) if merge_existing else rows
        write_jsonl(output_path, output_rows)
        report = _build_llm_job_report(
            job_dir=job_dir,
            job_manifest=job_manifest,
            prompts_path=prompts_path,
            output_path=output_path,
            output_rows=output_rows,
            rows=rows,
            existing_rows=existing_rows,
            prompt_reports=prompt_reports,
            base_url=base_url,
            model=model,
            reasoning_effort=reasoning_effort,
            use_json_response_format=use_json_response_format,
            api_key=api_key,
            start_index=start_index,
            max_prompts=max_prompts,
            prompts_available=len(prompts),
            prompts_selected=len(selected_prompts),
            output_filename=output_filename,
            finalized=finalized,
        )
        write_json(report_output_path, report)
        return report

    if not merge_existing:
        flush_progress(finalized=False)
    for offset, prompt in enumerate(selected_prompts, start=start_index):
        request_payload = _chat_completion_payload(
            prompt,
            model=model,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
            use_json_response_format=use_json_response_format,
            temperature=temperature,
        )
        started = time.time()
        try:
            response = _call_with_retries(
                used_caller,
                endpoint,
                request_payload,
                headers,
                timeout_seconds,
                retries=retries,
                retry_sleep_seconds=retry_sleep_seconds,
            )
            content = _response_content(response)
            raw_proposal = _extract_json_object(content)
            proposal, coercions = _coerce_rewrite_proposal(raw_proposal, prompt, model=model)
            model_validate(PolicyRewriteProposal, proposal)
            rows.append(proposal)
            prompt_reports.append(
                {
                    "prompt_index": offset,
                    "prompt_id": prompt.get("prompt_id"),
                    "annotation_id": prompt.get("annotation_id"),
                    "candidate_id": prompt.get("candidate_id"),
                    "status": "ok",
                    "elapsed_seconds": round(time.time() - started, 3),
                    "coercions": coercions,
                    "response_usage": response.get("usage", {}),
                }
            )
            flush_progress(finalized=False)
        except Exception as exc:
            prompt_reports.append(
                {
                    "prompt_index": offset,
                    "prompt_id": prompt.get("prompt_id"),
                    "annotation_id": prompt.get("annotation_id"),
                    "candidate_id": prompt.get("candidate_id"),
                    "status": "failed",
                    "elapsed_seconds": round(time.time() - started, 3),
                    "error": str(exc),
                }
            )
            flush_progress(finalized=False)

    report = flush_progress(finalized=True)
    if not report["passed"]:
        raise RuntimeError(f"LLM rewrite job had failed prompts: {report['summary']}")
    return report


def run_policy_rewrite_llm_jobs(
    rewrite_job_dir: Path,
    *,
    output_filename: str = "proposals.jsonl",
    report_path: Path | None = None,
    model: str = DEFAULT_MODEL,
    base_url: str | None = None,
    api_key: str | None = None,
    reasoning_effort: str | None = DEFAULT_REASONING_EFFORT,
    max_jobs: int | None = None,
    max_prompts_per_job: int | None = None,
    timeout_seconds: int = 180,
    max_output_tokens: int = 1600,
    retries: int = 2,
    retry_sleep_seconds: float = 2.0,
    use_json_response_format: bool = True,
    temperature: float | None = None,
    overwrite: bool = True,
    merge_existing: bool = False,
    caller: ChatCompletionCaller | None = None,
) -> dict[str, Any]:
    """Run the LLM proposal filler across a packaged rewrite-job directory."""

    rewrite_job_dir = Path(rewrite_job_dir)
    manifest = read_json(rewrite_job_dir / "rewrite_job_manifest.json")
    jobs = list(manifest.get("jobs", []))
    if max_jobs is not None:
        jobs = jobs[:max_jobs]
    if not jobs:
        raise ValueError(f"no rewrite jobs selected from {rewrite_job_dir}")

    reports = []
    failures = []
    for job in jobs:
        job_dir = _resolve_manifest_job_dir(rewrite_job_dir, job)
        try:
            reports.append(
                run_policy_rewrite_llm_job(
                    job_dir,
                    output_filename=output_filename,
                    model=model,
                    base_url=base_url,
                    api_key=api_key,
                    reasoning_effort=reasoning_effort,
                    max_prompts=max_prompts_per_job,
                    timeout_seconds=timeout_seconds,
                    max_output_tokens=max_output_tokens,
                    retries=retries,
                    retry_sleep_seconds=retry_sleep_seconds,
                    use_json_response_format=use_json_response_format,
                    temperature=temperature,
                    overwrite=overwrite,
                    merge_existing=merge_existing,
                    caller=caller,
                )
            )
        except Exception as exc:
            failures.append({"job_id": job.get("job_id"), "job_dir": str(job_dir), "error": str(exc)})

    report = {
        "rewrite_job_dir": str(rewrite_job_dir),
        "output_filename": output_filename,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": {
            "api_base_host": _safe_base_host(_resolve_base_url(base_url)),
            "model": model,
            "reasoning_effort": reasoning_effort,
            "json_response_format": use_json_response_format,
            "api_key_present": bool(_resolve_api_key(api_key)),
        },
        "passed": not failures and bool(reports),
        "jobs": [
            {
                "job_id": report.get("job_id"),
                "job_dir": report.get("job_dir"),
                "output_path": report.get("output_path"),
                "passed": report.get("passed"),
                "summary": report.get("summary", {}),
            }
            for report in reports
        ],
        "failures": failures,
        "summary": {
            "jobs_selected": len(jobs),
            "jobs_completed": len(reports),
            "jobs_failed": len(failures),
            "proposals_written": sum(report["summary"]["proposals_written"] for report in reports),
            "prompt_failures": sum(report["summary"]["failed"] for report in reports),
        },
        "constraints": {
            "llm_generation_performed": True,
            "api_key_not_serialized": True,
            "requires_collect_policy_rewrite_job_outputs": output_filename == "proposals.jsonl",
            "requires_validate_policy_rewrites_batch": True,
        },
    }
    write_json(report_path or (rewrite_job_dir / "llm_generation_batch_report.json"), report)
    if not report["passed"]:
        raise RuntimeError(f"LLM rewrite batch had failed jobs: {report['summary']} failures={failures}")
    return report


def _resolve_job_file(job_dir: Path, raw_path: Any, default_name: str) -> Path:
    if raw_path:
        path = Path(str(raw_path))
        if path.is_absolute() or path.exists():
            return path
        by_name = job_dir / path.name
        if by_name.exists():
            return by_name
        return job_dir / path
    return job_dir / default_name


def _resolve_manifest_job_dir(rewrite_job_dir: Path, job: dict[str, Any]) -> Path:
    raw = job.get("job_dir")
    if raw:
        path = Path(str(raw))
        if path.is_absolute() or path.exists():
            return path
        by_name = rewrite_job_dir / path.name
        if by_name.exists():
            return by_name
        return rewrite_job_dir / path
    return rewrite_job_dir / str(job.get("job_id"))


def _build_llm_job_report(
    *,
    job_dir: Path,
    job_manifest: dict[str, Any],
    prompts_path: Path,
    output_path: Path,
    output_rows: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    existing_rows: list[dict[str, Any]],
    prompt_reports: list[dict[str, Any]],
    base_url: str,
    model: str,
    reasoning_effort: str | None,
    use_json_response_format: bool,
    api_key: str,
    start_index: int,
    max_prompts: int | None,
    prompts_available: int,
    prompts_selected: int,
    output_filename: str,
    finalized: bool,
) -> dict[str, Any]:
    failures = sum(1 for item in prompt_reports if item["status"] != "ok")
    success_count = sum(1 for item in prompt_reports if item["status"] == "ok")
    passed = finalized and bool(rows) and len(prompt_reports) == prompts_selected and failures == 0
    return {
        "job_dir": str(job_dir),
        "job_id": job_manifest.get("job_id"),
        "prompts_path": str(prompts_path),
        "output_path": str(output_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "finalized": finalized,
        "passed": passed,
        "success_count": success_count,
        "failure_count": failures,
        "total_prompts": prompts_selected,
        "provider": {
            "api_base_host": _safe_base_host(base_url),
            "model": model,
            "reasoning_effort": reasoning_effort,
            "json_response_format": use_json_response_format,
            "api_key_present": bool(api_key),
        },
        "selection": {
            "start_index": start_index,
            "max_prompts": max_prompts,
            "prompts_available": prompts_available,
            "prompts_selected": prompts_selected,
        },
        "summary": {
            "prompts_selected": prompts_selected,
            "prompts_attempted": len(prompt_reports),
            "proposals_written": len(output_rows),
            "proposals_generated_this_run": len(rows),
            "existing_proposals_merged": len(existing_rows),
            "failed": failures,
            "coercions_total": sum(len(item.get("coercions", [])) for item in prompt_reports),
        },
        "prompts": prompt_reports,
        "constraints": {
            "llm_generation_performed": True,
            "api_key_not_serialized": True,
            "requires_collect_policy_rewrite_job_outputs": output_filename == "proposals.jsonl",
            "requires_validate_policy_rewrites_batch": True,
        },
    }


def _resolve_base_url(base_url: str | None) -> str:
    value = base_url or os.environ.get("ULB_OPENAI_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
    if not value:
        raise RuntimeError("missing OpenAI-compatible base URL; set ULB_OPENAI_BASE_URL or OPENAI_BASE_URL")
    return value.rstrip("/")


def _resolve_api_key(api_key: str | None) -> str:
    value = api_key or os.environ.get("ULB_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not value:
        raise RuntimeError("missing OpenAI-compatible API key; set ULB_OPENAI_API_KEY or OPENAI_API_KEY")
    return value


def _chat_completion_endpoint(base_url: str) -> str:
    if base_url.endswith("/chat/completions"):
        return base_url
    return base_url.rstrip("/") + "/chat/completions"


def _safe_base_host(base_url: str) -> str:
    parsed = urlparse(base_url)
    return parsed.netloc or parsed.path.split("/")[0]


def _chat_completion_payload(
    prompt: dict[str, Any],
    *,
    model: str,
    reasoning_effort: str | None,
    max_output_tokens: int,
    use_json_response_format: bool,
    temperature: float | None,
) -> dict[str, Any]:
    user_prompt = "\n".join(
        [
            str(prompt.get("user_prompt", "")),
            "Output schema JSON:",
            json_dumps_compact(prompt.get("output_schema", {})),
            "Return only one valid JSON object. Use exact fixed identifiers and event ids from the schema.",
        ]
    )
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": str(prompt.get("system_prompt", ""))},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_output_tokens,
    }
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    if use_json_response_format:
        payload["response_format"] = {"type": "json_object"}
    if temperature is not None:
        payload["temperature"] = temperature
    return payload


def _call_with_retries(
    caller: ChatCompletionCaller,
    endpoint: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: int,
    *,
    retries: int,
    retry_sleep_seconds: float,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return caller(endpoint, payload, headers, timeout_seconds)
        except Exception as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(retry_sleep_seconds * (attempt + 1))
    raise RuntimeError(str(last_error)) from last_error


def _call_chat_completion(endpoint: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: int) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"chat completion HTTP {exc.code}: {body[:1000]}") from exc


def _response_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("chat completion response had no choices")
    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
        text = "\n".join(part for part in text_parts if part)
        if text.strip():
            return text
    raise RuntimeError("chat completion response did not contain text content")


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").strip()
        if stripped.endswith("```"):
            stripped = stripped[:-3].strip()
    decoder = json.JSONDecoder()
    start = stripped.find("{")
    if start < 0:
        raise ValueError("model output did not contain a JSON object")
    obj, _ = decoder.raw_decode(stripped[start:])
    if not isinstance(obj, dict):
        raise ValueError("model output JSON was not an object")
    return obj


def _coerce_rewrite_proposal(raw: dict[str, Any], prompt: dict[str, Any], *, model: str) -> tuple[dict[str, Any], list[str]]:
    schema = prompt.get("output_schema", {})
    proposal = dict(raw)
    coercions: list[str] = []
    for field in ("annotation_id", "candidate_id"):
        expected = prompt.get(field) or schema.get(field)
        if proposal.get(field) != expected:
            proposal[field] = expected
            coercions.append(field)
    if not proposal.get("proposal_id"):
        proposal["proposal_id"] = f"proposal_{_safe_id(str(proposal.get('candidate_id') or prompt.get('candidate_id')))}"
        coercions.append("proposal_id")
    if not proposal.get("positive_event_ids"):
        proposal["positive_event_ids"] = schema.get("positive_event_ids", [])
        coercions.append("positive_event_ids")
    if "negative_event_ids" not in proposal:
        proposal["negative_event_ids"] = schema.get("negative_event_ids", [])
        coercions.append("negative_event_ids")
    if not proposal.get("action_boundary"):
        proposal["action_boundary"] = schema.get("action_boundary", {})
        coercions.append("action_boundary")
    if not isinstance(proposal.get("expected_behavior"), dict):
        proposal["expected_behavior"] = {"must_include": [], "must_not_include": []}
        coercions.append("expected_behavior")
    else:
        expected_behavior = dict(proposal["expected_behavior"])
        expected_behavior.setdefault("must_include", [])
        expected_behavior.setdefault("must_not_include", [])
        proposal["expected_behavior"] = expected_behavior
    _fill_expected_behavior_from_boundary(proposal)
    metadata = dict(proposal.get("metadata") or {})
    metadata.update(
        {
            "pack_id": prompt.get("pack_id"),
            "prompt_id": prompt.get("prompt_id"),
            "prompt_version": prompt.get("prompt_version"),
            "source_prompt_path": prompt.get("source_prompt_path"),
            "llm_model": model,
            "llm_generation": True,
        }
    )
    proposal["metadata"] = metadata
    proposal["pack_id"] = prompt.get("pack_id")
    return proposal, coercions


def _merge_proposal_rows_by_prompt_order(
    prompts: list[dict[str, Any]],
    existing_rows: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_annotation: dict[str, dict[str, Any]] = {}
    for row in existing_rows + new_rows:
        annotation_id = str(row.get("annotation_id") or "")
        if annotation_id:
            by_annotation[annotation_id] = row
    ordered = []
    prompt_annotation_ids = [str(prompt.get("annotation_id") or "") for prompt in prompts]
    for annotation_id in prompt_annotation_ids:
        row = by_annotation.pop(annotation_id, None)
        if row is not None:
            ordered.append(row)
    ordered.extend(by_annotation.values())
    return ordered


def _fill_expected_behavior_from_boundary(proposal: dict[str, Any]) -> None:
    expected = proposal.get("expected_behavior")
    boundary = proposal.get("action_boundary")
    if not isinstance(expected, dict) or not isinstance(boundary, dict):
        return
    must_include = _coerce_string_list(expected.get("must_include"))
    must_not_include = _coerce_string_list(expected.get("must_not_include"))
    for action in boundary.get("allowed_actions", []) + boundary.get("requires_approval", []) + boundary.get("requires_clarification", []):
        _append_unique(must_include, str(action).replace("_", " "))
    for action in boundary.get("forbidden_actions", []):
        _append_unique(must_not_include, str(action).replace("_", " "))
    expected["must_include"] = must_include
    expected["must_not_include"] = must_not_include
    proposal["expected_behavior"] = expected


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None:
        return []
    return [str(value)]


def _append_unique(values: list[str], item: str) -> None:
    normalized = {value.lower() for value in values}
    if item and item.lower() not in normalized:
        values.append(item)


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")
