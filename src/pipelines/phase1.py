from __future__ import annotations

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord, fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def _load_or_fetch_records(settings: Settings) -> list[PaperRecord]:
    paths = settings.paths
    if settings.refresh_source or not paths.raw_records_json.exists():
        return fetch_source_records(settings)
    return load_raw_records(paths.raw_records_json)


def _load_or_build_test_set(df, settings: Settings) -> list[dict]:
    paths = settings.paths
    if settings.refresh_test_set or not paths.eval_testset.exists():
        return build_test_set(df, paths.eval_testset)
    return read_json(paths.eval_testset)


def main() -> None:
    settings = load_settings()
    paths = settings.paths
    run_date = now_utc()

    records = _load_or_fetch_records(settings)
    df = build_clean_dataframe(records, run_date)
    if df.empty:
        raise RuntimeError("Cleaning produced an empty dataframe; check raw records and cleaning rules.")

    write_csv(df, paths.clean_csv)
    write_json(paths.clean_json, df.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(df, settings, embeddings_output_path=paths.embeddings_json)

    test_set = _load_or_build_test_set(df, settings)

    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=paths.eval_testset,
        metrics_output_path=paths.baseline_metrics,
        answers_output_path=paths.baseline_answers,
    )

    quality = run_data_quality_checks(df, settings, report_name="phase1_quality")
    freshness = build_freshness_report(df, settings, paths.freshness_report)

    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "raw_record_count": len(records),
        "clean_row_count": int(len(df)),
        "test_set_size": len(test_set),
        "collection_name": index.collection_name,
        "embedding_model": settings.embedding_model,
        "generated_at": run_date.isoformat(),
    }

    generate_phase1_report(
        report_path=paths.baseline_report,
        source_summary=source_summary,
        metrics=evaluation.summary,
        quality=quality,
        freshness=freshness,
    )


if __name__ == "__main__":
    main()
