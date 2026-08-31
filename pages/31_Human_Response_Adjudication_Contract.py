from __future__ import annotations

from datetime import datetime, timezone
import json

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_human_response_adjudication_contract import (
    HUMAN_RESPONSE_ADJUDICATION_VERSION,
    DECISION_LABELS_PT,
    LABEL_TO_DECISION,
    build_human_adjudication_package,
    run_human_adjudication_queue,
)

st.set_page_config(
    page_title="Human Response Adjudication Contract | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Human Response Adjudication Contract",
    "B2.12 transforma a fila B2.11 em decisões humanas explícitas com provenance completo. Nada é decidido por padrão, nada é persistido e nenhuma decisão altera Truth nesta fase.",
    eyebrow=f"NAVE by VOE · {HUMAN_RESPONSE_ADJUDICATION_VERSION} · human review contract",
)

client = get_nave_client()

canaries = (
    client.table("project_domain_consumer_canary")
    .select("*")
    .eq("domain_key", "requirements")
    .eq("consumer_key", "workspace.intelligence.matrix.requirements_readonly")
    .eq("status", "active")
    .execute()
    .data
    or []
)
project_ids = sorted({
    str(row.get("project_id") or "")
    for row in canaries
    if row.get("project_id")
})
if not project_ids:
    st.warning("Nenhum matrix requirements canary ativo encontrado.")
    st.stop()

projects = []
for project_id in project_ids:
    rows = (
        client.table("projects")
        .select("*")
        .eq("id", project_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    row = dict(rows[0]) if rows else {"id": project_id}
    label = (
        row.get("project_name")
        or row.get("event_name")
        or row.get("name")
        or project_id
    )
    projects.append((f"{label} · {project_id}", project_id))

selected = st.selectbox("Projeto", [label for label, _ in projects])
project_id = dict(projects)[selected]

queue_key = f"b212_queue::{project_id}"
package_key = f"b212_package::{project_id}"

if st.button("Carregar fila de adjudicação B2.12", type="primary"):
    try:
        state = get_cutover_state(client, project_id, "requirements")
        if state.get("read_mode") != "shadow_compare":
            st.error("B2.12 BLOCKED: requirements não está em shadow_compare.")
            st.stop()

        briefing_canary = fetch_active_canary(
            client,
            project_id=project_id,
            domain_key="requirements",
            consumer_key="workspace.briefing.requirements_readonly",
        )
        matrix_canary = fetch_active_canary(
            client,
            project_id=project_id,
            domain_key="requirements",
            consumer_key="workspace.intelligence.matrix.requirements_readonly",
        )
        if not briefing_canary or not matrix_canary:
            st.error(
                "B2.12 BLOCKED: briefing/matrix requirements canaries devem permanecer ativos."
            )
            st.stop()

        with st.spinner("Montando fila B2.12 a partir da projeção governada B2.11..."):
            queue = run_human_adjudication_queue(
                client,
                project_id=project_id,
            )
        st.session_state[queue_key] = queue
        st.session_state.pop(package_key, None)
    except Exception as exc:
        st.error(f"B2.12 BLOCKED: {type(exc).__name__}: {exc}")

queue = st.session_state.get(queue_key)
if queue is None:
    st.info(
        "Carregue a fila para iniciar a adjudicação. A fila contém apenas requirements em estado de revisão no B2.11; respostas já verificadas, falsos positivos excluídos e requirements sem resposta segura permanecem apenas como contexto."
    )
    st.stop()

st.caption(
    "Governança: a decisão humana desta página existe apenas no pacote exportado. "
    "Não há INSERT/UPDATE no Supabase, não há Human Review persistido e não há efeito em Truth. "
    "A opção inicial `— Selecione —` não conta como decisão."
)

st.dataframe(
    pd.DataFrame([{
        "version": HUMAN_RESPONSE_ADJUDICATION_VERSION,
        "project_id": queue.project_id,
        "source_projection_status": queue.source_projection_status,
        "total_requirements": queue.total_requirements,
        "adjudication_queue": queue.queue_count,
        "high_confidence": queue.high_confidence_count,
        "partial": queue.partial_count,
        "visual_or_structured": queue.visual_or_structured_count,
        "existing_review": queue.existing_review_count,
        "false_positive_excluded_context": queue.context_false_positive_excluded_count,
        "no_safe_response_context": queue.context_no_safe_response_count,
        "truth_changed": False,
        "persistence_performed": False,
    }]),
    hide_index=True,
    width="stretch",
)

if not queue.queue_rows:
    st.success("B2.12: não há rows de review para adjudicar neste projeto.")
    st.stop()

st.markdown("#### Fila para decisão humana")
st.info(
    "As DUAS PRIMEIRAS COLUNAS são as únicas que você precisa preencher: "
    "**Decisão humana** e **Justificativa humana**. Os 3 high-confidence aparecem primeiro. "
    "Você pode decidir apenas alguns itens e validar um PARTIAL_DRAFT antes de continuar."
)
st.caption(
    "Decisões permitidas: Confirmar resposta, Resposta parcial, Rejeitar correspondência, "
    "Requer revisão visual/estruturada ou Adiar decisão. Confirmar, parcial ou rejeitar exige justificativa humana."
)

reviewer = st.text_input(
    "Revisor",
    value="",
    placeholder="Nome ou identificação do revisor humano",
    help="Obrigatório quando houver qualquer decisão explícita.",
)

base = pd.DataFrame(list(queue.queue_rows))

def _preview(value: object, limit: int = 700) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"

editor = pd.DataFrame({
    "decisao": [DECISION_LABELS_PT[""]] * len(base),
    "justificativa_humana": [""] * len(base),
    "requirement": base["requirement_title"],
    "status_b2_11": base["projected_response_status"],
    "evidencia": base["evidence_locator"].fillna(""),
    "texto_evidencia": base["evidence_text"].fillna("").map(_preview),
    "candidate_id": base["candidate_id"],
})

edited = st.data_editor(
    editor,
    hide_index=True,
    width="stretch",
    height=min(900, 170 + len(editor) * 48),
    disabled=[
        "requirement",
        "status_b2_11",
        "evidencia",
        "texto_evidencia",
        "candidate_id",
    ],
    column_config={
        "decisao": st.column_config.SelectboxColumn(
            "Decisão humana",
            options=list(DECISION_LABELS_PT.values()),
            required=True,
            width="medium",
            help="Selecione uma decisão explícita. A opção — Selecione — não conta como decisão.",
        ),
        "justificativa_humana": st.column_config.TextColumn(
            "Justificativa humana",
            width="large",
            help="Obrigatória para Confirmar resposta, Resposta parcial e Rejeitar correspondência.",
        ),
        "requirement": st.column_config.TextColumn("Requirement", width="large"),
        "status_b2_11": st.column_config.TextColumn("Status B2.11", width="medium"),
        "evidencia": st.column_config.TextColumn("Localizador", width="small"),
        "texto_evidencia": st.column_config.TextColumn("Evidência · preview", width="large"),
        "candidate_id": st.column_config.TextColumn("Candidate ID", width="small"),
    },
    key=f"b212_editor::{project_id}",
)

if st.button("Validar pacote de adjudicação", type="secondary"):
    selected_labels = [
        str(row.get("decisao") or "")
        for row in edited.to_dict(orient="records")
        if LABEL_TO_DECISION.get(str(row.get("decisao") or ""), "")
    ]

    if not selected_labels:
        st.session_state.pop(package_key, None)
        st.warning(
            "Nenhuma decisão humana foi selecionada. Escolha pelo menos uma opção na primeira coluna "
            "`Decisão humana` antes de validar."
        )
    else:
        edited_rows = []
        source_by_id = {str(row["candidate_id"]): dict(row) for row in queue.queue_rows}
        for row in edited.to_dict(orient="records"):
            cid = str(row.get("candidate_id") or "")
            source = source_by_id.get(cid)
            if not source:
                continue
            label = str(row.get("decisao") or "")
            edited_rows.append({
                **source,
                "decision": LABEL_TO_DECISION.get(label, ""),
                "human_rationale": str(row.get("justificativa_humana") or ""),
            })

        package = build_human_adjudication_package(
            queue=queue,
            reviewer=reviewer,
            edited_rows=edited_rows,
            adjudicated_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        st.session_state[package_key] = package

package = st.session_state.get(package_key)
if package is not None:
    if package.package_status == "COMPLETE_REVIEW_PACKAGE":
        st.success(
            "B2.12: COMPLETE_REVIEW_PACKAGE · todas as rows da fila receberam uma decisão humana explícita. "
            "O pacote continua sem efeito em Truth até uma fase posterior separada."
        )
    elif package.package_status == "PARTIAL_DRAFT":
        st.warning(
            f"B2.12: PARTIAL_DRAFT · {package.explicitly_decided_count} de {package.queue_count} rows receberam decisão explícita."
        )
    elif package.package_status == "EMPTY_DRAFT":
        st.info("B2.12: EMPTY_DRAFT · nenhuma decisão explícita foi registrada.")
    else:
        st.error("B2.12: INVALID_DRAFT · corrija os erros de validação antes de tratar o pacote como adjudicação válida.")

    st.dataframe(
        pd.DataFrame([{
            "package_status": package.package_status,
            "queue_count": package.queue_count,
            "explicitly_decided": package.explicitly_decided_count,
            "undecided": package.undecided_count,
            "confirmed": package.confirmed_count,
            "partial": package.partial_count,
            "rejected": package.rejected_count,
            "visual_review": package.visual_review_count,
            "deferred": package.deferred_count,
            "truth_effect_applied": False,
            "persistence_performed": False,
        }]),
        hide_index=True,
        width="stretch",
    )

    if package.validation_errors:
        st.markdown("#### Erros de validação")
        for error in package.validation_errors:
            st.error(error)

    package_df = pd.DataFrame(list(package.decision_rows))
    st.markdown("#### Pacote de adjudicação")
    st.dataframe(
        package_df,
        hide_index=True,
        width="stretch",
        height=min(1000, 160 + len(package_df) * 42),
    )

    st.download_button(
        "Baixar pacote B2.12 em CSV",
        data=package_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"NAVE_B2_12_HUMAN_ADJUDICATION_{project_id}.csv",
        mime="text/csv",
    )
    st.download_button(
        "Baixar pacote B2.12 completo em JSON",
        data=json.dumps(
            package.to_dict(),
            ensure_ascii=False,
            indent=2,
            default=str,
        ).encode("utf-8"),
        file_name=f"NAVE_B2_12_HUMAN_ADJUDICATION_{project_id}.json",
        mime="application/json",
    )

with st.expander("Contexto fora da fila de adjudicação"):
    st.caption(
        "Estas rows não recebem decisão no B2.12: falsos positivos já excluídos ou requirements sem resposta segura. "
        "Elas permanecem visíveis para auditoria e não são convertidas em review por conveniência."
    )
    context = pd.DataFrame(list(queue.context_rows))
    if context.empty:
        st.info("Nenhuma row de contexto.")
    else:
        st.dataframe(context, hide_index=True, width="stretch")