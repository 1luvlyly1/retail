from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import structlog
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from app.core.config import settings

logger = structlog.get_logger(__name__)
SCOPES = ["https://www.googleapis.com/auth/drive"]


def _service():
    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _get_or_create_folder(svc, name: str, parent_id: Optional[str] = None) -> str:
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    res = svc.files().list(q=q, fields="files(id)").execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]
    f = svc.files().create(body=meta, fields="id").execute()
    return f["id"]


def _upload_sync(file_path: Path, filename: str, company_id: str, visit_date: str) -> Dict:
    svc = _service()

    root_id = settings.GOOGLE_DRIVE_ROOT_FOLDER_ID or \
        _get_or_create_folder(svc, settings.GOOGLE_DRIVE_ROOT_FOLDER_NAME)
    company_folder = _get_or_create_folder(svc, company_id, root_id)
    date_folder = _get_or_create_folder(svc, visit_date, company_folder)

    ts = datetime.now().strftime("%H%M%S")
    drive_name = f"{ts}_{filename}"

    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".heic": "image/heic", ".webp": "image/webp"}
    mime = mime_map.get(file_path.suffix.lower(), "image/jpeg")

    uploaded = svc.files().create(
        body={"name": drive_name, "parents": [date_folder]},
        media_body=MediaFileUpload(str(file_path), mimetype=mime, resumable=True),
        fields="id, webViewLink",
    ).execute()

    folder_path = f"{settings.GOOGLE_DRIVE_ROOT_FOLDER_NAME}/{company_id}/{visit_date}"
    logger.info("Uploaded to Drive", file_id=uploaded["id"], path=folder_path)
    return {
        "file_id": uploaded["id"],
        "web_view_url": uploaded.get("webViewLink", ""),
        "folder_path": folder_path,
    }


async def upload_to_gdrive(file_path: Path, filename: str, company_id: str, visit_date: str) -> Dict:
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _upload_sync, file_path, filename, company_id, visit_date)
    except HttpError as exc:
        logger.error("Drive upload failed", error=str(exc))
    except Exception as exc:
        logger.error("Drive error", error=str(exc))
    return {"file_id": "", "web_view_url": "", "folder_path": "", "error": "upload failed"}
