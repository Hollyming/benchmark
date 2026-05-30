from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Any

from ultra_long_benchmark.shared.io import read_json, write_json, write_text


DEFAULT_FAILURE_LABELS = (
    "retrieved_but_not_applied",
    "unsupported_policy",
    "overbroad_exception",
    "stale_policy_reuse",
    "negative_example_stored",
    "approval_gate_bypassed",
    "clarification_omitted",
    "action_boundary_missing",
    "forbidden_action_taken",
    "invalid_prediction",
)


def export_paper_tables(
    output_dir: Path,
    *,
    release_baseline_report: Path | None = None,
    prediction_reports: list[Path] | None = None,
    prediction_batch_reports: list[Path] | None = None,
    bootstrap_samples: int = 1000,
    bootstrap_seed: int = 0,
) -> dict[str, Any]:
    """Export paper-ready result tables from deterministic and submission reports."""

    output_dir = Path(output_dir)
    rows = []
    source_reports = []
    project_metrics_by_system: dict[str, list[dict[str, float]]] = {}
    if release_baseline_report is not None:
        baseline_report = read_json(Path(release_baseline_report))
        source_reports.append(str(release_baseline_report))
        rows.extend(_rows_from_release_baselines(baseline_report))
        project_metrics_by_system.update(_project_metrics_from_release_baselines(baseline_report))
    for path in prediction_reports or []:
        report = read_json(Path(path))
        source_reports.append(str(path))
        rows.append(_row_from_prediction_report(report))
        project_metrics_by_system[str(report.get("system_name") or "external_system")] = _project_metrics_from_prediction_report(report)
    for path in prediction_batch_reports or []:
        batch = read_json(Path(path))
        source_reports.append(str(path))
        for report_path in _prediction_reports_from_batch(batch):
            report = read_json(report_path)
            source_reports.append(str(report_path))
            rows.append(_row_from_prediction_report(report))
            project_metrics_by_system[str(report.get("system_name") or "external_system")] = _project_metrics_from_prediction_report(report)

    rows = sorted(rows, key=lambda row: (row["source_type"], row["system_name"]))
    ci_rows = _confidence_interval_rows(project_metrics_by_system, samples=bootstrap_samples, seed=bootstrap_seed)
    _attach_main_ci(rows, ci_rows)
    task_rows = _task_rows(rows)
    capability_rows = _capability_rows(rows)
    failure_rows = _failure_rows(rows)
    tables = {
        "source_reports": source_reports,
        "bootstrap": {
            "unit": "project",
            "samples": bootstrap_samples,
            "seed": bootstrap_seed,
            "interval": "percentile_95",
        },
        "counts": {
            "systems": len(rows),
            "task_rows": len(task_rows),
            "capability_rows": len(capability_rows),
            "failure_rows": len(failure_rows),
            "confidence_interval_rows": len(ci_rows),
        },
        "main_results": rows,
        "task_breakdown": task_rows,
        "capability_breakdown": capability_rows,
        "failure_breakdown": failure_rows,
        "confidence_intervals": ci_rows,
    }
    write_json(output_dir / "paper_tables.json", tables)
    _write_csv(output_dir / "main_results.csv", rows)
    _write_csv(output_dir / "task_breakdown.csv", task_rows)
    _write_csv(output_dir / "capability_breakdown.csv", capability_rows)
    _write_csv(output_dir / "failure_breakdown.csv", failure_rows)
    _write_csv(output_dir / "confidence_intervals.csv", ci_rows)
    write_text(output_dir / "main_results.md", _markdown_table(rows))
    write_text(output_dir / "task_breakdown.md", _markdown_table(task_rows))
    write_text(output_dir / "capability_breakdown.md", _markdown_table(capability_rows))
    write_text(output_dir / "failure_breakdown.md", _markdown_table(failure_rows))
    write_text(output_dir / "confidence_intervals.md", _markdown_table(ci_rows))
    return tables


def _rows_from_release_baselines(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    summary = report.get("summary", {})
    for baseline_name, baseline in summary.get("baselines", {}).items():
        rows.append(_main_row(baseline_name, "deterministic_baseline", baseline))
    return rows


def _row_from_prediction_report(report: dict[str, Any]) -> dict[str, Any]:
    return _main_row(str(report.get("system_name") or "external_system"), "external_submission", report.get("summary", {}))


def _project_metrics_from_release_baselines(report: dict[str, Any]) -> dict[str, list[dict[str, float]]]:
    by_system: dict[str, list[dict[str, float]]] = {}
    for project in report.get("projects", []):
        for baseline_name, baseline in project.get("baselines", {}).items():
            by_system.setdefault(str(baseline_name), []).append(_project_metric_row(project.get("project_id"), baseline))
    return by_system


def _project_metrics_from_prediction_report(report: dict[str, Any]) -> list[dict[str, float]]:
    return [_project_metric_row(project.get("project_id"), project.get("summary", {})) for project in report.get("projects", [])]


def _project_metric_row(project_id: Any, summary: dict[str, Any]) -> dict[str, float]:
    return {
        "project_id": str(project_id or ""),
        "pass_rate": float(_first_number(summary, "pass_rate", "micro_pass_rate")),
        "evidence_recall": float(_first_number(summary, "evidence_recall", "micro_evidence_recall")),
        "boundary_action_recall": float(_first_number(summary, "boundary_action_recall", "micro_boundary_action_recall")),
        "must_include_recall": float(_first_number(summary, "must_include_recall", "micro_must_include_recall")),
        "must_not_violation_rate": float(_first_number(summary, "must_not_violation_rate", "micro_must_not_violation_rate")),
    }


def _prediction_reports_from_batch(batch: dict[str, Any]) -> list[Path]:
    paths = []
    for item in batch.get("reports", []):
        path = item.get("report_path")
        if path:
            paths.append(Path(str(path)))
    return paths


def _confidence_interval_rows(
    project_metrics_by_system: dict[str, list[dict[str, float]]],
    *,
    samples: int,
    seed: int,
) -> list[dict[str, Any]]:
    rows = []
    for system_name, project_metrics in sorted(project_metrics_by_system.items()):
        if not project_metrics:
            continue
        for metric in ["pass_rate", "evidence_recall", "boundary_action_recall", "must_include_recall", "must_not_violation_rate"]:
            values = [float(item.get(metric, 0.0)) for item in project_metrics]
            mean, low, high = _bootstrap_mean_ci(values, samples=samples, seed=_metric_seed(seed, system_name, metric))
            rows.append(
                {
                    "system_name": system_name,
                    "metric": metric,
                    "unit": "project",
                    "n_units": len(values),
                    "mean": mean,
                    "ci_low": low,
                    "ci_high": high,
                }
            )
    return rows


def _attach_main_ci(rows: list[dict[str, Any]], ci_rows: list[dict[str, Any]]) -> None:
    ci_by_system_metric = {(row["system_name"], row["metric"]): row for row in ci_rows}
    for row in rows:
        for metric, prefix in [
            ("pass_rate", "project_bootstrap_pass_rate"),
            ("evidence_recall", "project_bootstrap_evidence_recall"),
            ("boundary_action_recall", "project_bootstrap_boundary_action_recall"),
        ]:
            ci = ci_by_system_metric.get((row["system_name"], metric))
            if not ci:
                continue
            row[f"{prefix}_mean"] = ci["mean"]
            row[f"{prefix}_ci_low"] = ci["ci_low"]
            row[f"{prefix}_ci_high"] = ci["ci_high"]


def _bootstrap_mean_ci(values: list[float], *, samples: int, seed: int) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    mean = round(sum(values) / len(values), 4)
    if len(values) == 1 or samples <= 0:
        return mean, mean, mean
    rng = random.Random(seed)
    boot_means = []
    for _ in range(samples):
        total = sum(values[rng.randrange(len(values))] for _ in values)
        boot_means.append(total / len(values))
    boot_means.sort()
    low = _percentile(boot_means, 0.025)
    high = _percentile(boot_means, 0.975)
    return mean, round(low, 4), round(high, 4)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    position = q * (len(values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction


def _metric_seed(seed: int, system_name: str, metric: str) -> int:
    stable = sum((index + 1) * ord(char) for index, char in enumerate(system_name + "::" + metric))
    return seed + stable


def _main_row(system_name: str, source_type: str, summary: dict[str, Any]) -> dict[str, Any]:
    diagnostics = summary.get("diagnostic_label_counts", {})
    return {
        "system_name": system_name,
        "source_type": source_type,
        "predictions": _first_number(summary, "predictions", "release_probes"),
        "micro_pass_rate": _first_number(summary, "micro_pass_rate", "pass_rate"),
        "macro_pass_rate": _first_number(summary, "macro_pass_rate"),
        "task_type_macro_pass_rate": _first_number(summary, "task_type_macro_pass_rate"),
        "capability_macro_pass_rate": _first_number(summary, "capability_macro_pass_rate"),
        "micro_must_include_recall": _first_number(summary, "micro_must_include_recall", "must_include_recall"),
        "micro_must_not_violation_rate": _first_number(summary, "micro_must_not_violation_rate", "must_not_violation_rate"),
        "micro_evidence_recall": _first_number(summary, "micro_evidence_recall", "evidence_recall"),
        "micro_boundary_action_recall": _first_number(summary, "micro_boundary_action_recall", "boundary_action_recall"),
        "diagnostic_total": sum(int(value) for value in diagnostics.values()),
        "diagnostic_label_counts": diagnostics,
        "by_task_type": summary.get("by_task_type", {}),
        "by_capability": summary.get("by_capability", {}),
    }


def _task_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        for task_type, metrics in row.get("by_task_type", {}).items():
            result.append(_breakdown_row(row, "task_type", task_type, metrics))
    return sorted(result, key=lambda item: (item["group"], item["system_name"]))


def _capability_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        for capability, metrics in row.get("by_capability", {}).items():
            result.append(_breakdown_row(row, "capability", capability, metrics))
    return sorted(result, key=lambda item: (item["group"], item["system_name"]))


def _breakdown_row(row: dict[str, Any], group_type: str, group: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "system_name": row["system_name"],
        "source_type": row["source_type"],
        "group_type": group_type,
        "group": group,
        "predictions": _first_number(metrics, "predictions"),
        "pass_rate": _first_number(metrics, "pass_rate"),
        "must_include_recall": _first_number(metrics, "must_include_recall"),
        "must_not_violation_rate": _first_number(metrics, "must_not_violation_rate"),
        "evidence_recall": _first_number(metrics, "evidence_recall"),
        "boundary_action_recall": _first_number(metrics, "boundary_action_recall"),
        "diagnostic_label_counts": metrics.get("diagnostic_label_counts", {}),
    }


def _failure_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    labels = sorted(set(DEFAULT_FAILURE_LABELS) | {label for row in rows for label in row.get("diagnostic_label_counts", {})})
    for row in rows:
        diagnostics = row.get("diagnostic_label_counts", {})
        total = max(1, int(row.get("predictions") or 0))
        for label in labels:
            count = int(diagnostics.get(label, 0))
            result.append(
                {
                    "system_name": row["system_name"],
                    "source_type": row["source_type"],
                    "failure_label": label,
                    "count": count,
                    "rate": round(count / total, 4),
                }
            )
    return result


def _first_number(mapping: dict[str, Any], *keys: str) -> int | float:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, (int, float)):
            return value
    return 0


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = _fieldnames(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _cell(row.get(key)) for key in fieldnames})


def _markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "\n"
    fieldnames = _fieldnames(rows)
    lines = [
        "| " + " | ".join(fieldnames) + " |",
        "| " + " | ".join("---" for _ in fieldnames) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_escape_md(_cell(row.get(key))) for key in fieldnames) + " |")
    return "\n".join(lines) + "\n"


def _fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    preferred = [
        "system_name",
        "source_type",
        "group_type",
        "group",
        "failure_label",
        "predictions",
        "micro_pass_rate",
        "macro_pass_rate",
        "task_type_macro_pass_rate",
        "capability_macro_pass_rate",
        "pass_rate",
        "micro_must_include_recall",
        "must_include_recall",
        "micro_must_not_violation_rate",
        "must_not_violation_rate",
        "micro_evidence_recall",
        "evidence_recall",
        "micro_boundary_action_recall",
        "boundary_action_recall",
        "diagnostic_total",
        "count",
        "rate",
        "diagnostic_label_counts",
    ]
    keys = set().union(*(row.keys() for row in rows))
    return [key for key in preferred if key in keys] + sorted(keys - set(preferred) - {"by_task_type", "by_capability"})


def _cell(value: Any) -> str | int | float:
    if isinstance(value, dict):
        return ";".join(f"{key}:{value[key]}" for key in sorted(value))
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    if value is None:
        return ""
    return value


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")
