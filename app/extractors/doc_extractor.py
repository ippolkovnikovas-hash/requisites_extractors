"""
Извлечение текста из старого .doc (Word 97-2003).

Формат бинарный, надёжно читается только конвертацией: LibreOffice в headless-режиме
переводит .doc → .docx, дальше работает обычный docx_extractor.
Путь к soffice задаётся LIBREOFFICE_PATH, иначе ищем в PATH и стандартных папках.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from loguru import logger

from app.config import settings
from app.core.enums import ExtractorType
from app.core.exceptions import TextExtractionError
from app.extractors.docx_extractor import extract_docx
from app.schemas.extraction import TextExtractionResult

_DEFAULT_PATHS = (
    Path("C:/Program Files/LibreOffice/program/soffice.exe"),
    Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
    Path("/usr/bin/soffice"),
    Path("/usr/bin/libreoffice"),
    Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
)
_CONVERT_TIMEOUT_SECONDS = 120


def find_soffice() -> str | None:
    if settings.libreoffice_path:
        return settings.libreoffice_path if Path(settings.libreoffice_path).exists() else None
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for path in _DEFAULT_PATHS:
        if path.exists():
            return str(path)
    return None


def extract_doc(file_path: Path) -> TextExtractionResult:
    soffice = find_soffice()
    if not soffice:
        raise TextExtractionError(
            "Cannot read .doc: LibreOffice not found. Install LibreOffice or set LIBREOFFICE_PATH, "
            "or save the document as .docx",
            {"path": str(file_path)},
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "docx", "--outdir", tmp_dir, str(file_path)],
                check=True,
                capture_output=True,
                timeout=_CONVERT_TIMEOUT_SECONDS,
            )
        except (subprocess.SubprocessError, OSError) as e:
            raise TextExtractionError(f"LibreOffice conversion failed: {e}", {"path": str(file_path)})

        converted = Path(tmp_dir) / (file_path.stem + ".docx")
        if not converted.exists():
            raise TextExtractionError("LibreOffice produced no .docx", {"path": str(file_path)})

        result = extract_docx(converted)

    logger.debug("DOC converted via LibreOffice", path=file_path.name, chars=len(result.text))
    return result.model_copy(update={"extractor_used": ExtractorType.LIBREOFFICE})
