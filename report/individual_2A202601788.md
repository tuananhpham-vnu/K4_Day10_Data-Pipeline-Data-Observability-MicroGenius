# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Đức Anh |
| MSSV | 2A202601788 |
| Khóa/Lớp | Khóa 4 |
| Tên nhóm | MicroGenius |
| Vai trò chính | Retrieval/RAG, evaluation-set và pipeline integration |
| Repository | https://github.com/tuananhpham-vnu/K4_Day10_Data-Pipeline-Data-Observability-MicroGenius |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Evaluation set | `src/evaluation/testset.py::build_test_set` | Cleaned DataFrame | `data/eval/test_set.json` | Hoàn thành |
| Baseline orchestration | `src/pipelines/phase1.py::main` | Raw snapshot, cleaned schema, settings | Baseline index, metrics, quality và report | Hoàn thành |
| Corruption/repair flow | `src/pipelines/corruption_flow.py::main` | Baseline data, raw records, evaluation set | Corrupted/repaired artifacts và comparison report | Hoàn thành |
| Retrieval verification | `src/retrieval/index.py`, `embeddings.py`, `qa.py` | Cleaned documents và query | Chroma index, SearchResult, smoke lookup/search | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra package observability | `src/observability/__init__.py` | Sửa import nhầm `observability.metrics`, giúp pipeline import được quality/reporting |
| Đồng bộ freshness threshold | `src/observability/quality.py` | Quality/freshness đọc đúng `Settings.freshness_threshold_days=180` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Tích hợp corruption → evaluate → repair | `corruption_flow.py`, `corruption.py` | Corruption log có 14 entries; metrics corrupted giảm và repaired phục hồi | `python script/run_corruption_flow.py` |
| Kiểm tra retrieval contract | `index.py`, `qa.py` | Semantic search trả 4 kết quả; exact lookup theo ID/title hoạt động | Smoke query/lookup trên Chroma index |

Output tiêu biểu là `data/reports/corruption_report.md`, được tạo từ metrics và quality/freshness artifacts thực tế, không nhập tay số liệu.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Các module retrieval, evaluation và observability đã có những contract riêng nhưng chưa được nối thành pipeline chạy được. Ngoài ra, evaluation set ban đầu không tạo được vì dữ liệu Crossref thiếu category. Để giữ schema đầy đủ, cleaning dùng `primary_category` làm fallback (`unknown` trong các record không có subject). Corruption flow cũng cần dùng cùng test set để phép so sánh baseline/corrupted/repaired có ý nghĩa.

### Cách triển khai

`build_test_set()` chọn tối đa năm paper đại diện theo vị trí ổn định trong cleaned DataFrame. Mỗi paper tạo bốn câu hỏi summary, authors, publication date và categories; category được bảo đảm từ `primary_category` fallback trong cleaning. `ground_truth_doc_ids` luôn lấy từ `paper_id` của cleaned record.

Baseline flow load raw snapshot, clean dữ liệu, build collection `papers-baseline`, tạo/load test set, evaluate, chạy quality/freshness và sinh report.

Corruption flow áp dụng các lỗi có seed cố định: drop latest, blank summary, inject noise, truncate title, stale date và duplicate row. Sau đó flow build collection `papers-corrupted`, đánh giá lại trên cùng test set, repair bằng cách clean lại raw records từ đầu và build collection `papers-repaired`.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `Settings`, `data/raw/crossref_records.json`, cleaned DataFrame và `data/eval/test_set.json` |
| Embedding | `sentence-transformers/all-MiniLM-L6-v2`, vector normalized, ChromaDB cosine |
| Output | `SearchResult`, metrics JSON, quality/freshness JSON và Markdown reports |
| Collection | `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Metadata | `paper_id`, `title`, `published`, `authors_joined`, `categories_joined`, `summary`, `abs_url`, `pdf_url` |
| Điều kiện lỗi | Thiếu raw/clean artifact, empty cleaned DataFrame, thiếu field evaluation hoặc lỗi collection phải dừng với lỗi rõ ràng |

### Cách xác minh

```powershell
python -m pip install -e .
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** baseline, corrupted và repaired tạo đủ artifact; corrupted quality/metrics xấu hơn baseline; repaired phục hồi.
- **Kết quả thực tế:** baseline và repaired có `retrieval_hit_rate=1.0`, corrupted giảm còn `0.8`; quality corrupted FAIL, repaired PASS.
- **Artifact:** `data/results/`, `data/quality/`, `data/embeddings/`, `data/reports/`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Evaluation set phải hoạt động khi Crossref không trả category và vẫn phải tạo ground truth không rỗng.
- **Các phương án đã cân nhắc:** loại bỏ toàn bộ sample thiếu category; để category rỗng; hoặc fallback sang `primary_category`.
- **Phương án đã chọn:** fallback sang `primary_category`, và dùng `unknown` khi Crossref không có subject.
- **Lý do:** Giữ evaluation schema đầy đủ bốn question type mà không tạo ground truth rỗng; đồng thời không loại bỏ paper hợp lệ chỉ vì Crossref thiếu `subject`.
- **Bằng chứng:** `data/eval/test_set.json` tạo được 20 sample và `baseline_metrics.json` có `samples=20`, `retrieval_hit_rate=1.0`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Chroma báo `NotFoundError` khi pipeline query ngay sau `LocalEmbeddingIndex.build()`.
- **Nguyên nhân gốc:** `build()` tạo một `PersistentClient` để ghi nhưng sau đó khởi tạo instance qua constructor, mở thêm client thứ hai vào cùng persistent store trong cùng process.
- **Cách xử lý:** Giữ lại client và collection vừa tạo, dựng instance bằng các handle đó thay vì mở client thứ hai.
- **Cách xác minh:** Chạy lại baseline và corruption flow; cả ba collection được build/query, metrics được ghi đầy đủ.
- **Bài học:** Với local vector store có state SQLite, cần quản lý vòng đời client nhất quán và tránh mở nhiều handle cùng persistent path trong một process.

## 7. Hiểu biết về luồng end-to-end

1. Crossref trả raw response và raw records. Cleaning chuẩn hóa record, tạo `text_for_embedding`, sau đó MiniLM biến text thành vector để lưu trong ChromaDB cùng metadata.
2. Evaluation set giữ câu hỏi, ground truth và `ground_truth_doc_ids`. Evaluator so sánh ID retrieved với ground-truth ID để tính retrieval hit và so answer với ground truth để tính token F1/judge metrics.
3. Quality checks kiểm tra tính toàn vẹn như null, duplicate, summary length; freshness kiểm tra tuổi bản ghi và stale date. Hai nhóm signal bổ sung cho nhau.
4. Cùng test set được dùng cho ba trạng thái để mọi thay đổi metric phản ánh thay đổi dữ liệu/index thay vì thay đổi câu hỏi.
5. Repair thành công khi repaired quality pass, freshness trở lại fresh và repaired metrics phục hồi về mức baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.00 | 0.80 | 1.00 | Corruption làm mất 20% hit; repair phục hồi hoàn toàn. |
| `mean_token_f1` | 1.00 | 0.807 | 1.00 | Summary rỗng, noise và title truncate làm answer lệch ground truth. |
| `judge_accuracy` | 1.00 | 0.80 | 1.00 | Mức giảm khớp với số sample bị ảnh hưởng. |
| `mean_judge_score` | 5.00 | 4.20 | 5.00 | Chất lượng answer giảm rõ sau corruption. |
| Quality checks | PASS | FAIL | PASS | Corrupted fail duplicate, summary length và freshness; repaired pass. |
| Freshness status | Fresh | Stale | Fresh | Hai stale dates bị phát hiện với threshold 180 ngày. |

### Kết luận từ số liệu

1. Corruption ở summary/title/date và duplicate row làm quality signal xấu đi; retrieval hit rate giảm từ 1.0 xuống 0.8 và token F1 giảm xuống khoảng 0.807.
2. Repair bằng raw source không chỉnh tay corrupted data. Sau khi clean lại và rebuild index, quality/freshness trở lại PASS/Fresh và metrics quay về baseline.

Ảnh hưởng rõ nhất được quan sát ở blank summary, duplicate row và stale date: chúng lần lượt làm `summary_length`, `paper_id_unique` và freshness check thất bại. Ở tầng RAG, các record mất hoặc bị biến dạng text làm semantic retrieval không còn tìm đúng ground-truth document.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Pipeline end-to-end cần contract rõ giữa raw schema, clean schema, embedding manifest và evaluation set.
2. Data quality/freshness phải được đo song song với RAG metrics; chỉ nhìn câu trả lời không đủ để tìm root cause.
3. Muốn chứng minh corruption ảnh hưởng agent, phải giữ nguyên evaluation set và rebuild index riêng cho từng trạng thái.

### Nếu có thêm thời gian

Có thể thêm test tự động cho từng corruption rule, kiểm tra collection count/metadata schema và chạy Ragas có kiểm soát. Ngoài ra nên tách cấu hình judge LLM khỏi fallback heuristic để báo cáo phân biệt rõ hai kiểu scoring.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Đức Anh  
**Ngày xác nhận:** 2026-08-06
