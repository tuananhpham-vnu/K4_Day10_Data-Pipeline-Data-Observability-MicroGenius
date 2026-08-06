from __future__ import annotations

from typing import Any

from core.utils import write_text

METRIC_KEYS = ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score")


def _metrics_table(rows: list[tuple[str, dict[str, Any]]]) -> str:
    header = "| metric | " + " | ".join(name for name, _ in rows) + " |"
    divider = "| --- | " + " | ".join("---" for _ in rows) + " |"
    lines = [header, divider]
    for key in METRIC_KEYS:
        values = [f"{metrics.get(key, 'n/a'):.4f}" if isinstance(metrics.get(key), (int, float)) else "n/a" for _, metrics in rows]
        lines.append(f"| {key} | " + " | ".join(values) + " |")
    return "\n".join(lines)


def _quality_summary(quality: dict[str, Any]) -> str:
    lines = [f"- overall_passed: **{quality.get('overall_passed')}**"]
    for check in quality.get("checks", []):
        lines.append(f"  - {check['check']}: {'PASS' if check['passed'] else 'FAIL'} ({check['details']})")
    return "\n".join(lines)


def _freshness_summary(freshness: dict[str, Any]) -> str:
    return (
        f"- latest_published: {freshness.get('latest_published')}\n"
        f"- oldest_published: {freshness.get('oldest_published')}\n"
        f"- stale_rows: {freshness.get('stale_rows')} / {freshness.get('total_rows')}\n"
        f"- is_fresh: **{freshness.get('is_fresh')}**"
    )


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Viet markdown report cho baseline phase."""
    lines = [
        "# Phase 1 Baseline Report",
        "",
        "## Source",
        "",
        "\n".join(f"- {key}: {value}" for key, value in source_summary.items()),
        "",
        "## Evaluation metrics",
        "",
        _metrics_table([("baseline", metrics)]),
        "",
        "## Data quality",
        "",
        _quality_summary(quality),
        "",
        "## Freshness",
        "",
        _freshness_summary(freshness),
        "",
    ]
    write_text(report_path, "\n".join(lines))


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Viet markdown report so sanh baseline/corrupted/repaired."""
    lines = [
        "# Corruption Comparison Report",
        "",
        "## Evaluation metrics",
        "",
        _metrics_table(
            [
                ("baseline", baseline_metrics),
                ("corrupted", corrupted_metrics),
                ("repaired", repaired_metrics),
            ]
        ),
        "",
        "## Data quality — corrupted",
        "",
        _quality_summary(corrupted_quality),
        "",
        "## Data quality — repaired",
        "",
        _quality_summary(repaired_quality),
        "",
        "## Freshness — corrupted",
        "",
        _freshness_summary(corrupted_freshness),
        "",
        "## Freshness — repaired",
        "",
        _freshness_summary(repaired_freshness),
        "",
    ]
    write_text(report_path, "\n".join(lines))
