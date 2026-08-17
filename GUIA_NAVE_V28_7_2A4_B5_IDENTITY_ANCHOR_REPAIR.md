# NAVE by VOE · V28.7.2A4 + B5 — Identity Anchor & Strategy Scope Repair

## O que o JOVI provou

O deploy A3+B4 finalmente rodou corretamente.

A parte B passou quase inteira:
- On Tour virou Creative Platform;
- EVENT JOURNEY ficou como única Experience Architecture;
- PRE-EVENT / EVENT / POST-EVENT / PRODUCT REVEAL / ACTIVATION REVEAL ficaram presentes;
- nenhuma observation Core ficou open.

Mas a A expôs um bug no resolver de identidade.

As 7 observations da A ficaram:
- 6 reconciliadas;
- 1 open;
- somente 1 nova Solution evidence-led;
- somente 1 Solution evidence-reconciled.

O banco terminou com apenas `KWAI activation`, enquanto os candidate outcomes verified eram 4 e o current outcome da mesma identidade chegou a ter reason `Proposal occurrence observed as 'YOUTUBE activation'.`

A causa está em `project_domain_identity.py`.

O matcher tratava `ativacao` como token genérico, mas não tratava o equivalente inglês `activation`. Por isso, depois de criar `KWAI activation`, o token compartilhado `activation` virava um "unique anchor" e YouTube / Instagram / TikTok eram anexados à mesma identity.

O caso `TIKTOK activation` ainda tinha outro risco: a similaridade de caracteres com `KWAI activation` ficava alta o suficiente para cair em `review_required`.

## Correção A4

O resolver passa a usar vocabulário genérico multilíngue e um score de identidade que separa:
- token genérico do domínio;
- anchor discriminativo.

Exemplo:

`KWAI activation`
vs
`YOUTUBE activation`

Compartilham somente o genérico `activation`.
Anchors `kwai` e `youtube` são distintos.
Resultado: `create_new`.

Mas variações morfológicas plausíveis continuam reviewable:

`Oficina Personalizada`
vs
`Oficina de Personalização`

não são transformadas automaticamente em identities distintas.

## Repair A4

Como o A3 já persistiu o collapse, o SQL:
- reabre as Semantic Observations anexadas à identity errada;
- invalida apenas as occurrences cross-platform erradas;
- supersede apenas os outcomes originados dessas observations;
- mantém a occurrence/outcome correto de KWAI;
- rebaixa os evidence bindings históricos errados para `context_only` com confidence 0;
- não apaga histórico.

Após nova reconciliação, esperamos quatro identities:
- KWAI activation
- YOUTUBE activation
- INSTAGRAM activation
- TIKTOK activation

Instagram possui duas Evidence Units de proposta, portanto múltiplas occurrences para a mesma identity continuam corretas.

## Correção B5

O runtime B4 já contém a proteção que impede público-alvo de atravessar `Alinhamento Estratégico`.

O objeto histórico `Frequentadores de festivais de música;` permaneceu ativo apenas porque o repair B4 não o selecionou.

O B5 invalida somente esse objeto legado e suas relações, preservando o histórico.

Strategy esperado no JOVI após o repair: 7 elementos ativos.

## Arquivos GitHub

Substituir:
- `project_domain_identity.py`
- `tests/test_v28_7_2a_identity_policy.py`

Nenhum outro runtime precisa mudar nesta rodada.

## SQL

Executar uma vez:
`NAVE_V28_7_2A4_B5_IDENTITY_ANCHOR_REPAIR.sql`

## Ordem

1. substituir os dois arquivos no GitHub;
2. reboot do Streamlit;
3. executar o Repair SQL A4+B5 uma vez;
4. abrir o mesmo JOVI;
5. clicar uma vez em `Reconciliar Core Semantic Domains · V28.7.2B`;
6. rodar `NAVE_V28_7_2A4_B5_VERIFY_GOLDEN_JOVI.sql`;
7. enviar print + CSV.

## Resultado esperado

### Reconciliation Kernel A
- Observations: 7
- Reconciled: 6
- Open: 1
- evidence-reconciled solutions: 4
- new evidence-led: 4
- 4 platform identities distintas
- aproximadamente 6 active evidence-led occurrences distribuídas entre as 4 identities
- proposal current truth: 4 identities

### Core B
- Strategy: 7
- Creative platforms: 1
- Creative elements: 1
- Experience architectures: 1
- Journey moments: 5
- Core observations open: 0
- On Tour permanece Creative Platform
- EVENT JOURNEY permanece única architecture
- Activation Reveal permanece

### Gates ainda fora desta rodada
Os 13 requirements sem provenance continuam deliberadamente fora.
Não são zerados por keyword binding.

## Validação local

A alteração de Identity Policy passou:
- 20 testes focados A/A3;
- casos existentes de Chambinho continuam passando;
- `Oficina Personalizada` continua review_required;
- as quatro platform activations passam a quatro identities distintas.

## Estado
- migration_mode: legacy_shadow
- Graph V28.6: congelado
- domain_primary: NÃO
- cutover: NÃO
