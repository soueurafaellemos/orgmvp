# NAVE by VOE · V28.4.0 — Knowledge Monotonicity + Decision Intelligence UX

## Objetivo da versão

A V28.4.0 nasce diretamente da auditoria completa do Golden Project Chambinho após a V28.3.0.

A V28.3.0 já conseguia detectar falsos vazios, evidências pós-evento e contradições internas. Porém, o reprocessamento ainda podia degradar uma leitura previamente válida — especialmente quando os masters já estavam no Cloudflare R2, mas um ponteiro legado continuava apontando para o Supabase Storage.

Esta versão corrige primeiro a regra mais importante:

> **Reprocessar nunca pode reduzir o conhecimento válido da NAVE.**

Ao mesmo tempo, separa o diagnóstico técnico da própria plataforma da inteligência de negócio apresentada ao usuário e melhora a projeção visual das evidências nas abas do workspace.

---

## 1. Knowledge Monotonicity: reprocessamento sem perda de conhecimento

O fluxo de reprocessamento passa a proteger leituras já estruturadas.

Antes de substituir briefing, planilha ou apresentação, a NAVE:

1. mede a cobertura existente;
2. captura um backup transacional das estruturas especializadas;
3. recupera o master;
4. executa a nova leitura;
5. mede a nova cobertura;
6. somente mantém a nova versão se os gates mínimos forem respeitados;
7. em caso de falha/regressão, remove a tentativa parcial e restaura a leitura anterior.

### Gates atuais

**Briefing**
- uma leitura que tinha requisitos não pode voltar para zero;
- uma leitura mais limpa pode ter menos requisitos quando os anteriores eram ruído de formulário.

**Custos**
- se existiam linhas úteis, a nova leitura não pode cair abaixo de 90% da cobertura anterior;
- zerar uma planilha previamente estruturada bloqueia a promoção.

**Apresentação**
- a quantidade de páginas preservadas não pode cair abaixo de 90% da leitura anterior;
- uma apresentação que já tinha entidades não pode voltar para zero.

---

## 2. Reprocessamento agora recupera corretamente masters no R2

A V28.3.0 ainda possuía um caminho legado que podia falhar ao tentar recuperar arquivos já migrados para Cloudflare R2.

A V28.4.0 usa `nave_storage.get_bytes()` e tenta recuperar o mesmo master por múltiplas referências confiáveis:

- ponteiro atual em `source_files`;
- `source_assets` do Intelligence Graph via SHA-256;
- `project_files` via projeto + SHA-256;
- outro `source_files` equivalente via projeto + SHA-256.

Quando encontra o master por um endereço mais novo, a NAVE:

- atualiza automaticamente o ponteiro de `source_files`;
- atualiza o registro correspondente de `project_files`;
- usa o endereço curado já no mesmo ciclo de materialização.

Isso é especialmente importante para projetos importados durante a transição Supabase Storage → Cloudflare R2.

---

## 3. O briefing deixa de transformar ruído de formulário em demanda

O Briefing Analyst recebe uma regra explícita para distinguir:

- nome/rótulo de campo;
- resposta administrativa;
- contexto;
- objetivo;
- restrição;
- obrigatoriedade;
- entregável real.

Textos como opções de envio, labels de tabela ou concatenações estruturais não devem virar automaticamente requisitos.

Também foi removido um fallback específico por nome de projeto/cliente no parser determinístico. A identidade deve vir da evidência, não de regras hardcoded de Chambinho, JOVI ou qualquer outro projeto.

---

## 4. Cross-source mais conservador: ano não prova identidade

A V28.3.0 chegou a vincular uma solução apresentada a uma evidência pós-evento usando apenas o token `2026`.

Isso é proibido na V28.4.0.

Entity Resolution e Cross-Source Linker agora ignoram tokens puramente numéricos em decisões de identidade. Anos, números de página e termos genéricos não podem comprovar que duas soluções são a mesma entidade.

O Golden Chambinho foi atualizado com essa inferência explicitamente proibida.

---

## 5. Público do festival ≠ público da ativação

A leitura de audiência foi revisada.

A NAVE agora distingue escopos como:

- `festival_event`;
- `project_attendees`;
- `project_audience`.

Exemplo Chambinho:

- `6 a 8 mil pessoas` = público de referência do Festivalzinho;
- isso **não** é convertido automaticamente em visitantes da Casa Chambinho.

Da mesma forma, `30 a 45 anos` é faixa etária e não pode ser interpretada como `45 participantes`.

Consequência prática:

> **Custo por participante só é calculado quando existe denominador comprovado para o projeto/ativação.**

Se a única audiência conhecida for a do festival hospedeiro, a interface mostra que o cálculo não é possível com as fontes atuais.

---

## 6. Relatório pós-evento não significa automaticamente “Ganho” ou “Integralmente aprovada”

A existência de um relatório pós-execução comprova evidência posterior e pode sustentar o estado de execução.

Ela **não prova sozinha**:

- resultado comercial `Ganho`;
- proposta `Integralmente aprovada`.

A V28.4.0 preserva esses campos apenas quando já existe uma fonte confirmada — cliente/VOE, e-mail, reunião ou feedback explícito.

Campos sem prova permanecem como **Não informado**.

Também foram removidos marcadores internos como `[NAVE-V28...] documento anexado` dos campos visíveis de Contexto/Aprendizados e Observações de execução.

---

## 7. Diagnóstico de negócio separado da Saúde da leitura NAVE

A V28.3.0 exibia mensagens como:

- falso vazio em Cenografia;
- relatório presente mas não materializado no legado;
- estrutura técnica incompleta.

Esses avisos são importantes para auditoria, mas não são diagnóstico de negócio.

Na V28.4.0:

### Diagnóstico e recomendações
Mostram somente inteligência útil sobre o projeto:

- aderência;
- riscos;
- oportunidades;
- decisões;
- conexões descobertas.

### Saúde da leitura NAVE · diagnóstico técnico
Fica em um expander separado e contém:

- fontes anexadas ainda não estruturadas;
- falsos vazios técnicos;
- inconsistências de processamento;
- problemas de cobertura.

Assim o backend deixa de parecer “o ouro” da plataforma.

---

## 8. Resultados e Aprendizados voltam a ser uma experiência própria

Resultados e Aprendizados deixam de ser uma aba interna do Diagnóstico.

Eles continuam consumindo a mesma Unified Project Truth, mas voltam a ter uma experiência própria no workspace, orientada ao fechamento pós-evento:

- público registrado e seu escopo;
- ativações/entregas executadas;
- pendências;
- inconsistências de dados;
- resultados consolidados;
- aprendizados reutilizáveis;
- memória que deve ser preservada;
- pontos que devem mudar em projetos futuros.

---

## 9. Estratégia e conceito passam a ser síntese — não dump de slide

O Project Analyst ganha um `strategy_framework` estruturado com:

- território;
- tensão;
- pilares;
- direção estratégica;
- conceito/POV;
- papel da experiência;
- aderência ao briefing.

A aba Estratégia passa a privilegiar essa leitura consolidada. Slides/páginas permanecem como evidência auditável abaixo da análise.

A regra é:

> **Fonte sustenta a análise; a fonte não substitui a análise.**

---

## 10. Cenografia, ativações, comunicação, jornada e brindes ganham projeção visual de evidências

Quando as fichas legadas/canônicas ainda não estiverem completas, a interface não mostra mais apenas listas de `PDF página 7`, `PPT slide 9` etc.

Quando uma `memory_page` visual já está preservada, a NAVE usa:

- imagem da página/slide;
- título;
- trecho relevante;
- fonte/página como provenance discreto.

Há fallback visual para:

- Cenografia e ambientes;
- Ativações e experiências;
- Comunicação e materiais;
- Jornada e operação;
- Brindes e press kits.

Quando uma única ficha de ativação ainda condensar várias mecânicas, a interface pode mostrar **evidências visuais complementares** em vez de esconder o restante do material.

---

## 11. Feedback: relatório pós-evento não é feedback automaticamente

A aba Feedbacks continua exigindo feedback explícito.

Se um relatório pós-evento contiver depoimentos, aprovação, crítica ou comentário do cliente, esses trechos podem aparecer como feedback.

Se não houver comentário explícito, a NAVE mostra:

> `Nenhum feedback explícito do cliente foi identificado nas fontes atuais.`

Isso evita preencher a aba artificialmente apenas porque existe um relatório de execução.

---

## 12. Inteligência financeira mais segura

A V28.4.0 mantém a leitura de:

- budget do briefing;
- total da proposta;
- diferença;
- uso do budget;
- maiores categorias;
- maiores itens;
- concentração financeira.

Se houver sinal de pagamento direto pelo cliente, a diferença aparece como **diferença bruta a reconciliar**, e não como estouro definitivo.

Se não houver audiência comprovada da ativação, custo por participante não é calculado.

---

## 13. Dossiê Inteligente v2

O Dossiê continua consumindo a mesma Unified Truth da interface.

A V28.4.0 adiciona o lockup **NAVE by VOE** de forma discreta na abertura e refina:

- resumo executivo;
- leitura estratégica;
- framework estratégico;
- inteligência financeira;
- diagnóstico;
- resultados;
- conexões descobertas;
- aprendizados;
- recomendações;
- riscos/unknowns;
- proveniência.

O relatório diferencia:

- FATO;
- INFERÊNCIA;
- APRENDIZADO;
- RECOMENDAÇÃO;
- CONTRADIÇÃO/RISCO.

---

## Golden Chambinho — inferências proibidas adicionadas

A NAVE deve falhar no IQ Bench se:

- usar apenas `2026` como evidência de execução de uma solução;
- usar a faixa etária 30–45 como quantidade de pessoas;
- usar 8 mil visitantes do festival como visitantes comprovados da ativação;
- inferir `Ganho` ou `Integralmente aprovada` apenas porque existe relatório pós-execução.

---

## Arquivos a substituir/adicionar no GitHub

Substituir/adicionar exatamente:

- `memory_briefing.py`
- `project_bundle_materializer.py`
- `project_workspace_ui.py`
- `project_workspace_db.py`
- `project_workspace_intelligence.py`
- `project_analyst.py`
- `project_intelligence_unified.py`
- `project_intelligence_report.py`
- `cross_source_linker.py`
- `entity_resolution.py`
- `project_batch_ingestion.py`
- `pages/14_Importar_Projeto.py`
- `evals/cases/golden_chambinho_festivalzinho_2026_full_cycle.yaml`
- `tests/test_file_analyst_integration_v2821.py`
- `tests/test_v28_4_0_knowledge_monotonicity.py`
- `GUIA_NAVE_V28_4_0_KNOWLEDGE_MONOTONICITY.md`

O ZIP não possui pasta externa envolvendo o conteúdo.

---

## SQL

**NÃO.**

A V28.4.0 usa a Intelligence Foundation e o schema atualmente instalados.

---

## Reboot

**SIM.**

Depois de subir os arquivos:

`Manage app → Reboot app`

---

## Teste recomendado — Golden Chambinho

Não reenvie os quatro masters.

Depois do reboot:

1. `Importar projeto completo`;
2. abrir `Corrigir um projeto importado por uma versão anterior da V28`;
3. escolher `Festivalzinho Chambinho`;
4. confirmar;
5. clicar em `Reprocessar conteúdo com leitura especializada`.

### O que deve acontecer nesta versão

- a planilha deve ser recuperada do R2 e voltar a produzir linhas financeiras;
- o PDF/DOCX devem ser recuperados pelos ponteiros corretos ou ter o ponteiro curado via SHA-256;
- se uma nova leitura ficar pior que uma leitura válida existente, a NAVE preserva/restaura a anterior;
- budget de R$ 400 mil permanece;
- total da proposta deve voltar quando a planilha for estruturada;
- `45 anos` não pode aparecer como `45 participantes`;
- `8.000` deve permanecer identificado como público do festival, não visitantes da ativação;
- Estratégia deve mostrar uma leitura consolidada quando o Project Analyst gerar `strategy_framework`;
- evidências de Cenografia/Ativações/Brindes devem aparecer visualmente quando houver páginas preservadas;
- Diagnóstico não deve exibir erros de backend como análise de negócio;
- Resultados e Aprendizados permanecem como seção própria;
- existência de relatório pós-evento não deve pré-selecionar `Ganho` ou `Integralmente aprovada` sem fonte confiável.

---

## Validação local desta entrega

### Regressão focada

**41 testes passaram** cobrindo:

- Knowledge Monotonicity;
- R2/pointer healing;
- Cross-Source;
- Entity Resolution;
- Golden Chambinho;
- Golden JOVI;
- Unified Intelligence;
- Project Intelligence Pipeline.

### Suíte coletável do repositório

Ao ignorar 5 módulos que não coletam neste container por ausência local de `streamlit`/`google-genai`:

- **166 testes passaram**;
- **4 testes legados já falhavam na V28.3.0 e continuam falhando** em `sitecustomize`/política visual de Locais — não foram introduzidos por esta versão.

Na mesma comparação, um teste legado de reprocessamento financeiro que falhava na V28.3.0 passou com a nova recuperação de master.

---

## Importante: o que esta versão ainda NÃO declara concluído

A V28.4.0 corrige segurança do reprocessamento e a projeção da inteligência já encontrada.

Ainda não considero encerrados:

- decomposição perfeita de toda apresentação em entidades canônicas individuais;
- ligação perfeita das 54 linhas de custo a cada solução;
- comparação visual automática proposta ↔ executado para todos os itens;
- benchmarks históricos amplos enquanto a base ainda é pequena;
- Recommendation Intelligence V2 baseada em todo o Intelligence Graph.

Esses pontos continuam no roadmap, mas agora podem evoluir sem o risco de cada reprocessamento destruir conhecimento já válido.
