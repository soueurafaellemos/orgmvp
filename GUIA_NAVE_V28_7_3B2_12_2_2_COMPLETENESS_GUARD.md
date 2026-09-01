# NAVE V28.7.3B2.12.2.2 — Completeness Quantifier Guard

## Diagnóstico

O Golden JOVI B2.12.2.1 melhorou corretamente depois do H3.1.3:
- 70 Current Requirements;
- 70 semantic eligible;
- 0 no-domain exclusions downstream;
- 0 semantic unknown;
- queue 33;
- 2 confirm / 5 partial / 26 reject;
- 1 canonical identity collision;
- zero Human Review / Truth / persistence / cutover effects.

O falso confirm `Storytelling detalhado` desapareceu.

Restou um false-confirm estrutural:
`Materiais Gráficos: ... convite, STD, Reminder e todo o material proposto no projeto.`

A evidência prova Save the Date + invitation + Reminder, mas não prova a cláusula aberta
`todo o material proposto no projeto`.

## Correção

B2.12.2.2 adiciona um guard conservador pós-B2.12.2.1.

Ele:
- nunca promove uma recomendação;
- só pode manter ou rebaixar;
- rebaixa confirm → partial quando existe quantificador de completude/universalidade
  não comprovado pela evidência;
- preserva todos os guards anteriores;
- preserva a collision de identidade sem auto-merge;
- mantém todo o fluxo read-only/shadow.

## Arquivos

ADICIONAR:
- `project_requirement_auto_adjudication_completeness.py`
- `tests/test_v28_7_3b2_12_2_2_completeness_guard.py`
- `GUIA_NAVE_V28_7_3B2_12_2_2_COMPLETENESS_GUARD.md`

SUBSTITUIR:
- `pages/32_Automated_Adjudication_Recommendations.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

## SQL

NÃO.

## Reboot

SIM.

## Teste

Depois do deploy:
1. Reboot.
2. Confirmar na página 32 `V28.7.3B2.12.2.2`.
3. Rodar SOMENTE Festivalzinho Chambinho primeiro.
4. Baixar JSON completo B2.12.2.2 e enviar.
5. Não rodar JOVI até Chambinho ser aprovado.

Esperado para Chambinho:
- 13 Current;
- 13 eligible;
- 0 excluded;
- 0 unknown;
- queue 3;
- 1 confirm / 1 partial / 1 reject;
- completeness_downgrades = 0.

Depois do Golden Chambinho, o JOVI esperado é:
- 70 Current / 70 eligible;
- queue 33;
- 1 confirm / 6 partial / 26 reject;
- completeness_downgrades = 1;
- Materiais Gráficos → partial por `unresolved_completeness_quantifier`;
- Espaço para plenária → permanece confirm;
- collision co-investimento permanece diagnosticada, sem auto-merge.

Os números são expectativas de regressão, não substituem auditoria semântica.
