"""
Correção global dos filtros de locais da NAVE by VOE.

Objetivos:
- usar GRUPO_LOCAL como chave canônica de filtro;
- aceitar registros legados classificados por TIPO_LOCAL_PADRONIZADO/CATEGORIA;
- normalizar caixa, acentos, espaços e variações de singular/plural;
- pesquisar em nome, descrição, cidade, estado, endereço, categoria e aliases;
- preservar registros não classificados em "Todos" e "Tipo não definido";
- impedir que o filtro de acervo altere indevidamente o filtro de tipo.

Integração esperada:
    from venue_filter_patch import (
        TYPE_OPTIONS,
        filter_venues,
        option_code,
    )

    selected_label = st.selectbox("Tipo de local", list(TYPE_OPTIONS))
    selected_code = option_code(selected_label)

    filtered = filter_venues(
        venues,
        search=search_term,
        type_code=selected_code,
        state=selected_state,
        collection=selected_collection,
    )
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
import re
import unicodedata


TYPE_OPTIONS: dict[str, str | None] = {
    "Todos": None,
    "Galpões / fábricas": "industrial",
    "Centros de convenções / pavilhões": "convencoes_pavilhoes",
    "Espaços de eventos": "espacos_eventos",
    "Casas de show": "casas_show",
    "Teatros / auditórios": "teatros_auditorios",
    "Hotéis": "hoteis",
    "Bares": "bares",
    "Restaurantes": "restaurantes",
    "Galerias de arte": "galerias_arte",
    "Estádios e arenas": "estadios",
    "Tipo não definido": "__undefined__",
}

# Compatibilidade com rótulos antigos ou usados em outras telas.
LEGACY_OPTION_LABELS: dict[str, str | None] = {
    "Estádios": "estadios",
    "Estadios": "estadios",
    "Centro de convenções / pavilhão": "convencoes_pavilhoes",
    "Centro de convenções/ pavilhão": "convencoes_pavilhoes",
    "Galpão / fábrica": "industrial",
    "Espaço de eventos": "espacos_eventos",
    "Casa de show": "casas_show",
    "Teatro / auditório": "teatros_auditorios",
    "Galeria de arte": "galerias_arte",
}

TYPE_ALIASES: dict[str, set[str]] = {
    "industrial": {
        "galpao", "galpoes", "fabrica", "fabricas", "warehouse",
        "industrial", "estudio", "estudios", "hangar",
    },
    "convencoes_pavilhoes": {
        "centro de convencoes", "centros de convencoes",
        "pavilhao", "pavilhoes", "expo center", "centro de exposicoes",
        "feira", "feiras", "convention center", "exhibition hall",
    },
    "espacos_eventos": {
        "espaco de eventos", "espacos de eventos", "casa de eventos",
        "casas de eventos", "event space", "event venue", "salao de eventos",
    },
    "casas_show": {
        "casa de show", "casas de show", "show house", "concert hall",
        "venue musical", "musica ao vivo",
    },
    "teatros_auditorios": {
        "teatro", "teatros", "auditorio", "auditorios", "cinema",
        "cinemas", "plenaria", "sala de plenaria",
    },
    "hoteis": {
        "hotel", "hoteis", "resort", "resorts", "ballroom",
        "centro de eventos de hotel",
    },
    "bares": {
        "bar", "bares", "pub", "pubs", "boteco", "bares e pubs",
    },
    "restaurantes": {
        "restaurante", "restaurantes", "gastronomico", "gastronomia",
        "restaurant",
    },
    "galerias_arte": {
        "galeria de arte", "galerias de arte", "galeria", "galerias",
        "museu", "museus", "espaco cultural", "centro cultural",
    },
    "estadios": {
        "estadio", "estadios", "arena", "arenas", "arena esportiva",
        "complexo esportivo", "estadio de futebol", "sports arena",
        "stadium",
    },
}

# Valores formais que já aparecem na base mestra.
FORMAL_VALUE_TO_CODE: dict[str, str] = {
    "galpao fabrica": "industrial",
    "centro de convencoes pavilhao": "convencoes_pavilhoes",
    "espaco de eventos": "espacos_eventos",
    "casas de show": "casas_show",
    "teatros auditorios": "teatros_auditorios",
    "hoteis": "hoteis",
    "bares": "bares",
    "restaurantes": "restaurantes",
    "galerias de arte": "galerias_arte",
    "estadios": "estadios",
}


def normalize_text(value: Any) -> str:
    """Normaliza texto para comparação: minúsculas, sem acento e sem pontuação."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text or text in {"nan", "none", "null", "nao informado", "não informado"}:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def option_code(label_or_code: str | None) -> str | None:
    """Converte rótulo da interface em código canônico."""
    if label_or_code is None:
        return None

    if label_or_code in TYPE_OPTIONS:
        return TYPE_OPTIONS[label_or_code]
    if label_or_code in LEGACY_OPTION_LABELS:
        return LEGACY_OPTION_LABELS[label_or_code]

    normalized = normalize_text(label_or_code)

    # Também aceita os mesmos rótulos com diferenças de caixa e acentuação.
    for label, code in TYPE_OPTIONS.items():
        if normalized == normalize_text(label):
            return code
    for label, code in LEGACY_OPTION_LABELS.items():
        if normalized == normalize_text(label):
            return code

    # O próprio código já pode ter sido recebido.
    for code in TYPE_ALIASES:
        if normalized == normalize_text(code):
            return code

    # Rótulo formal ou alias.
    if normalized in FORMAL_VALUE_TO_CODE:
        return FORMAL_VALUE_TO_CODE[normalized]

    for code, aliases in TYPE_ALIASES.items():
        if normalized in {normalize_text(alias) for alias in aliases}:
            return code

    return None


def _value(record: Mapping[str, Any], *keys: str) -> Any:
    """Busca um campo tolerando maiúsculas/minúsculas e variações simples."""
    normalized_keys = {normalize_text(key).replace(" ", "_") for key in keys}
    for key, value in record.items():
        normalized_key = normalize_text(key).replace(" ", "_")
        if normalized_key in normalized_keys:
            return value
    return None


def canonical_type(record: Mapping[str, Any]) -> str | None:
    """
    Resolve o tipo de local.

    Ordem de confiança:
    1. GRUPO_LOCAL;
    2. TIPO_LOCAL_PADRONIZADO;
    3. CATEGORIA;
    4. inferência segura por nome/descrição, apenas para registros sem tipo.
    """
    group = _value(record, "GRUPO_LOCAL", "grupo_local", "type_group", "type_code")
    group_code = option_code(str(group)) if group is not None else None
    if group_code:
        return group_code

    for key in (
        "TIPO_LOCAL_PADRONIZADO",
        "tipo_local_padronizado",
        "TIPO_LOCAL",
        "tipo_local",
        "CATEGORIA",
        "categoria",
    ):
        raw = _value(record, key)
        raw_norm = normalize_text(raw)
        if not raw_norm:
            continue

        if raw_norm in FORMAL_VALUE_TO_CODE:
            return FORMAL_VALUE_TO_CODE[raw_norm]

        for code, aliases in TYPE_ALIASES.items():
            normalized_aliases = {normalize_text(alias) for alias in aliases}
            if raw_norm in normalized_aliases:
                return code

    # Fallback seguro somente para cadastros não classificados.
    inference_text = " ".join(
        normalize_text(_value(record, key))
        for key in (
            "LOCAL", "local", "NOME", "nome", "title",
            "DESCRICAO_NAVE", "descricao_nave", "DESCRICAO", "descricao",
        )
    ).strip()

    if not inference_text:
        return None

    # Termos mais específicos primeiro.
    ordered_codes = (
        "convencoes_pavilhoes",
        "teatros_auditorios",
        "galerias_arte",
        "casas_show",
        "espacos_eventos",
        "estadios",
        "industrial",
        "hoteis",
        "restaurantes",
        "bares",
    )
    for code in ordered_codes:
        for alias in sorted(TYPE_ALIASES[code], key=len, reverse=True):
            alias_norm = normalize_text(alias)
            if alias_norm and re.search(rf"\b{re.escape(alias_norm)}\b", inference_text):
                return code

    return None


def searchable_text(record: Mapping[str, Any]) -> str:
    """Monta o índice textual de um local."""
    fields = (
        "LOCAL", "local", "NOME", "nome", "title",
        "DESCRICAO_NAVE", "descricao_nave", "DESCRICAO", "descricao",
        "CIDADE", "cidade", "ESTADO", "estado", "ENDERECO", "endereco",
        "ENDEREÇO", "CEP", "cep", "CATEGORIA", "categoria",
        "TIPO_LOCAL_PADRONIZADO", "tipo_local_padronizado",
        "GRUPO_LOCAL", "grupo_local", "TAGS", "tags", "ALIASES", "aliases",
        "OBS", "obs",
    )
    parts: list[str] = []
    for field in fields:
        value = _value(record, field)
        if isinstance(value, (list, tuple, set)):
            parts.extend(normalize_text(item) for item in value)
        else:
            parts.append(normalize_text(value))

    type_code = canonical_type(record)
    if type_code:
        parts.append(type_code)
        parts.extend(normalize_text(alias) for alias in TYPE_ALIASES[type_code])

    return " ".join(part for part in parts if part)


def _has_collection(record: Mapping[str, Any]) -> bool:
    """Detecta presença de acervo sem acoplar a um único schema."""
    for key in (
        "media_count", "MEDIA_COUNT", "image_count", "IMAGE_COUNT",
        "document_count", "DOCUMENT_COUNT", "asset_count", "ASSET_COUNT",
    ):
        raw = _value(record, key)
        try:
            if raw is not None and int(raw) > 0:
                return True
        except (TypeError, ValueError):
            pass

    for key in (
        "has_primary", "HAS_PRIMARY", "has_media", "HAS_MEDIA",
        "com_acervo", "COM_ACERVO",
    ):
        raw = normalize_text(_value(record, key))
        if raw in {"true", "1", "sim", "yes"}:
            return True

    for key in (
        "FOTO_URL_APROVADA", "foto_url_aprovada", "ARQUIVO_VISUAL",
        "arquivo_visual", "PLANTA_BAIXA_URL", "planta_baixa_url",
        "GALERIA_FOTOS_URL", "galeria_fotos_url",
        "BOOK_FICHA_TECNICA_URL", "book_ficha_tecnica_url",
    ):
        if normalize_text(_value(record, key)):
            return True

    return False


def filter_venues(
    records: Iterable[Mapping[str, Any]],
    *,
    search: str | None = None,
    type_code: str | None = None,
    state: str | None = None,
    collection: str | None = None,
) -> list[dict[str, Any]]:
    """
    Filtra locais sem depender de igualdade literal entre rótulo e categoria.

    `type_code` aceita tanto código canônico quanto rótulo de interface.
    """
    resolved_type = option_code(type_code) if type_code else None
    if type_code == "__undefined__":
        resolved_type = "__undefined__"

    normalized_search = normalize_text(search)
    search_tokens = [token for token in normalized_search.split() if token]

    normalized_state = normalize_text(state)
    if normalized_state in {"", "todos", "todas", "all"}:
        normalized_state = ""

    normalized_collection = normalize_text(collection)
    collection_mode = "all"
    if normalized_collection in {
        "com acervo", "com midia", "com mídia", "with media", "com arquivos",
    }:
        collection_mode = "with"
    elif normalized_collection in {
        "sem acervo", "sem midia", "sem mídia", "without media", "sem arquivos",
    }:
        collection_mode = "without"

    result: list[dict[str, Any]] = []

    for source_record in records:
        record = dict(source_record)
        record_type = canonical_type(record)

        if resolved_type == "__undefined__":
            if record_type is not None:
                continue
        elif resolved_type and record_type != resolved_type:
            continue

        if normalized_state:
            record_state = normalize_text(_value(record, "ESTADO", "estado", "UF", "uf"))
            if record_state != normalized_state:
                continue

        if collection_mode == "with" and not _has_collection(record):
            continue
        if collection_mode == "without" and _has_collection(record):
            continue

        if search_tokens:
            haystack = searchable_text(record)
            # Todos os termos digitados precisam aparecer em algum campo,
            # mas não necessariamente no mesmo campo.
            if not all(token in haystack for token in search_tokens):
                continue

        record["_canonical_type"] = record_type
        result.append(record)

    return result
