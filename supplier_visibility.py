from __future__ import annotations

from typing import Any, Iterable
import unicodedata


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().strip().split())


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value is True
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return bool(str(value).strip())


STRONG_SUPPLIER_FIELDS = (
    "contact_name",
    "contact_role",
    "email",
    "phone",
    "whatsapp",
    "instagram_url",
    "linkedin_url",
    "address",
    "notes",
    "served_states",
    "served_cities",
    "local_team_locations",
    "travel_pricing_mode",
    "default_travel_cost_brl",
    "freight_pricing_mode",
    "default_freight_cost_brl",
    "travel_lead_days",
    "coverage_notes",
)


def has_strong_supplier_evidence(record: dict) -> bool:
    if record.get("serves_nationally") is True:
        return True
    if record.get("has_local_teams") is True:
        return True
    if record.get("equipment_transport_required") is True:
        return True
    if record.get("accommodation_required") is True:
        return True
    return any(has_value(record.get(field)) for field in STRONG_SUPPLIER_FIELDS)


def is_visible_supplier(
    supplier: dict,
    *,
    linked_venue_names: Iterable[str] = (),
    products_count: int = 0,
    activations_count: int = 0,
) -> bool:
    """Diferencia fornecedor real de cadastro técnico criado para um local.

    Um local pode apontar para ``suppliers.id`` como operador. Isso é uma
    relação direcional e não transforma o local em fornecedor.
    """
    if products_count > 0 or activations_count > 0:
        return True

    venue_names = [str(name or "").strip() for name in linked_venue_names if str(name or "").strip()]
    if not venue_names:
        # Cadastro criado como fornecedor e que não é operador de local.
        return True

    supplier_name = normalize_name(supplier.get("name"))
    # Quando o fornecedor tem identidade própria e opera um local de nome
    # diferente, é um fornecedor ligado a um local — e deve aparecer.
    if any(normalize_name(name) != supplier_name for name in venue_names):
        return True

    # Contato/logística/cobertura real também caracteriza fornecedor.
    if has_strong_supplier_evidence(supplier):
        return True

    # Caso típico a esconder: supplier stub com o MESMO nome do venue,
    # criado apenas para preencher venues.operator_id.
    return False
