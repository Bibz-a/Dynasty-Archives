from __future__ import annotations

import os
import shutil
from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename

# Local backup copies of admin uploads (project `images/` remains the canonical web path).
LOCAL_STATIC_IMAGE_DIR = Path(__file__).resolve().parent / "static" / "images"

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2MB

MIME_MAP = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


class UploadError(RuntimeError):
    pass


def save_image_local_path(file, folder: str) -> str:
    """
    Save an uploaded image into project images/<folder>/ and return local path.

    Returned path is web-ready and stored as /images/<folder>/<filename>.
    """
    filename = getattr(file, "filename", "") or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadError(f"File type '.{ext}' not allowed. Use jpg, jpeg, png, or webp.")

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_SIZE_BYTES:
        raise UploadError(f"File too large ({size // 1024}KB). Maximum is 2MB.")

    root_dir = Path(__file__).resolve().parent.parent
    safe_folder = secure_filename(folder or "misc").strip() or "misc"
    target_dir = root_dir / "images" / safe_folder
    target_dir.mkdir(parents=True, exist_ok=True)

    stem = secure_filename(Path(filename).stem) or "image"
    unique_name = f"{stem}_{uuid4().hex[:8]}.{ext}"
    target_file = target_dir / unique_name

    file.seek(0)
    file.save(str(target_file))

    backup_dir = LOCAL_STATIC_IMAGE_DIR / safe_folder
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / unique_name
    shutil.copy2(target_file, backup_file)

    return f"/images/{safe_folder}/{unique_name}"

