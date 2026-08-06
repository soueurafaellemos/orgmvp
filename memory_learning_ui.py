from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from memory_cost_parser import (
    parse_cost_workbook,
)
from memory_learning_db import (
    add_feedback_entry,
    create_cost_signed_url,
    delete_cost_document,
    delete_feedback_entry,
    fetch_cost_documents,
    fetch_cost_items,
    fetch_cost_links,
    fetch_feedback_entries,
    fetch_item_outcomes,
    fetch_project_outcome,
    save_cost_correlations,
    save_cost_document,
    update_project_budget,
    upsert_project_outcome,
)
from memory_learning_models import (
    COMMERCIAL_RESULTS,
    CONFIDENCE_LEVELS,
    COST_ITEM_STATUS,
    ESTIMATE_TYPES,
    EXECUTION_RESULTS,
    FEEDBACK_SENTIMENTS,
    FEEDBACK_SOURCES,
    FEEDBACK_STAGES,
    FEEDBACK_THEMES,
    INFORMATION_SOURCES,
    ITEM_OUTCOME_STATUS,
    PROCESS_TYPES,
    PROPOSAL_RESULTS,
    RESULT_REASONS,
)


def _label(
    mapping: dict[str, str],
    value: str | None,
    default: str = "Não informado",
) -> str:
    return mapping.get(
        str(value or ""),
        default,
    )


def _index(
    options: list[str],
    current: str | None,
) -> int:
    try:
        return options.index(
            str(current)
        )
    except ValueError:
        return 0


def _date_value(
    value: Any,
) -> date | None:
    if not value:
        return None

    try:
        return pd.to_datetime(
            value
        ).date()
    except Exception:
        return None


def _money(
    value: Any,
    currency: str = "BRL",
) -> str:
    try:
        number = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return "Não informado"

    if currency == "BRL":
        formatted = (
            f"{number:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
        return "R$ " + formatted

    return (
        f"{currency} "
        f"{number:,.2f}"
    )


def _safe_records(
    dataframe: pd.DataFrame,
) -> list[dict]:
    if dataframe is None or dataframe.empty:
        return []

    return dataframe.to_dict(
        orient="records"
    )


def _learning_schema_error(
    exc: Exception,
) -> None:
    st.warning(
        "A estrutura da Fase 14 ainda não está "
        "disponível no Supabase. Execute o SQL "
        "da fase e reinicie a aplicação."
    )

    with st.expander(
        "Detalhe técnico",
        expanded=False,
    ):
        st.code(
            str(exc)
        )


def render_results_learning_tab(
    client,
    *,
    project_id: str,
    memory_items: pd.DataFrame,
) -> None:
    try:
        outcome = fetch_project_outcome(
            client,
            project_id=project_id,
        )
        feedbacks = fetch_feedback_entries(
            client,
            project_id=project_id,
        )
        item_outcomes = fetch_item_outcomes(
            client,
            project_id=project_id,
        )
    except Exception as exc:
        _learning_schema_error(exc)
        return

    st.subheader(
        "Resultados & Aprendizados"
    )
    st.caption(
        "Registre o que aconteceu depois da apresentação. "
        "Esses dados ficam disponíveis para análises futuras, "
        "mas ainda não alteram automaticamente as recomendações."
    )

    metric1, metric2, metric3, metric4 = (
        st.columns(4)
    )

    metric1.metric(
        "Resultado comercial",
        _label(
            COMMERCIAL_RESULTS,
            outcome.get(
                "commercial_result"
            ),
            "Em avaliação",
        ),
    )
    metric2.metric(
        "Proposta",
        _label(
            PROPOSAL_RESULTS,
            outcome.get(
                "proposal_result"
            ),
        ),
    )
    metric3.metric(
        "Execução",
        _label(
            EXECUTION_RESULTS,
            outcome.get(
                "execution_result"
            ),
        ),
    )
    metric4.metric(
        "Feedbacks",
        len(feedbacks),
    )

    with st.expander(
        "Editar resultado do projeto",
        expanded=not bool(outcome),
    ):
        process_options = list(
            PROCESS_TYPES.keys()
        )
        commercial_options = list(
            COMMERCIAL_RESULTS.keys()
        )
        proposal_options = list(
            PROPOSAL_RESULTS.keys()
        )
        execution_options = list(
            EXECUTION_RESULTS.keys()
        )
        confidence_options = list(
            CONFIDENCE_LEVELS.keys()
        )
        source_options = list(
            INFORMATION_SOURCES.keys()
        )

        with st.form(
            "phase14_project_outcome_"
            + project_id
        ):
            row1 = st.columns(3)

            with row1[0]:
                process_type = st.selectbox(
                    "Tipo de processo",
                    process_options,
                    index=_index(
                        process_options,
                        outcome.get(
                            "process_type"
                        )
                        or "not_informed",
                    ),
                    format_func=lambda value: (
                        PROCESS_TYPES[
                            value
                        ]
                    ),
                )

            with row1[1]:
                commercial_result = (
                    st.selectbox(
                        "Resultado comercial",
                        commercial_options,
                        index=_index(
                            commercial_options,
                            outcome.get(
                                "commercial_result"
                            )
                            or "in_evaluation",
                        ),
                        format_func=lambda value: (
                            COMMERCIAL_RESULTS[
                                value
                            ]
                        ),
                    )
                )

            with row1[2]:
                proposal_result = (
                    st.selectbox(
                        "Resultado da proposta",
                        proposal_options,
                        index=_index(
                            proposal_options,
                            outcome.get(
                                "proposal_result"
                            )
                            or "not_informed",
                        ),
                        format_func=lambda value: (
                            PROPOSAL_RESULTS[
                                value
                            ]
                        ),
                    )
                )

            row2 = st.columns(3)

            with row2[0]:
                execution_result = (
                    st.selectbox(
                        "Resultado da execução",
                        execution_options,
                        index=_index(
                            execution_options,
                            outcome.get(
                                "execution_result"
                            )
                            or "not_informed",
                        ),
                        format_func=lambda value: (
                            EXECUTION_RESULTS[
                                value
                            ]
                        ),
                    )
                )

            with row2[1]:
                result_date = st.date_input(
                    "Data do resultado",
                    value=_date_value(
                        outcome.get(
                            "result_date"
                        )
                    ),
                    format="DD/MM/YYYY",
                )

            with row2[2]:
                execution_date = st.date_input(
                    "Data da execução",
                    value=_date_value(
                        outcome.get(
                            "execution_date"
                        )
                    ),
                    format="DD/MM/YYYY",
                )

            relationship_cols = st.columns(2)

            with relationship_cols[0]:
                contracting_client = st.text_input(
                    "Cliente contratante",
                    value=str(
                        outcome.get(
                            "contracting_client"
                        )
                        or ""
                    ),
                )

            with relationship_cols[1]:
                partners_involved = st.text_input(
                    "Agências ou parceiros envolvidos",
                    value=str(
                        outcome.get(
                            "partners_involved"
                        )
                        or ""
                    ),
                )

            reasons = st.multiselect(
                "Motivos relacionados ao resultado",
                list(
                    RESULT_REASONS.keys()
                ),
                default=[
                    reason
                    for reason in (
                        outcome.get(
                            "result_reasons"
                        )
                        or []
                    )
                    if reason
                    in RESULT_REASONS
                ],
                format_func=lambda value: (
                    RESULT_REASONS[
                        value
                    ]
                ),
            )

            result_context = st.text_area(
                "Contexto do resultado",
                value=str(
                    outcome.get(
                        "result_context"
                    )
                    or ""
                ),
                height=120,
                placeholder=(
                    "Ex.: projeto perdido por budget, "
                    "mas conceito elogiado pelo cliente."
                ),
            )

            execution_notes = st.text_area(
                "Aprendizados da execução",
                value=str(
                    outcome.get(
                        "execution_notes"
                    )
                    or ""
                ),
                height=100,
            )

            row3 = st.columns(2)

            with row3[0]:
                confidence_level = (
                    st.selectbox(
                        "Confiança da informação",
                        confidence_options,
                        index=_index(
                            confidence_options,
                            outcome.get(
                                "confidence_level"
                            )
                            or "incomplete",
                        ),
                        format_func=lambda value: (
                            CONFIDENCE_LEVELS[
                                value
                            ]
                        ),
                    )
                )

            with row3[1]:
                information_source = (
                    st.selectbox(
                        "Fonte da informação",
                        source_options,
                        index=_index(
                            source_options,
                            outcome.get(
                                "information_source"
                            )
                            or "not_informed",
                        ),
                        format_func=lambda value: (
                            INFORMATION_SOURCES[
                                value
                            ]
                        ),
                    )
                )

            save_outcome = (
                st.form_submit_button(
                    "Salvar resultados",
                    type="primary",
                    width="stretch",
                )
            )

        if save_outcome:
            try:
                upsert_project_outcome(
                    client,
                    project_id=project_id,
                    values={
                        "process_type": (
                            process_type
                        ),
                        "commercial_result": (
                            commercial_result
                        ),
                        "proposal_result": (
                            proposal_result
                        ),
                        "execution_result": (
                            execution_result
                        ),
                        "result_date": (
                            result_date.isoformat()
                            if result_date
                            else None
                        ),
                        "execution_date": (
                            execution_date.isoformat()
                            if execution_date
                            else None
                        ),
                        "contracting_client": (
                            contracting_client.strip()
                            or None
                        ),
                        "partners_involved": (
                            partners_involved.strip()
                            or None
                        ),
                        "result_reasons": (
                            reasons
                        ),
                        "result_context": (
                            result_context.strip()
                            or None
                        ),
                        "execution_notes": (
                            execution_notes.strip()
                            or None
                        ),
                        "confidence_level": (
                            confidence_level
                        ),
                        "information_source": (
                            information_source
                        ),
                    },
                )
                st.success(
                    "Resultados do projeto atualizados."
                )
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.error(
                    "Não foi possível salvar "
                    "os resultados."
                )
                st.code(
                    str(exc)
                )

    st.divider()
    st.subheader(
        "Feedbacks recebidos"
    )

    with st.expander(
        "Adicionar feedback",
        expanded=feedbacks.empty,
    ):
        source_options = list(
            FEEDBACK_SOURCES.keys()
        )
        stage_options = list(
            FEEDBACK_STAGES.keys()
        )
        theme_options = list(
            FEEDBACK_THEMES.keys()
        )
        sentiment_options = list(
            FEEDBACK_SENTIMENTS.keys()
        )
        confidence_options = list(
            CONFIDENCE_LEVELS.keys()
        )

        with st.form(
            "phase14_feedback_"
            + project_id
        ):
            feedback_row1 = (
                st.columns(4)
            )

            with feedback_row1[0]:
                feedback_date = (
                    st.date_input(
                        "Data",
                        value=None,
                        format="DD/MM/YYYY",
                    )
                )

            with feedback_row1[1]:
                source_type = (
                    st.selectbox(
                        "Origem",
                        source_options,
                        index=_index(
                            source_options,
                            "client",
                        ),
                        format_func=lambda value: (
                            FEEDBACK_SOURCES[
                                value
                            ]
                        ),
                    )
                )

            with feedback_row1[2]:
                process_stage = (
                    st.selectbox(
                        "Etapa",
                        stage_options,
                        index=_index(
                            stage_options,
                            "presentation",
                        ),
                        format_func=lambda value: (
                            FEEDBACK_STAGES[
                                value
                            ]
                        ),
                    )
                )

            with feedback_row1[3]:
                sentiment = st.selectbox(
                    "Sentimento",
                    sentiment_options,
                    index=_index(
                        sentiment_options,
                        "neutral",
                    ),
                    format_func=lambda value: (
                        FEEDBACK_SENTIMENTS[
                            value
                        ]
                    ),
                )

            feedback_row2 = (
                st.columns(2)
            )

            with feedback_row2[0]:
                theme = st.selectbox(
                    "Tema",
                    theme_options,
                    format_func=lambda value: (
                        FEEDBACK_THEMES[
                            value
                        ]
                    ),
                )

            with feedback_row2[1]:
                feedback_confidence = (
                    st.selectbox(
                        "Confiança",
                        confidence_options,
                        index=_index(
                            confidence_options,
                            "client_confirmed",
                        ),
                        format_func=lambda value: (
                            CONFIDENCE_LEVELS[
                                value
                            ]
                        ),
                    )
                )

            original_feedback = (
                st.text_area(
                    "Comentário recebido",
                    height=110,
                )
            )
            internal_interpretation = (
                st.text_area(
                    "Interpretação interna da VOE",
                    height=90,
                )
            )
            action_taken = st.text_area(
                "Ação decorrente",
                height=80,
            )

            save_feedback = (
                st.form_submit_button(
                    "Adicionar feedback",
                    type="primary",
                    width="stretch",
                )
            )

        if save_feedback:
            if not original_feedback.strip():
                st.warning(
                    "Informe o comentário recebido."
                )
            else:
                try:
                    add_feedback_entry(
                        client,
                        project_id=(
                            project_id
                        ),
                        values={
                            "feedback_date": (
                                feedback_date.isoformat()
                                if feedback_date
                                else None
                            ),
                            "source_type": (
                                source_type
                            ),
                            "process_stage": (
                                process_stage
                            ),
                            "theme": theme,
                            "sentiment": (
                                sentiment
                            ),
                            "original_feedback": (
                                original_feedback.strip()
                            ),
                            "internal_interpretation": (
                                internal_interpretation.strip()
                                or None
                            ),
                            "action_taken": (
                                action_taken.strip()
                                or None
                            ),
                            "confidence_level": (
                                feedback_confidence
                            ),
                        },
                    )
                    st.success(
                        "Feedback adicionado."
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(
                        "Não foi possível salvar "
                        "o feedback."
                    )
                    st.code(
                        str(exc)
                    )

    for feedback in _safe_records(
        feedbacks
    ):
        with st.container(
            border=True,
        ):
            feedback_header = (
                st.columns(
                    [3, 1]
                )
            )

            with feedback_header[0]:
                st.markdown(
                    "### "
                    + _label(
                        FEEDBACK_THEMES,
                        feedback.get(
                            "theme"
                        ),
                        "Feedback",
                    )
                )
                st.caption(
                    " · ".join(
                        [
                            _label(
                                FEEDBACK_SOURCES,
                                feedback.get(
                                    "source_type"
                                ),
                            ),
                            _label(
                                FEEDBACK_STAGES,
                                feedback.get(
                                    "process_stage"
                                ),
                            ),
                            _label(
                                FEEDBACK_SENTIMENTS,
                                feedback.get(
                                    "sentiment"
                                ),
                            ),
                            str(
                                feedback.get(
                                    "feedback_date"
                                )
                                or "Data não informada"
                            ),
                        ]
                    )
                )

            with feedback_header[1]:
                if st.button(
                    "Excluir",
                    key=(
                        "delete_feedback_"
                        + str(
                            feedback["id"]
                        )
                    ),
                    width="stretch",
                ):
                    delete_feedback_entry(
                        client,
                        feedback_id=str(
                            feedback["id"]
                        ),
                    )
                    st.rerun()

            st.write(
                feedback.get(
                    "original_feedback"
                )
            )

            if feedback.get(
                "internal_interpretation"
            ):
                st.markdown(
                    "**Interpretação VOE:**"
                )
                st.write(
                    feedback[
                        "internal_interpretation"
                    ]
                )

            if feedback.get(
                "action_taken"
            ):
                st.markdown(
                    "**Ação decorrente:**"
                )
                st.write(
                    feedback[
                        "action_taken"
                    ]
                )

    if not item_outcomes.empty:
        st.divider()
        st.subheader(
            "Decisões registradas por ficha"
        )
        summary = (
            item_outcomes.groupby(
                "outcome_status"
            )
            .size()
            .reset_index(
                name="Fichas"
            )
        )
        summary["Resultado"] = (
            summary[
                "outcome_status"
            ].map(
                ITEM_OUTCOME_STATUS
            )
        )
        st.dataframe(
            summary[
                [
                    "Resultado",
                    "Fichas",
                ]
            ],
            hide_index=True,
            width="stretch",
        )


def _cost_preview_dataframe(
    parsed,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Incluir": True,
                "Código": (
                    item.item_code
                    or ""
                ),
                "Categoria": (
                    item.category
                    or ""
                ),
                "Item": item.item_name,
                "Quantidade": (
                    item.quantity
                ),
                "Valor unitário": (
                    item.unit_value
                ),
                "Valor final": (
                    item.client_total
                ),
                "Situação": (
                    COST_ITEM_STATUS.get(
                        item.item_status,
                        item.item_status,
                    )
                ),
                "Tipo": (
                    ESTIMATE_TYPES.get(
                        item.estimate_type,
                        item.estimate_type,
                    )
                ),
                "Linha": (
                    item.source_row
                ),
            }
            for item in parsed.items
        ]
    )


def render_budget_adherence_tab(
    client,
    *,
    project_id: str,
    memory_items: pd.DataFrame,
) -> None:
    try:
        outcome = fetch_project_outcome(
            client,
            project_id=project_id,
        )
        documents = fetch_cost_documents(
            client,
            project_id=project_id,
        )
        costs = fetch_cost_items(
            client,
            project_id=project_id,
        )
        links = fetch_cost_links(
            client,
            project_id=project_id,
        )
    except Exception as exc:
        _learning_schema_error(exc)
        return

    st.subheader(
        "Orçamento & Aderência"
    )
    st.caption(
        "A planilha é usada como evidência histórica do projeto. "
        "A NAVE não executa macros, não recalcula fórmulas e "
        "não funciona como sistema financeiro."
    )

    budget_value = outcome.get(
        "budget_amount"
    )
    currency = str(
        outcome.get("currency")
        or "BRL"
    )

    latest_document = (
        documents.iloc[0].to_dict()
        if not documents.empty
        else {}
    )
    proposal_total = (
        latest_document.get(
            "client_total"
        )
    )

    metric1, metric2, metric3, metric4 = (
        st.columns(4)
    )
    metric1.metric(
        "Budget",
        _money(
            budget_value,
            currency,
        ),
    )
    metric2.metric(
        "Proposta mais recente",
        _money(
            proposal_total,
            currency,
        ),
    )

    variance = None
    variance_percent = None

    try:
        if (
            budget_value is not None
            and proposal_total is not None
        ):
            variance = (
                float(proposal_total)
                - float(budget_value)
            )

            if float(
                budget_value
            ) != 0:
                variance_percent = (
                    variance
                    / float(
                        budget_value
                    )
                    * 100
                )
    except (
        TypeError,
        ValueError,
    ):
        pass

    metric3.metric(
        "Diferença",
        _money(
            variance,
            currency,
        ),
        (
            f"{variance_percent:+.1f}%"
            if variance_percent
            is not None
            else None
        ),
    )
    metric4.metric(
        "Itens estruturados",
        len(costs),
    )

    if (
        variance is not None
        and variance > 0
    ):
        st.warning(
            "A proposta mais recente está "
            f"{_money(variance, currency)} "
            "acima do budget registrado."
        )
    elif (
        variance is not None
        and variance <= 0
    ):
        st.success(
            "A proposta mais recente está "
            "dentro do budget registrado."
        )

    reasons = (
        outcome.get(
            "result_reasons"
        )
        or []
    )

    if (
        "budget" in reasons
        and outcome.get(
            "commercial_result"
        )
        in {
            "lost",
            "cancelled",
            "suspended",
        }
    ):
        st.info(
            "O resultado do projeto registra orçamento "
            "como um fator relacionado. Os itens de maior "
            "impacto aparecem abaixo. A NAVE mantém a "
            "fonte e a confiança informadas no projeto."
        )
    elif (
        variance is not None
        and variance > 0
    ):
        st.caption(
            "Estar acima do budget é um sinal de risco, "
            "mas não prova que o resultado comercial foi "
            "causado pelo custo."
        )

    with st.expander(
        "Informar ou atualizar o budget",
        expanded=budget_value is None,
    ):
        with st.form(
            "phase14_budget_"
            + project_id
        ):
            budget_input = (
                st.number_input(
                    "Budget do briefing",
                    min_value=0.0,
                    value=float(
                        budget_value
                        or 0
                    ),
                    step=1000.0,
                    format="%.2f",
                )
            )
            budget_currency = (
                st.selectbox(
                    "Moeda",
                    [
                        "BRL",
                        "USD",
                        "EUR",
                    ],
                    index=(
                        [
                            "BRL",
                            "USD",
                            "EUR",
                        ].index(currency)
                        if currency
                        in {
                            "BRL",
                            "USD",
                            "EUR",
                        }
                        else 0
                    ),
                )
            )
            save_budget = (
                st.form_submit_button(
                    "Salvar budget",
                    type="primary",
                    width="stretch",
                )
            )

        if save_budget:
            update_project_budget(
                client,
                project_id=project_id,
                budget_amount=(
                    budget_input
                    if budget_input > 0
                    else None
                ),
                currency=(
                    budget_currency
                ),
            )
            st.success(
                "Budget atualizado."
            )
            st.rerun()

    st.divider()
    st.subheader(
        "Adicionar planilha de custos"
    )

    uploaded = st.file_uploader(
        "Planilha final do projeto",
        type=[
            "xlsx",
            "xlsm",
            "xls",
            "csv",
        ],
        key=(
            "phase14_cost_upload_"
            + project_id
        ),
    )

    analyze_cost = st.button(
        "Analisar planilha",
        type="primary",
        width="stretch",
        disabled=uploaded is None,
        key=(
            "phase14_analyze_cost_"
            + project_id
        ),
    )

    if analyze_cost and uploaded:
        try:
            parsed = parse_cost_workbook(
                uploaded.name,
                uploaded.getvalue(),
            )
            st.session_state[
                "phase14_cost_parsed_"
                + project_id
            ] = parsed.model_dump()
            st.session_state[
                "phase14_cost_bytes_"
                + project_id
            ] = uploaded.getvalue()
            st.session_state[
                "phase14_cost_name_"
                + project_id
            ] = uploaded.name
            st.success(
                "Planilha analisada. "
                "Revise o resumo antes de salvar."
            )
        except Exception as exc:
            st.error(
                "Não foi possível identificar "
                "a estrutura de custos."
            )
            st.code(
                str(exc)
            )

    parsed_payload = st.session_state.get(
        "phase14_cost_parsed_"
        + project_id
    )

    if parsed_payload:
        from memory_learning_models import (
            CostWorkbookResult,
        )

        parsed = (
            CostWorkbookResult
            .model_validate(
                parsed_payload
            )
        )

        preview1, preview2, preview3 = (
            st.columns(3)
        )
        preview1.metric(
            "Itens identificados",
            len(parsed.items),
        )
        preview2.metric(
            "Total da proposta",
            _money(
                parsed.client_total,
                parsed.currency,
            ),
        )
        preview3.metric(
            "Aba utilizada",
            parsed.sheet_name,
        )

        preview_df = (
            _cost_preview_dataframe(
                parsed
            )
        )
        st.dataframe(
            preview_df,
            hide_index=True,
            width="stretch",
            height=360,
            column_config={
                "Valor unitário": (
                    st.column_config
                    .NumberColumn(
                        format="R$ %.2f"
                    )
                ),
                "Valor final": (
                    st.column_config
                    .NumberColumn(
                        format="R$ %.2f"
                    )
                ),
            },
        )

        for warning in (
            parsed.warnings
        ):
            st.warning(warning)

        save_cost = st.button(
            "Salvar planilha e sugerir correlações",
            type="primary",
            width="stretch",
            key=(
                "phase14_save_cost_"
                + project_id
            ),
        )

        if save_cost:
            try:
                result = save_cost_document(
                    client,
                    project_id=project_id,
                    file_name=st.session_state[
                        "phase14_cost_name_"
                        + project_id
                    ],
                    file_bytes=st.session_state[
                        "phase14_cost_bytes_"
                        + project_id
                    ],
                    parsed=parsed,
                    memory_items=(
                        _safe_records(
                            memory_items
                        )
                    ),
                )

                if (
                    result.get("status")
                    == "duplicate"
                ):
                    st.warning(
                        "Esta mesma planilha já está "
                        "vinculada ao projeto."
                    )
                else:
                    st.success(
                        f"{result.get('items_saved', 0)} "
                        "item(ns) salvos e "
                        f"{result.get('links_suggested', 0)} "
                        "correlação(ões) sugerida(s)."
                    )

                for suffix in [
                    "parsed",
                    "bytes",
                    "name",
                ]:
                    st.session_state.pop(
                        "phase14_cost_"
                        + suffix
                        + "_"
                        + project_id,
                        None,
                    )

                st.rerun()
            except Exception as exc:
                st.error(
                    "Não foi possível salvar "
                    "a planilha."
                )
                st.code(
                    str(exc)
                )

    if documents.empty:
        st.info(
            "Nenhuma planilha de custos foi "
            "vinculada a este projeto."
        )
        return

    st.divider()
    st.subheader(
        "Composição da proposta"
    )

    if not costs.empty:
        category_summary = (
            costs.assign(
                category_display=(
                    costs["category"]
                    .fillna(
                        "Sem categoria"
                    )
                ),
                client_total_numeric=(
                    pd.to_numeric(
                        costs[
                            "client_total"
                        ],
                        errors="coerce",
                    ).fillna(0)
                ),
            )
            .groupby(
                "category_display",
                as_index=False,
            )[
                "client_total_numeric"
            ]
            .sum()
            .sort_values(
                "client_total_numeric",
                ascending=False,
            )
        )
        category_summary.columns = [
            "Categoria",
            "Valor final",
        ]
        st.dataframe(
            category_summary,
            hide_index=True,
            width="stretch",
            column_config={
                "Valor final": (
                    st.column_config
                    .NumberColumn(
                        format="R$ %.2f"
                    )
                )
            },
        )

        top_items = costs.copy()
        top_items[
            "Valor final"
        ] = pd.to_numeric(
            top_items[
                "client_total"
            ],
            errors="coerce",
        ).fillna(0)
        top_items = top_items.sort_values(
            "Valor final",
            ascending=False,
        ).head(15)
        top_items["Item"] = top_items[
            "item_name"
        ]
        top_items["Categoria"] = (
            top_items["category"]
            .fillna(
                "Sem categoria"
            )
        )
        top_items["Situação"] = (
            top_items[
                "item_status"
            ].map(
                COST_ITEM_STATUS
            )
        )

        st.subheader(
            "Itens de maior impacto"
        )
        st.dataframe(
            top_items[
                [
                    "Item",
                    "Categoria",
                    "Valor final",
                    "Situação",
                ]
            ],
            hide_index=True,
            width="stretch",
            column_config={
                "Valor final": (
                    st.column_config
                    .NumberColumn(
                        format="R$ %.2f"
                    )
                )
            },
        )

    st.divider()
    st.subheader(
        "Correlação com as fichas da Memória"
    )
    st.caption(
        "As sugestões são aproximadas. Revise antes "
        "de confirmar; uma linha de custo pode permanecer "
        "sem associação."
    )

    memory_options = {
        (
            str(row.get("title") or "Sem título")
            + " · Slide "
            + str(
                row.get("source_page")
                or ""
            )
            + " · "
            + str(row.get("id"))[:6]
        ): str(row.get("id"))
        for row in _safe_records(
            memory_items
        )
    }
    reverse_options = {
        value: key
        for key, value
        in memory_options.items()
    }

    link_records = _safe_records(
        links
    )
    link_by_cost: dict[
        str,
        dict,
    ] = {}

    for link in link_records:
        cost_item_id = str(
            link.get(
                "cost_item_id"
            )
        )
        current = link_by_cost.get(
            cost_item_id
        )

        if (
            current is None
            or (
                link.get(
                    "link_status"
                )
                == "confirmed"
                and current.get(
                    "link_status"
                )
                != "confirmed"
            )
            or float(
                link.get(
                    "match_score"
                )
                or 0
            )
            > float(
                current.get(
                    "match_score"
                )
                or 0
            )
        ):
            link_by_cost[
                cost_item_id
            ] = link

    correlation_rows = []

    for cost in _safe_records(
        costs
    ):
        cost_id = str(cost["id"])
        link = link_by_cost.get(
            cost_id,
            {},
        )
        memory_item_id = str(
            link.get(
                "memory_item_id"
            )
            or ""
        )

        correlation_rows.append(
            {
                "_cost_item_id": (
                    cost_id
                ),
                "Item da planilha": (
                    cost.get(
                        "item_name"
                    )
                ),
                "Valor": (
                    cost.get(
                        "client_total"
                    )
                ),
                "Ficha da Memória": (
                    reverse_options.get(
                        memory_item_id,
                        "Sem associação",
                    )
                ),
                "Confiança": round(
                    float(
                        link.get(
                            "match_score"
                        )
                        or 0
                    )
                    * 100,
                    1,
                ),
                "Origem": (
                    "Confirmada"
                    if link.get(
                        "link_status"
                    )
                    == "confirmed"
                    else (
                        "Sugerida"
                        if link
                        else "Sem associação"
                    )
                ),
                "_reason": (
                    link.get(
                        "match_reason"
                    )
                ),
            }
        )

    correlation_df = pd.DataFrame(
        correlation_rows
    )

    edited_correlations = (
        st.data_editor(
            correlation_df,
            hide_index=True,
            width="stretch",
            height=520,
            key=(
                "phase14_correlations_"
                + project_id
            ),
            column_config={
                "_cost_item_id": None,
                "_reason": None,
                "Ficha da Memória": (
                    st.column_config
                    .SelectboxColumn(
                        "Ficha da Memória",
                        options=[
                            "Sem associação",
                            *memory_options.keys(),
                        ],
                    )
                ),
                "Valor": (
                    st.column_config
                    .NumberColumn(
                        format="R$ %.2f"
                    )
                ),
                "Confiança": (
                    st.column_config
                    .ProgressColumn(
                        min_value=0,
                        max_value=100,
                        format="%.1f%%",
                    )
                ),
            },
            disabled=[
                "Item da planilha",
                "Valor",
                "Confiança",
                "Origem",
            ],
        )
    )

    if st.button(
        "Salvar correlações",
        type="primary",
        width="stretch",
        key=(
            "phase14_save_correlations_"
            + project_id
        ),
    ):
        correlations = []

        for row in (
            edited_correlations
            .to_dict(
                orient="records"
            )
        ):
            selected_label = str(
                row.get(
                    "Ficha da Memória"
                )
                or "Sem associação"
            )

            correlations.append(
                {
                    "cost_item_id": (
                        row[
                            "_cost_item_id"
                        ]
                    ),
                    "memory_item_id": (
                        memory_options.get(
                            selected_label
                        )
                    ),
                    "match_score": (
                        float(
                            row.get(
                                "Confiança"
                            )
                            or 0
                        )
                        / 100
                    ),
                    "match_reason": (
                        row.get(
                            "_reason"
                        )
                        or "Correlação revisada manualmente"
                    ),
                }
            )

        save_cost_correlations(
            client,
            project_id=project_id,
            correlations=correlations,
        )
        st.success(
            "Correlações atualizadas."
        )
        st.rerun()

    st.divider()
    st.subheader(
        "Planilhas vinculadas"
    )

    for document in _safe_records(
        documents
    ):
        with st.container(
            border=True,
        ):
            doc_col1, doc_col2 = (
                st.columns(
                    [3, 1]
                )
            )

            with doc_col1:
                st.markdown(
                    "### "
                    + str(
                        document.get(
                            "title"
                        )
                        or document.get(
                            "file_name"
                        )
                    )
                )
                st.caption(
                    str(
                        document.get(
                            "sheet_name"
                        )
                        or "Aba não informada"
                    )
                    + " · "
                    + str(
                        document.get(
                            "total_items"
                        )
                        or 0
                    )
                    + " itens"
                )

            with doc_col2:
                st.metric(
                    "Total",
                    _money(
                        document.get(
                            "client_total"
                        ),
                        document.get(
                            "currency"
                        )
                        or "BRL",
                    ),
                )

            download_url = (
                create_cost_signed_url(
                    client,
                    document.get(
                        "storage_path"
                    ),
                    storage_bucket=(
                        document.get(
                            "storage_bucket"
                        )
                    ),
                    download=True,
                )
            )

            if download_url:
                st.link_button(
                    "Abrir planilha original",
                    download_url,
                    width="stretch",
                )

            diagnostic = (
                document.get(
                    "diagnostic"
                )
                or {}
            )

            for warning in (
                diagnostic.get(
                    "warnings"
                )
                or []
            ):
                st.warning(
                    str(warning)
                )

            with st.expander(
                "Excluir planilha",
                expanded=False,
            ):
                confirmation = (
                    st.text_input(
                        "Digite EXCLUIR",
                        key=(
                            "delete_cost_confirm_"
                            + str(
                                document["id"]
                            )
                        ),
                    )
                )

                if st.button(
                    "Excluir planilha",
                    disabled=(
                        confirmation
                        .strip()
                        .upper()
                        != "EXCLUIR"
                    ),
                    key=(
                        "delete_cost_"
                        + str(
                            document["id"]
                        )
                    ),
                    width="stretch",
                ):
                    delete_cost_document(
                        client,
                        document_id=str(
                            document["id"]
                        ),
                    )
                    st.success(
                        "Planilha excluída."
                    )
                    st.rerun()
