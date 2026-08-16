# NAVE by VOE · V28.7.2A
## Reconciliation Kernel, Context & Solution Lifecycle

**Status desta entrega:** pronta para **shadow rollout e validação Golden**.  
**Não significa aprovação da V28.7.2A, cutover ou `domain_primary`.**

---

## Objetivo

A V28.7.2A é a primeira etapa da **Core Semantic Domains & Evidence-Led Reconciliation**.

Ela substitui, para o novo caminho semântico, a lógica mental:

`memory_items → Project Solution Instance`

por:

**Evidence → Semantic Observation → Reconciliation → Domain**

O legado continua preservado para compatibilidade e comparação, mas deixa de ser o criador autoritativo das novas identidades reconciliadas.

A versão foi deliberadamente mantida pequena. Ela implementa apenas:

1. camada persistente de observações semânticas pré-domínio;
2. Reconciliation Kernel conservador para Project Solution Instances;
3. occurrences evidence-led ao longo do lifecycle;
4. execution outcomes evidence-backed;
5. Project Context inicial;
6. requirements quantitativos com valor, range e scope;
7. debugger/gates de reconciliação;
8. manutenção integral do Truth Gate da V28.7.1D.

**Não entram ainda:** Strategy, Creative Platform, Experience Architecture/Journey, Decision Layer, Feedback Domain final, Metric Observations final, Financial Envelopes, controlled taxonomy completa, Graph V2, Project Analyst V2 ou Recommendation V2.

---

# 1. Princípio arquitetural

A nova cadeia passa a ser:

```text
Source Asset
    ↓
Evidence Unit
    ↓
Semantic Observation
    ↓
Project Domain Reconciliation
    ↓
Project Solution Instance / Occurrence / Outcome / Context / Constraint
    ↓
Truth Gate
    ↓
Coverage & Identity Audit
```

`semantic_observations` **não é uma tabela de pseudo-entidades candidatas**.

Ela registra algo mais neutro:

> “esta Evidence Unit parece estar mencionando/registrando isto, neste papel e nesta fase”.

Uma observation não vira current truth, solução ou recomendação por existir.

---

# 2. Novas estruturas de banco

## `semantic_observations`

Staging persistente e auditável entre Evidence e Domain.

Estados:

- `open`
- `reconciled`
- `review_required`
- `no_domain_object`
- `dismissed`
- `superseded`

Ações de resolução:

- `attach_occurrence`
- `create_instance`
- `review_required`
- `no_domain_object`
- `insufficient_evidence`

## `project_context_elements`

Primeira separação explícita entre **Briefing Context** e Requirements.

Tipos iniciais incluem:

- objective
- audience_context
- business_context
- brand_context
- communication_problem
- geography
- deadline_context
- success_criterion
- assumption
- background

## `project_requirement_constraints`

Filho estruturado de `project_requirements` para preservar semântica quantitativa e scope.

Exemplos esperados no Golden:

- budget = `400000 BRL`, scope de projeto;
- audience = `6000–8000 people`, scope de evento.

**Regra importante:** um valor de budget não vira automaticamente `envelope`, `<=` ou `=`. Se a linguagem da Evidence não prova o operador, a NAVE registra `operator = unspecified`.

## `project_solution_occurrences`

A tabela existente é preservada e o vocabulário é ampliado.

Novas fases/papéis suportam explicitamente:

- `post_event`
- `feedback`
- `manual`
- `budget_reference`
- `result`
- `feedback_context`

Não foi criada uma segunda tabela de occurrences.

## `intelligence_reviews`

A infraestrutura existente passa a aceitar também:

`object_type = semantic_observation`

Não foi criada infraestrutura paralela de Human Review.

## `entity_outcomes`

Recebe somente a coluna aditiva:

`source_observation_id`

O Truth Gate da V28.7.1D **não é substituído nem redesenhado**.

---

# 3. Política de identidade da V28.7.2A

A política do antigo Graph V28.6 **não é reutilizada como autoridade de Project Domain Identity**.

### Permitido automaticamente

Uma nova observation pode ser anexada como occurrence a **uma única Project Solution Instance existente** quando o match é suficientemente inequívoco.

Exemplos Golden esperados:

- `Jogo da Memória` → `Jogo da memória`
- `Mascote Chambinho (Chambão)` → `Mascote em Tamanho Real`
- `Oficina de Origami` → `Oficina Origami de Coração`
- `Tatuagem` → `Tatuagens Temporárias`

### Nova identity

Pode ser criada quando:

- não há Project Solution Instance plausível; e
- existe Evidence qualificada de proposal **ou** resultado explícito de execução suficientemente confiável.

No Golden, os quatro gaps atuais devem ser candidatos naturais:

- Amarelinha
- Pescaria
- Distribuição de Produtos
- Folhas para colorir

### Nunca automático

**Duas Project Solution Instances já existentes nunca são auto-merged.**

O caso de controle permanece:

`Pelúcia ↔ Chaveiro`

A V28.7.2A deve manter as duas identities e o sinal de revisão. Merge/split exige resolução posterior.

### `NO_DOMAIN_OBJECT`

Materiais/logística de relatório não viram automaticamente Solution Domain.

Casos de controle:

- Polpas
- Pouchs
- Garrafinhas
- Petit Morango
- Petit Banana e Maçã
- Bola de sabão

Eles podem existir como observations, mas **não podem ser promovidos a Project Solution Instance só porque aparecem no pós-evento**.

---

# 4. Execution Lifecycle

Este é o principal salto funcional da 7.2A.

Antes, a execução do Golden sobrevivia como `memory_item_outcomes` sem provenance e foi corretamente isolada pela V28.7.1D.

Agora o caminho esperado é:

```text
post-event Evidence Unit
        ↓
Semantic Observation com status explícito
        ↓
execution occurrence
        ↓
entity_outcome execution_status
        ↓
Truth Gate
        ↓
current execution truth
```

A NAVE **não conclui `executed` apenas porque a fonte é pós-evento**.

Somente status explícitos normalizados podem materializar execution outcomes:

- executed
- partial
- not_executed
- planned

`not_executed` nunca é convertido em `executed`.

---

# 5. File Analyst e Graph V28.6

Nesta primeira 7.2A, **não substituir**:

- `file_analyst.py`
- `intelligence_graph_db.py`
- `entity_resolution.py`
- `cross_source_linker.py`

Isso é deliberado.

A V28.7.2A consome `entity_mentions` já produzidas pelo File Analyst apenas como **sinais locais de extração** quando:

`mention_role = file_analyst_entity`

A identity antiga da `knowledge_entity` criada pelo File Analyst **não é adotada como Domain Identity**.

O novo Reconciliation Kernel volta à Evidence Unit e resolve a identidade do Project Domain separadamente.

Menções antigas geradas por Cross-Source/V28.6 não alimentam o novo reconciler.

**Graph V28.6 continua congelado.**

---

# 6. Truth Gate permanece intacto

A migration da 7.2A:

- não substitui `entity_outcome_truth_status`;
- não substitui `entity_current_outcomes`;
- não promove `legacy_unverified`;
- não altera as regras `execution ≠ approval`;
- não altera `direct ≠ won`;
- não cria `domain_primary`.

Novos outcomes evidence-led só chegam ao estado projetado se passarem pelo Truth Gate já aprovado na 7.1D.

---

# 7. Arquivos desta entrega

## GitHub — ADICIONAR

- `project_domain_identity.py`
- `project_semantic_observations.py`
- `project_domain_reconciliation.py`
- `tests/test_v28_7_2a_identity_policy.py`
- `tests/test_v28_7_2a_reconciliation_plan.py`
- `tests/test_v28_7_2a_quantitative_constraints.py`
- `tests/test_v28_7_2a_semantic_observations.py`
- `tests/test_v28_7_2a_sql_contract.py`
- `tests/test_v28_7_2a_orchestration.py`

## GitHub — SUBSTITUIR

- `project_intelligence_pipeline.py`
- `pages/14_Importar_Projeto.py`
- `tests/test_v28_7_1d_orchestration_freeze.py`
- `tests/test_v28_7_1b_orchestration_gate.py`

## NÃO SUBSTITUIR nesta versão

- `project_domain_normalization.py`
- `project_domain_truth_audit.py`
- `file_analyst.py`
- `intelligence_graph_db.py`
- `entity_resolution.py`
- `cross_source_linker.py`
- `project_batch_ingestion.py`
- `project_report_extractor.py`

A V28.7.1D/D2 instalada permanece como baseline de compatibilidade e Truth.

---

# 8. SQL

## SIM — precisa executar SQL

No **Supabase → SQL Editor → New query**, execute integralmente:

`NAVE_V28_7_2A_RECONCILIATION_KERNEL.sql`

O SQL é aditivo, transacional e mantém `legacy_shadow`.

Ele:

- cria as três novas estruturas semânticas;
- amplia occurrence vocabulary;
- permite review de semantic observation;
- adiciona lineage de outcome para observation;
- cria debugger/status views;
- cria o RPC atômico `apply_project_domain_reconciliation_v2872a`;
- não faz backfill global;
- não executa cutover;
- não altera o Truth Gate.

Se houver qualquer erro, **não prossiga para a ação de reconciliação**. Envie o erro integral.

---

# 9. Ordem exata de deploy

1. **Supabase:** execute `NAVE_V28_7_2A_RECONCILIATION_KERNEL.sql`.
2. **GitHub:** adicione/substitua somente os arquivos listados neste guia.
3. **Reboot do Streamlit: SIM.**
4. **Não reprocessar os quatro masters do Chambinho.**
5. Abra o mesmo projeto **Festivalzinho Chambinho** na área de correção de projeto antigo.
6. Clique uma única vez em:

   **`Reconciliar domínio semântico · V28.7.2A`**

7. Abra os painéis de Truth/Reconciliation/Coverage & Identity.
8. Execute no Supabase, somente depois da ação:

   `NAVE_V28_7_2A_VERIFY_GOLDEN_CHAMBINHO.sql`

9. Exporte o resultado em CSV e envie junto com os prints do painel.

---

# 10. Golden Chambinho — resultado semântico esperado

Os números abaixo são consequência esperada, **não o critério de aprovação isolado**.

### Solutions

Os quatro gaps atuais devem deixar de ser apenas findings e virar identities/occurrences evidence-led quando a Evidence sustentar:

- Amarelinha
- Pescaria
- Distribuição de Produtos
- Folhas para colorir

Se exatamente essas quatro forem criadas, o inventário tende a sair de 15 para algo próximo de 19. **19 não é gate.**

### Execution

O conjunto principal comprovado pelo pós-evento deve produzir **current execution truth evidence-backed** para:

- Amarelinha
- Jogo da memória
- Pescaria
- Distribuição de Produtos
- Mascote em Tamanho Real
- Tatuagens Temporárias
- Folhas para colorir
- Oficina Origami de Coração

O SQL de verificação valida o conjunto pelo nome/identidade, não apenas pelo contador `8`.

### Anti-pollution

Não podem surgir como Project Solution Instances apenas por presença logística no relatório:

- Polpas
- Pouchs
- Garrafinhas
- Petit Morango
- Petit Banana e Maçã
- Bola de sabão

### Identity

`Pelúcia` e `Chaveiro` devem permanecer identities separadas nesta etapa e continuar com sinal explícito de revisão.

### Requirements quantitativos

- budget: `400000 BRL`, com scope de projeto;
- operador: somente o que a Evidence realmente sustentar; `unspecified` é válido quando não há linguagem comparativa explícita;
- audience: range `6000–8000`, `people`, scope de evento;
- jamais colapsar `6–8 mil` em `8000`.

### Context

Devem existir elementos evidence-backed para pelo menos:

- objective;
- audience_context.

### Regressões obrigatórias

- financeiro continua `54` linhas;
- `54` Evidence Units financeiras distintas;
- total continua `R$ 554.310,85`;
- `process_type = direct` continua current/verified;
- `commercial_result = not_applicable` continua current/verified;
- nenhum `legacy_unverified` vira current;
- Graph V28.6 continua sem rebuild;
- migration continua `legacy_shadow`.

---

# 11. Debugger novo

O painel passa a expor, entre outros:

- Observações
- Open
- Reconciliadas
- Review required
- No-domain
- Soluções
- **Cobertura evidence-led**
- Soluções reconciliadas por Evidence
- Novas evidence-led
- Execuções com Evidence
- Execution truth verified
- Constraints
- Context elements
- Occurrences aplicadas
- Outcomes de execução
- Outcomes de proposta

**“Cobertura evidence-led” é somente um proxy de cobertura da reconciliação atual. Não é Legacy Independence Ratio e não autoriza cutover.**

---

# 12. Testes locais desta entrega

Suíte focada V28.7.2A + regressões D/D2 + orchestration gate:

**56 passed · 1 skipped**

Também foi executada separadamente a suíte histórica `test_v28_7_1_domain_integrity_provenance.py`:

- **14 passed**;
- **6 falharam exclusivamente por `FileNotFoundError`**, porque o ZIP-base recebido não contém o antigo arquivo fixture `NAVE_V28_7_1B_DOMAIN_INTEGRITY_SQL_COMPAT.sql`.

Essas seis falhas não executaram lógica runtime da V28.7.2A.

A suíte global do repositório não é utilizável neste ambiente local como gate completo porque a coleta de módulos antigos depende de pacotes de runtime que não estão instalados aqui, incluindo `streamlit` e `google.genai`.

Além disso, o SQL da 7.2A passou por checagens estáticas adicionais:

- INSERT column/value counts consistentes;
- sem `DROP TABLE`;
- não substitui `entity_current_outcomes`;
- RPC atômico em `SECURITY DEFINER`;
- execução do RPC restrita a `service_role/postgres`;
- novas tabelas sem `DELETE` para `service_role`;
- migration mode permanece `legacy_shadow`.

---

# 13. O que NÃO aprovar depois do deploy

Mesmo que o deploy termine sem erro e os painéis fiquem verdes:

**não declarar V28.7.2A aprovada automaticamente.**

Precisamos auditar o CSV/prints e responder semanticamente:

- os quatro gaps viraram as coisas certas?
- as oito execuções são exatamente as oito comprovadas?
- logística ficou fora de Solution Domain?
- Pelúcia/Chaveiro não sofreram merge silencioso?
- ranges/scopes foram preservados?
- Truth/financeiro/commercial não regrediram?
- repeated run é idempotente?

Somente depois dessa auditoria a 7.2A pode ser aprovada e a V28.7.2B — Strategy / Creative / Experience — pode ser considerada.

---

## Reboot

**SIM.**

## SQL

**SIM.**

## Reprocessar masters

**NÃO.**

## Cutover / `domain_primary`

**NÃO.**
