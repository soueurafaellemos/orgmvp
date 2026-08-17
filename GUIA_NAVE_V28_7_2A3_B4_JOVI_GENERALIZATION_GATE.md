# NAVE by VOE · V28.7.2A3 + V28.7.2B4 — JOVI Generalization Gate

## Status

Hotfix coordenado de generalização revelado pelo Golden JOVI.

- **V28.7.2A2 Source Evidence Recovery: PASS**
- **V28.7.2B: ainda NÃO aprovada**
- Chambinho B permanece aprovado
- JOVI permanece em `legacy_shadow`

O objetivo deste patch não é maquiar o Golden. Ele corrige duas falhas independentes que o JOVI expôs:

1. **A3 — Proposal Activation Discovery:** a Evidence da proposta existe, mas o File Analyst histórico produziu zero `entity_mentions` para o PDF; por isso a A ainda não conseguia descobrir as quatro ativações de plataforma.
2. **B4 — Creative/Journey/Strategy Precision:** a B passou a ler a proposta, mas:
   - `On Tour` não foi materializado porque o layout-recovery pode quebrar uma frase nomeada que existe no texto flat da mesma página;
   - um `JOURNEY` usado como copy em Product Reveal virou uma segunda Experience Architecture;
   - isso deixou `ACTIVATION REVEAL` e vários Product Reveal observations abertos;
   - Strategy manteve quatro falsos objetos (`HIGHLIGHTS`, `INSIGHT` como territory, um item de audiência e um novo heading de diretrizes).

## Evidência do diagnóstico

Após A2:

- proposal Source Asset: **presente**
- proposal Evidence Units current: **106**
- occurrences: **41/41 com Evidence**
- File Analyst mentions na proposta: **0**
- A observations: **2**, ambas de feedback e ainda `open`
- platform solutions: **0**
- current outcomes: **0**
- Core B:
  - Strategy 11
  - Creative Platform 0
  - Experience Architectures 2
  - Journey Moments 5
  - Open Core observations 6

A proposta contém explicitamente páginas de ativação por plataforma, `On Tour`, `EVENT JOURNEY`, `PRODUCT REVEAL` e `ACTIVATION REVEAL`; portanto o problema não é documental.

---

# V28.7.2A3 — Proposal Activation Discovery

## Nova rota Evidence → Observation

A A3 adiciona um caminho independente de File Analyst para páginas de proposta com:

- heading curto e identificável;
- linguagem explícita de ativação/experiência/espaço;
- source role de proposal.

Exemplos de forma, não de nomes hardcoded:

`[LABEL] — [CONCEPT] ... This activation ...`

ou

`Ativação [LABEL]: ...`

Isso gera `solution_candidate` evidence-backed.

O runtime não conhece `YouTube`, `Instagram`, `TikTok`, `Kwai` nem `JOVI`.

No Golden, esperamos quatro identities novas e evidence-led, com duas occurrences quando uma mesma plataforma possui duas opções/páginas.

### Fail-closed

- briefing sozinho não usa essa regra para criar a Solution;
- páginas genéricas `EVENT`, `JOURNEY`, `OPTION`, etc. são rejeitadas;
- a Evidence Unit continua sendo a fonte da observation;
- `memory_items` não participa da descoberta.

---

# V28.7.2B4 — Creative/Journey/Strategy Precision

## 1. Dual semantic read da mesma Evidence

Para PDF histórico, a B já recupera layout/linhas.

Agora ela extrai sinais de:

- layout recuperado;
- **e também** `content_text` flat da mesma Evidence como fallback.

Isso é importante porque layout melhora headings, mas pode quebrar uma expressão nomeada em colunas/linhas.

A Evidence e o locator não mudam.

## 2. Creative Platform nomeada

Expressões explícitas da forma:

`“nome” idea`
`idea “nome”`

continuam source-explicit.

No JOVI, a página de Product Reveal deve permitir `On Tour` como Creative Platform / Big Idea sem qualquer regra por nome.

## 3. Experience Architecture

Um heading específico:

- `EVENT JOURNEY`
- `EXPERIENCE JOURNEY`
- `JORNADA DO EVENTO`

continua suficiente.

Um `JOURNEY` / `JORNADA` genérico só cria Architecture se a mesma Evidence trouxer pelo menos dois stages explícitos.

Isso impede copy como `AN INVITATION TO THE JOURNEY` de virar arquitetura.

## 4. Journey

Com somente uma Architecture válida, observations explícitas de:

- Product Reveal
- Activation Reveal

podem ser reconciliadas nela como associação evidence-synthesis quando estão em outra Evidence Unit.

Não é fact cross-page.

## 5. Strategy precision

- `HIGHLIGHTS` / `INSIGHT` não podem virar `territory` apenas porque o corpo usa a palavra “territory”.
- Territory por heading continua possível quando a fonte usa uma referência demonstrativa inequívoca, como `desse território`, ao lado de um único heading semântico.
- blocos adjacentes de `Alinhamento Estratégico` param ao entrar em `Público-alvo`;
- blocos de `Objetivos Estratégicos` param diante de um novo heading de `Diretrizes`.

---

# Repair B4

O banco já contém objetos errados da execução anterior.

`NAVE_V28_7_2A3_B4_JOVI_GENERALIZATION_REPAIR.sql`:

- resolve o Golden JOVI pelos masters;
- **não deleta nada**;
- invalida os falsos Strategy Elements;
- invalida a Experience Architecture genérica `JOURNEY`;
- invalida seus Journey Moments filhos;
- preserva Evidence/provenance;
- supersede relações tocadas por objetos invalidados;
- marca observations antigas como `superseded`.

Na execução seguinte, observations ainda válidas (ex.: Product Reveal) podem ser reconciliadas novamente sob a Architecture correta.

---

# Arquivos GitHub

## Substituir

- `project_semantic_observations.py`
- `project_core_semantic_extractor.py`
- `tests/test_v28_7_2a_semantic_observations.py`
- `tests/test_v28_7_2b_core_extractor.py`

## Não substituir

- `project_domain_reconciliation.py`
- `project_domain_identity.py`
- `project_core_semantic_domains.py`
- `project_semantic_relations.py`
- `project_intelligence_pipeline.py`
- `pages/14_Importar_Projeto.py`
- `file_analyst.py`
- `intelligence_graph_db.py`
- `cross_source_linker.py`

---

# SQL

**SIM — somente o repair B4.**

Não repetir:

- migration A;
- migration B;
- repair B2;
- SQL B3;
- A2 recovery.

---

# Ordem de implantação

1. Substituir os quatro arquivos no GitHub.
2. Reboot do Streamlit.
3. Executar **uma única vez**:
   `NAVE_V28_7_2A3_B4_JOVI_GENERALIZATION_REPAIR.sql`
4. Abrir `Lançamento Jovi X300`.
5. Clicar uma vez em:
   `Reconciliar Core Semantic Domains · V28.7.2B`
6. Enviar prints.
7. Rodar:
   `NAVE_V28_7_2A3_B4_VERIFY_GOLDEN_JOVI.sql`
8. Exportar CSV e enviar.

Não reprocessar masters.

---

# Resultado esperado — V28.7.2A

O resultado exato pode variar em contadores de observations por múltiplas páginas, mas semanticamente deve ocorrer:

- Source Evidence Recovery continua sem ausentes;
- 4 Project Solution Instances novas evidence-led para as quatro ativações de plataforma;
- as quatro permanecem identities distintas;
- 5 occurrences evidence-led esperadas no Golden (uma plataforma possui duas páginas/opções);
- proposal current truth evidence-backed para as quatro;
- as 41 occurrences legadas evidence-bound continuam preservadas;
- nenhum merge silencioso.

É esperado que `Current truth` deixe de ser zero.

Os 13 requirements sem Evidence **não são corrigidos neste patch**; continuam explicitamente em legacy_shadow para uma reconciliação semântica posterior de Requirements.

---

# Resultado esperado — V28.7.2B

## Strategy

Esperamos remover os falsos:

- `HIGHLIGHTS` como territory
- `INSIGHT` como territory
- item de audiência promovido por adjacency
- heading de Diretrizes promovido por adjacency

Permanecem os Strategy Elements explicitamente sustentados.

## Creative

- `On Tour` → Creative Platform / Big Idea
- `On Tour` → NÃO Solution

## Experience

- exatamente uma Architecture relevante: `EVENT JOURNEY`
- `JOURNEY` genérico → não ativo como Architecture

## Journey

Moments core:

- PRE-EVENT
- EVENT
- POST-EVENT
- PRODUCT REVEAL
- ACTIVATION REVEAL

Sem duplicação por arquitetura falsa.

## Solutions

As quatro ativações de plataforma devem existir separadamente.

---

# Regressões

- Graph V28.6 continua congelado.
- `migration_mode = legacy_shadow`.
- Truth Gate continua fail-closed.
- Financeiro JOVI 75/75 permanece.
- Nenhum legacy outcome sem provenance vira current.
- Chambinho não deve perder `NOSTALGIA` como territory; o teste de regressão cobre esse caso.

---

# Validação local

- `py_compile`: PASS
- A3 semantic observation tests + A reconciliation/identity: PASS
- B4 extractor/domain/relations/no-hardcode: PASS
- suíte focada executada: **48 passed**

Não há `JOVI`, `YouTube`, `Instagram`, `TikTok`, `Kwai`, `On Tour` ou nomes do Golden codificados nos módulos runtime.

---

# Cutover

NÃO.

A V28.7.2B só pode ser aprovada quando o JOVI passar os gates depois deste hotfix, sem regressão do Chambinho.
