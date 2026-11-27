# Deployment Information

## Public URL

https://day14-ai-agent-6shl.onrender.com

## Platform

Render Web Service (Docker) + Render Key Value on the free plans. Blueprint: [06-lab-complete/render.yaml](06-lab-complete/render.yaml).

## Test Commands

Đặt `BASE` là URL public bằng HTTPS. Nhập API key trong terminal qua prompt ẩn trước khi chạy các lệnh này:

```bash
BASE='https://day14-ai-agent-6shl.onrender.com'
read -r -s -p 'Agent API key: ' AGENT_API_KEY
printf '\n'
```

### Health Check

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"  # Expected: 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"   # Expected: 200
```

### API Test (with authentication)

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'  # Expected: 401

curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'  # Expected: 200

unset AGENT_API_KEY
```

### Test Results

| Request | HTTP thực tế |
| --- | --- |
| `GET /health` | 200 |
| `GET /ready` | 200 |
| `POST /ask` thiếu key | 401 |
| `POST /ask` có key | 200 |

## Environment Variables Set

- `PORT` do Render cấp cho web service.
- `ENVIRONMENT=production` qua Blueprint.
- `REDIS_URL` lấy từ connection string nội bộ của Key Value.
- `AGENT_API_KEY` nhập ở Render dashboard.

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [HTTP test results](screenshots/test.png)
