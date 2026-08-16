# NAVE by VOE · V28.7.2A1 — Occurrence Parity Hotfix

## Objetivo

Corrigir o bloqueio de idempotência revelado pela segunda execução da V28.7.2A.

A primeira reconciliação é válida e criou ocorrências evidence-led adicionais. O gate legado da Domain Normalization ainda comparava **total de ocorrências** com **total de `memory_items`**, o que era correto antes da reconciliação semântica, mas se tornou inválido depois que a V28.7.2A passou a representar múltiplas ocorrências por identidade.

No Golden Chambinho:

- `memory_items`: 16
- ocorrências após a primeira V28.7.2A: 36
- 16 continuam sendo ocorrências de compatibilidade ligadas aos `memory_items`
- 20 são ocorrências semânticas/evidence-led adicionais

Por isso a segunda execução produziu `occurrence_parity = false`, embora o domínio estivesse correto.

## Correção

O gate deixa de exigir:

`total de project_solution_occurrences == total de memory_items`

E passa a exigir o invariante semanticamente correto:

1. todo `memory_item` atual com ID deve continuar representado por **exatamente uma** ocorrência cujo `legacy_memory_item_id` corresponda ao seu ID;
2. nenhuma referência legada pode estar duplicada;
3. ocorrências semânticas adicionais são permitidas e não reduzem a paridade.

Isso é mais permissivo quanto ao crescimento legítimo do domínio, mas **mais rígido** quanto à preservação do legado: uma occurrence legada ausente ou duplicada continua bloqueando a geração.

## Arquivos

### Substituir

- `project_domain_normalization.py`

### Adicionar

- `tests/test_v28_7_2a1_occurrence_parity.py`

## SQL

**NÃO.**

Nenhuma tabela, view, RPC ou dado precisa ser alterado.

## Reboot

**SIM.**

Depois de subir os arquivos, reinicie o Streamlit.

## Reprocessamento de masters

**NÃO.**

Não reprocessar PDF, PPTX, DOCX ou planilha.

## Reteste

Depois do reboot:

1. abra o Golden `Festivalzinho Chambinho · Lactalis`;
2. clique **uma vez** em `Reconciliar domínio semântico · V28.7.2A`;
3. a Domain Normalization deve passar mesmo com mais de 16 occurrences;
4. rode `NAVE_V28_7_2A_VERIFY_GOLDEN_CHAMBINHO_CANONICAL.sql`;
5. exporte o CSV e envie para a auditoria final de idempotência.

### Cardinalidades que devem permanecer estáveis

- Solutions: 19
- Semantic observations: 22
- Solution occurrences: 36
- Verified execution truths: 8
- Evidence-led created identities: 4
- Requirement constraints: 2
- Context elements: 2
- Coverage gaps: 0
- Identity conflicts: 1
- Financial lines: 54

Uma nova `project_domain_reconciliation` run é esperada. Duplicação de objetos substantivos não é.

## Segurança

- Truth Gate V28.7.1D não é alterado.
- Graph V28.6 continua congelado.
- `migration_mode` permanece `legacy_shadow`.
- O pre-apply bundle da Domain Normalization continua exigindo uma occurrence de compatibilidade por `memory_item`.
- O hotfix altera somente o **post-apply parity gate**, para que ele valide cobertura por identidade legada em vez de cardinalidade total.

## Validação local

Suíte focada V28.7.2A + regressões de orquestração + novo gate de paridade:

**37 passed**.

O novo teste comprova:

- crescimento semântico não quebra paridade;
- `memory_item` ausente continua falhando;
- referência legada duplicada continua falhando.
