from __future__ import annotations

import base64
import io
import math
import os
import re
import unicodedata
from pathlib import Path
from typing import Type, TypeVar

import pandas as pd

from google import genai
from pydantic import BaseModel

from document_io import InputDocument, split_pdf
from models import (
    ActivationBatch,
    ActivationFallbackBatch,
    CatalogBatch,
    DocumentClassification,
    ProjectBriefing,
    RecommendationBrief,
    SupplierContact,
    VenueBatch,
    VenueSpace,
)
from prompts import (
    ACTIVATION_FALLBACK_PROMPT,
    ACTIVATION_SYSTEM_PROMPT,
    BRIEFING_SYSTEM_PROMPT,
    CATALOG_SYSTEM_PROMPT,
    CLASSIFICATION_SYSTEM_PROMPT,
    RECOMMENDATION_BRIEF_PROMPT,
    VENUE_SYSTEM_PROMPT,
)


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class GeminiQuotaError(RuntimeError):
    """Friendly error for Gemini 429 / quota exhaustion."""

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.model = model


def _quota_retry_seconds(message: str) -> int | None:
    patterns = [
        r"retry in\s+([0-9]+(?:\.[0-9]+)?)s",
        r"retryDelay[^0-9]*([0-9]+(?:\.[0-9]+)?)",
        r"retry after\s+([0-9]+(?:\.[0-9]+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return max(1, int(float(match.group(1)) + 0.999))
    return None


def _is_quota_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    signals = (
        "ratelimiterror",
        "too_many_requests",
        "resource_exhausted",
        "quota exceeded",
        "exceeded your current quota",
        "error code: 429",
        "code': 429",
        '"code": 429',
    )
    return any(signal in text for signal in signals)


def get_client(api_key: str | None = None) -> genai.Client:
    resolved = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved:
        raise RuntimeError(
            "Configure GEMINI_API_KEY nos Secrets do Streamlit."
        )
    return genai.Client(
        api_key=resolved,
        http_options={"api_version": "v1"},
    )


def _input_item(doc: InputDocument) -> dict:
    if doc.mime_type.startswith("text/"):
        return {
            "type": "text",
            "text": (
                f"\n\n===== FONTE: {doc.name} =====\n"
                + doc.data.decode("utf-8", errors="replace")
            ),
        }
    return {
        "type": "document",
        "data": base64.b64encode(doc.data).decode("utf-8"),
        "mime_type": doc.mime_type,
    }


def _structured_call(
    client: genai.Client,
    *,
    model: str,
    prompt: str,
    docs: list[InputDocument],
    schema: Type[SchemaT],
    context: str,
) -> SchemaT:
    try:
        interaction = client.interactions.create(
            model=model,
            input=[
                {"type": "text", "text": prompt},
                *[_input_item(doc) for doc in docs],
            ],
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": schema.model_json_schema(),
            },
        )
    except Exception as exc:
        if _is_quota_error(exc):
            retry_after = _quota_retry_seconds(str(exc))
            wait_text = (
                f" Aguarde aproximadamente {retry_after} segundos."
                if retry_after
                else " Aguarde um pouco antes de tentar novamente."
            )
            raise GeminiQuotaError(
                "O limite temporário do Gemini foi atingido."
                + wait_text,
                retry_after_seconds=retry_after,
                model=model,
            ) from exc
        raise
    if not interaction.output_text:
        raise RuntimeError(f"O Gemini não devolveu conteúdo para {context}.")
    try:
        return schema.model_validate_json(interaction.output_text)
    except Exception as exc:
        raise RuntimeError(
            f"Estrutura inválida devolvida para {context}: {exc}"
        ) from exc


def _classification_sample(
    docs: list[InputDocument],
) -> list[InputDocument]:
    sampled: list[InputDocument] = []
    for doc in docs:
        if doc.mime_type == "application/pdf":
            parts = split_pdf(
                doc,
                pages_per_batch=6,
                start_page=1,
                end_page=6,
            )
            if parts:
                sampled.append(parts[0][0])
        else:
            chunks = _spreadsheet_text_chunks(doc, rows_per_batch=30)
            sampled.append(chunks[0])
    return sampled


def classify_documents(
    docs: list[InputDocument],
    *,
    api_key: str | None,
    model: str,
) -> DocumentClassification:
    client = get_client(api_key)
    return _structured_call(
        client,
        model=model,
        prompt=(
            CLASSIFICATION_SYSTEM_PROMPT
            + "\n\nClassifique os arquivos e indique o modo e a base."
        ),
        docs=_classification_sample(docs),
        schema=DocumentClassification,
        context="classificação",
    )


def _jobs(
    docs: list[InputDocument],
    *,
    pages_per_batch: int,
    start_page: int,
    end_page: int | None,
) -> list[tuple[InputDocument, int | None, int | None, str]]:
    result = []
    for doc in docs:
        if doc.mime_type == "application/pdf":
            for part, first, last in split_pdf(
                doc,
                pages_per_batch=pages_per_batch,
                start_page=start_page,
                end_page=end_page,
            ):
                result.append((part, first, last, doc.name))
        else:
            for chunk in _spreadsheet_text_chunks(doc):
                result.append((chunk, None, None, doc.name))
    return result


def extract_catalog(
    docs: list[InputDocument],
    *,
    api_key: str | None,
    model: str,
    pages_per_batch: int,
    start_page: int,
    end_page: int | None,
    progress_callback=None,
) -> list[CatalogBatch]:
    client = get_client(api_key)
    jobs = _jobs(
        docs,
        pages_per_batch=pages_per_batch,
        start_page=start_page,
        end_page=end_page,
    )
    batches = []
    total = len(jobs)

    for index, (doc, first, last, original_name) in enumerate(jobs, 1):
        if progress_callback:
            progress_callback(index - 1, total, f"Analisando {doc.name}")
        instruction = (
            f"Arquivo original: {original_name}. "
            f"Páginas: {first or 'não aplicável'} a "
            f"{last or 'não aplicável'}. Use o nome original em source_file "
            "e a numeração original em source_page."
        )
        batches.append(
            _structured_call(
                client,
                model=model,
                prompt=CATALOG_SYSTEM_PROMPT + "\n\n" + instruction,
                docs=[doc],
                schema=CatalogBatch,
                context=doc.name,
            )
        )

    if progress_callback:
        progress_callback(total, total, "Extração concluída")
    return batches



def _cost_from_text(text: str, source_page: int | None):
    from models import CostComponent

    return CostComponent(
        description=text,
        amount=None,
        currency="Não informado",
        treatment="Não informado",
        notes=(
            "Componente extraído como texto na etapa de segurança. "
            "Revisar valor e classificação manualmente."
        ),
        source_page=source_page,
        confidence=0.6,
    )


def _fallback_to_activation_batch(
    fallback: ActivationFallbackBatch,
) -> ActivationBatch:
    from models import ActivationSolution

    solutions = []

    for item in fallback.items:
        missing_fields = []
        if item.base_price is None:
            missing_fields.append("base_price")
        if item.lead_time_days is None:
            missing_fields.append("lead_time_days")
        if not item.supplier_name and not fallback.supplier_name:
            missing_fields.append("supplier_name")

        solutions.append(
            ActivationSolution(
                source_file=item.source_file,
                source_page=item.source_page,
                visual_crop=item.visual_crop,
                supplier_name=(
                    item.supplier_name or fallback.supplier_name
                ),
                client_brand=(
                    item.client_brand or fallback.client_brand
                ),
                project_name=(
                    item.project_name or fallback.project_name
                ),
                event_name=item.event_name,
                category="Solução de ativação",
                record_type="Outro",
                name=item.name,
                description=item.description,
                base_price=item.base_price,
                currency=item.currency,
                price_status=item.price_status,
                pricing_period=item.pricing_period,
                price_notes=item.price_notes,
                additional_costs=[
                    _cost_from_text(text, item.source_page)
                    for text in item.additional_costs_text
                ],
                included_items=item.included_items,
                excluded_items=item.excluded_items,
                infrastructure_requirements=(
                    item.infrastructure_requirements
                ),
                lead_time_days=item.lead_time_days,
                location=item.location,
                customizable=None,
                tags=item.tags,
                confidence=item.confidence,
                missing_fields=missing_fields,
                evidence=item.evidence,
            )
        )

    return ActivationBatch(
        supplier_name=fallback.supplier_name,
        supplier_contact=None,
        proposal_name=fallback.proposal_name,
        client_brand=fallback.client_brand,
        project_name=fallback.project_name,
        document_year=fallback.document_year,
        global_rules=[],
        solutions=solutions,
        warnings=[
            *fallback.warnings,
            (
                "A extração principal retornou zero soluções. "
                "Foi utilizada a extração de segurança simplificada."
            ),
        ],
    )


def _extract_activation_batch_with_fallback(
    client: genai.Client,
    *,
    model: str,
    doc: InputDocument,
    instruction: str,
) -> ActivationBatch:
    primary = _structured_call(
        client,
        model=model,
        prompt=ACTIVATION_SYSTEM_PROMPT + "\n\n" + instruction,
        docs=[doc],
        schema=ActivationBatch,
        context=doc.name,
    )

    if primary.solutions:
        return primary

    fallback = _structured_call(
        client,
        model=model,
        prompt=(
            ACTIVATION_FALLBACK_PROMPT
            + "\n\n"
            + instruction
            + "\n\nAtenção: gere ao menos uma linha para cada item "
              "comercial presente no documento."
        ),
        docs=[doc],
        schema=ActivationFallbackBatch,
        context=f"extração de segurança de {doc.name}",
    )

    return _fallback_to_activation_batch(fallback)


def extract_activation(
    docs: list[InputDocument],
    *,
    api_key: str | None,
    model: str,
    pages_per_batch: int,
    start_page: int,
    end_page: int | None,
    progress_callback=None,
) -> list[ActivationBatch]:
    client = get_client(api_key)
    jobs = _jobs(
        docs,
        pages_per_batch=pages_per_batch,
        start_page=start_page,
        end_page=end_page,
    )
    batches = []
    total = len(jobs)

    for index, (doc, first, last, original_name) in enumerate(jobs, 1):
        if progress_callback:
            progress_callback(index - 1, total, f"Analisando {doc.name}")
        instruction = (
            f"Arquivo original: {original_name}. "
            f"Páginas: {first or 'não aplicável'} a "
            f"{last or 'não aplicável'}. Use o nome original em source_file "
            "e a numeração original em source_page."
        )
        batches.append(
            _extract_activation_batch_with_fallback(
                client,
                model=model,
                doc=doc,
                instruction=instruction,
            )
        )

    if progress_callback:
        progress_callback(total, total, "Extração concluída")
    return batches




_SPREADSHEET_EXTENSIONS = {".xlsx", ".xls", ".csv", ".tsv"}
_STRUCTURED_VENUE_BATCH_SIZE = 25


def _normalize_header(value: object) -> str:
    text = str(value or "").strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


def _clean_cell(value: object) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return text


def _number_or_none(value: object) -> float | None:
    text = _clean_cell(value)
    if text is None:
        return None
    compact = re.sub(r"[^0-9,.-]", "", text)
    if not compact:
        return None
    if "," in compact and "." in compact:
        if compact.rfind(",") > compact.rfind("."):
            compact = compact.replace(".", "").replace(",", ".")
        else:
            compact = compact.replace(",", "")
    elif "," in compact:
        compact = compact.replace(".", "").replace(",", ".")
    try:
        number = float(compact)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _integer_or_none(value: object) -> int | None:
    number = _number_or_none(value)
    if number is None or not float(number).is_integer():
        return None
    return int(number)


def _split_list_cell(value: object) -> list[str]:
    text = _clean_cell(value)
    if not text:
        return []
    parts = re.split(r"[;|\n]+", text)
    return [part.strip() for part in parts if part.strip()]


def _row_value(
    row: pd.Series,
    columns: dict[str, str],
    *aliases: str,
) -> object:
    for alias in aliases:
        source = columns.get(_normalize_header(alias))
        if source is not None:
            return row.get(source)
    return None


def _spreadsheet_bytes(doc: InputDocument) -> bytes | None:
    suffix = Path(doc.name).suffix.lower()
    original_mime = (doc.original_mime_type or "").lower()
    if suffix not in _SPREADSHEET_EXTENSIONS and not any(
        token in original_mime
        for token in ("spreadsheet", "excel", "csv", "tab-separated")
    ):
        return None
    return doc.original_data or (
        doc.data if doc.mime_type != "text/plain" else None
    )


def _read_spreadsheet(doc: InputDocument) -> dict[str, pd.DataFrame] | None:
    data = _spreadsheet_bytes(doc)
    if data is None:
        return None
    suffix = Path(doc.name).suffix.lower()
    buffer = io.BytesIO(data)
    try:
        if suffix in {".csv", ".tsv"}:
            separator = "\t" if suffix == ".tsv" else None
            frame = pd.read_csv(
                buffer,
                sep=separator,
                engine="python",
                dtype=object,
                keep_default_na=False,
            )
            return {"Planilha": frame}
        return pd.read_excel(
            buffer,
            sheet_name=None,
            dtype=object,
            keep_default_na=False,
        )
    except Exception:
        return None


def _venue_type_from_value(value: object) -> str:
    normalized = _normalize_header(value)
    if not normalized:
        return "Não informado"
    if "GALPAO" in normalized or "FABRICA" in normalized:
        return "Galpão"
    if "CENTRO_DE_CONVEN" in normalized:
        return "Centro de convenções"
    if "PAVILHAO" in normalized:
        return "Pavilhão"
    if "HOTEL" in normalized:
        return "Hotel"
    if "RESTAURANTE" in normalized or "BAR" in normalized:
        return "Restaurante / bar"
    if any(
        token in normalized
        for token in ("TEATRO", "AUDITORIO", "CASA_DE_SHOW")
    ):
        return "Auditório / teatro"
    if any(
        token in normalized
        for token in ("GALERIA", "MUSEU", "CULTURAL")
    ):
        return "Espaço cultural"
    if "ESTADIO" in normalized or "ARENA" in normalized:
        return "Estádio / arena"
    if "SHOPPING" in normalized:
        return "Shopping"
    if any(
        token in normalized
        for token in ("AREA_EXTERNA", "PARQUE", "PRACA")
    ):
        return "Área externa"
    if any(
        token in normalized
        for token in ("ESPACO_DE_EVENTOS", "CASA_DE_EVENTOS")
    ):
        return "Casa de eventos"
    return "Não informado"


def _confidence_from_value(value: object) -> float:
    text = _normalize_header(value)
    if text in {"ALTA", "HIGH"}:
        return 0.95
    if text in {"MEDIA", "MEDIUM"}:
        return 0.8
    if text in {"BAIXA", "LOW"}:
        return 0.6
    number = _number_or_none(value)
    if number is not None:
        if number > 1:
            number /= 100
        return min(1.0, max(0.0, number))
    return 0.75


def _contact_from_row(
    row: pd.Series,
    columns: dict[str, str],
    *,
    venue_name: str,
) -> SupplierContact | None:
    contact_text = _clean_cell(
        _row_value(row, columns, "CONTATO", "CONTACT", "CONTATOS")
    )
    website = _clean_cell(
        _row_value(
            row,
            columns,
            "SITE",
            "WEBSITE",
            "WEBSITE_URL",
            "SITE_ORIGINAL",
        )
    )
    instagram = _clean_cell(
        _row_value(row, columns, "INSTAGRAM", "INSTAGRAM_URL")
    )
    address = _clean_cell(
        _row_value(row, columns, "ENDERECO", "ADDRESS")
    )
    city = _clean_cell(_row_value(row, columns, "CIDADE", "CITY"))
    state = _clean_cell(_row_value(row, columns, "ESTADO", "STATE"))

    email = None
    phone = None
    contact_name = None
    if contact_text:
        email_match = re.search(
            r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            contact_text,
            flags=re.IGNORECASE,
        )
        if email_match:
            email = email_match.group(0)
        phone_match = re.search(
            r"(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?"
            r"\d{4,5}[-\s]?\d{4}",
            contact_text,
        )
        if phone_match:
            phone = phone_match.group(0).strip()
        prefix = contact_text
        if email:
            prefix = prefix.split(email, 1)[0]
        if phone:
            prefix = prefix.split(phone, 1)[0]
        prefix = re.sub(r"[|;/,]+$", "", prefix).strip(" -–—")
        if prefix and len(prefix) <= 120:
            contact_name = prefix

    if not any((contact_text, website, instagram, address, city, state)):
        return None
    return SupplierContact(
        supplier_name=venue_name,
        website_url=website,
        contact_name=contact_name,
        email=email,
        phone=phone,
        whatsapp=phone,
        instagram_url=instagram,
        address=address,
        base_city=city,
        base_state=state,
        base_country="Brasil" if state else None,
        notes=contact_text,
        confidence=0.8 if contact_text else 0.65,
    )


def _structured_venue_batches(
    doc: InputDocument,
) -> list[VenueBatch] | None:
    sheets = _read_spreadsheet(doc)
    if not sheets:
        return None

    batches: list[VenueBatch] = []
    recognized_rows = 0
    for sheet_name, frame in sheets.items():
        if frame is None or frame.empty:
            continue
        columns = {
            _normalize_header(column): str(column)
            for column in frame.columns
        }
        name_column = next(
            (
                columns.get(alias)
                for alias in (
                    "LOCAL",
                    "NOME_DO_LOCAL",
                    "NOME_LOCAL",
                    "VENUE_NAME",
                    "NAME",
                )
                if columns.get(alias)
            ),
            None,
        )
        venue_signals = sum(
            alias in columns
            for alias in (
                "CATEGORIA",
                "TIPO_DE_LOCAL",
                "CAPACIDADE",
                "CAPACIDADE_EM_PE",
                "ENDERECO",
                "SITE",
                "DESCRICAO_NAVE",
                "CIDADE",
                "ESTADO",
            )
        )
        if name_column is None or venue_signals < 2:
            continue

        for position, (_, row) in enumerate(frame.iterrows(), start=2):
            name = _clean_cell(row.get(name_column))
            if not name:
                continue
            recognized_rows += 1
            category = _row_value(
                row,
                columns,
                "CATEGORIA",
                "TIPO_LOCAL_PADRONIZADO",
                "TIPO_DE_LOCAL",
                "TIPO",
                "VENUE_TYPE",
            )
            website = _clean_cell(
                _row_value(
                    row,
                    columns,
                    "SITE",
                    "WEBSITE",
                    "WEBSITE_URL",
                    "SITE_ORIGINAL",
                )
            )
            description = _clean_cell(
                _row_value(
                    row,
                    columns,
                    "DESCRICAO_NAVE",
                    "DESCRICAO",
                    "DESCRIPTION",
                    "OBS",
                )
            )
            address = _clean_cell(
                _row_value(
                    row,
                    columns,
                    "ENDERECO",
                    "ADDRESS",
                    "ENDERECO_ORIGINAL",
                )
            )
            city = _clean_cell(
                _row_value(row, columns, "CIDADE", "CITY")
            )
            state = _clean_cell(
                _row_value(row, columns, "ESTADO", "STATE")
            )
            source_row = _integer_or_none(
                _row_value(
                    row,
                    columns,
                    "LINHA_ORIGINAL",
                    "LINHA_PLANILHA",
                    "__LINHA_PLANILHA__",
                )
            ) or position

            missing_fields = []
            for field_name, field_value in (
                ("address", address),
                ("city", city),
                ("state", state),
                ("website_url", website),
            ):
                if not field_value:
                    missing_fields.append(field_name)

            standing = _integer_or_none(
                _row_value(
                    row,
                    columns,
                    "CAPACIDADE_EM_PE",
                    "STANDING_CAPACITY",
                )
            )
            seated = _integer_or_none(
                _row_value(
                    row,
                    columns,
                    "CAPACIDADE_SENTADA",
                    "SEATED_CAPACITY",
                )
            )
            auditorium = _integer_or_none(
                _row_value(
                    row,
                    columns,
                    "CAPACIDADE_AUDITORIO",
                    "AUDITORIUM_CAPACITY",
                )
            )
            if standing is None and seated is None and auditorium is None:
                missing_fields.append("capacity")

            category_text = _clean_cell(category)
            tags = []
            if category_text:
                tags.append(category_text)
            tags.extend(
                _split_list_cell(
                    _row_value(
                        row,
                        columns,
                        "TIPOS_MIDIA_PUBLICA",
                        "TAGS",
                    )
                )
            )
            confidence = _confidence_from_value(
                _row_value(
                    row,
                    columns,
                    "NIVEL_CONFIANCA",
                    "CONFIDENCE",
                )
            )
            evidence_parts = [
                f"Importação tabular direta da aba {sheet_name}",
                f"linha {source_row}",
            ]
            obs = _clean_cell(
                _row_value(
                    row,
                    columns,
                    "OBS_PESQUISA",
                    "OBS",
                    "NOTES",
                )
            )
            if obs:
                evidence_parts.append(obs[:300])

            venue = VenueSpace(
                source_file=doc.name,
                source_page=source_row,
                operator_name=_clean_cell(
                    _row_value(
                        row,
                        columns,
                        "OPERADOR",
                        "OPERATOR_NAME",
                    )
                ),
                name=name,
                venue_type=_venue_type_from_value(category),
                description=description,
                address=address,
                neighborhood=_clean_cell(
                    _row_value(row, columns, "BAIRRO", "NEIGHBORHOOD")
                ),
                city=city,
                state=state,
                country=_clean_cell(
                    _row_value(row, columns, "PAIS", "COUNTRY")
                ) or ("Brasil" if state else None),
                postal_code=_clean_cell(
                    _row_value(row, columns, "CEP", "POSTAL_CODE")
                ),
                map_url=_clean_cell(
                    _row_value(row, columns, "MAPA_URL", "MAP_URL")
                ),
                website_url=website,
                total_area_sqm=_number_or_none(
                    _row_value(
                        row,
                        columns,
                        "AREA_TOTAL_M2",
                        "TOTAL_AREA_SQM",
                    )
                ),
                indoor_area_sqm=_number_or_none(
                    _row_value(
                        row,
                        columns,
                        "AREA_PRINCIPAL_M2",
                        "INDOOR_AREA_SQM",
                    )
                ),
                ceiling_height_m=_number_or_none(
                    _row_value(
                        row,
                        columns,
                        "PE_DIREITO_M",
                        "CEILING_HEIGHT_M",
                    )
                ),
                standing_capacity=standing,
                seated_capacity=seated,
                auditorium_capacity=auditorium,
                parking=_clean_cell(
                    _row_value(row, columns, "ESTACIONAMENTO", "PARKING")
                ),
                accessibility=_clean_cell(
                    _row_value(
                        row,
                        columns,
                        "ACESSIBILIDADE",
                        "ACCESSIBILITY",
                    )
                ),
                loading_access=_clean_cell(
                    _row_value(
                        row,
                        columns,
                        "CARGA_DESCARGA",
                        "LOADING_ACCESS",
                    )
                ),
                kitchen_or_catering=_clean_cell(
                    _row_value(
                        row,
                        columns,
                        "COZINHA_CATERING",
                        "KITCHEN_OR_CATERING",
                    )
                ),
                audiovisual=_clean_cell(
                    _row_value(
                        row,
                        columns,
                        "AUDIOVISUAL_INTERNET",
                        "AUDIOVISUAL",
                    )
                ),
                internet=_clean_cell(
                    _row_value(row, columns, "INTERNET")
                ),
                event_availability=_clean_cell(
                    _row_value(
                        row,
                        columns,
                        "STATUS_EM_CASO_DE_EVENTOS",
                        "STATUS",
                    )
                ),
                operating_hours=_clean_cell(
                    _row_value(
                        row,
                        columns,
                        "DATA_DISPONIVEL_EM_CASO_DE_EVENTOS",
                        "DISPONIBILIDADE",
                    )
                ),
                base_price=_number_or_none(
                    _row_value(
                        row,
                        columns,
                        "VALOR_DA_DIARIA_DECUPADO",
                        "BASE_PRICE",
                    )
                ),
                currency=(
                    "BRL"
                    if _number_or_none(
                        _row_value(
                            row,
                            columns,
                            "VALOR_DA_DIARIA_DECUPADO",
                            "BASE_PRICE",
                        )
                    )
                    is not None
                    else "Não informado"
                ),
                price_status=(
                    "Informado"
                    if _number_or_none(
                        _row_value(
                            row,
                            columns,
                            "VALOR_DA_DIARIA_DECUPADO",
                            "BASE_PRICE",
                        )
                    )
                    is not None
                    else "Não informado"
                ),
                price_notes=_clean_cell(
                    _row_value(
                        row,
                        columns,
                        "VALOR_DA_DIARIA_DECUPADO",
                        "PRICE_NOTES",
                    )
                ),
                tags=list(dict.fromkeys(tags)),
                confidence=confidence,
                missing_fields=missing_fields,
                evidence="; ".join(evidence_parts),
            )
            contact = _contact_from_row(
                row,
                columns,
                venue_name=name,
            )
            batches.append(
                VenueBatch(
                    operator_name=venue.operator_name,
                    venue_contact=contact,
                    document_name=doc.name,
                    venues=[venue],
                    warnings=[],
                )
            )

    return batches if recognized_rows else None


def _spreadsheet_text_chunks(
    doc: InputDocument,
    *,
    rows_per_batch: int = _STRUCTURED_VENUE_BATCH_SIZE,
) -> list[InputDocument]:
    try:
        text = doc.data.decode("utf-8", errors="replace")
    except Exception:
        return [doc]
    if "TIPO: PLANILHA" not in text:
        return [doc]

    chunks: list[InputDocument] = []
    sections = re.split(r"(?=^=== ABA: )", text, flags=re.MULTILINE)
    preamble = sections[0].strip()
    for section in sections[1:]:
        lines = [line for line in section.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        sheet_marker = lines[0]
        header = lines[1]
        data_lines = lines[2:]
        for start in range(0, len(data_lines), rows_per_batch):
            selected = data_lines[start:start + rows_per_batch]
            chunk_number = start // rows_per_batch + 1
            content = "\n".join(
                [
                    preamble,
                    sheet_marker,
                    header,
                    *selected,
                ]
            )
            chunks.append(
                InputDocument(
                    name=(
                        f"{Path(doc.name).stem}_"
                        f"lote_{chunk_number:03d}.txt"
                    ),
                    data=content.encode("utf-8"),
                    mime_type="text/plain",
                    original_data=doc.original_data,
                    original_mime_type=doc.original_mime_type,
                )
            )
    return chunks or [doc]


def _venue_jobs(
    docs: list[InputDocument],
    *,
    pages_per_batch: int,
    start_page: int,
    end_page: int | None,
) -> list[tuple[InputDocument, int | None, int | None, str]]:
    result = []
    for doc in docs:
        if doc.mime_type == "application/pdf":
            for part, first, last in split_pdf(
                doc,
                pages_per_batch=pages_per_batch,
                start_page=start_page,
                end_page=end_page,
            ):
                result.append((part, first, last, doc.name))
            continue
        for chunk in _spreadsheet_text_chunks(doc):
            result.append((chunk, None, None, doc.name))
    return result


def extract_venues(
    docs: list[InputDocument],
    *,
    api_key: str | None,
    model: str,
    pages_per_batch: int,
    start_page: int,
    end_page: int | None,
    progress_callback=None,
) -> list[VenueBatch]:
    batches: list[VenueBatch] = []
    remaining_docs: list[InputDocument] = []

    direct_results: list[tuple[InputDocument, list[VenueBatch]]] = []
    direct_total = 0
    for doc in docs:
        parsed = _structured_venue_batches(doc)
        if parsed is None:
            remaining_docs.append(doc)
            continue
        direct_results.append((doc, parsed))
        direct_total += len(parsed)

    jobs = _venue_jobs(
        remaining_docs,
        pages_per_batch=pages_per_batch,
        start_page=start_page,
        end_page=end_page,
    )
    total = direct_total + len(jobs)
    completed = 0

    for doc, parsed_batches in direct_results:
        for parsed in parsed_batches:
            if progress_callback:
                progress_callback(
                    completed,
                    total,
                    (
                        "Lendo planilha estruturada: "
                        f"{completed + 1} de {total} registros/lotes"
                    ),
                )
            batches.append(parsed)
            completed += 1

    client = get_client(api_key) if jobs else None
    for doc, first, last, original_name in jobs:
        if progress_callback:
            progress_callback(
                completed,
                total,
                f"Analisando {doc.name}",
            )
        instruction = (
            f"Arquivo original: {original_name}. "
            f"Páginas: {first or 'não aplicável'} a "
            f"{last or 'não aplicável'}. Use o nome original em source_file "
            "e a numeração original em source_page. "
            "Este é um lote parcial: extraia somente os registros presentes "
            "neste lote e não tente reconstruir linhas ausentes."
        )
        batches.append(
            _structured_call(
                client,
                model=model,
                prompt=VENUE_SYSTEM_PROMPT + "\n\n" + instruction,
                docs=[doc],
                schema=VenueBatch,
                context=doc.name,
            )
        )
        completed += 1

    if progress_callback:
        progress_callback(total, total, "Extração concluída")
    return batches


def extract_briefing(
    docs: list[InputDocument],
    *,
    pasted_text: str,
    api_key: str | None,
    model: str,
) -> ProjectBriefing:
    client = get_client(api_key)
    all_docs = list(docs)
    if pasted_text.strip():
        all_docs.append(
            InputDocument(
                name="texto_colado_usuario.txt",
                data=pasted_text.strip().encode("utf-8"),
                mime_type="text/plain",
            )
        )
    return _structured_call(
        client,
        model=model,
        prompt=(
            BRIEFING_SYSTEM_PROMPT
            + "\n\nConsolide todas as fontes em um briefing estruturado."
        ),
        docs=all_docs,
        schema=ProjectBriefing,
        context="briefing",
    )




def _recommendation_call_with_fallback(
    client: genai.Client,
    *,
    model: str,
    prompt: str,
    docs: list[InputDocument],
    context: str,
) -> RecommendationBrief:
    models_to_try = [model]

    economical_model = "gemini-3.5-flash-lite"
    if model != economical_model:
        models_to_try.append(economical_model)

    last_quota_error: GeminiQuotaError | None = None

    for candidate_model in models_to_try:
        try:
            return _structured_call(
                client,
                model=candidate_model,
                prompt=prompt,
                docs=docs,
                schema=RecommendationBrief,
                context=context,
            )
        except GeminiQuotaError as exc:
            last_quota_error = exc

    if last_quota_error:
        raise GeminiQuotaError(
            (
                "Os modelos disponíveis atingiram o limite temporário "
                "do Gemini. Nenhuma informação do briefing foi perdida."
            ),
            retry_after_seconds=(
                last_quota_error.retry_after_seconds
            ),
            model=last_quota_error.model,
        ) from last_quota_error

    raise RuntimeError(
        "Não foi possível processar o briefing com os modelos disponíveis."
    )



def parse_recommendation_brief(
    text: str,
    *,
    api_key: str | None,
    model: str,
) -> RecommendationBrief:
    client = get_client(api_key)
    source = InputDocument(
        name="consulta_recomendador.txt",
        data=text.encode("utf-8"),
        mime_type="text/plain",
    )
    return _recommendation_call_with_fallback(
        client,
        model=model,
        prompt=(
            RECOMMENDATION_BRIEF_PROMPT
            + "\n\nEstruture a consulta abaixo."
        ),
        docs=[source],
        context="consulta do recomendador",
    )



def parse_recommendation_sources(
    docs: list[InputDocument],
    *,
    pasted_text: str,
    api_key: str | None,
    model: str,
) -> RecommendationBrief:
    client = get_client(api_key)

    all_docs = list(docs)
    if pasted_text.strip():
        all_docs.append(
            InputDocument(
                name="briefing_colado_usuario.txt",
                data=pasted_text.strip().encode("utf-8"),
                mime_type="text/plain",
            )
        )

    if not all_docs:
        raise ValueError(
            "Envie ao menos um arquivo ou cole o briefing."
        )

    result = _recommendation_call_with_fallback(
        client,
        model=model,
        prompt=(
            RECOMMENDATION_BRIEF_PROMPT
            + "\n\nLeia todas as fontes, consolide as informações e "
              "preencha o formulário da consulta."
        ),
        docs=all_docs,
        context="preenchimento automático do briefing",
    )

    result.source_files = [doc.name for doc in docs]
    return result
