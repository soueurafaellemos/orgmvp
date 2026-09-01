# NAVE V28.7.2C0.2.4H3.1.3 — Structural Refinement Precedence

## Motivo
O Golden JOVI H3.1.2 corrigiu as duas regressões de H3.1.1: a diretiva criativa local voltou a Current Requirement Truth e o heading `Ativação Instagram: ...` voltou a `solution_reference`. Porém a precedência H3.1.2 ficou conservadora demais e preservou classificações contextuais erradas do H3 base.

Exemplos observados no JSON H3.1.2:
- `Kit de lentes teleobjetivas destacáveis` → `audience_context`, apesar de estar sob `Foco do Produto`;
- `Conteúdo de longa duração` / `Reviews técnicos aprofundados` → `audience_context`, apesar de estarem sob `Adequação à Plataforma`;
- `Curadoria visual impecável` / `Conteúdo aspiracional` → `audience_context`, apesar de estarem sob `Adequação à Plataforma`.

O problema não é Truth inclusion/exclusion apenas. Mesmo quando todos esses objetos ficam no-domain, a ontologia precisa registrar o papel semântico correto.

## Correção estrutural
H3.1.3 mantém:
- lookback cross-Evidence-Unit;
- Section Boundary Guard;
- Local Directive Guard;
- proteção de Human Confirmed;
- isolamento de A/B/Graph/canaries/cutover.

A mudança é a precedência:

1. **Semânticas intrínsecas/autossuficientes do H3 são preservadas**, como `solution_reference`, `reference_signal`, `suggestion_signal`, `example_signal`, `parameter_signal`, `constraint_qualifier` e `form_prompt`.
2. **Semânticas dependentes de contexto podem ser refinadas pelo parent estrutural mais próximo**, incluindo `audience_context`, `product_attribute`, `platform_scope`, `strategy_context` e `channel_scope`, além de `requirement_candidate` e `constraint_candidate`.
3. **Diretivas locais explícitas** (`Direcionamento criativo:`, `Creative Direction:` etc.) continuam protegidas e não podem ser demovidas pelo contexto anterior.

Assim, o wrapper não reescreve headings/referências intrínsecas, mas também não congela um erro contextual do H3 base.

## Arquivos a substituir
- `project_requirement_semantic_h31.py`
- `project_requirement_reconciliation_h31.py`
- `pages/33_Requirement_Semantic_Truth_Repair.py`
- `tests/test_v28_7_2c0_2_4h3_1_cross_unit_context.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

## Arquivos a adicionar
- `NAVE_V28_7_2C0_2_4H3_1_3_VERIFY_GOLDEN_JOVI.sql`
- `GUIA_NAVE_V28_7_2C0_2_4H3_1_3_STRUCTURAL_REFINEMENT_PRECEDENCE.md`

## SQL
Migration SQL: **NÃO**.

O SQL incluído é somente verifier READ-ONLY e só deve ser executado depois do Golden JOVI H3.1.3, após Chambinho passar novamente.

O verifier H3.1.3 adiciona checks de **role integrity**, não apenas no-domain/Truth exclusion:
- filhos de `Foco do Produto` do YouTube devem ser `product_attribute`;
- filhos de `Adequação à Plataforma` do YouTube devem ser `platform_scope`;
- filhos de `Adequação à Plataforma` do Instagram devem ser `platform_scope`;
- diretiva criativa Instagram deve continuar Requirement;
- heading de ativação Instagram deve continuar `solution_reference`.

## Sequência
1. Subir/substituir apenas os arquivos listados.
2. Reboot.
3. Confirmar `V28.7.2C0.2.4H3.1.3` na página Requirement Semantic Truth Repair.
4. Rodar **Chambinho** uma vez e enviar JSON.
5. Só após aprovação do Chambinho, rodar **JOVI** uma vez e enviar JSON.
6. Só após aprovação preliminar do JSON JOVI, executar `NAVE_V28_7_2C0_2_4H3_1_3_VERIFY_GOLDEN_JOVI.sql` no Supabase e enviar CSV.
7. Não rodar B2.12.2.1 nem B2.13 durante esta validação.
