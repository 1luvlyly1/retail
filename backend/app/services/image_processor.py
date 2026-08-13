from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import structlog
from PIL import Image, ExifTags

logger = structlog.get_logger(__name__)


def resize_image_if_needed(file_path: Path, max_size_bytes: int) -> Tuple[Path, bool]:
    if file_path.stat().st_size <= max_size_bytes:
        return file_path, False

    try:
        with Image.open(file_path) as img:
            out_path = file_path.with_stem(file_path.stem + "_r").with_suffix(".jpg")
            exif = img.info.get("exif", b"")

            if max(img.size) > 4096:
                img.thumbnail((4096, 4096), Image.LANCZOS)
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")

            quality = 90
            while quality >= 50:
                kw = {"format": "JPEG", "quality": quality, "optimize": True}
                if exif:
                    kw["exif"] = exif
                img.save(out_path, **kw)
                if out_path.stat().st_size <= max_size_bytes:
                    break
                quality -= 10

            return out_path, True
    except Exception as exc:
        logger.error("Resize failed", error=str(exc))
        return file_path, False


def extract_exif_datetime(file_path: Path) -> Optional[datetime]:
    try:
        with Image.open(file_path) as img:
            exif_data = img._getexif()
            if not exif_data:
                return None
            exif = {ExifTags.TAGS.get(t, t): v for t, v in exif_data.items()}
            for field in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
                if dt := exif.get(field):
                    try:
                        return datetime.strptime(dt, "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        continue
    except Exception:
        pass
    return None
