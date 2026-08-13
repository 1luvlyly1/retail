# Google Drive Service Account Setup

## Bước 1: Tạo Google Cloud Project
1. https://console.cloud.google.com → New Project → đặt tên `SiteVisitAI`

## Bước 2: Enable Drive API
Menu → APIs & Services → Library → "Google Drive API" → Enable

## Bước 3: Tạo Service Account
1. APIs & Services → Credentials → Create Credentials → Service Account
2. Name: `sitevisit-gdrive` → Done

## Bước 4: Tải JSON key
Click service account → Keys → Add Key → JSON → Download

## Bước 5: Đặt file vào project
```bash
cp ~/Downloads/sitevisitai-xxx.json docker/google-credentials.json
```

## Bước 6: Chia sẻ folder Drive
1. Tạo folder **SiteVisit** trên Drive
2. Share với email service account (VD: `sitevisit-gdrive@sitevisitai.iam.gserviceaccount.com`)
3. Role: Editor
4. Copy folder ID từ URL vào `.env`:
   ```
   GOOGLE_DRIVE_ROOT_FOLDER_ID=1ABC123XYZ
   ```
