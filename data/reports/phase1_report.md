# Phase 1 — Baseline Evaluation Report

- **Generated at:** 2026-08-06T09:45:17.787551Z
- **Overall data status:** **PASS**
- **Data quality:** PASS
- **Freshness:** PASS

## 1. Source summary

| Field | Value |
| --- | --- |
| source_api | Crossref REST API |
| source_query | agentic retrieval augmented generation large language model |
| source_filter | from-pub-date:2026-02-07,has-abstract:true |
| raw_record_count | 24 |
| clean_row_count | 24 |
| test_set_size | 20 |
| collection_name | papers-baseline |
| embedding_model | sentence-transformers/all-MiniLM-L6-v2 |
| generated_at | 2026-08-06T09:44:51.085987+00:00 |

## 2. Retrieval and answer quality

| Metric | Value |
| --- | --- |
| samples | 20 |
| retrieval_hit_rate | 100.00% |
| mean_token_f1 | 100.00% |
| judge_accuracy | 100.00% |
| mean_judge_score | 5 |

## 3. Data-quality checks

| Check | Status | Details |
| --- | --- | --- |
| row_count | PASS | value=24, minimum=1, failed_rows=0 |
| paper_id_not_null | PASS | null_rows=0, failed_rows=0 |
| paper_id_unique | PASS | duplicate_rows=0, failed_rows=0 |
| title_not_null | PASS | null_rows=0, failed_rows=0 |
| summary_length | PASS | null_rows=0, short_rows=0, failed_rows=0 |
| freshness | PASS | stale_rows=0, future_rows=0, invalid_age_rows=0, failed_rows=0 |

### Quality overview

| Signal | Value |
| --- | --- |
| row_count | 24 |
| total_null_count | 16 |
| duplicate_count | 0 |
| failed_checks | — |

## 4. Freshness

| Signal | Value |
| --- | --- |
| total_rows | 24 |
| latest_published | 2026-08-01T00:00:00Z |
| oldest_published | 2026-02-12T00:00:00Z |
| stale_rows | 0 |
| invalid_date_rows | 0 |
| source_timestamp | N/A |
| is_fresh | PASS |

## 5. Interpretation

The baseline dataset passed the configured quality and freshness gates. The RAG metrics above can be used as the reference point for the corruption experiment.

## Appendix — Machine-readable inputs

### Metrics

```json
{
  "samples": 20,
  "retrieval_hit_rate": 1.0,
  "mean_token_f1": 1.0,
  "judge_accuracy": 1.0,
  "mean_judge_score": 5.0,
  "ragas": {
    "skipped": "Set RUN_RAGAS=1 to enable the slower Ragas pass."
  }
}
```

### Quality

```json
{
  "report_name": "phase1_quality",
  "generated_at": "2026-08-06T09:45:17.785864Z",
  "as_of": "2026-08-06T09:45:17.783680Z",
  "source_timestamp": null,
  "row_count": 24,
  "column_count": 13,
  "columns": [
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "primary_category",
    "published",
    "updated",
    "age_days",
    "summary_chars",
    "text_for_embedding",
    "abs_url",
    "pdf_url"
  ],
  "null_counts": {
    "paper_id": 0,
    "title": 0,
    "summary": 0,
    "authors_joined": 0,
    "categories_joined": 0,
    "primary_category": 0,
    "published": 0,
    "updated": 0,
    "age_days": 0,
    "summary_chars": 0,
    "text_for_embedding": 0,
    "abs_url": 0,
    "pdf_url": 16
  },
  "total_null_count": 16,
  "duplicate_count": 0,
  "stale_rows": 0,
  "thresholds": {
    "minimum_rows": 1,
    "minimum_summary_characters": 80,
    "maximum_age_days": 3650
  },
  "checks": {
    "row_count": {
      "passed": true,
      "value": 24,
      "minimum": 1,
      "failed_rows": 0
    },
    "paper_id_not_null": {
      "passed": true,
      "column": "paper_id",
      "null_rows": 0,
      "failed_rows": 0
    },
    "paper_id_unique": {
      "passed": true,
      "column": "paper_id",
      "duplicate_rows": 0,
      "duplicate_values": 0,
      "failed_rows": 0
    },
    "title_not_null": {
      "passed": true,
      "column": "title",
      "null_rows": 0,
      "failed_rows": 0
    },
    "summary_length": {
      "passed": true,
      "column": "summary",
      "minimum_characters": 80,
      "null_rows": 0,
      "short_rows": 0,
      "length_stats": {
        "min": 834,
        "median": 1661.0,
        "mean": 1728.0,
        "max": 2610
      },
      "failed_rows": 0
    },
    "freshness": {
      "passed": true,
      "published_column": "published",
      "age_days_column": "age_days",
      "maximum_age_days": 3650,
      "invalid_age_rows": 0,
      "stale_rows": 0,
      "future_rows": 0,
      "failed_rows": 0
    }
  },
  "passed_checks": 6,
  "failed_checks": [],
  "is_valid": true,
  "passed": true,
  "report_path": "data/quality/phase1_quality.json"
}
```

### Freshness

```json
{
  "generated_at": "2026-08-06T09:45:17.787128Z",
  "as_of": "2026-08-06T09:45:17.786300Z",
  "source_timestamp": null,
  "published_column": "published",
  "age_days_column": "age_days",
  "latest_published": "2026-08-01T00:00:00Z",
  "oldest_published": "2026-02-12T00:00:00Z",
  "maximum_age_days": 3650,
  "stale_rows": 0,
  "fresh_rows": 24,
  "future_rows": 0,
  "invalid_date_rows": 0,
  "valid_published_rows": 24,
  "total_rows": 24,
  "stale_ratio": 0.0,
  "is_fresh": true
}
```
