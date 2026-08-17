# NAVE by VOE · V28.7.2B3 — Semantic Scope & Atomicity

## Diagnóstico

O B2 corrigiu corretamente os quatro falsos Strategy Elements e o Golden ficou com o conjunto exato de 8 Strategy Elements.

O CSV pós-B2 revelou dois pontos restantes:

1. `PRESENÇA E ATENÇÃO` ainda mantinha a página inteira como `statement`, enquanto `CONEXÃO` e `MEMÓRIA AFETIVA` já estavam atômicos;
2. o painel Core B mostrava `Unsupported = 4`, mas esses quatro registros eram exatamente os objetos históricos que o B2 havia invalidado. Eles não são current Core Truth;
3. como `semantic_observations` é compartilhada, o painel V28.7.2A passou a contar também as 9 observations de Strategy/Creative da B, inflando `Observações` de 22 para 31.

Nenhum desses pontos reabre Solution Identity, Truth Gate de outcomes ou financeiro.

## O que muda

### Runtime

`project_core_semantic_extractor.py` passa a manter o corpo local do último heading de `PONTOS DE PARTIDA` até o fim da página visual quando não existe um heading irmão posterior.

No Chambinho:

`PRESENÇA E ATENÇÃO`
→ `Espaço e ativações desenvolvidas para / estimular a imaginação e a presença`

A Evidence Unit continua sendo a página original.

### SQL de views

`project_semantic_observation_status` volta a medir somente o escopo do Reconciliation Kernel V28.7.2A.

Strategy/Creative/Experience/Journey continuam na mesma tabela de staging, mas deixam de inflar os contadores da A.

`project_core_semantic_status` passa a contar `Unsupported` somente para objetos `lifecycle_status='active'`.

Os quatro falsos objetos invalidated pelo B2 continuam preservados no histórico e continuam consultáveis em `project_core_semantic_truth_status`, mas deixam de aparecer como current unsupported truth.

## Arquivos GitHub

Substituir:

- `project_core_semantic_extractor.py`
- `tests/test_v28_7_2b_core_extractor.py`

Adicionar:

- `tests/test_v28_7_2b3_semantic_scope.py`

## Supabase

Executar uma vez:

`NAVE_V28_7_2B3_SEMANTIC_SCOPE_ATOMICITY.sql`

É um hotfix de views. Não executa repair de objetos e não repete a migration B.

## Ordem

1. executar o SQL B3;
2. substituir os arquivos no GitHub;
3. reboot do Streamlit;
4. no Chambinho, clicar uma vez em `Reconciliar Core Semantic Domains · V28.7.2B`;
5. rodar `NAVE_V28_7_2B3_VERIFY_GOLDEN_CHAMBINHO.sql`;
6. exportar o CSV e enviar com print.

## Resultado esperado

### V28.7.2A

- Observações: **22**
- Reconciliadas: **20**
- No-domain: **2**
- Solutions: 19
- Occurrences: 36
- execution truth: 8

### V28.7.2B

- Strategy: **8**
- Creative platforms: **1**
- Creative elements: **1**
- Experience architectures: **0**
- Journey moments: **0**
- Semantic observations: **9**
- Verified explicit: **10**
- Unsupported: **0**
- Fact relations: **1**
- Inference relations: **4**

### Strategy

Conjunto ativo exato:

- NOSTALGIA
- CONEXÃO
- MEMÓRIA AFETIVA
- PRESENÇA E ATENÇÃO
- Resgate da infância
- Conexão familiar entre pais e filhos
- Imaginação e memórias
- Coração

Os três `PONTOS DE PARTIDA` devem ter statements locais.

## Regressões obrigatórias

- Truth Gate PASS
- Coverage 0
- Identity conflict 1
- 54/54 financeiro
- R$ 554.310,85
- Graph V28.6 congelado
- migration_mode = legacy_shadow

## Validação local

- `py_compile`: PASS
- suíte focada B após alteração: 28 PASS
- teste adicional B3 valida atomicidade final e contratos SQL.

## SQL / reboot / masters / JOVI

- SQL: **SIM — B3 views**
- Reboot: **SIM**
- Reprocessar masters: **NÃO**
- JOVI: **AINDA NÃO**
- Cutover/domain_primary: **NÃO**
