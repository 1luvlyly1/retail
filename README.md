# Site Visit AI Assistant

Ứng dụng hỗ trợ nhân viên khảo sát hiện trường (site visit): chụp ảnh, chat với AI để bổ sung thông tin, tra cứu công ty và xuất báo cáo.

## Tech stack

- **Backend:** FastAPI + SQLAlchemy (async) + Alembic, Celery + Redis cho xử lý ảnh nền
- **Frontend:** React + Vite + Tailwind CSS
- **DB:** PostgreSQL
- **AI:** Anthropic Claude, OpenAI GPT-4, Tavily Search
- **Lưu trữ ảnh:** Local disk hoặc Google Drive
- **Hạ tầng:** Docker Compose, Nginx

## Cấu trúc

```
backend/    FastAPI app (api, services, models, workers)
frontend/   React app
docker/     Dockerfile phụ trợ, init.sql
nginx/      Nginx config
scripts/    setup.sh — script cài đặt tự động
```

## Chạy nhanh

```bash
cp .env.example .env   # điền ANTHROPIC_API_KEY, OPENAI_API_KEY, TAVILY_API_KEY
./scripts/setup.sh
```

Script sẽ khởi động Postgres, Redis, chạy migration, và bật toàn bộ services qua Docker Compose.

- API: http://localhost:8000
- API docs: http://localhost:8000/api/docs
- Frontend: http://localhost:80

## Google Drive (tuỳ chọn — lưu ảnh trên Drive thay vì local)

1. Tạo Google Cloud Project → bật **Google Drive API**
2. Tạo **Service Account** → tải file JSON key
3. Lưu vào `docker/google-credentials.json`
4. Tạo folder trên Drive, share cho email service account (role Editor)
5. Điền `GOOGLE_DRIVE_ROOT_FOLDER_ID` trong `.env`

## Cloudflare Access (tuỳ chọn — bảo vệ URL không cần code auth)

Dùng Cloudflare Tunnel + Access để chặn truy cập ở tầng DNS, yêu cầu đăng nhập bằng email công ty (Google/Microsoft/GitHub SSO) mà không cần viết login trong app.

```bash
brew install cloudflare/cloudflare/cloudflared
cloudflared tunnel login
cloudflared tunnel create sitevisit-ai
cloudflared tunnel route dns sitevisit-ai <your-domain>
cloudflared tunnel run sitevisit-ai
```

Sau đó vào [Cloudflare Zero Trust dashboard](https://one.dash.cloudflare.com) → **Access → Applications** → tạo policy giới hạn theo domain email.

## Biến môi trường

Xem [.env.example](.env.example) để biết đầy đủ danh sách.
