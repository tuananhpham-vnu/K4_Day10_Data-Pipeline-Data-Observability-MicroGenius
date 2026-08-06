# Corruption and Recovery Evaluation Report

- **Generated at:** 2026-08-06T09:58:25.596021Z
- **Metrics degraded after corruption:** 4/4
- **Metrics improved after repair:** 4/4
- **Metrics restored to baseline or better:** 4/4
- **Corrupted data quality:** FAIL
- **Repaired data quality:** PASS

## 1. RAG quality comparison

| Metric | Baseline | Corrupted | Repaired | Corruption Δ | Repair Δ | Recovery |
| --- | --- | --- | --- | --- | --- | --- |
| retrieval_hit_rate | 100.00% | 80.00% | 100.00% | -20.00 pp | +20.00 pp | 100.0% |
| mean_token_f1 | 100.00% | 80.70% | 100.00% | -19.30 pp | +19.30 pp | 100.0% |
| judge_accuracy | 100.00% | 80.00% | 100.00% | -20.00 pp | +20.00 pp | 100.0% |
| mean_judge_score | 5 | 4.2000 | 5 | -0.8000 | +0.8000 | 100.0% |

> Corruption Δ = corrupted − baseline. Repair Δ = repaired − corrupted. For the listed RAG metrics, higher values are better.

## 2. Data-quality recovery

| Check | Corrupted | Failed rows | Repaired | Failed rows |
| --- | --- | --- | --- | --- |
| freshness | PASS | 0 | PASS | 0 |
| paper_id_not_null | PASS | 0 | PASS | 0 |
| paper_id_unique | FAIL | 2 | PASS | 0 |
| row_count | PASS | 0 | PASS | 0 |
| summary_length | FAIL | 5 | PASS | 0 |
| title_not_null | PASS | 0 | PASS | 0 |

### Aggregate quality signals

| Signal | Corrupted | Repaired |
| --- | --- | --- |
| row_count | 24 | 24 |
| total_null_count | 22 | 16 |
| duplicate_count | 2 | 0 |
| failed_checks | paper_id_unique, summary_length | — |

## 3. Freshness recovery

| Signal | Corrupted | Repaired |
| --- | --- | --- |
| stale_rows | 0 | 0 |
| invalid_date_rows | 0 | 0 |
| latest_published | 2026-07-13T00:00:00Z | 2026-08-01T00:00:00Z |
| oldest_published | 2025-04-03T00:00:00Z | 2026-02-12T00:00:00Z |
| is_fresh | PASS | PASS |

## 4. Findings

- Corruption reduced: `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`.
- Repair improved: `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`.
- Reached baseline or better: `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`.
- The repair moved the dataset from failing to passing the configured quality gates.

## 5. Conclusion

The observed direction is consistent with the hypothesis that degraded source data harms retrieval and answer quality, while repair recovers at least part of the lost performance. This is evidence for this experiment, not a claim of universal causality.

## Appendix — Machine-readable inputs

### Baseline metrics

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

### Corrupted metrics

```json
{
  "samples": 20,
  "retrieval_hit_rate": 0.8,
  "mean_token_f1": 0.8069767441860465,
  "judge_accuracy": 0.8,
  "mean_judge_score": 4.2,
  "ragas": {
    "skipped": "Set RUN_RAGAS=1 to enable the slower Ragas pass."
  }
}
```

### Repaired metrics

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

### Corrupted quality and freshness

```json
{
  "quality": {
    "report_name": "corrupted_quality",
    "generated_at": "2026-08-06T09:56:21.549281Z",
    "as_of": "2026-08-06T09:56:21.480860Z",
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
      "summary": 5,
      "authors_joined": 0,
      "categories_joined": 0,
      "primary_category": 0,
      "published": 0,
      "updated": 0,
      "age_days": 0,
      "summary_chars": 0,
      "text_for_embedding": 0,
      "abs_url": 0,
      "pdf_url": 17
    },
    "total_null_count": 22,
    "duplicate_count": 2,
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
        "passed": false,
        "column": "paper_id",
        "duplicate_rows": 2,
        "duplicate_values": 2,
        "failed_rows": 2
      },
      "title_not_null": {
        "passed": true,
        "column": "title",
        "null_rows": 0,
        "failed_rows": 0
      },
      "summary_length": {
        "passed": false,
        "column": "summary",
        "minimum_characters": 80,
        "null_rows": 5,
        "short_rows": 5,
        "length_stats": {
          "min": 0,
          "median": 1573.0,
          "mean": 1398.4583333333333,
          "max": 2610
        },
        "failed_rows": 5
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
    "passed_checks": 4,
    "failed_checks": [
      "paper_id_unique",
      "summary_length"
    ],
    "is_valid": false,
    "passed": false,
    "report_path": "data\\quality\\corrupted_quality.json"
  },
  "freshness": {
    "generated_at": "2026-08-06T09:56:21.556281Z",
    "as_of": "2026-08-06T09:56:21.554282Z",
    "source_timestamp": null,
    "published_column": "published",
    "age_days_column": "age_days",
    "latest_published": "2026-07-13T00:00:00Z",
    "oldest_published": "2025-04-03T00:00:00Z",
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
}
```

### Repaired quality and freshness

```json
{
  "quality": {
    "report_name": "repaired_quality",
    "generated_at": "2026-08-06T09:58:25.589008Z",
    "as_of": "2026-08-06T09:58:25.588008Z",
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
    "report_path": "data\\quality\\repaired_quality.json"
  },
  "freshness": {
    "generated_at": "2026-08-06T09:58:25.592024Z",
    "as_of": "2026-08-06T09:58:25.590013Z",
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
}
```
