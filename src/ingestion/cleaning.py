from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed."""
    rows: list[dict] = []

    for record in records:
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)
        published_date = _parse_date(record.published)

        if not record.paper_id or not title or not summary or published_date is None:
            continue

        authors = list(dict.fromkeys(a for a in (record.authors or []) if a))
        categories = list(dict.fromkeys(c for c in (record.categories or []) if c))
        if not categories and record.primary_category:
            # Crossref rarely returns `subject` anymore; fall back to the
            # PaperRecord's primary_category so downstream test-set/quality
            # checks always see a non-empty category value.
            categories = [record.primary_category]
        authors_joined = compact_join(authors)
        categories_joined = compact_join(categories)
        text_for_embedding = normalize_whitespace(f"{title}. {summary}")

        rows.append(
            {
                "paper_id": record.paper_id,
                "title": title,
                "summary": summary,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "primary_category": record.primary_category,
                "published": published_date.isoformat(),
                "updated": record.updated or published_date.isoformat(),
                "age_days": (run_date.date() - published_date).days,
                "summary_chars": len(summary),
                "text_for_embedding": text_for_embedding,
                "abs_url": record.abs_url,
                "pdf_url": record.pdf_url,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.sort_values("published", ascending=False, kind="stable")
    df = df.drop_duplicates(subset="paper_id", keep="first")
    df = df.reset_index(drop=True)
    return df
