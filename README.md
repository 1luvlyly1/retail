# Site Visit AI Assistant

Ứng dụng hỗ trợ nhân viên khảo sát hiện trường: chụp ảnh, chat với AI để bổ sung thông tin, tra cứu công ty và xuất báo cáo.

## Kiến trúc

```
                       ┌──────────────┐
                       │    Nginx     │
                       └──────┬───────┘
                              │
                   ┌──────────┴──────────┐
                   │                     │
            ┌──────▼──────┐      ┌───────▼───────┐
            │  Frontend   │      │    Backend     │
            │ React+Vite  │      │   FastAPI      │
            └─────────────┘      └───────┬────────┘
                                          │
                    ┌─────────────┬───────┴───────┬──────────────┐
                    │             │                │              │
             ┌──────▼─────┐ ┌─────▼─────┐  ┌───────▼──────┐ ┌────▼─────┐
             │ PostgreSQL │ │   Redis   │  │ Celery Worker │ │  AI APIs │
             │            │ │(broker/   │  │ (xử lý ảnh,   │ │ Claude / │
             │            │ │ cache)    │  │  enrichment)  │ │ GPT-4 /  │
             └────────────┘ └───────────┘  └───────┬───────┘ │ Tavily   │
                                                     │         └──────────┘
                                            ┌────────▼────────┐
                                            │ Local disk /     │
                                            │ Google Drive     │
                                            └──────────────────┘
```

- **Backend:** FastAPI (async) + SQLAlchemy + Alembic — REST API và WebSocket
- **Celery + Redis:** xử lý ảnh và enrichment chạy nền, tách khỏi request chính
- **Frontend:** React + Vite, giao tiếp qua REST + WebSocket
- **Lưu ảnh:** local disk hoặc Google Drive (tuỳ chọn qua service account)
- **Nginx:** reverse proxy, serve frontend build + route API/WS tới backend

```
backend/    FastAPI app (api, services, models, workers)
frontend/   React app
docker/     Dockerfile phụ trợ, init.sql
nginx/      Nginx config
scripts/    setup.sh
```

## Chạy nhanh

```bash
cp .env.example .env   # điền ANTHROPIC_API_KEY, OPENAI_API_KEY, TAVILY_API_KEY
./scripts/setup.sh
```

API: `localhost:8000` · Docs: `localhost:8000/api/docs` · Frontend: `localhost:80`

## Tuỳ chọn khác

- **Google Drive:** tạo service account trên Google Cloud, lưu key vào `docker/google-credentials.json`, điền `GOOGLE_DRIVE_ROOT_FOLDER_ID` trong `.env`.
- **Cloudflare Access:** dùng `cloudflared tunnel` + Cloudflare Zero Trust để bảo vệ URL bằng SSO công ty, không cần code auth.
- **Biến môi trường đầy đủ:** xem [.env.example](.env.example).
