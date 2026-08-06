from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

import pandas as pd

from core.config import Settings
from core.utils import write_json


_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "paper_id": ("paper_id", "doc_id", "document_id", "id", "entry_id"),
    "title": ("title", "paper_title", "name"),
    "summary": ("summary", "abstract", "description"),
    "published": (
        "published",
        "published_at",
        "publication_date",
        "date",
        "created",
        "updated",
    ),
    "age_days": ("age_days", "document_age_days", "paper_age_days"),
    "source_timestamp": (
        "source_timestamp",
        "fetched_at",
        "retrieved_at",
        "ingested_at",
        "loaded_at",
    ),
}

_DEFAULT_MIN_ROWS = 1
_DEFAULT_MIN_SUMMARY_CHARS = 80
_DEFAULT_MAX_AGE_DAYS = 3650


def _setting(settings: Settings, names: Iterable[str], default: Any) -> Any:
    """Read a setting from either an object or mapping, with alias support."""
    for name in names:
        if isinstance(settings, Mapping) and name in settings:
            value = settings[name]
        else:
            value = getattr(settings, name, None)
        if value is not None:
            return value
    return default


def _int_setting(settings: Settings, names: Iterable[str], default: int) -> int:
    value = _setting(settings, names, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _resolve_column(df: pd.DataFrame, canonical: str) -> str | None:
    columns = {str(column).strip().casefold(): str(column) for column in df.columns}
    return next(
        (columns[alias.casefold()] for alias in _COLUMN_ALIASES[canonical] if alias.casefold() in columns),
        None,
    )


def _missing_mask(series: pd.Series) -> pd.Series:
    """Treat null and whitespace-only scalar values as missing."""
    mask = series.isna()
    try:
        text_mask = series.astype("string").str.strip().eq("").fillna(False)
    except (AttributeError, TypeError, ValueError):
        text_mask = pd.Series(False, index=series.index)
    return (mask | text_mask).astype(bool)


def _as_utc_timestamp(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _as_of_timestamp(settings: Settings) -> pd.Timestamp:
    configured = _setting(
        settings,
        ("quality_as_of", "freshness_as_of", "as_of_date", "reference_date"),
        None,
    )
    if configured is None:
        return pd.Timestamp.now(tz="UTC")
    try:
        return _as_utc_timestamp(configured)
    except (TypeError, ValueError, OverflowError):
        return pd.Timestamp.now(tz="UTC")


def _to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def _calculate_age_days(published: pd.Series, as_of: pd.Timestamp) -> pd.Series:
    dates = _to_datetime(published)
    return (as_of - dates).dt.total_seconds().div(86_400).apply(
        lambda value: int(value // 1) if pd.notna(value) else float("nan")
    )


def _freshness_values(
    df: pd.DataFrame,
    settings: Settings,
) -> tuple[pd.Series, pd.Series, str | None, str | None, pd.Timestamp]:
    """Return parsed dates, numeric age values, source columns, and as-of time."""
    published_column = _resolve_column(df, "published")
    age_column = _resolve_column(df, "age_days")
    as_of = _as_of_timestamp(settings)

    if published_column is None:
        dates = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    else:
        dates = _to_datetime(df[published_column])

    if age_column is not None:
        ages = pd.to_numeric(df[age_column], errors="coerce")
    elif published_column is not None:
        ages = _calculate_age_days(df[published_column], as_of)
    else:
        ages = pd.Series(float("nan"), index=df.index, dtype="float64")

    return dates, ages, published_column, age_column, as_of


def _iso_or_none(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    try:
        timestamp = _as_utc_timestamp(value)
    except (TypeError, ValueError, OverflowError):
        return str(value)
    return timestamp.isoformat().replace("+00:00", "Z")


def _quality_output_path(settings: Settings, report_name: str) -> Path:
    configured_dir = _setting(
        settings,
        (
            "quality_dir",
            "data_quality_dir",
            "quality_output_dir",
            "quality_reports_dir",
        ),
        None,
    )
    if configured_dir is None:
        data_dir = _setting(settings, ("data_dir", "data_path"), Path("data"))
        configured_dir = Path(data_dir) / "quality"

    safe_name = Path(str(report_name)).name.strip()
    if not safe_name:
        raise ValueError("report_name must not be empty.")
    if not safe_name.lower().endswith(".json"):
        safe_name = f"{safe_name}.json"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", safe_name)
    return Path(configured_dir) / safe_name


def _write_payload(path: str | Path, payload: dict[str, Any]) -> None:
    destination = Path(path)
    if destination.exists() and destination.is_dir():
        raise IsADirectoryError(f"Report path points to a directory: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_json(destination, payload)


def _source_timestamp(df: pd.DataFrame) -> str | None:
    column = _resolve_column(df, "source_timestamp")
    if column is None or df.empty:
        return None
    timestamps = _to_datetime(df[column]).dropna()
    return _iso_or_none(timestamps.max()) if not timestamps.empty else None


def _length_stats(lengths: pd.Series) -> dict[str, float | int | None]:
    valid = pd.to_numeric(lengths, errors="coerce").dropna()
    if valid.empty:
        return {"min": None, "median": None, "mean": None, "max": None}
    return {
        "min": int(valid.min()),
        "median": float(valid.median()),
        "mean": float(valid.mean()),
        "max": int(valid.max()),
    }


def run_data_quality_checks(
    df: pd.DataFrame,
    settings: Settings,
    report_name: str,
) -> dict[str, Any]:
    """Run core quality checks and persist a JSON report under ``data/quality``.

    The function is deliberately tolerant of common clean-schema aliases, but
    every absent required field becomes a failed check rather than being
    silently ignored.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    min_rows = _int_setting(
        settings,
        ("quality_min_rows", "min_row_count", "minimum_row_count", "min_rows"),
        _DEFAULT_MIN_ROWS,
    )
    min_summary_chars = _int_setting(
        settings,
        (
            "quality_min_summary_chars",
            "min_summary_chars",
            "summary_min_length",
            "min_summary_length",
        ),
        _DEFAULT_MIN_SUMMARY_CHARS,
    )
    max_age_days = _int_setting(
        settings,
        (
            "freshness_max_age_days",
            "freshness_threshold_days",
            "max_age_days",
            "stale_after_days",
            "freshness_days",
        ),
        _DEFAULT_MAX_AGE_DAYS,
    )

    row_count = int(len(df))
    null_counts = {
        str(column): int(_missing_mask(df[column]).sum())
        for column in df.columns
    }

    paper_id_column = _resolve_column(df, "paper_id")
    title_column = _resolve_column(df, "title")
    summary_column = _resolve_column(df, "summary")

    if paper_id_column is None:
        paper_id_nulls = row_count
        duplicate_rows = 0
        duplicate_values = 0
    else:
        paper_id_missing = _missing_mask(df[paper_id_column])
        paper_id_nulls = int(paper_id_missing.sum())
        paper_ids = df.loc[~paper_id_missing, paper_id_column].astype("string").str.strip()
        duplicate_rows = int(paper_ids.duplicated(keep="first").sum())
        duplicate_values = int(paper_ids[paper_ids.duplicated(keep=False)].nunique())

    if title_column is None:
        title_nulls = row_count
    else:
        title_nulls = int(_missing_mask(df[title_column]).sum())

    if summary_column is None:
        summary_nulls = row_count
        short_summary_rows = row_count
        summary_lengths = pd.Series(dtype="float64")
    else:
        summary_missing = _missing_mask(df[summary_column])
        summary_nulls = int(summary_missing.sum())
        summary_lengths = df[summary_column].astype("string").fillna("").str.strip().str.len()
        short_summary_rows = int((summary_missing | (summary_lengths < min_summary_chars)).sum())

    dates, ages, published_column, age_column, as_of = _freshness_values(df, settings)
    valid_ages = ages.notna()
    invalid_age_rows = int((~valid_ages).sum())
    stale_rows = int((valid_ages & (ages > max_age_days)).sum())
    future_rows = int((valid_ages & (ages < 0)).sum())

    checks: dict[str, dict[str, Any]] = {
        "row_count": {
            "passed": row_count >= min_rows,
            "value": row_count,
            "minimum": min_rows,
            "failed_rows": max(min_rows - row_count, 0),
        },
        "paper_id_not_null": {
            "passed": paper_id_column is not None and paper_id_nulls == 0,
            "column": paper_id_column,
            "null_rows": paper_id_nulls,
            "failed_rows": paper_id_nulls,
        },
        "paper_id_unique": {
            "passed": paper_id_column is not None and duplicate_rows == 0,
            "column": paper_id_column,
            "duplicate_rows": duplicate_rows,
            "duplicate_values": duplicate_values,
            "failed_rows": duplicate_rows,
        },
        "title_not_null": {
            "passed": title_column is not None and title_nulls == 0,
            "column": title_column,
            "null_rows": title_nulls,
            "failed_rows": title_nulls,
        },
        "summary_length": {
            "passed": summary_column is not None and short_summary_rows == 0,
            "column": summary_column,
            "minimum_characters": min_summary_chars,
            "null_rows": summary_nulls,
            "short_rows": short_summary_rows,
            "length_stats": _length_stats(summary_lengths),
            "failed_rows": short_summary_rows,
        },
        "freshness": {
            "passed": (
                row_count > 0
                and (published_column is not None or age_column is not None)
                and invalid_age_rows == 0
                and stale_rows == 0
                and future_rows == 0
            ),
            "published_column": published_column,
            "age_days_column": age_column,
            "maximum_age_days": max_age_days,
            "invalid_age_rows": invalid_age_rows,
            "stale_rows": stale_rows,
            "future_rows": future_rows,
            "failed_rows": invalid_age_rows + stale_rows + future_rows,
        },
    }

    failed_checks = [name for name, result in checks.items() if not result["passed"]]
    payload: dict[str, Any] = {
        "report_name": Path(str(report_name)).stem,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "as_of": as_of.isoformat().replace("+00:00", "Z"),
        "source_timestamp": _source_timestamp(df),
        "row_count": row_count,
        "column_count": int(len(df.columns)),
        "columns": [str(column) for column in df.columns],
        "null_counts": null_counts,
        "total_null_count": int(sum(null_counts.values())),
        "duplicate_count": duplicate_rows,
        "stale_rows": stale_rows,
        "thresholds": {
            "minimum_rows": min_rows,
            "minimum_summary_characters": min_summary_chars,
            "maximum_age_days": max_age_days,
        },
        "checks": checks,
        "passed_checks": len(checks) - len(failed_checks),
        "failed_checks": failed_checks,
        "is_valid": not failed_checks,
        "passed": not failed_checks,
    }

    output_path = _quality_output_path(settings, report_name)
    payload["report_path"] = str(output_path)
    _write_payload(output_path, payload)
    return payload


def build_freshness_report(
    df: pd.DataFrame,
    settings: Settings,
    report_path,
) -> dict[str, Any]:
    """Build and persist a dataset freshness report.

    ``age_days`` is used when available. Otherwise, ages are derived from the
    publication date relative to a configurable as-of date or the current UTC
    time.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    max_age_days = _int_setting(
        settings,
        (
            "freshness_max_age_days",
            "freshness_threshold_days",
            "max_age_days",
            "stale_after_days",
            "freshness_days",
        ),
        _DEFAULT_MAX_AGE_DAYS,
    )
    dates, ages, published_column, age_column, as_of = _freshness_values(df, settings)

    # If only age_days exists, infer dates so the required latest/oldest fields
    # remain meaningful and internally consistent.
    if dates.notna().sum() == 0 and ages.notna().any():
        dates = as_of - pd.to_timedelta(ages, unit="D")

    valid_dates = dates.dropna()
    valid_ages = ages.notna()
    stale_mask = valid_ages & (ages > max_age_days)
    future_mask = valid_ages & (ages < 0)
    invalid_mask = ~valid_ages

    total_rows = int(len(df))
    stale_rows = int(stale_mask.sum())
    future_rows = int(future_mask.sum())
    invalid_rows = int(invalid_mask.sum())
    fresh_rows = int((valid_ages & ~stale_mask & ~future_mask).sum())

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "as_of": as_of.isoformat().replace("+00:00", "Z"),
        "source_timestamp": _source_timestamp(df),
        "published_column": published_column,
        "age_days_column": age_column,
        "latest_published": _iso_or_none(valid_dates.max()) if not valid_dates.empty else None,
        "oldest_published": _iso_or_none(valid_dates.min()) if not valid_dates.empty else None,
        "maximum_age_days": max_age_days,
        "stale_rows": stale_rows,
        "fresh_rows": fresh_rows,
        "future_rows": future_rows,
        "invalid_date_rows": invalid_rows,
        "valid_published_rows": int(valid_dates.shape[0]),
        "total_rows": total_rows,
        "stale_ratio": (stale_rows / total_rows) if total_rows else 0.0,
        "is_fresh": (
            total_rows > 0
            and (published_column is not None or age_column is not None)
            and stale_rows == 0
            and future_rows == 0
            and invalid_rows == 0
        ),
    }

    _write_payload(report_path, payload)
    return payload
