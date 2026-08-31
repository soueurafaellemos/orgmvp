# NAVE by VOE · V28.7.2C0.2.4H3.1.1
## Section Boundary Guard — stale cross-unit inheritance repair

## Diagnóstico do Golden Chambinho H3.1

A execução H3.1 concluiu tecnicamente, com `semantic_gate_pass=true`, mas NÃO foi
aprovada semanticamente.

O JSON mostrou:

- 16 observations;
- 2 no-domain;
- 1 cross-unit override;
- 0 review required;
- 0 gate blockers;
- 0 new requirements.

`Público-alvo` foi corretamente classificado como `audience_context`.

Porém `Objetivo principal` recebeu `audience_context` por
`h31_structural_context=cross_unit_parent`.

Na fonte, a ordem estrutural é:

- `PUBLICO ALVO:`
- descritores do público;
- `OBJETIVO E DESAFIO`
- `Objetivo principal: ...`

Portanto o parent de público NÃO pode atravessar `OBJETIVO E DESAFIO`.

## Causa

H3.1 interrompia herança stale somente em headings compactos terminados por `:`.

Briefings DOCX/PDF frequentemente materializam headings sem pontuação terminal.
`OBJETIVO E DESAFIO` não terminava em `:`, então o lookback continuava até
`PUBLICO ALVO:` e aplicava o papel errado.

## Correção H3.1.1

`project_requirement_semantic_h31.py` passa a reconhecer um boundary estrutural mesmo
sem `:` quando a linha:

- é heading pelo detector H3 já existente; ou
- corresponde a uma seção genérica de briefing/documento, como objetivo/desafio,
  resultado esperado, entregáveis, obrigatoriedades, financeiro/budget, apresentação,
  logística, público-alvo, adequação à plataforma ou foco do produto.

A regra NÃO usa all-caps como critério isolado, porque bullets legítimos de decks podem
estar em caixa alta.

A ordem permanece fail-closed:

1. semantic parent conhecido pode retornar seu papel;
2. explicit requirement parent pode retornar `requirement_parent`;
3. só então um novo section boundary interrompe a busca por parents mais antigos.

Assim H3.1.1 preserva o ganho de recall do lookback amplo sem permitir herança através
de uma nova seção.

## Golden esperado — Chambinho

Depois de rodar H3.1.1 uma vez:

- `semantic_gate_pass = true`;
- `semantic_gate_blockers = 0`;
- `review_required = 0`;
- `Público-alvo` = `audience_context`;
- `Objetivo principal` = `strategy_context` (papel base H3), NÃO `audience_context`;
- `Objetivo principal` não deve ter `h31_structural_context=cross_unit_parent`;
- `new_requirements = 0`;
- nenhuma alteração em A/B/Graph/canaries/read_mode.

O total de no-domain pode continuar 2; o ponto do hotfix é a SEMÂNTICA correta do papel,
não maquiar contagens.

## Deploy

### Substituir
- `project_requirement_semantic_h31.py`
- `project_requirement_reconciliation_h31.py`
- `pages/33_Requirement_Semantic_Truth_Repair.py`
- `tests/test_v28_7_2c0_2_4h3_1_cross_unit_context.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

### Adicionar
- `NAVE_V28_7_2C0_2_4H3_1_1_VERIFY_GOLDEN_JOVI.sql`
- `GUIA_NAVE_V28_7_2C0_2_4H3_1_1_SECTION_BOUNDARY_GUARD.md`

## SQL

Migration SQL: NÃO.

O verifier JOVI H3.1.1 é READ-ONLY e só será executado depois que o Golden Chambinho
for aprovado e o JOVI for explicitamente liberado.

## Depois do deploy

1. Commit/push.
2. Streamlit → Manage app → Reboot app.
3. Abrir `Requirement Semantic Truth Repair`.
4. Confirmar versão `V28.7.2C0.2.4H3.1.1`.
5. Rodar SOMENTE Festivalzinho Chambinho.
6. Baixar `NAVE_H3_1_1_REQUIREMENT_TRUTH_REPAIR_<project_id>.json`.
7. Enviar o JSON para Golden Verify.
8. Não rodar JOVI antes da aprovação.
