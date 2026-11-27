# Benchmark & Observability Report — Day 14

**Họ tên:** Trần Đức Trung

**Ngày chạy:** 26–27/11/2026

**Môi trường:** Develop benchmark trên Windows 11, Python 3.12.10, AMD Ryzen 7 5800H (16 luồng logic); hai agent dùng Uvicorn cục bộ. Production benchmark trong Docker Desktop 29.5.2 qua Ubuntu 24.04 WSL2; Locust chạy trong Compose, 1 rồi 3 replica agent.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Ngưỡng mặc định của load test, theo dõi trải nghiệm của nhóm request chậm. |
| Error rate `/ask` | ≤ 2% | Ngưỡng mặc định của load test, giới hạn tỷ lệ request không trả 200. |
| Accuracy trên golden dataset | ≥ 85% | Ngưỡng CI của bài 7.3. Gate cuối CP7 yêu cầu 100% và không regression. |

**Exercise 7.1 — Metrics.** Sau một request thành công, `/metrics` ghi counter `http_requests_total{method="POST",route="/ask",status="200"} 1.0`, gauge `agent_in_flight_requests 0.0`, và histogram `agent_question_length_chars` với count 1, sum 40. Gauge được đọc khi không còn request đang chạy. Dùng `route.path` và giá trị `unmatched` giữ số time series trong một tập nhỏ. Nếu dùng URL thực tế, mỗi URL lạ có thể tạo thêm series theo method, status và bucket, làm tăng RAM và chi phí scrape.

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.13 | 204.0 | 237.2 | 1700.4 | 1.00% | PASS |
| 10 | 42.54 | 191.9 | 234.6 | 1701.9 | 1.00% | PASS |
| 50 | 101.88 | 208.1 | 425.1 | 1742.0 | 0.67% | PASS |
| 100 | 51.22 | 495.8 | 4137.4 | 4519.9 | 2.00% | FAIL |

**Nhận xét:** Từ concurrency 1 đến 100, RPS đi từ **4.13** đến **51.22** (gấp **12.4 lần**), với mức cao nhất ở concurrency **50**. RPS không tăng tuyến tính. Các request chồng thời gian chờ mock LLM nên tăng concurrency giúp tận dụng thời gian chờ. Khi tải tăng, client và server còn chia sẻ CPU và event loop. Với 300 request mỗi lượt, một vài request mất thêm 1.500 ms cũng có thể kéo dài thời gian của lượt chạy, nhất là ở đợt cuối.

Mỗi lượt gửi 300 request, cùng model `mock-llm-small`, `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01`. RPS tính mọi request đo được. Percentile chỉ tính response HTTP 200. Số liệu: [`load_v2_c1.json`](06-lab-complete/benchmark-observability/develop/reports/load_v2_c1.json), [`load_v2_c10.json`](06-lab-complete/benchmark-observability/develop/reports/load_v2_c10.json), [`load_v2_c50.json`](06-lab-complete/benchmark-observability/develop/reports/load_v2_c50.json), [`load_v2_c100.json`](06-lab-complete/benchmark-observability/develop/reports/load_v2_c100.json).

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 186.2 | 220.3 | 235.3 |
| 0.03 (mặc định) | 225.0 | 233.7 | 1680.8 |
| 0.1 | 353.9 | 1699.6 | 1720.4 |

**Nhận xét:** Ở mức slow rate 3%, p99 là **1680.8 ms** so với **235.3 ms** khi không chèn request chậm, còn avg chỉ đổi từ **186.2** lên **225.0 ms**. Ở mức 10%, p95 đạt **1699.6 ms**. p99 nhạy với nhóm chậm nhỏ, còn p95 bắt đầu phản ánh rõ khi hơn khoảng 5% request rơi vào nhóm chậm. SLO theo p95 hoặc p99 giúp thấy phần đuôi mà average làm loãng.

Ba lượt dùng concurrency 20 và 300 request mỗi lượt, chỉ đổi `MOCK_SLOW_RATE` khi khởi động lại v2. Số liệu: [`load_v2_slow_0.json`](06-lab-complete/benchmark-observability/develop/reports/load_v2_slow_0.json), [`load_v2_slow_0.03.json`](06-lab-complete/benchmark-observability/develop/reports/load_v2_slow_0.03.json), [`load_v2_slow_0.1.json`](06-lab-complete/benchmark-observability/develop/reports/load_v2_slow_0.1.json).

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100.00% (23/23) |
| Avg tokens / câu | 57.3 | 109.0 | 114.7 |
| Tổng cost (USD) | $0.000407 | $0.000759 | $0.000799 |
| Cost / câu đúng (USD) | $0.00040695 | $0.00003616 | $0.00003475 |
| Quality gate | FAIL (≥ 80%) | PASS (≥ 80%) | PASS (≥ 100%) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | token, hết hạn, chữ ký | Thêm tài liệu phân biệt API key tĩnh với JWT có chữ ký và thời hạn. |
| `scaling-03` | cpu, memory, custom metrics | Thêm tài liệu về HPA thay đổi số Pod theo CPU, memory và custom metrics. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

V2 dùng retrieval nên trung bình tăng từ **57.3** lên **109.0 token/câu**. p95 của eval tăng từ **198.4** lên **231.4 ms** trong lần chạy này. V2 trả lời đúng nhiều hơn, nên chi phí trên câu đúng giảm từ **$0.00040695** xuống **$0.00003616**. Sau khi bổ sung tài liệu, **23/23** câu đạt và không có regression so với v2 ban đầu. Các lượt eval đặt `MOCK_ERROR_RATE=0` để đo chất lượng câu trả lời, còn load test vẫn bật tỷ lệ lỗi giả lập.

**CI quality gate.** Chạy agent v2 và gọi `python eval/run_eval.py --url http://127.0.0.1:8002 --min-accuracy 0.85 --baseline <baseline-đã-duyệt>.json`. Exit code 1 làm job thất bại nếu accuracy dưới 85% hoặc câu từng đúng bị sai. Đặt job là required status check thì PR phải qua gate mới merge. Đã chạy thử v1 so với baseline v2 ở ngưỡng 85% và nhận exit code 1. Lượt kiểm tra v2 đã sửa dùng ngưỡng 100% với baseline v2 ban đầu và nhận exit code 0.

Số liệu: [`eval_v1.json`](06-lab-complete/benchmark-observability/develop/reports/eval_v1.json), [`eval_v2.json`](06-lab-complete/benchmark-observability/develop/reports/eval_v2.json), [`eval_v2_fixed.json`](06-lab-complete/benchmark-observability/develop/reports/eval_v2_fixed.json).

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] [Dashboard Grafana khi đang có tải](screenshots/grafana-dashboard.png): 15,4 req/s, error rate 20,85%, p95 1,89 giây, 2 instance.
- [x] [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png): span `chat mock-llm-small` chiếm khoảng 1,7 giây.
- [x] [Trace lỗi trong Jaeger](screenshots/jaeger-error-trace.png): HTTP 503 và event `exception`.
- [x] [Trang Alerts của Prometheus](screenshots/prometheus-alert-firing.png): `AgentHighErrorRate` và `AgentHighLatencyP95` đồng thời **firing**.

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (22,17%; đồng thời thấy `LLMCostBurnRateHigh`) | 95,5 giây đến lần quan sát thấy firing | Error rate `/ask` |
| B | Giữ error rate 0,2; đặt `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (1,894 giây); cùng lúc `AgentHighErrorRate` vẫn firing | 143,6 giây đến lần quan sát thấy firing | p95 latency `/ask` |
| C | `LLM_MODEL=mock-llm-large` | Chưa chạy | — | — |
| D | `docker pause` 1 instance | Chưa chạy | — | — |
| E | `AGENT_VERSION=v1` | Chưa chạy; bài yêu cầu giải thích trường hợp metric vận hành vẫn bình thường | — | — |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Theo dõi chất lượng bằng bộ golden dataset và metric accuracy theo phiên bản agent. Chạy eval định kỳ hoặc theo mỗi lần deploy, đặt quality gate trong CI, rồi cảnh báo nếu accuracy giảm hoặc có câu từng đúng bị sai. Latency và tỷ lệ lỗi HTTP không thể hiện được câu trả lời sai về nội dung.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `ba76215685bf2cb87312f7572411e8b9`
- Tổng thời gian: 1720,577 ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (1696,918 ms, 98,6%). Đây là phần chờ mock LLM, phù hợp với thí nghiệm tăng `MOCK_SLOW_RATE`.
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts":"2026-11-26T15:35:47.231153+00:00","level":"INFO","service":"observable-agent","instance":"ef545ec974af","event":"llm_call","trace_id":"ba76215685bf2cb87312f7572411e8b9","span_id":"d7e2a39df0b978e3","request_id":"978ab166db80","model":"mock-llm-small","agent_version":"v2","input_tokens":95,"output_tokens":55,"cost_usd":0.000047,"llm_ms":1696.0}
```

Trace lỗi `e453022ef373896bc7c57048076fff39` có event `exception`; tổng 860,156 ms, span `chat mock-llm-small` 840,654 ms. Log tương ứng có `event=llm_error` và lỗi `Upstream LLM error: 503 Service Unavailable (mock)`. Bản JSON của [trace chậm](benchmark-results/jaeger-slow-trace.json), [trace lỗi](benchmark-results/jaeger-error-trace.json) và [các phép đo CP8](benchmark-results/cp8-observed.json) được lưu cùng repo.

Ở lúc đo dashboard, Prometheus ghi p95 khoảng 291,9 ms và trung bình khoảng 224,4 ms. RPS theo hai instance là 7,73 và 8,09; lưu lượng được chia tương đối đều. Tốc độ token input 1211,0/s cao hơn output 631,7/s, phù hợp với prompt chứa ngữ cảnh retrieval. `/metrics` qua Nginx trả 404 trong cấu hình này; Prometheus scrape trực tiếp agent trên mạng nội bộ.

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 60,04 | 190 | 280 | 1700 | 82/7108 |
| 3 | 59,97 | 190 | 230 | 1700 | 67/7161 |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

Ở tải cố định 100 user trong 2 phút, ba instance cải thiện p95 từ 280 xuống 230 ms (giảm khoảng 17,9%), nhưng throughput vẫn gần 60 RPS. p99 giữ ở 1700 ms vì các request chậm giả lập ở LLM không hết đi khi tăng replica. Tải được áp từ một máy Locust, nên kết quả này cho thấy cải thiện latency ở mức tải đã đo, chưa chứng minh giới hạn throughput tối đa của cụm. Số liệu từ [`scale_1_stats.csv`](06-lab-complete/benchmark-observability/production/benchmark-results/scale_1_stats.csv) và [`scale_3_stats.csv`](06-lab-complete/benchmark-observability/production/benchmark-results/scale_3_stats.csv).

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. So sánh p95/p99 cùng RPS và tỷ lệ lỗi: average thấp vẫn có thể che giấu request chậm.
  2. Trace và log dùng cùng `trace_id` giúp xác định span chậm hoặc lỗi cụ thể; alert chỉ cho biết xu hướng vượt ngưỡng.
  3. Tăng replica cải thiện p95 ở tải cố định, nhưng không loại bỏ độ trễ do mock LLM; phải đo lại ở nhiều mức tải trước khi chọn số replica.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

Thêm metric và alert cho tỷ lệ câu trả lời đạt golden dataset theo phiên bản, độ trễ và lỗi riêng của upstream LLM, cùng queue time nếu có hàng đợi. Theo dõi chi phí/token trên mỗi câu trả lời đúng để phát hiện tăng chi phí khi chất lượng không đổi. Ngưỡng cảnh báo cần hiệu chỉnh từ traffic thật và tránh báo động từ mẫu quá ít.
