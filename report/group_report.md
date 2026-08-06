# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | Khóa 4              |
| Tên nhóm         | MicroGenius     |
| Repository         | https://github.com/tuananhpham-vnu/K4_Day10_Data-Pipeline-Data-Observability-MicroGenius |
| Ngày hoàn thành | 2026-08-06               |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Phạm Tuấn Anh | 2A202601070 | Vai trò 1 — Pipeline integrator (lead) | `src/core/config.py` (contract), `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` — orchestration baseline và corruption flow |
| 2 | Nguyễn Thị Thương | 2A202601226 | Vai trò 2 — Data foundation & recovery (ingest\|clean) | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, `src/ingestion/corruption.py`, — raw ingestion, clean schema, corruption scenarios, repair orchestration|
| 3 | Nguyễn Đức Anh | 2A202601788 | Vai trò 3 — RAG & agent owner | `src/retrieval/embeddings.py`, `src/retrieval/index.py`, `src/retrieval/agent.py`, `src/retrieval/qa.py`, `src/retrieval/llm.py` — MiniLM embedding, Chroma index, semantic search/lookup, agent, provider selection |
| 4 | Mai Tiến Dũng | 2A202601838 | Vai trò 4 — Evaluation & observability | `src/evaluation/testset.py`, `src/evaluation/metrics.py`, `src/observability/quality.py`, `src/observability/reporting.py` — test set, metrics, quality/freshness checks, report generation, testet function builder |

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành toàn bộ luồng end-to-end: fetch dữ liệu thật từ Crossref REST API, làm sạch thành dataframe chuẩn (24 bản ghi), build Chroma index với MiniLM embeddings, tạo evaluation set 20 câu hỏi (5 paper × 4 loại câu hỏi: summary/authors/date/categories), evaluate baseline, chạy quality/freshness checks và sinh `phase1_report.md`. Baseline đạt điểm tuyệt đối trên toàn bộ metric đo được (`retrieval_hit_rate = mean_token_f1 = judge_accuracy = 1.0`, `mean_judge_score = 5.0/5`).

Ở bước corruption, nhóm áp dụng 6 loại lỗi có kiểm soát trên bản sao của clean dataset (drop 2 bản ghi mới nhất, làm rỗng 3 summary, chèn noise vào 3 summary, cắt ngắn 2 title, làm cũ ngày xuất bản của 2 bản ghi, nhân đôi 2 bản ghi) và log đầy đủ trong `corruption_log.json`. Corruption làm giảm rõ rệt cả bộ metric RAG (`retrieval_hit_rate`/`judge_accuracy` giảm còn 0.8, `mean_token_f1` còn ~0.807) lẫn data-quality gate (`paper_id_unique` và `summary_length` FAIL). Repair bằng cách chạy lại toàn bộ cleaning từ raw Crossref records gốc (không sửa tay) đã phục hồi **hoàn toàn** cả quality checks (6/6 PASS) lẫn RAG metrics (quay về đúng baseline: 1.0 / 5.0).

Blocker quan trọng nhất đã xử lý: `LocalEmbeddingIndex.build()` mở hai `chromadb.PersistentClient` trỏ cùng path trong cùng tiến trình, gây `NotFoundError` ngay sau khi build index — đã sửa để tái sử dụng client/collection đã tạo. Giới hạn còn lại: ngưỡng `maximum_age_days=3650` quá cao so với corruption `stale_date` (+400 ngày), nên tín hiệu freshness không phản ánh được loại corruption này (`is_fresh=true` ở cả bản corrupted và repaired).

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API
    -> raw response/raw records          (data/raw/)
    -> cleaning và data modeling         (data/clean/)
    -> embedding + ChromaDB index        (data/embeddings/, data/chroma/, collection papers-baseline)
    -> evaluation baseline               (data/eval/test_set.json, data/results/baseline_*.json)
    -> quality/freshness reports         (data/quality/phase1_quality.json, freshness_report.json)
    -> corruption                        (data/clean/papers_clean_corrupted.*, collection papers-corrupted)
    -> re-index và re-evaluate           (data/results/corrupted_*.json, data/quality/corrupted_*.json)
    -> repair từ dữ liệu nguồn (raw)     (data/clean/papers_clean_repaired.*, collection papers-repaired)
    -> comparison report                 (data/reports/corruption_report.md)
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref `/works` API | Fetch với retry/backoff (429/503), parse `PaperRecord` với DOI làm `paper_id` ổn định | `data/raw/crossref_response.json`, `crossref_records.json` | Nguyễn Thị Thương |
| Cleaning          | Raw `PaperRecord` list | Normalize whitespace, parse `published`, dedupe theo `paper_id`, tính `age_days`, ghép `text_for_embedding` | `data/clean/papers_clean.{csv,json}` | Nguyễn Thị Thương |
| Embedding/index   | Clean dataframe | MiniLM (`all-MiniLM-L6-v2`) encode `text_for_embedding`, lưu vào Chroma collection | `data/embeddings/papers_embeddings.json`, collection `papers-baseline` | Nguyễn Đức Anh |
| Evaluation        | Clean dataframe + index | Sinh 20 câu hỏi (5 paper × 4 loại), evaluate qua `answer_question` + LLM-judge | `data/eval/test_set.json`, `data/results/baseline_answers.json`, `baseline_metrics.json` | Mai Tiến Dũng |
| Observability     | Clean/corrupted/repaired dataframe | Row/null/duplicate/summary-length checks, freshness so với `age_days` | `data/quality/*.json` | Mai Tiến Dũng |
| Corruption/repair | Baseline clean dataframe, raw records | 6 loại corruption có log; repair bằng rebuild từ raw | `data/results/corruption_log.json`, `data/clean/papers_clean_{corrupted,repaired}.*` | Nguyễn Thị Thương |
| Orchestration     | Toàn bộ module trên | Nối thành 2 flow chạy được: `phase1.py`, `corruption_flow.py` | `data/reports/phase1_report.md`, `corruption_report.md` | Phạm Tuấn Anh |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | theo `.env` cục bộ của máy chạy (không commit) |
| `LLM_MODEL`                | theo `.env` cục bộ của máy chạy (không commit) |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | `max_results = 24` |
| Retrieval `top_k`           | 4 |
| Freshness threshold          | 180 ngày (`freshness_threshold_days`, dùng để lọc `source_filter` khi fetch); quality/freshness report dùng ngưỡng mặc định `maximum_age_days = 3650` |
| Random seed, nếu có        | `RANDOM_SEED = 42` trong `src/ingestion/corruption.py` |

Không dán nội dung API key hoặc file `.env` vào báo cáo.

### Lệnh cài đặt

```bash
uv sync
```

### Lệnh chạy

Baseline:

```bash
uv run python script/run_phase1.py
```

Corruption flow:

```bash
uv run python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công | 2026-08-06 | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow   | Thành công | 2026-08-06 | `data/results/corrupted_metrics.json`, `repaired_metrics.json`, `data/reports/corruption_report.md` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API (`https://api.crossref.org/works`) |
| Query/filter                | `query="agentic retrieval augmented generation large language model"`, `filter="from-pub-date:<180 ngày trước>,has-abstract:true"` |
| Thời điểm lấy dữ liệu | 2026-08-06 |
| Số record nhận được    | 24 (sau khi loại record thiếu DOI/title/abstract) |
| Cơ chế retry/backoff      | Retry tối đa 5 lần, exponential backoff (`2**attempt` giây) cho status 429/503 |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id` (DOI) | str | Có | Định danh ổn định xuyên suốt pipeline | Record thiếu DOI bị loại ngay khi parse |
| `published` | str (`YYYY-MM-DD`) | Có | Ngày xuất bản, dùng tính `age_days` | Record parse ngày thất bại bị loại ở bước cleaning |
| `categories` (`subject`) | list[str] | Không (Crossref thường không trả) | Phân loại chủ đề | Fallback sang `primary_category` (`"unknown"`) khi rỗng, để `categories_joined` không rỗng |
| `text_for_embedding` | str | Có (sinh ra, không từ raw) | Nội dung dùng để encode embedding | Ghép từ `title` + `summary` đã normalize |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Loại record thiếu DOI/title/summary/published hợp lệ | Completeness | 0 trong lần chạy này (24/24 raw records đều hợp lệ) | `data/clean/papers_clean.json` có 24 dòng, khớp `data/raw/crossref_records.json` |
| Dedupe theo `paper_id` (giữ bản mới nhất theo `published`) | Uniqueness | 0 (không có DOI trùng trong raw data) | `paper_id_unique` PASS trong `phase1_quality.json` |
| Fallback `categories` rỗng → `[primary_category]` | Completeness | 24/24 (Crossref không trả `subject` cho hầu hết record hiện nay) | So sánh `categories_joined` trước/sau fix trong `cleaning.py` |

Giải thích cách nhóm tạo `text_for_embedding`, document ID và `age_days`:

`paper_id` = DOI gốc từ Crossref (ổn định, không tự sinh). `text_for_embedding` = `normalize_whitespace(f"{title}. {summary}")`. `age_days` = số ngày giữa thời điểm chạy pipeline và `published`, dùng cho cả `text_for_embedding`-independent freshness checks và làm mục tiêu của corruption `stale_date`.

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 20 (5 paper đại diện × 4 câu hỏi/paper) |
| Các `question_type`                    | `summary`, `authors`, `date`, `categories` |
| Ground-truth document ID                 | `ground_truth_doc_ids = [paper_id]` lấy trực tiếp từ `paper_id` đã clean, không tự đặt ID |
| Embedding model                          | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collection                  | ChromaDB persistent tại `data/chroma/`; collection `papers-baseline` / `papers-corrupted` / `papers-repaired` |
| Retrieval `top_k`                       | 4 |
| LLM provider/model                       | Theo `.env` (`LLM_PROVIDER`/`LLM_MODEL`), dùng cho câu trả lời agent và LLM-judge |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` — sinh một lần từ baseline clean dataframe, được cache lại và tái sử dụng nguyên vẹn cho cả evaluate corrupted và repaired |

Giải thích vì sao test set được giữ nguyên khi đánh giá baseline, corrupted và repaired:

Nếu đổi câu hỏi hoặc ground truth giữa các lần evaluate, chênh lệch metric có thể đến từ việc thay đổi thước đo chứ không phải từ chất lượng dữ liệu. `corruption_flow.py` luôn trỏ `test_set_path=paths.eval_testset` (không tạo test set mới) cho cả ba lần `evaluate_pipeline`, đảm bảo so sánh baseline/corrupted/repaired là apples-to-apples.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/`                          | Có | `crossref_response.json` (payload thô), `crossref_records.json` (24 `PaperRecord`) |
| Cleaned dataset          | `data/clean/`                        | Có | `papers_clean.csv`/`.json`, 24 dòng |
| Embedding manifest/index | `data/embeddings/`                   | Có | `papers_embeddings.json`, collection `papers-baseline` trong `data/chroma/` |
| Evaluation set           | `data/eval/`                         | Có | `test_set.json`, 20 câu hỏi |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | Xem bảng dưới |
| Quality/freshness        | `data/quality/`                      | Có | `phase1_quality.json`, `freshness_report.json` |
| Baseline report          | `data/reports/phase1_report.md`      | Có | Sinh tự động từ `generate_phase1_report` |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` |    1.00 | Cả 20/20 câu hỏi retrieval đúng `paper_id` mong đợi trong top-4 |
| `mean_token_f1`      |    1.00 | Câu trả lời khớp gần như tuyệt đối với ground truth (dữ liệu sạch, câu hỏi sinh trực tiếp từ nội dung) |
| `judge_accuracy`     |    1.00 | LLM-judge đánh giá đúng toàn bộ 20 câu |
| `mean_judge_score`   |    5.00 | Điểm trung bình tối đa (thang 1–5) |
| Ragas                 | N/A (skipped) | Chưa set `RUN_RAGAS=1`, ragas evaluation bị bỏ qua có chủ đích để giảm thời gian chạy |

## 8. Data quality và freshness

### Quality checks (baseline)

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| `row_count` | Completeness | ≥ 1 | PASS — 24 dòng | `phase1_quality.json` |
| `paper_id_unique` | Uniqueness | 0 trùng | PASS — 0 duplicate | `phase1_quality.json` |
| `summary_length` | Validity | ≥ 80 ký tự | PASS — không có summary rỗng/ngắn | `phase1_quality.json` |
| `freshness` (trong quality checks) | Timeliness | `age_days` hợp lệ, không stale/future | PASS | `phase1_quality.json` |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | `data/clean/papers_clean.json` (baseline) |
| Timestamp mới nhất       | theo `latest_published` trong `data/quality/freshness_report.json` |
| Ngưỡng freshness         | `maximum_age_days = 3650` (mặc định trong `observability/quality.py`) |
| Trạng thái baseline      | Fresh (`is_fresh = true`, `stale_rows = 0`) |
| Lý do                     | Toàn bộ 24 bản ghi có `published` hợp lệ và `age_days` trong ngưỡng 10 năm |

## 9. Corruption scenarios và repair

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| `drop_latest` | Xóa 2 bản ghi có `published` mới nhất | 2 | Giảm `row_count` | Corpus còn 22 (trước khi duplicate bù lại thành 24) | Rebuild từ raw — 2 bản ghi này có mặt lại |
| `blank_summary` | Set `summary = ""` | 3 | `summary_length` FAIL | `summary_length`: 5 dòng short/null (bao gồm cả 2 dòng duplicate của bản blank) trong `corrupted_quality.json` | Rebuild từ raw — summary gốc được khôi phục |
| `inject_noise` | Nối `"[CORRUPTED-NOISE lorem ipsum dolor sit amet]"` vào summary | 3 | Không tự động fail quality check nào (không đo semantic noise), nhưng ảnh hưởng embedding | `retrieval_hit_rate`/`judge_accuracy` giảm theo tổng thể | Rebuild từ raw — noise biến mất |
| `truncate_title` | Cắt còn 15 ký tự đầu | 2 | Ảnh hưởng exact-title lookup trong `qa.py` | Các câu hỏi dùng `'title gốc'` không match được title đã cắt | Rebuild từ raw — title đầy đủ được khôi phục |
| `stale_date` | `published -= 400 ngày`, `age_days += 400` | 2 | Kỳ vọng ảnh hưởng freshness | Không FAIL vì `maximum_age_days=3650` >> 400 ngày (giới hạn tham số, xem mục 12) | Rebuild từ raw — ngày gốc được khôi phục |
| `duplicate_row` | Nhân đôi 2 bản ghi (trùng với 2 bản ghi vừa bị `blank_summary`) | 2 | `paper_id_unique` FAIL | FAIL — `duplicate_rows: 2` trong `corrupted_quality.json` | Rebuild từ raw — không có bản ghi trùng |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log đủ cả 6 loại corruption, ghi rõ `paper_id`, `corruption_type`, `parameter`, `before`/`after` cho từng thay đổi — đủ để truy vết record nào bị tác động bởi loại lỗi nào.

Giải thích cách repair đảm bảo dữ liệu được phục hồi từ nguồn đáng tin cậy thay vì chỉ che kết quả lỗi:

`corruption_flow.py` **không** sửa tay `papers_clean_corrupted.*` để tạo bản repaired. Thay vào đó, nó gọi lại `load_raw_records(paths.raw_records_json)` (đọc snapshot raw Crossref gốc, chưa từng bị corrupt) rồi chạy lại `build_clean_dataframe` từ đầu — đúng quy trình cleaning giống hệt lúc tạo baseline. Vì vậy repaired dataset không phải là "corrupted đã vá tay" mà là một lần cleaning độc lập, hoàn toàn từ nguồn tin cậy.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   |     1.00 |      0.80 |     1.00 |                    −0.20 |           100% | Phục hồi hoàn toàn |
| `mean_token_f1`        |     1.00 |     0.807 |     1.00 |                   −0.193 |           100% | Phục hồi hoàn toàn |
| `judge_accuracy`       |     1.00 |      0.80 |     1.00 |                    −0.20 |           100% | Phục hồi hoàn toàn |
| `mean_judge_score`     |     5.00 |      4.20 |     5.00 |                    −0.80 |           100% | Phục hồi hoàn toàn |
| Quality checks pass/fail | 6/6 PASS | 4/6 PASS (FAIL: `paper_id_unique`, `summary_length`) | 6/6 PASS | 2 check chuyển FAIL | 100% | Phục hồi hoàn toàn |
| Freshness status         | `is_fresh=true` | `is_fresh=true` | `is_fresh=true` | Không đổi | N/A | `stale_date` (+400 ngày) không đủ vượt ngưỡng `maximum_age_days=3650` — xem mục 12 |

Nêu ít nhất hai kết luận có quan hệ nhân quả được hỗ trợ bởi artifacts:

1. **Corruption → quality/freshness signal → retrieval/answer metric:** `blank_summary` (3 record) + `duplicate_row` (2 record) làm `corrupted_quality.json` FAIL ở `summary_length` và `paper_id_unique` → `text_for_embedding` của các record này bị rỗng hoặc trùng lặp trong index `papers-corrupted` → `corrupted_metrics.json` cho `retrieval_hit_rate` giảm từ 1.0 xuống 0.8 vì agent không còn tìm đúng tài liệu cho các câu hỏi nhắm vào những paper này.
2. **Repair action → quality/freshness recovery → agent metric recovery:** Repair rebuild toàn bộ clean dataset từ raw Crossref records gốc (không sửa tay) → `repaired_quality.json` PASS 6/6 check, không còn duplicate hay summary ngắn → `repaired_metrics.json` quay lại đúng 1.0/5.0 ở cả 4 chỉ số, khớp hoàn toàn với baseline — chứng minh repair phục hồi cả tín hiệu chất lượng dữ liệu lẫn hiệu năng RAG, không chỉ "chạy xong không lỗi".

Freshness là ngoại lệ: dù `stale_date` nằm trong danh sách corruption, nó không tạo ra thay đổi tín hiệu đo được (`is_fresh` giữ nguyên `true` ở cả ba trạng thái) vì tham số `STALE_DATE_EXTRA_DAYS=400` nhỏ hơn nhiều so với ngưỡng `maximum_age_days=3650` — nhóm không kết luận "corruption làm giảm freshness" vì số liệu không cho thấy điều đó.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** `chromadb.errors.NotFoundError: Error getting collection: Collection [...] does not exist.` xảy ra ngay trong lần chạy `phase1.py` đầu tiên, ở bước `evaluate_pipeline` gọi `index.search()` ngay sau khi `LocalEmbeddingIndex.build()` vừa tạo xong collection.
- **Nguyên nhân:** `LocalEmbeddingIndex.build()` (trong `retrieval/index.py`) mở một `chromadb.PersistentClient` để ghi collection, rồi gọi `cls(...)` — hàm này mở **một client Chroma thứ hai** trỏ cùng path để đọc lại trong cùng tiến trình. Hai client cùng process tranh chấp cache/khóa trên cùng file lưu trữ của Chroma. Đã xác minh: mở một tiến trình Python mới để `list_collections()` cho thấy dữ liệu ghi đúng, chỉ lỗi khi dùng hai client trong cùng process.
- **Cách xử lý:** Sửa `build()` để dựng `LocalEmbeddingIndex` qua `cls.__new__(cls)` và gán trực tiếp `client`/`collection` đã tạo, không mở `PersistentClient` lần thứ hai.
- **Cách xác minh:** `uv run python script/run_phase1.py` và `uv run python script/run_corruption_flow.py` chạy hết cả ba lần build index (baseline, corrupted, repaired) không còn `NotFoundError`.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| `stale_date` corruption (+400 ngày) nhỏ hơn nhiều so với `maximum_age_days=3650` mặc định | Tín hiệu freshness không phản ánh loại corruption này (`is_fresh` không đổi ở cả 3 trạng thái) | Giảm `maximum_age_days` (hoặc thêm setting riêng cho lab) rồi so `corrupted_freshness_report.json["is_fresh"]`/`stale_rows` trước và sau khi chỉnh |
| Crossref thường không trả `subject`, phải fallback `categories` sang `primary_category="unknown"` | Test set có category ground truth kém đa dạng (nhiều câu hỏi trả lời "unknown") | Thử nguồn phân loại chủ đề khác (ví dụ suy luận category từ `container-title`/từ khóa trong abstract) để câu hỏi `categories` có ý nghĩa hơn |
| Ragas chưa được bật (`RUN_RAGAS=1`) | Thiếu bộ metric ngữ nghĩa sâu hơn (`faithfulness`, `context_precision`, ...) để đối chiếu với token-F1/judge | Bật `RUN_RAGAS=1` cho một lần chạy đầy đủ và bổ sung kết quả vào báo cáo |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [ ] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng (mới có báo cáo của Phạm Tuấn Anh — `report/individual_report.md`; 3 thành viên còn lại cần tự hoàn thành `<MSSV>_HoTen.md` theo `report/README.md`).
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.

## 14. Quản lý dự án, kế hoạch & merge workflow

### Kế hoạch theo checkpoint (4 giờ, 7 mốc)

Nhóm dùng công cụ checkpoint timer (`phan-cong-day-10-data-pipeline-4h(2).html`, cấu hình Nhóm 4) để chia phiên làm việc 4 giờ thành 7 mốc, mỗi mốc có tiêu chí hoàn thành (pass criteria) riêng trước khi chuyển tiếp:

| Checkpoint | Khung giờ | Mục tiêu | Tiêu chí hoàn thành |
| --- | --- | --- | --- |
| CP0 | 00:00–00:30 | Khởi động, chốt contract, ingestion raw | Raw response/records tồn tại, `paper_id` ổn định |
| CP1 | 00:30–01:05 | Cleaning, data model & quality gates | Clean CSV/JSON đọc được, `paper_id` unique |
| CP2 | 01:05–01:35 | Test set, RAG index & agent smoke test | `test_set.json`, embedding manifest, collection baseline tồn tại |
| CP3 | 01:35–02:00 | Baseline end-to-end & báo cáo | `baseline_metrics.json`, `phase1_report.md` khớp artifact thật |
| CP4 | 02:00–02:15 | Nghỉ | — |
| CP5 | 02:15–03:15 | Corruption có kiểm soát & đo impact | Corruption log, corrupted metrics/quality tồn tại, baseline không bị ghi đè |
| CP6 | 03:15–04:00 | Repair, comparison, review & demo | Repaired artifacts, `corruption_report.md`, không secret |

Kế hoạch này khớp với thực tế commit history (xem bên dưới): ingestion/cleaning và evaluation/observability hoàn thành trước (tương ứng CP0–CP2), baseline orchestration (CP3) và corruption/repair orchestration (CP5–CP6) hoàn thành sau cùng vì phụ thuộc vào artifact của các module trước.

### Phân chia kế hoạch theo vai trò

Việc chia kế hoạch bám theo phân công ở mục 1: mỗi vai trò làm việc trên nhánh riêng, chỉ đụng vào phần module mình sở hữu (không sửa chữ ký hàm module khác đang gọi), rồi tích hợp dần vào `main` để tránh xung đột lớn ở cuối buổi — thay vì đợi tất cả xong mới ghép một lần.

### Quản lý team & merge workflow (bằng chứng từ `git log --graph --all`)

| Nhánh | Chủ | Nội dung chính | Trạng thái |
| --- | --- | --- | --- |
| `main` | Chung | Nhánh tích hợp — mọi feature branch merge về đây | Nhánh ổn định |
| `DungMai` | Mai Tiến Dũng (Vai trò 4) | `Implement build_testset.py`, `src/eval + src/observability` | Đã merge qua **PR #1** (commit `892a0d7`) |
| `tuananh` | Phạm Tuấn Anh (Vai trò 1) | `role 1 day 10` (CP1 ingest, orchestration), `finish individual report` | Đã merge qua **PR #3** (commit `375174c`) và merge trực tiếp (commit `66261e9`) |
| `dev` | Chung | Nhánh phát triển song song, đồng bộ hai chiều với `main` | Đang hoạt động |

Trình tự merge thực tế (từ cũ đến mới, rút gọn từ `git log`):

```text
10218c3 first commit
540736f Add files via upload
1f7b45a Implement src/eval + src/observability          (nhánh DungMai)
47fb9fb [feat]: CP1 - role 2, ingest data                (nhánh main)
62c234f [feat] role 2 update ingest data, clean data     (nhánh main)
e5c9b37 Implement build_testset.py                       (nhánh DungMai)
892a0d7 Merge pull request #1 from .../DungMai            <- merge vào main
5c06ff5 role 1 day 10                                     (nhánh tuananh)
375174c Merge pull request #3 from .../tuananh             <- merge vào main
802f207 end step 12                                       (nhánh tuananh, sau merge)
38c03e7 Add files via upload
33022d1 finish individual report                          (nhánh tuananh)
66261e9 Merge branch main ... into tuananh                 <- đồng bộ hai chiều
```

Nhận xét: các module có thể phát triển độc lập (`DungMai` làm `testset.py`/`eval`/`observability`, `tuananh` làm `ingest`/orchestration) được merge về `main` qua Pull Request để review trước khi tích hợp, đúng nguyên tắc "chia theo deliverable, có owner, input/output rõ ràng" ở mục 3. Hai thành viên còn lại (Nguyễn Thị Thương, Nguyễn Đức Anh) hiện chưa có nhánh remote riêng trong lịch sử — cần bổ sung nhánh/PR tương ứng cho `crossref.py`/`corruption.py` (Thương) và `retrieval/*` (Đức Anh) trước khi nộp để lịch sử merge phản ánh đúng toàn bộ phân công ở mục 1.

### Rủi ro tích hợp đã quản lý

- **Trùng file cấu hình chung (`core/config.py`, `Paths`):** chỉ Vai trò 1 (lead) được sửa, các vai trò khác chỉ đọc, tránh xung đột merge trên file được nhiều module phụ thuộc.
- **Thứ tự phụ thuộc:** `corruption_flow.py` chủ động kiểm tra `paths.clean_json`/`baseline_metrics.json` tồn tại trước khi chạy, raise lỗi rõ ràng nếu ai đó merge/chạy corruption flow trước khi baseline hoàn tất — tránh lỗi âm thầm khi tích hợp sai thứ tự.
- **Artifact do nhiều người ghi:** mỗi trạng thái (baseline/corrupted/repaired) dùng path và Chroma collection riêng (`papers-baseline`/`-corrupted`/`-repaired`) để việc một thành viên chạy lại corruption flow không ghi đè kết quả baseline của người khác.
