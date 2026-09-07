# NAVE V28.7.3B2.12.4.1 — Transaction Integrity Hardening

## Por que existe

O JOVI B2.12.4 acertou o núcleo:
- 70 Current -> 69 projected;
- 1 collision -> 0 projected;
- 1 ready plan;
- B2.1 pós-simulação PASS;
- occurrence duplicate corretamente identificada;
- Legacy alias projetado para o survivor.

Mas o dry-run revelou dois gaps antes de um write real:

1. nove Domain Evidence links históricos da identity antiga foram projetados um-a-um para o survivor,
   embora oito sejam `occurrence` para o mesmo Evidence Unit;
2. o dry-run anterior projetava Governance / Knowledge Entity changes sem validar as linhas reais
   que receberiam a transação.

## Hardening

B2.12.4.1 continua 100% read-only.

Agora:
- exige exatamente uma Governance row e uma Knowledge Entity row para survivor e superseded identities;
- valida domain_table/domain_id quando presentes;
- bloqueia survivor já superseded/canonicalizado em outra identity;
- bloqueia superseded identity já apontando para outro canonical entity;
- preserva review_status;
- coalesce historical Domain Evidence por `(evidence_unit_id, link_role)`;
- se survivor já possui Evidence+role equivalente, reutiliza esse link em vez de inserir outro;
- caso contrário, projeta exatamente um novo link determinístico;
- mantém todos os links históricos antigos intactos;
- expõe `raw_historical_evidence_link_count` vs `coalesced_evidence_action_count`;
- mantém B2.1 compatibility simulation;
- não toca em metadata conflitante.

## Arquivos

SUBSTITUIR:
- `project_requirement_identity_supersession_dry_run.py`
- `pages/35_Requirement_Identity_Supersession_Dry_Run.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

ADICIONAR:
- `tests/test_v28_7_3b2_12_4_1_transaction_integrity.py`
- `GUIA_NAVE_V28_7_3B2_12_4_1_TRANSACTION_INTEGRITY.md`

## SQL
NÃO.

## Reboot
SIM.

## Golden
Chambinho primeiro:
- 13 Current;
- 0 collision;
- 0 transaction plans;
- projected Current 13;
- no writes.

Depois JOVI:
- 70 -> 69;
- 1 -> 0 collision;
- 1 ready / 0 blocked;
- B2.1 PASS;
- Governance/Knowledge Entity integrity sem blockers;
- historical evidence raw count pode continuar 9;
- coalesced evidence actions deve ser muito menor (esperado 1–2, ou reuse existing);
- nenhum write.

B2.12.5 continua bloqueado até este hardening fechar Golden.
