# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyen Thi Thuong             |
| MSSV               | 2A202601226                     |
| Khóa/Lớp         | K4            |
| Tên nhóm         | MicroGenius     |
| Vai trò chính    | Role 2 — Ingestion & Cleaning; bổ sung Corruption/Repair orchestration                |
| Repository         | https://github.com/tuananhpham-vnu/K4_Day10_Data-Pipeline-Data-Observability-MicroGenius |
| Ngày hoàn thành | 2026-08-06               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Raw ingestion | `src/ingestion/crossref.py` (`PaperRecord`, `parse_crossref_payload`, `fetch_source_records`, `load_raw_records`) | Crossref REST API (`query`, `filter`, `rows` từ `Settings`) | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Hoàn thành |
| Cleaning & data modeling | `src/ingestion/cleaning.py` (`build_clean_dataframe`) | `list[PaperRecord]` + `run_date` | `data/clean/papers_clean.csv`, `data/clean/papers_clean.json` | Hoàn thành |
| Corruption/repair orchestration | `src/pipelines/corruption_flow.py` (`main`) | `data/clean/papers_clean.json` + `data/results/baseline_metrics.json` (artifact baseline) | `data/clean/papers_clean_corrupted.*`, `papers_clean_repaired.*`, `data/results/corruption_log.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `data/reports/corruption_report.md` | Hoàn thành |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Fetch + parse Crossref, lưu raw response trước parse, retry/backoff cho 429/503 | `src/ingestion/crossref.py` | `data/raw/crossref_response.json` (239KB), `data/raw/crossref_records.json` (24 records) | `cat data/raw/crossref_records.json \| python3 -c "import json,sys;print(len(json.load(sys.stdin)))"` → 24 |
| Chuẩn hóa title/summary/authors/categories, dedupe theo `paper_id`, tính `age_days`, build `text_for_embedding` | `src/ingestion/cleaning.py` | `data/clean/papers_clean.csv/json` (24 rows, 0 record bị loại) | So khớp `raw_count == clean_count` = 24 |
| Orchestrate corrupt → evaluate → repair → evaluate → compare, tái sử dụng đúng 1 evaluation set cho cả 3 trạng thái | `src/pipelines/corruption_flow.py` | `corruption_log.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `corruption_report.md` | `uv run python script/run_corruption_flow.py` → exit code 0 |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

`data/reports/corruption_report.md` — báo cáo so sánh baseline/corrupted/repaired do `corruption_flow.py` gọi `generate_corruption_report`. Report cho thấy `retrieval_hit_rate` giảm từ 1.000 xuống 0.800 sau corruption và phục hồi lại đúng 1.000 sau repair.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần của tôi giải quyết 3 việc: (1) lấy dữ liệu paper học thuật từ một nguồn sống bên ngoài (Crossref) một cách có thể truy vết (lưu raw trước khi biến đổi) và chịu được lỗi tạm thời (retry/backoff); (2) chuẩn hóa dữ liệu thô, không đồng nhất thành một schema sạch, ổn định để các bước embedding/evaluation phía sau dùng được ngay không phải đoán; (3) chứng minh bằng số liệu thật rằng dữ liệu lỗi làm giảm chất lượng RAG agent và có thể phục hồi bằng cách repair lại từ raw — đây là phần orchestration nối toàn bộ các module quality/evaluation của các bạn khác thành một luồng chạy được.

### Cách triển khai

- **Document identity ổn định**: dùng `DOI` làm `paper_id` vì đây là field duy nhất, bất biến theo chuẩn Crossref cho mọi công bố — không dùng `title` (có thể trùng) hay index trong response (đổi giữa các lần gọi).
- **Retry/backoff**: tối đa 5 lần, chờ `2**attempt` giây khi gặp status `429`/`503`, dừng ngay với status khác.
- **Cleaning rules**: loại record thiếu `paper_id`/`title`/`summary`/ngày hợp lệ; dedupe `authors`/`categories` giữ thứ tự bằng `dict.fromkeys`; sort theo `published` giảm dần rồi `drop_duplicates(subset="paper_id", keep="first")` để giữ bản mới nhất nếu trùng DOI.
- **Corruption/repair orchestration**: đọc **clean baseline đã lưu** để corrupt — đúng ngữ nghĩa "dữ liệu sạch bị hỏng sau cleaning". Ngược lại, repair đọc lại **raw** (`load_raw_records` + `build_clean_dataframe`) và build lại từ đầu — đúng ngữ nghĩa "khôi phục từ nguồn gốc", không sửa tay dữ liệu đã hỏng. Cả corrupted và repaired đều evaluate trên **cùng một `eval_testset`** đã dùng cho baseline để phép so sánh có ý nghĩa.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | Crossref API response (JSON) → `list[PaperRecord]` → `pandas.DataFrame` (schema 13 cột: `paper_id, title, summary, authors_joined, categories_joined, primary_category, published, updated, age_days, summary_chars, text_for_embedding, abs_url, pdf_url`) |
| Output                         | `data/raw/*.json`, `data/clean/*.csv|json`, và (từ `corruption_flow.py`) `data/clean/*_corrupted.*`, `*_repaired.*`, `corruption_log.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `corruption_report.md` |
| Module phụ thuộc             | `core.config` (Settings/Paths), `core.utils` (`write_json`, `read_json`, `write_csv`) |
| Module sử dụng output        | `retrieval.index.LocalEmbeddingIndex` (role 1), `evaluation.metrics.evaluate_pipeline`, `observability.quality`/`reporting` (role 3/4) |
| Điều kiện lỗi cần xử lý | `corruption_flow.py` guard: raise `RuntimeError` rõ ràng nếu chưa có `clean_json`/`baseline_metrics.json` (chưa chạy baseline) thay vì lỗi mơ hồ giữa chừng |

### Cách xác minh

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** cả hai lệnh chạy hết, không exception; `retrieval_hit_rate` của corrupted thấp hơn baseline rõ rệt, repaired quay lại bằng baseline.
- **Kết quả thực tế:** cả hai lệnh exit code 0. `hit_rate baseline=1.000 corrupted=0.800 repaired=1.000` (in trực tiếp bởi `corruption_flow.py`), khớp với `data/results/*.json`.
- **Artifact/log:** `data/results/baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `data/results/corruption_log.json`, `data/reports/corruption_report.md`. Không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** trong `corruption_flow.py`, bước repair cần đưa dataset đã bị corrupt (mất record, summary rỗng, ngày sai, duplicate...) trở lại trạng thái đúng. Có 2 cách tiếp cận khả thi để làm việc này.
- **Các phương án đã cân nhắc:** (1) **Patch ngược từ log** — đọc `corruption_log.json` (đã ghi `paper_id`, `corruption_type`, `before`/`after` cho từng thao tác) rồi áp ngược lại từng thay đổi lên `corrupted_df` để khôi phục nguyên trạng; (2) **Re-derive toàn bộ từ raw** — bỏ qua `corrupted_df` hoàn toàn, gọi lại `load_raw_records(raw_records_json)` + `build_clean_dataframe(...)` để build một dataset sạch mới từ nguồn gốc.
- **Phương án đã chọn:** (2) — repair bằng cách build lại hoàn toàn từ raw, không đụng đến `corrupted_df` hay `corruption_log.json` ở bước repair.
- **Lý do:** phương án (1) chỉ đúng nếu log ghi lại **đầy đủ mọi side-effect** của mọi loại corruption — nếu sau này có ai thêm 1 loại corruption mới mà quên log đủ field, patch ngược sẽ phục hồi sai mà không có cách nào tự phát hiện. Phương án (2) không phụ thuộc vào tính đầy đủ của log: raw response là nguồn dữ liệu độc lập, chưa từng bị corruption chạm vào, nên dataset build lại từ đó **chắc chắn sạch 100%** bất kể corruption đã làm gì. Đây cũng đúng tinh thần "repair từ nguồn đáng tin cậy" mà bài lab yêu cầu, thay vì chỉ che triệu chứng.
- **Bằng chứng quyết định phù hợp:** `repaired_quality.json` có `passed_checks: 6`, `failed_checks: []` — sạch tuyệt đối, không còn dấu vết của bất kỳ loại corruption nào (kể cả những loại không được kiểm tra trực tiếp bởi quality checks, ví dụ `truncate_title`). Nếu dùng phương án patch-ngược, kết quả sẽ phụ thuộc vào độ đầy đủ của log và khó đảm bảo mức sạch tuyệt đối này.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `uv run python -c "print('hello')"` treo vô thời hạn, không in ra gì, cuối cùng bị kill với exit code `120` — không có traceback, không có thông báo lỗi nào để dựa vào.
- **Lệnh hoặc bước tái hiện:** bất kỳ lệnh nào bắt đầu bằng `uv run ...` (kể cả lệnh đơn giản nhất) đều treo và bị kill sau timeout, trong khi cùng lệnh đó chạy trong terminal thường của tôi thì bình thường.
- **Nguyên nhân gốc:** cô lập vấn đề bằng cách loại trừ dần: gọi trực tiếp `.venv/bin/python3.11 -c "print('hello')"` (không qua `uv`) thì chạy tức thì, không treo. Vậy vấn đề không nằm ở code hay ở Python, mà nằm ở chính `uv` — nhiều khả năng `uv run` cố gắng resolve/verify lockfile qua mạng trước khi thực thi, và ở môi trường tôi đang thao tác, việc gọi mạng dạng đó không được phản hồi nên `uv` treo mãi cho tới khi bị kill.
- **Cách xử lý:** bỏ qua `uv run`, gọi thẳng `.venv/bin/python3.11 <script>` cho mọi lệnh cần chạy trong môi trường đó — vì `.venv` đã có sẵn đầy đủ dependency (không có dependency mới nào cần cài thêm sau khi merge, đã kiểm tra `pyproject.toml`/`uv.lock` không đổi), nên bỏ qua bước resolve của `uv` không ảnh hưởng đến kết quả chạy.
- **Cách xác minh sau khi sửa:** chạy `timeout 400 .venv/bin/python3.11 script/run_phase1.py` và `.../script/run_corruption_flow.py` — cả hai chạy xong, exit code 0, cho ra đầy đủ artifact thật (`baseline_metrics.json`, `corruption_report.md`...).
- **Điều học được:** khi một lệnh treo mà không có lỗi rõ ràng, nên cô lập từng lớp công cụ (wrapper `uv` vs. runtime `python` bên dưới) để xác định lớp nào thực sự gây treo, thay vì đoán mò hoặc thêm timeout rồi bỏ qua — nếu không có bằng chứng loại trừ rõ ràng, rất dễ kết luận sai nguyên nhân.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Crossref → vector index:** `crossref.py` gọi API lấy JSON thô, lưu nguyên vẹn (`raw_api_response`) rồi parse thành `PaperRecord` (dùng DOI làm `paper_id`, lưu `raw_records_json`). `cleaning.py` chuẩn hóa các record này thành `DataFrame` sạch (`build_clean_dataframe`), thêm `text_for_embedding` và `age_days`. `retrieval/index.py` (role 1) lấy `text_for_embedding` của từng row, encode bằng `sentence-transformers/all-MiniLM-L6-v2`, nạp vào một collection ChromaDB cùng metadata (`paper_id`, `title`, `published`, `authors_joined`...).
2. **Evaluation set & ground-truth doc IDs:** mỗi câu hỏi trong test set gắn với `ground_truth` (câu trả lời đúng, ví dụ `authors_joined` của đúng 1 paper) và `ground_truth_doc_ids` (danh sách `paper_id` chứa câu trả lời đó). Khi agent trả lời, hệ thống so `retrieved_doc_ids` (từ ChromaDB search) với `ground_truth_doc_ids` để tính `retrieval_hit_rate`, và so nội dung câu trả lời với `ground_truth` để tính `token_f1` và điểm judge (LLM chấm).
3. **Quality checks vs. freshness monitoring:** quality checks (`run_data_quality_checks`) kiểm tra tính toàn vẹn cấu trúc tại một thời điểm — null, duplicate `paper_id`, độ dài `summary` tối thiểu. Freshness monitoring (`build_freshness_report`) chỉ tập trung vào chiều thời gian — dữ liệu có "cũ" quá ngưỡng (`age_days` so với `freshness_threshold_days`) hay không. Một dataset có thể pass hết quality checks nhưng vẫn stale, hoặc ngược lại.
4. **Vì sao dùng chung 1 test set cho cả 3 trạng thái:** nếu mỗi trạng thái dùng test set khác nhau, chênh lệch metric có thể do câu hỏi khác nhau (độ khó khác nhau) chứ không phải do chất lượng dữ liệu thay đổi — làm phép so sánh vô nghĩa. Dùng chung 1 test set đảm bảo biến số duy nhất thay đổi giữa 3 lần evaluate là chính dữ liệu (baseline/corrupted/repaired), nên chênh lệch metric mới thực sự phản ánh tác động của corruption/repair.
5. **Repair thành công dựa trên artifact/metric nào:** (a) `repaired_quality.json` có `failed_checks: []` (pass hết, giống baseline, khác corrupted có `paper_id_unique` và `summary_length` fail); (b) `repaired_metrics.json` có `retrieval_hit_rate/mean_token_f1/judge_accuracy/mean_judge_score` quay lại đúng bằng số của baseline (1.0/1.0/1.0/5.0), không chỉ "tốt hơn corrupted" mà phải "bằng hoặc tốt hơn baseline".

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |    1.000 |     0.800 |    1.000 | Giảm 20 điểm phần trăm do 2 record "drop_latest" biến mất khỏi index — câu hỏi hỏi về các paper đó không còn tài liệu đúng để retrieve. |
| `mean_token_f1`      |    1.000 |     0.807 |    1.000 | Giảm tương ứng với hit_rate — khi không tìm đúng tài liệu, câu trả lời rút ra từ tài liệu sai nên overlap từ vựng với ground truth giảm mạnh. |
| `judge_accuracy`     |    1.000 |     0.800 |    1.000 | Khớp chính xác với `retrieval_hit_rate` — LLM judge chấm "sai" đúng ở các câu bị ảnh hưởng bởi drop, không có false negative/positive. |
| `mean_judge_score`   |      5.0 |       4.2 |      5.0 | Giảm 0.8 điểm/5 — mức giảm nhỏ hơn tỉ lệ vì các câu trả lời "sai do thiếu tài liệu" vẫn được judge chấm điểm một phần nếu câu trả lời gần đúng theo ngữ cảnh khác. |
| Quality checks         |     PASS |      FAIL (`paper_id_unique`, `summary_length`) |     PASS | Đúng như log corruption: 2 duplicate row → fail unique; 5 summary bị blank/rỗng → fail min length. |
| Freshness status       |    Fresh |     Fresh (stale_rows=0) |    Fresh | Bất ngờ: `stale_date` corruption (+400 ngày) không đủ để vượt ngưỡng `maximum_age_days=3650` mà role 3/4 cấu hình — nên freshness check không bắt được lỗi này (xem mục "kết quả khác kỳ vọng" bên dưới). |

### Kết luận từ số liệu

1. **Drop 2 record mới nhất + blank/nhiễu summary** (`corruption_log.json`) → **quality check `paper_id_unique` và `summary_length` chuyển FAIL** (do thêm duplicate và summary rỗng) → **`retrieval_hit_rate` giảm từ 1.000 xuống 0.800** (agent không còn tìm được tài liệu đúng cho các câu hỏi liên quan record bị drop/hỏng).
2. **Repair (đọc lại raw, build lại clean từ đầu)** → **toàn bộ quality checks quay lại PASS, `failed_checks: []`** → **cả 4 metric agent (`retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`) phục hồi đúng bằng baseline**, không chỉ "cải thiện" mà "khôi phục hoàn toàn".

**Corruption ảnh hưởng rõ nhất:** `drop_latest` (xóa 2 record) — vì đây là loại lỗi duy nhất **xóa mất thông tin hoàn toàn** thay vì làm nhiễu thông tin có sẵn; các câu hỏi ground-truth trỏ vào 2 record đó chắc chắn miss, kéo `retrieval_hit_rate` giảm trực tiếp và tỉ lệ thuận với số record bị mất trên tổng eval set.

**Kết quả khác kỳ vọng:** ban đầu tôi kỳ vọng `is_fresh` sẽ chuyển `false` ở dataset corrupted vì có corruption loại `stale_date` (+400 ngày). Thực tế `stale_rows=0` cả 2 phía vì ngưỡng `maximum_age_days` trong `quality.py` (role 3/4 viết) mặc định là 3650 ngày (~10 năm) — rộng hơn nhiều so với `freshness_threshold_days=180` mà `core/config.py` định nghĩa cho mục đích khác. Đây là một khoảng hở giữa 2 ngưỡng do 2 module độc lập, chưa thống nhất — tôi đã kiểm tra bằng cách đọc trực tiếp `thresholds.maximum_age_days` trong `corrupted_quality.json` để xác nhận giả thuyết, chưa sửa vì không thuộc phạm vi file tôi sở hữu.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Artifact dữ liệu đã commit vào git **không tự động đúng theo code hiện tại** — luôn ưu tiên regenerate từ raw bằng code mới nhất khi có nghi ngờ, thay vì tin artifact cũ.
2. Data quality checks và freshness monitoring là 2 tín hiệu độc lập, đo 2 chiều khác nhau (cấu trúc vs. thời gian) — một corruption có thể "lọt" qua tín hiệu này nhưng bị bắt bởi tín hiệu kia (hoặc không bị bắt bởi cả hai nếu ngưỡng cấu hình không khớp mục đích, như trường hợp `stale_date` ở mục 8).
3. Corruption dạng "mất thông tin" (drop record) tác động lên RAG agent trực tiếp và đo được rõ ràng hơn nhiều so với corruption dạng "làm nhiễu thông tin" (noise/truncate) trong evaluation set nhỏ — vì retrieval fail là nhị phân (có/không tìm thấy đúng tài liệu), trong khi nhiễu nội dung chỉ làm giảm dần chất lượng câu trả lời.

### Nếu có thêm thời gian

Thống nhất lại ngưỡng `maximum_age_days` trong `quality.py` với `freshness_threshold_days` trong `core/config.py` (hiện đang lệch nhau 3650 ngày vs 180 ngày) để freshness check thực sự bắt được corruption loại `stale_date` — đo cải thiện bằng cách chạy lại `corruption_flow.py` và kiểm tra `corrupted_freshness_report.json` có `is_fresh: false` sau khi chỉnh ngưỡng.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyen Thi Thuong
**Ngày xác nhận:** 2026-08-06
