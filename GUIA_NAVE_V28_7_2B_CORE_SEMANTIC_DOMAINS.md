# NAVE by VOE — V28.7.2B

## Strategy, Creative Platform & Experience Architecture — SHADOW ROLLOUT

**Status desta entrega:** pronta para implantação e validação em shadow. **Ainda não aprovada para cutover.**

A V28.7.2B amplia o kernel evidence-led aprovado na V28.7.2A/A1 para representar três camadas cognitivas que não podem continuar misturadas com `Project Solution Instance` nem com a síntese editorial do Project Analyst:

1. **Strategy Domain** — por que / segundo qual lógica o projeto responde ao contexto;
2. **Creative Platform / Concept System** — qual ideia transforma estratégia em linguagem criativa;
3. **Experience Architecture / Journey** — como a ideia se organiza no tempo e nos momentos da experiência.

Fluxo desta versão:

```text
Evidence Unit
   ↓
Semantic Observation
   ↓
Core Semantic Reconciliation
   ↓
Strategy / Creative / Experience / Journey
   ↓
knowledge_relations + relation_evidence
```

O Graph V28.6 continua congelado. O Project Analyst antigo não é usado para criar verdade factual desta camada.

---

## 1. Regra central de verdade semântica

A V28.7.2B separa explicitamente:

- `source_explicit` — declarado pela própria fonte;
- `evidence_synthesis` — síntese/associação sustentada por evidências, mas não literalmente declarada daquela forma;
- `human_confirmed` — confirmado por revisão humana auditável;
- `analyst_inference` — leitura analítica; **não vira Domain Truth**.

Na primeira shadow release, o extrator automático só materializa **objetos `source_explicit`**. Associações cross-evidence conservadoras podem existir como `knowledge_relations.relation_kind='inference'`, sempre com `relation_evidence`.

A view `project_core_semantic_truth_status` diferencia:

- `verified_explicit`;
- `verified_synthesis`;
- `human_confirmed`;
- `review_required`;
- `unsupported`.

---

## 2. Semântica preservada da fonte

A B não renomeia categorias apenas para encaixar o Golden.

Exemplo importante do Chambinho:

- `PONTOS DE PARTIDA` continua semanticamente como `strategic_principle`;
- somente uma fonte que diga `PILARES` gera `strategy_type='pillar'`;
- `NOSTALGIA`, quando a própria fonte fala em se apropriar daquele **território**, pode ser `territory`;
- `A Casa Chambinho mais nostálgica de todas`, apresentada como `POINT OF VIEW`, pertence à Creative Platform/POV, não à Strategy nem a Solutions.

Isso evita transformar uma síntese anterior da NAVE em “fato da fonte”.

---

## 3. Estruturas criadas

### `project_strategy_elements`
Tipos iniciais:

- `challenge`
- `tension`
- `insight`
- `opportunity`
- `territory`
- `strategic_direction`
- `pillar`
- `brand_role`
- `audience_role`
- `experience_role`
- `strategic_principle`
- `materialization_criterion`

### `project_creative_platforms`
Identidade de uma rota/plataforma/conceito criativo.

### `project_creative_elements`
Elementos pertencentes à plataforma:

- `big_idea`
- `proposition`
- `pov`
- `naming`
- `narrative`
- `creative_territory`
- `message`
- `message_hierarchy`
- `visual_system`
- `proprietary_code`
- `materialization_rule`

Uma `creative_territory` ou mensagem **não cria automaticamente uma plataforma paralela**. Precisa haver plataforma criativa inequívoca para associação; quando a associação é apenas same-source/unique-platform, ela é registrada como inferência, não como fato.

### `project_experience_architectures`
Arquitetura/orquestração explícita da experiência.

### `project_journey_moments`
Stages/moments/touchpoints pertencentes à arquitetura. Journey não é Solution.

---

## 4. `semantic_observations` ampliada

A tabela staging da 7.2A é reutilizada e recebe:

- `domain_hint`
- `semantic_role`
- `assertion_mode`

Novos `observation_kind`:

- `strategy_signal`
- `creative_signal`
- `experience_signal`
- `journey_signal`
- `relation_signal`

Não há segunda tabela de candidatos.

---

## 5. Relações

A B reutiliza `knowledge_relations` + `relation_evidence`.

Vocabulário ampliado:

- `informs`
- `supports`
- `contradicts`
- `expressed_by`
- `orchestrated_as`
- `governs`
- `contains`

O SQL **preserva e amplia** tipos de origem/destino já existentes na ontologia; não substitui silenciosamente semântica antiga.

Regra de autoridade:

- mesma Evidence Unit → relação pode ser `fact`;
- associação entre Evidence Units distintas só ocorre em casos conservadores e fica `relation_kind='inference'`;
- proximidade no mesmo projeto, sozinha, não cria relação crítica;
- múltiplas rotas criativas bloqueiam associação por proximidade;
- Journey → Solution exige occurrence da solution na mesma Evidence Unit.

---

## 6. Arquivos do patch

### ADICIONAR

- `project_core_semantic_extractor.py`
- `project_core_semantic_domains.py`
- `project_semantic_relations.py`
- `tests/test_v28_7_2b_core_extractor.py`
- `tests/test_v28_7_2b_domain_plan.py`
- `tests/test_v28_7_2b_relations.py`
- `tests/test_v28_7_2b_sql_contract.py`
- `tests/test_v28_7_2b_no_golden_hardcode.py`

### SUBSTITUIR

- `project_intelligence_pipeline.py`
- `pages/14_Importar_Projeto.py`
- `tests/test_v28_7_1d_orchestration_freeze.py`
- `tests/test_v28_7_1b_orchestration_gate.py`
- `tests/test_v28_7_2a_orchestration.py`

### NÃO ALTERAR NESTA ENTREGA

- `project_domain_normalization.py`
- `project_domain_reconciliation.py`
- `project_domain_identity.py`
- `project_domain_truth_audit.py`
- `project_semantic_observations.py`
- `file_analyst.py`
- `intelligence_graph_db.py`
- `cross_source_linker.py`
- `entity_resolution.py`
- `project_analyst.py`
- camada financeira
- V28.7.1D Truth Gate SQL/views

---

## 7. SQL

### Executar

`NAVE_V28_7_2B_CORE_SEMANTIC_DOMAINS.sql`

Ele:

- valida pré-requisitos A/D/Foundation;
- cria os cinco domínios semânticos;
- amplia Semantic Observations;
- amplia ontologia relacional;
- cria Semantic Truth/Status views;
- cria o writer transacional `apply_project_core_semantics_v2872b`;
- mantém `migration_mode='legacy_shadow'`;
- avança somente `domain_schema_version` para `28.7.2b`.

### Não faz

- não altera `entity_current_outcomes`;
- não altera `entity_outcome_truth_status`;
- não reconstrói Graph V28.6;
- não executa Cross-Source Linker V28.6;
- não promove `domain_primary`;
- não executa Project Analyst para fabricar Strategy/Creative/Journey.

---

## 8. Ordem de implantação

1. No Supabase SQL Editor, execute **somente** `NAVE_V28_7_2B_CORE_SEMANTIC_DOMAINS.sql`.
2. Se terminar sem erro, suba os arquivos do patch para as posições correspondentes no GitHub.
3. Faça **reboot do Streamlit**.
4. **Não reprocessar os masters.**
5. Validar primeiro Chambinho.
6. Validar depois JOVI.
7. Não promover cutover após os prints; executar os SQLs read-only e auditar os CSVs.

---

## 9. Golden Chambinho — teste

No mesmo projeto canônico Festivalzinho Chambinho:

1. abrir `Corrigir um projeto importado por uma versão anterior da V28`;
2. selecionar o projeto;
3. confirmar;
4. clicar uma vez em **`Reconciliar Core Semantic Domains · V28.7.2B`**;
5. enviar print completo do painel `Core Semantic Domains`;
6. executar `NAVE_V28_7_2B_VERIFY_GOLDEN_CHAMBINHO.sql`;
7. exportar uma linha CSV e enviar.

Gates principais:

- A continua intacta: 19 solutions, 8 executions, Coverage 0;
- `NOSTALGIA` como `territory` explicitamente grounded;
- `MEMÓRIA AFETIVA`, `CONEXÃO`, `PRESENÇA E ATENÇÃO` como **`strategic_principle`** porque a fonte as apresenta como `PONTOS DE PARTIDA`;
- plataforma/POV `Casa ... mais nostálgica ...` em Creative, não Strategy/Solution;
- nenhum Journey inventado sem Evidence explícita;
- relações Strategy → Creative tipadas e grounded;
- financeiro permanece 54 / 54 / R$ 554.310,85;
- Graph V28.6 permanece congelado.

---

## 10. Golden JOVI — teste

No projeto JOVI X300 já importado:

1. selecionar o projeto;
2. clicar uma vez em **`Reconciliar Core Semantic Domains · V28.7.2B`**;
3. enviar print completo dos painéis A + B;
4. executar `NAVE_V28_7_2B_VERIFY_GOLDEN_JOVI.sql`;
5. exportar uma linha CSV e enviar.

O SQL resolve o projeto pelos **dois masters anexados (briefing + proposta)**, não por `project_name + LIMIT 1`.

Gates principais:

- challenge explícito;
- insight explícito;
- direcionamento estratégico evidence-backed;
- `ON TOUR` como Creative Platform/Big Idea, não Solution;
- `EVENT JOURNEY` como Experience Architecture, não Solution/Press Kit;
- PRE-EVENT / EVENT / POST-EVENT;
- Product Reveal;
- Activation Reveal;
- YouTube / Instagram / TikTok / Kwai continuam solutions distintas;
- relações de Journey possuem provenance;
- Analyst inference não é materializada como truth;
- Graph V28.6 permanece congelado.

A B **não valida ainda** feedback positivo do ON TOUR, perda comercial, críticas de venue/plataforma ou razões eliminatórias. Esses fatos pertencem à V28.7.2C — Decision/Feedback/Metric/Financial Semantics.

---

## 11. Testes locais

Validação desta entrega:

- compilação Python dos 5 arquivos runtime afetados: **PASS**;
- suíte focada B + regressões A/A1/D/D2/orchestration: **72 passed · 1 skipped**;
- uma execução mais ampla encontrou **8 testes históricos não executáveis** apenas porque o repositório-base fornecido não contém `NAVE_V28_7_1B_DOMAIN_INTEGRITY_SQL_COMPAT.sql`; não são falhas da B;
- scan de produção: nenhum nome de Golden (`Chambinho`, `JOVI`, `ON TOUR`) nos módulos Core da B;
- SQL: sem `DROP TABLE`, sem `domain_primary`, sem rebuild/call do Graph V28.6, sem substituição dos resolvers do Truth Gate;
- validação sintática local do SQL é estática: este ambiente não possui PostgreSQL/`psql`, portanto o deploy no Supabase continua sendo o teste final do SQL real.

---

## 12. Estado após deploy esperado

- V28.7.1D: permanece aprovada;
- V28.7.2A/A1: permanece aprovada;
- V28.7.2B: **shadow / em validação**;
- `legacy_shadow`: **SIM**;
- `domain_primary`: **NÃO**;
- Graph V28.6: **CONGELADO**;
- Graph V2: **NÃO**;
- Project Analyst editorial: **não promovido nesta rodada**;
- cutover geral: **NÃO**.

## Reboot

**SIM.**

## SQL

**SIM.**

## Reprocessar masters

**NÃO.**
