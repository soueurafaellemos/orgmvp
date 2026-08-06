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
    recover_incompatible_merges,
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
    cleanup_key = "duplicate_revalidation_v27_8_9"
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
st.subheader("Recuperar uniões já realizadas")
st.caption(
    "Esta área reconstrói cadastros apagados por uma união incorreta usando "
    "o payload original da importação ou o snapshot gravado no momento da "
    "consolidação. A recuperação não apaga o cadastro que ficou na direita."
)

if recovery_candidates.empty:
    st.success("Não há uniões anteriores aguardando recuperação.")
else:
    recovery_labels = {
        "incompatible": "União incompatível — recuperação automática segura",
        "hierarchy": "Local principal e subespaço — recuperar com hierarquia",
        "ambiguous": "Exige revisão humana",
        "likely_correct": "União provavelmente correta",
        "unrecoverable": "Dados insuficientes para reconstrução automática",
    }
    recovery_view = recovery_candidates.copy()
    recovery_view["Classificação"] = (
        recovery_view["recovery_classification"]
        .map(recovery_labels)
        .fillna(recovery_view["recovery_classification"])
    )
    recovery_view["Semelhança corrigida"] = recovery_view[
        "corrected_score"
    ].map(lambda value: f"{float(value or 0) * 100:.0f}%")

    automatic = recovery_candidates[
        recovery_candidates["recovery_classification"].isin(
            ["incompatible", "hierarchy"]
        )
    ]
    ambiguous_recovery = recovery_candidates[
        recovery_candidates["recovery_classification"] == "ambiguous"
    ]
    unavailable_recovery = recovery_candidates[
        recovery_candidates["recovery_classification"] == "unrecoverable"
    ]

    recover1, recover2, recover3 = st.columns(3)
    recover1.metric("Recuperação automática segura", len(automatic))
    recover2.metric("Revisão humana", len(ambiguous_recovery))
    recover3.metric("Sem payload recuperável", len(unavailable_recovery))

    with st.expander(
        "Ver diagnóstico das uniões realizadas",
        expanded=bool(len(automatic)),
    ):
        st.dataframe(
            recovery_view[
                [
                    "source_name",
                    "candidate_name",
                    "Classificação",
                    "Semelhança corrigida",
                    "recovery_reason",
                ]
            ].rename(
                columns={
                    "source_name": "Cadastro apagado",
                    "candidate_name": "Cadastro que foi preservado",
                    "recovery_reason": "Motivo técnico",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    if not automatic.empty:
        st.warning(
            f"{len(automatic)} união(ões) foram classificadas como "
            "incompatíveis ou como relação entre local e subespaço. "
            "A recuperação recriará os cadastros apagados e devolverá "
            "as mídias que puderem ser atribuídas pela origem e página."
        )
        confirm_recovery = st.checkbox(
            "Confirmo a recuperação das uniões incompatíveis identificadas acima.",
            key="confirm_incompatible_merge_recovery",
        )
        if st.button(
            "Recuperar automaticamente as uniões incompatíveis",
            type="primary",
            disabled=not confirm_recovery,
            use_container_width=True,
            key="recover_incompatible_merges",
        ):
            try:
                with st.spinner("Reconstruindo cadastros e devolvendo mídias..."):
                    recovery_result = recover_incompatible_merges(client)
                st.success(
                    f"Recuperação concluída: {recovery_result.get('recovered', 0)} "
                    "cadastro(s) reconstruído(s) e "
                    f"{recovery_result.get('media_restored', 0)} mídia(s) e "
                    f"{recovery_result.get('costs_restored', 0)} custo(s) "
                    "devolvido(s)."
                )
                if recovery_result.get("failed"):
                    st.error(
                        f"{recovery_result.get('failed')} item(ns) não puderam ser "
                        "recuperados automaticamente. Os registros permanecem no "
                        "histórico para diagnóstico."
                    )
                    st.dataframe(
                        pd.DataFrame(recovery_result.get("errors") or []),
                        use_container_width=True,
                        hide_index=True,
                    )
                st.rerun()
            except Exception as exc:
                report_service_error(
                    "recuperação de uniões incompatíveis",
                    user_message=(
                        "Não foi possível concluir a recuperação automática."
                    ),
                    exception=exc,
                )

    if not ambiguous_recovery.empty:
        st.markdown("#### Recuperação individual de casos ambíguos")
        ambiguous_options = {}
        for index, row in ambiguous_recovery.iterrows():
            label = (
                f"{row.get('source_name')} ↔ {row.get('candidate_name')} · "
                f"{float(row.get('corrected_score') or 0) * 100:.0f}%"
            )
            ambiguous_options[label] = index
        selected_recovery_label = st.selectbox(
            "União realizada para revisar",
            options=list(ambiguous_options.keys()),
            key="ambiguous_merge_recovery_selection",
        )
        selected_recovery = ambiguous_recovery.loc[
            ambiguous_options[selected_recovery_label]
        ].to_dict()
        st.info(
            "Use esta ação somente quando os dois nomes representarem itens "
            "diferentes. O cadastro da esquerda será reconstruído como registro "
            "separado."
        )
        confirm_manual_recovery = st.checkbox(
            "Confirmei que estes dois cadastros representam itens diferentes.",
            key="confirm_manual_merge_recovery",
        )
        if st.button(
            "Restaurar o cadastro apagado como item separado",
            disabled=not confirm_manual_recovery,
            use_container_width=True,
            key="recover_ambiguous_merge",
        ):
            try:
                result = recover_merged_review(
                    client,
                    review_id=str(selected_recovery["id"]),
                    force=True,
                )
                st.success(
                    "Cadastro reconstruído. "
                    f"Mídias devolvidas: {result.get('media_restored', 0)} · "
                    f"custos devolvidos: {result.get('costs_restored', 0)}."
                )
                st.rerun()
            except Exception as exc:
                report_service_error(
                    "recuperação individual de união",
                    user_message="Não foi possível reconstruir este cadastro.",
                    exception=exc,
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
        "A NAVE identificou uma relação entre local principal e ambiente. "
        "Os dois cadastros devem permanecer separados e ser vinculados por "
        "hierarquia, sem apagar nenhum deles."
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
            "Manter separados e vincular como subespaço",
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
            "Os dois locais foram preservados e o ambiente foi vinculado "
            "ao local principal."
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
