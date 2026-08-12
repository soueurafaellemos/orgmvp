# NAVE by VOE · V28.5.0 — Intelligence Productization

## Objetivo da versão

A V28.5.0 transforma a inteligência que a NAVE já consegue extrair em uma experiência de produto mais executiva, visual, objetiva e confiável.

Esta versão nasce diretamente da auditoria completa do Golden Project **Festivalzinho Chambinho** na V28.4.0. O problema principal já não é Storage nem preservação: os quatro masters voltaram a ser lidos, 54 linhas de custo foram recuperadas, 16 conteúdos da proposta foram materializados, 14 demandas do briefing foram estruturadas e o pós-evento passou a ser lido.

O gargalo agora é outro:

> a NAVE precisa mostrar primeiro o que concluiu, e não como o backend chegou até lá.

A V28.5.0 ataca quatro frentes ao mesmo tempo:

1. **Productização da inteligência** — menos auditoria/backend na interface principal; mais conclusão, decisão e contexto.
2. **Projection Guard** — análise mais ousada, mas afirmações mais conservadoras e sustentadas.
3. **UX visual e sem truncamento** — cards com wrap, menos tabelas cruas, menos repetição e recuperação de visuais de cenografia.
4. **Dossiê Inteligente v2 editorial** — conclusão antes de números; sem Graph, links legados, hashes ou TODOs do Project Analyst no corpo executivo.

---

## 1. Projection Guard — Unsupported Insight Rate = 0

A NAVE passa a bloquear da projeção executiva afirmações que ultrapassem a evidência disponível.

Sem KPI, participação específica, feedback explícito ou outra fonte equivalente, a NAVE não deve afirmar:

- “realizada com sucesso”;
- “alto engajamento”;
- “alto índice de participação”;
- “altamente eficaz”;
- “excelente aceitação”;
- “valor percebido superior”;
- “principal driver de interação/engajamento”;
- “92% de sobra/desperdício” quando os números de produzido, distribuído e saldo não reconciliam;
- que a agência “ignorou” ou “desconsiderou” uma restrição sem fonte que comprove intenção.

### Regra central

**Execução comprovada ≠ performance comprovada.**

A NAVE pode concluir que uma ativação foi executada quando existe evidência posterior. Só pode qualificar performance quando existe evidência específica para isso.

---

## 2. Público do evento não vira participante da ativação

A V28.5.0 endurece a proteção contra um erro observado no Chambinho:

**8.000 pessoas = público do Festivalzinho.**

Esse número não pode virar automaticamente:

- visitantes da Casa Chambinho;
- participantes das ativações;
- impactos da marca;
- denominador de custo por participante.

Mesmo quando uma claim antiga tiver sido rotulada como `project_attendees`, a Unified Truth do pós-evento prevalece quando comprova que o escopo real é `festival_event`.

Consequência prática: **R$ 69,29 por participante deixa de aparecer no Chambinho** enquanto não houver um denominador específico da ativação.

---

## 3. Financeiro — reconciliação antes de classificar estouro

A leitura financeira continua preservando:

- Budget do briefing: R$ 400.000,00;
- Total bruto da proposta: R$ 554.310,85;
- Diferença bruta: R$ 154.310,85;
- concentração por categoria e principais drivers.

Mas, quando houver evidência de **pagamento direto pelo cliente**, o Project Analyst e a camada determinística deixam de gerar automaticamente “Aderência financeira / proposta excedeu o budget”.

A linguagem correta passa a ser:

**Diferença bruta a reconciliar**

até que responsabilidades financeiras sejam separadas.

---

## 4. Briefing — sem `None`, sem tabela truncada, com resposta identificada

### Correções

- Se o parser estruturado do briefing não tiver `budget_amount`, a interface usa o budget comprovado da Unified Truth.
- A lista de demandas deixa de ser uma tabela comprimida e passa a ser uma grade de cards responsivos com texto completo.
- Cada card mostra:
  - tipo;
  - prioridade;
  - obrigatoriedade;
  - demanda completa;
  - leitura atual de aderência.
- Quando a demanda ainda está `not_assessed`, mas a Unified Truth encontrou correspondência na proposta, a interface mostra **Resposta identificada**.
- Quando não encontrou, mostra **Ainda sem evidência**.

Isso elimina o cenário em que a NAVE dizia saber que seis demandas tinham resposta, mas mostrava as 14 como “Não avaliada”.

---

## 5. Diagnóstico e recomendações — só inteligência de negócio no caminho principal

O bloco principal passa a priorizar:

- resumo executivo;
- diagnóstico;
- recomendações;
- conexões descobertas;
- leituras objetivas financeiras/estratégicas.

Ficam fora do fluxo executivo:

- `FACT` / `INFERENCE` como gramática dominante;
- “Projeto com evidência de execução” como insight;
- “links legados incompletos”;
- “Intelligence Graph contém…”;
- instruções como “Project Analyst deve avaliar…”;
- grandes matrizes e contagens de auditoria.

Esses elementos permanecem, quando úteis, em:

**Detalhes e auditoria do projeto**

e

**Saúde da leitura NAVE**

ambos recolhidos por padrão.

---

## 6. Estratégia — síntese primeiro, evidência depois

A estratégia continua apresentando:

- leitura estratégica consolidada;
- território;
- tensão;
- direção estratégica;
- conceito / POV;
- papel da experiência;
- aderência ao briefing;
- pilares.

Mas afirmações de performance sem sustentação são removidas pela Projection Guard.

As páginas/fontes que sustentam a leitura ficam em um expander secundário, em vez de competir com a síntese.

---

## 7. Cenografia — recuperação de sequências de renders

Este é um dos principais ajustes da V28.5.0.

O Chambinho mostrou um padrão recorrente de apresentações de live marketing:

1. um slide textual introduz o conceito espacial (“Casa”, “espaço”, “ambiente”);
2. em seguida vêm vários slides quase sem texto, compostos principalmente por renders;
3. o parser textual antigo tendia a manter esses slides em Estratégia.

A V28.5.0 cria uma heurística de **continuidade visual espacial**:

- reconhece contexto espacial no slide anterior;
- mantém o contexto para sequências image-heavy com pouco texto;
- encerra o contexto quando aparece uma nova seção forte, como ativações ou brindes;
- reclassifica esses visuais como cenografia para projeção;
- consegue usar inclusive páginas visuais já preservadas que estavam classificadas em outra seção.

### Efeito esperado no Chambinho

Em **Cenografia e ambientes**, a grande lista de DOCX/XLSM/PDF pages deve ser substituída por visuais da Casa Chambinho — fachada, vistas externas, internas e ambientação — sempre que os masters permitirem recuperar essas páginas.

A lista de filenames deixa de ser a experiência principal.

---

## 8. Ativações e Brindes — menos ruído de custo

A frase repetida em quase todos os cards:

> `Sem linha direta · R$ 17.880,00 em custos da seção ainda não rateados`

não é mais exibida por card.

### Nova regra

- custo não rateado da seção → aparece **uma única vez no topo**;
- custo específico confirmado/sugerido e maior que zero → pode aparecer no card;
- match sugerido com valor zero → não vira badge de `R$ 0,00`.

Isso reduz muito o ruído visual em Brindes e Ativações.

---

## 9. Comunicação — termos genéricos deixam de sequestrar evidências

Termos genéricos como `foto`, `vídeo` e `conteúdo` deixam de ser suficientes para classificar uma evidência como Comunicação.

Isso reduz casos como o slide do **Mascote em Tamanho Real** sendo projetado em Comunicação apenas porque sua descrição menciona “tirar fotos”.

Comunicação passa a exigir sinais mais específicos, como:

- comunicação;
- convite;
- save the date;
- social media;
- conteúdo digital;
- peça digital;
- e-mail marketing;
- sinalização;
- identidade visual;
- key visual.

---

## 10. Resultados e aprendizados — execução, performance e aprendizado separados

### A leitura do relatório agora diferencia

**O que o relatório comprova**

**Indicadores comprovados**

**Resultados por ativação ou entrega**

**Aprendizados explicitamente registrados na fonte**

**Aprendizados inferidos pela NAVE**

### Proteções

- `Participantes: 8000` vira **Público registrado no evento**;
- o card explica que isso não equivale a visitantes da ativação;
- resultados por ativação são cards em vez de schema cru `name / result / status / evidence`;
- provenance detalhada fica em `Ver fonte`;
- objetivos extraídos por versões antigas que misturavam “atingiu público-alvo” com público total do evento são projetados de forma conservadora;
- learnings inferidos pelo Project Analyst passam pela Projection Guard.

### Conflitos de quantidade

Quando produzido, distribuído e saldo não reconciliam, a NAVE registra **inconsistência de dados**.

Ela não calcula desperdício nem percentual de sobra até a validação.

---

## 11. Feedbacks

O comportamento correto fica explícito:

- relatório pós-evento **não é automaticamente feedback do cliente**;
- só entra em Feedbacks se contiver comentário, aprovação, crítica ou percepção explicitamente atribuível ao cliente;
- caso contrário, a tela informa que nenhum feedback explícito foi identificado e que o pós-evento está sendo tratado em Resultados e Aprendizados.

---

## 12. Dossiê Inteligente v2 — editorial, não backend

O PDF foi reestruturado para responder primeiro **“e daí?”**.

### Estrutura

1. Capa com lockup NAVE by VOE discreto;
2. **O projeto em 1 minuto**;
3. **Briefing x resposta da proposta**;
4. **Estratégia x materialização**;
5. **Inteligência financeira**;
6. **Resultados comprovados**;
7. **O que ainda não foi possível medir**;
8. **Aprendizados para a VOE**;
9. **Recomendações para próximos projetos**;
10. **Fontes consideradas**.

### Não entra mais no corpo executivo

- hashes;
- links internos;
- Intelligence Graph;
- links legados;
- `FACT / INFERENCE` repetidos;
- “Project Analyst deve avaliar…”;
- listas longas de páginas/slides;
- TODOs técnicos da NAVE.

As fontes aparecem apenas com nome e papel em linguagem humana.

---

## 13. IQ Bench — novos guardrails do Golden Chambinho

O Golden passa a proibir explicitamente:

- chamar a ativação de sucesso apenas por evidência de execução;
- afirmar alto engajamento, alta participação, excelente aceitação, valor percebido superior ou principal driver sem fonte específica;
- transformar a inconsistência de tatuagens em 92% de sobra/desperdício;
- expor linguagem de backend como parte da análise executiva.

A regra de produto fica formalizada como:

> **A NAVE deve ser mais ousada em analisar e mais conservadora em afirmar.**

---

## Arquivos a substituir/adicionar no GitHub

Substituir:

- `project_analyst.py`
- `project_batch_ingestion.py`
- `project_bundle_materializer.py`
- `project_intelligence_report.py`
- `project_intelligence_unified.py`
- `project_report_extractor.py`
- `project_workspace_intelligence.py`
- `project_workspace_reports.py`
- `project_workspace_ui.py`
- `project_workspace_visuals.py`
- `pages/14_Importar_Projeto.py`
- `evals/cases/golden_chambinho_festivalzinho_2026_full_cycle.yaml`
- `tests/test_file_analyst_integration_v2821.py`
- `tests/test_v28_4_0_knowledge_monotonicity.py`

Adicionar:

- `tests/test_v28_5_0_intelligence_productization.py`
- `GUIA_NAVE_V28_5_0_INTELLIGENCE_PRODUCTIZATION.md`

---

## SQL

**NÃO.**

A V28.5.0 não altera schema.

---

## Reboot

**SIM.**

Depois de substituir os arquivos:

**Streamlit → Manage app → Reboot app**

---

## Como testar o Chambinho nesta rodada

### Primeiro teste — NÃO reprocessar

Depois do reboot:

1. abra diretamente **Festivalzinho Chambinho**;
2. não reenvie arquivos;
3. não rode reprocessamento ainda;
4. revise as abas com o conhecimento já preservado pela V28.4.0.

Isso permite validar a nova camada de projeção sem misturar o teste com uma nova extração.

### O que observar

**Visão geral**
- sem conclusão de “sucesso” não comprovada;
- sem custo por participante calculado a partir dos 8 mil do Festivalzinho;
- leitura financeira com reconciliação de pagamento direto.

**Briefing**
- budget visível como R$ 400.000,00;
- demandas em cards com texto completo;
- `Resposta identificada` para o que a proposta já responde;
- sem `None` como budget.

**Diagnóstico e recomendações**
- sem FACT/INFERENCE no caminho principal;
- sem links legados/Graph/backend;
- conclusões e recomendações antes das matrizes.

**Estratégia**
- síntese executiva preservada;
- sem “sucesso de engajamento” quando não há métrica.

**Cenografia**
- a abertura da aba pode disparar uma recuperação de páginas visuais e rerun automático;
- devem aparecer renders da Casa Chambinho no lugar da grande lista de arquivos, quando as páginas do master forem recuperáveis.

**Brindes / Ativações**
- custo não rateado aparece uma vez por seção;
- badges R$ 0,00 sugeridos desaparecem.

**Orçamento**
- percentuais coerentes: Infraestrutura ~63,8%, Staff ~14,0% etc.;
- sem custo por participante baseado no público do festival.

**Feedbacks**
- vazio é aceitável quando não existe feedback explícito;
- a explicação deve deixar claro que pós-evento está em Resultados.

**Resultados e aprendizados**
- `Público registrado no evento`, não `Participantes`;
- ativações em cards;
- execução não chamada automaticamente de sucesso;
- aprendizados inferidos sem afirmações de eficácia/aceitação não comprovadas;
- inconsistência de tatuagens preservada, sem “92% de sobra”.

**Dossiê Inteligente**
- conclusão antes de números;
- lockup NAVE discreto;
- sem backend/links/hashes no corpo;
- fontes em linguagem humana no final.

### Segundo teste — reprocessamento somente se necessário

Só rode **Reprocessar conteúdo com leitura especializada** depois de observar a interface da V28.5.0 se ainda houver texto antigo proveniente da análise do relatório/Project Analyst que precise ser regenerado com os prompts novos.

A Knowledge Monotonicity da V28.4.0 continua ativa e protege o conhecimento anterior.

---

## Validação técnica desta entrega

### Regressão focada

**39 testes passaram.**

Inclui V28.5.0 + Knowledge Monotonicity + Unified Intelligence + Pipeline + IQ Bench + integração do File Analyst.

### Suíte coletável neste ambiente

**174 testes passaram.**

Persistem **4 falhas legadas**, já existentes e fora do escopo desta entrega:

- 3 testes de `sitecustomize` ligados à seleção de Locais;
- 1 teste da política visual de Locais sobre `source_image_url`.

### Coleta integral

5 módulos antigos ainda não coletam neste container local porque o ambiente não possui `streamlit` e `google-genai`; essas dependências existem no deploy do Streamlit e aparecem instaladas no log do app.

### PDF

O Dossiê v2 de amostra foi gerado, renderizado em PNG e revisado visualmente em todas as páginas. Não foram observados clipping, sobreposição ou quebra de layout.

---

## Resultado esperado da V28.5.0

A NAVE deixa de dizer:

> “encontrei evidências / há links / o Analyst deve avaliar”.

E passa a dizer:

> **“Isto é o que os documentos permitem concluir; isto é o que ainda não sabemos; isto é o que aprendemos; e esta é a decisão que muda no próximo projeto.”**
