from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

CROSSREF_API_URL = "https://api.crossref.org/works"
RETRYABLE_STATUS_CODES = {429, 503}
MAX_RETRIES = 5


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _strip_jats_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "")


def _date_from_parts(item: dict, *keys: str) -> str:
    for key in keys:
        node = item.get(key)
        if not node:
            continue
        parts = node.get("date-parts")
        if not parts or not parts[0]:
            continue
        values = parts[0]
        year = values[0] if len(values) > 0 else 1
        month = values[1] if len(values) > 1 else 1
        day = values[2] if len(values) > 2 else 1
        try:
            return f"{year:04d}-{month:02d}-{day:02d}"
        except (TypeError, ValueError):
            continue
    return ""


def _pdf_url_from_links(item: dict) -> str:
    for link in item.get("link", []) or []:
        if link.get("content-type") == "application/pdf":
            return link.get("URL", "")
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref `/works` payload thanh list `PaperRecord`."""
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        doi = item.get("DOI", "").strip()
        titles = item.get("title") or []
        title = normalize_whitespace(titles[0]) if titles else ""
        summary = normalize_whitespace(_strip_jats_tags(item.get("abstract", "")))

        if not doi or not title or not summary:
            continue

        authors = [
            normalize_whitespace(f"{author.get('given', '')} {author.get('family', '')}")
            for author in item.get("author", []) or []
            if author.get("given") or author.get("family")
        ]
        categories = [normalize_whitespace(subject) for subject in item.get("subject", []) or []]
        primary_category = categories[0] if categories else "unknown"

        published = _date_from_parts(item, "published-print", "published-online", "issued")
        updated = _date_from_parts(item, "deposited", "indexed") or published
        abs_url = item.get("URL") or f"https://doi.org/{doi}"
        pdf_url = _pdf_url_from_links(item)
        comment = normalize_whitespace((item.get("container-title") or [""])[0]) if item.get("container-title") else ""

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi Crossref API, luu raw response, parse thanh records."""
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }

    response = None
    for attempt in range(MAX_RETRIES):
        response = requests.get(CROSSREF_API_URL, params=params, timeout=30)
        if response.status_code not in RETRYABLE_STATUS_CODES:
            break
        time.sleep(2**attempt)
    response.raise_for_status()

    payload = response.json()
    write_json(settings.paths.raw_api_response, payload)

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh `PaperRecord`."""
    payload = read_json(path)
    return [PaperRecord(**record) for record in payload]
