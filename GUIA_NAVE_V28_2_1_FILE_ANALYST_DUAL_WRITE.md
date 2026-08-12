# NAVE by VOE · V28.2.1 — File Analyst v1 + Intelligence Dual-Write

## Objetivo

Esta entrega implementa o primeiro consumidor real da **NAVE Intelligence Foundation**.

A NAVE passa a analisar cada arquivo em duas camadas simultâneas:

1. **pipeline legado/workspace**, que continua funcionando como hoje;
2. **Intelligence Graph**, em paralelo, sem substituir o legado.

O arquivo volta a ser tratado como uma unidade profunda de inteligência: página, slide, parágrafo, linha de planilha, imagem e transcrição passam a existir como evidências auditáveis.

---

## Pré-requisito

A **NAVE Intelligence Foundation v1** da entrega 03A deve estar instalada no Supabase.

Se ainda não estiver, a V28.2.1 é **fail-open**: o workspace continua funcionando e o dual-write é simplesmente ignorado. Nenhum projeto é quebrado por ausência das novas tabelas.

---

## O que muda

### 1. File Analyst v1

Novo módulo `file_analyst.py`.

Para cada fonte, ele produz:

- papel documental resolvido;
- evidências granulares;
- entidades;
- claims;
- relações explícitas suportadas pela própria fonte;
- unknowns;
- contradições internas;
- confiança e provenance.

### 2. Evidence Units

A extração determinística cria evidências em diferentes escalas:

- PDF → página;
- DOCX → parágrafo/tabela;
- PPTX → slide;
- XLSX/XLSM → sheet/linha;
- imagem → unidade visual;
- texto → parágrafo.

Cada evidence unit recebe um locator estável e hash de conteúdo.

### 3. Planilhas financeiras

O File Analyst reutiliza o parser financeiro especializado da NAVE.

Ele grava no Graph:

- linhas financeiras como entidades;
- preço proposto por linha;
- quantidade;
- categorias de custo;
- total proposto.

**Não cria `actual_total` a partir de orçamento/proposta.**

### 4. Briefings

Mesmo quando Gemini não estiver disponível, uma camada conservadora já consegue materializar claims de alta confiança como:

- teto de budget explicitamente declarado;
- quantidade de convidados;
- comportamento/formato obrigatório por plataforma quando explicitamente escrito.

A regra é genérica e baseada em seção, não em nome de cliente/projeto.

### 5. Feedback multimodal

Quando a fonte é feedback e Gemini está disponível, o File Analyst reutiliza o extrator multimodal especializado para gerar:

- transcrição como Evidence Unit;
- decisão comercial;
- claims independentes por assunto;
- sentimento;
- approval status;
- motivo da decisão.

Quando a fonte é de cliente/marketing/procurement/branding, o dual-write também pode criar relações `validated_by` / `challenged_by` para as entidades avaliadas.

### 6. Dual-write

`project_bundle_materializer.py` agora chama o File Analyst após a materialização do workspace.

A sequência é:

**arquivo original → workspace legado → File Analyst → Intelligence Graph**

Se o File Analyst falhar:

**o workspace legado permanece válido.**

A falha aparece apenas como diagnóstico técnico.

### 7. Observabilidade

Cada análise gera `intelligence_runs` com:

- analyzer_type = `file_analyst`;
- versão do pipeline;
- prompt version;
- input/output signatures;
- status;
- latência;
- warnings;
- contagem de evidências, entidades, claims, relações e findings.

---

## Arquivos a adicionar

- `file_analyst.py`
- `intelligence_graph_db.py`
- `file_analyst_iq_adapter.py`
- `tests/test_file_analyst_v1.py`
- `tests/test_file_analyst_integration_v2821.py`
- `NAVE_IQ_FILE_ANALYST_V1_BASELINE.md`
- `GUIA_NAVE_V28_2_1_FILE_ANALYST_DUAL_WRITE.md`

## Arquivos a substituir

- `project_bundle_materializer.py`
- `project_batch_ingestion.py`
- `pages/14_Importar_Projeto.py`

---

## SQL

**NÃO há SQL novo nesta entrega.**

Porém, a `NAVE_INTELLIGENCE_FOUNDATION_V1.sql` da etapa anterior é pré-requisito para o dual-write persistir.

---

## Reboot

**SIM.**

Depois de substituir os arquivos:

**Manage app → Reboot app**

---

## Como validar no projeto JOVI

Não reenvie os arquivos.

Vá em:

**Importar projeto completo → Corrigir um projeto importado por uma versão anterior da V28 → Lançamento Jovi X300 → Reprocessar conteúdo com leitura especializada**

No diagnóstico arquivo por arquivo, a coluna `Criado no workspace` deve passar a exibir também contagens como:

- `intelligence_evidence`;
- `intelligence_entities`;
- `intelligence_claims`;
- `intelligence_relations`;
- `intelligence_findings`.

Essas contagens são paralelas às estruturas legadas.

---

## NAVE IQ — primeiro baseline real

O adapter `file_analyst_iq_adapter.py` conecta o File Analyst ao IQ Bench Runner da etapa 04.

Foi executado nesta entrega contra os quatro Golden fixtures reais do JOVI **sem Gemini disponível no ambiente local**.

Resultado:

- Source Understanding: **100%**
- Financial Intelligence: **93,3%**
- Golden financial total accuracy: **PASS**
- Forbidden inference count: **0**
- Entity Resolution: **50%**
- Claim Accuracy: **38,9%** na dimensão agregada / 57,1% de recall no Golden JOVI
- Relation Precision: **0%**
- Feedback Linking: **0%**
- Cross-source Reasoning: **0%**
- Overall NAVE IQ offline/determinístico: **49,8% — BLOCKED**

Isso é deliberadamente útil: o benchmark mostra exatamente o que esta camada ainda **não** resolve sozinha.

O File Analyst v1 não substitui o Project Analyst nem o futuro Entity Resolver. Ele cria evidência e conhecimento de fonte. O score bloqueado impede que tratemos esta fundação como “inteligência final” apenas porque ela já extrai muita coisa.

### Observação sobre claim precision

O primeiro run também revelou uma limitação do próprio benchmark: o File Analyst gera muitas linhas financeiras corretas, enquanto o Golden case rotula apenas um subconjunto de claims obrigatórios. Portanto, a métrica de precision bruta ainda penaliza claims adicionais não rotulados. Não vamos ajustar o pipeline para “jogar para o benchmark”; o IQ Bench deverá evoluir com conjuntos positivos/negativos mais completos.

---

## Testes

Regressão focada executada:

```text
24 passed
```

Inclui:

- V28.1.5 semantic materialization;
- V28.1.7.3 role recovery;
- V28.2.0 Intelligence Core;
- Golden JOVI existente;
- File Analyst v1;
- integração V28.2.1.

A suíte integral continua sem coletar neste container por dependências de runtime ausentes (`streamlit` e `google-genai`). O deploy real possui essas dependências conforme o log do Streamlit Cloud.

---

# Próximo passo recomendado

## 06 — Entity Resolution v1 + Cross-Source Linker

Agora teremos arquivos produzindo evidências e entidades em paralelo. Antes de fazer o Project Analyst V2 raciocinar sobre o Graph, precisamos garantir que:

- “Cinemateca” em proposta e “the Cinemateca” no feedback sejam a mesma entidade;
- “JOVI X300 Series ON TOUR” e “the concept” possam ser ligados com confiança;
- ativações de plataforma em briefing, proposta e feedback sejam resolvidas para a mesma instância de projeto;
- aliases, traduções, abreviações e referências indiretas não criem duplicatas;
- ambiguidades gerem `review_required`, não merge silencioso.

O próximo passo deve portanto construir **Entity Resolution + Cross-Source Linker**, plugado no IQ Bench, antes do Project Analyst V2.
