from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import PurePath
from typing import Any, Iterable, Mapping


AUTO_LINK_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.70
SIGNATURE_VERSION = 1

DOCUMENT_ROLES = {
    "briefing_original",
    "cost_sheet",
    "budget_study",
    "final_presentation",
    "feedback",
    "approval",
    "closure_report",
    "post_execution_report",
    "production_file",
    "supplier_reference",
    "gift_presskit_reference",
    "project_document",
    "other",
}

ROLE_LABELS = {
    "briefing_original": "Briefing original",
    "cost_sheet": "Planilha de custos",
    "budget_study": "Estudo preliminar de verba",
    "final_presentation": "Apresentação de proposta",
    "feedback": "Feedback",
    "approval": "Aprovação",
    "closure_report": "Relatório de encerramento",
    "post_execution_report": "Relatório pós-execução",
    "production_file": "Arquivo de produção",
    "supplier_reference": "Fornecedor / referência",
    "gift_presskit_reference": "Brinde / press kit",
    "project_document": "Documento do projeto",
    "other": "Outro arquivo",
}


@dataclass(slots=True)
class ProjectSignals:
    project_name: str | None = None
    client_brand: str | None = None
    event_name: str | None = None
    edition: str | None = None
    reference_year: int | None = None
    event_start: date | None = None
    event_end: date | None = None
    venue_name: str | None = None
    city: str | None = None
    state: str | None = None
    audience_size: int | None = None
    budget_amount: Decimal | None = None
    keywords: tuple[str, ...] = ()
    document_role: str | None = None
    source_file: str | None = None
    raw_signals: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("event_start", "event_end"):
            value = payload.get(key)
            if isinstance(value, date):
                payload[key] = value.isoformat()
        value = payload.get("budget_amount")
        if isinstance(value, Decimal):
            payload["budget_amount"] = str(value)
        payload["keywords"] = list(self.keywords)
        return payload


@dataclass(slots=True)
class MatchResult:
    project_id: str | None
    project_name: str
    score: float
    decision: str
    reasons: list[str]
    conflicts: list[str]
    matched_fields: list[str]
    evidence_count: int
    critical_conflict: bool = False

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


_FIELD_WEIGHTS = {
    "project_name": 0.20,
    "client_brand": 0.15,
    "event_name": 0.15,
    "edition": 0.14,
    "reference_year": 0.08,
    "event_dates": 0.10,
    "venue_name": 0.08,
    "location": 0.03,
    "audience_size": 0.03,
    "budget_amount": 0.04,
}

_STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "br",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "final",
    "para",
    "por",
    "projeto",
    "proposta",
    "the",
    "versao",
    "voe",
}


def normalize_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalized_tokens(value: Any) -> set[str]:
    return {
        token
        for token in normalize_text(value).split()
        if len(token) > 1 and token not in _STOPWORDS
    }


def parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    formats = (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%d-%m-%Y",
        "%d.%m.%Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def parse_integer(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(
            re.sub(r"[^0-9,.-]+", "", str(value))
            .replace(".", "")
            .replace(",", ".")
        )
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return int(round(number))


def parse_money(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None

    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"[^\d,.-]+", "", text)
    if not text:
        return None

    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def extract_edition(*values: Any) -> str | None:
    candidates = " ".join(str(value or "") for value in values)
    normalized = normalize_text(candidates)

    patterns = (
        r"\bplaneja\s*(\d{2,4})\b",
        r"\bedicao\s*(\d{1,4})\b",
        r"\b(?:evento|project)\s*(\d{2})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            raw = match.group(1)
            if len(raw) == 4 and raw.startswith("20"):
                return raw[2:]
            return raw.lstrip("0") or "0"
    return None


def extract_reference_year(*values: Any) -> int | None:
    text = " ".join(str(value or "") for value in values)
    years = [
        int(match)
        for match in re.findall(r"\b20\d{2}\b", normalize_text(text))
    ]
    if not years:
        return None
    return max(years)


def infer_document_role(
    file_name: str | None,
    *,
    mime_type: str | None = None,
    title: str | None = None,
    text_sample: str | None = None,
) -> str:
    name = normalize_text(PurePath(str(file_name or "")).name)
    combined = " ".join(
        filter(
            None,
            [
                name,
                normalize_text(title),
                normalize_text(text_sample),
            ],
        )
    )
    extension = PurePath(str(file_name or "")).suffix.casefold()

    if re.search(r"\bbriefing\b|\bbrief\b", combined):
        return "briefing_original"

    if re.search(
        r"\bestudo\s+de\s+verba\b|\bverba\b|\bbudget\s+study\b",
        combined,
    ):
        return "budget_study"

    if extension in {".xls", ".xlsx", ".csv", ".tsv"} and re.search(
        r"\bcusto\b|\bcustos\b|\borcamento\b|\bfinanceiro\b|\bplanilha\b",
        combined,
    ):
        return "cost_sheet"

    if re.search(
        r"\bfeedback\b|\bcomentarios?\b|\bdevolutiva\b",
        combined,
    ):
        return "feedback"

    if re.search(
        r"\baprovacao\b|\baprovado\b|\bok\s+cliente\b",
        combined,
    ):
        return "approval"

    if re.search(
        r"\bpos\s+evento\b|\bpos\s+execucao\b|\bresultados\b",
        combined,
    ):
        return "post_execution_report"

    if re.search(
        r"\bencerramento\b|\bclosure\b",
        combined,
    ):
        return "closure_report"

    if re.search(
        r"\bfornecedor\b|\bfornecedores\b|\bcotacao\b|\breferencia\b",
        combined,
    ):
        return "supplier_reference"

    if re.search(
        r"\bbrinde\b|\bpress\s*kit\b|\bpresskit\b|\bkit\b",
        combined,
    ):
        return "gift_presskit_reference"

    if extension in {".ppt", ".pptx", ".pdf"} and re.search(
        r"\bproposta\b|\bapresentacao\b|\bideias\b|\bconceito\b",
        combined,
    ):
        return "final_presentation"

    if extension in {".ppt", ".pptx"}:
        return "final_presentation"

    if re.search(
        r"\bproducao\b|\bcronograma\b|\boperacao\b|\brider\b",
        combined,
    ):
        return "production_file"

    if mime_type and "presentation" in mime_type.casefold():
        return "final_presentation"

    return "project_document"


def signals_from_mapping(
    payload: Mapping[str, Any],
    *,
    source_file: str | None = None,
    document_role: str | None = None,
) -> ProjectSignals:
    raw_project_name = (
        payload.get("project_name")
        or payload.get("name")
        or payload.get("title")
    )
    client_brand = (
        payload.get("client_brand")
        or payload.get("client")
        or payload.get("brand")
    )
    event_name = (
        payload.get("event_name")
        or payload.get("event")
        or payload.get("project_event")
    )
    venue_name = (
        payload.get("venue_name")
        or payload.get("venue")
        or payload.get("location_name")
        or payload.get("local")
    )

    edition = (
        str(payload.get("edition") or "").strip()
        or extract_edition(raw_project_name, event_name, source_file)
    )
    reference_year = (
        parse_integer(payload.get("reference_year"))
        or extract_reference_year(
            raw_project_name,
            event_name,
            payload.get("event_start"),
            payload.get("event_end"),
            source_file,
        )
    )

    keywords_value = payload.get("keywords") or ()
    if isinstance(keywords_value, str):
        keywords = tuple(
            item.strip()
            for item in re.split(r"[,;|]", keywords_value)
            if item.strip()
        )
    else:
        keywords = tuple(
            str(item).strip()
            for item in keywords_value
            if str(item).strip()
        )

    return ProjectSignals(
        project_name=str(raw_project_name).strip() if raw_project_name else None,
        client_brand=str(client_brand).strip() if client_brand else None,
        event_name=str(event_name).strip() if event_name else None,
        edition=edition or None,
        reference_year=reference_year,
        event_start=parse_date(
            payload.get("event_start")
            or payload.get("start_date")
            or payload.get("event_date_start")
        ),
        event_end=parse_date(
            payload.get("event_end")
            or payload.get("end_date")
            or payload.get("event_date_end")
        ),
        venue_name=str(venue_name).strip() if venue_name else None,
        city=str(payload.get("city") or "").strip() or None,
        state=str(payload.get("state") or "").strip() or None,
        audience_size=parse_integer(
            payload.get("audience_size")
            or payload.get("participants")
            or payload.get("pax")
        ),
        budget_amount=parse_money(
            payload.get("budget_amount")
            or payload.get("budget")
            or payload.get("estimated_budget")
        ),
        keywords=keywords,
        document_role=(
            document_role
            or str(payload.get("document_role") or "").strip()
            or None
        ),
        source_file=source_file,
        raw_signals=dict(payload),
    )


def _string_similarity(first: Any, second: Any) -> float:
    left = normalize_text(first)
    right = normalize_text(second)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0

    left_compact = left.replace(" ", "")
    right_compact = right.replace(" ", "")
    if left_compact == right_compact:
        return 1.0
    if left_compact in right_compact or right_compact in left_compact:
        return 0.95

    left_tokens = normalized_tokens(left)
    right_tokens = normalized_tokens(right)
    token_score = 0.0
    if left_tokens and right_tokens:
        token_score = len(left_tokens & right_tokens) / len(
            left_tokens | right_tokens
        )

    sequence_score = SequenceMatcher(None, left, right).ratio()
    containment = 0.92 if left in right or right in left else 0.0
    return max(token_score, sequence_score, containment)


def _numeric_similarity(
    first: int | Decimal | None,
    second: int | Decimal | None,
    *,
    tight: float,
    loose: float,
) -> float:
    if first is None or second is None:
        return 0.0
    left = float(first)
    right = float(second)
    denominator = max(abs(left), abs(right), 1.0)
    difference = abs(left - right) / denominator
    if difference <= tight:
        return 1.0
    if difference <= loose:
        return 0.60
    return 0.0


def _date_similarity(
    incoming: ProjectSignals,
    candidate: ProjectSignals,
) -> float:
    pairs = [
        (incoming.event_start, candidate.event_start),
        (incoming.event_end, candidate.event_end),
    ]
    available = [
        (left, right)
        for left, right in pairs
        if left is not None and right is not None
    ]
    if not available:
        return 0.0

    scores = []
    for left, right in available:
        days = abs((left - right).days)
        if days == 0:
            scores.append(1.0)
        elif days <= 3:
            scores.append(0.85)
        elif days <= 14:
            scores.append(0.50)
        else:
            scores.append(0.0)
    return sum(scores) / len(scores)


def _location_similarity(
    incoming: ProjectSignals,
    candidate: ProjectSignals,
) -> float:
    scores = []
    if incoming.city and candidate.city:
        scores.append(_string_similarity(incoming.city, candidate.city))
    if incoming.state and candidate.state:
        scores.append(_string_similarity(incoming.state, candidate.state))
    return sum(scores) / len(scores) if scores else 0.0


def _record_reason(
    *,
    label: str,
    similarity: float,
    reasons: list[str],
    matched_fields: list[str],
) -> None:
    if similarity >= 0.80:
        reasons.append(f"{label} coincidente")
        matched_fields.append(label)


def compare_project_signals(
    incoming: ProjectSignals,
    candidate: ProjectSignals,
    *,
    project_id: str | None = None,
    project_label: str | None = None,
) -> MatchResult:
    similarities = {
        "project_name": _string_similarity(
            incoming.project_name,
            candidate.project_name,
        ),
        "client_brand": _string_similarity(
            incoming.client_brand,
            candidate.client_brand,
        ),
        "event_name": _string_similarity(
            incoming.event_name,
            candidate.event_name,
        ),
        "edition": (
            1.0
            if normalize_text(incoming.edition)
            and normalize_text(incoming.edition)
            == normalize_text(candidate.edition)
            else 0.0
        ),
        "reference_year": (
            1.0
            if incoming.reference_year
            and incoming.reference_year == candidate.reference_year
            else 0.0
        ),
        "event_dates": _date_similarity(incoming, candidate),
        "venue_name": _string_similarity(
            incoming.venue_name,
            candidate.venue_name,
        ),
        "location": _location_similarity(incoming, candidate),
        "audience_size": _numeric_similarity(
            incoming.audience_size,
            candidate.audience_size,
            tight=0.05,
            loose=0.15,
        ),
        "budget_amount": _numeric_similarity(
            incoming.budget_amount,
            candidate.budget_amount,
            tight=0.05,
            loose=0.20,
        ),
    }

    score = sum(
        _FIELD_WEIGHTS[field] * similarity
        for field, similarity in similarities.items()
    )
    reasons: list[str] = []
    conflicts: list[str] = []
    matched_fields: list[str] = []

    labels = {
        "project_name": "nome do projeto",
        "client_brand": "cliente/marca",
        "event_name": "nome do evento",
        "edition": "edição",
        "reference_year": "ano de referência",
        "event_dates": "datas",
        "venue_name": "local",
        "location": "cidade/estado",
        "audience_size": "público",
        "budget_amount": "budget",
    }
    for field_name, similarity in similarities.items():
        _record_reason(
            label=labels[field_name],
            similarity=similarity,
            reasons=reasons,
            matched_fields=matched_fields,
        )

    critical_conflict = False

    if (
        incoming.client_brand
        and candidate.client_brand
        and similarities["client_brand"] < 0.45
    ):
        conflicts.append("cliente/marca divergente")
        score -= 0.25
        critical_conflict = True

    if (
        incoming.edition
        and candidate.edition
        and similarities["edition"] == 0
    ):
        conflicts.append(
            f"edição divergente: {incoming.edition} × {candidate.edition}"
        )
        score -= 0.30
        critical_conflict = True

    if (
        incoming.reference_year
        and candidate.reference_year
        and similarities["reference_year"] == 0
    ):
        conflicts.append(
            "ano de referência divergente: "
            f"{incoming.reference_year} × {candidate.reference_year}"
        )
        score -= 0.20
        critical_conflict = True

    if (
        incoming.event_start
        and candidate.event_start
        and abs((incoming.event_start - candidate.event_start).days) > 45
    ):
        conflicts.append("datas do evento incompatíveis")
        score -= 0.15

    score = max(0.0, min(1.0, score))
    evidence_count = sum(
        1 for similarity in similarities.values() if similarity >= 0.60
    )

    if (
        score >= AUTO_LINK_THRESHOLD
        and evidence_count >= 4
        and not critical_conflict
    ):
        decision = "auto_link"
    elif (
        score >= REVIEW_THRESHOLD
        and evidence_count >= 3
        and not critical_conflict
    ):
        decision = "review"
    else:
        decision = "unmatched"

    label = (
        project_label
        or candidate.project_name
        or candidate.event_name
        or "Projeto sem nome"
    )

    return MatchResult(
        project_id=project_id,
        project_name=label,
        score=round(score, 5),
        decision=decision,
        reasons=reasons,
        conflicts=conflicts,
        matched_fields=matched_fields,
        evidence_count=evidence_count,
        critical_conflict=critical_conflict,
    )


def rank_project_matches(
    incoming: ProjectSignals,
    projects: Iterable[
        tuple[str | None, str, ProjectSignals]
        | Mapping[str, Any]
    ],
    *,
    limit: int = 5,
) -> list[MatchResult]:
    results: list[MatchResult] = []

    for item in projects:
        if isinstance(item, Mapping):
            project_id = (
                str(item.get("project_id") or item.get("id") or "").strip()
                or None
            )
            label = str(
                item.get("project_name")
                or item.get("event_name")
                or "Projeto sem nome"
            )
            candidate = signals_from_mapping(item)
        else:
            project_id, label, candidate = item

        results.append(
            compare_project_signals(
                incoming,
                candidate,
                project_id=project_id,
                project_label=label,
            )
        )

    results.sort(
        key=lambda result: (
            result.score,
            result.evidence_count,
        ),
        reverse=True,
    )
    return results[: max(1, limit)]


def merge_project_signals(
    signals: Iterable[ProjectSignals],
) -> ProjectSignals:
    items = list(signals)
    if not items:
        return ProjectSignals()

    def most_informative(field_name: str):
        values = [
            getattr(item, field_name)
            for item in items
            if getattr(item, field_name) not in (None, "", (), [])
        ]
        if not values:
            return None
        return max(values, key=lambda value: len(str(value)))

    keyword_set: list[str] = []
    seen: set[str] = set()
    for item in items:
        for keyword in item.keywords:
            normalized = normalize_text(keyword)
            if normalized and normalized not in seen:
                seen.add(normalized)
                keyword_set.append(keyword)

    return ProjectSignals(
        project_name=most_informative("project_name"),
        client_brand=most_informative("client_brand"),
        event_name=most_informative("event_name"),
        edition=most_informative("edition"),
        reference_year=most_informative("reference_year"),
        event_start=most_informative("event_start"),
        event_end=most_informative("event_end"),
        venue_name=most_informative("venue_name"),
        city=most_informative("city"),
        state=most_informative("state"),
        audience_size=most_informative("audience_size"),
        budget_amount=most_informative("budget_amount"),
        keywords=tuple(keyword_set),
        document_role=None,
        source_file=None,
        raw_signals={
            "merged_sources": [
                item.to_payload()
                for item in items
            ]
        },
    )
