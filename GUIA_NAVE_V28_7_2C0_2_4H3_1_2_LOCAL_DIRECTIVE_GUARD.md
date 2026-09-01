# NAVE V28.7.2C0.2.4H3.1.2 — Local Directive & Base Semantic Precedence Guard

## Motivo
O Golden JOVI H3.1.1 comprovou a correção dos pseudo-requirements de audiência, plataforma e exemplos, mas revelou um novo falso-negativo: uma instrução local real — `Direcionamento criativo: Construir...` — herdou `platform_scope` da seção anterior e foi retirada de Current Requirement Truth. Também houve retyping desnecessário de um heading de ativação que H3 já reconhecia como `solution_reference`.

## Correção estrutural
H3.1.2 mantém o lookback cross-unit e o Section Boundary Guard, mas adiciona duas regras de precedência:

1. **Base H3 semantic precedence** — H3.1.x só pode corrigir rows que H3 ainda tratou como `requirement_candidate` ou `constraint_candidate`. Se H3 já reconheceu scope/reference/attribute/context, o wrapper não reescreve essa semântica.
2. **Local Directive Guard** — uma nova diretiva explícita local (`Direcionamento criativo:`, `Creative Direction:`, variantes para a agência) não pode ser demovida por parent estrutural anterior.

Não há hardcode de cliente/plataforma na lógica de produção. Os exemplos JOVI aparecem somente nos testes/verifier Golden.

## Arquivos a substituir
- `project_requirement_semantic_h31.py`
- `project_requirement_reconciliation_h31.py`
- `pages/33_Requirement_Semantic_Truth_Repair.py`
- `tests/test_v28_7_2c0_2_4h3_1_cross_unit_context.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

## Arquivo a adicionar
- `NAVE_V28_7_2C0_2_4H3_1_2_VERIFY_GOLDEN_JOVI.sql`
- `GUIA_NAVE_V28_7_2C0_2_4H3_1_2_LOCAL_DIRECTIVE_GUARD.md`

## SQL
Migration SQL: **NÃO**. O SQL incluído é apenas verifier READ-ONLY e só deve ser executado após o novo Golden JOVI H3.1.2.

## Sequência
1. Subir arquivos.
2. Reboot.
3. Rodar Chambinho H3.1.2 e enviar JSON.
4. Só após aprovação, rodar JOVI H3.1.2.
5. Depois da aprovação preliminar do JSON JOVI, executar o verifier READ-ONLY H3.1.2 e enviar CSV.

Não rodar B2.12.2.1 nem B2.13 durante esta validação.
