# NAVE by VOE · V28.6.0 — Canonical Entity Graph & Cross-Source Resolution

## Objetivo

A V28.6.0 ataca o principal gargalo que permaneceu depois da V28.5: a NAVE já consegue extrair briefing, proposta, custos e pós-evento, mas ainda conecta pouco o mesmo objeto ao longo das fontes.

A regra nova é:

> uma solução do projeto precisa ter identidade própria antes de a NAVE tentar relacioná-la a custo, execução, briefing, feedback ou aprendizado.

Exemplo esperado:

`Amarelinha` → entidade canônica do projeto → proposta → linha financeira “Ativação - Amarelinha” → evidência pós-evento → resultado/aprendizado.

## O que muda

### 1. Canonical Project Entity Graph

Novo módulo `project_entity_graph.py`.

Antes do Cross-Source Linker, ele usa estruturas já validadas do workspace como sementes canônicas:

- `memory_items` → soluções/ativações/brindes/cenografia/comunicação;
- `memory_cost_items` → linhas financeiras;
- `memory_briefing_requirements` → requisitos do briefing.

Nenhum conhecimento anterior é apagado.

### 2. Entity Resolution v2

O resolver passa a aceitar identidade entre tipos semanticamente compatíveis, sem transformar qualquer tipo igual em merge.

Exemplos permitidos:

- `activation ↔ solution`;
- `activation ↔ deliverable`;
- `solution ↔ deliverable`;
- `gift ↔ presskit` quando o nome for realmente distintivo;
- `concept ↔ strategy`;
- `venue ↔ venue_space`.

Exemplos que continuam bloqueados:

- `activation ↔ gift` apenas porque o texto coincide;
- entidades de projetos diferentes;
- nomes genéricos como “Brincadeiras”, “Ativações” ou “Materiais”.

### 3. Cost Linking v2

O vínculo financeiro passa a aceitar linhas cujo nome é uma versão mais curta, porém distintiva, da solução apresentada.

Isso cobre casos como:

- `Oficina Origami de Coração` ↔ `Ativação - Oficina de Origami`;
- `Amarelinha` ↔ `Ativação - Amarelinha`;
- `Pescaria` ↔ `Ativação - Pescaria`.

Linhas com valor `R$ 0,00` continuam podendo representar vínculo de escopo; custo zero não significa ausência da solução na planilha.

### 4. Reconstrução sem reprocessar arquivos

A tela **Importar projeto completo → Corrigir um projeto importado...** ganha o botão:

**Reconstruir apenas conexões inteligentes**

Ele NÃO reprocessa PDF, DOCX, XLSM ou PPTX.

Ele apenas executa novamente:

1. Canonical Entity Graph;
2. Cross-Source Linker;
3. Unified Snapshot;
4. Project Analyst.

Isso permite evoluir o cérebro relacional sem arriscar uma nova materialização dos masters.

## Teste recomendado — Golden Chambinho

Depois do deploy:

1. não reenvie arquivos;
2. não faça o reprocessamento completo;
3. abra **Importar projeto completo**;
4. expanda **Corrigir um projeto importado por uma versão anterior da V28**;
5. selecione **Festivalzinho Chambinho**;
6. confirme a caixa;
7. clique em **Reconstruir apenas conexões inteligentes**.

### O que observar

Os números não precisam ficar perfeitos ainda, mas devem sair do estado anterior de quase desconexão total.

Prioridade de validação:

- `Entidades canônicas` > 0;
- `Solução ↔ custo` deve reconhecer principalmente Origami, Amarelinha e Pescaria;
- `Entidades unificadas` deve crescer quando a mesma solução aparece em mais de uma fonte;
- `Evidências de execução` deve preservar/aumentar correspondências confiáveis;
- nenhum merge pode usar apenas ano, número ou palavra genérica.

## Arquivos a substituir/adicionar

### Adicionar

- `project_entity_graph.py`
- `tests/test_v28_6_0_canonical_entity_graph.py`
- `GUIA_NAVE_V28_6_0_CANONICAL_ENTITY_GRAPH.md`

### Substituir

- `entity_resolution.py`
- `cross_source_linker.py`
- `project_intelligence_pipeline.py`
- `project_bundle_materializer.py`
- `project_batch_ingestion.py`
- `pages/14_Importar_Projeto.py`

## SQL

**NÃO.**

A V28.6.0 usa as tabelas do Intelligence Foundation já existentes.

## Reboot

**SIM.**

Depois de subir os arquivos, faça **Manage app → Reboot app**.

## Critério arquitetural preservado

A V28.6 não substitui a V28.5. Ela fica abaixo dela:

`fontes → evidências → entidades canônicas → relações cross-source → Unified Truth → Decision Intelligence → workspace / Dossiê`.

A NAVE continua proibida de transformar correspondência incerta em fato. Relações ambíguas permanecem revisão auditável.
