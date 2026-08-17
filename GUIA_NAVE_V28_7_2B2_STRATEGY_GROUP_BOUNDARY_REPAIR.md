# NAVE by VOE · V28.7.2B2 — Strategy Group Boundary & Precision Repair

## Status

Hotfix de precisão para o shadow rollout V28.7.2B.

A V28.7.2B continua **não aprovada** até o Golden Chambinho passar este B2 e depois o Golden JOVI passar a B.

## O que o Golden revelou

A B1 recuperou corretamente Strategy que havia sido perdida pela Evidence PDF achatada, mas o teste real revelou um novo false positive:

um grupo explícito iniciado por `Pilares:` continuava lendo parágrafos seguintes até um limite numérico. Como `Canais oficiais:` não estava no vocabulário de stop headings, o grupo atravessou a fronteira documental e materializou recursos como Strategy:

- Canais oficiais
- Site Lactalis
- Site Chambinho
- YouTube

Isso é semanticamente inválido mesmo que todos os gates anteriores estejam verdes.

Também foi observado que os três `PONTOS DE PARTIDA` da proposta estavam usando a página inteira como `statement`, em vez de manter a explicação local de cada heading.

## O que muda no runtime

### 1. Boundary detection genérico

Depois de `Pilares:` / `Pontos de partida`, um novo parágrafo curto que **termina em `:`** encerra o grupo, mesmo que o heading não faça parte de uma lista hardcoded.

Exemplo:

`Pilares:` → itens válidos → `Canais oficiais:` → STOP.

Uma linha como `Inovação: simplificar a experiência...` continua válida como item porque não termina no rótulo.

### 2. Statements atômicos em páginas visuais

Quando uma página possui:

`PONTOS DE PARTIDA`
`CONEXÃO`
`corpo de Conexão`
`MEMÓRIA AFETIVA`
`corpo de Memória`
...

cada Strategy Element recebe apenas seu corpo local como `statement`.

A Evidence Unit original continua sendo a página inteira; atomicidade aqui é semântica, não uma nova Evidence Unit artificial.

## Repair SQL

A B1 já persistiu quatro falsos objetos. A Knowledge Monotonicity impede que uma nova leitura simplesmente os apague.

Por isso o B2 inclui um repair SQL de lifecycle:

- não deleta nada;
- marca os falsos Strategy Elements como `invalidated`;
- marca seus mirrors em `domain_object_governance`;
- deixa `knowledge_entities` como `inactive`;
- marca a Semantic Observation original como `superseded`;
- supersede qualquer relation ativa que toque uma entidade invalidada;
- preserva `domain_object_evidence` e `relation_evidence` para auditoria histórica.

O repair é genérico: só atua em Strategy que veio de `adjacent_explicit_group_heading` e cuja Evidence é um novo heading terminal curto ou contém URL/web resource.

## Arquivos do GitHub

Substituir:

- `project_core_semantic_extractor.py`
- `tests/test_v28_7_2b_core_extractor.py`

Não substituir outros módulos.

## Supabase

Executar uma única vez:

`NAVE_V28_7_2B2_STRATEGY_GROUP_BOUNDARY_REPAIR.sql`

Não executar novamente a migration V28.7.2B.

## Ordem

1. substituir os dois arquivos no GitHub;
2. reboot do Streamlit;
3. executar o repair SQL B2 uma vez;
4. abrir o Golden canônico Festivalzinho Chambinho;
5. clicar uma vez em `Reconciliar Core Semantic Domains · V28.7.2B`;
6. rodar `NAVE_V28_7_2B2_VERIFY_GOLDEN_CHAMBINHO.sql`;
7. exportar CSV + enviar print.

## Resultado esperado no Chambinho

Core B ativo:

- Strategy: **8**
- Creative platforms: **1**
- Creative elements: **1**
- Experience architectures: **0**
- Journey moments: **0**

Strategy ativa esperada:

- NOSTALGIA — territory
- CONEXÃO — strategic_principle
- MEMÓRIA AFETIVA — strategic_principle
- PRESENÇA E ATENÇÃO — strategic_principle
- Resgate da infância — pillar
- Conexão familiar entre pais e filhos — pillar
- Imaginação e memórias — pillar
- Coração — pillar

Não podem permanecer ativos como Strategy:

- Canais oficiais
- Site Lactalis
- Site Chambinho
- YouTube
- outros links/canais/recursos documentais

Os três `strategic_principle` devem possuir statements locais/atômicos, não a página completa.

## Regressões que devem permanecer

- 19 Solutions
- 36 Occurrences
- 8 execution truths evidence-backed
- Coverage gaps 0
- Identity conflicts 1
- 54 linhas financeiras / 54 Evidence Units / R$ 554.310,85
- Truth Gate PASS
- migration_mode = legacy_shadow
- Graph V28.6 congelado

## Validação local

- `py_compile`: PASS
- suíte focada `test_v28_7_2b_*.py`: 27 PASS
- novos testes cobrem:
  - section boundary após `Pilares:`
  - item legítimo com `rótulo: corpo`
  - statements atômicos entre headings visuais

## SQL / reboot / masters / cutover

- SQL: **SIM — somente repair B2**
- Reboot: **SIM**
- Reprocessar masters: **NÃO**
- `domain_primary`: **NÃO**
- Cutover: **NÃO**
