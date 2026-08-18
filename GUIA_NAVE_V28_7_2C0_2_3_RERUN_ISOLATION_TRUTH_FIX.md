# NAVE by VOE · V28.7.2C0.2.3 — Rerun Isolation & Truth Identity Fix

## Diagnóstico provado pelo Golden Chambinho

A C0.2.2 corrigiu o falso positivo do template prompt, mas a segunda execução revelou um bug de idempotência/isolamento de identidade.

O CSV mostrou:

- Legacy rows: 14
- Legacy recall: 16
- Evidence-first: 2
- Observações: 18
- Current identities: 12
- Verified: 12
- Legacy unverified: 3
- Occurrences com Evidence: 13

A inconsistência decisiva é: `Legacy recall = 16` com apenas `14` legacy rows.

As duas Requirement identities evidence-led criadas em runs anteriores estavam entrando novamente pela rota `legacy_recall` porque o extractor iterava todas as `project_requirements`, e não apenas rows com `legacy_source_id`.

Além disso, a view `project_requirement_truth_status` fazia o lookup de legacy explanation com fallback para string vazia. Para uma identity evidence-led (`legacy_source_id = null`), isso permitia que uma observation legacy-recall com `legacy_requirement_id = null` de OUTRA identity contaminasse seu truth state.

Foi exatamente o que ocorreu:

- o antigo prompt de formulário já estava corretamente histórico/no-domain;
- a Requirement válida `Precisamos organizar para pagarem a cenografia...` tinha occurrence atual;
- mesmo assim ela recebeu `legacy_explanation_role = form_prompt` e caiu para `legacy_unverified`.

## Correção C0.2.3

### 1. Legacy recall estritamente legado

A Route 1 agora processa somente `project_requirements` com `legacy_source_id` real.

Requirements evidence-led de runs anteriores:

- não voltam por legacy recall;
- são redescobertas exclusivamente pela Route 2 Evidence-first;
- desaparecem/supersedem se a Evidence canônica deixar de sustentá-las.

### 2. Truth lookup isolado por identidade

Uma `legacy_recall` observation só pode explicar uma Requirement quando:

- a Requirement possui `legacy_source_id`;
- `semantic_observations.attributes.legacy_requirement_id` é exatamente esse mesmo `legacy_source_id`.

Não existe mais fallback por `''` nem por `domain id` para evidence-led identities.

### 3. Métrica evidence-led passa a significar CURRENT

`evidence_led_requirement_identities` agora conta apenas evidence-led identities cujo truth state atual é:

- `verified`;
- `human_confirmed`; ou
- `review_required`.

A identity histórica do template prompt deixa de inflar essa métrica.

## Resultado esperado no próximo Chambinho

No painel Requirement Semantic Reconciliation:

- Legacy rows: **14**
- Current identities: **13**
- Verified: **13**
- Legacy unverified: **2**
- Occurrences com Evidence: **13**
- Review required: **0**
- Conflicted: **0**
- Observações: **16**
- Legacy recall: **14**
- Evidence-first: **2**
- Reconciliadas: **14**
- No-domain: **2**
- Open: **0**
- Context: **2**
- Constraints: **2**
- Shadow explicado: **2**
- Shadow sem explicação: **0**

`Novos evidence-led` no painel deve aparecer como **0 nesta run**, porque essa métrica é quantidade de identities CRIADAS nesta execução. A Requirement financeira evidence-led já existe e deve ser reutilizada, não recriada.

No Verify, `evidence_led_requirement_identities` deve ser **1**, pois essa métrica representa evidence-led CURRENT, e a única atual deve ser:

`Precisamos organizar para pagarem a cenografia de forma direta antes do evento acontecer para evitar bitributação.`

## Importante sobre o painel Domain Truth Gate

O card geral `Requisitos` pode continuar mostrando **15**, porque ele preserva rows do domínio legado/shadow, incluindo `Objetivo principal` e `Público-alvo` como registros históricos/contextuais.

O número autoritativo para Requirements atuais nesta etapa é `Current identities` no painel C0.2.3.

## SQL

SIM.

Executar uma única vez:

`NAVE_V28_7_2C0_2_3_RERUN_ISOLATION_TRUTH_FIX.sql`

Não executar novamente C0, C0.1, C0.2, C0.2.1 ou C0.2.2.

## GitHub

Substituir exatamente:

- `project_requirement_semantic_extractor.py`
- `project_requirement_reconciliation.py`
- `pages/14_Importar_Projeto.py`
- `tests/test_v28_7_2c0_2_evidence_first.py`

## Reboot

SIM, depois do commit GitHub.

## Reteste

1. Não reprocessar masters.
2. Abrir `Festivalzinho Chambinho`.
3. Executar uma vez `Reconciliar Requirements + Core Semantics · V28.7.2C0.2.3`.
4. Rodar `NAVE_V28_7_2C0_2_3_VERIFY_GOLDEN_CHAMBINHO.sql`.
5. Exportar CSV e enviar junto com prints completos.
6. Ainda não rodar JOVI.

## Gates adicionais

O Verify C0.2.3 também exige:

- nenhuma observation `legacy_recall` current com `legacy_requirement_id` nulo;
- a Requirement financeira evidence-led explicitamente `verified`;
- 14 legacy recall observations para 14 legacy rows;
- template prompt fora de current truth;
- 13 current Requirements;
- 13 verified;
- 1 evidence-led current;
- Solutions/Execution/Finance preservados;
- Graph V28.6 não rerodado.

## Estado

- `migration_mode = legacy_shadow`
- `domain_primary = NÃO`
- Graph V28.6 = congelado
- C1 Decision/Feedback = bloqueada
