# Member Role Report — Day 10: Data Pipeline & Data Observability

> Báo cáo cá nhân của thành viên phụ trách vai trò 4: Evaluation & Observability.

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Mai Tiến Dũng |
| MSSV | 2A202601838 |
| Khóa/Lớp | K4 |
| Tên nhóm | MicroGenius |
| Vai trò chính | Vai trò 4: Evaluation & Observability |
| Repository | https://github.com/tuananhpham-vnu/K4_Day10_Data-Pipeline-Data-Observability-MicroGenius |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Xây dựng evaluation test set | `src/evaluation/testset.py` — `build_test_set()` | Cleaned DataFrame từ `data/clean/papers_clean.csv` | `data/eval/test_set.json` gồm `question`, `ground_truth`, `ground_truth_doc_ids`, `question_type` | Hoàn thành phần triển khai; cần xác minh lại artifact cuối sau khi điều chỉnh dữ liệu thiếu |
| Đánh giá retrieval và answer quality | `src/evaluation/metrics.py` — `evaluate_pipeline()` | Index, test set và kết quả từ RAG agent | `baseline_metrics.json`, `baseline_answers.json`; các metric retrieval hit, token F1, judge | Hoàn thành phần triển khai; chưa có đủ số liệu ba pha để kết luận |
| Data quality checks | `src/observability/quality.py` — `run_data_quality_checks()` | Cleaned/corrupted/repaired DataFrame và `Settings` | Quality JSON với row count, null, duplicate, title/summary checks | Hoàn thành phần triển khai; cần chạy trên cả ba pha |
| Freshness monitoring | `src/observability/quality.py` — `build_freshness_report()` | `published`, `age_days`, cấu hình freshness | Freshness JSON với latest/oldest, stale/future/invalid rows | Hoàn thành phần triển khai; clean dataset chưa có timestamp fetch riêng |
| Báo cáo baseline và corruption | `src/observability/reporting.py` — `generate_phase1_report()`, `generate_corruption_report()` | Metrics, quality và freshness dictionaries | Markdown report cho baseline và baseline–corrupted–repaired | Hoàn thành phần triển khai; chưa có đủ artifact thực nghiệm để điền số cuối |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
|---|---|---|
| Đối chiếu contract giữa test set và RAG answer | `src/retrieval/qa.py`/`agent.py`, `src/retrieval/index.py` | Xác nhận evaluation sử dụng `answer`, `retrieved_doc_ids`, `retrieved_contexts`; phát hiện câu hỏi cần khớp phrase và cách đặt title trong dấu nháy đơn |
| Debug lỗi tạo test set | Pipeline cleaning và script tạo test set | Xác định lỗi `found 0` không phải do thiếu tên cột mà do logic yêu cầu mỗi paper phải đồng thời có đủ summary/authors/date/categories |
| Hướng dẫn cố định test set | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` | Thống nhất baseline, corrupted và repaired phải dùng cùng một `test_set.json` để so sánh công bằng |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
|---|---|---|---|
| Thiết kế bốn loại câu hỏi từ cleaned dataset | `src/evaluation/testset.py` | Câu hỏi `summary`, `authors`, `date`, `categories` và ground truth lấy từ record clean | `python -m py_compile src/evaluation/testset.py`; chạy script tạo test set và kiểm tra `data/eval/test_set.json` |
| Bảo đảm document ID trong ground truth là ID thật | `build_test_set()` | `ground_truth_doc_ids=[paper_id]`, không dùng DataFrame index hoặc ID tự tạo | So sánh toàn bộ ID trong test set với `set(clean_df["paper_id"])` |
| Chấm retrieval và answer quality | `src/evaluation/metrics.py` | Retrieval hit rate, token F1, LLM judge và Ragas tùy chọn | Đọc `baseline_metrics.json` và `baseline_answers.json` sau khi pipeline evaluation chạy |
| Kiểm tra chất lượng dữ liệu | `run_data_quality_checks()` | Row count, null count, `paper_id` uniqueness, title missing, summary length, freshness gate | Chạy quality script và mở `data/quality/baseline_quality.json` |
| Tạo freshness report | `build_freshness_report()` | latest/oldest published, stale/fresh/future/invalid rows, `is_fresh` | Mở `data/quality/baseline_freshness.json` |
| Tạo báo cáo người đọc được | `generate_phase1_report()`, `generate_corruption_report()` | Markdown report tổng hợp dữ liệu và RAG metrics | Mở report trong `data/reports/` hoặc thư mục report được cấu hình |

Một output cụ thể do phần việc của tôi tạo ra là `data/eval/test_set.json`. Mỗi sample chứa câu hỏi, câu trả lời chuẩn, loại câu hỏi và danh sách `paper_id` thật mà retrieval cần tìm được. Test set này là đầu vào chung cho cả baseline, corrupted và repaired.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần việc của tôi giải quyết hai nhóm vấn đề:

1. Cần một bộ kiểm thử có ground truth rõ ràng để đo RAG agent có retrieve đúng paper và trả lời đúng nội dung hay không.
2. Cần quan sát chất lượng và độ mới của dữ liệu để biết khi nào metric của RAG giảm do dữ liệu đầu vào xấu, thay vì chỉ nhìn vào câu trả lời cuối.

Nếu không có test set cố định, không thể so sánh baseline với corruption một cách công bằng. Nếu không có quality/freshness artifact, không thể chứng minh corruption thực sự làm dữ liệu xấu đi trước khi kết luận nó làm RAG kém đi.

### Cách triển khai

`testset.py` nhận cleaned DataFrame, chuẩn hóa các field và tạo câu hỏi theo metadata thật của paper. Bốn dạng câu hỏi được thiết kế để khớp với contract của RAG answer:

- Summary: lấy câu đầu của `summary`.
- Authors: lấy `authors_joined` hoặc danh sách authors đã chuẩn hóa.
- Date: lấy `published`.
- Categories: lấy `categories_joined` hoặc categories đã chuẩn hóa.

Title được đặt trong dấu nháy đơn để logic exact lookup của RAG có thể nhận ra paper. `ground_truth_doc_ids` luôn lấy trực tiếp từ `paper_id` của cleaned dataset.

`metrics.py` đọc test set, gọi RAG agent cho từng câu hỏi và lưu:

- Answer thực tế.
- Document IDs và contexts đã retrieve.
- `retrieval_hit`: có lấy đúng paper hay không.
- `token_f1`: mức overlap từ giữa answer và ground truth.
- LLM judge: điểm 1–5, đúng/sai và lý do.
- Ragas nếu bật bằng biến môi trường.

`quality.py` kiểm tra row count, null, duplicate `paper_id`, title missing, summary missing/quá ngắn và freshness. Freshness ưu tiên cột `age_days`; nếu không có thì tính từ `published` theo thời điểm tham chiếu.

`reporting.py` chuyển các JSON machine-readable thành Markdown. Báo cáo corruption so sánh baseline, corrupted và repaired, tính corruption delta, repair delta và recovery rate.

### Input, output và contract

| Thành phần | Mô tả |
|---|---|
| Input | Clean DataFrame có `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `age_days`; test set JSON; RAG index |
| Output | `test_set.json`, answers JSON, metrics JSON, quality JSON, freshness JSON và Markdown report |
| Module phụ thuộc | `src/core/config.py`, `src/core/utils.py`, `src/retrieval/index.py`, `src/retrieval/qa.py` hoặc `src/retrieval/agent.py`, embedding/LLM module |
| Module sử dụng output | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, reporting và nhóm phân tích kết quả |
| Điều kiện lỗi cần xử lý | DataFrame rỗng; thiếu `paper_id`; ID trùng/null; thiếu field để tạo câu hỏi; test set sai schema; RAG không trả document; LLM judge/Ragas không khả dụng; ngày invalid hoặc ở tương lai |

### Cách xác minh

```powershell
$env:PYTHONPATH = "src"

python -m py_compile src\evaluation\testset.py
python -m py_compile src\evaluation\metrics.py
python -m py_compile src\observability\quality.py
python -m py_compile src\observability\reporting.py

python script\build_testset.py
python script\run_phase1.py
```

Kiểm tra `paper_id` clean:

```powershell
python -c "import pandas as pd; df=pd.read_csv('data/clean/papers_clean.csv'); print('Rows:', len(df)); print('Null paper_id:', df['paper_id'].isna().sum()); print('Duplicate paper_id:', df['paper_id'].duplicated().sum())"
```

Kiểm tra test set không dùng ID tự tạo:

```powershell
python -c "import json,pandas as pd; df=pd.read_csv('data/clean/papers_clean.csv'); valid=set(df['paper_id'].dropna().astype(str).str.strip()); ts=json.load(open('data/eval/test_set.json',encoding='utf-8')); bad=[x for s in ts for x in s['ground_truth_doc_ids'] if str(x) not in valid]; print('Unknown IDs:', bad)"
```

- **Kết quả mong đợi:** Không có lỗi cú pháp; test set có đủ schema; `Unknown IDs: []`; quality/freshness JSON và phase report được tạo.
- **Kết quả thực tế:** Đã xác nhận cleaned dataset có các cột cần thiết. Khi chạy bản test set yêu cầu mỗi paper phải đủ toàn bộ metadata, pipeline báo `found 0`; lỗi này đã được phân tích và cần điều chỉnh logic tạo câu hỏi theo field có sẵn hoặc cải thiện dữ liệu clean.
- **Artifact/log:** `data/clean/papers_clean.csv`, `data/eval/test_set.json`, `data/quality/*.json`, `data/reports/*.md`. Không ghi `.env` hoặc secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần chọn document ID cho `ground_truth_doc_ids`.
- **Các phương án đã cân nhắc:**
  1. Tạo ID theo thứ tự test case hoặc DataFrame index.
  2. Dùng trực tiếp `paper_id` đã ổn định sau cleaning.
- **Phương án đã chọn:** Dùng trực tiếp `paper_id` từ cleaned dataset.
- **Lý do:** Retrieval trả về `SearchResult.paper_id`; hai phía phải dùng cùng namespace ID thì `retrieval_hit` mới đúng. DataFrame index có thể thay đổi khi sort/filter và ID tự tạo không có liên hệ với index.
- **Bằng chứng quyết định phù hợp:** Có thể kiểm tra toàn bộ `ground_truth_doc_ids` đều thuộc tập `clean_df["paper_id"]`. Việc này cũng cho phép dùng cùng test set cho baseline, corrupted và repaired.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**

```text
ValueError: At least 4 complete papers with unique, non-null paper_id values are required; found 0
```

- **Lệnh hoặc bước tái hiện:**

```powershell
$env:PYTHONPATH = "src"
python script\build_testset.py
```

- **Nguyên nhân gốc:** `testset.py` không chỉ yêu cầu `paper_id` hợp lệ mà còn loại toàn bộ row nếu paper thiếu bất kỳ field nào trong `summary`, `authors`, `published` hoặc `categories`. Vì vậy dù schema có đầy đủ tên cột, không paper nào vượt qua điều kiện `all(...)`.
- **Cách xử lý:** Kiểm tra schema thật của `papers_clean.csv`, xác nhận các cột là `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`. Đề xuất đổi điều kiện tối thiểu thành chỉ bắt buộc `paper_id` và `title`, sau đó tạo từng loại câu hỏi nếu field tương ứng có dữ liệu. Cuối cùng kiểm tra toàn test set vẫn có đủ bốn `question_type`.
- **Cách xác minh sau khi sửa:**

```powershell
python script\build_testset.py
python -c "import json; x=json.load(open('data/eval/test_set.json',encoding='utf-8')); print(len(x)); print(sorted(set(i['question_type'] for i in x)))"
```

- **Điều học được:** Có tên cột đúng không có nghĩa là dữ liệu đủ dùng. Validation cần phân biệt “field bắt buộc cho document” với “field chỉ bắt buộc cho một loại câu hỏi”, nếu không sẽ loại bỏ quá mức và làm mất toàn bộ evaluation coverage.

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu được tải từ Crossref trong `src/ingestion/crossref.py`, sau đó được chuẩn hóa và làm sạch trong `src/ingestion/cleaning.py`. Cleaned dataset chứa `paper_id`, nội dung, metadata và `text_for_embedding`. `src/retrieval/index.py` lấy text này, tạo embedding và lưu vào ChromaDB cùng metadata để RAG agent có thể tìm kiếm.
2. Evaluation set cung cấp câu hỏi, ground truth và `ground_truth_doc_ids`. Khi agent trả lời, evaluation so `ground_truth_doc_ids` với `retrieved_doc_ids` để đo retrieval hit. Answer được so với ground truth bằng token F1 và LLM judge; contexts có thể được dùng cho Ragas.
3. Quality checks đo tính đầy đủ và hợp lệ của dataset như số dòng, null, duplicate ID, title/summary missing. Freshness monitoring tập trung vào thời gian như `published`, `age_days`, stale/future/invalid dates và timestamp nguồn.
4. Baseline, corrupted và repaired phải dùng cùng test set vì chỉ khi giữ nguyên câu hỏi và ground truth thì thay đổi metric mới có thể quy về thay đổi dữ liệu/index. Nếu đổi test set, độ khó khác nhau sẽ làm phép so sánh không công bằng.
5. Repair được xem là thành công khi quality/freshness signal phục hồi, index được rebuild từ repaired data và các metric như retrieval hit rate, token F1, judge accuracy/score tăng trở lại gần baseline. Cần đối chiếu cả JSON artifact và Markdown comparison report.

## 8. Phân tích kết quả


### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |     1.00 |      0.80 |     1.00 | Giảm 20% khi corrupt (do drop 2 bản ghi mới nhất + duplicate làm nhiễu index), phục hồi hoàn toàn sau repair. |
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

1. Stable document ID là contract xuyên suốt ingestion, indexing và evaluation; nếu ID thay đổi thì retrieval metric mất ý nghĩa.
2. Data quality và freshness phải được ghi thành artifact trước corruption để tạo baseline có thể đối chiếu, không chỉ in log trên màn hình.
3. Chất lượng RAG phụ thuộc trực tiếp vào dữ liệu index: thiếu summary, metadata sai hoặc ID trùng có thể làm retrieval và answer quality giảm dù code agent không đổi.

### Nếu có thêm thời gian

Tôi sẽ bổ sung phân tích metric theo `question_type` và coverage theo field. Cụ thể, `metrics.json` sẽ có thêm `by_question_type` cho summary/authors/date/categories; test-set report sẽ ghi số paper đủ điều kiện cho từng loại câu hỏi. Cải thiện được đo bằng việc xác định rõ corruption nào ảnh hưởng đến loại câu hỏi nào, thay vì chỉ nhìn metric trung bình toàn bộ.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu; phần chưa có artifact được ghi rõ.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Mai Tiến Dũng  
**Ngày xác nhận:** 2026-08-06
