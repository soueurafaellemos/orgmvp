# NAVE V28.7.3B2.12.4 — Transactional Requirement Identity Supersession · DRY RUN

## Objetivo
Simular, sem writes, a transação necessária para resolver uma canonical Requirement identity collision.

## O dry-run prova
- superseded Requirement pode virar histórica usando o lifecycle já existente;
- occurrence rebind exige recomputar `occurrence_hash`;
- colisão de target hash vira supersession da occurrence antiga, não overwrite inseguro;
- Legacy alias continua resolvendo via occurrence ativa ou `survivor.legacy_source_id`;
- B2.1 compatibility continua PASS no estado projetado;
- old domain evidence é preservada e uma cópia para o survivor é apenas projetada;
- semantic observations históricas permanecem imutáveis;
- `mandatory`, `requirement_type` e `priority` conflitantes não são mesclados silenciosamente.

## Arquivos
ADICIONAR:
- `project_requirement_identity_supersession_dry_run.py`
- `pages/35_Requirement_Identity_Supersession_Dry_Run.py`
- `tests/test_v28_7_3b2_12_4_supersession_dry_run.py`
- `GUIA_NAVE_V28_7_3B2_12_4_SUPERSESSION_DRY_RUN.md`

SUBSTITUIR:
- `streamlit_app.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

## SQL
NÃO.

## Reboot
SIM.

## Golden
1. Rodar Chambinho primeiro.
2. Esperado: 13 Current, 0 collisions, 0 plans, projected Current 13.
3. Enviar JSON.
4. Após aprovação, rodar JOVI.
5. Esperado: 70 Current, 1 collision, 1 ready plan, projected Current 69, projected collision 0, B2.1 compatibility PASS.
6. Só depois desenhar B2.12.5 com write real transacional.
