from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from document_io import InputDocument
from supplier_geography import is_country_name


MISSING_MARKERS = {
    "", "-", "--", ".", "n/a", "na", "n.a", "s/n", "sn", "none", "null",
    "nao informado", "não informado", "nao se aplica", "não se aplica",
    "sem informacao", "sem informação", "indisponivel", "indisponível",
}

BRAZIL_STATE_TO_UF = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM",
    "bahia": "BA", "ceara": "CE", "distrito federal": "DF",
    "espirito santo": "ES", "goias": "GO", "maranhao": "MA",
    "mato grosso": "MT", "mato grosso do sul": "MS", "minas gerais": "MG",
    "para": "PA", "paraiba": "PB", "parana": "PR", "pernambuco": "PE",
    "piaui": "PI", "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR",
    "santa catarina": "SC", "sao paulo": "SP", "sergipe": "SE",
    "tocantins": "TO",
}
UF_VALUES = set(BRAZIL_STATE_TO_UF.values())

CATEGORY_FAMILY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Produção física / PDV / cenografia", (
        "comunicacao visual", "cenografia", "marcenaria", "serralheria",
        "grafica", "impressao", "display", "acrilico", "fachada",
        "fornecedor de materiais", "pdv", "mobiliario promocional",
    )),
    ("Brindes / produtos promocionais", (
        "brinde", "produto promocional", "presente corporativo", "press kit",
        "welcome kit", "uniforme", "kit corporativo",
    )),
    ("Tecnologia / digital", (
        "tecnologia", "digital", "software", "sistema", "aplicativo",
        "hotsite", "game", "gamificacao", "interativo", "plataforma",
    )),
    ("Audiovisual / conteúdo / artístico", (
        "audiovisual", "video", "audio", "iluminacao", "produtora", "artista",
        "musica", "conteudo",
    )),
    ("Operação de eventos", (
        "staff", "promotor", "credenciamento", "rsvp", "controle de acesso",
        "catering", "alimentacao", "beleza", "seguro", "operacao de evento",
    )),
    ("Logística / montagem / rollout", (
        "logistica", "instalacao", "montagem", "desmontagem", "rollout",
        "armazenagem", "manutencao", "atendimento emergencial",
    )),
    ("Locação / infraestrutura", (
        "locacao", "aluguel de mobiliario", "aluguel de equipamentos", "infraestrutura",
    )),
]

# Campos de primeira classe. Cabeçalhos desconhecidos continuam preservados em
# profile_data; portanto este mapa não é uma exigência de template.
HEADER_ALIASES: dict[str, str] = {
    "razao social": "legal_name",
    "nome fantasia": "trade_name",
    "nome da empresa": "trade_name",
    "nome do fornecedor": "trade_name",
    "fornecedor": "trade_name",
    "parceiro": "trade_name",
    "cnpj": "cnpj",
    "inscricao estadual municipal": "state_municipal_registration",
    "inscricao estadual": "state_municipal_registration",
    "inscricao municipal": "state_municipal_registration",
    "ano de fundacao": "founded_year",
    "tipo de empresa": "company_type",
    "endereco completo": "address",
    "complemento do endereco": "address_complement",
    "cidade estado": "city_state",
    "cidade": "base_city",
    "municipio": "base_city",
    "estado": "base_state",
    "uf": "base_state",
    "pais": "base_country",
    "contato principal nome cargo": "contact",
    "contato": "contact_name",
    "cargo": "contact_role",
    "telefone": "phone",
    "e mail": "email",
    "email": "email",
    "site": "website_url",
    "website": "website_url",
    "tipo de fornecedor": "supplier_types",
    "principais segmentos atendidos": "market_segments",
    "principais clientes marcas atendidas": "client_brands",
    "diferencial competitivo declarado": "differentiators",
    "possui alguma certificacao": "certifications",
    "tempo de experiencia com agencias": "agency_experience",
    "ja atendeu alguma agencia do grupo 4zero4": "group_404_experience",
    "capacidade de pico": "peak_capacity",
    "producao interna": "production_internal_pct",
    "producao terceirizada": "production_outsourced_pct",
    "lead time medio por tipo de material": "lead_time",
    "principais gargalos produtivos": "production_bottlenecks",
    "area total m2": "facility_total_area",
    "pe direito": "facility_ceiling_height",
    "area de marcenaria": "facility_carpentry_area",
    "area de serralheria": "facility_metalwork_area",
    "area de impressao": "facility_print_area",
    "area de montagem pre montagem": "facility_assembly_area",
    "area de estoque": "facility_storage_area",
    "possui doca para carga descarga": "facility_loading_dock",
    "numero total de colaboradores": "team_total",
    "equipe fixa": "team_fixed",
    "freelancers terceiros": "team_third_party",
    "possui responsavel tecnico": "technical_manager",
    "estrutura tecnica disponivel": "technical_structure",
    "impressao digital tipo largura tecnologia": "equipment_printing",
    "cnc router area util espessura max": "equipment_cnc",
    "laser co2 fibra area util": "equipment_laser",
    "dobradeira calandra": "equipment_bending",
    "tipo de solda": "equipment_welding",
    "tipo de pintura": "equipment_painting",
    "corte e vinco": "equipment_cutting",
    "laminacao acabamento": "equipment_finishing",
    "softwares utilizados": "software_tools",
    "marque as especialidades que sao atendidas pela sua empresa": "specialties",
    "marque os servicos que sao oferecidos pela sua empresa": "services_offered",
    "atende nivel nacional": "serves_nationally",
    "estados atendidos diretamente": "direct_states",
    "estados via parceiros": "partner_states",
    "possui equipe propria de instalacao": "own_installation_team",
    "capacidade de rollout simultaneo": "rollout_capacity",
    "possui controle de qualidade": "quality_control",
    "etapas de checagem antes da entrega": "quality_checks",
    "politica de retrabalho": "rework_policy",
    "aceita visita tecnica da agencia": "accepts_technical_visit",
    "emite nf": "emits_invoice",
    "a empresa possui algum beneficio fiscal vigente": "tax_benefits",
    "a empresa trabalha com credito de icms ipi pis cofins": "tax_credits",
    "em qual regime tributario esta a sua empresa": "tax_regime",
    "praticas de sustentabilidade": "sustainability_practices",
    "possui termo de garantia": "has_warranty",
    "qual tempo de garantia concedido para o cliente": "warranty_terms",
    "forma de pagamento padrao": "payment_method",
    "prazo medio de pagamento aceito": "payment_terms",
    "flexibilidade para grandes volumes": "large_volume_flexibility",
    "trabalha com contrato": "works_with_contract",
}


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).casefold().strip()
    return " ".join(text.split())


def clean_value(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).replace("\u00a0", " ").strip()
    if normalize_text(text) in MISSING_MARKERS:
        return None
    return text or None


def split_values(value: Any) -> list[str]:
    text = clean_value(value)
    if not text:
        return []
    chunks = [item.strip() for item in re.split(r"[;|\n]+", text) if item.strip()]
    if len(chunks) == 1 and "," in text and not re.search(r"\b[A-Z]{2}\s*$", text):
        chunks = [item.strip() for item in text.split(",") if item.strip()]
    result: list[str] = []
    seen: set[str] = set()
    for item in chunks:
        marker = normalize_text(item)
        if not marker or marker in MISSING_MARKERS or marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def parse_bool(value: Any) -> bool | None:
    text = clean_value(value)
    if not text:
        return None
    key = normalize_text(text)
    if key.startswith(("sim", "yes", "possui", "tem")):
        return True
    if key.startswith(("nao", "no", "não")):
        return False
    return None


def parse_percentage(value: Any) -> float | None:
    text = clean_value(value)
    if not text:
        return None
    match = re.search(r"-?\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    try:
        number = float(match.group(0).replace(",", "."))
    except ValueError:
        return None
    if 0 <= number <= 100:
        return number
    return None


def parse_int(value: Any) -> int | None:
    text = clean_value(value)
    if not text:
        return None
    match = re.search(r"\b(\d{1,6})\b", text.replace(".", ""))
    return int(match.group(1)) if match else None


def normalize_cnpj(value: Any) -> str | None:
    text = clean_value(value)
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    return digits if len(digits) == 14 else None


def _state_value(value: str) -> str | None:
    key = normalize_text(value)
    if key.upper() in UF_VALUES:
        return key.upper()
    if key in BRAZIL_STATE_TO_UF:
        return BRAZIL_STATE_TO_UF[key]
    match = re.search(r"\(([A-Za-z]{2})\)", value)
    if match and match.group(1).upper() in UF_VALUES:
        return match.group(1).upper()
    text = str(value).strip().upper()
    return text if text in UF_VALUES else None


def parse_states(value: Any) -> list[str]:
    result: list[str] = []
    for item in split_values(value):
        key = normalize_text(item)
        if key in {"todos", "todo brasil", "brasil", "nacional"}:
            continue
        state = _state_value(item)
        if state and state not in result:
            result.append(state)
    return result


def parse_city_state(value: Any) -> tuple[str | None, str | None]:
    text = clean_value(value)
    if not text or is_country_name(text):
        return None, None
    municipality = re.search(
        r"munic[ií]pio\s+(.+?)\s+uf\s+([a-z]{2})\b",
        text,
        flags=re.IGNORECASE,
    )
    if municipality:
        return municipality.group(1).strip(" -/,"), municipality.group(2).upper()
    for pattern in (
        r"^(.+?)\s*[—–-]\s*([A-Za-z]{2})\s*$",
        r"^(.+?)\s*,\s*([A-Za-z]{2})\s*$",
        r"^(.+?)\s+([A-Za-z]{2})\s*$",
    ):
        match = re.match(pattern, text)
        if match and match.group(2).upper() in UF_VALUES:
            return match.group(1).strip(" -/,"), match.group(2).upper()
    full_state = re.match(r"^(.+?)\s*[,/—–-]\s*([A-Za-zÀ-ÿ ]+)\s*$", text)
    if full_state:
        state = _state_value(full_state.group(2))
        if state:
            return full_state.group(1).strip(" -/,"), state
    # Cidade sem UF é válida; não inventamos o estado.
    if len(text) > 2:
        return text.strip(), None
    return None, None


def split_contact(value: Any) -> tuple[str | None, str | None]:
    text = clean_value(value)
    if not text:
        return None, None
    for separator in (" - ", " / ", " – ", " — "):
        if separator in text:
            left, right = text.split(separator, 1)
            return clean_value(left), clean_value(right)
    return text, None


def _header_key(header: Any) -> str:
    key = normalize_text(header)
    # Forms/Excel sometimes suffix duplicate prompts with 2, .1 etc.
    key = re.sub(r"\s+\d+$", "", key).strip()
    return key


def map_header(header: Any) -> str | None:
    key = _header_key(header)
    if key in HEADER_ALIASES:
        return HEADER_ALIASES[key]
    # Tolerant semantic fallbacks. Unknown columns are never discarded.
    if "cnpj" in key:
        return "cnpj"
    if "razao social" in key:
        return "legal_name"
    if "nome fantasia" in key or key in {"nome da empresa", "nome do fornecedor", "fornecedor", "parceiro"}:
        return "trade_name"
    if key in {"cidade", "municipio"}:
        return "base_city"
    if key in {"estado", "uf"}:
        return "base_state"
    if key == "pais":
        return "base_country"
    if "cidade" in key and "estado" in key:
        return "city_state"
    if "tipo" in key and "fornecedor" in key:
        return "supplier_types"
    if "especialidade" in key:
        return "specialties"
    if "servico" in key and ("ofere" in key or "empresa" in key):
        return "services_offered"
    if "estado" in key and "parceir" in key:
        return "partner_states"
    if "estado" in key and ("diret" in key or "atendid" in key):
        return "direct_states"
    if "nacional" in key and ("atende" in key or "cobertura" in key):
        return "serves_nationally"
    return None


def _profile_bucket(header: str) -> str:
    key = normalize_text(header)
    if any(token in key for token in ("cnc", "laser", "solda", "pintura", "impressao digital", "dobradeira", "calandra", "software", "corte e vinco", "laminacao")):
        return "equipamentos"
    if any(token in key for token in ("area", "pe direito", "doca", "colaborador", "equipe fixa", "freelancer", "responsavel tecnico", "estrutura tecnica")):
        return "estrutura"
    if any(token in key for token in ("capacidade", "producao", "lead time", "gargalo")):
        return "producao"
    if any(token in key for token in ("qualidade", "checagem", "retrabalho", "visita tecnica")):
        return "qualidade"
    if any(token in key for token in ("nf", "fiscal", "tribut", "icms", "ipi", "pis", "cofins")):
        return "fiscal"
    if any(token in key for token in ("sustent", "garantia")):
        return "qualidade_esg"
    if any(token in key for token in ("pagamento", "contrato", "grandes volumes")):
        return "comercial"
    if any(token in key for token in ("cliente", "marca", "segmento", "diferencial", "agencia", "certificacao")):
        return "repertorio"
    return "outros"


def _category_families(values: Iterable[Any]) -> list[str]:
    blob = normalize_text(" ".join(str(value or "") for value in values))
    categories: list[str] = []
    for label, tokens in CATEGORY_FAMILY_RULES:
        if any(token in blob for token in tokens):
            categories.append(label)
    return categories or ["Outros fornecedores"]


def _merge_profile(target: dict, incoming: dict) -> dict:
    result = dict(target or {})
    for bucket, values in (incoming or {}).items():
        if not isinstance(values, dict):
            if values not in (None, "", [], {}):
                result[bucket] = values
            continue
        current = dict(result.get(bucket) or {})
        for key, value in values.items():
            if value in (None, "", [], {}):
                continue
            if key not in current or current.get(key) in (None, "", [], {}):
                current[key] = value
            elif current[key] != value:
                existing = current[key]
                if not isinstance(existing, list):
                    existing = [existing]
                values_to_merge = value if isinstance(value, list) else [value]
                for item in values_to_merge:
                    if item not in existing:
                        existing.append(item)
                current[key] = existing
        result[bucket] = current
    return result


def merge_supplier_records(left: dict, right: dict) -> dict:
    result = dict(left)
    list_fields = {
        "supplier_categories", "specialties", "services_offered", "client_brands",
        "market_segments", "certifications", "direct_states", "partner_states",
        "served_states", "served_cities", "local_team_locations",
    }
    for key, value in right.items():
        if value in (None, "", [], {}):
            continue
        if key == "profile_data":
            result[key] = _merge_profile(result.get(key) or {}, value)
        elif key in list_fields:
            existing = list(result.get(key) or [])
            for item in list(value or []):
                if normalize_text(item) not in {normalize_text(x) for x in existing}:
                    existing.append(item)
            result[key] = existing
        elif result.get(key) in (None, "", [], {}):
            result[key] = value
        elif key == "confidence":
            result[key] = max(float(result.get(key) or 0), float(value or 0))
    return result


def _read_frames(doc: InputDocument) -> list[tuple[str, pd.DataFrame]]:
    data = doc.original_data or doc.data
    suffix = Path(doc.name).suffix.casefold()
    buffer = io.BytesIO(data)
    if suffix in {".xlsx", ".xls"}:
        sheets = pd.read_excel(buffer, sheet_name=None, dtype=str, keep_default_na=False)
        return [(str(name), df) for name, df in sheets.items()]
    if suffix in {".csv", ".tsv"}:
        sep = "\t" if suffix == ".tsv" else None
        df = pd.read_csv(buffer, sep=sep, engine="python", dtype=str, keep_default_na=False)
        return [("Planilha", df)]
    return []


def supplier_registry_score(docs: list[InputDocument]) -> float:
    score = 0.0
    best = 0.0
    for doc in docs:
        for _sheet, df in _read_frames(doc):
            headers = {_header_key(col) for col in df.columns}
            if not headers:
                continue
            signals = {
                "razao social": 0.15,
                "nome fantasia": 0.12,
                "cnpj": 0.22,
                "tipo de fornecedor": 0.18,
                "contato principal nome cargo": 0.08,
                "principais segmentos atendidos": 0.08,
                "marque as especialidades que sao atendidas pela sua empresa": 0.12,
                "marque os servicos que sao oferecidos pela sua empresa": 0.12,
            }
            score = sum(weight for signal, weight in signals.items() if signal in headers)
            if len(df) >= 2:
                score += 0.05
            best = max(best, min(score, 1.0))
    return best


def looks_like_supplier_registry(docs: list[InputDocument], threshold: float = 0.45) -> bool:
    try:
        return supplier_registry_score(docs) >= threshold
    except Exception:
        return False


@dataclass
class SupplierParseResult:
    records: pd.DataFrame
    diagnostics: pd.DataFrame
    rows_detected: int
    rows_valid: int
    rows_skipped: int
    rows_merged: int


def _row_record(row: pd.Series, *, source_file: str, sheet_name: str, row_number: int) -> tuple[dict | None, list[str]]:
    canonical: dict[str, Any] = {}
    profile: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    original: dict[str, Any] = {}

    for header, raw_value in row.items():
        value = clean_value(raw_value)
        if not value:
            continue
        header_text = str(header).strip()
        original[header_text] = value
        mapped = map_header(header_text)
        if mapped and mapped not in canonical:
            canonical[mapped] = value
        elif mapped:
            # Repeated semantic question: preserve every answer sem perder o valor
            # comercial mais útil (ex.: Forms traz "Email=anonymous" antes de "E-mail").
            current = canonical.get(mapped)
            if mapped == "email":
                current_values = current if isinstance(current, list) else [current]
                candidates = [*current_values, value]
                preferred = next((item for item in candidates if item and "@" in str(item) and normalize_text(item) != "anonymous"), None)
                canonical[mapped] = preferred or candidates[-1]
            elif current != value:
                canonical[mapped] = [current, value] if not isinstance(current, list) else [*current, value]
        bucket = _profile_bucket(header_text)
        profile.setdefault(bucket, {})[header_text] = value

    legal_name = clean_value(canonical.get("legal_name"))
    trade_name = clean_value(canonical.get("trade_name"))
    name = trade_name or legal_name
    cnpj = normalize_cnpj(canonical.get("cnpj"))
    email = clean_value(canonical.get("email"))
    if isinstance(canonical.get("email"), list):
        email_candidates = [clean_value(item) for item in canonical.get("email") or []]
        email = next((item for item in email_candidates if item and "@" in item and normalize_text(item) != "anonymous"), None)
    phone = clean_value(canonical.get("phone"))
    if isinstance(canonical.get("phone"), list):
        phone = next((clean_value(item) for item in canonical.get("phone") or [] if len(re.sub(r"\D", "", str(item))) >= 8), None)
    valid_email = bool(email and "@" in email and "." in email.split("@", 1)[-1])
    valid_phone = bool(phone and len(re.sub(r"\D", "", phone)) >= 8)

    if not name and not cnpj and not valid_email and not valid_phone:
        return None, ["linha sem identidade suficiente"]
    if name and len(normalize_text(name)) < 3 and not cnpj and not valid_email and not valid_phone:
        return None, ["nome insuficiente para criar fornecedor"]

    contact_name, contact_role = split_contact(canonical.get("contact"))
    city, state = parse_city_state(canonical.get("city_state"))
    if not city:
        explicit_city = clean_value(canonical.get("base_city"))
        if explicit_city and not is_country_name(explicit_city):
            city = explicit_city
    if not state:
        explicit_state = clean_value(canonical.get("base_state"))
        if explicit_state:
            state = _state_value(explicit_state)
    supplier_types = split_values(canonical.get("supplier_types"))
    specialties = split_values(canonical.get("specialties"))
    services = split_values(canonical.get("services_offered"))
    market_segments = split_values(canonical.get("market_segments"))
    client_brands = split_values(canonical.get("client_brands"))
    certifications = split_values(canonical.get("certifications"))
    direct_states = parse_states(canonical.get("direct_states"))
    partner_states = parse_states(canonical.get("partner_states"))
    serves_nationally = parse_bool(canonical.get("serves_nationally"))

    # "TODOS" em estados não vira lista artificial de 27 UFs; a declaração
    # nacional continua preservada como cobertura macro.
    direct_raw = normalize_text(canonical.get("direct_states"))
    partner_raw = normalize_text(canonical.get("partner_states"))
    if serves_nationally is None and ("todos" in direct_raw or "todo brasil" in direct_raw):
        serves_nationally = True

    served_states = list(dict.fromkeys([*direct_states, *partner_states]))
    record: dict[str, Any] = {
        "supplier_name": name,
        "name": name,
        "legal_name": legal_name,
        "cnpj_normalized": cnpj,
        "company_type": clean_value(canonical.get("company_type")),
        "founded_year": parse_int(canonical.get("founded_year")),
        "address": clean_value(canonical.get("address")),
        "contact_name": contact_name,
        "contact_role": contact_role,
        "phone": phone,
        "email": email,
        "website_url": clean_value(canonical.get("website_url")),
        "base_city": city,
        "base_state": state,
        "base_country": clean_value(canonical.get("base_country")),
        "serves_nationally": serves_nationally,
        "served_states": served_states,
        "direct_states": direct_states,
        "partner_states": partner_states,
        "has_local_teams": parse_bool(canonical.get("own_installation_team")),
        "own_installation_team": parse_bool(canonical.get("own_installation_team")),
        "supplier_categories": _category_families(supplier_types or [*specialties, *services]),
        "specialties": list(dict.fromkeys([*supplier_types, *specialties])),
        "services_offered": services,
        "market_segments": market_segments,
        "client_brands": client_brands,
        "certifications": certifications,
        "rollout_capacity": clean_value(canonical.get("rollout_capacity")),
        "differentiators": clean_value(canonical.get("differentiators")),
        "agency_experience": clean_value(canonical.get("agency_experience")),
        "production_internal_pct": parse_percentage(canonical.get("production_internal_pct")),
        "production_outsourced_pct": parse_percentage(canonical.get("production_outsourced_pct")),
        "lead_time": clean_value(canonical.get("lead_time")),
        "production_bottlenecks": clean_value(canonical.get("production_bottlenecks")),
        "facility_total_area": clean_value(canonical.get("facility_total_area")),
        "facility_ceiling_height": clean_value(canonical.get("facility_ceiling_height")),
        "team_total": parse_int(canonical.get("team_total")),
        "technical_structure": split_values(canonical.get("technical_structure")),
        "quality_control": parse_bool(canonical.get("quality_control")),
        "accepts_technical_visit": parse_bool(canonical.get("accepts_technical_visit")),
        "emits_invoice": parse_bool(canonical.get("emits_invoice")),
        "tax_regime": clean_value(canonical.get("tax_regime")),
        "sustainability_practices": clean_value(canonical.get("sustainability_practices")),
        "has_warranty": parse_bool(canonical.get("has_warranty")),
        "warranty_terms": clean_value(canonical.get("warranty_terms")),
        "payment_method": clean_value(canonical.get("payment_method")),
        "payment_terms": clean_value(canonical.get("payment_terms")),
        "large_volume_flexibility": parse_bool(canonical.get("large_volume_flexibility")),
        "works_with_contract": parse_bool(canonical.get("works_with_contract")),
        "recognized_as_supplier": True,
        "confidence": 0.96 if cnpj else (0.90 if name and email else 0.82),
        "profile_data": {
            "repertorio": {
                "diferencial_competitivo": clean_value(canonical.get("differentiators")),
                "experiencia_com_agencias": clean_value(canonical.get("agency_experience")),
                "experiencia_grupo_4zero4": clean_value(canonical.get("group_404_experience")),
            },
            "producao": {
                "capacidade_de_pico": clean_value(canonical.get("peak_capacity")),
                "producao_interna_percentual": parse_percentage(canonical.get("production_internal_pct")),
                "producao_terceirizada_percentual": parse_percentage(canonical.get("production_outsourced_pct")),
                "lead_time": clean_value(canonical.get("lead_time")),
                "gargalos": clean_value(canonical.get("production_bottlenecks")),
            },
            "estrutura": {
                "area_total": clean_value(canonical.get("facility_total_area")),
                "pe_direito": clean_value(canonical.get("facility_ceiling_height")),
                "area_marcenaria": clean_value(canonical.get("facility_carpentry_area")),
                "area_serralheria": clean_value(canonical.get("facility_metalwork_area")),
                "area_impressao": clean_value(canonical.get("facility_print_area")),
                "area_montagem": clean_value(canonical.get("facility_assembly_area")),
                "area_estoque": clean_value(canonical.get("facility_storage_area")),
                "doca_carga_descarga": parse_bool(canonical.get("facility_loading_dock")),
                "colaboradores_total": parse_int(canonical.get("team_total")),
                "equipe_fixa": parse_int(canonical.get("team_fixed")),
                "freelancers_terceiros": parse_int(canonical.get("team_third_party")),
                "responsavel_tecnico": clean_value(canonical.get("technical_manager")),
                "estrutura_tecnica": split_values(canonical.get("technical_structure")),
            },
            "equipamentos": {
                "impressao_digital": clean_value(canonical.get("equipment_printing")),
                "cnc_router": clean_value(canonical.get("equipment_cnc")),
                "laser": clean_value(canonical.get("equipment_laser")),
                "dobradeira_calandra": clean_value(canonical.get("equipment_bending")),
                "solda": split_values(canonical.get("equipment_welding")),
                "pintura": split_values(canonical.get("equipment_painting")),
                "corte_vinco": clean_value(canonical.get("equipment_cutting")),
                "laminacao_acabamento": clean_value(canonical.get("equipment_finishing")),
                "softwares": split_values(canonical.get("software_tools")),
            },
            "qualidade": {
                "controle_de_qualidade": parse_bool(canonical.get("quality_control")),
                "etapas_de_checagem": clean_value(canonical.get("quality_checks")),
                "politica_de_retrabalho": clean_value(canonical.get("rework_policy")),
                "aceita_visita_tecnica": parse_bool(canonical.get("accepts_technical_visit")),
            },
            "fiscal": {
                "emite_nf": parse_bool(canonical.get("emits_invoice")),
                "beneficios_fiscais": clean_value(canonical.get("tax_benefits")),
                "creditos_tributarios": clean_value(canonical.get("tax_credits")),
                "regime_tributario": clean_value(canonical.get("tax_regime")),
            },
            "qualidade_esg": {
                "sustentabilidade": clean_value(canonical.get("sustainability_practices")),
                "possui_garantia": parse_bool(canonical.get("has_warranty")),
                "termos_de_garantia": clean_value(canonical.get("warranty_terms")),
            },
            "comercial": {
                "forma_de_pagamento": clean_value(canonical.get("payment_method")),
                "prazo_de_pagamento": clean_value(canonical.get("payment_terms")),
                "flexibilidade_grandes_volumes": parse_bool(canonical.get("large_volume_flexibility")),
                "trabalha_com_contrato": parse_bool(canonical.get("works_with_contract")),
            },
            "origem": {
                "arquivo": source_file,
                "aba": sheet_name,
                "linha": row_number,
            },
        },
        "raw_data": {
            "source_file": source_file,
            "sheet_name": sheet_name,
            "sheet_row": row_number,
            "original_fields": original,
        },
    }

    # Mescla os buckets livres para que novas perguntas do Excel sejam
    # absorvidas sem exigir alteração do parser.
    record["profile_data"] = _merge_profile(record["profile_data"], profile)
    if not cnpj:
        warnings.append("CNPJ ausente ou fora do padrão; identidade será resolvida por sinais secundários")
    return record, warnings


def extract_supplier_registry(docs: list[InputDocument]) -> SupplierParseResult:
    parsed: list[dict] = []
    diagnostic_rows: list[dict] = []
    rows_detected = 0
    rows_skipped = 0

    for doc in docs:
        frames = _read_frames(doc)
        for sheet_name, df in frames:
            for index, row in df.iterrows():
                rows_detected += 1
                record, warnings = _row_record(
                    row,
                    source_file=doc.name,
                    sheet_name=sheet_name,
                    row_number=int(index) + 2,
                )
                if record is None:
                    rows_skipped += 1
                    diagnostic_rows.append({
                        "Arquivo": doc.name,
                        "Aba": sheet_name,
                        "Linha": int(index) + 2,
                        "Tratamento": "Ignorada",
                        "Detalhe": "; ".join(warnings) or "Sem dados utilizáveis",
                    })
                    continue
                parsed.append(record)
                diagnostic_rows.append({
                    "Arquivo": doc.name,
                    "Aba": sheet_name,
                    "Linha": int(index) + 2,
                    "Fornecedor": record.get("name"),
                    "Tratamento": "Estruturada",
                    "Detalhe": "; ".join(warnings),
                })

    merged: dict[str, dict] = {}
    anonymous_counter = 0
    for record in parsed:
        cnpj = str(record.get("cnpj_normalized") or "")
        name_key = normalize_text(record.get("name"))
        email_key = normalize_text(record.get("email"))
        if cnpj:
            key = f"cnpj:{cnpj}"
        elif name_key and email_key:
            key = f"name_email:{name_key}|{email_key}"
        elif name_key:
            key = f"name:{name_key}"
        else:
            anonymous_counter += 1
            key = f"anonymous:{anonymous_counter}"
        if key in merged:
            merged[key] = merge_supplier_records(merged[key], record)
        else:
            merged[key] = record

    records_df = pd.DataFrame(list(merged.values()))
    diagnostics_df = pd.DataFrame(diagnostic_rows)
    return SupplierParseResult(
        records=records_df,
        diagnostics=diagnostics_df,
        rows_detected=rows_detected,
        rows_valid=len(parsed),
        rows_skipped=rows_skipped,
        rows_merged=max(0, len(parsed) - len(merged)),
    )

EDITOR_LIST_FIELDS = {
    "supplier_categories", "specialties", "services_offered", "client_brands",
    "market_segments", "certifications", "served_states", "direct_states",
    "partner_states", "served_cities", "local_team_locations", "technical_structure",
}


def prepare_supplier_editor(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.copy()
    for field in EDITOR_LIST_FIELDS:
        if field in result.columns:
            result[field] = result[field].map(
                lambda value: " | ".join(str(item) for item in (value or []))
                if isinstance(value, (list, tuple, set)) else (value or "")
            )
    return result


def normalize_supplier_editor(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.copy()
    for field in EDITOR_LIST_FIELDS:
        if field in result.columns:
            result[field] = result[field].map(split_values)
    return result
