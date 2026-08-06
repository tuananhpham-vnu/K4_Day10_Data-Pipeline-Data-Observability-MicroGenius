# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Phạm Tuấn Anh             |
| MSSV               | 2A202601070                     |
| Khóa/Lớp         | Khóa 4              |
| Tên nhóm         | MicroGenius     |
| Vai trò chính    | Vai trò 1 — Pipeline integrator (lead), Nhóm 4 người                 |
| Repository         | https://github.com/tuananhpham-vnu/K4_Day10_Data-Pipeline-Data-Observability-MicroGenius |
| Ngày hoàn thành | 2026-08-06               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Baseline pipeline orchestration | `src/pipelines/phase1.py::main` | Settings, raw/clean data, test set | `data/results/baseline_metrics.json`, `baseline_answers.json`, `data/quality/phase1_quality.json`, `freshness_report.json`, `data/reports/phase1_report.md` | Hoàn thành |
| Corruption/repair orchestration | `src/pipelines/corruption_flow.py::main` | Clean baseline df, baseline metrics, raw records | `data/clean/papers_clean_corrupted.*`, `papers_clean_repaired.*`, corrupted/repaired metrics & quality/freshness, `data/reports/corruption_report.md` | Hoàn thành |
| Settings/paths contract | `src/core/config.py` (chỉ đọc, không sửa) | `.env` | `Settings`, `Paths` dùng chung cho toàn pipeline | Hoàn thành (kế thừa, xác minh contract) |

Chỉ nhận ownership cho phần bạn trực tiếp thực hiện. Liên hệ rõ phần việc của bạn với đầu vào, đầu ra và các thành viên phụ thuộc vào phần đó.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Sửa lỗi import sai trong `src/observability/__init__.py` (đang import từ `evaluation` do copy-paste nhầm) | Vai trò 4 (eval/observe) | Package `observability` import được, không còn `ModuleNotFoundError: No module named 'observability.metrics'` |
| Thêm fallback category trong `src/ingestion/cleaning.py` khi Crossref không trả `subject` | Vai trò 2 (ingest/clean) | `categories_joined` không còn rỗng cho mọi bản ghi, `build_test_set` tạo được test set thay vì lỗi "0 complete papers" |
| Sửa lỗi double-client Chroma trong `src/retrieval/index.py::LocalEmbeddingIndex.build` | Vai trò 3 (rag) | Query ngay sau khi build index không còn văng `chromadb.errors.NotFoundError` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Viết pipeline baseline end-to-end | `src/pipelines/phase1.py` | `retrieval_hit_rate=1.0`, `mean_token_f1=1.0`, `judge_accuracy=1.0` trên 20 câu hỏi | `uv run python script/run_phase1.py` |
| Viết corruption → evaluate → repair → compare flow | `src/pipelines/corruption_flow.py` | Metrics giảm khi corrupt (`retrieval_hit_rate=0.8`), phục hồi hoàn toàn sau repair (`=1.0`) | `uv run python script/run_corruption_flow.py` |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

`data/reports/corruption_report.md` — báo cáo so sánh baseline/corrupted/repaired được sinh tự động từ `generate_corruption_report`, trỏ tới `data/results/baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json` và các quality/freshness report tương ứng, không có số liệu tự bịa.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần của tôi (lead) chịu trách nhiệm nối toàn bộ các module do các thành viên khác xây dựng (ingestion, cleaning, retrieval/RAG, evaluation, observability) thành hai luồng chạy được end-to-end: (1) baseline — từ raw Crossref data đến metrics và report; (2) corruption flow — corrupt dữ liệu có kiểm soát, đo tác động, repair từ raw, và tạo báo cáo so sánh ba trạng thái.

### Cách triển khai

`phase1.py::main()` thực hiện tuần tự: load `Settings` → fetch hoặc load raw records (cache theo `REFRESH_SOURCE`) → `build_clean_dataframe` → ghi CSV/JSON clean → `LocalEmbeddingIndex.build` (Chroma collection `papers-baseline`) → tạo hoặc load `test_set.json` (cache theo `REFRESH_TEST_SET`) → `evaluate_pipeline` → `run_data_quality_checks` + `build_freshness_report` → `generate_phase1_report`.

`corruption_flow.py::main()` đọc lại `papers_clean.json` + `baseline_metrics.json` đã có (bắt buộc phải chạy `phase1.py` trước, có kiểm tra rõ ràng và raise lỗi nếu thiếu) → `corrupt_clean_dataframe` (drop latest, blank summary, inject noise, truncate title, stale date, duplicate row) → build index riêng `papers-corrupted` → evaluate lại **trên cùng `test_set.json`** → quality/freshness cho bản corrupted → repair bằng cách **load lại raw records gốc và chạy lại `build_clean_dataframe` từ đầu** (không sửa tay dữ liệu đã corrupt) → build index `papers-repaired` → evaluate lại trên cùng test set → quality/freshness cho bản repaired → `generate_corruption_report` tổng hợp cả ba trạng thái.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | `Settings`/`Paths` từ `core.config`; `data/clean/papers_clean.json`; `data/raw/crossref_records.json`; `data/eval/test_set.json` |
| Output                         | `data/clean/papers_clean_corrupted.*`, `papers_clean_repaired.*`; `data/results/{corrupted,repaired}_metrics.json` và `_answers.json`; `data/quality/{corrupted,repaired}_quality.json`, `{corrupted,repaired}_freshness_report.json`; `data/results/corruption_log.json`; `data/reports/{phase1_report.md,corruption_report.md}` |
| Module phụ thuộc             | `ingestion.crossref`, `ingestion.cleaning`, `ingestion.corruption`, `retrieval.index`, `evaluation.metrics`, `evaluation.testset`, `observability.quality`, `observability.reporting` |
| Module sử dụng output        | Không có module downstream trong lab này — output là artifact cuối để nộp/demo |
| Điều kiện lỗi cần xử lý | Thiếu `papers_clean.json`/`baseline_metrics.json` (chưa chạy phase1) → raise `RuntimeError` rõ ràng thay vì lỗi mơ hồ |

### Cách xác minh

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** cả hai script chạy hết, exit code 0, artifacts trong `data/results`, `data/quality`, `data/reports`, `data/clean` được tạo/cập nhật.
- **Kết quả thực tế:** cả hai chạy thành công; `baseline_metrics.json` cho `retrieval_hit_rate=1.0`; `corrupted_metrics.json` giảm còn `0.8`; `repaired_metrics.json` phục hồi về `1.0`.
- **Artifact/log:** `data/results/baseline_metrics.json`, `data/results/corrupted_metrics.json`, `data/results/repaired_metrics.json`, `data/reports/corruption_report.md` (không chứa secret).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** `LocalEmbeddingIndex.build()` (trong `retrieval/index.py`) tạo một `chromadb.PersistentClient` để ghi collection, rồi gọi `cls(...)` — hàm này lại mở **một client Chroma thứ hai** trỏ cùng path để đọc lại ngay trong cùng tiến trình. Khi `evaluate_pipeline` gọi `index.search()` ngay sau `build()`, Chroma báo `NotFoundError: Collection ... does not exist`, dù dữ liệu đã ghi đúng xuống đĩa (xác minh bằng cách mở lại collection ở một tiến trình Python mới — dữ liệu tồn tại và đọc được bình thường).
- **Các phương án đã cân nhắc:**
  1. Thêm `time.sleep()`/retry trước khi query, hy vọng client thứ hai "bắt kịp".
  2. Sửa `build()` để tái sử dụng client/collection đã tạo thay vì mở client thứ hai.
- **Phương án đã chọn:** Phương án 2 — sửa `build()` dựng instance qua `cls.__new__` và gán trực tiếp `client`/`collection` đã có, không mở `PersistentClient` lần thứ hai.
- **Lý do:** `sleep`/retry là giải pháp che triệu chứng, không sửa nguyên nhân gốc (hai client cùng process tranh chấp cache/khóa trên cùng file SQLite của Chroma) và không đảm bảo đúng trong mọi lần chạy (flaky). Tái sử dụng client là fix đúng nguyên nhân, không thêm độ trễ, và loại bỏ hoàn toàn race condition.
- **Bằng chứng quyết định phù hợp:** Sau khi sửa, `uv run python script/run_phase1.py` và `run_corruption_flow.py` chạy hết cả ba lần build index (baseline, corrupted, repaired) không còn `NotFoundError`; `baseline_metrics.json` sinh ra với `retrieval_hit_rate=1.0` ngay lần chạy kế tiếp.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```
  chromadb.errors.NotFoundError: Error getting collection: Collection [c3788b83-026d-47cf-b692-52a008f0bb78] does not exist.
  ```
- **Lệnh hoặc bước tái hiện:** `uv run python script/run_phase1.py` (lỗi xảy ra ở bước `evaluate_pipeline` → `answer_question` → `index.search()`, ngay sau khi `LocalEmbeddingIndex.build()` vừa tạo collection `papers-baseline`).
- **Nguyên nhân gốc:** `LocalEmbeddingIndex.build()` mở hai `chromadb.PersistentClient` khác nhau trỏ cùng một `persist_path` trong cùng một tiến trình Python — một để ghi (`collection.add`), một (qua `cls(...)` gọi `__init__`) để đọc lại. Đã xác minh bằng cách mở một tiến trình Python mới chỉ để `client.list_collections()` — collection tồn tại và đọc được bình thường, chứng tỏ dữ liệu ghi đúng, vấn đề chỉ nằm ở việc dùng hai client cùng lúc trong một process.
- **Cách xử lý:** Sửa `build()` để không gọi `cls(...)` (mở client mới) nữa; thay vào đó dựng đối tượng `LocalEmbeddingIndex` qua `cls.__new__(cls)` và gán trực tiếp `client`, `collection` đã tạo ở phía trên cùng hàm.
- **Cách xác minh sau khi sửa:** Chạy lại `uv run python script/run_phase1.py` — không còn traceback, `data/results/baseline_metrics.json` được tạo với `retrieval_hit_rate=1.0`, `samples=20`.
- **Điều học được:** Với thư viện có state cục bộ (local persistent storage như SQLite/Chroma), tránh mở nhiều client/connection trỏ cùng resource trong cùng một tiến trình trừ khi thư viện đảm bảo an toàn cho việc đó; ưu tiên tái sử dụng handle đã có thay vì mở lại.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Crossref → vector index:** `fetch_source_records` gọi Crossref REST API (`/works`, có retry cho 429/503), lưu response thô vào `data/raw/crossref_response.json`, parse thành `PaperRecord` (DOI làm `paper_id` ổn định) lưu vào `crossref_records.json`. `build_clean_dataframe` chuẩn hóa whitespace, parse ngày xuất bản, loại bản ghi thiếu trường bắt buộc, dedupe theo `paper_id`, tính `age_days` và ghép `text_for_embedding`. `LocalEmbeddingIndex.build` encode `text_for_embedding` bằng MiniLM, lưu vào Chroma collection (`papers-baseline`/`-corrupted`/`-repaired`) kèm metadata đầy đủ để phục vụ retrieval và exact lookup.
2. **Test set & ground-truth doc IDs:** `build_test_set` chọn tối đa 5 paper đại diện (trải đều theo vị trí trong dataframe đã sort) và sinh 4 câu hỏi/paper (summary, authors, date, categories). Mỗi câu hỏi có `ground_truth_doc_ids = [paper_id]` lấy trực tiếp từ `paper_id` đã clean — không tự đặt ID. Khi evaluate, `retrieval_hit_rate` so khớp `ground_truth_doc_ids` với `retrieved_doc_ids` mà `index.search()` trả về, còn `token_f1`/judge so `answer` sinh ra với `ground_truth` bằng text.
3. **Quality checks vs freshness monitoring:** Quality checks (`run_data_quality_checks`) đánh giá **cấu trúc và tính toàn vẹn tại một thời điểm** — row count, null, `paper_id` unique, độ dài summary. Freshness monitoring (`build_freshness_report`) đánh giá **độ mới theo thời gian** — tuổi bản ghi (`age_days`) so với ngưỡng `freshness_threshold_days`, có bản ghi nào "stale" hoặc có ngày tương lai bất thường hay không. Hai loại kiểm tra bổ sung cho nhau: dữ liệu có thể "toàn vẹn" (đủ trường, không trùng) nhưng vẫn "cũ" (stale), hoặc ngược lại.
4. **Vì sao dùng cùng test set cho cả ba trạng thái:** Để đảm bảo so sánh công bằng (apples-to-apples) — nếu đổi câu hỏi hoặc ground truth giữa các lần evaluate, sự khác biệt về metric có thể đến từ việc thay đổi thước đo chứ không phải từ chất lượng dữ liệu. Giữ nguyên `test_set.json`, evaluator và `top_k` là điều kiện tiên quyết để kết luận "corruption làm giảm chất lượng" và "repair phục hồi chất lượng" có ý nghĩa nhân quả.
5. **Repair được coi là thành công dựa trên:** (a) `repaired_quality.json` có `is_valid=true`/`failed_checks=[]` (so với `corrupted_quality.json` có `paper_id_unique` và `summary_length` FAIL); (b) `repaired_freshness_report.json` có `is_fresh=true`, `stale_rows=0`; (c) `repaired_metrics.json` có `retrieval_hit_rate/mean_token_f1/judge_accuracy` quay lại đúng bằng `baseline_metrics.json` (1.0 ở cả ba lần chạy của tôi) — tức là repair không chỉ "chạy xong" mà thực sự khôi phục cả tín hiệu chất lượng dữ liệu lẫn hiệu năng RAG.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |     1.00 |      0.80 |     1.00 | Giảm 20 điểm phần trăm khi corrupt (do drop 2 bản ghi mới nhất + duplicate làm nhiễu index), phục hồi hoàn toàn sau repair. |
| `mean_token_f1`      |     1.00 |     0.807 |     1.00 | Giảm tương ứng khi câu trả lời agent bị ảnh hưởng bởi summary rỗng/noise/title bị cắt. |
| `judge_accuracy`     |     1.00 |      0.80 |     1.00 | LLM-judge đồng thuận với retrieval_hit_rate: 4/20 câu bị đánh giá sai sau corruption. |
| `mean_judge_score`   |     5.00 |      4.20 |     5.00 | Điểm trung bình giảm từ 5.0 xuống 4.2/5, khớp với tỉ lệ 20% câu bị ảnh hưởng. |
| Quality checks (`is_valid`) | PASS (không log riêng ở CP3, coi baseline sạch) | FAIL — `paper_id_unique` (2 dòng trùng do `duplicate_row`) và `summary_length` (5 dòng bị `blank_summary`) | PASS — 6/6 check đều PASS | Corruption tạo đúng 2 loại lỗi có thể phát hiện bằng quality gate; repair xóa sạch cả hai. |
| Freshness status       | `is_fresh=true` | `is_fresh=true` (corruption `stale_date` chỉ +400 ngày, chưa vượt ngưỡng `maximum_age_days=3650`) | `is_fresh=true` | Với ngưỡng mặc định 3650 ngày, `stale_date` corruption không đủ mạnh để lật cờ freshness — đây là giới hạn của bộ tham số corruption hiện tại, không phải lỗi pipeline. |

### Kết luận từ số liệu

Hoàn thành hai chuỗi nguyên nhân–bằng chứng sau:

1. **Corruption → quality/freshness signal → agent metric:** `corrupt_clean_dataframe` xóa 2 bản ghi mới nhất, làm rỗng summary của 3 bản ghi, chèn noise vào 3 bản ghi khác, cắt ngắn title của 2 bản ghi, làm cũ ngày xuất bản của 2 bản ghi, và nhân đôi 2 bản ghi (log chi tiết trong `data/results/corruption_log.json`) → `corrupted_quality.json` báo FAIL ở `paper_id_unique` (2 dòng trùng) và `summary_length` (5 dòng < 80 ký tự, gồm cả rỗng) → `corrupted_metrics.json` cho `retrieval_hit_rate` giảm từ 1.0 xuống 0.8 vì các câu hỏi nhắm vào paper có summary bị xóa/title bị cắt không còn khớp semantic search hoặc exact lookup theo title gốc.
2. **Repair action → quality/freshness signal phục hồi → agent metric phục hồi:** `corruption_flow.py` repair bằng cách load lại `crossref_records.json` (raw gốc, không bị corrupt) và chạy lại `build_clean_dataframe` từ đầu → `repaired_quality.json` PASS toàn bộ 6/6 check, không còn duplicate hay summary ngắn → `repaired_metrics.json` quay lại đúng `1.0` ở cả 4 chỉ số, khớp hoàn toàn với baseline.

**Corruption nào ảnh hưởng rõ nhất và vì sao?** `blank_summary` (làm rỗng summary của 3/24 bản ghi) và `duplicate_row` (2 bản ghi bị nhân đôi, khiến `paper_id_unique` FAIL) có ảnh hưởng rõ nhất tới `summary_length` và `paper_id_unique` — hai check duy nhất FAIL trong `corrupted_quality.json`. Về phía RAG metric, `blank_summary` + `truncate_title` là nguyên nhân trực tiếp khiến agent không lấy đúng answer cho các câu hỏi "What is the paper ... about?" và các câu dùng exact-title lookup, vì `text_for_embedding` rỗng/tiêu đề không khớp câu hỏi gốc.

**Kết quả nào khác với kỳ vọng ban đầu?** Freshness (`is_fresh`) **không đổi** giữa corrupted và repaired (cả hai đều `true`) — ban đầu tôi kỳ vọng `stale_date` corruption (+400 ngày) sẽ làm freshness FAIL. Đã kiểm tra `corrupted_freshness_report.json`: `maximum_age_days=3650` (10 năm) trong khi corruption chỉ cộng thêm 400 ngày cho 2 bản ghi — không đủ vượt ngưỡng. Giả thuyết đã kiểm chứng bằng cách đọc trực tiếp `stale_rows: 0` trong report, chứ không suy đoán. Đây là giới hạn của bộ tham số `STALE_DATE_EXTRA_DAYS=400` so với ngưỡng mặc định, không phải lỗi logic.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** Một pipeline "chạy hết, exit code 0" chưa chắc đúng — cần đối chiếu artifact thật (đã gặp trường hợp `papers_clean.json` chứa dữ liệu bất thường không do code sinh ra, phải xóa và regenerate toàn bộ artifact để đảm bảo sạch trước khi tin vào kết quả).
2. **Về data quality/observability:** Quality checks và freshness checks đo hai chiều độc lập (toàn vẹn cấu trúc vs. độ mới theo thời gian) — một dataset có thể pass check này nhưng fail check kia, nên cần cả hai để có bức tranh đầy đủ, và ngưỡng (threshold) phải được chọn phù hợp với loại corruption muốn phát hiện.
3. **Về ảnh hưởng của data đến RAG agent:** Corruption ở tầng text (summary rỗng, title bị cắt) ảnh hưởng trực tiếp và đo được lên `retrieval_hit_rate`/`judge_accuracy`, vì các trường này quyết định nội dung `text_for_embedding` dùng để search — chứng minh bằng số liệu rằng chất lượng dữ liệu đầu vào quyết định chất lượng RAG, không chỉ là lý thuyết.

### Nếu có thêm thời gian

Tôi sẽ giảm `maximum_age_days` (hoặc thêm setting riêng cho corruption flow) để `stale_date` corruption thực sự lật cờ `is_fresh=false`, giúp demo đầy đủ cả 3 loại signal (RAG metrics, quality, freshness) đều bị ảnh hưởng bởi corruption thay vì chỉ 2/3 như hiện tại — đo cải thiện bằng cách so `corrupted_freshness_report.json["is_fresh"]` trước/sau khi chỉnh ngưỡng.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phạm Tuấn Anh
**Ngày xác nhận:** 2026-08-06
