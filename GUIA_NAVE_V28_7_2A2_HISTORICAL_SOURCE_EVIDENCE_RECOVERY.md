# NAVE by VOE · V28.7.2A2 — Historical Source Evidence Recovery

## Por que esta versão existe

O Golden JOVI provou que o problema não estava originalmente no parser de Creative/Journey.

O diagnóstico mostrou:

- `project_files` contém o briefing e a proposta, ambos com SHA-256 e master preservado;
- o briefing possui `source_asset` e 195 Evidence Units current;
- a proposta `PDF_LANCAMENTO_JOVI_X300_30.06.pdf` possui SHA-256 no `project_files`, mas **zero `source_asset`**;
- por consequência a proposta possui zero Evidence Units e zero File Analyst mentions;
- V28.7.2A não consegue ligar as occurrences legadas da proposta a Evidence;
- V28.7.2B consegue ler apenas Strategy do briefing e não consegue enxergar Creative Platform / Experience / Journey da proposta.

Isso é um problema de **substrato histórico da Intelligence Foundation**. O projeto foi importado em uma fase na qual o master operacional ficou válido, mas o File Analyst dual-write da proposta não existe no Foundation.

## Decisão arquitetural

A correção pertence à V28.7.2A, antes de Domain Normalization / Reconciliation / Core Semantics.

Novo fluxo no refresh:

`project_files master`  
→ verifica se Source Asset + Evidence current existem  
→ se faltarem, baixa o MESMO master já preservado  
→ valida SHA-256  
→ executa o mesmo `File Analyst dual-write` usado em imports novos  
→ Source Asset + Evidence + mentions / claims / contexts  
→ Domain Normalization  
→ V28.7.2A Reconciliation  
→ Audits  
→ V28.7.2B Core Semantics

Não existe conversão de JSON legado em Evidence.

## Novo módulo

`project_source_evidence_backfill.py`

Ele procura somente arquivos primários current com hash:

- briefing_original
- proposal_presentation
- final_presentation
- detailed_costs
- preliminary_budget
- feedback_approval
- post_event_report / post_execution_report / closure_report

Para cada master:

1. localiza `source_asset` pelo `content_sha256`;
2. garante o `source_asset_context` do projeto quando o asset já existe;
3. verifica se há Evidence Units current;
4. se Source Asset ou Evidence estiverem faltando, recupera o master de R2/Supabase legacy storage;
5. recalcula o SHA-256 e exige igualdade com `project_files.content_sha256`;
6. executa `dual_write_source_file(...)`;
7. relê o Foundation e informa quantos primários ainda estão sem Evidence.

## Segurança

- idempotente por SHA-256;
- não altera `project_files.content_sha256`;
- não cria Evidence a partir de memory_*;
- não deleta Source Asset / Evidence anterior;
- não reconstrói Graph V28.6;
- falha de backfill não apaga domínio já válido;
- o pipeline continua em `legacy_shadow`.

## UI

A página de Importar/Reprocessar ganha o expander:

`Source Evidence Recovery · V28.7.2A2`

Ele mostra:

- masters primários sem Source Asset/Evidence;
- recuperados;
- falhas;
- ainda ausentes;
- resultado por arquivo.

## Arquivos do GitHub

### Adicionar

- `project_source_evidence_backfill.py`
- `tests/test_v28_7_2a2_source_evidence_backfill.py`

### Substituir

- `project_intelligence_pipeline.py`
- `pages/14_Importar_Projeto.py`
- `tests/test_v28_7_2a_orchestration.py`
- `tests/test_v28_7_1d_orchestration_freeze.py`

## SQL

**NÃO.**

A Foundation necessária já está instalada.

## Reboot

**SIM.**

## Masters

**NÃO reenviar. NÃO usar “Reprocessar conteúdo com leitura especializada”.**

A A2 lê o master que já está preservado no storage apenas para preencher o Foundation ausente.

## Reteste JOVI

Depois do deploy/reboot:

1. abra `Lançamento Jovi X300`;
2. clique **uma vez** em `Reconciliar Core Semantic Domains · V28.7.2B`;
3. confira o novo expander `Source Evidence Recovery · V28.7.2A2`;
4. no caso diagnosticado esperamos a proposta PDF como `backfilled`, com Source Asset ID e Evidence Units > 0;
5. depois envie prints dos painéis;
6. rode novamente:
   - `NAVE_V28_7_2B_VERIFY_GOLDEN_JOVI.sql`
   - `NAVE_V28_7_2B4_DIAGNOSTICO_JOVI_SOURCE_BINDING_SUBSTRATE.sql`
7. exporte ambos os resultados como CSV.

## O que esperamos observar

A2 deve melhorar primeiro o substrato, não “forçar” os números finais:

- `proposal_source_asset_count`: 0 → 1;
- `proposal_current_evidence_count`: 0 → >0;
- proposal File Analyst mentions: 0 → >0 quando a análise semântica concluir;
- occurrences da proposta começam a receber Evidence;
- proposal outcomes evidence-backed podem começar a aparecer;
- V28.7.2B passa a ter acesso real ao PDF da proposta.

Só depois disso auditaremos:

- ON TOUR como Creative Platform;
- EVENT JOURNEY como Experience Architecture;
- PRE-EVENT / EVENT / POST-EVENT;
- Product Reveal / Activation Reveal;
- YouTube / Instagram / TikTok / Kwai como soluções distintas;
- precisão dos Strategy Elements do briefing.

## O que esta versão NÃO corrige deliberadamente

Os 13 requirements ainda sem Evidence não são automaticamente “amarrados” por nome.

O diagnóstico mostra que vários são fragments legados (`YouTube`, `Instagram`, `Stories`, `Filmmakers`, `JOVI X300 Ultra` etc.) e podem representar tanto falha de binding quanto fragmentação semântica ruim do domínio de Requirements. Fazer binding arbitrário agora violaria o fail-closed.

Primeiro recuperamos o Source/Evidence substrate faltante. Depois auditamos Requirements com a proposta efetivamente presente e decidimos se o problema é provenance binding ou Semantic Requirement Reconciliation.

## Validação local

- `py_compile`: PASS
- A2 + A/A1 + B/B1/B2/B3 + orchestration selecionados: **73 passed · 1 skipped**
- nenhum nome JOVI/Chambinho foi hardcoded no runtime da recuperação.

## Estado de arquitetura

- V28.7.2A/A1: aprovada no Chambinho;
- V28.7.2A2: shadow repair para generalização histórica;
- V28.7.2B: **ainda não aprovada**;
- Chambinho B: aprovado;
- JOVI B: bloqueado até Source/Evidence substrate passar;
- `migration_mode`: legacy_shadow;
- `domain_primary`: NÃO;
- Graph V28.6: congelado.
