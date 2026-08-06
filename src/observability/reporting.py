from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping


_STANDARD_METRICS = (
    "retrieval_hit_rate",
    "mean_token_f1",
    "judge_accuracy",
    "mean_judge_score",
)
_RAGAS_METRICS = (
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "faithfulness",
)


def _write_markdown(report_path, content: str) -> None:
    path = Path(report_path)
    if path.exists() and path.is_dir():
        raise IsADirectoryError(f"Report path points to a directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _format_value(value: Any, *, percentage: bool = False) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if _is_number(value):
        number = float(value)
        if percentage:
            return f"{number * 100:.2f}%"
        if number.is_integer():
            return str(int(number))
        return f"{number:.4f}"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_escape(item) for item in value) or "—"
    if isinstance(value, Mapping):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return _escape(value)


def _rate_like(name: str) -> bool:
    lowered = name.casefold()
    return any(token in lowered for token in ("rate", "accuracy", "precision", "recall", "faithfulness", "relevancy", "ratio", "f1"))


def _table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    header_list = list(headers)
    lines = [
        "| " + " | ".join(_escape(item) for item in header_list) + " |",
        "| " + " | ".join("---" for _ in header_list) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_escape(item) for item in row) + " |")
    return "\n".join(lines)


def _nested_get(payload: Mapping[str, Any], path: Iterable[str], default: Any = None) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return default
        current = current[key]
    return current


def _metric_value(metrics: Mapping[str, Any], name: str) -> Any:
    if name in metrics:
        return metrics[name]
    ragas = metrics.get("ragas")
    if isinstance(ragas, Mapping):
        if name in ragas:
            return ragas[name]
        # Some Ragas versions expose a nested score dictionary/dataframe dump.
        for container_name in ("scores", "metrics", "result"):
            container = ragas.get(container_name)
            if isinstance(container, Mapping) and name in container:
                return container[name]
    return None


def _available_metric_names(*payloads: Mapping[str, Any]) -> list[str]:
    names: list[str] = []
    for name in (*_STANDARD_METRICS, *_RAGAS_METRICS):
        if any(_is_number(_metric_value(payload, name)) for payload in payloads):
            names.append(name)
    return names


def _status(value: Any) -> str:
    return "PASS" if bool(value) else "FAIL"


def _flatten_mapping(payload: Mapping[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for key, value in payload.items():
        label = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            rows.extend(_flatten_mapping(value, label))
        elif not isinstance(value, (list, tuple, set)) or all(
            not isinstance(item, (dict, list, tuple, set)) for item in value
        ):
            rows.append((label, value))
    return rows


def _quality_rows(quality: Mapping[str, Any]) -> list[list[str]]:
    checks = quality.get("checks", {})
    if not isinstance(checks, Mapping):
        return []
    rows: list[list[str]] = []
    for name, result in checks.items():
        if not isinstance(result, Mapping):
            continue
        detail_parts = []
        for key in (
            "value",
            "minimum",
            "null_rows",
            "duplicate_rows",
            "short_rows",
            "stale_rows",
            "future_rows",
            "invalid_age_rows",
            "failed_rows",
        ):
            if key in result:
                detail_parts.append(f"{key}={_format_value(result[key])}")
        rows.append(
            [
                str(name),
                _status(result.get("passed")),
                ", ".join(detail_parts) or "—",
            ]
        )
    return rows


def _json_block(payload: Mapping[str, Any]) -> str:
    return "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n```"


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Generate a human-readable baseline evaluation report in Markdown."""
    for name, value in {
        "source_summary": source_summary,
        "metrics": metrics,
        "quality": quality,
        "freshness": freshness,
    }.items():
        if not isinstance(value, dict):
            raise TypeError(f"{name} must be a dictionary.")

    metric_names = _available_metric_names(metrics)
    metric_rows = [
        [
            name,
            _format_value(_metric_value(metrics, name), percentage=_rate_like(name)),
        ]
        for name in metric_names
    ]
    if "samples" in metrics:
        metric_rows.insert(0, ["samples", _format_value(metrics.get("samples"))])

    source_rows = [
        [key, _format_value(value)]
        for key, value in _flatten_mapping(source_summary)
    ] or [["source", "No source summary supplied"]]

    quality_rows = _quality_rows(quality)
    freshness_rows = [
        ["total_rows", _format_value(freshness.get("total_rows"))],
        ["latest_published", _format_value(freshness.get("latest_published"))],
        ["oldest_published", _format_value(freshness.get("oldest_published"))],
        ["stale_rows", _format_value(freshness.get("stale_rows"))],
        ["invalid_date_rows", _format_value(freshness.get("invalid_date_rows"))],
        ["source_timestamp", _format_value(freshness.get("source_timestamp"))],
        ["is_fresh", _status(freshness.get("is_fresh"))],
    ]

    quality_passed = bool(quality.get("is_valid", quality.get("passed", False)))
    freshness_passed = bool(freshness.get("is_fresh", False))
    overall_status = "PASS" if quality_passed and freshness_passed else "FAIL"
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    lines = [
        "# Phase 1 — Baseline Evaluation Report",
        "",
        f"- **Generated at:** {generated_at}",
        f"- **Overall data status:** **{overall_status}**",
        f"- **Data quality:** {_status(quality_passed)}",
        f"- **Freshness:** {_status(freshness_passed)}",
        "",
        "## 1. Source summary",
        "",
        _table(("Field", "Value"), source_rows),
        "",
        "## 2. Retrieval and answer quality",
        "",
        _table(("Metric", "Value"), metric_rows or [["metrics", "No numeric metrics available"]]),
        "",
        "## 3. Data-quality checks",
        "",
        _table(("Check", "Status", "Details"), quality_rows or [["checks", "N/A", "No detailed checks supplied"]]),
        "",
        "### Quality overview",
        "",
        _table(
            ("Signal", "Value"),
            [
                ["row_count", _format_value(quality.get("row_count"))],
                ["total_null_count", _format_value(quality.get("total_null_count"))],
                ["duplicate_count", _format_value(quality.get("duplicate_count"))],
                ["failed_checks", _format_value(quality.get("failed_checks"))],
            ],
        ),
        "",
        "## 4. Freshness",
        "",
        _table(("Signal", "Value"), freshness_rows),
        "",
        "## 5. Interpretation",
        "",
    ]

    if overall_status == "PASS":
        lines.append(
            "The baseline dataset passed the configured quality and freshness gates. "
            "The RAG metrics above can be used as the reference point for the corruption experiment."
        )
    else:
        lines.append(
            "The baseline dataset did not pass every configured data gate. Interpret downstream RAG metrics "
            "with caution and review the failed checks before treating this run as a reliable baseline."
        )

    lines.extend(
        [
            "",
            "## Appendix — Machine-readable inputs",
            "",
            "### Metrics",
            "",
            _json_block(metrics),
            "",
            "### Quality",
            "",
            _json_block(quality),
            "",
            "### Freshness",
            "",
            _json_block(freshness),
        ]
    )
    _write_markdown(report_path, "\n".join(lines))


def _delta(current: Any, previous: Any) -> float | None:
    if not (_is_number(current) and _is_number(previous)):
        return None
    return float(current) - float(previous)


def _format_delta(value: float | None, *, percentage: bool) -> str:
    if value is None:
        return "N/A"
    if percentage:
        return f"{value * 100:+.2f} pp"
    return f"{value:+.4f}"


def _recovery_rate(baseline: Any, corrupted: Any, repaired: Any) -> float | None:
    if not all(_is_number(value) for value in (baseline, corrupted, repaired)):
        return None
    lost = float(baseline) - float(corrupted)
    if abs(lost) < 1e-12:
        return None
    return (float(repaired) - float(corrupted)) / lost


def _check_result(quality: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    checks = quality.get("checks", {})
    if isinstance(checks, Mapping):
        result = checks.get(name, {})
        if isinstance(result, Mapping):
            return result
    return {}


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
    """Generate a Markdown comparison of baseline, corrupted, and repaired runs."""
    payloads = {
        "baseline_metrics": baseline_metrics,
        "corrupted_metrics": corrupted_metrics,
        "repaired_metrics": repaired_metrics,
        "corrupted_quality": corrupted_quality,
        "repaired_quality": repaired_quality,
        "corrupted_freshness": corrupted_freshness,
        "repaired_freshness": repaired_freshness,
    }
    for name, value in payloads.items():
        if not isinstance(value, dict):
            raise TypeError(f"{name} must be a dictionary.")

    metric_names = _available_metric_names(
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
    )
    metric_rows: list[list[str]] = []
    degraded_metrics: list[str] = []
    improved_metrics: list[str] = []
    recovered_metrics: list[str] = []

    for name in metric_names:
        baseline = _metric_value(baseline_metrics, name)
        corrupted = _metric_value(corrupted_metrics, name)
        repaired = _metric_value(repaired_metrics, name)
        corruption_delta = _delta(corrupted, baseline)
        repair_delta = _delta(repaired, corrupted)
        recovery = _recovery_rate(baseline, corrupted, repaired)

        if corruption_delta is not None and corruption_delta < 0:
            degraded_metrics.append(name)
        if repair_delta is not None and repair_delta > 0:
            improved_metrics.append(name)
        if (
            _is_number(baseline)
            and _is_number(repaired)
            and float(repaired) >= float(baseline) - 1e-12
        ):
            recovered_metrics.append(name)

        percentage = _rate_like(name)
        metric_rows.append(
            [
                name,
                _format_value(baseline, percentage=percentage),
                _format_value(corrupted, percentage=percentage),
                _format_value(repaired, percentage=percentage),
                _format_delta(corruption_delta, percentage=percentage),
                _format_delta(repair_delta, percentage=percentage),
                "N/A" if recovery is None else f"{recovery * 100:.1f}%",
            ]
        )

    check_names = sorted(
        set(
            list((corrupted_quality.get("checks") or {}).keys())
            + list((repaired_quality.get("checks") or {}).keys())
        )
    )
    quality_comparison_rows: list[list[str]] = []
    for name in check_names:
        corrupted_check = _check_result(corrupted_quality, name)
        repaired_check = _check_result(repaired_quality, name)
        quality_comparison_rows.append(
            [
                name,
                _status(corrupted_check.get("passed")),
                _format_value(corrupted_check.get("failed_rows")),
                _status(repaired_check.get("passed")),
                _format_value(repaired_check.get("failed_rows")),
            ]
        )

    freshness_rows = [
        [
            "stale_rows",
            _format_value(corrupted_freshness.get("stale_rows")),
            _format_value(repaired_freshness.get("stale_rows")),
        ],
        [
            "invalid_date_rows",
            _format_value(corrupted_freshness.get("invalid_date_rows")),
            _format_value(repaired_freshness.get("invalid_date_rows")),
        ],
        [
            "latest_published",
            _format_value(corrupted_freshness.get("latest_published")),
            _format_value(repaired_freshness.get("latest_published")),
        ],
        [
            "oldest_published",
            _format_value(corrupted_freshness.get("oldest_published")),
            _format_value(repaired_freshness.get("oldest_published")),
        ],
        [
            "is_fresh",
            _status(corrupted_freshness.get("is_fresh")),
            _status(repaired_freshness.get("is_fresh")),
        ],
    ]

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    corrupted_valid = bool(corrupted_quality.get("is_valid", corrupted_quality.get("passed", False)))
    repaired_valid = bool(repaired_quality.get("is_valid", repaired_quality.get("passed", False)))

    lines = [
        "# Corruption and Recovery Evaluation Report",
        "",
        f"- **Generated at:** {generated_at}",
        f"- **Metrics degraded after corruption:** {len(degraded_metrics)}/{len(metric_names)}",
        f"- **Metrics improved after repair:** {len(improved_metrics)}/{len(metric_names)}",
        f"- **Metrics restored to baseline or better:** {len(recovered_metrics)}/{len(metric_names)}",
        f"- **Corrupted data quality:** {_status(corrupted_valid)}",
        f"- **Repaired data quality:** {_status(repaired_valid)}",
        "",
        "## 1. RAG quality comparison",
        "",
        _table(
            (
                "Metric",
                "Baseline",
                "Corrupted",
                "Repaired",
                "Corruption Δ",
                "Repair Δ",
                "Recovery",
            ),
            metric_rows or [["metrics", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"]],
        ),
        "",
        "> Corruption Δ = corrupted − baseline. Repair Δ = repaired − corrupted. "
        "For the listed RAG metrics, higher values are better.",
        "",
        "## 2. Data-quality recovery",
        "",
        _table(
            ("Check", "Corrupted", "Failed rows", "Repaired", "Failed rows"),
            quality_comparison_rows
            or [["checks", "N/A", "N/A", "N/A", "N/A"]],
        ),
        "",
        "### Aggregate quality signals",
        "",
        _table(
            ("Signal", "Corrupted", "Repaired"),
            [
                [
                    "row_count",
                    _format_value(corrupted_quality.get("row_count")),
                    _format_value(repaired_quality.get("row_count")),
                ],
                [
                    "total_null_count",
                    _format_value(corrupted_quality.get("total_null_count")),
                    _format_value(repaired_quality.get("total_null_count")),
                ],
                [
                    "duplicate_count",
                    _format_value(corrupted_quality.get("duplicate_count")),
                    _format_value(repaired_quality.get("duplicate_count")),
                ],
                [
                    "failed_checks",
                    _format_value(corrupted_quality.get("failed_checks")),
                    _format_value(repaired_quality.get("failed_checks")),
                ],
            ],
        ),
        "",
        "## 3. Freshness recovery",
        "",
        _table(("Signal", "Corrupted", "Repaired"), freshness_rows),
        "",
        "## 4. Findings",
        "",
    ]

    if degraded_metrics:
        lines.append(
            "- Corruption reduced: " + ", ".join(f"`{name}`" for name in degraded_metrics) + "."
        )
    else:
        lines.append(
            "- No available RAG metric decreased after corruption. The experiment does not currently "
            "demonstrate a measurable degradation, or the required metrics are missing."
        )

    if improved_metrics:
        lines.append(
            "- Repair improved: " + ", ".join(f"`{name}`" for name in improved_metrics) + "."
        )
    else:
        lines.append("- No available RAG metric improved after repair.")

    if recovered_metrics:
        lines.append(
            "- Reached baseline or better: "
            + ", ".join(f"`{name}`" for name in recovered_metrics)
            + "."
        )

    if not corrupted_valid and repaired_valid:
        lines.append("- The repair moved the dataset from failing to passing the configured quality gates.")
    elif not repaired_valid:
        lines.append("- The repaired dataset still fails one or more configured quality gates.")

    lines.extend(
        [
            "",
            "## 5. Conclusion",
            "",
        ]
    )
    if degraded_metrics and improved_metrics:
        lines.append(
            "The observed direction is consistent with the hypothesis that degraded source data harms "
            "retrieval and answer quality, while repair recovers at least part of the lost performance. "
            "This is evidence for this experiment, not a claim of universal causality."
        )
    elif degraded_metrics:
        lines.append(
            "Corruption harmed at least one measured RAG dimension, but the repair did not produce a clear "
            "measured recovery. Review the repair rules, index rebuild, and evaluation coverage."
        )
    else:
        lines.append(
            "This run does not yet provide clear evidence that corruption harmed RAG quality. Verify that "
            "the corrupted data was actually indexed and that the test set targets the affected documents."
        )

    lines.extend(
        [
            "",
            "## Appendix — Machine-readable inputs",
            "",
            "### Baseline metrics",
            "",
            _json_block(baseline_metrics),
            "",
            "### Corrupted metrics",
            "",
            _json_block(corrupted_metrics),
            "",
            "### Repaired metrics",
            "",
            _json_block(repaired_metrics),
            "",
            "### Corrupted quality and freshness",
            "",
            _json_block({"quality": corrupted_quality, "freshness": corrupted_freshness}),
            "",
            "### Repaired quality and freshness",
            "",
            _json_block({"quality": repaired_quality, "freshness": repaired_freshness}),
        ]
    )
    _write_markdown(report_path, "\n".join(lines))