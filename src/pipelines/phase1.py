from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Xay dung baseline pipeline end-to-end tren du lieu sach."""
    settings = load_settings()

    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        records = fetch_source_records(settings)
    else:
        records = load_raw_records(settings.paths.raw_records_json)

    df = build_clean_dataframe(records, now_utc())
    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(df, settings)

    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        test_set = build_test_set(df, settings.paths.eval_testset)
    else:
        test_set = read_json(settings.paths.eval_testset)

    bundle = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )

    quality = run_data_quality_checks(df, settings, "baseline_quality")
    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)

    source_summary = {
        "source_api": settings.source_api,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "raw_count": len(records),
        "clean_count": len(df),
    }
    generate_phase1_report(settings.paths.baseline_report, source_summary, bundle.summary, quality, freshness)

    try:
        agent = build_agent(settings, index)
        demo_questions = test_set[:2]
        demo_answers = [
            {"question": item["question"], "answer": run_agent_question(agent, item["question"])}
            for item in demo_questions
        ]
        write_json(settings.paths.demo_answers, demo_answers)
    except Exception as exc:  # pragma: no cover
        print(f"[phase1] Skipping agent demo: {exc}")

    print(
        f"[phase1] samples={bundle.summary['samples']} "
        f"retrieval_hit_rate={bundle.summary['retrieval_hit_rate']:.3f} "
        f"quality_overall_passed={quality['overall_passed']} "
        f"is_fresh={freshness['is_fresh']}"
    )
