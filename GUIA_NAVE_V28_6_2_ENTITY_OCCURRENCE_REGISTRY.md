# NAVE by VOE · V28.6.2 — Entity Occurrence Registry + Resolution Debugger

## Objetivo

A V28.6.1 provou que criar entidades canônicas não era suficiente. No Golden Chambinho, o painel chegou a **14 entidades canônicas**, mas apenas **1 entidade unificada, 2 vínculos solução↔custo, 1 execução ligada e 0 relações hierárquicas**.

A V28.6.2 corrige a causa estrutural: as estruturas especializadas do workspace (`memory_items`, `memory_item_outcomes`, `memory_cost_links`, `memory_briefing_links`) ainda viviam em paralelo ao Intelligence Graph. O Cross-Source tentava redescobrir por fuzzy matching identidades que o workspace já conhecia.

A regra nova é:

> **Todo registro estruturado relevante vira uma ocorrência de uma entidade ou uma relação explícita no Intelligence Graph.**

## O que muda

### 1. Occurrence Registry sem nova tabela

A versão reutiliza `knowledge_entities` para registrar ocorrências de domínio, evitando uma migração SQL desnecessária.

- `memory_items` → ocorrência de **proposta** ligada diretamente à entidade canônica.
- `memory_item_outcomes` → ocorrência de **execução** ligada diretamente à mesma entidade canônica.
- `memory_cost_items` → ocorrência financeira relacionável.
- `memory_briefing_requirements` → ocorrência de requisito relacionável.

A identidade conhecida pelo parser especializado deixa de depender de novo fuzzy matching.

### 2. Links estruturados entram ANTES do Cross-Source

Na V28.6.1, `ensure_automatic_cost_links()` e `ensure_automatic_briefing_links()` eram executados depois do Cross-Source Linker. Isso fazia o grafo só enxergar os vínculos no clique seguinte.

Agora a ordem é:

1. relatório pós-evento / outcomes;
2. links estruturados de custo e briefing;
3. Canonical Entity Graph;
4. Cross-Source Linker;
5. Unified Snapshot;
6. Project Analyst.

### 3. Workspace → Knowledge Graph

Os vínculos já calculados pelo workspace passam a gerar relações no grafo:

- solução → `costed_by` → linha financeira;
- solução → `responds_to` → requisito do briefing;
- solução → `has_execution_record` → occurrence pós-evento;
- outcome executado → claim `execution_result = executed` na entidade canônica.

Links de briefing têm threshold mais conservador que links financeiros para evitar erros como **“Restrição de verba e estrutura” → “Personalize o seu cadarço”**.

### 4. Press Kit vira entidade-contêiner válida

`Press Kit` estava sendo descartado como título genérico, portanto a NAVE não tinha um nó canônico sobre o qual gravar `part_of` / `contains`.

Na V28.6.2, `Press Kit` é permitido quando o tipo semântico é `presskit`. Isso desbloqueia a composição do kit quando a mesma evidência comprova os componentes.

### 5. Métricas deixam de mostrar apenas inserts do clique

O painel anterior podia mostrar `1` mesmo quando havia conhecimento válido de runs anteriores.

Agora o painel apresenta o estado consolidado:

- **Entidades canônicas**
- **Entidades multi-fonte**
- **Ocorrências ligadas**
- **Solução ↔ custo**
- **Execuções ligadas**
- **Relações hierárquicas**

### 6. Resolution Debugger

Depois de “Reconstruir apenas conexões inteligentes”, aparece um expander técnico temporário:

**Diagnóstico do Entity Resolution · por entidade**

Para cada canônico, mostra:

- proposta;
- execução;
- custo;
- briefing;
- hierarquia;
- número de ocorrências;
- motivo da lacuna.

Exemplos de diagnóstico:

- `sem ocorrência/menção pós-evento ligada`
- `sem costed_by`
- `press kit sem componentes ligados`

O objetivo é parar de olhar apenas um total como “1” e descobrir precisamente onde a cadeia quebra.

## Arquivos a substituir no GitHub

- `project_entity_graph.py`
- `cross_source_linker.py`
- `project_intelligence_pipeline.py`
- `project_bundle_materializer.py`
- `project_batch_ingestion.py`
- `pages/14_Importar_Projeto.py`
- `tests/test_file_analyst_integration_v2821.py`

## Arquivos a adicionar

- `tests/test_v28_6_2_occurrence_registry.py`
- `GUIA_NAVE_V28_6_2_ENTITY_OCCURRENCE_REGISTRY.md`

## SQL

**NÃO.**

A V28.6.2 reutiliza `knowledge_entities`, `knowledge_relations` e `knowledge_claims` já existentes.

## Reboot

**SIM.**

Depois de subir os arquivos:

1. `Manage app`
2. `Reboot app`

## Como testar o Golden Chambinho

Não reenvie e não reprocese os quatro arquivos.

Vá em:

**Importar projeto completo → Corrigir um projeto importado por uma versão anterior da V28 → Festivalzinho Chambinho → Reconstruir apenas conexões inteligentes**

Depois, envie:

1. o novo painel de métricas;
2. o expander **Diagnóstico do Entity Resolution · por entidade**.

O segundo print é agora mais importante que qualquer número agregado, porque vai mostrar exatamente quais entidades ainda estão isoladas e por quê.

## Critério desta rodada

A V28.6.2 não será considerada aprovada apenas por aumentar números.

O que precisa acontecer é coerência por entidade:

- soluções com outcome estruturado devem aparecer com execução ligada;
- links financeiros já existentes no workspace devem aparecer no grafo quando atingirem confiança suficiente;
- Press Kit precisa existir como contêiner antes de inferir componentes;
- briefing fraco/ambíguo deve permanecer como revisão, não virar verdade;
- nenhum ano, número ou heading genérico pode criar identidade.

## Validação local

- suíte focada V28.4–V28.6.2: **36 testes passaram**;
- suíte ampla coletável neste container: **105 passaram, 2 skipped**;
- 3 falhas restantes nessa execução são externas à V28.6.2: 1 teste legado de política visual de Locais e 2 imports que dependem do módulo de runtime `nave_storage`, ausente neste snapshot local do repositório;
- a coleta integral também encontra módulos que dependem de `streamlit` / `google-genai`, indisponíveis neste container.
