from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_batch_ingestion import (
    LABEL_TO_ROLE,
    ROLE_LABELS,
    TARGET_SECTIONS,
    ProjectBatchError,
    fetch_projects,
    infer_project_name,
    prepare_documents,
    rank_project_candidates,
    save_project_bundle,
)
from project_bundle_materializer import reprocess_project_semantically

st.set_page_config(
    page_title="Importar projeto completo | NAVE by VOE",
    page_icon=NAVE_APP_ICON,
    layout="wide",
)

enforce_existing_app_access()
apply_nave_branding()
page_header(
    "Importar projeto completo",
    "Envie briefing, proposta, orçamento, planilha, apresentação, feedbacks e relatórios em um único lote. A NAVE organiza os papéis, evita duplicidade de projeto e prepara cada arquivo para a área correta do workspace.",
    eyebrow="NAVE by VOE · V28.7.2B",
)

client = get_nave_client()


def _domain_result(container: dict) -> dict:
    direct = container.get("domain_normalization") if isinstance(container, dict) else None
    if isinstance(direct, dict):
        return direct
    finalization = container.get("project_intelligence_finalization") if isinstance(container, dict) else None
    if isinstance(finalization, dict) and isinstance(finalization.get("domain_normalization"), dict):
        return finalization["domain_normalization"]
    return {}


def _reconciliation_result(container: dict) -> dict:
    direct = container.get("domain_reconciliation") if isinstance(container, dict) else None
    if isinstance(direct, dict):
        return direct
    finalization = container.get("project_intelligence_finalization") if isinstance(container, dict) else None
    if isinstance(finalization, dict) and isinstance(finalization.get("domain_reconciliation"), dict):
        return finalization["domain_reconciliation"]
    return {}


def _core_semantic_result(container: dict) -> dict:
    direct = container.get("core_semantics") if isinstance(container, dict) else None
    if isinstance(direct, dict):
        return direct
    finalization = container.get("project_intelligence_finalization") if isinstance(container, dict) else None
    if isinstance(finalization, dict) and isinstance(finalization.get("core_semantics"), dict):
        return finalization["core_semantics"]
    return {}


def _render_core_semantics(container: dict, *, expanded: bool = False) -> None:
    result = _core_semantic_result(container)
    if not result:
        return
    status = str(result.get("status") or "")
    if status == "schema_missing":
        st.warning(
            "Core Semantic Domains V28.7.2B ainda não estão visíveis no Data API. "
            "Execute NAVE_V28_7_2B_CORE_SEMANTIC_DOMAINS.sql no Supabase e rode novamente."
        )
        return
    if status in {"schema_check_error", "transaction_error", "orchestration_error", "blocked"}:
        st.error("A V28.7.2B não promoveu uma nova geração de Strategy / Creative / Experience. A V28.7.2A anterior permanece válida.")
        for warning in (result.get("warnings") or [])[:10]:
            if str(warning).strip():
                st.caption("• " + str(warning))
        return
    if status != "completed":
        st.warning(f"Core Semantic Domains V28.7.2B: {status or 'status desconhecido'}.")
        return

    core = result.get("core_semantics") or {}
    actions = result.get("actions") or {}
    with st.expander("Core Semantic Domains · Strategy / Creative / Experience · V28.7.2B", expanded=expanded):
        cols = st.columns(6)
        cols[0].metric("Strategy", int(core.get("strategy_elements") or actions.get("strategy_elements") or 0))
        cols[1].metric("Creative platforms", int(core.get("creative_platforms") or actions.get("creative_platforms") or 0))
        cols[2].metric("Creative elements", int(core.get("creative_elements") or actions.get("creative_elements") or 0))
        cols[3].metric("Experience architectures", int(core.get("experience_architectures") or actions.get("experience_architectures") or 0))
        cols[4].metric("Journey moments", int(core.get("journey_moments") or actions.get("journey_moments") or 0))
        cols[5].metric("Semantic observations", int(core.get("semantic_observations") or actions.get("observations") or 0))

        truth_cols = st.columns(5)
        truth_cols[0].metric("Verified explicit", int(core.get("verified_explicit") or 0))
        truth_cols[1].metric("Verified synthesis", int(core.get("verified_synthesis") or 0))
        truth_cols[2].metric("Human confirmed", int(core.get("human_confirmed") or 0))
        truth_cols[3].metric("Review required", int(core.get("review_required") or 0))
        truth_cols[4].metric("Unsupported", int(core.get("unsupported") or 0))

        rel_cols = st.columns(3)
        rel_cols[0].metric("Fact relations", int(core.get("fact_relations") or 0))
        rel_cols[1].metric("Inference relations", int(core.get("inference_relations") or 0))
        rel_cols[2].metric("Observações open", int(core.get("semantic_observations_open") or 0))

        st.caption(
            f"Migration mode: {core.get('migration_mode') or 'legacy_shadow'} · "
            f"Domain schema: {core.get('domain_schema_version') or '28.7.2b'} · "
            f"Run: {result.get('run_id') or core.get('last_completed_run_id') or '—'}"
        )
        st.caption(
            "Fonte explícita, síntese evidence-backed e leitura do Analyst são estados diferentes. "
            "Nesta shadow release, o extrator automático promove apenas semântica explicitamente sustentada pela fonte. "
            "Journey não é Solution e nenhuma relação crítica vira fact apenas por proximidade no projeto."
        )

        strategy_titles = [str(v) for v in (actions.get("strategy_titles") or []) if str(v).strip()]
        creative_names = [str(v) for v in (actions.get("creative_names") or []) if str(v).strip()]
        journey_titles = [str(v) for v in (actions.get("journey_titles") or []) if str(v).strip()]
        if strategy_titles or creative_names or journey_titles:
            with st.expander("Core Semantics · objetos desta run", expanded=False):
                if strategy_titles:
                    st.markdown("**Strategy Elements**")
                    st.caption(" · ".join(strategy_titles))
                if creative_names:
                    st.markdown("**Creative Platforms**")
                    st.caption(" · ".join(creative_names))
                if journey_titles:
                    st.markdown("**Journey Moments**")
                    st.caption(" · ".join(journey_titles))


def _render_domain_reconciliation(container: dict, *, expanded: bool = False) -> None:
    result = _reconciliation_result(container)
    if not result:
        return
    status = str(result.get("status") or "")
    if status == "schema_missing":
        st.warning(
            "Semantic Domain Reconciliation V28.7.2A ainda não está visível no Data API. "
            "Execute NAVE_V28_7_2A_RECONCILIATION_KERNEL.sql no Supabase e rode novamente."
        )
        return
    if status in {"schema_check_error", "transaction_error", "orchestration_error", "blocked"}:
        st.error("A V28.7.2A não aplicou uma nova reconciliação. O domínio anterior permanece válido.")
        for warning in (result.get("warnings") or [])[:10]:
            if str(warning).strip():
                st.caption("• " + str(warning))
        return
    if status != "completed":
        st.warning(f"Semantic Domain Reconciliation: {status or 'status desconhecido'}.")
        return

    rec = result.get("reconciliation") or {}
    actions = result.get("actions") or {}
    with st.expander("Core Semantic Domains · Reconciliation Kernel · V28.7.2A", expanded=expanded):
        cols = st.columns(7)
        cols[0].metric("Observações", int(rec.get("observations_total") or actions.get("observations") or 0))
        cols[1].metric("Open", int(rec.get("observations_open") or 0))
        cols[2].metric("Reconciliadas", int(rec.get("observations_reconciled") or 0))
        cols[3].metric("Review required", int(rec.get("observations_review_required") or 0))
        cols[4].metric("No-domain", int(rec.get("observations_no_domain_object") or 0))
        cols[5].metric("Soluções", int(rec.get("solution_instances") or 0))
        cols[6].metric("Cobertura evidence-led", f"{float(rec.get('evidence_reconciliation_coverage_pct') or 0):.1f}%")

        lifecycle_cols = st.columns(5)
        lifecycle_cols[0].metric("Soluções reconciliadas por evidence", int(rec.get("evidence_reconciled_solutions") or 0))
        lifecycle_cols[1].metric("Novas evidence-led", int(rec.get("evidence_led_created_solutions") or actions.get("new_solutions") or 0))
        lifecycle_cols[2].metric("Execuções com evidence", int(rec.get("execution_occurrences_with_evidence") or 0))
        lifecycle_cols[3].metric("Execution truth verified", int(rec.get("verified_execution_outcomes") or 0))
        lifecycle_cols[4].metric("Constraints", int(rec.get("requirement_constraints") or 0))

        context_cols = st.columns(4)
        context_cols[0].metric("Context elements", int(rec.get("context_elements") or 0))
        context_cols[1].metric("Ocorrências aplicadas", int(actions.get("occurrences") or 0))
        context_cols[2].metric("Outcomes de execução", int(actions.get("execution_outcomes") or 0))
        context_cols[3].metric("Outcomes de proposta", int(actions.get("proposal_outcomes") or 0))

        st.caption(
            f"Migration mode: {rec.get('migration_mode') or 'legacy_shadow'} · "
            f"Domain schema: {rec.get('domain_schema_version') or '28.7.2a'} · "
            f"Run: {result.get('run_id') or rec.get('last_completed_run_id') or '—'}"
        )
        st.caption(
            "Evidence → Semantic Observation → Reconciliation → Domain. Cobertura evidence-led é um proxy de reconciliação, não um gate de cutover. "
            "A V28.7.2A pode anexar uma nova ocorrência a uma identidade inequívoca, mas nunca faz auto-merge de duas identities existentes. "
            "Graph V28.6 continua congelado e migration_mode permanece legacy_shadow."
        )

        new_names = [str(v) for v in (actions.get("new_solution_names") or []) if str(v).strip()]
        review_names = [str(v) for v in (actions.get("review_names") or []) if str(v).strip()]
        no_domain_names = [str(v) for v in (actions.get("no_domain_names") or []) if str(v).strip()]
        execution_names = [str(v) for v in (actions.get("execution_names") or []) if str(v).strip()]
        if new_names or review_names or no_domain_names or execution_names:
            with st.expander("Reconciliation · decisões desta run", expanded=False):
                if new_names:
                    st.markdown("**Novas Project Solution Instances evidence-led**")
                    st.caption(" · ".join(new_names))
                if execution_names:
                    st.markdown("**Execuções ligadas a Evidence**")
                    st.caption(" · ".join(execution_names))
                if review_names:
                    st.markdown("**Observações bloqueadas para revisão**")
                    st.caption(" · ".join(review_names))
                if no_domain_names:
                    st.markdown("**Observações preservadas sem virar Solution**")
                    st.caption(" · ".join(no_domain_names))


def _render_domain_normalization(container: dict, *, expanded: bool = False) -> None:
    domain = _domain_result(container)
    if not domain:
        return
    status = str(domain.get("status") or "")
    if status == "schema_missing":
        st.warning(
            "Domain Truth Gate V28.7.1D não está visível no Data API. Execute/revalide o SQL "
            "NAVE_V28_7_1D_DOMAIN_TRUTH_GATE_LEGACY_ISOLATION.sql e rode esta ação novamente."
        )
        return
    if status == "schema_check_error":
        st.error(
            "Não foi possível validar o schema de Domain Truth Gate. Isso não será tratado como migration ausente nem como banco vazio."
        )
        for warning in (domain.get("warnings") or [])[:8]:
            st.caption("• " + str(warning))
        return
    if status in {"read_or_validation_error", "transaction_error", "post_apply_read_error", "orchestration_error", "completed_with_gate_warning"}:
        st.error("Domain Truth Gate não promoveu uma nova geração. O estado anterior permanece válido.")
        for warning in (domain.get("warnings") or [])[:8]:
            st.caption("• " + str(warning))
        return

    parity = domain.get("parity") or {}
    normalized = parity.get("normalized") or {}
    legacy = parity.get("legacy") or {}
    integrity = parity.get("integrity") or {}

    with st.expander("Domain Truth Gate & Legacy Isolation · V28.7.1D", expanded=expanded):
        cols = st.columns(6)
        cols[0].metric("Soluções", int(normalized.get("solution_instances") or domain.get("solution_instances") or 0))
        cols[1].metric("Ocorrências", int(normalized.get("solution_occurrences") or domain.get("solution_occurrences") or 0))
        cols[2].metric("Requisitos", int(normalized.get("requirements") or domain.get("requirements") or 0))
        cols[3].metric("Linhas financeiras", int(normalized.get("financial_line_items") or domain.get("financial_line_items") or 0))
        cols[4].metric("Current truth", int(normalized.get("outcomes") or 0))
        cols[5].metric(
            "Outcomes verificáveis",
            f"{int(normalized.get('outcomes_verified') or 0)}/{int(normalized.get('outcomes_total') or 0)}",
        )

        truth_cols = st.columns(5)
        truth_cols[0].metric("Verified", int(normalized.get("outcomes_verified") or 0))
        truth_cols[1].metric("Legacy unverified", int(normalized.get("outcomes_legacy_unverified") or 0))
        truth_cols[2].metric("Inferred", int(normalized.get("outcomes_inferred") or 0))
        truth_cols[3].metric("Conflicted", int(normalized.get("outcomes_conflicted") or 0))
        truth_cols[4].metric("Truth Gate", "PASS" if integrity.get("truth_gate_passed") else "REVIEW")

        proposal_total = int(integrity.get("proposal_outcomes_total") or 0)
        proposal_verified = int(integrity.get("proposal_outcomes_verified") or 0)
        execution_total = int(integrity.get("execution_outcomes_total") or 0)
        execution_verified = int(integrity.get("execution_outcomes_verified") or 0)
        commercial_total = int(integrity.get("commercial_outcomes_total") or 0)
        commercial_verified = int(integrity.get("commercial_outcomes_verified") or 0)
        st.caption(
            "Outcome provenance · "
            f"proposal {proposal_verified}/{proposal_total} · "
            f"execution {execution_verified}/{execution_total} · "
            f"commercial {commercial_verified}/{commercial_total}."
        )

        evidence_cols = st.columns(4)
        evidence_cols[0].metric("Evidence links", int(normalized.get("evidence_links") or domain.get("evidence_links") or 0))
        evidence_cols[1].metric(
            "Ocorrências com evidência",
            f"{int(normalized.get('occurrences_with_evidence') or 0)}/{int(normalized.get('solution_occurrences') or 0)}",
        )
        evidence_cols[2].metric(
            "Requisitos com evidência",
            f"{int(normalized.get('requirements_with_evidence') or 0)}/{int(normalized.get('requirements') or 0)}",
        )
        evidence_cols[3].metric(
            "Custos com evidência",
            f"{int(normalized.get('financial_lines_with_evidence') or 0)}/{int(normalized.get('financial_line_items') or 0)}",
        )

        audit_cols = st.columns(2)
        audit_cols[0].metric("Coverage gaps", int(integrity.get("coverage_findings_open") or 0))
        audit_cols[1].metric("Identity conflicts", int(integrity.get("identity_conflicts_open") or 0))

        migration_mode = str(integrity.get("migration_mode") or "legacy_shadow")
        schema_version = str(integrity.get("domain_schema_version") or "28.7.1d")
        st.caption(
            f"Migration mode: {migration_mode} · Domain schema: {schema_version} · "
            f"Run: {domain.get('run_id') or integrity.get('last_completed_run_id') or '—'}"
        )
        breakdown = integrity.get("outcome_breakdown") or {}
        if breakdown:
            st.caption("Current truth por tipo: " + " · ".join(f"{key} {value}" for key, value in sorted(breakdown.items())))

        reduction = int(parity.get("solution_occurrence_reduction") or 0)
        if reduction > 0:
            st.success(
                f"{reduction} ocorrência(s) memory_items foram consolidadas em instâncias de solução do projeto, sem perder os registros legados."
            )
        st.caption(
            "V28.7.1D mantém legacy_shadow. Outcome legado sem Evidence Unit, Claim auditável ou Human Review continua preservado, "
            "mas não pode decidir current truth. O Graph V28.6 permanece congelado e não participa destes gates."
        )
        if legacy:
            st.caption(
                "Paridade legacy → domínio: "
                f"memory_items {int(legacy.get('memory_items') or 0)} · "
                f"requisitos {int(legacy.get('requirements') or 0)} · "
                f"docs custo {int(legacy.get('cost_documents') or 0)} · "
                f"linhas custo {int(legacy.get('cost_items') or 0)}."
            )
        domain_warnings = [str(v) for v in (domain.get("warnings") or []) if str(v).strip()]
        if domain_warnings:
            with st.expander(f"Lacunas de provenance / integridade ({len(domain_warnings)})", expanded=False):
                for warning in domain_warnings[:20]:
                    st.caption("• " + warning)
                if len(domain_warnings) > 20:
                    st.caption(f"… e mais {len(domain_warnings) - 20} aviso(s). Ausência de evidence_unit é diagnóstico; a NAVE não inventa vínculo para fechar cobertura.")


# Migrações/reprocessamentos são explícitos. Abrir a página nunca altera dados.
# A rotina legada continua disponível somente quando o usuário solicita correção.

with st.expander("Corrigir um projeto importado por uma versão anterior da V28", expanded=False):
    st.caption(
        "Use quando um projeto já importado precisar de uma nova leitura especializada. "
        "A NAVE preserva os masters e a materialização válida anterior; a nova leitura só substitui a anterior depois de passar pelos gates de cobertura e qualidade."
    )
    try:
        repair_projects = fetch_projects(client)
    except Exception as exc:
        repair_projects = []
        st.warning(f"Não foi possível consultar os projetos agora: {exc}")
    if repair_projects:
        repair_options = {
            f"{row.get('project_name') or 'Projeto sem nome'} · {row.get('client_brand') or 'cliente não informado'}": str(row.get('id'))
            for row in repair_projects if row.get('id')
        }
        repair_label = st.selectbox(
            "Projeto a reprocessar",
            list(repair_options.keys()),
            key="v2815_reprocess_project",
        )
        confirm_reprocess = st.checkbox(
            "Confirmo o reprocessamento sem alterar arquivos originais nem conteúdo manual.",
            key="v2815_reprocess_confirm",
        )
        if st.button(
            "Reprocessar conteúdo com leitura especializada",
            type="primary",
            width="stretch",
            disabled=not confirm_reprocess,
            key="v2815_reprocess_button",
        ):
            with st.spinner("Reprocessando briefing, apresentação e orçamento já preservados..."):
                outcome = reprocess_project_semantically(client, repair_options[repair_label])
            counts = outcome.get("workspace_counts") or {}
            if outcome.get("errors") or outcome.get("incomplete"):
                st.warning(
                    f"Reprocessamento concluído com diagnóstico: {outcome.get('processed', 0)} arquivo(s) materializado(s), "
                    f"{outcome.get('errors', 0)} erro(s). A NAVE não considera a correção concluída enquanto briefing/apresentação esperados continuarem zerados."
                )
            else:
                st.success(f"{outcome.get('processed', 0)} arquivo(s) reprocessado(s) com a leitura especializada da V28.7.0.")
                st.session_state["nave_project_hub_focus_id"] = repair_options[repair_label]

            if counts:
                metric_cols = st.columns(6)
                metric_cols[0].metric("Briefings", counts.get("briefings", 0))
                metric_cols[1].metric("Apresentações", counts.get("presentations", 0))
                metric_cols[2].metric("Conteúdos", counts.get("contents", 0))
                metric_cols[3].metric("Custos", counts.get("cost_documents", 0))
                metric_cols[4].metric("Feedbacks", counts.get("feedbacks", 0))

            diagnostic_rows = []
            for item in outcome.get("results") or []:
                created = item.get("created") or {}
                diagnostic_rows.append({
                    "Arquivo": item.get("file_name") or item.get("source_file_id"),
                    "Papel anterior": item.get("role_before"),
                    "Papel resolvido": item.get("role_after") or item.get("role"),
                    "Status": item.get("status"),
                    "Criado no workspace": ", ".join(f"{key}: {value}" for key, value in created.items()) or "—",
                    "Observação": " | ".join(str(w) for w in (item.get("warnings") or [])[:3]) or "—",
                })
            if diagnostic_rows:
                with st.expander("Diagnóstico arquivo por arquivo", expanded=bool(outcome.get("errors") or outcome.get("incomplete"))):
                    st.dataframe(pd.DataFrame(diagnostic_rows), hide_index=True, width="stretch")

            _render_domain_normalization(outcome, expanded=False)

            cross = outcome.get("cross_source_intelligence") or {}
            if cross and str(cross.get("status") or "").startswith("completed"):
                with st.expander("Intelligence Graph · conexões entre arquivos", expanded=False):
                    c0, c1, c2, c3, c4, c5 = st.columns(6)
                    canonical = outcome.get("canonical_entity_graph") or {}
                    c0.metric("Entidades canônicas", int(canonical.get("memory_items_considered") or 0))
                    c1.metric("Entidades multi-fonte", int(cross.get("multi_source_entities_total") or 0))
                    c2.metric("Ocorrências ligadas", int(cross.get("unified_occurrences_total") or cross.get("entities_merged") or 0))
                    c3.metric("Solução ↔ custo", int(cross.get("cost_links_total") or cross.get("cost_links") or 0))
                    c4.metric("Execuções ligadas", int(cross.get("execution_claims_total") or cross.get("execution_claims") or 0))
                    c5.metric("Relações hierárquicas", int(cross.get("hierarchy_links_total") or cross.get("hierarchy_links") or 0))
                    reviews = int(cross.get("resolution_reviews") or 0) + int(cross.get("cost_link_reviews") or 0)
                    st.caption(
                        "O Entity Graph V28.6.2 permanece ativo apenas por compatibilidade durante a migração; a V28.7.1 mantém o domínio em legacy_shadow, com provenance e integridade transacional. "
                        f"Revisões ambíguas pendentes: {reviews}."
                    )
                    debug_rows = cross.get("resolution_debug") or []
                    if debug_rows:
                        with st.expander("Diagnóstico do Entity Resolution · por entidade", expanded=False):
                            st.dataframe(pd.DataFrame(debug_rows), hide_index=True, width="stretch")
                            st.caption("Este quadro é técnico e temporário: mostra onde cada entidade ainda perde proposta, execução, custo, briefing ou hierarquia.")

            warnings = list(dict.fromkeys(str(w) for w in (outcome.get("warnings") or []) if str(w).strip()))
            if warnings:
                with st.expander("Avisos técnicos do reprocessamento", expanded=bool(outcome.get("errors") or outcome.get("incomplete"))):
                    for warning in warnings[:30]:
                        st.caption("• " + warning)

            st.page_link("pages/4_Historico_de_Projetos.py", label="Abrir projeto reprocessado")

        if st.button(
            "Reconciliar Core Semantic Domains · V28.7.2B",
            width="stretch",
            disabled=not confirm_reprocess,
            key="v2872b_reconcile_core_domains",
            help="Executa Truth Gate + V28.7.2A reconciliation + audits e, depois, materializa Strategy / Creative Platform / Experience/Journey explicitamente evidence-backed. Não reconstrói o Graph V28.6.",
        ):
            from project_intelligence_pipeline import finalize_project_intelligence

            with st.spinner("Aplicando Truth Gate, reconciliando o domínio e materializando Strategy / Creative / Experience sem reconstruir o Graph legado..."):
                finalization = finalize_project_intelligence(client, repair_options[repair_label], analyze_pending_reports=False)
            _render_domain_normalization(finalization, expanded=False)
            _render_domain_reconciliation(finalization, expanded=False)
            _render_core_semantics(finalization, expanded=True)
            domain = _domain_result(finalization)
            reconciliation = _reconciliation_result(finalization)
            core_semantics = _core_semantic_result(finalization)
            audits = finalization.get("domain_audits") or {}
            domain_ok = str(domain.get("status") or "") == "completed"
            reconciliation_ok = str(reconciliation.get("status") or "") == "completed"
            audits_ok = str(audits.get("status") or "") == "completed"
            core_ok = str(core_semantics.get("status") or "") == "completed"
            if domain_ok and reconciliation_ok and audits_ok and core_ok:
                coverage = audits.get("coverage") or {}
                identity = audits.get("identity") or {}
                st.success(
                    "V28.7.2B materializada em legacy_shadow. Evidence → Observation → Domain agora cobre "
                    "Solutions + Strategy + Creative Platform + Experience/Journey; o Truth Gate permaneceu ativo e o Graph V28.6 continuou congelado."
                )
                st.caption(
                    f"Domain Coverage Audit: {int(coverage.get('findings') or 0)} gap(s) · "
                    f"Identity Audit: {int(identity.get('findings') or 0)} conflito(s). "
                    "Findings não criam, unem ou reclassificam soluções automaticamente."
                )
                missing_names = [str(v) for v in (coverage.get("missing_names") or []) if str(v).strip()]
                conflict_pairs = [pair for pair in (identity.get("conflict_pairs") or []) if isinstance(pair, (list, tuple)) and len(pair) >= 2]
                if missing_names or conflict_pairs:
                    with st.expander("Domain Coverage & Identity Audit · detalhes", expanded=True):
                        if missing_names:
                            st.markdown("**Possíveis soluções ausentes do domínio**")
                            for name in missing_names:
                                st.caption("• " + name)
                        if conflict_pairs:
                            st.markdown("**Conflitos de identidade para revisão**")
                            for left, right, *_rest in conflict_pairs:
                                st.caption(f"• {left} ↔ {right}")
                        st.caption("Na V28.7.2A, Coverage é validado depois da reconciliation. Identity conflict entre identities existentes continua review-required; não existe auto-merge.")
            elif not domain_ok:
                st.error(
                    "Atualização interrompida: Domain Truth Gate não foi promovido. O Graph V28.6 permaneceu congelado e nenhuma síntese nova foi promovida."
                )
            elif not reconciliation_ok:
                st.error(
                    "O Truth Gate foi aplicado, mas a Semantic Domain Reconciliation não terminou. "
                    "Nenhum cutover foi promovido e o Graph V28.6 permaneceu congelado."
                )
            elif not audits_ok:
                st.error(
                    "Truth Gate e reconciliation foram aplicados, mas um dos audits de Coverage/Identity não terminou corretamente. "
                    "O Graph V28.6 permaneceu congelado; consulte os avisos técnicos."
                )
            else:
                st.error(
                    "A V28.7.2A permaneceu válida, mas Strategy / Creative / Experience V28.7.2B não terminou. "
                    "Nenhum cutover foi promovido e o Graph V28.6 permaneceu congelado."
                )
            final_warnings = [str(v) for v in (finalization.get("warnings") or []) if str(v).strip()]
            if final_warnings:
                with st.expander("Avisos da atualização", expanded=False):
                    for warning in final_warnings[:30]:
                        st.caption("• " + warning)

st.markdown("### 1. Arquivos do projeto")
st.caption(
    "Você pode enviar vários arquivos de uma vez. Nesta etapa a NAVE lê sinais do nome e do conteúdo, sugere o papel de cada documento e sempre permite revisar antes de salvar."
)

uploaded = st.file_uploader(
    "Documentos do projeto",
    type=["pdf", "docx", "pptx", "ppt", "xlsx", "xlsm", "xls", "csv", "txt", "md", "eml", "msg", "jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    help="Limite da NAVE: 300 MB por arquivo. Prints e imagens aceitos: JPG, JPEG, PNG e WEBP.",
)

current_signature = tuple(
    (item.name, getattr(item, "size", None), getattr(item, "type", None))
    for item in (uploaded or [])
)

if current_signature != st.session_state.get("v281_upload_signature"):
    for state_key in (
        "v281_documents",
        "v281_review",
        "v281_project_name",
        "v281_project_name_input",
        "v281_client_brand",
        "v281_event_name",
        "v281_role_editor",
        "v281_destination",
    ):
        st.session_state.pop(state_key, None)
    st.session_state["v281_upload_signature"] = current_signature

if uploaded and st.button("Analisar conjunto de documentos", type="primary", width="stretch"):
    with st.spinner("Lendo e organizando o conjunto de documentos..."):
        try:
            source = []
            for item in uploaded:
                data = item.getvalue()
                source.append((item.name, data, getattr(item, "type", None)))
            documents = prepare_documents(source)
            st.session_state["v281_documents"] = documents
            st.session_state["v281_project_name"] = infer_project_name(documents)
            st.session_state["v281_review"] = None
        except ProjectBatchError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"A NAVE não conseguiu analisar o conjunto. Detalhe técnico: {exc}")

documents = st.session_state.get("v281_documents") or []

if documents:
    st.success(f"{len(documents)} arquivo(s) lido(s). Revise a organização antes de importar.")

    st.markdown("### 2. Revisar o papel de cada documento")
    review_rows = []
    for document in documents:
        review_rows.append({
            "Incluir": True,
            "Arquivo": document.name,
            "Papel do documento": document.role_label,
            "Confiança": f"{round(document.role_confidence * 100)}%",
            "Sinais encontrados": "; ".join(document.role_reasons) or "revisão manual",
            "Destino no workspace": " · ".join(document.target_sections),
            "_sha256": document.sha256,
        })
    base_review = pd.DataFrame(review_rows)

    edited = st.data_editor(
        base_review,
        hide_index=True,
        width="stretch",
        disabled=["Arquivo", "Confiança", "Sinais encontrados", "Destino no workspace", "_sha256"],
        column_config={
            "Incluir": st.column_config.CheckboxColumn("Incluir", width="small"),
            "Arquivo": st.column_config.TextColumn("Arquivo", width="large"),
            "Papel do documento": st.column_config.SelectboxColumn(
                "Papel do documento",
                options=list(ROLE_LABELS.values()),
                required=True,
                width="medium",
            ),
            "Confiança": st.column_config.TextColumn("Confiança", width="small"),
            "Sinais encontrados": st.column_config.TextColumn("Sinais encontrados", width="large"),
            "Destino no workspace": st.column_config.TextColumn("Destino no workspace", width="large"),
            "_sha256": None,
        },
        key="v281_role_editor",
    )
    st.caption(
        "Ao alterar o papel do documento, o destino definitivo é recalculado no momento da importação. A coluna acima mostra o destino sugerido na análise inicial."
    )

    st.markdown("### 3. Identidade do projeto")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        project_name = st.text_input(
            "Nome do projeto",
            value=st.session_state.get("v281_project_name", ""),
            key="v281_project_name_input",
        )
    with c2:
        client_brand = st.text_input("Cliente / marca", key="v281_client_brand")
    with c3:
        event_name = st.text_input("Evento", key="v281_event_name")

    try:
        projects = fetch_projects(client)
    except Exception as exc:
        projects = []
        st.warning(f"A lista de projetos existentes não pôde ser consultada agora: {exc}")

    candidates = rank_project_candidates(
        projects,
        project_name=project_name,
        client_brand=client_brand,
        event_name=event_name,
        limit=5,
    )

    if candidates:
        st.markdown("#### Projetos existentes parecidos")
        candidate_rows = []
        for candidate in candidates:
            candidate_rows.append({
                "Projeto": candidate.project_name,
                "Cliente": candidate.client_brand or "",
                "Evento": candidate.event_name or "",
                "Confiança": candidate.confidence.capitalize(),
                "Aderência": f"{round(candidate.score * 100)}%",
                "Leitura": "; ".join(candidate.reasons) or "sem sinal adicional",
                "Conflitos": "; ".join(candidate.conflicts) or "—",
            })
        st.dataframe(pd.DataFrame(candidate_rows), hide_index=True, width="stretch")
        top = candidates[0]
        if top.confidence == "alta" and not top.conflicts:
            st.info(
                f"Correspondência forte encontrada: **{top.project_name}**. A NAVE não associa automaticamente: confirme o destino abaixo."
            )

    st.markdown("### 4. Destino")
    strong_match = bool(
        candidates
        and candidates[0].confidence == "alta"
        and not candidates[0].conflicts
    )
    destination = st.radio(
        "Este conjunto pertence a:",
        ["Um novo projeto", "Um projeto que já existe"],
        horizontal=True,
        index=1 if strong_match else 0,
        key="v281_destination",
    )

    force_new_confirmed = True
    if destination == "Um novo projeto" and strong_match:
        force_new_confirmed = st.checkbox(
            f"Confirmo criar um novo projeto mesmo com forte correspondência a **{candidates[0].project_name}**.",
            value=False,
            help="Esta confirmação existe para evitar duplicatas como projetos com o mesmo cliente, nome e edição.",
        )
        if not force_new_confirmed:
            st.caption(
                "A NAVE recomenda associar o lote ao projeto existente. O novo cadastro só será liberado após a confirmação acima."
            )

    existing_project_id = None
    selected_existing = None
    if destination == "Um projeto que já existe":
        if not projects:
            st.warning("Nenhum projeto existente está disponível para seleção.")
        else:
            project_options = []
            option_to_id = {}
            for row in projects:
                label = str(row.get("project_name") or "Projeto sem nome")
                project_client_label = str(row.get("client_brand") or "").strip()
                event = str(row.get("event_name") or "").strip()
                suffix = " · ".join(item for item in (project_client_label, event) if item)
                display = f"{label} — {suffix}" if suffix else label
                # Evita colisão visual sem mostrar UUID ao usuário.
                if display in option_to_id:
                    display = f"{display} · registro {len(project_options) + 1}"
                project_options.append(display)
                option_to_id[display] = str(row.get("id"))
            default_index = 0
            if candidates:
                candidate_id = candidates[0].project_id
                for index, option in enumerate(project_options):
                    if option_to_id[option] == candidate_id:
                        default_index = index
                        break
            selected_existing = st.selectbox(
                "Projeto existente",
                project_options,
                index=default_index,
            )
            existing_project_id = option_to_id.get(selected_existing)

    selected_rows = edited[edited["Incluir"] == True]  # noqa: E712
    include_sha256 = set(selected_rows["_sha256"].astype(str).tolist())
    role_overrides = {
        str(row["_sha256"]): LABEL_TO_ROLE.get(
            str(row["Papel do documento"]),
            "complementary_document",
        )
        for _, row in selected_rows.iterrows()
    }

    if include_sha256:
        destination_preview: dict[str, int] = {}
        for sha, role in role_overrides.items():
            for section in TARGET_SECTIONS.get(role, ("Documentos",)):
                destination_preview[section] = destination_preview.get(section, 0) + 1
        with st.expander("Ver distribuição prevista no workspace"):
            preview = pd.DataFrame([
                {"Área": section, "Arquivo(s) relacionado(s)": count}
                for section, count in destination_preview.items()
            ])
            st.dataframe(preview, hide_index=True, width="stretch")

    can_save = (
        bool(include_sha256)
        and bool(project_name.strip() or existing_project_id)
        and bool(force_new_confirmed)
    )
    if st.button(
        "Importar projeto completo",
        type="primary",
        width="stretch",
        disabled=not can_save,
    ):
        match_context = {}
        if candidates:
            top = candidates[0]
            match_context = {
                "top_candidate_project_id": top.project_id,
                "top_candidate_score": top.score,
                "top_candidate_confidence": top.confidence,
                "top_candidate_reasons": top.reasons,
                "top_candidate_conflicts": top.conflicts,
                "user_destination": destination,
            }
        with st.spinner("Preservando arquivos no Cloudflare R2 e criando o lote do projeto..."):
            try:
                result = save_project_bundle(
                    client,
                    documents=documents,
                    role_overrides=role_overrides,
                    include_sha256=include_sha256,
                    project_name=project_name,
                    client_brand=client_brand,
                    event_name=event_name,
                    existing_project_id=existing_project_id,
                    match_context=match_context,
                )
            except ProjectBatchError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"A importação não pôde ser concluída. Detalhe técnico: {exc}")
            else:
                st.session_state["v281_last_result"] = result
                workspace_ok = int(result.get("workspace_materialized") or 0)
                workspace_errors = int(result.get("workspace_errors") or 0)
                st.success(
                    f"Projeto importado: {result['documents_saved']} arquivo(s) preservado(s) e {workspace_ok} incorporado(s) ao workspace."
                )
                if result.get("duplicates_reused"):
                    st.info(
                        f"{result['duplicates_reused']} arquivo(s) já existiam no projeto e foram reaproveitados sem duplicar o arquivo físico."
                    )
                if workspace_errors:
                    st.warning(
                        f"{workspace_errors} arquivo(s) tiveram alguma etapa de incorporação incompleta. O original continua preservado para nova tentativa, sem perda do lote."
                    )
                cols = st.columns(4)
                cols[0].metric("Arquivos", result["documents_saved"])
                cols[1].metric("No workspace", workspace_ok)
                cols[2].metric("Reaproveitados", result.get("duplicates_reused", 0))
                cols[3].metric("Projeto", "Novo" if result.get("created_project") else "Existente")
                st.caption(
                    "Os masters ficam preservados no Cloudflare R2; briefing, custos, apresentações, feedbacks e relatórios alimentam as estruturas que a Visão geral e as abas do projeto realmente consultam."
                )
                materialization_rows = []
                role_labels_by_key = ROLE_LABELS
                source_name_by_sha = {document.sha256: document.name for document in documents}
                source_id_to_name = {}
                # O resultado técnico vem por source_file_id; o nome é recuperado
                # do lote quando disponível e, caso contrário, o papel ainda deixa
                # claro qual pipeline falhou.
                for item in result.get("materialization_results") or []:
                    created = item.get("created") or {}
                    materialization_rows.append({
                        "Papel": role_labels_by_key.get(str(item.get("role") or ""), str(item.get("role") or "Documento")),
                        "Status": "OK" if str(item.get("status") or "") != "error" else "Erro",
                        "Estruturas criadas": ", ".join(f"{key}: {value}" for key, value in created.items() if int(value or 0) > 0) or "arquivo preservado",
                        "Observações": " | ".join(str(w) for w in (item.get("warnings") or [])[:4]) or "—",
                    })
                if materialization_rows:
                    with st.expander("Ver diagnóstico da incorporação ao workspace", expanded=bool(workspace_errors)):
                        st.dataframe(pd.DataFrame(materialization_rows), hide_index=True, width="stretch")
                        st.caption(
                            "Um arquivo pode estar preservado e ainda assim ter falha na leitura estruturada. Este quadro separa as duas situações."
                        )
                _render_domain_normalization(result, expanded=False)

                cross = result.get("cross_source_intelligence") or {}
                if cross and str(cross.get("status") or "").startswith("completed"):
                    with st.expander("Intelligence Graph · conexões entre arquivos", expanded=False):
                        c0, c1, c2, c3, c4, c5 = st.columns(6)
                        canonical = result.get("canonical_entity_graph") or {}
                        c0.metric("Entidades canônicas", int(canonical.get("memory_items_considered") or 0))
                        c1.metric("Entidades multi-fonte", int(cross.get("multi_source_entities_total") or 0))
                        c2.metric("Ocorrências ligadas", int(cross.get("unified_occurrences_total") or cross.get("entities_merged") or 0))
                        c3.metric("Solução ↔ custo", int(cross.get("cost_links_total") or cross.get("cost_links") or 0))
                        c4.metric("Execuções ligadas", int(cross.get("execution_claims_total") or cross.get("execution_claims") or 0))
                        c5.metric("Relações hierárquicas", int(cross.get("hierarchy_links_total") or cross.get("hierarchy_links") or 0))
                        reviews = int(cross.get("resolution_reviews") or 0) + int(cross.get("cost_link_reviews") or 0)
                        st.caption(f"Revisões ambíguas pendentes: {reviews}. A NAVE não força vínculos sem evidência suficiente.")
                        debug_rows = cross.get("resolution_debug") or []
                        if debug_rows:
                            with st.expander("Diagnóstico do Entity Resolution · por entidade", expanded=False):
                                st.dataframe(pd.DataFrame(debug_rows), hide_index=True, width="stretch")
                st.page_link(
                    "pages/4_Historico_de_Projetos.py",
                    label="Abrir Projetos",
                )

else:
    st.markdown("### Como esta etapa funciona")
    st.markdown(
        """
        1. envie todos os documentos que já pertencem ao mesmo job;
        2. a NAVE sugere o papel de cada arquivo;
        3. você revisa a classificação;
        4. a plataforma compara o conjunto com projetos existentes;
        5. você confirma **novo projeto** ou **projeto existente**;
        6. os arquivos são preservados no acervo privado do projeto com papel, confiança e origem;
        7. briefing, custos, apresentações, feedbacks e relatórios são incorporados às estruturas reais do workspace.
        """
    )
    st.info(
        "O Upload de Conhecimento continua existindo para alimentar o repertório transversal. Esta tela é específica para documentos que, juntos, formam um projeto."
    )
