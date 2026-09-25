"""
Замер точности извлечения по эталону (ground truth).

Формат эталона — JSON {имя_файла: {поле: значение}}:
  - null  — значение ещё не проверено человеком, поле не учитывается в метриках;
  - ""    — поля в документе нет, правильный ответ — пусто;
  - строка — ожидаемое значение.
Ключи, начинающиеся с "_", игнорируются (комментарии).

Сравнение нестрогое: для чисел — только цифры, для текста — без регистра,
кавычек, лишних пробелов и «ё/е».
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.schemas.requisites import RequisitesData

FIELDS: tuple[str, ...] = tuple(RequisitesData.model_fields.keys())
NUMERIC_FIELDS = frozenset(
    {"inn", "kpp", "ogrn", "bik", "checking_account", "correspondent_account"}
)
_QUOTES_RE = re.compile(r"[«»\"'“”„`]")


def normalize_value(field_name: str, value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""

    if field_name in NUMERIC_FIELDS:
        return re.sub(r"\D", "", text)

    if field_name == "phone":
        phones = []
        for part in re.split(r"[,;]", text):
            digits = re.sub(r"\D", "", part)
            if len(digits) == 11 and digits[0] == "8":
                digits = "7" + digits[1:]
            if digits:
                phones.append(digits)
        return ",".join(sorted(set(phones)))

    if field_name == "email":
        return text.lower().replace(" ", "")

    text = text.lower().replace("ё", "е")
    text = _QUOTES_RE.sub("", text)
    if field_name == "ceo_fio":
        text = text.replace(" ", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .,;:")


def values_match(field_name: str, expected, actual) -> bool:
    return normalize_value(field_name, expected) == normalize_value(field_name, actual)


@dataclass
class DocumentEvaluation:
    file_name: str
    doc_type: str
    # поле → True/False; поля с expected=null отсутствуют
    fields: dict[str, bool] = field(default_factory=dict)
    error: str | None = None

    @property
    def correct(self) -> int:
        return sum(self.fields.values())

    @property
    def total(self) -> int:
        return len(self.fields)


def evaluate_document(
    file_name: str, doc_type: str, expected: dict, actual: dict | None, error: str | None = None
) -> DocumentEvaluation:
    result = DocumentEvaluation(file_name=file_name, doc_type=doc_type, error=error)
    for name in FIELDS:
        exp = expected.get(name)
        if exp is None:
            continue
        result.fields[name] = actual is not None and values_match(name, exp, actual.get(name))
    return result


@dataclass
class Score:
    correct: int = 0
    total: int = 0

    def add(self, ok: bool) -> None:
        self.correct += int(ok)
        self.total += 1

    @property
    def rate(self) -> float | None:
        return round(self.correct / self.total, 3) if self.total else None


@dataclass
class EvaluationSummary:
    by_field: dict[str, Score]
    by_doc_type: dict[str, Score]
    overall: Score
    documents: list[DocumentEvaluation]

    def to_dict(self) -> dict:
        def s(score: Score) -> dict:
            return {"correct": score.correct, "total": score.total, "rate": score.rate}

        return {
            "overall": s(self.overall),
            "by_field": {k: s(v) for k, v in self.by_field.items()},
            "by_doc_type": {k: s(v) for k, v in self.by_doc_type.items()},
            "documents": [
                {
                    "file_name": d.file_name,
                    "doc_type": d.doc_type,
                    "correct": d.correct,
                    "total": d.total,
                    "error": d.error,
                }
                for d in self.documents
            ],
        }


def summarize(documents: list[DocumentEvaluation]) -> EvaluationSummary:
    by_field = {name: Score() for name in FIELDS}
    by_doc_type: dict[str, Score] = {}
    overall = Score()
    for doc in documents:
        type_score = by_doc_type.setdefault(doc.doc_type, Score())
        for name, ok in doc.fields.items():
            by_field[name].add(ok)
            type_score.add(ok)
            overall.add(ok)
    return EvaluationSummary(
        by_field={k: v for k, v in by_field.items() if v.total},
        by_doc_type=by_doc_type,
        overall=overall,
        documents=documents,
    )


def load_ground_truth(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, dict)}


def init_ground_truth(path: Path, file_names: list[str]) -> int:
    """
    Создаёт или дополняет эталон пустыми записями (все поля null) для новых файлов.
    Уже заполненные значения не трогает. Возвращает число добавленных файлов.
    """
    data: dict = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault(
        "_readme",
        "null — не проверено (не учитывается); \"\" — поля в документе нет; "
        "строка — правильное значение. Поля: " + ", ".join(FIELDS),
    )
    added = 0
    for name in file_names:
        if name not in data:
            data[name] = {f: None for f in FIELDS}
            added += 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return added
