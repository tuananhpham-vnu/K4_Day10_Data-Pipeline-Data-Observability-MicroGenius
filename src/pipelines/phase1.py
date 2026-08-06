from __future__ import annotations

import os

import pandas as pd

from core.config import load_settings, require_llm_credentials
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex


def _load_or_fetch_records(settings):
    raw_path = settings.paths.raw_records_json
    if settings.refresh_source or not raw_path.exists():
        return fetch_source_records(settings)
    return load_raw_records(raw_path)


def _save_clean_artifacts(clean_df: pd.DataFrame, settings) -> None:
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))


def _ensure_test_set(clean_df: pd.DataFrame, settings) -> None:
    test_set_path = settings.paths.eval_testset
    if settings.refresh_test_set or not test_set_path.exists():
        build_test_set(clean_df, test_set_path)


def _run_optional_agent_demo(settings, index: LocalEmbeddingIndex) -> None:
    """Run an LLM-backed demo only when explicitly enabled."""
    if os.getenv("RUN_AGENT_DEMO", "").lower() not in {"1", "true", "yes"}:
        return

    try:
        require_llm_credentials(settings)
        agent = build_agent(settings, index)
        questions = [
            "Which papers discuss retrieval augmented generation?",
            "What is the main contribution of the first indexed paper?",
        ]
        answers = [
            {"question": question, "answer": run_agent_question(agent, question)}
            for question in questions
        ]
        write_json(settings.paths.demo_answers, answers)
    except Exception as exc:
        write_json(
            settings.paths.demo_answers,
            {
                "status": "skipped",
                "reason": f"Agent demo unavailable: {type(exc).__name__}",
            },
        )


def main() -> None:
    """TODO(student): xay dung baseline pipeline end-to-end.

    Pseudo-code:
    1. Load settings.
    2. Load hoac fetch raw records.
    3. Clean data.
    4. Save clean CSV/JSON.
    5. Build Chroma index.
    6. Tao hoac load evaluation set.
    7. Evaluate.
    8. Run quality checks va freshness report.
    9. Tao markdown report.
    10. Co the demo agent tren vai sample question.
    """
    settings = load_settings()
    run_timestamp = now_utc()

    records = _load_or_fetch_records(settings)
    clean_df = build_clean_dataframe(records, run_date=run_timestamp)
    if clean_df.empty:
        raise RuntimeError("Cleaning produced no valid paper records.")
    _save_clean_artifacts(clean_df, settings)

    index = LocalEmbeddingIndex.build(
        df=clean_df,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )

    _ensure_test_set(clean_df, settings)
    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )

    quality = run_data_quality_checks(
        clean_df,
        settings=settings,
        report_name="baseline_quality",
    )
    freshness = build_freshness_report(
        clean_df,
        settings=settings,
        report_path=settings.paths.freshness_report,
    )

    source_summary = {
        "source_api": settings.source_api,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "records_loaded": len(records),
        "clean_records": len(clean_df),
        "raw_records_path": str(settings.paths.raw_records_json),
        "embedding_model": settings.embedding_model,
        "collection_name": index.collection_name,
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=evaluation.summary,
        quality=quality,
        freshness=freshness,
    )

    _run_optional_agent_demo(settings, index)

    print(f"Baseline pipeline completed: {len(clean_df)} clean papers.")
    print(f"Metrics: {settings.paths.baseline_metrics}")
    print(f"Report: {settings.paths.baseline_report}")
