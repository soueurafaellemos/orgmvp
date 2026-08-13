# NAVE by VOE · V28.7.0 — Domain Normalization Foundation

## Objetivo desta versão

A V28.7.0 corrige uma lacuna arquitetural identificada depois da V28.6.2: a NAVE já possuía Evidence Layer, Intelligence Graph e diversos objetos `memory_*`, mas ainda não havia concluído a **Domain Normalization** prevista no Data Model original.

Esta versão cria a camada que separa definitivamente:

- **Project Solution Instance** — a solução contextual daquele projeto;
- **Evidence / Mention** — onde a solução apareceu em arquivo/página/slide;
- **Requirement** — o que o briefing pediu;
- **Financial Line Item** — a linha financeira;
- **Outcome** — o que aconteceu/aprovação/execução/resultado.

O objetivo NÃO é melhorar artificialmente o contador do Entity Graph. O objetivo é dar à NAVE os objetos corretos para o próximo Relation Graph V2.

---

## O que muda no banco

A migration cria apenas cinco novos sources of truth de domínio:

1. `project_solution_instances`
2. `project_requirements`
3. `financial_documents`
4. `financial_line_items`
5. `entity_outcomes`

E duas views de apoio:

- `entity_current_outcomes`
- `project_domain_normalization_status`

### Importante

`memory_*` **não é removido, migrado destrutivamente nem apagado**.

A V28.7.0 funciona em **shadow/dual-write**. A interface atual continua compatível com o legado enquanto validamos a nova camada.

---

## Mudança conceitual importante: `memory_items` não vira 1:1 uma nova entidade

O erro que queremos evitar é continuar tratando ocorrência como identidade.

Por isso, o backfill consolida ocorrências exatas de `memory_items` em uma única **Project Solution Instance** quando a identidade contextual é equivalente.

Exemplo:

- slide “Press Kit” de abertura;
- slide “Press Kit” detalhando a composição;

podem alimentar a mesma instância `Press Kit — Festivalzinho Chambinho 2026`, preservando os dois IDs legados em `legacy_source_ids`.

O mesmo princípio reduz duplicatas óbvias sem criar um canônico global prematuro.

---

## Identidade ≠ papel contextual

A nova tabela `project_solution_instances` possui:

- `solution_kind` — o que a solução é naquele projeto;
- `roles[]` — papéis contextuais adicionais.

Isso prepara casos como:

- uma meia ser `gift` e futuramente `presskit_component`;
- uma oficina ser uma `activation/workshop`, mesmo se entregar um brinde;
- um Press Kit funcionar como container, e não como sinônimo de qualquer brinde do projeto.

Nesta versão, relações como `part_of` ainda continuam no Graph V28.6. O cutover dessas relações para as Project Solution Instances acontece na próxima fase.

---

## Knowledge Entities nesta versão

Cada objeto de domínio recebe um mirror 1:1 em `knowledge_entities`:

- `project_solution_instances` → mirror de solução;
- `project_requirements` → mirror `requirement`;
- `financial_line_items` → mirror `financial_line_item`.

`canonical_solution_id` permanece opcional.

Isso é intencional: uma solução nova de um projeto **não precisa ganhar automaticamente uma identidade canônica global**.

---

## Outcomes são append-only

`entity_outcomes` não sobrescreve história.

Uma atualização posterior de `memory_item_outcomes` ou `memory_project_outcomes` gera um novo evento quando a versão legada mudou. A view `entity_current_outcomes` resolve o estado atual por:

1. confirmação humana;
2. autoridade da fonte;
3. data do outcome;
4. data de criação.

Esse é o primeiro passo para que `projects.status` deixe de ser, no futuro, a autoridade semântica final.

---

## Knowledge Monotonicity também vale aqui

`sync_project_domain_normalization()` é idempotente e monotônico:

- adiciona objetos novos;
- atualiza objetos que continuam representados no legado;
- **não apaga automaticamente uma solução normalizada porque uma leitura legacy desapareceu**.

Isso evita repetir o problema que já corrigimos no reprocessamento de arquivos.

---

# Instalação

## 1. SQL — SIM, precisa executar

No Supabase:

**SQL Editor → New query**

Execute integralmente:

`NAVE_V28_7_0_DOMAIN_NORMALIZATION_FOUNDATION.sql`

O SQL é idempotente e não contém `DROP TABLE` nem delete de `memory_*`.

### Por que `source_asset_id` e `source_evidence_id` ainda aceitam NULL?

Durante a migração, alguns projetos antigos possuem materialização legacy válida sem mapeamento completo para a Evidence Layer. Tornar essas FKs obrigatórias agora bloquearia o backfill.

A restrição poderá ser endurecida depois que a cobertura de Evidence atingir o gate definido pelo IQ Bench.

---

## 2. GitHub — adicionar/substituir exatamente estes arquivos

### Adicionar

- `project_domain_normalization.py`
- `tests/test_v28_7_0_domain_normalization.py`

### Substituir

- `project_intelligence_pipeline.py`
- `project_workspace_db.py`
- `project_workspace_visuals.py`
- `cross_source_linker.py`
- `pages/14_Importar_Projeto.py`

### Não precisa subir no GitHub para o runtime

- `NAVE_V28_7_0_DOMAIN_NORMALIZATION_FOUNDATION.sql` — executar no Supabase;
- `GUIA_NAVE_V28_7_0_DOMAIN_NORMALIZATION_FOUNDATION.md` — documentação do patch.

---

## 3. Reboot — SIM

Depois de executar o SQL e subir os arquivos:

**Streamlit → Manage app → Reboot app**

---

# Como validar no Golden Chambinho

Não reenvie arquivos e não faça novo reprocessamento semântico.

Vá em:

**Importar projeto completo → Corrigir um projeto importado por uma versão anterior da V28 → Festivalzinho Chambinho**

Clique:

**Atualizar domínio e conexões inteligentes**

A ação agora executa, em ordem:

1. Domain Normalization;
2. Canonical/Occurrence Graph legado V28.6 em shadow compatibility;
3. Cross-Source atual;
4. Unified Snapshot / Project Analyst.

## O que deve aparecer

Um novo expander:

**Domain Normalization · nova camada de domínio**

Com métricas:

- Soluções do projeto;
- Requisitos;
- Docs financeiros;
- Linhas financeiras;
- Outcomes.

### Gates desta rodada

Para Chambinho, a validação mais importante é:

- `Requisitos` deve manter cobertura equivalente às 14 demandas legacy;
- `Docs financeiros` deve preservar o documento financeiro estruturado;
- `Linhas financeiras` deve manter as 54 linhas;
- `Soluções do projeto` pode ser **menor que `memory_items`**, porque a normalização deve consolidar ocorrências/duplicatas em vez de copiar o erro 1:1;
- nenhum `memory_*` pode desaparecer;
- o workspace atual deve continuar funcionando como antes.

Não usamos ainda o contador do Entity Graph como gate principal desta versão. O Relation Graph continua sendo a camada V28.6 até o próximo patch.

---

# Por que `cross_source_linker.py` foi alterado

Os novos mirrors de `financial_line_items` já existem em `knowledge_entities`, mas o Relation Graph V28.6 ainda trabalha com os mirrors legacy.

Sem proteção, ele poderia enxergar ao mesmo tempo:

- `memory_cost_items`;
- `financial_line_items` normalizados;

e duplicar candidatos de custo.

Por isso os domain mirrors novos ficam explicitamente em **shadow mode** no linker atual. Essa proteção será removida no Relation Graph V2, quando o Graph passar a operar sobre os objetos normalizados como fonte primária.

---

# O que esta versão propositalmente NÃO faz

- não troca as telas para ler `project_solution_instances` ainda;
- não remove `memory_*`;
- não cria Knowledge Across Projects;
- não cria feedback granular ainda;
- não faz global canonical resolution de toda solução;
- não tenta resolver todo `part_of` / Press Kit por fuzzy matching;
- não reescreve o Project Analyst.

Esses pontos dependem primeiro de validar a paridade da nova camada de domínio.

---

# Próximo passo se a V28.7.0 passar

**Project Relation Graph V2**.

O debugger deixa de responder “entidade canônica” e passa a responder por **Project Solution Instance**:

| Solução do projeto | Briefing | Proposta | Custo | Execução | Feedback | Outcome | Evidências |
|---|---:|---:|---:|---:|---:|---:|---:|

A partir daí, links como `responds_to`, `costed_by`, `part_of` e execução/outcome deixam de precisar ser reparented entre identidades concorrentes: eles passam a ligar diretamente os objetos corretos.

---

# Testes

Validação focada sobre V28.4 → V28.5 → V28.6.x → V28.7.0:

**41 testes passando.**

A suíte integral deste container não coleta seis módulos por dependências de runtime ausentes localmente (`streamlit`, `google.genai` e `nave_storage`). Esses erros são de ambiente de teste e não foram tratados como regressão da V28.7.0.

## Novo gate arquitetural

**Domain Normalization Parity**

- requirements/financial objects: sem perda frente ao legado;
- solution instances: consolidação permitida e desejável;
- nenhuma exclusão automática;
- nenhum insight novo é produzido apenas pela migração.
