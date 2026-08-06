from __future__ import annotations

import ast
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json


# CP0 requires ground_truth_doc_ids to come from the cleaned paper_id.
# Other fields may still use common aliases to remain compatible with
# slightly different cleaned schemas.
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "paper_id": ("paper_id",),
    "title": ("title", "paper_title", "name"),
    "summary": ("summary", "abstract", "description"),
    "authors": (
        "authors",
        "authors_joined",
        "author",
        "author_names",
    ),
    "date": (
        "published",
        "published_at",
        "publication_date",
        "date",
        "updated",
    ),
    "categories": (
        "categories",
        "categories_joined",
        "category",
        "subjects",
        "tags",
    ),
}

_MIN_DOCUMENTS = 4
_MAX_SELECTED_DOCUMENTS = 5


def _resolve_columns(df: pd.DataFrame) -> dict[str, str]:
    """Resolve canonical fields to actual dataframe columns.

    ``paper_id`` is intentionally strict: the cleaned dataframe must expose
    that exact column because retrieval returns ``SearchResult.paper_id``.
    """
    columns_by_lower = {
        str(column).strip().casefold(): str(column)
        for column in df.columns
    }

    resolved: dict[str, str] = {}
    missing: list[str] = []

    for canonical, aliases in _COLUMN_ALIASES.items():
        match = next(
            (
                columns_by_lower[alias.casefold()]
                for alias in aliases
                if alias.casefold() in columns_by_lower
            ),
            None,
        )

        if match is None and canonical != "categories":
            missing.append(f"{canonical} ({', '.join(aliases)})")
        elif match is not None:
            resolved[canonical] = match

    if missing:
        raise ValueError(
            "Cannot build the evaluation set because required columns "
            f"are missing: {'; '.join(missing)}."
        )

    return resolved


def _is_missing(value: Any) -> bool:
    """Return True for scalar null-like values."""
    if value is None:
        return True

    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False

    return bool(result) if isinstance(result, bool) else False


def _as_text(value: Any) -> str:
    """Convert a scalar value to normalized text."""
    if _is_missing(value):
        return ""

    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    return normalize_whitespace(str(value))


def _parse_serialized_collection(text: str) -> Any:
    """Parse JSON/Python collection strings when possible."""
    stripped = text.strip()
    if not stripped:
        return None

    if stripped[:1] not in "[{(" or stripped[-1:] not in "]})":
        return None

    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(stripped)
        except (ValueError, SyntaxError, json.JSONDecodeError, TypeError):
            continue

    return None


def _as_items(value: Any) -> list[str]:
    """Convert authors/categories into a deduplicated list of strings."""
    if _is_missing(value):
        return []

    values: Iterable[Any]

    if isinstance(value, dict):
        values = value.values()
    elif isinstance(value, (list, tuple, set)):
        values = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return []

        parsed = _parse_serialized_collection(text)

        if isinstance(parsed, dict):
            values = parsed.values()
        elif isinstance(parsed, (list, tuple, set)):
            values = parsed
        else:
            if ";" in text:
                values = text.split(";")
            elif "," in text:
                values = text.split(",")
            else:
                values = [text]
    else:
        values = [value]

    items: list[str] = []
    seen: set[str] = set()

    for item in values:
        normalized = _as_text(item)
        if not normalized:
            continue

        key = normalized.casefold()
        if key in seen:
            continue

        seen.add(key)
        items.append(normalized)

    return items


def _format_date(value: Any) -> str:
    """Convert a publication date to stable ISO-like text."""
    if _is_missing(value):
        return ""

    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return _as_text(value)


def _representative_positions(
    row_count: int,
    sample_size: int,
) -> list[int]:
    """Choose deterministic positions spread across the valid records."""
    if row_count <= 0:
        return []

    if sample_size >= row_count:
        return list(range(row_count))

    if sample_size == 1:
        return [row_count // 2]

    positions = {
        round(index * (row_count - 1) / (sample_size - 1))
        for index in range(sample_size)
    }

    if len(positions) < sample_size:
        for position in range(row_count):
            positions.add(position)
            if len(positions) == sample_size:
                break

    return sorted(positions)[:sample_size]


def _question_rows(
    *,
    sequence_start: int,
    paper_id: str,
    title: str,
    summary: str,
    authors: list[str],
    published: str,
    categories: list[str],
) -> list[dict[str, Any]]:
    """Create QA-compatible test cases for one paper.

    Category questions are only created when the source contains categories;
    Crossref records are allowed to omit that field.
    """
    # qa.py extracts title using r"'([^']+)'".
    safe_title = title.replace("'", "’")

    facts = [
        (
            "summary",
            f"What is the paper '{safe_title}' about?",
            first_sentence(summary),
        ),
        (
            "authors",
            f"Who authored the paper '{safe_title}'?",
            ", ".join(authors),
        ),
        (
            "date",
            f"When was the paper '{safe_title}' published?",
            published,
        ),
    ]

    if categories:
        facts.append(
            (
                "categories",
                f"What categories does the paper '{safe_title}' belong to?",
                ", ".join(categories),
            )
        )

    return [
        {
            "id": f"eval-{sequence_start + offset:03d}",
            "question_type": question_type,
            "question": question,
            "ground_truth": ground_truth,
            "ground_truth_doc_ids": [paper_id],
        }
        for offset, (
            question_type,
            question,
            ground_truth,
        ) in enumerate(facts)
    ]


def build_test_set(
    df: pd.DataFrame,
    output_path,
) -> list[dict[str, Any]]:
    """Build and persist a deterministic evaluation set from cleaned papers.

    Up to five representative papers are selected. Summary, authors and
    publication-date questions are created for every selected paper; a
    categories question is added only when category data is available.

    ``ground_truth_doc_ids`` always contains the cleaned ``paper_id`` so it can
    be compared directly with ``AnswerResult.retrieved_doc_ids``.

    Args:
        df: Cleaned paper dataframe.
        output_path: JSON destination accepted by ``core.utils.write_json``.

    Returns:
        The generated evaluation examples.

    Raises:
        TypeError: If ``df`` is not a pandas DataFrame.
        ValueError: If required columns are missing or fewer than four complete
            papers with unique, non-null ``paper_id`` values remain.
        IsADirectoryError: If ``output_path`` points to a directory.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    if df.empty:
        raise ValueError("Cannot build a test set from an empty dataframe.")

    columns = _resolve_columns(df)

    records: list[dict[str, Any]] = []
    seen_paper_ids: set[str] = set()

    for _, row in df.iterrows():
        paper_id = _as_text(row[columns["paper_id"]])
        title = _as_text(row[columns["title"]])
        summary = _as_text(row[columns["summary"]])
        authors = _as_items(row[columns["authors"]])
        published = _format_date(row[columns["date"]])
        categories = (
            _as_items(row[columns["categories"]])
            if "categories" in columns
            else []
        )

        if not all(
            (
                paper_id,
                title,
                summary,
                authors,
                published,
            )
        ):
            continue

        if paper_id in seen_paper_ids:
            continue

        seen_paper_ids.add(paper_id)

        records.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "published": published,
                "categories": categories,
            }
        )

    if len(records) < _MIN_DOCUMENTS:
        raise ValueError(
            f"At least {_MIN_DOCUMENTS} complete papers with unique, "
            f"non-null paper_id values are required; found {len(records)}."
        )

    sample_size = min(_MAX_SELECTED_DOCUMENTS, len(records))

    selected = [
        records[position]
        for position in _representative_positions(
            len(records),
            sample_size,
        )
    ]

    test_set: list[dict[str, Any]] = []

    for paper in selected:
        test_set.extend(
            _question_rows(
                sequence_start=len(test_set) + 1,
                paper_id=paper["paper_id"],
                title=paper["title"],
                summary=paper["summary"],
                authors=paper["authors"],
                published=paper["published"],
                categories=paper["categories"],
            )
        )

    if isinstance(output_path, (str, Path)):
        output = Path(output_path)
        if output.exists() and output.is_dir():
            raise IsADirectoryError(
                f"output_path points to a directory: {output_path}"
            )

    write_json(output_path, test_set)
    return test_set
