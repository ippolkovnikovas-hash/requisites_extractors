"""
Извлечение текста из .odt (OpenDocument Text) без внешних зависимостей.

ODT — zip-архив, текст лежит в content.xml. Собираем абзацы и заголовки,
строки таблиц склеиваем через " | " — так же, как docx_extractor.
"""

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from loguru import logger

from app.core.enums import ExtractorType
from app.core.exceptions import TextExtractionError
from app.schemas.extraction import TextExtractionResult

_NS = {
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
}
_TEXT = "{%s}" % _NS["text"]
_TABLE = "{%s}" % _NS["table"]


def _node_text(node: ElementTree.Element) -> str:
    """Текст узла с учётом <text:s/> (пробелы), <text:tab/> и <text:line-break/>."""
    parts: list[str] = [node.text or ""]
    for child in node:
        if child.tag == _TEXT + "s":
            parts.append(" " * int(child.get(_TEXT + "c", "1")))
        elif child.tag == _TEXT + "tab":
            parts.append("\t")
        elif child.tag == _TEXT + "line-break":
            parts.append("\n")
        else:
            parts.append(_node_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _walk(node: ElementTree.Element, parts: list[str]) -> None:
    for child in node:
        if child.tag == _TABLE + "table":
            for row in child.iter(_TABLE + "table-row"):
                cells = []
                for cell in row.findall(_TABLE + "table-cell"):
                    cell_text = " ".join(
                        _node_text(p).strip()
                        for p in cell.iter()
                        if p.tag in (_TEXT + "p", _TEXT + "h")
                    ).strip()
                    if cell_text:
                        cells.append(cell_text)
                if cells:
                    parts.append(" | ".join(cells))
        elif child.tag in (_TEXT + "p", _TEXT + "h"):
            text = _node_text(child).strip()
            if text:
                parts.append(text)
        else:
            _walk(child, parts)


def extract_odt(file_path: Path) -> TextExtractionResult:
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(file_path) as archive:
            root = ElementTree.fromstring(archive.read("content.xml"))
    except Exception as e:
        raise TextExtractionError(f"Cannot open ODT: {e}", {"path": str(file_path)})

    parts: list[str] = []
    _walk(root, parts)
    full_text = "\n".join(parts)

    if not full_text.strip():
        warnings.append("ODT extracted text is empty — document may be blank or image-only")

    logger.debug("ODT extraction done", path=file_path.name, chars=len(full_text))
    return TextExtractionResult(
        text=full_text,
        extractor_used=ExtractorType.ODF,
        ocr_used=False,
        warnings=warnings,
    )
