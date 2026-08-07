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
from entity_matching import analyze_candidate_pair
from media_library import fetch_primary_media_urls
from merge_recovery import (
    fetch_merge_recovery_candidates,
    recover_merged_review,
)
from runtime_ui import (
    report_service_error,
    require_admin_access,
    require_app_access,
)
from supabase_db import (
    fetch_duplicate_candidates,
    get_supabase_client,
    resolve_duplicate_as_distinct,
    resolve_duplicate_as_hierarchy,
    resolve_duplicate_decisions_bulk,
    resolve_duplicate_merge,
    revalidate_pending_duplicate_candidates,
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
    cleanup_key = "duplicate_revalidation_v28_1_2"
    cleanup_result = None
    if not st.session_state.get(cleanup_key):
        cleanup_result = revalidate_pending_duplicate_candidates(client)
        st.session_state[cleanup_key] = True

    reviews = fetch_duplicate_candidates(
        client,
        status="pending",
    )
    recovery_candidates = fetch_merge_recovery_candidates(
        client,
        limit=1000,
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

if cleanup_result and cleanup_result.get("dismissed"):
    st.info(
        f"{cleanup_result.get('dismissed', 0)} sugestão(ões) incorreta(s) "
        "foram removidas automaticamente da fila. Nenhum cadastro ou "
        "arquivo foi apagado."
    )

st.divider()
st.subheader("Correções pendentes de uniões antigas")
st.caption(
    "A NAVE mostra aqui somente uniões anteriores que realmente precisam de "
    "uma decisão ou reorganização. Uniões já consideradas corretas ficam fora "
    "da área de ação."
)

recovery_labels = {
    "incompatible": "União realmente incompatível",
    "hierarchy": "Ambiente interno a organizar",
    "ambiguous": "Exige revisão humana",
    "likely_correct": "União correta — identidade confirmada",
    "unrecoverable": "Histórico sem dados suficientes para reconstrução",
}

if recovery_candidates.empty:
    st.success("Não há correções de uniões antigas pendentes.")
else:
    actionable_recovery = recovery_candidates[
        recovery_candidates["recovery_classification"].isin(
            ["incompatible", "hierarchy", "ambiguous"]
        )
    ].copy()

    if actionable_recovery.empty:
        st.success(
            "Não há correções de uniões antigas pendentes. As uniões "
            "reavaliadas foram consideradas compatíveis com a identidade atual."
        )
    else:
        correction1, correction2, correction3 = st.columns(3)
        correction1.metric(
            "Separações necessárias",
            int((actionable_recovery["recovery_classification"] == "incompatible").sum()),
        )
        correction2.metric(
            "Ambientes internos",
            int((actionable_recovery["recovery_classification"] == "hierarchy").sum()),
        )
        correction3.metric(
            "Revisão humana",
            int((actionable_recovery["recovery_classification"] == "ambiguous").sum()),
        )

        correction_options: dict[str, int] = {}
        for index, row in actionable_recovery.iterrows():
            classification = str(row.get("recovery_classification") or "")
            label = (
                f"{row.get('source_name')} ↔ {row.get('candidate_name')} · "
                f"{recovery_labels.get(classification, classification)} · "
                f"{float(row.get('corrected_score') or 0) * 100:.0f}%"
            )
            correction_options[label] = index

        selected_correction_label = st.selectbox(
            "Correção para revisar",
            options=list(correction_options.keys()),
            key="legacy_merge_correction_selection",
        )
        selected_correction = actionable_recovery.loc[
            correction_options[selected_correction_label]
        ].to_dict()
        correction_class = str(
            selected_correction.get("recovery_classification") or ""
        )
        source_name = str(selected_correction.get("source_name") or "Cadastro anterior")
        target_name = str(selected_correction.get("candidate_name") or "Cadastro preservado")

        if correction_class == "hierarchy":
            st.info(
                f"**{source_name}** foi identificado como um ambiente interno de "
                f"**{target_name}**. A correção o reconstruirá dentro da ficha do "
                "local principal, preservando seus dados e mídias, sem criar outro "
                "local independente na lista."
            )
            confirmation_text = (
                "Confirmo que este item é um ambiente/subespaço do local principal."
            )
            button_text = "Incorporar ambiente ao local principal"
            force_recovery = False
        elif correction_class == "incompatible":
            st.warning(
                f"A união entre **{source_name}** e **{target_name}** possui conflito "
                "real de identidade. A correção reconstruirá o cadastro da esquerda "
                "como uma entidade independente."
            )
            confirmation_text = (
                "Confirmo que estes cadastros representam entidades diferentes."
            )
            button_text = "Restaurar cadastro como item separado"
            force_recovery = False
        else:
            st.info(
                f"A união entre **{source_name}** e **{target_name}** ainda é "
                "ambígua. Só restaure o cadastro se você souber que são entidades "
                "diferentes."
            )
            confirmation_text = (
                "Confirmei que estes dois cadastros representam entidades diferentes."
            )
            button_text = "Restaurar como item separado"
            force_recovery = True

        confirm_correction = st.checkbox(
            confirmation_text,
            key=f"confirm_legacy_correction_{selected_correction.get('id')}",
        )
        if st.button(
            button_text,
            type="primary",
            disabled=not confirm_correction,
            use_container_width=True,
            key=f"apply_legacy_correction_{selected_correction.get('id')}",
        ):
            try:
                with st.spinner("Aplicando a correção e preservando os vínculos..."):
                    result = recover_merged_review(
                        client,
                        review_id=str(selected_correction["id"]),
                        force=force_recovery,
                    )
                if correction_class == "hierarchy":
                    st.success(
                        "Ambiente incorporado ao local principal. Ele passará a "
                        "aparecer dentro da ficha do empreendimento, e não como "
                        "outro local na lista."
                    )
                else:
                    st.success(
                        "Cadastro reconstruído como entidade independente. "
                        f"Mídias recuperadas: {result.get('media_restored', 0)}."
                    )
                st.rerun()
            except Exception as exc:
                report_service_error(
                    "correção de união anterior",
                    user_message="Não foi possível aplicar esta correção.",
                    exception=exc,
                )

    # Histórico é diagnóstico, não ação. Ele fica oculto por padrão para não
    # competir visualmente com a fila de decisões reais.
    if st.checkbox(
        "Mostrar histórico técnico de uniões já analisadas",
        value=False,
        key="show_legacy_merge_history",
    ):
        history_view = recovery_candidates.copy()
        history_view["Classificação"] = (
            history_view["recovery_classification"]
            .map(recovery_labels)
            .fillna(history_view["recovery_classification"])
        )
        history_view["Semelhança corrigida"] = history_view[
            "corrected_score"
        ].map(lambda value: f"{float(value or 0) * 100:.0f}%")
        st.dataframe(
            history_view[
                [
                    "source_name",
                    "candidate_name",
                    "Classificação",
                    "Semelhança corrigida",
                ]
            ].rename(
                columns={
                    "source_name": "Cadastro incorporado",
                    "candidate_name": "Cadastro preservado",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

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
st.subheader("Revisão segura")
st.warning(
    "A união em lote foi desativada. Nomes semelhantes não garantem que "
    "os registros representem o mesmo item. Nenhum cadastro é unido ou "
    "apagado sem uma decisão individual confirmada abaixo."
)

if st.button(
    "Revalidar sugestões pendentes",
    use_container_width=True,
    key="revalidate_pending_duplicates",
):
    try:
        result = revalidate_pending_duplicate_candidates(client)
        st.session_state.pop("duplicate_revalidation_v27_8_9", None)
        st.success(
            f"Revalidação concluída: {result.get('dismissed', 0)} "
            "falso(s) positivo(s) removido(s) da fila e "
            f"{result.get('retained', 0)} correspondência(s) mantida(s) "
            "para revisão humana."
        )
        st.rerun()
    except Exception as exc:
        report_service_error(
            "revalidação das possíveis duplicidades",
            user_message=(
                "Não foi possível revalidar a fila de duplicidades."
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
match_analysis = analyze_candidate_pair(
    entity_type,
    source,
    candidate,
)
match_relation = match_analysis.get("relation") or {}

st.caption(
    "A semelhança é apenas um sinal. Confirme usando "
    "nome, fornecedor, cidade, valores, características "
    "e imagens."
)

evidence_labels = {
    "sku_exact": "Mesmo SKU",
    "supplier_same": "Mesmo fornecedor",
    "project_same": "Mesmo projeto",
    "taxonomy_same": "Taxonomia compatível",
    "name_exact": "Nome normalizado idêntico",
    "distinctive_words_exact": "Palavras distintivas em comum",
    "website_domain_same": "Mesmo domínio oficial",
    "address_same": "Mesmo endereço",
    "postal_code_same": "Mesmo CEP",
    "operator_same": "Mesmo operador",
    "parent_name_exact": "Nome do local principal contido no ambiente",
    "location_identifier_same": "Identificador de localização compatível",
}
blocker_labels = {
    "sku_different": "SKUs diferentes",
    "supplier_different": "Fornecedores diferentes",
    "project_different": "Projetos diferentes",
    "taxonomy_incompatible": "Taxonomias incompatíveis",
    "no_distinctive_word_in_common": "Nenhuma palavra distintiva em comum",
    "no_distinctive_word_or_identifier_in_common": (
        "Nenhuma palavra distintiva ou identificador em comum"
    ),
    "only_generic_words_in_common": "Somente palavras genéricas em comum",
    "city_different": "Cidades diferentes",
    "state_different": "Estados diferentes",
    "operator_different": "Operadores diferentes",
    "official_domains_different": "Domínios oficiais diferentes",
}

signal1, signal2, signal3 = st.columns(3)
signal1.metric(
    "Pontuação corrigida",
    f"{float(match_analysis.get('score') or 0) * 100:.0f}%",
)
signal2.metric(
    "Palavras distintivas em comum",
    len(
        (match_analysis.get("name_features") or {}).get(
            "common_distinctive"
        ) or []
    ),
)
signal3.metric(
    "Taxonomia",
    {
        "same": "Compatível",
        "different": "Incompatível",
    }.get(match_analysis.get("taxonomy_state"), "Não conclusiva"),
)

if match_analysis.get("evidence"):
    st.success(
        "Sinais confirmados: "
        + "; ".join(
            evidence_labels.get(item, item)
            for item in match_analysis.get("evidence") or []
        )
    )
if match_analysis.get("blockers"):
    st.error(
        "Travas de segurança: "
        + "; ".join(
            blocker_labels.get(item, item)
            for item in match_analysis.get("blockers") or []
        )
    )
if match_relation.get("type") == "parent_subspace":
    st.info(
        "A NAVE identificou um ambiente pertencente a um local principal. "
        "Ao confirmar, o ambiente ficará incorporado à ficha do empreendimento, "
        "com seus dados próprios, sem aparecer como outro local na lista."
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

hierarchy_clicked = False
merge_clicked = False

if match_relation.get("type") == "parent_subspace":
    action1, action2 = st.columns(2)
    with action1:
        hierarchy_clicked = st.button(
            "Incorporar ambiente ao local principal",
            type="primary",
            disabled=not confirmation,
            use_container_width=True,
        )
    with action2:
        distinct_clicked = st.button(
            "Não possuem relação — manter totalmente separados",
            disabled=not confirmation,
            use_container_width=True,
        )
else:
    merge_confirmation = st.text_input(
        "Para liberar a união destrutiva, digite UNIR",
        value="",
        key=f"merge_confirmation_{selected.get('id')}",
    )
    action1, action2 = st.columns(2)
    with action1:
        merge_clicked = st.button(
            "São o mesmo item — unir cadastros",
            type="primary",
            disabled=(
                not confirmation
                or merge_confirmation.strip().upper() != "UNIR"
                or bool(match_analysis.get("blockers"))
            ),
            use_container_width=True,
        )
    with action2:
        distinct_clicked = st.button(
            "São itens diferentes — manter separados",
            disabled=not confirmation,
            use_container_width=True,
        )

if hierarchy_clicked:
    try:
        result = resolve_duplicate_as_hierarchy(
            client,
            review_id=str(selected["id"]),
        )
        st.success(
            "Ambiente incorporado ao local principal. Ele ficará disponível "
            "dentro da ficha do empreendimento e não como outro local na lista."
        )
        st.rerun()
    except Exception as exc:
        report_service_error(
            "vínculo hierárquico de locais",
            user_message=(
                "Não foi possível criar a relação entre local e subespaço."
            ),
            exception=exc,
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
