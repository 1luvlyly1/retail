"""
Local Storage Service — thay thế Google Drive.
Lưu ảnh trực tiếp trên Mac Mini, serve qua Nginx static files.

Cấu trúc thư mục:
  /data/sitevisit/photos/{company_id}/{visit_date}/{timestamp}_{filename}

URL truy cập (qua Nginx):
  https://your-domain.com/media/{company_id}/{visit_date}/{timestamp}_{filename}
"""
from __future__ import annotations

import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


def _copy_sync(file_path: Path, filename: str, company_id: str, visit_date: str) -> Dict[str, str]:
    """Copy file vào thư mục lưu trữ vĩnh viễn, trả về đường dẫn + URL."""
    dest_dir = settings.MEDIA_ROOT / company_id / visit_date
    dest_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%H%M%S")
    dest_filename = f"{ts}_{filename}"
    dest_path = dest_dir / dest_filename

    # Nếu trùng tên (hiếm khi cùng giây), thêm suffix
    counter = 1
    while dest_path.exists():
        dest_filename = f"{ts}_{counter}_{filename}"
        dest_path = dest_dir / dest_filename
        counter += 1

    shutil.copy2(file_path, dest_path)

    relative_path = f"{company_id}/{visit_date}/{dest_filename}"
    public_url = f"{settings.MEDIA_URL_PREFIX}/{relative_path}"

    logger.info("Photo saved locally", path=str(dest_path), url=public_url)

    return {
        "file_id": relative_path,        # dùng relative_path làm "id" thay cho gdrive_file_id
        "web_view_url": public_url,
        "folder_path": str(dest_dir),
        "local_path": str(dest_path),
    }


async def save_photo_locally(
    file_path: Path,
    filename: str,
    company_id: str,
    visit_date: str,
) -> Dict[str, str]:
    """
    Async wrapper — copy ảnh vào thư mục lưu trữ vĩnh viễn trên Mac Mini.
    Trả về dict tương thích với format cũ của gdrive (file_id, web_view_url, folder_path).
    """
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, _copy_sync, file_path, filename, company_id, visit_date
        )
    except Exception as exc:
        logger.error("Local save failed", error=str(exc), filename=filename)
        return {
            "file_id": "",
            "web_view_url": "",
            "folder_path": "",
            "local_path": "",
            "error": str(exc),
        }


def delete_photo_locally(relative_path: str) -> bool:
    """Xóa file ảnh khỏi storage (dùng khi xóa visit/photo)."""
    try:
        full_path = settings.MEDIA_ROOT / relative_path
        if full_path.exists():
            full_path.unlink()
            return True
    except Exception as exc:
        logger.error("Delete failed", error=str(exc), path=relative_path)
    return False
