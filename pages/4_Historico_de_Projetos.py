from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from briefing_diagnostic import generate_service_agenda
from exporters import format_pt_br_number
from supabase_db import (
    fetch_project_history_overview,
    fetch_recommendation_feedback,
    fetch_recommendation_history,
    fetch_recommendation_query,
    fetch_recommendation_results,
    get_supabase_client,
    save_recommendation_feedback,
)


st.set_page_config(
    page_title="Histórico de projetos",
    page_icon="🕘",
    layout="wide",
)

st.title("Histórico de projetos")
st.caption(
    "Consulte versões, compare mudanças, recupere briefings e registre "
    "o que foi aprovado ou rejeitado."
)

try:
    supabase_url = st.secrets.get("SUPABASE_URL", "")
    supabase_key = st.secrets.get(
        "SUPABASE_SECRET_KEY",
        st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", ""),
    )
except Exception:
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = (
        os.getenv("SUPABASE_SECRET_KEY", "")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    )

if not supabase_url or not supabase_key:
    st.error("Configure o Supabase nos Secrets.")
    st.stop()

client = get_supabase_client(
    supabase_url,
    supabase_key,
)


def _missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return not str(value).strip()


def _money(value: Any) -> str:
    return (
        format_pt_br_number(value, prefix="R$ ")
        or "Não informado"
    )


def _integer(value: Any) -> str:
    if _missing(value):
        return "Não informado"
    try:
        return f"{int(float(value)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def _list_text(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _date_value(value: Any):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _snapshot_name(row: pd.Series) -> str:
    snapshot = row.get("snapshot") or {}
    if isinstance(snapshot, str):
        try:
            snapshot = json.loads(snapshot)
        except Exception:
            snapshot = {}
    return snapshot.get("name") or "Item sem nome"


def _snapshot_supplier(row: pd.Series) -> str:
    snapshot = row.get("snapshot") or {}
    if isinstance(snapshot, str):
        try:
            snapshot = json.loads(snapshot)
        except Exception:
            snapshot = {}
    return snapshot.get("supplier_name") or "Não informado"


def _version_label(row: pd.Series) -> str:
    created = str(row.get("created_at") or "")[:10]
    note = str(row.get("version_notes") or "").strip()
    base = (
        f"V{int(row.get('version_number') or 0)}"
        f" · {created}"
    )
    return f"{base} · {note}" if note else base


def _field_rows(
    first_query: dict,
    second_query: dict,
) -> pd.DataFrame:
    fields = [
        ("Objetivo", "objective", "text"),
        ("Público", "audience_profile", "text"),
        ("Quantidade", "audience_quantity", "integer"),
        ("Budget total", "budget_total_brl", "money"),
        ("Budget unitário", "budget_unit_brl", "money"),
        ("Cidade", "location_city", "text"),
        ("Estado", "location_state", "text"),
        ("Data", "event_date", "text"),
        ("Prazo disponível", "available_days", "integer"),
        ("Tipos desejados", "desired_types", "list"),
        ("Atributos", "desired_attributes", "list"),
        ("Restrições", "restrictions", "list"),
        ("Status", "readiness_status", "text"),
        ("Completude", "completeness_score", "percent"),
    ]

    def format_value(value, kind):
        if kind == "money":
            return _money(value)
        if kind == "integer":
            return _integer(value)
        if kind == "list":
            return _list_text(value) or "Não informado"
        if kind == "percent":
            return (
                f"{int(value)}%"
                if not _missing(value)
                else "Não informado"
            )
        return str(value or "Não informado")

    rows = []
    for label, key, kind in fields:
        first = format_value(first_query.get(key), kind)
        second = format_value(second_query.get(key), kind)
        rows.append(
            {
                "Campo": label,
                "Versão A": first,
                "Versão B": second,
                "Alterou": "Sim" if first != second else "Não",
            }
        )
    return pd.DataFrame(rows)


def _results_comparison(
    first_results: pd.DataFrame,
    second_results: pd.DataFrame,
) -> pd.DataFrame:
    first_map = {
        (
            str(row.get("item_type")),
            str(row.get("item_id")),
        ): row
        for row in first_results.to_dict("records")
    }
    second_map = {
        (
            str(row.get("item_type")),
            str(row.get("item_id")),
        ): row
        for row in second_results.to_dict("records")
    }

    keys = set(first_map) | set(second_map)
    rows = []

    for key in keys:
        first = first_map.get(key)
        second = second_map.get(key)
        source = second or first or {}
        snapshot = source.get("snapshot") or {}
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except Exception:
                snapshot = {}

        first_score = (
            float(first.get("total_score"))
            if first and first.get("total_score") is not None
            else None
        )
        second_score = (
            float(second.get("total_score"))
            if second and second.get("total_score") is not None
            else None
        )

        if first and second:
            status = "Permaneceu"
        elif second:
            status = "Entrou"
        else:
            status = "Saiu"

        rows.append(
            {
                "Item": snapshot.get("name") or "Sem nome",
                "Tipo": source.get("item_type"),
                "Status": status,
                "Nota A": first_score,
                "Nota B": second_score,
                "Variação": (
                    round(second_score - first_score, 2)
                    if first_score is not None
                    and second_score is not None
                    else None
                ),
            }
        )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values(
        by=["Status", "Nota B", "Nota A"],
        ascending=[True, False, False],
        na_position="last",
    )


def _reuse_version(
    query: dict,
) -> None:
    parsed = query.get("parsed_brief") or {}
    diagnostic = query.get("diagnostic_snapshot") or {}

    if isinstance(parsed, str):
        parsed = json.loads(parsed)
    if isinstance(diagnostic, str):
        diagnostic = json.loads(diagnostic)

    st.session_state["rec_project_name"] = (
        parsed.get("project_name") or ""
    )
    st.session_state["rec_objective"] = (
        parsed.get("objective") or ""
    )
    st.session_state["rec_audience_profile"] = (
        parsed.get("audience_profile") or ""
    )
    st.session_state["rec_quantity"] = int(
        parsed.get("audience_quantity") or 0
    )
    st.session_state["rec_budget_total"] = float(
        parsed.get("budget_total_brl") or 0
    )
    st.session_state["rec_city"] = (
        parsed.get("location_city") or ""
    )
    st.session_state["rec_state"] = (
        parsed.get("location_state") or ""
    )
    st.session_state["rec_event_date"] = _date_value(
        parsed.get("event_date")
    )
    st.session_state["rec_available_days"] = int(
        parsed.get("available_days") or 0
    )
    st.session_state["rec_desired_types"] = (
        parsed.get("desired_types") or ["product"]
    )
    st.session_state["rec_desired_attributes"] = _list_text(
        parsed.get("desired_attributes")
    )
    st.session_state["rec_restrictions"] = _list_text(
        parsed.get("restrictions")
    )
    st.session_state["rec_briefing_paste"] = (
        query.get("briefing_text") or ""
    )
    st.session_state["recommendation_prefill"] = parsed
    st.session_state["recommendation_diagnostic"] = diagnostic
    st.session_state["recommendation_service_agenda"] = (
        generate_service_agenda(parsed, diagnostic)
        if diagnostic
        else ""
    )
    st.session_state["recommendation_source_text"] = (
        query.get("briefing_text")
        or parsed.get("source_summary")
        or ""
    )
    st.session_state["recommendation_brief"] = None
    st.session_state["recommendation_results"] = None


try:
    projects = fetch_project_history_overview(client)
except Exception as exc:
    st.exception(exc)
    st.stop()

if projects.empty:
    st.info(
        "Ainda não existem projetos com briefings ou recomendações salvas."
    )
    st.stop()

total_versions = int(
    pd.to_numeric(
        projects["recommendation_versions"],
        errors="coerce",
    ).fillna(0).sum()
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Projetos", len(projects))
m2.metric("Versões de recomendação", total_versions)
m3.metric(
    "Prontos para recomendar",
    int(
        projects["latest_readiness_status"]
        .fillna("")
        .eq("Pronto para recomendar")
        .sum()
    ),
)
m4.metric(
    "Com pendências críticas",
    int(
        projects["latest_readiness_status"]
        .fillna("")
        .isin(
            [
                "Aguardando respostas do atendimento",
                "Briefing insuficiente",
            ]
        )
        .sum()
    ),
)

st.divider()

search = st.text_input(
    "Buscar projeto, cliente ou evento",
    placeholder="Ex.: Nissin, CCXP, Oktoberfest...",
)

filtered_projects = projects.copy()
if search.strip():
    query_text = search.strip().lower()
    searchable = (
        filtered_projects["project_name"].fillna("").astype(str)
        + " "
        + filtered_projects["client_brand"].fillna("").astype(str)
        + " "
        + filtered_projects["event_name"].fillna("").astype(str)
    ).str.lower()
    filtered_projects = filtered_projects[
        searchable.str.contains(
            query_text,
            regex=False,
        )
    ]

if filtered_projects.empty:
    st.warning("Nenhum projeto corresponde à busca.")
    st.stop()

project_options = {
    (
        f"{row.get('project_name') or 'Projeto sem nome'}"
        f" · {int(row.get('recommendation_versions') or 0)} versão(ões)"
    ): row.get("project_id")
    for _, row in filtered_projects.iterrows()
}

selected_project_label = st.selectbox(
    "Projeto",
    options=list(project_options.keys()),
)
selected_project_id = project_options[selected_project_label]

versions = fetch_recommendation_history(
    client,
    project_id=selected_project_id,
)

if versions.empty:
    st.info(
        "Este projeto existe, mas ainda não possui recomendações salvas."
    )
    st.stop()

versions = versions.sort_values(
    by=["version_number", "created_at"],
    ascending=[False, False],
).reset_index(drop=True)

version_options = {
    _version_label(row): row.get("query_id")
    for _, row in versions.iterrows()
}

selected_version_label = st.selectbox(
    "Versão para visualizar",
    options=list(version_options.keys()),
)
selected_query_id = version_options[selected_version_label]

query = fetch_recommendation_query(
    client,
    selected_query_id,
)
results = fetch_recommendation_results(
    client,
    selected_query_id,
)
feedback = fetch_recommendation_feedback(
    client,
    selected_query_id,
)

if not query:
    st.error("A versão selecionada não foi encontrada.")
    st.stop()

parsed_brief = query.get("parsed_brief") or {}
diagnostic = query.get("diagnostic_snapshot") or {}

if isinstance(parsed_brief, str):
    parsed_brief = json.loads(parsed_brief)
if isinstance(diagnostic, str):
    diagnostic = json.loads(diagnostic)

st.divider()

header1, header2, header3, header4 = st.columns(4)
header1.metric(
    "Versão",
    f"V{int(query.get('version_number') or 0)}",
)
header2.metric(
    "Completude",
    (
        f"{int(query.get('completeness_score'))}%"
        if query.get("completeness_score") is not None
        else "Não calculada"
    ),
)
header3.metric(
    "Status",
    query.get("readiness_status") or "Não informado",
)
header4.metric(
    "Resultados",
    len(results),
)

if query.get("version_notes"):
    st.info(
        "Observação da versão: "
        + str(query.get("version_notes"))
    )

tab_brief, tab_diagnostic, tab_results, tab_compare, tab_feedback = st.tabs(
    [
        "Briefing",
        "Diagnóstico",
        "Recomendações",
        "Comparar versões",
        "Feedback",
    ]
)

with tab_brief:
    st.subheader("Entendimento salvo")

    b1, b2, b3, b4 = st.columns(4)
    b1.metric(
        "Budget total",
        _money(query.get("budget_total_brl")),
    )
    b2.metric(
        "Budget unitário",
        _money(query.get("budget_unit_brl")),
    )
    b3.metric(
        "Público",
        _integer(query.get("audience_quantity")),
    )
    b4.metric(
        "Prazo",
        (
            f"{int(query.get('available_days'))} dias"
            if query.get("available_days") is not None
            else "Não informado"
        ),
    )

    st.markdown("**Objetivo**")
    st.write(query.get("objective") or "Não informado")

    st.markdown("**Perfil do público**")
    st.write(
        query.get("audience_profile") or "Não informado"
    )

    st.markdown("**Localização e data**")
    st.write(
        ", ".join(
            item
            for item in [
                query.get("location_city"),
                query.get("location_state"),
                query.get("event_date"),
            ]
            if item
        )
        or "Não informado"
    )

    st.markdown("**Tipos procurados**")
    st.write(
        _list_text(query.get("desired_types"))
        or "Não informado"
    )

    st.markdown("**Resumo da fonte**")
    st.write(
        parsed_brief.get("source_summary")
        or query.get("briefing_text")
        or "Não informado"
    )

    source_files = query.get("source_files") or []
    if source_files:
        st.caption(
            "Fontes: " + _list_text(source_files)
        )

    if st.button(
        "Reutilizar esta versão em uma nova recomendação",
        type="primary",
        use_container_width=True,
    ):
        _reuse_version(query)
        st.switch_page("pages/3_Nova_Recomendacao.py")

with tab_diagnostic:
    issues = diagnostic.get("issues") or []

    if not diagnostic:
        st.info(
            "Esta versão foi salva antes do diagnóstico estruturado."
        )
    else:
        st.write(
            diagnostic.get("diagnostic_summary") or ""
        )
        st.caption(
            diagnostic.get("recommended_next_step") or ""
        )

        for severity in [
            "Crítica",
            "Importante",
            "Enriquecimento",
        ]:
            group = [
                issue for issue in issues
                if issue.get("severity") == severity
            ]
            st.markdown(
                f"### {severity} ({len(group)})"
            )
            if not group:
                st.success("Nenhum item nesta categoria.")
                continue
            for item in group:
                st.markdown(
                    f"**{item.get('title')}** · "
                    f"{item.get('category')} · "
                    f"{item.get('responsible')}"
                )
                st.write(item.get("finding") or "")
                st.info(item.get("question") or "")
                st.caption(
                    "Impacto: "
                    + str(item.get("impact") or "Outro")
                )

with tab_results:
    if results.empty:
        st.info("Nenhum resultado foi salvo nesta versão.")
    else:
        result_display = results.copy()
        result_display["Item"] = result_display.apply(
            _snapshot_name,
            axis=1,
        )
        result_display["Fornecedor"] = result_display.apply(
            _snapshot_supplier,
            axis=1,
        )
        result_display["Estimativa"] = result_display[
            "estimated_total"
        ].apply(_money)

        st.dataframe(
            result_display[
                [
                    "rank",
                    "Item",
                    "item_type",
                    "Fornecedor",
                    "total_score",
                    "Estimativa",
                    "reason",
                ]
            ].rename(
                columns={
                    "rank": "Posição",
                    "item_type": "Tipo",
                    "total_score": "Nota",
                    "reason": "Motivo",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

with tab_compare:
    if len(versions) < 2:
        st.info(
            "Salve uma segunda versão para habilitar a comparação."
        )
    else:
        compare_options = {
            _version_label(row): row.get("query_id")
            for _, row in versions.iterrows()
        }

        c1, c2 = st.columns(2)
        with c1:
            first_label = st.selectbox(
                "Versão A",
                list(compare_options.keys()),
                index=min(1, len(compare_options) - 1),
                key="history_compare_a",
            )
        with c2:
            second_label = st.selectbox(
                "Versão B",
                list(compare_options.keys()),
                index=0,
                key="history_compare_b",
            )

        first_id = compare_options[first_label]
        second_id = compare_options[second_label]

        if first_id == second_id:
            st.warning("Selecione duas versões diferentes.")
        else:
            first_query = fetch_recommendation_query(
                client,
                first_id,
            )
            second_query = fetch_recommendation_query(
                client,
                second_id,
            )
            first_results = fetch_recommendation_results(
                client,
                first_id,
            )
            second_results = fetch_recommendation_results(
                client,
                second_id,
            )

            st.markdown("### Mudanças no briefing")
            field_comparison = _field_rows(
                first_query or {},
                second_query or {},
            )
            st.dataframe(
                field_comparison,
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("### Mudanças nas recomendações")
            result_comparison = _results_comparison(
                first_results,
                second_results,
            )

            if result_comparison.empty:
                st.info(
                    "As versões não possuem resultados para comparar."
                )
            else:
                st.dataframe(
                    result_comparison,
                    use_container_width=True,
                    hide_index=True,
                )

with tab_feedback:
    if results.empty:
        st.info(
            "Não há recomendações nesta versão para registrar feedback."
        )
    else:
        result_choices = {}
        for _, row in results.iterrows():
            label = (
                f"{int(row.get('rank') or 0)}. "
                f"{_snapshot_name(row)}"
            )
            result_choices[label] = row

        selected_result_label = st.selectbox(
            "Recomendação",
            list(result_choices.keys()),
        )
        selected_result = result_choices[
            selected_result_label
        ]

        existing_feedback = None
        if not feedback.empty:
            matching = feedback[
                (
                    feedback["item_type"]
                    == selected_result.get("item_type")
                )
                & (
                    feedback["item_id"].astype(str)
                    == str(selected_result.get("item_id"))
                )
            ]
            if not matching.empty:
                existing_feedback = matching.iloc[0].to_dict()

        decision_options = [
            "Favorito",
            "Cotação solicitada",
            "Aprovado",
            "Rejeitado",
            "Arquivado",
        ]
        current_decision = (
            existing_feedback.get("decision")
            if existing_feedback
            else "Favorito"
        )

        decision = st.selectbox(
            "Decisão",
            decision_options,
            index=decision_options.index(current_decision),
        )
        reason = st.text_input(
            "Motivo principal",
            value=(
                existing_feedback.get("reason") or ""
                if existing_feedback
                else ""
            ),
            placeholder=(
                "Ex.: dentro do budget, baixa aderência, "
                "prazo inviável..."
            ),
        )
        notes = st.text_area(
            "Observações",
            value=(
                existing_feedback.get("notes") or ""
                if existing_feedback
                else ""
            ),
            height=110,
        )

        if st.button(
            "Salvar feedback",
            type="primary",
            use_container_width=True,
        ):
            saved = save_recommendation_feedback(
                client,
                query_id=selected_query_id,
                result_id=selected_result.get("id"),
                item_type=selected_result.get("item_type"),
                item_id=selected_result.get("item_id"),
                decision=decision,
                reason=reason or None,
                notes=notes or None,
            )
            st.success(
                f"Feedback salvo: {saved.get('decision')}."
            )
            st.rerun()

        if not feedback.empty:
            st.markdown("### Feedback registrado")
            st.dataframe(
                feedback[
                    [
                        "decision",
                        "reason",
                        "notes",
                        "updated_at",
                    ]
                ].rename(
                    columns={
                        "decision": "Decisão",
                        "reason": "Motivo",
                        "notes": "Observações",
                        "updated_at": "Atualizado em",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
