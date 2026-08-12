from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from nave_storage import get_bytes as storage_get_bytes


def _money(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "Não informado"
    formatted = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _list_block(title: str, values: list[Any]) -> None:
    st.markdown(f"**{title}**")
    if not values:
        st.caption("Não identificado no relatório.")
        return
    for value in values:
        st.markdown(f"- {value}")


def render_report_analyses(snapshot: dict[str, Any]) -> None:
    analyses = snapshot.get("report_analyses", [])
    if not analyses:
        return
    latest = analyses[0]
    st.markdown("#### Leitura estruturada do relatório")
    metrics = st.columns(4)
    metrics[0].metric("Participantes", latest.get("participants_count") or "—")
    metrics[1].metric("Custo previsto", _money(latest.get("planned_cost")))
    metrics[2].metric("Custo realizado", _money(latest.get("actual_cost")))
    planned = latest.get("planned_cost")
    actual = latest.get("actual_cost")
    if planned not in (None, 0, "") and actual not in (None, ""):
        try:
            variation = float(actual) - float(planned)
            metrics[3].metric("Variação", _money(variation))
        except Exception:
            metrics[3].metric("Variação", "—")
    else:
        metrics[3].metric("Variação", "—")
    if latest.get("executive_summary"):
        st.info(str(latest.get("executive_summary")))
    if latest.get("objectives_result"):
        st.markdown("**Resultado dos objetivos**")
        st.write(latest.get("objectives_result"))
    cols = st.columns(2)
    with cols[0]:
        _list_block("Destaques", latest.get("highlights") or [])
        _list_block("Aprendizados", latest.get("learnings") or [])
    with cols[1]:
        _list_block("Ocorrências e pontos de atenção", latest.get("issues") or [])
        _list_block("Recomendações futuras", latest.get("recommendations") or [])
    kpis = latest.get("kpis") or []
    if kpis:
        st.markdown("**Indicadores e resultados**")
        st.dataframe(pd.DataFrame(kpis), hide_index=True, width="stretch")
    activation_results = latest.get("activation_results") or []
    if activation_results:
        st.markdown("**Resultados por ativação ou entrega**")
        st.dataframe(pd.DataFrame(activation_results), hide_index=True, width="stretch")
    supplier_evaluations = latest.get("supplier_evaluations") or []
    if supplier_evaluations:
        st.markdown("**Avaliação de fornecedores**")
        st.dataframe(pd.DataFrame(supplier_evaluations), hide_index=True, width="stretch")
    media_results = latest.get("media_results") or []
    if media_results:
        st.markdown("**Resultados de mídia e conteúdo**")
        st.dataframe(pd.DataFrame(media_results), hide_index=True, width="stretch")
    feedbacks = latest.get("client_feedback") or []
    if feedbacks:
        st.markdown("**Feedbacks extraídos do relatório**")
        for feedback in feedbacks:
            if isinstance(feedback, dict):
                st.markdown(f"- {feedback.get('text') or feedback.get('feedback') or feedback}")
            else:
                st.markdown(f"- {feedback}")


def render_pending_report_actions(
    client,
    *,
    project_id: str,
    snapshot: dict[str, Any],
    report_role: str,
) -> None:
    from project_report_extractor import analyze_project_report
    from project_workspace_db import save_project_report_analysis

    analysed_ids = {
        str(row.get("report_file_id"))
        for row in snapshot.get("report_analyses", [])
        if row.get("report_file_id")
    }
    pending = [
        row
        for row in snapshot.get("project_files", [])
        if row.get("file_role") == report_role
        and not row.get("is_archived")
        and str(row.get("id")) not in analysed_ids
    ]
    if not pending:
        return

    st.warning(
        "Há relatório anexado sem leitura estruturada. "
        "Analise-o para preencher resultados, indicadores, feedbacks e aprendizados."
    )

    for row in pending:
        file_id = str(row.get("id"))
        file_name = str(row.get("file_name") or row.get("title") or "Relatório")
        if st.button(
            f"Analisar arquivo já anexado — {file_name}",
            key=f"analyse_existing_report_{file_id}",
            width="stretch",
        ):
            try:
                bucket = str(row.get("storage_bucket") or "nave-project-files")
                path = str(row.get("storage_path") or "")
                if not path:
                    raise RuntimeError("O caminho do arquivo não foi encontrado.")
                file_bytes = storage_get_bytes(client, bucket_name=bucket, path=path)
                if not file_bytes:
                    raise RuntimeError("O arquivo não pôde ser baixado do armazenamento privado.")
                api_key = (
                    st.secrets.get("GEMINI_API_KEY")
                    or st.secrets.get("GOOGLE_API_KEY")
                )
                model = st.secrets.get("GEMINI_MODEL")
                report_type = "closure" if report_role == "closure_report" else "post_execution"
                with st.spinner(
                    "Lendo o relatório e aplicando os dados ao projeto..."
                ):
                    analysis = analyze_project_report(
                        file_name=file_name,
                        mime_type=row.get("mime_type"),
                        file_bytes=file_bytes,
                        report_type=report_type,
                        api_key=str(api_key or ""),
                        model=str(model or "") or None,
                    )
                    save_project_report_analysis(
                        client,
                        project_id=project_id,
                        report_file_id=file_id,
                        report_type=report_type,
                        analysis=analysis,
                    )
            except Exception as exc:
                st.error(f"Não foi possível analisar o relatório: {exc}")
            else:
                st.success(
                    "Relatório analisado e aplicado ao projeto."
                )
                st.rerun()
