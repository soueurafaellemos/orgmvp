from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd
import streamlit as st

from branding import (
    NAVE_APP_ICON,
    apply_nave_branding,
    page_header,
)
from knowledge_details import DETAIL_SCHEMAS
from media_library import fetch_primary_media_urls
from runtime_ui import (
    report_service_error,
    require_admin_access,
    require_app_access,
)
from supabase_db import (
    fetch_duplicate_candidates,
    get_supabase_client,
    resolve_duplicate_as_distinct,
    resolve_duplicate_decisions_bulk,
    resolve_duplicate_merge,
)


st.set_page_config(
    page_title="NAVE by VOE | Revisar duplicidades",
    page_icon=NAVE_APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

if not require_app_access():
    st.stop()

apply_nave_branding()
page_header(
    "Revisar duplicidades",
    "Confirme quando dois cadastros representam o mesmo item "
    "ou mantenha-os separados.",
    eyebrow="Qualidade da base",
)

if not require_admin_access():
    st.stop()


def _setting(
    name: str,
    default: str = "",
) -> str:
    try:
        return str(
            st.secrets.get(
                name,
                os.getenv(name, default),
            )
        )
    except Exception:
        return str(os.getenv(name, default))


def _display_value(value: Any) -> str:
    if value is None:
        return "Não informado"

    if isinstance(value, bool):
        return "Sim" if value else "Não"

    if isinstance(value, (list, tuple, set)):
        if not value:
            return "Não informado"
        return "\n".join(
            f"• {item}"
            for item in value
        )

    if isinstance(value, dict):
        if not value:
            return "Não informado"
        return json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    text = str(value).strip()
    return text or "Não informado"


def _comparison_rows(
    entity_type: str,
    source: dict,
    candidate: dict,
) -> pd.DataFrame:
    fields = []

    for _, section_fields in DETAIL_SCHEMAS.get(
        entity_type,
        [],
    ):
        fields.extend(section_fields)

    seen = set()
    rows = []

    for field, label in fields:
        if field in seen:
            continue
        seen.add(field)

        source_value = _display_value(
            source.get(field)
        )
        candidate_value = _display_value(
            candidate.get(field)
        )

        if (
            source_value == "Não informado"
            and candidate_value == "Não informado"
        ):
            continue

        rows.append(
            {
                "Campo": label,
                "Novo cadastro": source_value,
                "Cadastro existente": candidate_value,
                "Situação": (
                    "Igual"
                    if source_value == candidate_value
                    else "Revisar"
                ),
            }
        )

    return pd.DataFrame(rows)


url = _setting("SUPABASE_URL")
key = (
    _setting("SUPABASE_SECRET_KEY")
    or _setting("SUPABASE_SERVICE_ROLE_KEY")
)

if not url or not key:
    st.error(
        "A base de conhecimento não está disponível."
    )
    st.stop()

try:
    client = get_supabase_client(url, key)
    reviews = fetch_duplicate_candidates(
        client,
        status="pending",
    )
except Exception as exc:
    report_service_error(
        "consulta das possíveis duplicidades",
        user_message=(
            "Não foi possível carregar a fila de revisão."
        ),
        exception=exc,
    )
    st.stop()

if reviews.empty:
    st.success(
        "Não existem possíveis duplicidades aguardando revisão."
    )
    st.stop()

metric1, metric2 = st.columns(2)
metric1.metric(
    "Aguardando revisão",
    len(reviews),
)
metric2.metric(
    "Maior semelhança",
    (
        f"{float(reviews['similarity_score'].max()) * 100:.0f}%"
    ),
)

st.divider()
st.subheader("Resolver uma importação inteira")
st.caption(
    "Use este atalho quando um PDF visual criou variações do nome do mesmo "
    "local, como pavimento, pavilhão, planta ou área interna. O cadastro "
    "existente é preservado e recebe as imagens, plantas e documentos."
)

bulk_options = {}
for import_id, group in reviews.groupby("import_id", dropna=False):
    import_text = str(import_id or "Sem importação identificada")
    created_source = (
        group["created_at"]
        if "created_at" in group.columns
        else pd.Series(dtype="object")
    )
    created_values = pd.to_datetime(
        created_source,
        errors="coerce",
        utc=True,
    )
    created = (
        created_values.max()
        if not created_values.empty
        else pd.NaT
    )
    created_label = (
        created.tz_convert("America/Sao_Paulo").strftime("%d/%m/%Y %H:%M")
        if pd.notna(created)
        else "data não informada"
    )
    label = (
        f"{created_label} · {len(group)} item(ns) · "
        f"{import_text[-8:]}"
    )
    bulk_options[label] = import_id

selected_bulk_label = st.selectbox(
    "Importação com pendências",
    options=list(bulk_options.keys()),
    key="duplicate_bulk_import",
)
selected_import_id = bulk_options[selected_bulk_label]
selected_group = reviews[
    reviews["import_id"].astype(str)
    == str(selected_import_id)
].copy()

bulk_preview = pd.DataFrame(
    [
        {
            "Novo item": row.get("source_name") or "Não informado",
            "Cadastro existente": row.get("candidate_name") or "Não informado",
            "Semelhança": (
                f"{float(row.get('similarity_score') or 0) * 100:.0f}%"
            ),
        }
        for _, row in selected_group.iterrows()
    ]
)
st.dataframe(
    bulk_preview,
    use_container_width=True,
    hide_index=True,
)

bulk_confirmation = st.checkbox(
    "Revisei a lista e confirmo que todos representam cadastros já existentes.",
    key=f"confirm_bulk_{selected_import_id}",
)

if st.button(
    "Unir todos desta importação no cadastro existente",
    type="primary",
    use_container_width=True,
    disabled=not bulk_confirmation,
    key=f"merge_bulk_{selected_import_id}",
):
    try:
        with st.spinner(
            "Consolidando informações, imagens, plantas e documentos..."
        ):
            result = resolve_duplicate_decisions_bulk(
                client,
                decisions=[
                    {
                        "review_id": str(row.get("id")),
                        "action": "merge",
                    }
                    for _, row in selected_group.iterrows()
                ],
                strategy="enrich_safe",
            )

        if result.get("failed"):
            st.warning(
                f"Consolidação parcial: {result.get('merged', 0)} unido(s) "
                f"e {result.get('failed', 0)} falha(s)."
            )
        else:
            st.success(
                f"{result.get('merged', 0)} cadastro(s) unido(s). "
                "Os materiais foram transferidos para os cadastros preservados."
            )
        st.rerun()
    except Exception as exc:
        report_service_error(
            "consolidação em lote de duplicidades",
            user_message=(
                "Não foi possível consolidar esta importação em lote."
            ),
            exception=exc,
        )

st.divider()
st.subheader("Revisar item por item")


review_options = {}

for index, row in reviews.iterrows():
    label = (
        f"{row.get('source_name')} ↔ "
        f"{row.get('candidate_name')} · "
        f"{float(row.get('similarity_score') or 0) * 100:.0f}%"
    )
    review_options[label] = index

selected_label = st.selectbox(
    "Correspondência para revisar",
    options=list(review_options.keys()),
)

selected = reviews.loc[
    review_options[selected_label]
].to_dict()

entity_type = str(selected["entity_type"])
source_id = str(selected["source_entity_id"])
candidate_id = str(selected["candidate_entity_id"])
source = dict(selected.get("source_record") or {})
candidate = dict(
    selected.get("candidate_record") or {}
)

st.caption(
    "A semelhança é apenas um sinal. Confirme usando "
    "nome, fornecedor, cidade, valores, características "
    "e imagens."
)

try:
    image_urls = fetch_primary_media_urls(
        client,
        [
            (entity_type, source_id),
            (entity_type, candidate_id),
        ],
    )
except Exception:
    image_urls = {}

source_column, candidate_column = st.columns(2)

with source_column:
    st.markdown("### Novo cadastro")
    source_url = image_urls.get(
        (entity_type, source_id)
    )
    if source_url:
        st.image(
            source_url,
            use_container_width=True,
        )
    st.write(
        f"**{source.get('name') or selected.get('source_name')}**"
    )
    st.caption(
        f"ID interno: {source_id}"
    )

with candidate_column:
    st.markdown("### Cadastro existente")
    candidate_url = image_urls.get(
        (entity_type, candidate_id)
    )
    if candidate_url:
        st.image(
            candidate_url,
            use_container_width=True,
        )
    st.write(
        f"**{candidate.get('name') or selected.get('candidate_name')}**"
    )
    st.caption(
        f"ID interno: {candidate_id}"
    )

st.markdown("### Comparação")

comparison = _comparison_rows(
    entity_type,
    source,
    candidate,
)

st.dataframe(
    comparison,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Novo cadastro": st.column_config.TextColumn(
            "Novo cadastro",
            width="large",
        ),
        "Cadastro existente": st.column_config.TextColumn(
            "Cadastro existente",
            width="large",
        ),
        "Situação": st.column_config.TextColumn(
            "Situação",
            width="small",
        ),
    },
)

st.divider()
st.subheader("Decisão")

merge_label_to_strategy = {
    (
        "Unir preservando o cadastro existente "
        "e preenchendo lacunas"
    ): "enrich_safe",
    (
        "Unir priorizando os dados do novo cadastro"
    ): "prefer_new",
}

merge_label = st.selectbox(
    "Ao unir os cadastros",
    options=list(
        merge_label_to_strategy.keys()
    ),
)

confirmation = st.checkbox(
    "Revisei as informações e confirmo esta decisão.",
)

action1, action2 = st.columns(2)

with action1:
    merge_clicked = st.button(
        "São o mesmo item — unir cadastros",
        type="primary",
        disabled=not confirmation,
        use_container_width=True,
    )

with action2:
    distinct_clicked = st.button(
        "São itens diferentes — manter separados",
        disabled=not confirmation,
        use_container_width=True,
    )

if merge_clicked:
    try:
        with st.spinner(
            "Unindo informações, imagens e arquivos..."
        ):
            result = resolve_duplicate_merge(
                client,
                review_id=str(selected["id"]),
                strategy=merge_label_to_strategy[
                    merge_label
                ],
            )

        st.success(
            "Cadastros unidos. As informações e mídias "
            "foram consolidadas no cadastro existente."
        )
        st.caption(
            f"Mídias movidas: "
            f"{result.get('media_moved', 0)} · "
            f"arquivos repetidos removidos: "
            f"{result.get('duplicate_media_removed', 0)}."
        )
        st.rerun()

    except Exception as exc:
        report_service_error(
            "união manual de cadastros",
            user_message=(
                "Não foi possível unir os cadastros."
            ),
            exception=exc,
        )

if distinct_clicked:
    try:
        resolve_duplicate_as_distinct(
            client,
            review_id=str(selected["id"]),
        )
        st.success(
            "Os cadastros foram confirmados como itens diferentes."
        )
        st.rerun()

    except Exception as exc:
        report_service_error(
            "confirmação de cadastros distintos",
            user_message=(
                "Não foi possível registrar a decisão."
            ),
            exception=exc,
        )
