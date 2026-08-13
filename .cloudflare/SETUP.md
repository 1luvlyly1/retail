# Cloudflare Access — Bảo vệ app không cần code auth

## Tại sao dùng Cloudflare Access?
- Không cần viết login/logout trong code
- Cloudflare chặn ở tầng DNS trước khi request vào server
- Hỗ trợ Google, Microsoft, GitHub SSO — nhân viên dùng email công ty
- Free plan đủ dùng cho team nhỏ

## Bước 1: Setup Cloudflare Tunnel

```bash
# Cài cloudflared
brew install cloudflare/cloudflare/cloudflared

# Login (mở browser)
cloudflared tunnel login

# Tạo tunnel
cloudflared tunnel create sitevisit-ai

# Lấy tunnel ID từ output, VD: abc123-def456-...
# File credentials tự lưu vào ~/.cloudflared/<tunnel-id>.json
```

## Bước 2: Config tunnel

Tạo file `~/.cloudflared/config.yml`:
```yaml
tunnel: <TUNNEL-ID>
credentials-file: /Users/<USERNAME>/.cloudflared/<TUNNEL-ID>.json

ingress:
  - hostname: sitevisit.congty.com
    service: http://localhost:80
  - service: http_status:404
```

## Bước 3: Route DNS

```bash
# Tạo DNS record tự động
cloudflared tunnel route dns sitevisit-ai sitevisit.congty.com

# Chạy tunnel
cloudflared tunnel run sitevisit-ai
```

## Bước 4: Setup Cloudflare Access (bảo vệ URL)

1. Vào https://one.dash.cloudflare.com
2. **Access → Applications → Add an application**
3. Chọn **Self-hosted**
4. Điền:
   - Application name: Site Visit AI
   - Application domain: `sitevisit.congty.com`
5. **Next → Add a policy**
6. Policy name: `Nhan vien cong ty`
7. Action: **Allow**
8. Rule: **Emails ending in** → `@congty.com`
   (hoặc **Email** → liệt kê từng email cụ thể)
9. **Save**

Từ giờ ai muốn vào `sitevisit.congty.com` phải đăng nhập bằng email `@congty.com`.
Cloudflare lo toàn bộ — app không cần biết gì.

## Bước 5: Auto-start khi Mac Mini khởi động

```bash
# Cài thành service
sudo cloudflared service install

# Hoặc dùng LaunchAgent (không cần sudo)
cloudflared service install --user
```

## Tóm tắt luồng bảo mật

```
Người dùng → sitevisit.congty.com
    ↓
Cloudflare DNS (chặn ở đây)
    ↓ (nếu có email @congty.com)
Cloudflare Tunnel
    ↓
Mac Mini :80 (Nginx)
    ↓
FastAPI / React App
```
