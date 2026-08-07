from __future__ import annotations

"""PDF visual de selecao/recomendacao da NAVE by VOE.

V28.0.3.7
- independente de knowledge_details.py para nao bloquear a Base de Conhecimento;
- identifica a area de origem da exportacao;
- enriquece os itens com a ficha completa quando o banco estiver disponivel;
- usa capa e galeria validada do acervo, sem transformar slide/pagina de origem em foto;
- redimensiona/comprime imagens grandes antes de inclui-las no PDF;
- gera um caderno visual em A4 vertical, com o lockup oficial fornecido pelo usuario;
- remove blocos de imagem quando nenhuma foto esta disponivel;
- simplifica a hierarquia das fichas e aumenta o respiro entre informacoes;
- posiciona a identificacao de exportacao no canto superior direito;
- remove Tags da exportacao para manter o documento mais editorial.
"""

from datetime import datetime
from html import escape as html_escape
from io import BytesIO
from pathlib import Path
import inspect
import math
from typing import Any
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen

from PIL import Image as PILImage, ImageOps
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


NAVY = colors.HexColor("#121B42")
CYAN = colors.HexColor("#18CDEA")
SURFACE = colors.HexColor("#F4F6F9")
BORDER = colors.HexColor("#E1E6EF")
TEXT = colors.HexColor("#30384F")
MUTED = colors.HexColor("#687188")
WHITE = colors.white

ENTITY_LABELS = {
    "product": "Brinde",
    "activation": "Ativação",
    "venue": "Local / espaço",
    "supplier": "Fornecedor",
}
AREA_LABELS = {
    "product": "Brindes",
    "activation": "Ativações",
    "venue": "Locais e espaços",
    "supplier": "Fornecedores",
}
TABLES = {
    "product": "products",
    "activation": "activation_solutions",
    "venue": "venues",
    "supplier": "suppliers",
}

# Campos apresentados no resumo visual de cada tipo.
KEY_FIELDS: dict[str, list[tuple[str, str]]] = {
    "product": [
        ("category", "Categoria"),
        ("material", "Material"),
        ("supplier_name", "Fornecedor"),
        ("unit_price", "Valor unitario"),
        ("min_order_qty", "Pedido minimo"),
        ("sku", "Codigo / SKU"),
    ],
    "activation": [
        ("category", "Categoria"),
        ("client_brand", "Marca / cliente"),
        ("project_name", "Projeto"),
        ("supplier_name", "Fornecedor"),
        ("base_price", "Valor base"),
        ("location", "Localizacao"),
    ],
    "venue": [
        ("venue_type", "Tipo de espaco"),
        ("city_state", "Cidade / UF"),
        ("standing_capacity", "Capacidade em pe"),
        ("seated_capacity", "Capacidade sentada"),
        ("total_area_sqm", "Area total"),
        ("supplier_name", "Operador / responsavel"),
    ],
    "supplier": [
        ("base_city_state", "Base"),
        ("coverage_summary", "Cobertura"),
        ("contact_name", "Contato"),
        ("email", "E-mail"),
        ("phone", "Telefone"),
        ("portfolio_summary", "Repertorio associado"),
    ],
}

# Secoes completas. So aparecem quando ao menos um campo tem valor.
SECTIONS: dict[str, list[tuple[str, list[tuple[str, str]]]]] = {
    "product": [
        ("Caracteristicas", [
            ("capacity", "Capacidade"), ("capacity_ml", "Capacidade em ml"),
            ("dimensions_raw", "Dimensoes"), ("finish", "Acabamento"),
            ("decoration", "Personalizacao / decoracao"), ("customizable", "Personalizavel"),
            ("licensing_notes", "Licenciamento"),
        ]),
        ("Valores e condicoes", [
            ("unit_price", "Valor unitario"), ("price_min", "Valor minimo"),
            ("price_max", "Valor maximo"), ("price_reference_qty", "Qtd. de referencia"),
            ("min_order_qty", "Pedido minimo"), ("price_status", "Status do valor"),
            ("price_notes", "Observacoes de valor"),
        ]),
        ("Origem", [
            ("catalog_name", "Catalogo"), ("document_year", "Ano"),
            ("source_file", "Arquivo de origem"), ("source_page", "Pagina de origem"),
            ("origin", "Origem"), ("development_status", "Status de desenvolvimento"),
        ]),
    ],
    "activation": [
        ("Projeto e contexto", [
            ("record_type", "Tipo de registro"), ("proposal_name", "Proposta"),
            ("client_brand", "Marca / cliente"), ("project_name", "Projeto"),
            ("event_name", "Evento"), ("location", "Localizacao"),
            ("event_period", "Periodo"),
        ]),
        ("Execucao e infraestrutura", [
            ("lead_time_days", "Prazo de producao"), ("setup_window", "Janela de montagem"),
            ("internet_requirement", "Internet"), ("staff_included", "Equipe incluida"),
            ("staff_description", "Descricao da equipe"), ("customizable", "Personalizavel"),
            ("included_items", "Itens incluidos"), ("excluded_items", "Itens nao incluidos"),
            ("infrastructure_requirements", "Necessidades de infraestrutura"),
        ]),
        ("Valores e condicoes", [
            ("base_price", "Valor base"), ("price_status", "Status do valor"),
            ("pricing_period", "Periodo de cobranca"), ("discount_percent", "Desconto"),
            ("negotiated_benefit", "Beneficio negociado"), ("validity", "Validade"),
            ("payment_terms", "Condicoes de pagamento"), ("price_notes", "Observacoes de valor"),
        ]),
        ("Classificacao e origem", [
            ("document_year", "Ano"),
            ("source_file", "Arquivo de origem"), ("source_page", "Pagina de origem"),
            ("evidence", "Evidencias encontradas"),
        ]),
    ],
    "venue": [
        ("Localizacao e acesso", [
            ("address", "Endereco"), ("neighborhood", "Bairro"),
            ("city", "Cidade"), ("state", "Estado"), ("country", "Pais"),
            ("postal_code", "CEP"), ("parking", "Estacionamento"),
            ("accessibility", "Acessibilidade"), ("loading_access", "Acesso de carga"),
            ("website_url", "Site"), ("map_url", "Mapa"),
        ]),
        ("Areas e capacidades", [
            ("total_area_sqm", "Area total"), ("indoor_area_sqm", "Area interna"),
            ("outdoor_area_sqm", "Area externa"), ("ceiling_height_m", "Pe-direito"),
            ("standing_capacity", "Capacidade em pe"), ("seated_capacity", "Capacidade sentada"),
            ("auditorium_capacity", "Capacidade auditorio"), ("rooms_or_areas", "Ambientes / areas"),
        ]),
        ("Infraestrutura e operacao", [
            ("kitchen_or_catering", "Cozinha / catering"), ("power_supply", "Energia"),
            ("internet", "Internet"), ("air_conditioning", "Climatizacao"),
            ("bathrooms", "Banheiros"), ("furniture", "Mobiliario"),
            ("audiovisual", "Audiovisual"), ("infrastructure", "Infraestrutura disponivel"),
            ("restrictions", "Restricoes"), ("operating_hours", "Horarios de operacao"),
            ("event_availability", "Disponibilidade para eventos"),
        ]),
        ("Valores e origem", [
            ("base_price", "Valor base"), ("price_min", "Valor minimo"),
            ("price_max", "Valor maximo"), ("pricing_period", "Periodo de cobranca"),
            ("price_notes", "Observacoes de valor"), ("document_name", "Documento de origem"),
            ("document_year", "Ano"),
        ]),
    ],
    "supplier": [
        ("Contato", [
            ("contact_name", "Contato"), ("contact_role", "Funcao"),
            ("email", "E-mail"), ("phone", "Telefone"), ("whatsapp", "WhatsApp"),
            ("website_url", "Site"), ("instagram_url", "Instagram"),
            ("linkedin_url", "LinkedIn"), ("address", "Endereco"),
        ]),
        ("Cobertura", [
            ("base_city", "Cidade-base"), ("base_state", "Estado-base"),
            ("base_country", "Pais-base"), ("serves_nationally", "Atende nacionalmente"),
            ("served_states", "Estados atendidos"), ("served_cities", "Cidades atendidas"),
            ("has_local_teams", "Possui equipes locais"), ("local_team_locations", "Equipes locais"),
            ("coverage_notes", "Observacoes de cobertura"),
        ]),
        ("Logistica", [
            ("travel_pricing_mode", "Modelo de deslocamento"),
            ("default_travel_cost_brl", "Custo padrao de deslocamento"),
            ("freight_pricing_mode", "Modelo de frete"),
            ("default_freight_cost_brl", "Custo padrao de frete"),
            ("travel_lead_days", "Antecedencia para deslocamento"),
            ("equipment_transport_required", "Exige transporte de equipamento"),
            ("accommodation_required", "Exige hospedagem"),
        ]),
        ("Repertorio", [
            ("products_count", "Brindes / produtos"), ("activations_count", "Ativacoes / solucoes"),
            ("venues_count", "Locais / espacos"), ("linked_venue_names", "Locais relacionados"),
            ("notes", "Observacoes"),
        ]),
    ],
}

ALIASES = {
    "Capa": "cover_url",
    "Brinde": "name",
    "Ativacao": "name",
    "Ativação": "name",
    "Local": "name",
    "Fornecedor": "supplier_name",
    "Categoria": "category",
    "Material": "material",
    "Codigo / SKU": "sku",
    "Código / SKU": "sku",
    "Marca / cliente": "client_brand",
    "Projeto": "project_name",
    "Cobertura": "coverage_level",
    "Base": "base_label",
    "Brindes": "products_count",
    "Ativacoes": "activations_count",
    "Ativações": "activations_count",
    "Locais relacionados": "venues_count",
    "Tipo": "venue_type",
    "Cidade": "city",
    "Estado": "state",
}

MISSING = {
    "", "none", "null", "nan", "na", "n/a", "nao informado", "não informado",
    "nao disponivel", "não disponível", "sem informacao", "sem informação", "-", "—",
}
MONEY_FIELDS = {
    "unit_price", "price_min", "price_max", "base_price",
    "default_travel_cost_brl", "default_freight_cost_brl",
}
NUMERIC_SUFFIX = {
    "capacity_ml": " ml", "total_area_sqm": " m²", "indoor_area_sqm": " m²",
    "outdoor_area_sqm": " m²", "ceiling_height_m": " m", "discount_percent": "%",
}
BOOL_FIELDS = {
    "customizable", "staff_included", "serves_nationally", "has_local_teams",
    "equipment_transport_required", "accommodation_required",
}
IMAGE_TYPES = {"main_image", "gallery_image"}
URL_FIELDS = {"website_url", "map_url", "instagram_url", "linkedin_url", "source_image_url"}
ADDRESS_FIELDS = {"address"}


def _as_rows(value: Any) -> list[dict]:
    if value is None:
        return []
    try:
        import pandas as pd
        if isinstance(value, pd.DataFrame):
            return [dict(row) for row in value.to_dict(orient="records")]
    except Exception:
        pass
    if isinstance(value, dict):
        for key in ("items", "records", "rows", "selected_items", "selected_records"):
            nested = value.get(key)
            if isinstance(nested, (list, tuple)):
                return [dict(item) for item in nested if isinstance(item, dict)]
        return [dict(value)]
    if isinstance(value, (list, tuple, set)):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _first_rows(args: tuple[Any, ...], kwargs: dict[str, Any]) -> list[dict]:
    for key in ("items", "records", "rows", "selected_items", "selected_records", "selection"):
        if key in kwargs:
            rows = _as_rows(kwargs.get(key))
            if rows:
                return rows
    for value in args:
        rows = _as_rows(value)
        if rows:
            return rows
    return []


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in MISSING
    if isinstance(value, (list, tuple, set)):
        return not value or all(_is_missing(item) for item in value)
    if isinstance(value, dict):
        return not value or all(_is_missing(item) for item in value.values())
    try:
        return bool(math.isnan(float(value)))
    except Exception:
        return False


def _value(record: dict, *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if not _is_missing(value):
            return value
    raw = record.get("raw_data")
    if isinstance(raw, dict):
        for key in keys:
            value = raw.get(key)
            if not _is_missing(value):
                return value
    return None


def _text_value(value: Any) -> str:
    if _is_missing(value):
        return ""
    if isinstance(value, dict):
        return " | ".join(
            f"{str(key).replace('_', ' ').strip().capitalize()}: {_text_value(item)}"
            for key, item in value.items() if not _is_missing(item)
        )
    if isinstance(value, (list, tuple, set)):
        return " | ".join(_text_value(item) for item in value if not _is_missing(item))
    return str(value).strip()


def _item_type(record: dict) -> str:
    explicit = _text_value(_value(record, "item_type", "entity_type", "type")).casefold()
    if explicit in {"product", "activation", "venue", "supplier"}:
        return explicit
    keys = {str(key) for key in record}
    if "Brinde" in keys:
        return "product"
    if "Ativação" in keys or "Ativacao" in keys:
        return "activation"
    if "Local" in keys:
        return "venue"
    if "Fornecedor" in keys and ("Cobertura" in keys or "Brindes" in keys or "Ativações" in keys):
        return "supplier"
    # Heuristicas para registros completos vindos da Base.
    if any(key in record for key in ("venue_type", "standing_capacity", "seated_capacity", "total_area_sqm")):
        return "venue"
    if any(key in record for key in ("base_city", "served_states", "travel_pricing_mode", "coverage_notes")):
        return "supplier"
    if any(key in record for key in ("client_brand", "project_name", "event_name", "lead_time_days")):
        return "activation"
    if any(key in record for key in ("material", "sku", "min_order_qty", "capacity_ml")):
        return "product"
    return "item"


def _canonical_record(record: dict) -> dict:
    out = dict(record)
    for source, target in ALIASES.items():
        if source in record and _is_missing(out.get(target)):
            out[target] = record.get(source)
    # Fornecedor como nome da propria entidade, quando o registro e supplier.
    if _item_type(record) == "supplier":
        if _is_missing(out.get("name")):
            out["name"] = record.get("Fornecedor") or record.get("supplier_name")
    return out


def _infer_source_context(rows: list[dict], explicit: Any = None) -> str:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    # Base de Conhecimento chama diretamente build_selection_pdf.
    try:
        for frame in inspect.stack()[1:8]:
            filename = str(frame.filename or "").replace("\\", "/")
            if filename.endswith("/pages/2_Consultar_Base.py") or filename.endswith("/2_Consultar_Base.py"):
                return "Base de Conhecimento"
    except Exception:
        pass
    types = {_item_type(row) for row in rows}
    types.discard("item")
    if len(types) == 1:
        return AREA_LABELS.get(next(iter(types)), "Base de Conhecimento")
    return "Base de Conhecimento"


def _source_descriptor(context: str) -> str:
    mapping = {
        "Brindes": "Seleção de brindes do repertório NAVE",
        "Ativacoes": "Seleção de ativações e experiências do repertório NAVE",
        "Ativações": "Seleção de ativações e experiências do repertório NAVE",
        "Locais e espacos": "Seleção de locais e espaços do repertório NAVE",
        "Locais e espaços": "Seleção de locais e espaços do repertório NAVE",
        "Fornecedores": "Seleção de fornecedores e parceiros do repertório NAVE",
        "Base de Conhecimento": "Seleção transversal da Base de Conhecimento NAVE",
    }
    return mapping.get(context, f"Seleção exportada da área {context}")


def _safe_client() -> Any | None:
    try:
        from nave_data_client import get_nave_client
        return get_nave_client()
    except Exception:
        return None


def _response_rows(response: Any) -> list[dict]:
    return [dict(row) for row in (getattr(response, "data", None) or []) if isinstance(row, dict)]


def _query_record(client: Any, entity_type: str, record: dict) -> dict | None:
    table = TABLES.get(entity_type)
    if not client or not table:
        return None
    entity_id = _text_value(_value(record, "id", "_id", "entity_id"))
    name = _text_value(_value(record, "name", "Brinde", "Ativação", "Ativacao", "Local", "Fornecedor"))
    try:
        if entity_id:
            rows = _response_rows(client.table(table).select("*").eq("id", entity_id).limit(1).execute())
            if rows:
                return rows[0]
        if name:
            rows = _response_rows(client.table(table).select("*").eq("name", name).limit(5).execute())
            if not rows:
                return None
            if len(rows) == 1:
                return rows[0]
            # Desambiguacao leve para nomes repetidos.
            for candidate in rows:
                if entity_type == "venue":
                    city = _text_value(_value(record, "city", "Cidade"))
                    state = _text_value(_value(record, "state", "Estado"))
                    if city and city.casefold() != _text_value(candidate.get("city")).casefold():
                        continue
                    if state and state.casefold() != _text_value(candidate.get("state")).casefold():
                        continue
                    return candidate
                category = _text_value(_value(record, "category", "Categoria"))
                if category and category.casefold() != _text_value(candidate.get("category")).casefold():
                    continue
                return candidate
            return rows[0]
    except Exception:
        return None
    return None


def _enrich_supplier_name(client: Any, record: dict) -> None:
    if not client or not _is_missing(record.get("supplier_name")):
        return
    supplier_id = _text_value(record.get("supplier_id") or record.get("operator_id"))
    if not supplier_id:
        return
    try:
        rows = _response_rows(client.table("suppliers").select("id,name").eq("id", supplier_id).limit(1).execute())
        if rows:
            record["supplier_name"] = rows[0].get("name")
    except Exception:
        pass


def _enrich_supplier_relations(client: Any, record: dict) -> None:
    supplier_id = _text_value(_value(record, "id", "_id", "entity_id"))
    if not client or not supplier_id:
        return
    try:
        products = _response_rows(client.table("products").select("id").eq("supplier_id", supplier_id).limit(10000).execute())
        record.setdefault("products_count", len(products))
    except Exception:
        pass
    try:
        activations = _response_rows(client.table("activation_solutions").select("id").eq("supplier_id", supplier_id).limit(10000).execute())
        record.setdefault("activations_count", len(activations))
    except Exception:
        pass
    try:
        venues = _response_rows(client.table("venues").select("id,name").eq("operator_id", supplier_id).limit(10000).execute())
        record.setdefault("venues_count", len(venues))
        names = [_text_value(row.get("name")) for row in venues if _text_value(row.get("name"))]
        if names:
            record.setdefault("linked_venue_names", names)
    except Exception:
        pass


def _derived_fields(record: dict, entity_type: str) -> None:
    if entity_type == "venue":
        city = _text_value(record.get("city"))
        state = _text_value(record.get("state"))
        record["city_state"] = ", ".join(value for value in (city, state) if value)
    elif entity_type == "supplier":
        city = _text_value(record.get("base_city"))
        state = _text_value(record.get("base_state"))
        record["base_city_state"] = ", ".join(value for value in (city, state) if value)
        if record.get("serves_nationally") is True:
            coverage = "Nacional"
        else:
            states = _text_value(record.get("served_states"))
            cities = _text_value(record.get("served_cities"))
            coverage = states or cities or _text_value(record.get("coverage_level"))
        record["coverage_summary"] = coverage
        counts = []
        for key, label in (("products_count", "brindes"), ("activations_count", "ativacoes"), ("venues_count", "locais")):
            value = record.get(key)
            if not _is_missing(value):
                counts.append(f"{_format_number(value, 0)} {label}")
        record["portfolio_summary"] = " | ".join(counts)


def _merge_record(client: Any, raw_record: dict) -> tuple[str, dict]:
    entity_type = _item_type(raw_record)
    visible = _canonical_record(raw_record)
    full = _query_record(client, entity_type, visible)
    if full:
        merged = dict(full)
        # Dados da tabela podem conter aliases/URLs de capa que nao estao na ficha completa.
        for key, value in visible.items():
            if not _is_missing(value) or key not in merged:
                merged.setdefault(key, value)
        if not _is_missing(visible.get("cover_url")):
            merged["cover_url"] = visible.get("cover_url")
    else:
        merged = visible
    _enrich_supplier_name(client, merged)
    if entity_type == "supplier":
        _enrich_supplier_relations(client, merged)
    _derived_fields(merged, entity_type)
    return entity_type, merged


def _asset_url(client: Any, asset: dict) -> str:
    external = _text_value(asset.get("external_url"))
    if external:
        return external
    bucket = _text_value(asset.get("storage_bucket"))
    path = _text_value(asset.get("storage_path"))
    if not client or not bucket or not path:
        return ""
    try:
        response = client.storage.from_(bucket).create_signed_url(path, 3600)
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            return _text_value(response.get("signedURL") or response.get("signedUrl") or response.get("signed_url"))
        return _text_value(
            getattr(response, "signedURL", None)
            or getattr(response, "signedUrl", None)
            or getattr(response, "signed_url", None)
        )
    except Exception:
        return ""


def _looks_like_external_photo(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = (parsed.netloc or "").casefold()
    path = (parsed.path or "").casefold()
    query = (parsed.query or "").casefold()
    if not host or "supabase" in host or "streamlit" in host:
        return False
    if any(token in path or token in query for token in ("rendered_page", "rendered-pages", "/pages/", "slide_render", "page_render")):
        return False
    image_ext = path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"))
    image_query = any(token in query for token in ("image", "img", "webp", "jpg", "jpeg", "png"))
    common_photo_hosts = (
        "wikimedia.org", "squarespace-cdn.com", "cloudfront.net",
        "googleusercontent.com", "images.", "imagekit", "cdn",
    )
    return image_ext or image_query or any(token in host or token in path for token in common_photo_hosts)


def _walk_visual_urls(value: Any, *, parent_key: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_visual_urls(item, parent_key=str(key).casefold())
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _walk_visual_urls(item, parent_key=parent_key)
    elif isinstance(value, str):
        clean = value.strip()
        if not clean.startswith(("http://", "https://")):
            return
        visual = any(token in parent_key for token in ("photo", "foto", "image", "imagem", "cover", "capa", "gallery", "galeria", "visual"))
        blocked = any(token in parent_key for token in ("slide", "page", "pagina", "document", "pdf", "plan", "planta", "source_file"))
        if visual and not blocked:
            yield clean


def _visual_fallback_url(entity_type: str, record: dict) -> str:
    raw = record.get("raw_data")
    if isinstance(raw, dict):
        for key in (
            "visual_crop_url", "crop_url", "cropped_image_url",
            "product_crop_url", "activation_crop_url", "venue_crop_url",
            "cover_url", "main_image_url", "gallery_image_url", "photo_url",
            "foto_url", "official_photo_url", "imagem_url",
        ):
            value = _text_value(raw.get(key))
            if value.startswith(("http://", "https://")):
                return value
        if entity_type in {"venue", "supplier"}:
            for value in _walk_visual_urls(raw):
                if entity_type != "venue" or _looks_like_external_photo(value):
                    return value
    if entity_type == "venue":
        value = _text_value(record.get("source_image_url"))
        if value and _looks_like_external_photo(value):
            return value
    return ""


def _media_urls(client: Any, entity_type: str, record: dict, limit: int = 3) -> list[str]:
    urls: list[str] = []
    # A capa exibida na tabela tem prioridade e pode ser uma imagem representativa.
    for key in ("cover_url", "Capa"):
        cover = _text_value(record.get(key))
        if cover and cover not in urls:
            urls.append(cover)
    entity_id = _text_value(_value(record, "id", "_id", "entity_id"))
    if client and entity_id:
        try:
            assets = _response_rows(
                client.table("media_assets").select("*")
                .eq("entity_type", entity_type).eq("entity_id", entity_id)
                .order("is_primary", desc=True).order("sort_order").execute()
            )
            def rank(asset: dict) -> tuple[int, int]:
                asset_type = _text_value(asset.get("asset_type"))
                if bool(asset.get("is_primary")):
                    kind = 0
                elif asset_type == "main_image":
                    kind = 1
                elif asset_type == "gallery_image":
                    kind = 2
                else:
                    kind = 9
                return kind, int(asset.get("sort_order") or 0)
            for asset in sorted(assets, key=rank):
                asset_type = _text_value(asset.get("asset_type"))
                mime = _text_value(asset.get("mime_type"))
                if asset_type not in IMAGE_TYPES and not mime.startswith("image/"):
                    continue
                url = _asset_url(client, asset)
                if url and url not in urls:
                    urls.append(url)
                    if len(urls) >= limit:
                        return urls[:limit]
        except Exception:
            pass

    fallback = _visual_fallback_url(entity_type, record)
    if fallback and fallback not in urls and len(urls) < limit:
        urls.append(fallback)

    # Fornecedor sem logo/capa própria: usa fotos validadas do seu repertório
    # como apoio visual, sem confundir local com fornecedor.
    if client and entity_type == "supplier" and entity_id and len(urls) < limit:
        for child_type, table in (("product", "products"), ("activation", "activation_solutions")):
            try:
                children = _response_rows(
                    client.table(table).select("id,source_image_url,raw_data")
                    .eq("supplier_id", entity_id).limit(3).execute()
                )
            except Exception:
                children = []
            for child in children:
                for url in _media_urls(client, child_type, child, limit=limit):
                    if url and url not in urls:
                        urls.append(url)
                        if len(urls) >= limit:
                            return urls[:limit]
    return urls[:limit]


def _project_links(client: Any, entity_type: str, record: dict) -> list[dict]:
    entity_id = _text_value(_value(record, "id", "_id", "entity_id"))
    if not client or not entity_id:
        return []
    try:
        links = _response_rows(
            client.table("knowledge_project_links").select("project_id,relation_type,context")
            .eq("entity_type", entity_type).eq("entity_id", entity_id).limit(20).execute()
        )
        ids = [str(link.get("project_id")) for link in links if link.get("project_id")]
        if not ids:
            return []
        projects = _response_rows(client.table("projects").select("*").in_("id", ids).execute())
        by_id = {str(project.get("id")): project for project in projects if project.get("id")}
        result = []
        for link in links:
            project = by_id.get(str(link.get("project_id"))) or {}
            name = _text_value(
                project.get("name") or project.get("project_name") or project.get("event_name")
                or project.get("job_name") or project.get("title")
            )
            client_name = _text_value(
                project.get("client_name") or project.get("client") or project.get("brand")
            )
            result.append({
                "name": name or "Projeto relacionado",
                "client": client_name,
                "relation": _text_value(link.get("relation_type")),
                "context": _text_value(link.get("context")),
            })
        return result
    except Exception:
        return []


def _format_number(value: Any, decimals: int = 2) -> str:
    try:
        number = float(value)
    except Exception:
        return _text_value(value)
    if decimals == 0 or number.is_integer():
        return f"{int(round(number)):,}".replace(",", ".")
    text = f"{number:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def _formatted(record: dict, field: str) -> str:
    value = _value(record, field)
    if _is_missing(value):
        return ""
    if field in BOOL_FIELDS or isinstance(value, bool):
        return "Sim" if bool(value) else "Não"
    if field in MONEY_FIELDS:
        currency = _text_value(record.get("currency"))
        prefix = {"BRL": "R$ ", "USD": "US$ ", "EUR": "EUR "}.get(currency, "R$ " if field.startswith("default_") else "")
        return f"{prefix}{_format_number(value)}"
    if field in NUMERIC_SUFFIX:
        return f"{_format_number(value)}{NUMERIC_SUFFIX[field]}"
    if isinstance(value, (list, tuple, set)):
        return " | ".join(_text_value(item) for item in value if not _is_missing(item))
    if isinstance(value, dict):
        return " | ".join(
            f"{str(key).replace('_', ' ').strip().capitalize()}: {_text_value(item)}"
            for key, item in value.items() if not _is_missing(item)
        )
    return _text_value(value)


def _paragraph_text(value: str) -> str:
    safe = html_escape(value or "")
    safe = safe.replace("\n", "<br/>")
    return safe


def _pdf_value_markup(field: str, value: str) -> str:
    safe_value = _paragraph_text(value)
    if not value:
        return safe_value
    if field in ADDRESS_FIELDS:
        href = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(value)
        safe_href = html_escape(href, quote=True)
        return f'<link href="{safe_href}" color="#121B42"><u>{safe_value}</u></link>'
    if field in URL_FIELDS and value.startswith(("http://", "https://")):
        safe_href = html_escape(value, quote=True)
        labels = {
            "website_url": "Abrir site",
            "map_url": "Abrir mapa",
            "instagram_url": "Abrir Instagram",
            "linkedin_url": "Abrir LinkedIn",
            "source_image_url": "Abrir imagem",
        }
        label = html_escape(labels.get(field, "Abrir link"))
        return f'<link href="{safe_href}" color="#121B42"><u>{label}</u></link>'
    return safe_value


def _styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle("brand", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=8.5, leading=10.5, textColor=CYAN, alignment=TA_RIGHT),
        "cover_title": ParagraphStyle("cover_title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=27, leading=30, textColor=NAVY, spaceAfter=4 * mm),
        "cover_area": ParagraphStyle("cover_area", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=NAVY, spaceAfter=3 * mm),
        "cover_body": ParagraphStyle("cover_body", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5, leading=15, textColor=TEXT),
        "eyebrow": ParagraphStyle("eyebrow", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=8.5, leading=10, textColor=CYAN, spaceAfter=1.5 * mm),
        "item_title": ParagraphStyle("item_title", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=23, textColor=NAVY, spaceAfter=2.8 * mm),
        "description": ParagraphStyle("description", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.3, leading=14.4, textColor=TEXT),
        "section": ParagraphStyle("section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, leading=13.5, textColor=NAVY, spaceBefore=5 * mm, spaceAfter=2.5 * mm),
        "label": ParagraphStyle("label", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=7.7, leading=9, textColor=MUTED, spaceAfter=0.7 * mm),
        "value": ParagraphStyle("value", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.1, leading=13.0, textColor=TEXT),
        "value_bold": ParagraphStyle("value_bold", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=9.3, leading=13.2, textColor=NAVY),
        "small": ParagraphStyle("small", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.8, leading=10.5, textColor=MUTED),
        "metric": ParagraphStyle("metric", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=18, leading=20, textColor=NAVY, alignment=TA_CENTER),
        "metric_label": ParagraphStyle("metric_label", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.8, leading=10, textColor=MUTED, alignment=TA_CENTER),
    }


class AccentRule(Flowable):
    def __init__(self, width: float, thickness: float = 2.2):
        super().__init__()
        self.width = width
        self.height = thickness
        self.thickness = thickness

    def draw(self) -> None:
        self.canv.setStrokeColor(CYAN)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.width, 0)


class ImagePlaceholder(Flowable):
    def __init__(self, width: float, height: float, text: str = "Imagem não disponível"):
        super().__init__()
        self.width = width
        self.height = height
        self.text = text

    def draw(self) -> None:
        self.canv.setFillColor(SURFACE)
        self.canv.setStrokeColor(BORDER)
        self.canv.roundRect(0, 0, self.width, self.height, 5, fill=1, stroke=1)
        self.canv.setFillColor(MUTED)
        self.canv.setFont("Helvetica", 8)
        self.canv.drawCentredString(self.width / 2, self.height / 2 - 3, self.text)


def _download_image(source: Any, *, max_bytes: int = 12_000_000) -> bytes | None:
    if source is None:
        return None
    if isinstance(source, bytes):
        data = source
    elif isinstance(source, bytearray):
        data = bytes(source)
    else:
        text = str(source).strip()
        if not text:
            return None
        try:
            path = Path(text)
            if path.exists() and path.is_file():
                data = path.read_bytes()
            elif text.startswith(("http://", "https://")):
                request = Request(text, headers={"User-Agent": "NAVE-by-VOE/1.0"})
                with urlopen(request, timeout=6) as response:
                    length = response.headers.get("Content-Length")
                    if length and int(length) > max_bytes:
                        return None
                    data = response.read(max_bytes + 1)
                    if len(data) > max_bytes:
                        return None
            else:
                return None
        except Exception:
            return None
    try:
        image = PILImage.open(BytesIO(data))
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        elif image.mode == "L":
            image = image.convert("RGB")
        image.thumbnail((1600, 1200), PILImage.Resampling.LANCZOS)
        out = BytesIO()
        image.save(out, format="JPEG", quality=84, optimize=True)
        return out.getvalue()
    except Exception:
        return None


def _image_flowable(data: bytes, max_w: float, max_h: float) -> Image | None:
    try:
        pil = PILImage.open(BytesIO(data))
        width, height = pil.size
        if not width or not height:
            return None
        ratio = min(max_w / width, max_h / height)
        draw_w = width * ratio
        draw_h = height * ratio
        return Image(BytesIO(data), width=draw_w, height=draw_h)
    except Exception:
        return None


def _gallery_block(urls: list[str], styles: dict[str, ParagraphStyle], full_width: float) -> Table | None:
    """Galeria editorial para A4 vertical. Sem foto valida, nao cria placeholder."""
    hero_w = min(full_width, 168 * mm)
    hero_h = 82 * mm
    gutter = 4 * mm
    loaded: list[bytes] = []
    for url in urls[:3]:
        data = _download_image(url)
        if data:
            loaded.append(data)
    if not loaded:
        return None

    hero = _image_flowable(loaded[0], hero_w - 4, hero_h - 4)
    if hero is None:
        return None
    hero_cell = Table([[hero]], colWidths=[hero_w], rowHeights=[hero_h])
    hero_cell.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER), ("BACKGROUND", (0, 0), (-1, -1), WHITE),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    content: list[list[Any]] = [[hero_cell]]

    extras = loaded[1:3]
    if extras:
        if len(extras) == 1:
            thumb_w = hero_w
            thumb_h = 35 * mm
            thumb = _image_flowable(extras[0], thumb_w - 3, thumb_h - 3)
            if thumb is not None:
                thumb_table = Table([[thumb]], colWidths=[thumb_w], rowHeights=[thumb_h])
                thumb_table.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]))
                content.append([thumb_table])
        else:
            thumb_w = (hero_w - gutter) / 2
            thumb_h = 31 * mm
            thumbs = [
                _image_flowable(data, thumb_w - 3, thumb_h - 3)
                for data in extras
            ]
            if all(thumb is not None for thumb in thumbs):
                thumb_table = Table([thumbs], colWidths=[thumb_w, thumb_w], rowHeights=[thumb_h])
                thumb_table.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), gutter),
                    ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]))
                content.append([thumb_table])

    outer = Table(content, colWidths=[hero_w], hAlign="LEFT")
    outer.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return outer


def _field_card(label: str, value: str, styles: dict[str, ParagraphStyle], width: float) -> Table:
    table = Table([
        [Paragraph(_paragraph_text(label.upper()), styles["label"])],
        [Paragraph(_paragraph_text(value), styles["value_bold"])],
    ], colWidths=[width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _key_fields_table(entity_type: str, record: dict, styles: dict[str, ParagraphStyle], width: float) -> Table:
    cards = []
    for field, label in KEY_FIELDS.get(entity_type, []):
        value = _formatted(record, field)
        if value:
            cards.append(_field_card(label, value, styles, (width - 4 * mm) / 2))
    if not cards:
        return Table([[Paragraph("A ficha ainda possui poucas informações estruturadas.", styles["small"]) ]], colWidths=[width])
    rows = []
    for i in range(0, len(cards), 2):
        pair = cards[i:i + 2]
        if len(pair) == 1:
            pair.append(Spacer((width - 4 * mm) / 2, 1))
        rows.append(pair)
    table = Table(rows, colWidths=[(width - 4 * mm) / 2, (width - 4 * mm) / 2], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _detail_section(title: str, fields: list[tuple[str, str]], record: dict, styles: dict[str, ParagraphStyle], full_width: float) -> list[Any]:
    available: list[tuple[str, str, str]] = []
    for field, label in fields:
        value = _formatted(record, field)
        if value:
            available.append((field, label, value))
    if not available:
        return []
    elements: list[Any] = [Paragraph(_paragraph_text(title), styles["section"])]
    data = []
    for field, label, value in available:
        data.append([
            Paragraph(_paragraph_text(label), styles["label"]),
            Paragraph(_pdf_value_markup(field, value), styles["value"]),
        ])
    table = Table(data, colWidths=[42 * mm, full_width - 42 * mm], hAlign="LEFT", repeatRows=0)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    elements.append(table)
    return elements


def _projects_section(projects: list[dict], styles: dict[str, ParagraphStyle], full_width: float) -> list[Any]:
    if not projects:
        return []
    elements: list[Any] = [Paragraph("Projetos relacionados", styles["section"])]
    rows = []
    for project in projects[:6]:
        name = _text_value(project.get("name")) or "Projeto relacionado"
        client = _text_value(project.get("client"))
        relation = _text_value(project.get("relation"))
        context = _text_value(project.get("context"))
        meta = " | ".join(value for value in (client, relation) if value)
        content = f"<b>{_paragraph_text(name)}</b>"
        if meta:
            content += f"<br/><font color='#687188'>{_paragraph_text(meta)}</font>"
        if context:
            content += f"<br/>{_paragraph_text(context)}"
        rows.append([Paragraph(content, styles["value"])])
    table = Table(rows, colWidths=[full_width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)
    return elements


def _logo_flowable(max_w: float = 54 * mm, max_h: float = 20 * mm) -> Image | None:
    """Renderiza o lockup oficial já existente em assets/nave_lockup.svg.

    PyMuPDF já faz parte do ambiente da NAVE. Se o SVG não estiver disponível
    ou não puder ser rasterizado, a capa mantém um fallback tipográfico.
    """
    logo_path = Path(__file__).resolve().parent / "assets" / "nave_lockup.svg"
    if not logo_path.exists():
        return None
    try:
        import pymupdf

        svg_doc = pymupdf.open(str(logo_path))
        page = svg_doc[0]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2.4, 2.4), alpha=True)
        png = pix.tobytes("png")
        return _image_flowable(png, max_w, max_h)
    except Exception:
        return None


def _logo_cover_block(styles: dict[str, ParagraphStyle], content_w: float) -> Table:
    logo = _logo_flowable()
    if logo is not None:
        content: Any = logo
    else:
        content = Paragraph("<b>NAVE</b> by VOE", styles["cover_area"])
    block = Table([[content]], colWidths=[content_w], hAlign="LEFT")
    block.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return block


def _cover_header(styles: dict[str, ParagraphStyle], content_w: float) -> Table:
    logo = _logo_flowable(max_w=58 * mm, max_h=18 * mm)
    left: Any = logo if logo is not None else Paragraph("<b>NAVE by VOE</b>", styles["cover_area"])
    right = Paragraph("EXPORTAÇÃO DE REPERTÓRIO", styles["brand"])
    table = Table([[left, right]], colWidths=[content_w * 0.62, content_w * 0.38], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def _footer(canvas: Any, doc: Any) -> None:
    page_w, _ = A4
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(16 * mm, 10.5 * mm, page_w - 16 * mm, 10.5 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 6.3)
    footer = (
        "NAVE by VOE | Conectando briefing, repertório e decisão. | "
        "Documento de uso interno. © 2026 VOE. Todos os direitos reservados."
    )
    canvas.drawString(16 * mm, 6.2 * mm, footer)
    canvas.setFont("Helvetica", 6.5)
    canvas.drawRightString(page_w - 16 * mm, 3.8 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _cover_story(
    source_context: str,
    item_count: int,
    item_names: list[str],
    styles: dict[str, ParagraphStyle],
    content_w: float,
) -> list[Any]:
    generated = datetime.now().strftime("%d/%m/%Y - %H:%M")
    items_word = "item selecionado" if item_count == 1 else "itens selecionados"
    title_map = {
        "Brindes": "Seleção de Brindes",
        "Ativações": "Seleção de Ativações",
        "Ativacoes": "Seleção de Ativações",
        "Locais e espaços": "Seleção de Locais e espaços",
        "Locais e espacos": "Seleção de Locais e espaços",
        "Fornecedores": "Seleção de Fornecedores",
        "Base de Conhecimento": "Seleção da Base de Conhecimento",
    }
    cover_title = title_map.get(source_context, f"Seleção - {source_context}")
    story: list[Any] = [
        Spacer(1, 3 * mm),
        _cover_header(styles, content_w),
        Spacer(1, 12 * mm),
        Paragraph(_paragraph_text(cover_title), styles["cover_title"]),
        AccentRule(48 * mm),
        Spacer(1, 6 * mm),
        Paragraph("Caderno de possibilidades e referências", styles["cover_area"]),
        Paragraph(
            _paragraph_text(
                f"Origem da exportação: {source_context}. "
                f"{_source_descriptor(source_context)}."
            ),
            styles["cover_body"],
        ),
        Spacer(1, 8 * mm),
        Table([
            [Paragraph(str(item_count), styles["metric"]), Paragraph(_paragraph_text(generated), styles["metric"])],
            [Paragraph(items_word, styles["metric_label"]), Paragraph("data de exportação", styles["metric_label"])],
        ], colWidths=[52 * mm, 64 * mm], rowHeights=[12 * mm, 8 * mm], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])),
    ]

    clean_names = [name for name in item_names if name][:8]
    if clean_names:
        story.extend([Spacer(1, 7 * mm), Paragraph("ITENS DESTA SELEÇÃO", styles["eyebrow"])])
        rows = []
        for index in range(0, len(clean_names), 2):
            pair = clean_names[index:index + 2]
            cells = []
            for offset, name in enumerate(pair):
                number = index + offset + 1
                cells.append(Paragraph(f"<b>{number:02d}</b>  {_paragraph_text(name)}", styles["value"]))
            if len(cells) == 1:
                cells.append(Paragraph("", styles["value"]))
            rows.append(cells)
        table = Table(rows, colWidths=[content_w / 2, content_w / 2])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFBFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
        if item_count > len(clean_names):
            story.append(Paragraph(f"+ {item_count - len(clean_names)} item(ns) adicionais", styles["small"]))

    story.extend([
        Spacer(1, 7 * mm),
        Table([[Paragraph(
            "Documento gerado automaticamente a partir do repertório cadastrado na NAVE. "
            "As fotos são ajustadas proporcionalmente para o relatório e somente informações disponíveis no momento da exportação são exibidas.",
            styles["small"],
        )]], colWidths=[content_w], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFBFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])),
    ])
    return story


def _item_story(index: int, entity_type: str, record: dict, image_urls: list[str], projects: list[dict], source_context: str, styles: dict[str, ParagraphStyle], content_w: float) -> list[Any]:
    name = _text_value(_value(record, "name", "Brinde", "Ativação", "Ativacao", "Local", "Fornecedor")) or f"Item {index}"
    type_label = ENTITY_LABELS.get(entity_type, "Possibilidade")
    description = _formatted(record, "description") or _formatted(record, "notes")

    elements: list[Any] = [
        Paragraph(_paragraph_text(type_label.upper()), styles["eyebrow"]),
        Paragraph(_paragraph_text(name), styles["item_title"]),
        AccentRule(38 * mm, 1.7),
        Spacer(1, 7 * mm),
    ]

    gallery = _gallery_block(image_urls, styles, content_w)
    if gallery is not None:
        elements.append(gallery)
        elements.append(Spacer(1, 7 * mm))

    key_table = _key_fields_table(entity_type, record, styles, content_w)
    elements.extend([Paragraph("Informações principais", styles["section"]), key_table])

    if description:
        elements.extend([
            Spacer(1, 4 * mm),
            Paragraph("Visão geral", styles["section"]),
            Table([[Paragraph(_paragraph_text(description), styles["description"]) ]], colWidths=[content_w], style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFBFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ])),
        ])

    key_names = {field for field, _ in KEY_FIELDS.get(entity_type, [])}
    for title, fields in SECTIONS.get(entity_type, []):
        detail_fields = [(field, label) for field, label in fields if field not in key_names]
        elements.extend(_detail_section(title, detail_fields, record, styles, content_w))
    elements.extend(_projects_section(projects, styles, content_w))
    return elements


def build_selection_pdf(*args: Any, **kwargs: Any) -> bytes:
    """Gera o caderno PDF mantendo compatibilidade com chamadas legadas.

    Aceita listas/DataFrames em argumentos posicionais ou em ``selected_records``.
    Keywords extras sao ignoradas quando nao fazem parte do layout atual.
    """
    raw_rows = _first_rows(args, kwargs)
    source_context = _infer_source_context(raw_rows, kwargs.get("source_context") or kwargs.get("area") or kwargs.get("export_area"))
    title = str(kwargs.get("title") or kwargs.get("document_title") or "Selecao de possibilidades - NAVE by VOE")

    client = _safe_client()
    enriched: list[tuple[str, dict, list[str], list[dict]]] = []
    for raw in raw_rows:
        entity_type, record = _merge_record(client, raw)
        images = _media_urls(client, entity_type, record, limit=3) if entity_type != "item" else []
        projects = _project_links(client, entity_type, record) if entity_type != "item" else []
        enriched.append((entity_type, record, images, projects))

    page_size = A4
    buffer = BytesIO()
    left_margin = 16 * mm
    right_margin = 16 * mm
    top_margin = 14 * mm
    bottom_margin = 16 * mm
    content_w = page_size[0] - left_margin - right_margin
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=right_margin,
        leftMargin=left_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
        title=title,
        author="NAVE by VOE",
        subject=f"Selecao exportada de {source_context}",
    )
    styles = _styles()
    item_names = [
        _text_value(_value(record, "name", "Brinde", "Ativação", "Ativacao", "Local", "Fornecedor"))
        or f"Item {index}"
        for index, (_, record, _, _) in enumerate(enriched, start=1)
    ]
    story: list[Any] = _cover_story(source_context, len(enriched), item_names, styles, content_w)

    if not enriched:
        story.extend([Spacer(1, 8 * mm), Paragraph("Nenhum item foi selecionado.", styles["cover_body"])])
    else:
        for index, (entity_type, record, image_urls, projects) in enumerate(enriched, start=1):
            story.append(PageBreak())
            story.extend(_item_story(index, entity_type, record, image_urls, projects, source_context, styles, content_w))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
