from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

MIN_DOCUMENTS = 3
MAX_SAMPLE_PAPERS = 8


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Tao bo evaluation set tu cleaned dataframe.

    Cau hoi duoc viet dung format ma `retrieval.qa.answer_question` hieu:
    title trong dau nhay don de exact-lookup, va keyword dung voi tung
    question_type de `_extract_answer` tra ve dung field.
    """
    if df.empty or len(df) < MIN_DOCUMENTS:
        raise ValueError("Not enough clean documents to build a test set")

    rows: list[dict[str, Any]] = []
    for _, row in df.head(MAX_SAMPLE_PAPERS).iterrows():
        paper_id = row["paper_id"]
        title = row["title"]

        rows.append(
            {
                "id": f"{paper_id}::summary",
                "question_type": "summary",
                "question": f"What is the paper '{title}' about?",
                "ground_truth": first_sentence(row["summary"]),
                "ground_truth_doc_ids": [paper_id],
            }
        )

        if row["authors_joined"]:
            rows.append(
                {
                    "id": f"{paper_id}::authors",
                    "question_type": "authors",
                    "question": f"Who authored the paper '{title}'?",
                    "ground_truth": row["authors_joined"],
                    "ground_truth_doc_ids": [paper_id],
                }
            )

        rows.append(
            {
                "id": f"{paper_id}::date",
                "question_type": "date",
                "question": f"When was the paper '{title}' published?",
                "ground_truth": row["published"],
                "ground_truth_doc_ids": [paper_id],
            }
        )

        if row["categories_joined"]:
            rows.append(
                {
                    "id": f"{paper_id}::categories",
                    "question_type": "categories",
                    "question": f"What categories does the paper '{title}' belong to?",
                    "ground_truth": row["categories_joined"],
                    "ground_truth_doc_ids": [paper_id],
                }
            )

    write_json(output_path, rows)
    return rows
