from pathlib import Path

from ultra_long_benchmark.claim_lint import lint_paper_claims
from ultra_long_benchmark.claim_lint import verify_paper_claim_lint_report
from ultra_long_benchmark.shared.io import read_json


def test_claim_lint_allows_explicit_blocked_language(tmp_path: Path):
    doc = tmp_path / "paper.md"
    doc.write_text(
        "\n".join(
            [
                "The current release is a GitHub developer workflow release.",
                "Do not describe the current release as a multi-domain email/calendar/docs/chat/browser/web-search workflow benchmark.",
                "Email workflow remains blocked until a license/privacy/PII manifest passes.",
                "The memory-profile score is not a SOTA result.",
            ]
        ),
        encoding="utf-8",
    )

    report = lint_paper_claims([doc], output_path=tmp_path / "lint.json", root=tmp_path)

    assert report["passed"] is True
    assert report["summary"]["issues"] == 0
    assert report["summary"]["files_hashed"] == 1
    assert len(next(iter(report["checks"].values()))["sha256"]) == 64
    assert report["summary"]["allowed_blocked_claim_mentions"] >= 1
    assert read_json(tmp_path / "lint.json")["passed"] is True
    assert verify_paper_claim_lint_report(tmp_path / "lint.json")["passed"] is True


def test_claim_lint_blocks_affirmative_multi_domain_claim(tmp_path: Path):
    doc = tmp_path / "paper.md"
    doc.write_text(
        "The current release covers email/calendar/docs/chat/browser/web-search office workflows.\n",
        encoding="utf-8",
    )

    report = lint_paper_claims([doc], root=tmp_path)

    assert report["passed"] is False
    assert report["summary"]["issue_codes"] == ["blocked_claim_affirmed"]
    assert report["issues"][0]["claim_id"] == "multi_domain_office_release"


def test_claim_lint_blocks_human_audited_and_sota_claims(tmp_path: Path):
    doc = tmp_path / "paper.md"
    doc.write_text(
        "\n".join(
            [
                "LLM rewrite quality passed the human audit.",
                "Mem0/A-MEM/Graphiti results are executed SOTA memory baselines.",
                "The original-query memory-profile score is a SOTA capability result.",
            ]
        ),
        encoding="utf-8",
    )

    report = lint_paper_claims([doc], root=tmp_path)

    claim_ids = {issue["claim_id"] for issue in report["issues"]}
    assert report["passed"] is False
    assert "human_audited_rewrite_quality" in claim_ids
    assert "executed_sota_memory_baselines" in claim_ids
    assert "original_query_scores_as_sota" in claim_ids


def test_claim_lint_reports_missing_file(tmp_path: Path):
    report = lint_paper_claims([tmp_path / "missing.md"], root=tmp_path)

    assert report["passed"] is False
    assert "claim_lint_file_missing" in report["summary"]["issue_codes"]


def test_verify_claim_lint_report_fails_when_source_doc_changes(tmp_path: Path):
    doc = tmp_path / "paper.md"
    doc.write_text("The current release is a GitHub developer workflow release.\n", encoding="utf-8")
    report_path = tmp_path / "lint.json"
    lint_paper_claims([doc], output_path=report_path, root=tmp_path)
    doc.write_text("The current release covers email/calendar/docs/chat/browser workflows.\n", encoding="utf-8")

    report = verify_paper_claim_lint_report(report_path, root=tmp_path)

    assert report["passed"] is False
    assert "claim_lint_source_sha256_mismatch" in report["summary"]["issue_codes"]
