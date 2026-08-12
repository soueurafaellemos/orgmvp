# NAVE by VOE · V28.3.0 — Unified Intelligence + Decision Layer + Dossiê

## Objetivo desta versão

A V28.3.0 corrige uma falha arquitetural revelada pelo Golden Chambinho: a NAVE já podia ter evidências suficientes nos arquivos e no Intelligence Graph, mas cada aba ainda chegava a uma "verdade" diferente sobre o mesmo projeto.

Esta versão cria uma camada única de consolidação e faz o workspace, o diagnóstico, o Project Analyst e o novo Dossiê Inteligente consumirem o mesmo cérebro:

**Evidence Layer → Unified Project Truth → Consistency Engine → Project Analyst V2 → Decision Intelligence → Workspace + Dossiê PDF**

O foco passa a ser explicitamente o OURO da NAVE:

- Diagnóstico
- Resultados
- Aprendizados
- Recomendações
- Conexões descobertas pela NAVE

A base continua sendo o patrimônio que sustenta essas conclusões.

---

## Principais correções

### 1. Uma verdade consolidada do projeto

Novo `project_intelligence_unified.py` cria o Unified Project Snapshot. Ele reconcilia:

- situação comercial / estágio;
- evidência de execução;
- budget comprovado;
- briefing;
- proposta;
- custos;
- Intelligence Graph;
- relatório pós-evento;
- cobertura semântica das áreas do workspace.

Exemplo do Chambinho: se existe relatório pós-evento com evidência real, a inteligência consolidada não pode continuar tratando o projeto como mera proposta.

### 2. Consistency Engine

A NAVE passa a detectar explicitamente contradições internas, como:

- status legado "em proposta" com evidência pós-evento;
- relatório com dezenas de evidências no Graph, mas interface dizendo "aguardando leitura";
- Estratégia vazia apesar de haver páginas estratégicas;
- Cenografia vazia apesar de haver evidência cenográfica;
- budget explícito no Graph, mas vazio no briefing estruturado.

Esses casos deixam de ser interpretados como ausência de conteúdo e passam a ser tratados como **falha de consolidação da NAVE**.

### 3. False Empty Resolver

As áreas do workspace passam a ter três estados conceituais:

1. **Estruturado** — conteúdo consolidado disponível;
2. **Evidência encontrada, ainda não consolidada** — a NAVE sabe que o conteúdo existe e não pode exibir um falso vazio;
3. **Nenhuma evidência encontrada** — ausência real nas fontes disponíveis.

A aba Estratégia e a área de Cenografia já usam fallback do Unified Snapshot quando o legado estiver vazio.

### 4. Relatório pós-evento entra no pipeline automaticamente

Novo `project_intelligence_pipeline.py` fecha a inteligência ao final de uma importação ou reprocessamento.

Quando existe `post_execution_report` ou `closure_report` ainda sem análise estruturada, a NAVE tenta automaticamente:

- recuperar o master pelo NAVE Storage (R2-aware);
- analisar o relatório com o extrator pós-evento;
- salvar a análise;
- atualizar outcomes/status quando comprovado;
- rodar Cross-Source Linker;
- reconstruir o Unified Snapshot;
- criar links automáticos de briefing/custos;
- executar o Project Analyst semântico;
- persistir a inteligência consolidada.

Importação nova e reprocessamento agora convergem para o **mesmo finalizador de inteligência**.

### 5. Proposal × Execution deixa de depender apenas do legado

O Unified Snapshot busca correspondência entre itens apresentados e evidências pós-evento.

No Golden Chambinho, por exemplo, registros como Jogo da Memória, Amarelinha e Pescaria podem ser relacionados ao conteúdo posterior do relatório. Ausência de evidência continua não sendo tratada como prova de não execução.

### 6. Budget comprovado pode vir do Intelligence Graph

Se o parser legado não materializou o budget, mas existe claim de alta autoridade como `budget_max`, o workspace passa a usar a verdade consolidada.

No Chambinho, o Golden exige R$ 400.000 como referência do briefing.

### 7. Decision Intelligence — o OURO da NAVE

O diagnóstico passa a ter uma camada explícita com cinco saídas:

- **Diagnóstico** — o que aconteceu e o que significa;
- **Resultados** — o que está comprovado como execução, resultado ou pendência;
- **Aprendizados** — conhecimento reutilizável pela VOE;
- **Recomendações** — decisões melhores e específicas, não tarefas burocráticas genéricas;
- **Conexões descobertas** — conclusões que só aparecem ao cruzar duas ou mais fontes.

A camada determinística produz conclusões auditáveis mesmo antes da resposta semântica do Gemini. O Project Analyst V2 aprofunda a leitura quando a IA está disponível.

### 8. Project Analyst V2 recebe Graph + Unified Snapshot

O pacote de evidências do Project Analyst agora inclui:

- requisitos;
- soluções;
- custos;
- feedbacks;
- links existentes;
- outcomes;
- evidence units do Graph;
- claims do Graph;
- relations do Graph;
- Unified Project Snapshot.

O prompt passa a exigir Diagnóstico, Resultados, Conexões, Aprendizados e Recomendações, evitando recomendações rasas como simplesmente "revisar planilha" quando a própria NAVE pode fazer a análise.

### 9. Novo Dossiê Inteligente NAVE — PDF

O workspace ganha o botão:

**↓ Baixar Dossiê Inteligente — PDF**

O PDF **não é uma impressão das abas**. Ele é uma segunda projeção do mesmo Unified Snapshot consumido pela interface.

A primeira versão do dossiê contém:

- resumo executivo;
- inteligência financeira;
- diagnóstico;
- resultados;
- conexões descobertas;
- aprendizados;
- recomendações;
- repertório / benchmarks / pesquisas disponíveis no snapshot;
- evidências consolidadas de estratégia;
- riscos, conflitos e incertezas;
- apêndice de fontes e provenance;
- snapshot/version signature.

FATO, INFERÊNCIA, APRENDIZADO, RECOMENDAÇÃO e CONTRADIÇÃO aparecem diferenciados no documento.

Quando não há pesquisa transversal ou benchmark histórico disponível, o dossiê informa isso explicitamente em vez de inventar repertório.

### 10. Central de arquivos — correção preventiva de `file_role`

No reprocessamento, `file_role` passa a ser resolvido antes da sincronização com `project_files`, evitando repetir o aviso:

`null value in column "file_role" of relation "project_files"`

### 11. NAVE IQ Bench v1.1

O Golden Chambinho passa a medir também:

- verdade consolidada do projeto;
- false-empty rate;
- execução ligada à proposta;
- cobertura da Decision Intelligence.

Novos gates conceituais:

- `false_empty_count_max = 0`
- `unified_truth_accuracy_min = 1.0`

A versão não deve ser considerada mais inteligente apenas porque uma aba ficou mais bonita.

---

## Arquivos do patch

Substituir/adicionar exatamente estes arquivos no GitHub:

- `project_intelligence_unified.py` **NOVO**
- `project_intelligence_pipeline.py` **NOVO**
- `project_intelligence_report.py` **NOVO**
- `project_workspace_db.py`
- `project_workspace_intelligence.py`
- `project_workspace_ui.py`
- `project_analyst.py`
- `project_batch_ingestion.py`
- `project_bundle_materializer.py`
- `pages/14_Importar_Projeto.py`
- `iq_bench_runner.py`
- `evals/suite.yaml`
- `evals/cases/golden_chambinho_festivalzinho_2026_full_cycle.yaml`
- `evals/RESPONSE_CONTRACT.md`
- `tests/test_v28_3_0_unified_intelligence.py` **NOVO**
- `tests/test_v28_3_0_pipeline.py` **NOVO**
- `tests/test_iq_bench_runner_v1.py`
- `tests/test_file_analyst_integration_v2821.py`

---

## SQL

**NÃO.**

A V28.3.0 usa as tabelas do Intelligence Foundation já instaladas. Não execute SQL novo para esta entrega.

---

## Reboot

**SIM.**

Depois de subir os arquivos:

**Streamlit → Manage app → Reboot app**

---

## Como testar o Chambinho já importado

**Não reenvie os quatro arquivos.**

Depois do reboot:

1. Abra **Importar projeto completo**.
2. Expanda **Corrigir um projeto importado por uma versão anterior da V28**.
3. Selecione **Festivalzinho Chambinho**.
4. Marque a confirmação.
5. Clique em **Reprocessar conteúdo com leitura especializada**.
6. Aguarde a finalização completa.
7. Abra o workspace.

O reprocessamento preserva os masters no R2 e refaz somente a materialização automática/inteligência.

---

## Critérios de aceite no Golden Chambinho

Depois do reprocessamento, observar principalmente:

- situação tratada de forma coerente como **Executada / Projeto direto** quando o relatório comprovar execução;
- **Budget do briefing = R$ 400.000** na verdade consolidada;
- Estratégia não pode aparecer como ausência real se existem evidências estratégicas na proposta;
- Cenografia não pode aparecer como ausência real se existem evidências cenográficas;
- pós-evento não deve permanecer simplesmente "aguardando leitura" quando sua análise já ocorreu;
- Proposal × Execution deve começar a vincular itens apresentados a evidências posteriores;
- 8 mil deve permanecer identificado como público do **evento/festival**, não como visitação automática da ativação Chambinho;
- After Movie deve permanecer **pendente** enquanto a fonte disser `AGUARDANDO`;
- inconsistência das tatuagens deve ser sinalizada como qualidade de dado, não corrigida por inferência;
- Diagnóstico / Resultados / Aprendizados / Recomendações / Conexões devem ter conteúdo analítico;
- o botão **Baixar Dossiê Inteligente — PDF** deve gerar documento válido.

---

## O que esta versão ainda NÃO promete resolver completamente

A V28.3.0 é a primeira camada de verdade consolidada e Decision Intelligence. Ela **não declara concluídos** ainda:

- todos os 54 vínculos custo ↔ solução do Chambinho;
- entity resolution perfeito de toda a base;
- benchmarks transversais profundos entre muitos projetos;
- retrieval híbrido da base inteira;
- recomendador aprendido por outcomes históricos;
- migração do legado inteiro para o Intelligence Graph.

Esses componentes continuam no roadmap do NAVE Intelligence Core. A diferença é que, a partir desta versão, eles passam a alimentar uma única verdade e o mesmo motor de decisão, em vez de criar novas ilhas.

---

## Validação realizada

Validação focada local:

**47 testes passando** nos módulos de:

- Unified Intelligence V28.3;
- pipeline de relatório/finalização;
- Entity Resolution;
- Cross-Source Linker;
- Golden Chambinho;
- Golden JOVI;
- File Analyst;
- Intelligence Core;
- IQ Bench Runner.

O PDF programático do Dossiê foi gerado, renderizado em PNG e inspecionado visualmente em 4 páginas, sem clipping/overlap no teste sintético.

A coleta da suíte integral do repositório continua bloqueada neste container por dependências de runtime não instaladas localmente (`streamlit` e `google-genai`). Foram coletados 149 testes antes de 5 erros de importação por ambiente. Isso **não** foi contado como suíte integral aprovada.

---

## Norte arquitetural preservado

A V28.3.0 segue a regra:

> A base é o patrimônio. Diagnóstico, Resultados, Aprendizados, Recomendações e Conexões descobertas são o valor competitivo entregue pela NAVE.

E acrescenta outra regra operacional:

> Workspace e Dossiê Inteligente precisam ser duas projeções do MESMO cérebro. Se chegarem a verdades diferentes, a NAVE está errada.
