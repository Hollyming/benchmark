from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from ultra_long_benchmark.shared.io import read_json
from ultra_long_benchmark.shared.io import write_json


DEFAULT_CLAIM_LINT_PATHS = [
    "README.md",
    "docs/comp_research_mem_alignment.md",
    "docs/evaluation_protocol.md",
    "LongUserPolicyBench：长期用户策略与习惯归纳Benchmark方案.md",
]

BLOCKED_CLAIM_PATTERNS = [
    {
        "claim_id": "multi_domain_office_release",
        "message": "Text appears to claim the current release is multi-domain across office/web workflows.",
        "patterns": [
            r"current\s+(?:paper[- ]candidate\s+)?release.{0,80}covers.{0,80}email/calendar/docs/chat/browser",
            r"current\s+(?:paper[- ]candidate\s+)?release.{0,80}(?:multi[- ]domain|office[- ]workflow)",
            r"multi[- ]domain.{0,80}email/calendar/docs/chat/browser(?:/web-search)?.{0,80}(?:release|benchmark)",
        ],
    },
    {
        "claim_id": "reviewed_real_email_workflow_release",
        "message": "Text appears to claim reviewed real email workflow coverage.",
        "patterns": [
            r"current\s+(?:paper[- ]candidate\s+)?release.{0,80}(?:includes|covers).{0,80}(?:reviewed\s+)?real\s+email\s+workflow",
            r"reviewed\s+real\s+email\s+workflow.{0,80}(?:release|coverage|data)",
            r"email\s+workflow.{0,80}(?:release[- ]ready|released|covered)",
        ],
    },
    {
        "claim_id": "human_audited_rewrite_quality",
        "message": "Text appears to claim LLM rewrite quality has passed human audit.",
        "patterns": [
            r"(?:human[- ]audited|human\s+audited).{0,80}(?:rewrite|LLM)",
            r"(?:LLM\s+)?rewrite\s+quality.{0,80}(?:passed|passes).{0,80}human\s+audit",
        ],
    },
    {
        "claim_id": "executed_sota_memory_baselines",
        "message": "Text appears to claim SOTA memory baselines have executed.",
        "patterns": [
            r"(?:Mem0|A-MEM|Graphiti).{0,100}(?:executed|run|scored|results).{0,100}(?:SOTA|baseline)",
            r"SOTA\s+memory\s+baselines?.{0,80}(?:executed|run|scored|complete)",
        ],
    },
    {
        "claim_id": "original_query_scores_as_sota",
        "message": "Text appears to treat original-query shortcut-sensitive scores as SOTA evidence.",
        "patterns": [
            r"original[- ]query.{0,100}(?:SOTA|state[- ]of[- ]the[- ]art)",
            r"memory[- ]profile\s+score.{0,100}(?:SOTA|state[- ]of[- ]the[- ]art)",
        ],
    },
]

SAFE_CONTEXT_TERMS = [
    "do not",
    "don't",
    "cannot",
    "can not",
    "must not",
    "not yet",
    "not a",
    "not currently",
    "not release-ready",
    "blocked",
    "block",
    "warning",
    "caveat",
    "planned",
    "pending",
    "requires",
    "until",
    "only",
    "不是",
    "不能",
    "不得",
    "不支持",
    "尚未",
    "仍未",
    "未完成",
    "缺失",
    "阻断",
    "阻塞",
    "后续",
    "当前只有",
    "仍为",
    "不是",
    "只说明",
]


def lint_paper_claims(
    paths: list[Path | str] | None = None,
    output_path: Path | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Lint paper-facing docs for affirmative claims blocked by claim-boundary audit."""

    root = Path(root or Path.cwd())
    target_paths = [Path(path) for path in (paths or DEFAULT_CLAIM_LINT_PATHS)]
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    file_checks: dict[str, dict[str, Any]] = {}
    allowed_mentions: list[dict[str, Any]] = []

    compiled = [
        {
            "claim_id": item["claim_id"],
            "message": item["message"],
            "patterns": [re.compile(pattern, flags=re.IGNORECASE) for pattern in item["patterns"]],
        }
        for item in BLOCKED_CLAIM_PATTERNS
    ]

    for raw_path in target_paths:
        path = _resolve_path(raw_path, root)
        key = str(raw_path)
        if not path.exists():
            file_checks[key] = {"status": "fail", "path": str(path), "issues": ["file missing"]}
            _issue(issues, "claim_lint_file_missing", "claim-lint target file is missing", path)
            continue
        text = path.read_text(encoding="utf-8")
        file_issues: list[dict[str, Any]] = []
        file_allowed = 0
        lines = text.splitlines()
        for line_number, line in enumerate(lines, start=1):
            context = _context(lines, line_number)
            for item in compiled:
                for pattern in item["patterns"]:
                    match = pattern.search(line)
                    if match is None:
                        continue
                    mention = {
                        "claim_id": item["claim_id"],
                        "path": str(path),
                        "line": line_number,
                        "match": match.group(0),
                        "context": line.strip(),
                    }
                    if _safe_context(context):
                        file_allowed += 1
                        if len(allowed_mentions) < 50:
                            allowed_mentions.append(mention)
                        continue
                    finding = mention | {
                        "code": "blocked_claim_affirmed",
                        "message": item["message"],
                    }
                    file_issues.append(finding)
                    issues.append(finding)
        file_checks[key] = {
            "status": "pass" if not file_issues else "fail",
            "path": str(path),
            "issues": file_issues,
            "allowed_blocked_claim_mentions": file_allowed,
            "lines": len(lines),
            "bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
        }

    summary = {
        "files_total": len(target_paths),
        "files_scanned": sum(1 for check in file_checks.values() if check["status"] in {"pass", "fail"} and Path(check["path"]).exists()),
        "files_hashed": sum(1 for check in file_checks.values() if "sha256" in check),
        "issues": len(issues),
        "warnings": len(warnings),
        "issue_codes": sorted({issue["code"] for issue in issues}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
        "allowed_blocked_claim_mentions": sum(check.get("allowed_blocked_claim_mentions", 0) for check in file_checks.values()),
    }
    report = {
        "passed": not issues,
        "root": str(root),
        "summary": summary,
        "checks": file_checks,
        "allowed_mentions": allowed_mentions,
        "issues": issues,
        "warnings": warnings,
        "blocked_claim_patterns": [
            {"claim_id": item["claim_id"], "message": item["message"], "patterns": item["patterns"]}
            for item in BLOCKED_CLAIM_PATTERNS
        ],
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def verify_paper_claim_lint_report(
    report_path: Path,
    output_path: Path | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Verify that a paper-claim lint report still matches the scanned docs."""

    report_path = Path(report_path)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    file_results: dict[str, dict[str, Any]] = {}

    if not report_path.exists():
        report = {
            "passed": False,
            "report_path": str(report_path),
            "summary": {
                "files_total": 0,
                "files_verified": 0,
                "issues": 1,
                "warnings": 0,
                "issue_codes": ["claim_lint_report_missing"],
                "warning_codes": [],
            },
            "checks": {},
            "issues": [{"code": "claim_lint_report_missing", "message": "paper claim lint report is missing", "path": str(report_path)}],
            "warnings": [],
        }
        if output_path is not None:
            write_json(output_path, report)
        return report

    source = read_json(report_path)
    source_root = Path(root or source.get("root") or report_path.resolve().parent)
    source_summary = source.get("summary", {}) if isinstance(source.get("summary"), dict) else {}
    if source.get("passed") is not True or int(source_summary.get("issues", 0)) > 0:
        _issue(issues, "claim_lint_not_passed", "paper claim lint did not pass", report_path)

    checks = source.get("checks", {})
    if not isinstance(checks, dict) or not checks:
        _issue(issues, "claim_lint_checks_missing", "paper claim lint report has no file checks", report_path)
        checks = {}

    for name, expected in sorted(checks.items()):
        if not isinstance(expected, dict):
            _issue(issues, "claim_lint_check_invalid", f"claim-lint check is not an object: {name}", report_path)
            continue
        path = _resolve_path(expected.get("path") or name, source_root)
        result = {
            "path": str(path),
            "expected_status": expected.get("status"),
            "expected_sha256": expected.get("sha256"),
            "expected_bytes": expected.get("bytes"),
            "actual_sha256": None,
            "actual_bytes": None,
            "passed": True,
        }
        file_results[name] = result
        if not path.exists():
            result["passed"] = False
            _issue(issues, "claim_lint_file_missing", f"claim-lint source file is missing: {name}", path)
            continue
        if not expected.get("sha256"):
            result["passed"] = False
            _issue(issues, "claim_lint_digest_missing", f"claim-lint report does not record a source digest: {name}", path)
            continue
        actual_sha256 = _file_sha256(path)
        actual_bytes = path.stat().st_size
        result["actual_sha256"] = actual_sha256
        result["actual_bytes"] = actual_bytes
        if expected.get("sha256") != actual_sha256:
            result["passed"] = False
            _issue(issues, "claim_lint_source_sha256_mismatch", f"claim-lint source file changed: {name}", path)
        if expected.get("bytes") is not None and expected.get("bytes") != actual_bytes:
            result["passed"] = False
            _issue(issues, "claim_lint_source_bytes_mismatch", f"claim-lint source file size changed: {name}", path)

    summary = {
        "files_total": len(file_results),
        "files_verified": sum(1 for result in file_results.values() if result["passed"]),
        "source_issues": int(source_summary.get("issues", 0)),
        "issues": len(issues),
        "warnings": len(warnings),
        "issue_codes": sorted({issue["code"] for issue in issues}),
        "warning_codes": sorted({warning["code"] for warning in warnings}),
    }
    report = {
        "passed": not issues,
        "report_path": str(report_path),
        "root": str(source_root),
        "source_summary": source_summary,
        "summary": summary,
        "checks": file_results,
        "issues": issues,
        "warnings": warnings,
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def _safe_context(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in SAFE_CONTEXT_TERMS)


def _context(lines: list[str], line_number: int) -> str:
    start = max(0, line_number - 2)
    end = min(len(lines), line_number + 1)
    return "\n".join(lines[start:end])


def _resolve_path(path: Path | str, root: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _issue(issues: list[dict[str, Any]], code: str, message: str, path: Path | str | None = None) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        item["path"] = str(path)
    issues.append(item)
