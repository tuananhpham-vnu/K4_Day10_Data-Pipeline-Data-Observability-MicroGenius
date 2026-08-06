from __future__ import annotations

from datetime import date, timedelta
import random

import pandas as pd

from core.utils import normalize_whitespace, write_json

RANDOM_SEED = 42
DROP_LATEST_N = 2
BLANK_SUMMARY_N = 3
NOISE_N = 3
TRUNCATE_TITLE_N = 2
TRUNCATE_TITLE_CHARS = 15
STALE_DATE_N = 2
STALE_DATE_EXTRA_DAYS = 400
DUPLICATE_N = 2
NOISE_TEXT = " [CORRUPTED-NOISE lorem ipsum dolor sit amet] "


def _rebuild_text_for_embedding(row: pd.Series) -> str:
    return normalize_whitespace(f"{row['title']}. {row['summary']}")


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Simulate nhieu dang data corruption tren clean dataframe."""
    rng = random.Random(RANDOM_SEED)
    corrupted = df.sort_values("published", ascending=False, kind="stable").reset_index(drop=True)
    log_entries: list[dict] = []

    def log(paper_id: str, corruption_type: str, parameter, before, after) -> None:
        log_entries.append(
            {
                "paper_id": paper_id,
                "corruption_type": corruption_type,
                "parameter": parameter,
                "before": before,
                "after": after,
            }
        )

    before_count = len(corrupted)
    dropped_ids = corrupted.iloc[:DROP_LATEST_N]["paper_id"].tolist()
    corrupted = corrupted.iloc[DROP_LATEST_N:].reset_index(drop=True)
    for paper_id in dropped_ids:
        log(paper_id, "drop_latest", DROP_LATEST_N, before_count, len(corrupted))

    remaining_indices = list(corrupted.index)
    rng.shuffle(remaining_indices)

    blank_idx = remaining_indices[:BLANK_SUMMARY_N]
    for idx in blank_idx:
        before = corrupted.at[idx, "summary"]
        corrupted.at[idx, "summary"] = ""
        log(corrupted.at[idx, "paper_id"], "blank_summary", None, before, "")

    noise_idx = remaining_indices[BLANK_SUMMARY_N : BLANK_SUMMARY_N + NOISE_N]
    for idx in noise_idx:
        before = corrupted.at[idx, "summary"]
        corrupted.at[idx, "summary"] = normalize_whitespace(before + NOISE_TEXT)
        log(corrupted.at[idx, "paper_id"], "inject_noise", NOISE_TEXT.strip(), before, corrupted.at[idx, "summary"])

    truncate_idx = remaining_indices[
        BLANK_SUMMARY_N + NOISE_N : BLANK_SUMMARY_N + NOISE_N + TRUNCATE_TITLE_N
    ]
    for idx in truncate_idx:
        before = corrupted.at[idx, "title"]
        corrupted.at[idx, "title"] = before[:TRUNCATE_TITLE_CHARS]
        log(corrupted.at[idx, "paper_id"], "truncate_title", TRUNCATE_TITLE_CHARS, before, corrupted.at[idx, "title"])

    stale_idx = remaining_indices[
        BLANK_SUMMARY_N + NOISE_N + TRUNCATE_TITLE_N : BLANK_SUMMARY_N + NOISE_N + TRUNCATE_TITLE_N + STALE_DATE_N
    ]
    for idx in stale_idx:
        before = corrupted.at[idx, "published"]
        stale_date = date.fromisoformat(before) - timedelta(days=STALE_DATE_EXTRA_DAYS)
        corrupted.at[idx, "published"] = stale_date.isoformat()
        corrupted.at[idx, "age_days"] = corrupted.at[idx, "age_days"] + STALE_DATE_EXTRA_DAYS
        log(corrupted.at[idx, "paper_id"], "stale_date", STALE_DATE_EXTRA_DAYS, before, corrupted.at[idx, "published"])

    dup_candidates = remaining_indices[:DUPLICATE_N]
    if dup_candidates:
        duplicate_rows = corrupted.loc[dup_candidates]
        before_count = len(corrupted)
        corrupted = pd.concat([corrupted, duplicate_rows], ignore_index=True)
        for idx in dup_candidates:
            log(corrupted.at[idx, "paper_id"], "duplicate_row", None, before_count, len(corrupted))

    touched_idx = set(blank_idx) | set(noise_idx) | set(truncate_idx)
    for idx in touched_idx:
        corrupted.at[idx, "text_for_embedding"] = _rebuild_text_for_embedding(corrupted.loc[idx])
        corrupted.at[idx, "summary_chars"] = len(corrupted.at[idx, "summary"])

    write_json(output_log_path, log_entries)
    return corrupted
