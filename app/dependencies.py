from pathlib import Path

from flask import Request, abort

from app.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


def validate_upload(request: Request) -> tuple[bytes, str]:
    if "file" not in request.files:
        abort(400, description="No file part in request")

    file = request.files["file"]
    if not file.filename:
        abort(400, description="Empty filename")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        abort(400, description=f"Unsupported file type: {ext}. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

    data = file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        abort(413, description=f"File size {len(data)} bytes exceeds limit {max_bytes} bytes")

    return data, file.filename
