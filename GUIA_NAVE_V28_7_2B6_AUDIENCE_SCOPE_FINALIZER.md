# NAVE by VOE · V28.7.2B6 — Audience Scope Finalizer

## Diagnóstico

O A5 convergiu corretamente a camada A no Golden JOVI:

- 27 Solutions;
- 47 Occurrences, todas com Evidence;
- 7 observations A;
- 6 reconciled / 1 open;
- 4 evidence-reconciled solutions;
- 4 evidence-led platform identities;
- 4 current proposal truths;
- KWAI / YouTube / Instagram / TikTok distintas;
- nenhum cross-platform collapse;
- Truth Gate PASS.

No Verify, todos os gates da A estão `true`.

A B também convergiu em Creative + Experience/Journey:

- On Tour = Creative Platform;
- EVENT JOURNEY = única Experience Architecture;
- PRE-EVENT / EVENT / POST-EVENT / PRODUCT REVEAL / ACTIVATION REVEAL presentes;
- Core observations open = 0.

Restaram somente dois gates falsos, ambos causados pelo mesmo Strategy histórico:

- `strategy_count_is_7 = false`
- `no_meta_strategy_pollution = false`

O objeto residual é:

`Frequentadores de festivais de música;` → `strategic_direction`

A fonte mostra que isso pertence ao público-alvo dentro do bloco `Alinhamento Estratégico`, não é uma direção estratégica.

## Causa

O B4 já parava quando encontrava um parágrafo separado `Público-alvo:`.

Mas o briefing JOVI possui uma variação documental em que a mesma Evidence do heading pode conter:

`Alinhamento Estratégico:`
`A proposta deve estar fortemente conectada ao nosso público-alvo principal:`

Nesse formato, o adjacency collector abria o grupo antes de perceber que o próprio heading já estava audience-scoped. Os bullets seguintes eram então candidatos; somente `Frequentadores de festivais de música` tinha comprimento suficiente para ser materializado.

## Correção runtime

`project_core_semantic_extractor.py` agora detecta um strategic heading que já contém:

- público-alvo;
- target audience;
- audience profile;
- perfil de público.

O heading estratégico pode continuar existindo como Strategy, mas **não abre adjacency para os bullets seguintes**.

A regra é genérica e não contém JOVI ou nomes do Golden.

## Repair

Como o falso objeto já foi persistido e a Knowledge Monotonicity não o apaga por ausência posterior, o SQL B6 o invalida uma última vez.

O repair:
- não usa DELETE;
- invalida o Strategy stale;
- invalida governance;
- mantém a Knowledge Entity histórica como inactive;
- supersede a Semantic Observation antiga;
- supersede relations dependentes;
- preserva Evidence e trilha de auditoria.

## Arquivos GitHub

Substituir:
- `project_core_semantic_extractor.py`
- `tests/test_v28_7_2b_core_extractor.py`

## SQL

Executar uma única vez:
`NAVE_V28_7_2B6_AUDIENCE_SCOPE_REPAIR.sql`

## Ordem

1. substituir os dois arquivos no GitHub;
2. reboot do Streamlit;
3. executar o Repair SQL B6 uma vez;
4. abrir o mesmo JOVI;
5. clicar uma vez em `Reconciliar Core Semantic Domains · V28.7.2B`;
6. rodar `NAVE_V28_7_2B6_VERIFY_GOLDEN_JOVI.sql`;
7. enviar print + CSV.

## Resultado esperado

### A
Permanece:
- Solutions 27;
- Occurrences 47;
- Current truth 4;
- Verified 4;
- 7 observations / 6 reconciled / 1 open;
- 4 evidence-led platform identities.

### B
- Strategy 7;
- Creative platforms 1;
- Creative elements 1;
- Experience architectures 1;
- Journey moments 5;
- Unsupported 0;
- Core open 0.

Todos os gates do Verify devem ficar `true`.

## Requirements

Os 13 Requirements sem provenance continuam registrados como dívida separada. Eles não fazem parte deste B6 e não serão ligados por keyword para zerar contador.

## Validação local

- `py_compile`: PASS
- suíte focada do extractor: 20 PASS
- inclui regressão específica para heading estratégico já audience-scoped
- inclui regressão para boundary de audiência em parágrafo separado

## Estado

- migration_mode: legacy_shadow
- Graph V28.6: congelado
- domain_primary: NÃO
- cutover: NÃO
