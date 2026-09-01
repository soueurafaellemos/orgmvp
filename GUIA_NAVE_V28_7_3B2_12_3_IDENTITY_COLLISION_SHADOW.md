# NAVE V28.7.3B2.12.3 — Canonical Requirement Identity Collision Resolution Shadow

## Contexto

H3.1.3 e B2.12.2.2 fecharam Golden em Chambinho e JOVI.

O único blocker antes de qualquer B2.13 / Truth-effect é uma collision Current no JOVI:
a mesma obrigação canônica de co-investimento + KOLs existe em duas Requirement identities.

O reconciliador atual deliberadamente NÃO auto-mergeia duas identities existentes.
Essa regra permanece correta.

## Objetivo

B2.12.3 é SOMENTE um plano read-only.

Ele:
- lê Requirement Truth Current;
- reutiliza a canonical obligation source-bounded do B2.12.2.x;
- agrupa apenas canonical obligations exatamente iguais após normalização;
- audita provenance de cada identity;
- conta occurrences e aliases legacy;
- calcula um ranking de survivor;
- informa metadados divergentes;
- propõe survivor/superseded IDs apenas quando a margem de provenance é suficientemente forte;
- NÃO escreve nada.

## Precedência de survivor no shadow

1. `human_confirmed`;
2. identity evidence-led;
3. canonical derivada de `semantic_observation.source_atom`;
4. título completo em vez de truncado;
5. canonical confidence;
6. occurrences ativas.

Metadata divergente é registrada, mas NÃO é usada para inventar uma nova obrigação.
A identity resolution é baseada em canonical obligation + provenance.

Empate de provenance ou múltiplas human-confirmed => review required.

## Arquivos

ADICIONAR:
- `project_requirement_identity_collision_shadow.py`
- `pages/34_Requirement_Identity_Collision_Shadow.py`
- `tests/test_v28_7_3b2_12_3_identity_collision_shadow.py`
- `GUIA_NAVE_V28_7_3B2_12_3_IDENTITY_COLLISION_SHADOW.md`

SUBSTITUIR:
- `streamlit_app.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

## SQL

NÃO.

## Reboot

SIM.

## Ordem de Golden

1. Deploy.
2. Reboot.
3. Abrir `Requirement Identity Collision Shadow`.
4. Confirmar `V28.7.3B2.12.3`.
5. Rodar Festivalzinho Chambinho primeiro.
6. Esperado: 0 collisions; nenhum write.
7. Enviar JSON.
8. Após aprovação, rodar JOVI.
9. Esperado: exatamente 1 collision e um plano de survivor/supersession; nenhum merge/write.
10. Só após Golden do plano desenhar a transação B2.12.4.

## Governança

Continua proibido:
- auto-merge;
- update/delete/supersession neste estágio;
- rebind de occurrences;
- rebind de evidence links;
- Human Review sintético;
- Truth effect;
- domain_primary;
- mudança de read_mode/canary;
- B2.13.

`ready_for_transactional_resolution` é autorização apenas para DESENHAR a fase
transacional seguinte, não para executar a resolução.
