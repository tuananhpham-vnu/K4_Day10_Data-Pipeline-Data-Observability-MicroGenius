from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json

MIN_SUMMARY_CHARS = 20


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chay cac data quality check co ban tren cleaned dataframe."""
    checks: list[dict[str, Any]] = []

    row_count = len(df)
    checks.append({"check": "row_count", "passed": row_count > 0, "details": {"row_count": row_count}})

    if row_count == 0:
        result = {"report_name": report_name, "checks": checks, "overall_passed": False}
        write_json(settings.paths.quality_dir / f"{report_name}.json", result)
        return result

    paper_id_missing = int((df["paper_id"].isna() | (df["paper_id"].astype(str).str.strip() == "")).sum())
    checks.append(
        {"check": "paper_id_not_null", "passed": paper_id_missing == 0, "details": {"missing_count": paper_id_missing}}
    )

    paper_id_unique = bool(df["paper_id"].is_unique)
    duplicate_count = int(df["paper_id"].duplicated().sum())
    checks.append(
        {"check": "paper_id_unique", "passed": paper_id_unique, "details": {"duplicate_count": duplicate_count}}
    )

    title_missing = int((df["title"].isna() | (df["title"].astype(str).str.strip() == "")).sum())
    checks.append({"check": "title_not_null", "passed": title_missing == 0, "details": {"missing_count": title_missing}})

    short_summary_count = int((df["summary_chars"] < MIN_SUMMARY_CHARS).sum())
    checks.append(
        {
            "check": "summary_min_length",
            "passed": short_summary_count == 0,
            "details": {"threshold_chars": MIN_SUMMARY_CHARS, "short_summary_count": short_summary_count},
        }
    )

    stale_count = int((df["age_days"] > settings.freshness_threshold_days).sum())
    checks.append(
        {
            "check": "freshness",
            "passed": stale_count == 0,
            "details": {"threshold_days": settings.freshness_threshold_days, "stale_count": stale_count},
        }
    )

    result = {
        "report_name": report_name,
        "checks": checks,
        "overall_passed": all(check["passed"] for check in checks),
    }
    write_json(settings.paths.quality_dir / f"{report_name}.json", result)
    return result


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop freshness report tu cleaned dataframe."""
    total_rows = len(df)
    if total_rows == 0:
        payload = {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": 0,
            "is_fresh": False,
        }
        write_json(report_path, payload)
        return payload

    stale_rows = int((df["age_days"] > settings.freshness_threshold_days).sum())
    payload = {
        "latest_published": df["published"].max(),
        "oldest_published": df["published"].min(),
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "is_fresh": stale_rows == 0,
    }
    write_json(report_path, payload)
    return payload
