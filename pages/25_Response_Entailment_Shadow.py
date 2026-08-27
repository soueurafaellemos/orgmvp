from __future__ import annotations

import pandas as pd
import streamlit as st

from branding import NAVE_APP_ICON, apply_nave_branding, page_header
from nave_data_client import enforce_existing_app_access, get_nave_client
from project_domain_consumer_canary import fetch_active_canary
from project_domain_reader import get_cutover_state
from project_requirement_response_entailment_shadow import (
    RESPONSE_ENTAILMENT_VERSION,
    run_response_entailment_shadow,
)

st.set_page_config(
    page_title='Response Entailment Shadow | NAVE by VOE',
    page_icon=NAVE_APP_ICON,
    layout='wide',
)
enforce_existing_app_access()
apply_nave_branding()
page_header(
    'Response Entailment Shadow',
    'Audita se a evidência material realmente sustenta a semântica canônica da demanda — ownership e source role, sozinhos, não bastam.',
    eyebrow=f'NAVE by VOE · {RESPONSE_ENTAILMENT_VERSION} · shadow only',
)

client = get_nave_client()
canaries = (
    client.table('project_domain_consumer_canary')
    .select('*')
    .eq('domain_key', 'requirements')
    .eq('consumer_key', 'workspace.intelligence.matrix.requirements_readonly')
    .eq('status', 'active')
    .execute().data or []
)
project_ids = sorted({str(r.get('project_id') or '') for r in canaries if r.get('project_id')})
if not project_ids:
    st.warning('Nenhum matrix requirements canary ativo encontrado.')
    st.stop()

projects = []
for project_id in project_ids:
    rows = client.table('projects').select('*').eq('id', project_id).limit(1).execute().data or []
    row = dict(rows[0]) if rows else {'id': project_id}
    label = row.get('project_name') or row.get('event_name') or row.get('name') or project_id
    projects.append((f'{label} · {project_id}', project_id))

selected = st.selectbox('Projeto', [label for label, _ in projects])
project_id = dict(projects)[selected]

if st.button('Executar Response Entailment Shadow B2.6', type='primary'):
    try:
        state = get_cutover_state(client, project_id, 'requirements')
        if state.get('read_mode') != 'shadow_compare':
            st.error('B2.6 BLOCKED: requirements não está em shadow_compare.')
            st.stop()

        briefing = fetch_active_canary(
            client, project_id=project_id, domain_key='requirements',
            consumer_key='workspace.briefing.requirements_readonly',
        )
        matrix = fetch_active_canary(
            client, project_id=project_id, domain_key='requirements',
            consumer_key='workspace.intelligence.matrix.requirements_readonly',
        )
        if not briefing or not matrix:
            st.error('B2.6 BLOCKED: briefing/matrix requirements canaries devem permanecer ativos.')
            st.stop()

        with st.spinner('Auditando suporte semântico entre demanda e evidência...'):
            result = run_response_entailment_shadow(client, project_id=project_id)

        if result.status == 'PASS_PROJECTED_RESPONSE_ENTAILMENT':
            st.success('B2.6: PASS_PROJECTED_RESPONSE_ENTAILMENT')
        elif result.status == 'BLOCKED_RESPONSE_EVIDENCE_FALSE_POSITIVE_RISK':
            st.error(
                'B2.6: BLOCKED_RESPONSE_EVIDENCE_FALSE_POSITIVE_RISK · existe resposta '
                'atualmente atribuída a uma requirement governada sem suporte canônico suficiente.'
            )
        else:
            st.warning(
                'B2.6: PASS_WITH_RESPONSE_REVIEW · não há hard blocker, mas existem '
                'evidências/ownerships que exigem revisão antes de qualquer Unified canary.'
            )

        st.caption(
            'Shadow only. Este audit não é um novo matcher e não altera thresholds. '
            'Ele apenas procura falsos positivos semânticos nas respostas já retidas.'
        )

        st.dataframe(pd.DataFrame([{
            'version': RESPONSE_ENTAILMENT_VERSION,
            'status': result.status,
            'audited_responses': result.audited_response_count,
            'supported': result.supported_count,
            'response_reviews': result.review_count,
            'hard_blockers': result.hard_blocker_count,
            'ownership_reviews': result.ownership_review_count,
        }]), hide_index=True, width='stretch')

        detail = pd.DataFrame(list(result.detail_rows))
        if not detail.empty:
            st.markdown('#### Suporte canônico por resposta')
            st.dataframe(detail, hide_index=True, width='stretch', height=min(1000, 130 + len(detail)*42))
            st.download_button(
                'Baixar B2.6 em CSV',
                data=detail.to_csv(index=False).encode('utf-8-sig'),
                file_name=f'NAVE_B2_6_{project_id}.csv',
                mime='text/csv',
            )
    except Exception as exc:
        st.error(f'B2.6 BLOCKED: {type(exc).__name__}: {exc}')
