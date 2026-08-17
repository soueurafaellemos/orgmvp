# NAVE by VOE · V28.7.2C0 — Requirement Semantic Reconciliation

## Objetivo

A C0 corrige a semântica de Requirements antes de abrir Decision / Feedback.

O contrato passa a ser:

`Requirement Identity ≠ Requirement Occurrence ≠ Constraint`

A camada existente `project_requirements` continua sendo a identidade do Requirement. A C0 não cria um domínio paralelo e não apaga o legado.

## Por que esta fase existe

O Golden JOVI encerrou a V28.7.2B com 63 linhas legadas de Requirement, das quais 50 tinham Evidence e 13 permaneciam sem provenance exata.

Essas 13 linhas não podem ser tratadas automaticamente como "13 Requirements sem link". Algumas podem representar:

- Requirement real;
- ocorrência textual;
- scope/canal;
- atributo de produto;
- contexto/audiência;
- constraint;
- ambiguidade que exige revisão.

A C0 foi desenhada para explicar essa diferença sem keyword binding para fechar contador.

## O que entra

### 1. `project_requirement_occurrences`

Nova tabela evidence-backed para ocorrências de Requirement.

Uma ocorrência guarda:

- Requirement identity;
- Evidence Unit;
- Source Asset;
- Semantic Observation;
- phase;
- role;
- texto observado;
- confidence;
- lifecycle.

Roles iniciais:

- requirement;
- scope;
- attribute;
- constraint;
- context;
- reference.

### 2. Requirement Semantic Observations

A C0 reutiliza `semantic_observations` e adiciona ações próprias de Requirement:

- `create_requirement`;
- `attach_requirement_occurrence`;
- `attach_scope`;
- `attach_attribute`;
- `attach_constraint`;
- `review_required`;
- `no_domain_object`;
- `insufficient_evidence`.

Toda observation C0 nasce de uma **Evidence Unit atual**.

Quando o Requirement legado ainda possui lineage para o briefing original, a recuperação de Evidence é **source-local**. A NAVE não usa uma ocorrência em outro PDF/relatório apenas porque a mesma palavra aparece no projeto.

### 3. Requirement Identity Resolution

Ordem de autoridade:

1. Requirement ID explícito;
2. lineage do Requirement legado;
3. identidade textual/semântica inequívoca;
4. review quando houver mais de uma identidade plausível;
5. nova identity evidence-led somente com Evidence explícita, confiança alta e fonte com autoridade suficiente.

**Duas Requirement identities existentes nunca são auto-merged.**

Uma semelhança moderada bloqueia criação silenciosa e abre review; só um match materialmente mais forte pode anexar automaticamente.

### 4. Requirement Truth Gate

Nova view:

`project_requirement_truth_status`

Estados:

- verified;
- human_confirmed;
- legacy_unverified;
- review_required;
- conflicted;
- historical.

Uma linha legacy preservada não vira verdade por existir em `project_requirements`.

Para `verified`, precisa existir Evidence atual diretamente ligada ao Requirement ou através de uma occurrence C0 ativa. Human confirmation continua separada.

### 5. Requirement Reconciliation Status

Nova view:

`project_requirement_reconciliation_status`

Mostra:

- Requirement identities;
- verified;
- legacy unverified;
- human confirmed;
- review required;
- conflicts;
- occurrences com Evidence;
- constraints;
- observations open/reconciled/no-domain;
- scope/attribute/context classificados;
- legacy shadow explicado;
- legacy shadow ainda sem explicação.

O objetivo não é forçar `63/63`. O objetivo é não confundir Requirement com fragmento semântico.

## O que NÃO muda

A C0 não altera:

- Solution reconciliation V28.7.2A;
- Strategy / Creative / Experience V28.7.2B;
- `project_requirement_constraints` já existente;
- financial lines;
- Outcome Truth Gate;
- Graph V28.6;
- Recommendation Engine;
- Analyst;
- migration mode.

Não existe cutover nesta versão.

## Pipeline

A ordem passa a ser:

1. V28.7.1D Truth Gate;
2. V28.7.2A Solution Reconciliation;
3. Coverage / Identity Audits;
4. **V28.7.2C0 Requirement Semantic Reconciliation**;
5. V28.7.2B Strategy / Creative / Experience.

Se C0 falhar, a A e os audits anteriores permanecem válidos, mas a B não roda naquela geração.

## Arquivos GitHub

### Adicionar

- `project_requirement_identity.py`
- `project_requirement_semantic_extractor.py`
- `project_requirement_reconciliation.py`
- `tests/test_v28_7_2c0_requirement_identity.py`
- `tests/test_v28_7_2c0_requirement_extractor.py`
- `tests/test_v28_7_2c0_reconciliation_plan.py`
- `tests/test_v28_7_2c0_sql_contract.py`
- `tests/test_v28_7_2c0_orchestration.py`
- `tests/test_v28_7_2c0_no_golden_hardcode.py`

### Substituir

- `project_intelligence_pipeline.py`
- `pages/14_Importar_Projeto.py`
- `tests/test_v28_7_2a_orchestration.py`
- `tests/test_v28_7_1b_orchestration_gate.py`
- `tests/test_v28_7_1d_orchestration_freeze.py`

## SQL

**SIM, precisa executar SQL.**

Executar uma única vez:

`NAVE_V28_7_2C0_REQUIREMENT_SEMANTIC_RECONCILIATION.sql`

A migration é aditiva/não destrutiva e recarrega o schema do PostgREST ao final.

## Ordem de deploy

1. executar `NAVE_V28_7_2C0_REQUIREMENT_SEMANTIC_RECONCILIATION.sql` no Supabase;
2. subir os arquivos do patch no GitHub, respeitando as pastas;
3. fazer reboot do Streamlit;
4. abrir **Festivalzinho Chambinho**;
5. clicar uma vez em `Reconciliar Requirements + Core Semantics · V28.7.2C0`;
6. executar `NAVE_V28_7_2C0_VERIFY_GOLDEN_CHAMBINHO.sql`;
7. exportar o resultado em CSV e enviar print + CSV para análise;
8. somente depois da aprovação do Chambinho, repetir no JOVI com `NAVE_V28_7_2C0_VERIFY_GOLDEN_JOVI.sql`;
9. depois dos dois Goldens, executar uma segunda run de idempotência antes de aprovar C0.

**Não reprocessar os masters.** A ação correta é a reconciliação sem nova leitura dos arquivos originais.

## Golden Chambinho — intenção do gate

A C0 deve ser regressiva/conservadora no Chambinho:

- 14 Requirement identities preservadas;
- 14 verificadas/human-confirmed;
- nenhum legacy_unverified novo;
- nenhum Requirement evidence-led artificial;
- constraints preservadas;
- 19 Solutions preservadas;
- 8 execution truths preservadas;
- 54/54 financial lines com Evidence preservadas;
- Graph V28.6 não rerodado.

## Golden JOVI — intenção do gate

O teste não exige que a cardinalidade final seja `63` porque `63` é uma cardinalidade legada, não uma verdade semântica.

O Verify exige principalmente:

- os 13 gaps originais continuam localizáveis;
- cada um está verificado, em review ou semanticamente explicado por Evidence;
- nenhum legacy shadow fica sem explicação;
- scope / atributo / contexto podem permanecer sem virar Requirement;
- qualquer novo Requirement C0 precisa de Evidence atual;
- nenhum existing-existing auto-merge;
- A continua com 27 Solutions / 47 Solution Occurrences;
- B continua com Strategy 7 / Creative Platform 1 / Creative Element 1 / Experience Architecture 1 / Journey 5;
- Graph V28.6 continua congelado.

## Idempotência

Na segunda run:

- Requirement IDs devem permanecer;
- occurrence hashes devem permanecer;
- Evidence bindings não devem duplicar;
- classifications não devem oscilar;
- Requirements ativos não devem crescer sem nova Evidence;
- a mesma observation pode ser reaplicada, mas o estado substantivo não pode inflar.

## Validação local

- `py_compile`: PASS
- suíte focada C0 + regressões A/B/Truth Gate: **38 passed, 1 skipped**
- runtime C0 sem nomes de Golden/client hardcoded
- sem Graph rebuild
- sem cutover
- sem DELETE destrutivo de Requirement

## Estado após deploy

- migration_mode: `legacy_shadow`
- Graph V28.6: congelado
- domain_primary: NÃO
- cutover: NÃO
- C1 Decision / Feedback: BLOQUEADA até C0 passar nos dois Goldens + idempotência
