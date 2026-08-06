from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def _load_clean_dataframe(settings) -> pd.DataFrame:
    clean_path = settings.paths.clean_json
    raw_path = settings.paths.raw_records_json

    # Rebuild from raw whenever the snapshot exists so a stale or malformed
    # clean artifact cannot contaminate the corruption experiment.
    if raw_path.exists() or settings.refresh_source:
        records = _load_raw_records(settings)
        clean_df = build_clean_dataframe(records, run_date=now_utc())
        if clean_df.empty:
            raise RuntimeError("Cleaning produced no valid baseline paper records.")
        write_csv(clean_df, settings.paths.clean_csv)
        write_json(clean_path, clean_df.to_dict(orient="records"))
        return clean_df

    if clean_path.exists():
        return pd.DataFrame(read_json(clean_path))

    raise FileNotFoundError(
        "Neither the raw records snapshot nor the clean baseline dataset exists."
    )


def _load_raw_records(settings):
    raw_path = settings.paths.raw_records_json
    if raw_path.exists() and not settings.refresh_source:
        return load_raw_records(raw_path)
    return fetch_source_records(settings)


def _save_clean_artifacts(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def _ensure_test_set(clean_df: pd.DataFrame, settings) -> None:
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        build_test_set(clean_df, settings.paths.eval_testset)


def _freshness_path(settings, name: str) -> Path:
    return settings.paths.quality_dir / name


def main() -> None:
    """Run corruption, evaluation, repair, and comparison flow.

    Pseudo-code:
    1. Load baseline metrics va clean dataset.
    2. Tao corrupted dataframe.
    3. Save corrupted artifacts.
    4. Rebuild index va evaluate.
    5. Run quality checks/freshness tren corrupted data.
    6. Repair lai tu raw records.
    7. Evaluate repaired dataset.
    8. Tao comparison report.
    """
    settings = load_settings()

    baseline_df = _load_clean_dataframe(settings)
    if baseline_df.empty:
        raise RuntimeError("Baseline clean dataset is empty.")
    _ensure_test_set(baseline_df, settings)

    corrupted_df = corrupt_clean_dataframe(
        baseline_df,
        output_log_path=settings.paths.corruption_log,
    )
    _save_clean_artifacts(
        corrupted_df,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
    )

    corrupted_index = LocalEmbeddingIndex.build(
        df=corrupted_df,
        settings=settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    corrupted_evaluation = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(
        corrupted_df,
        settings=settings,
        report_name="corrupted_quality",
    )
    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings=settings,
        report_path=_freshness_path(settings, "freshness_corrupted.json"),
    )

    repaired_records = _load_raw_records(settings)
    repaired_df = build_clean_dataframe(repaired_records, run_date=now_utc())
    if repaired_df.empty:
        raise RuntimeError("Repair produced no valid paper records.")
    _save_clean_artifacts(
        repaired_df,
        settings.paths.repaired_clean_csv,
        settings.paths.repaired_clean_json,
    )

    repaired_index = LocalEmbeddingIndex.build(
        df=repaired_df,
        settings=settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    repaired_evaluation = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(
        repaired_df,
        settings=settings,
        report_name="repaired_quality",
    )
    repaired_freshness = build_freshness_report(
        repaired_df,
        settings=settings,
        report_path=_freshness_path(settings, "freshness_repaired.json"),
    )

    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=read_json(settings.paths.baseline_metrics),
        corrupted_metrics=corrupted_evaluation.summary,
        repaired_metrics=repaired_evaluation.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )

    print(
        "Corruption flow completed: "
        f"baseline={len(baseline_df)}, "
        f"corrupted={len(corrupted_df)}, "
        f"repaired={len(repaired_df)} papers."
    )
    print(f"Corruption log: {settings.paths.corruption_log}")
    print(f"Comparison report: {settings.paths.comparison_report}")
