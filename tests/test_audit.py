from pathlib import Path

from ultra_long_benchmark.audit import audit_generated, format_audit_text
from ultra_long_benchmark.cli import GENERATED, run_smoke_all
from ultra_long_benchmark.shared.io import write_json, write_jsonl


def test_audit_reports_counts_schema_and_qc_for_smoke_artifacts():
    run_smoke_all()

    report = audit_generated(GENERATED)

    assert report["passed"] is True
    assert report["counts"]["source_documents"] == 2
    assert report["counts"]["personas"] == 2
    assert report["counts"]["events"] == 12
    assert report["counts"]["trajectories"] == 2
    assert report["counts"]["sessions"] == 12
    assert report["counts"]["messages"] == 24
    assert report["counts"]["queries"] == 8
    assert report["counts"]["privacy_sensitive_queries"] == 2
    assert report["counts"]["capabilities"]["privacy_refusal"] == 2
    assert all(status["valid"] for status in report["schema"].values())
    assert report["qc"]["present"] is True
    assert report["qc"]["passed"] is True


def test_audit_text_includes_core_sections():
    run_smoke_all()

    text = format_audit_text(audit_generated(GENERATED))

    assert "Generated artifact audit" in text
    assert "Counts:" in text
    assert "Schema:" in text
    assert "QC: present=True passed=True issues=0" in text


def test_audit_reports_missing_and_invalid_generated_artifacts(tmp_path: Path):
    generated = tmp_path / "generated"
    write_jsonl(generated / "seed_corpora_ingestion" / "source_documents.jsonl", [{"doc_id": "missing-required-fields"}])
    write_json(generated / "annotation_and_quality_control" / "qc_report.json", {"passed": False, "issues": ["manual issue"]})

    report = audit_generated(generated)

    assert report["passed"] is False
    assert report["schema"]["source_documents"]["valid"] is False
    assert "row 1:" in report["schema"]["source_documents"]["errors"][0]
    assert report["schema"]["personas"]["valid"] is False
    assert report["schema"]["personas"]["errors"] == ["missing file"]
    assert report["qc"]["present"] is True
    assert report["qc"]["passed"] is False
    assert report["qc"]["issues"] == ["manual issue"]
