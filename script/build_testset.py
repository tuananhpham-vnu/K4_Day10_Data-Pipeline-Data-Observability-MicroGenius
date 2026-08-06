from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from evaluation.testset import build_test_set


ROOT_DIR = Path(__file__).resolve().parents[1]

CLEAN_DATA_PATH = ROOT_DIR / "data" / "clean" / "papers_clean.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "eval" / "test_set.json"


def main() -> None:
    if not CLEAN_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Clean dataset not found: {CLEAN_DATA_PATH}"
        )

    clean_df = pd.read_csv(CLEAN_DATA_PATH)

    print("Clean dataset:", CLEAN_DATA_PATH)
    print("Rows:", len(clean_df))
    print("Columns:", clean_df.columns.tolist())

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    test_set = build_test_set(
        clean_df,
        OUTPUT_PATH,
    )

    required_fields = {
        "question",
        "ground_truth",
        "ground_truth_doc_ids",
        "question_type",
    }

    clean_paper_ids = set(
        clean_df["paper_id"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    for position, sample in enumerate(test_set):
        missing_fields = required_fields - sample.keys()

        if missing_fields:
            raise ValueError(
                f"Sample {position} is missing fields: "
                f"{sorted(missing_fields)}"
            )

        doc_ids = sample["ground_truth_doc_ids"]

        if not isinstance(doc_ids, list) or not doc_ids:
            raise ValueError(
                f"Sample {position} has invalid "
                "ground_truth_doc_ids."
            )

        unknown_ids = [
            paper_id
            for paper_id in doc_ids
            if str(paper_id) not in clean_paper_ids
        ]

        if unknown_ids:
            raise ValueError(
                f"Sample {position} contains paper IDs "
                f"not found in clean data: {unknown_ids}"
            )

    question_types = {
        sample["question_type"]
        for sample in test_set
    }

    expected_types = {
        "summary",
        "authors",
        "date",
        "categories",
    }

    if question_types != expected_types:
        raise ValueError(
            f"Unexpected question types: {question_types}. "
            f"Expected: {expected_types}"
        )

    # Kiểm tra file JSON vừa ghi có đọc lại được không.
    with OUTPUT_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        persisted_test_set = json.load(file)

    if persisted_test_set != test_set:
        raise ValueError(
            "Persisted JSON does not match returned test set."
        )

    print()
    print("Test set generated successfully.")
    print("Samples:", len(test_set))
    print("Question types:", sorted(question_types))
    print("Output:", OUTPUT_PATH)

    print()
    print("First four samples:")

    for sample in test_set[:4]:
        print(json.dumps(
            sample,
            ensure_ascii=False,
            indent=2,
        ))


if __name__ == "__main__":
    main()