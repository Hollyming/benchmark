from __future__ import annotations

from pathlib import Path
from typing import Any

from ultra_long_benchmark.release_integrity import verify_annotation_release_integrity
from ultra_long_benchmark.shared.io import read_json, write_json


PROFILE_THRESHOLDS: dict[str, dict[str, Any]] = {
    "fixture": {
        "min_packs": 1,
        "min_repos": 1,
        "min_tasks": 1,
        "min_nonempty_splits": 1,
        "min_tasks_per_split": {"train": 1, "dev": 0, "test": 0},
        "min_candidate_types": 1,
        "required_candidate_types": [],
        "min_events": 1,
        "min_eligible_windows": 0,
        "min_repos_spanning_multiple_windows": 0,
        "min_span_days": 0,
        "min_repos_with_min_span_days": 0,
        "max_empty_splits": 2,
        "max_skipped_ratio": 1.0,
        "require_scale_summary": False,
        "require_window_report": False,
        "require_release_integrity_pass": True,
    },
    "pilot": {
        "min_packs": 5,
        "min_repos": 5,
        "min_tasks": 20,
        "min_nonempty_splits": 2,
        "min_tasks_per_split": {"train": 5, "dev": 1, "test": 1},
        "min_candidate_types": 2,
        "required_candidate_types": ["authorization_boundary", "negative_policy_example"],
        "min_events": 100,
        "min_eligible_windows": 3,
        "min_repos_spanning_multiple_windows": 2,
        "min_span_days": 7,
        "min_repos_with_min_span_days": 2,
        "max_empty_splits": 0,
        "max_skipped_ratio": 0.8,
        "require_scale_summary": True,
        "require_window_report": True,
        "require_release_integrity_pass": True,
    },
    "paper": {
        "min_packs": 30,
        "min_repos": 30,
        "min_tasks": 150,
        "min_nonempty_splits": 3,
        "min_tasks_per_split": {"train": 60, "dev": 20, "test": 20},
        "min_candidate_types": 3,
        "required_candidate_types": ["authorization_boundary", "contextual_policy", "issue_triage_policy", "negative_policy_example"],
        "min_events": 1000,
        "min_eligible_windows": 30,
        "min_repos_spanning_multiple_windows": 15,
        "min_span_days": 14,
        "min_repos_with_min_span_days": 15,
        "max_empty_splits": 0,
        "max_skipped_ratio": 0.7,
        "require_scale_summary": True,
        "require_window_report": True,
        "require_release_integrity_pass": True,
    },
}


def assess_release_scale(
    release_dir: Path,
    *,
    profile: str = "paper",
    scale_summary_path: Path | None = None,
    window_report_path: Path | None = None,
    release_integrity_report_path: Path | None = None,
    prompt_export_dir: Path | None = None,
    output_path: Path | None = None,
    threshold_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess whether a grounded release is large and balanced enough for a paper."""

    if profile not in PROFILE_THRESHOLDS:
        raise ValueError(f"unknown paper-scale profile {profile!r}; choose from {sorted(PROFILE_THRESHOLDS)}")

    release_dir = Path(release_dir)
    thresholds = _merged_thresholds(profile, threshold_overrides)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    manifest_path = release_dir / "release_manifest.json"
    if not manifest_path.exists():
        _issue(issues, "release_manifest_missing", f"release manifest is missing: {manifest_path}", path=manifest_path)
        report = _report(release_dir, profile, thresholds, {}, issues, warnings)
        if output_path is not None:
            write_json(output_path, report)
        return report

    manifest = read_json(manifest_path)
    scale_summary = _read_optional_json(scale_summary_path, "scale_summary", thresholds["require_scale_summary"], issues, warnings)
    window_report = _read_optional_json(window_report_path, "window_report", thresholds["require_window_report"], issues, warnings)
    integrity_report = _load_or_compute_integrity(
        release_dir,
        release_integrity_report_path=release_integrity_report_path,
        prompt_export_dir=prompt_export_dir,
        issues=issues,
        warnings=warnings,
    )

    release_stats = _release_stats(manifest)
    quality_stats = _quality_stats(scale_summary)
    window_stats = _window_stats(window_report)
    integrity_stats = _integrity_stats(integrity_report)
    summary = {
        "release": release_stats,
        "quality": quality_stats,
        "windows": window_stats,
        "integrity": integrity_stats,
    }

    _check_release_scale(release_stats, thresholds, issues, warnings)
    _check_candidate_coverage(release_stats, thresholds, issues, warnings)
    _check_quality_scale(quality_stats, thresholds, issues)
    _check_window_scale(window_stats, thresholds, issues)
    _check_integrity(integrity_stats, thresholds, issues, warnings)

    report = _report(release_dir, profile, thresholds, summary, issues, warnings)
    if output_path is not None:
        write_json(output_path, report)
    return report


def _merged_thresholds(profile: str, overrides: dict[str, Any] | None) -> dict[str, Any]:
    thresholds = dict(PROFILE_THRESHOLDS[profile])
    thresholds["min_tasks_per_split"] = dict(PROFILE_THRESHOLDS[profile]["min_tasks_per_split"])
    thresholds["required_candidate_types"] = list(PROFILE_THRESHOLDS[profile]["required_candidate_types"])
    for key, value in (overrides or {}).items():
        if value is None:
            continue
        if key == "min_tasks_per_split":
            thresholds["min_tasks_per_split"].update(value)
        else:
            thresholds[key] = value
    return thresholds


def _release_stats(manifest: dict[str, Any]) -> dict[str, Any]:
    packs = list(manifest.get("packs", []))
    repos = sorted({pack.get("repo") for pack in packs if pack.get("repo")})
    candidate_types: dict[str, int] = {}
    for pack in packs:
        for candidate_type, count in pack.get("candidate_types", {}).items():
            candidate_types[str(candidate_type)] = candidate_types.get(str(candidate_type), 0) + _as_int(count)
    splits = {split: _as_int(manifest.get("splits", {}).get(split)) for split in ("train", "dev", "test")}
    skipped_repos = _as_int(manifest.get("counts", {}).get("skipped_repos"))
    packs_total = _as_int(manifest.get("counts", {}).get("packs"))
    skipped_ratio = skipped_repos / (skipped_repos + packs_total) if skipped_repos + packs_total > 0 else 0.0
    return {
        "packs": packs_total,
        "repos": len(repos),
        "tasks": _as_int(manifest.get("counts", {}).get("tasks")),
        "splits": splits,
        "nonempty_splits": sum(1 for count in splits.values() if count > 0),
        "empty_splits": sum(1 for count in splits.values() if count == 0),
        "candidate_types": dict(sorted(candidate_types.items())),
        "candidate_type_count": len(candidate_types),
        "candidate_type_total": sum(candidate_types.values()),
        "skipped_repos": skipped_repos,
        "skipped_ratio": round(skipped_ratio, 4),
        "split_policy": manifest.get("split_policy"),
        "dataset_name": manifest.get("dataset_name"),
        "version": manifest.get("version"),
    }


def _quality_stats(scale_summary: dict[str, Any] | None) -> dict[str, Any]:
    if scale_summary is None:
        return {"present": False}
    quality = scale_summary.get("quality", {})
    repos = scale_summary.get("repos", {})
    tasks = scale_summary.get("tasks", {})
    return {
        "present": True,
        "events_total": _as_int(quality.get("events_total")),
        "repos_total": _as_int(quality.get("repos_total")),
        "repos_eligible": _as_int(quality.get("repos_eligible") or repos.get("eligible_packs")),
        "repos_skipped": _as_int(repos.get("skipped")),
        "tasks_total": _as_int(tasks.get("total")),
        "mean_tasks_per_pack": float(tasks.get("mean_per_pack", 0.0) or 0.0),
    }


def _window_stats(window_report: dict[str, Any] | None) -> dict[str, Any]:
    if window_report is None:
        return {"present": False}
    repos = list(window_report.get("repos", []))
    spans = [float(repo.get("span_days", 0.0) or 0.0) for repo in repos]
    summary = window_report.get("summary", {})
    return {
        "present": True,
        "window_days": window_report.get("window_days"),
        "repos_total": _as_int(summary.get("repos_total")),
        "windows_total": _as_int(summary.get("windows_total")),
        "eligible_windows": _as_int(summary.get("eligible_windows")),
        "repos_with_eligible_windows": _as_int(summary.get("repos_with_eligible_windows")),
        "repos_spanning_multiple_windows": _as_int(summary.get("repos_spanning_multiple_windows")),
        "max_span_days": max(spans) if spans else 0.0,
        "mean_span_days": round(sum(spans) / len(spans), 4) if spans else 0.0,
        "repo_span_days": {str(repo.get("repo")): float(repo.get("span_days", 0.0) or 0.0) for repo in repos if repo.get("repo")},
    }


def _integrity_stats(integrity_report: dict[str, Any] | None) -> dict[str, Any]:
    if integrity_report is None:
        return {"present": False}
    summary = integrity_report.get("summary", {})
    return {
        "present": True,
        "passed": integrity_report.get("passed") is True,
        "issues": _as_int(summary.get("issues")),
        "warnings": _as_int(summary.get("warnings")),
        "issue_codes": list(summary.get("issue_codes", [])),
        "warning_codes": list(summary.get("warning_codes", [])),
    }


def _check_release_scale(stats: dict[str, Any], thresholds: dict[str, Any], issues: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    _min_issue(stats["packs"], thresholds["min_packs"], "min_packs_not_met", "release packs", issues)
    _min_issue(stats["repos"], thresholds["min_repos"], "min_repos_not_met", "release repos", issues)
    _min_issue(stats["tasks"], thresholds["min_tasks"], "min_tasks_not_met", "release tasks", issues)
    _min_issue(stats["nonempty_splits"], thresholds["min_nonempty_splits"], "min_nonempty_splits_not_met", "non-empty train/dev/test splits", issues)
    if stats["empty_splits"] > thresholds["max_empty_splits"]:
        _issue(issues, "too_many_empty_splits", f"empty splits={stats['empty_splits']} exceeds max_empty_splits={thresholds['max_empty_splits']}")
    for split, minimum in thresholds["min_tasks_per_split"].items():
        actual = _as_int(stats["splits"].get(split))
        if actual < minimum:
            _issue(issues, "min_split_tasks_not_met", f"{split} split has {actual} tasks; required >= {minimum}")
    if stats["skipped_ratio"] > thresholds["max_skipped_ratio"]:
        _issue(issues, "skipped_ratio_too_high", f"skipped repo ratio={stats['skipped_ratio']} exceeds {thresholds['max_skipped_ratio']}")
    split_counts = [count for count in stats["splits"].values() if count > 0]
    if len(split_counts) >= 2 and max(split_counts) / min(split_counts) > 10:
        _warn(warnings, "split_imbalance_high", f"non-empty split imbalance is high: {stats['splits']}")


def _check_candidate_coverage(stats: dict[str, Any], thresholds: dict[str, Any], issues: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    _min_issue(stats["candidate_type_count"], thresholds["min_candidate_types"], "min_candidate_types_not_met", "candidate types", issues)
    missing = sorted(set(thresholds["required_candidate_types"]) - set(stats["candidate_types"]))
    if missing:
        _issue(issues, "required_candidate_types_missing", f"required candidate types missing: {missing}")
    total = stats["candidate_type_total"]
    if total > 0:
        dominant_type, dominant_count = max(stats["candidate_types"].items(), key=lambda item: item[1])
        if dominant_count / total > 0.75 and len(stats["candidate_types"]) > 1:
            _warn(warnings, "candidate_type_distribution_dominated", f"candidate type {dominant_type} accounts for {dominant_count}/{total} tasks")


def _check_quality_scale(stats: dict[str, Any], thresholds: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    if not stats.get("present"):
        return
    _min_issue(stats["events_total"], thresholds["min_events"], "min_events_not_met", "source events", issues)
    _min_issue(stats["repos_eligible"], thresholds["min_repos"], "min_eligible_repos_not_met", "eligible repos", issues)


def _check_window_scale(stats: dict[str, Any], thresholds: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    if not stats.get("present"):
        return
    _min_issue(stats["eligible_windows"], thresholds["min_eligible_windows"], "min_eligible_windows_not_met", "eligible time windows", issues)
    _min_issue(
        stats["repos_spanning_multiple_windows"],
        thresholds["min_repos_spanning_multiple_windows"],
        "min_multi_window_repos_not_met",
        "repos spanning multiple windows",
        issues,
    )
    min_span_days = thresholds["min_span_days"]
    repos_with_span = sum(1 for span in stats.get("repo_span_days", {}).values() if span >= min_span_days)
    _min_issue(repos_with_span, thresholds["min_repos_with_min_span_days"], "min_longitudinal_repos_not_met", f"repos with span >= {min_span_days} days", issues)


def _check_integrity(stats: dict[str, Any], thresholds: dict[str, Any], issues: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    if not stats.get("present"):
        if thresholds["require_release_integrity_pass"]:
            _issue(issues, "release_integrity_missing", "release integrity report is required")
        return
    if thresholds["require_release_integrity_pass"] and not stats["passed"]:
        _issue(issues, "release_integrity_failed", f"release integrity failed with issue codes {stats['issue_codes']}")
    for code in stats.get("warning_codes", []):
        if code == "empty_split" and thresholds["max_empty_splits"] == 0:
            _issue(issues, "release_integrity_empty_split", "release integrity reports empty splits, which are not allowed for this profile")
        else:
            _warn(warnings, f"release_integrity_warning_{code}", f"release integrity warning: {code}")


def _load_or_compute_integrity(
    release_dir: Path,
    *,
    release_integrity_report_path: Path | None,
    prompt_export_dir: Path | None,
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if release_integrity_report_path is not None:
        path = Path(release_integrity_report_path)
        if not path.exists():
            _issue(issues, "release_integrity_report_missing", f"release integrity report missing: {path}", path=path)
            return None
        return read_json(path)
    if prompt_export_dir is not None:
        return verify_annotation_release_integrity(release_dir, prompt_export_dir=prompt_export_dir)
    _warn(warnings, "release_integrity_not_supplied", "release integrity was not supplied or computed; pass --release-integrity-report or --prompt-export-dir")
    return None


def _read_optional_json(
    path: Path | None,
    label: str,
    required: bool,
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if path is None:
        if required:
            _issue(issues, f"{label}_missing", f"{label} is required for this profile")
        else:
            _warn(warnings, f"{label}_not_supplied", f"{label} was not supplied")
        return None
    path = Path(path)
    if not path.exists():
        if required:
            _issue(issues, f"{label}_missing", f"{label} is missing: {path}", path=path)
        else:
            _warn(warnings, f"{label}_missing", f"{label} is missing: {path}", path=path)
        return None
    return read_json(path)


def _report(
    release_dir: Path,
    profile: str,
    thresholds: dict[str, Any],
    checks: dict[str, Any],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "release_dir": str(release_dir),
        "profile": profile,
        "thresholds": thresholds,
        "passed": not issues,
        "summary": {
            "issues": len(issues),
            "warnings": len(warnings),
            "issue_codes": sorted({issue["code"] for issue in issues}),
            "warning_codes": sorted({warning["code"] for warning in warnings}),
        },
        "checks": checks,
        "issues": issues,
        "warnings": warnings,
        "recommended_next_actions": _recommended_next_actions(issues),
    }


def _recommended_next_actions(issues: list[dict[str, Any]]) -> list[str]:
    codes = {issue["code"] for issue in issues}
    actions = []
    if codes & {"min_packs_not_met", "min_repos_not_met", "min_tasks_not_met", "min_events_not_met", "min_eligible_repos_not_met"}:
        actions.append("Stage a larger GHArchive slice with more repositories and events before claiming paper-scale coverage.")
    if codes & {"too_many_empty_splits", "min_split_tasks_not_met", "release_integrity_empty_split", "min_nonempty_splits_not_met"}:
        actions.append("Increase eligible repository count until train/dev/test splits are all populated with enough tasks.")
    if codes & {"required_candidate_types_missing", "min_candidate_types_not_met"}:
        actions.append("Extend mining rules or select richer repositories so contextual policy, authorization boundary, and negative-example tasks are all represented.")
    if codes & {"window_report_missing", "min_eligible_windows_not_met", "min_multi_window_repos_not_met", "min_longitudinal_repos_not_met"}:
        actions.append("Use multi-day or multi-week GHArchive slices and run gharchive-window-report to verify longitudinal evidence.")
    if codes & {"release_integrity_failed", "release_integrity_missing", "release_integrity_report_missing"}:
        actions.append("Run verify-release-integrity and fix hash, split, task, or prompt coverage issues before scale claims.")
    return actions


def _min_issue(actual: int | float, minimum: int | float, code: str, label: str, issues: list[dict[str, Any]]) -> None:
    if actual < minimum:
        _issue(issues, code, f"{label}={actual} below required minimum {minimum}")


def _issue(issues: list[dict[str, Any]], code: str, message: str, path: Path | None = None) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        item["path"] = str(path)
    issues.append(item)


def _warn(warnings: list[dict[str, Any]], code: str, message: str, path: Path | None = None) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        item["path"] = str(path)
    warnings.append(item)


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
