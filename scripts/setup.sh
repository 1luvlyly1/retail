#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()   { echo -e "${GREEN}[OK]${NC}    $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()  { echo -e "${RED}[ERR]${NC}   $1"; exit 1; }

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║    Site Visit AI — Phase 1 Setup         ║"
echo "╚══════════════════════════════════════════╝"
echo ""

command -v docker >/dev/null 2>&1 || err "Docker không tìm thấy. Cài Docker Desktop."

# .env
if [ ! -f ".env" ]; then
    cp .env.example .env
    warn ".env đã tạo — điền API keys trước khi tiếp tục:"
    warn "  ANTHROPIC_API_KEY, OPENAI_API_KEY, TAVILY_API_KEY"
    echo ""
    read -p "Nhấn Enter sau khi điền .env..." || true
fi
ok ".env sẵn sàng"

# Dirs
mkdir -p /tmp/sitevisit/{uploads,skills,reports}
mkdir -p frontend/dist
ok "Thư mục tạo xong"

# Google credentials placeholder
if [ ! -f "docker/google-credentials.json" ]; then
    warn "Thiếu docker/google-credentials.json"
    warn "Xem hướng dẫn: README.md"
    echo '{"type":"service_account","placeholder":true}' > docker/google-credentials.json
fi

# Start DB + Redis
log "Khởi động PostgreSQL + Redis..."
docker compose up -d postgres redis

log "Chờ PostgreSQL..."
timeout 60 bash -c 'until docker compose exec postgres pg_isready -U sitevisit -d sitevisit_db 2>/dev/null; do sleep 2; done'
ok "PostgreSQL sẵn sàng"

# Migrations
log "Chạy migrations..."
docker compose run --rm backend sh -c "
  cd /app && python -m alembic upgrade head
" && ok "Migrations OK" || warn "Migration lỗi — kiểm tra logs"

# Start all services
log "Khởi động tất cả services..."
docker compose up -d

sleep 5
curl -sf http://localhost:8000/health >/dev/null && ok "Backend đang chạy" || warn "Backend chưa sẵn sàng — thử lại sau"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║             Setup hoàn tất!              ║"
echo "╠══════════════════════════════════════════╣"
echo "║  API:      http://localhost:8000         ║"
echo "║  Docs:     http://localhost:8000/api/docs║"
echo "║  Frontend: http://localhost:80           ║"
echo "║                                          ║"
echo "║  Logs: docker compose logs -f            ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Cloudflare Tunnel & Google Drive: xem README.md"
