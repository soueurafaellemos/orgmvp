# NAVE by VOE · V28.2.2 — Entity Resolution + Cross-Source Intelligence v1

## Objetivo

A V28.2.2 é a primeira camada da NAVE que deixa de apenas analisar cada fonte separadamente e passa a tentar reconhecer **a mesma entidade atravessando arquivos diferentes**.

Ela não substitui o File Analyst nem o Workspace legado. Ela roda depois do dual-write da V28.2.1 e conecta o Intelligence Graph de forma conservadora e auditável.

Exemplos do tipo de identidade que a camada precisa reconhecer:

- `Cinemateca` ↔ `Cinemateca Brasileira`;
- `ON TOUR` ↔ `JOVI X300 Series ON TOUR`;
- uma ativação apresentada ↔ a linha de custo correspondente;
- uma solução apresentada ↔ evidência posterior de execução;
- uma exigência de pagamento direto do cliente ↔ uma família financeira potencialmente relacionada.

Quando a evidência não é suficiente, a NAVE **não faz merge silencioso**: registra revisão/finding.

---

## O que muda

### 1. Entity Resolution v1

Novo módulo `entity_resolution.py`.

O resolver usa:

- tipo da entidade;
- nome canônico;
- aliases;
- escopo do projeto;
- similaridade nominal;
- sobreposição de termos;
- contexto estruturado disponível.

Decisões possíveis:

- **AUTO_MERGE** — identidade forte;
- **REVIEW** — identidade plausível, precisa de revisão/mais evidência;
- **DISTINCT** — evidência insuficiente para tratar como a mesma entidade.

Entidades de tipos diferentes nunca são unificadas apenas porque têm nomes parecidos.

### 2. Cross-Source Linker v1

Novo módulo `cross_source_linker.py`.

Depois que todos os arquivos do projeto foram analisados pelo File Analyst, a NAVE executa uma rodada única sobre o grafo do projeto para:

- consolidar aliases e identidades equivalentes;
- ligar soluções/ativações a linhas financeiras quando a correspondência é forte;
- reconhecer evidência explícita de execução em relatório pós-evento;
- identificar instruções explícitas de pagamento direto pelo cliente;
- sinalizar ambiguidade de budget quando o total bruto e a responsabilidade financeira não permitem concluir um estouro líquido com segurança;
- criar findings de revisão em vínculos ambíguos.

### 3. File Analyst v1.1

O File Analyst passa a:

- preservar papéis documentais específicos já resolvidos no lote (por exemplo, `post_event_report`);
- reconhecer budget quando o rótulo `BUDGET` e o valor aparecem em parágrafos consecutivos;
- reconhecer faixas como `6 a 8 mil pessoas`;
- transformar instruções explícitas de pagamento direto em requisito estruturado, sem inventar a linha financeira relacionada.

### 4. Classificação de relatório pós-evento

`RELATORIO`, `POST EVENT`, `PÓS-EVENTO`, `ENCERRAMENTO` e sinais de execução passam a ter prioridade estrutural sobre vocabulário interno de proposta.

Isso evita que um relatório que recapitulou estratégia e ativações volte a ser classificado como apresentação de proposta.

### 5. Intelligence Graph evita novas duplicatas por aliases

`intelligence_graph_db.py` passa a consultar aliases já resolvidos antes de criar uma nova entidade e passa a persistir novos aliases mesmo quando a entidade canônica já existia.

### 6. Golden Project #2 — Chambinho / Festivalzinho 2026

O IQ Bench agora contém:

`golden_chambinho_festivalzinho_2026_full_cycle`

Os quatro arquivos proprietários continuam **fora do GitHub**. O benchmark registra apenas basename + SHA-256.

O caso mede, entre outras coisas:

- briefing → proposta → orçamento → execução;
- `proposto ≠ orçado ≠ executado`;
- budget nominal x responsabilidade de pagamento direto;
- solução ↔ custo;
- solução ↔ evidência de execução;
- dados contraditórios/incompletos;
- resíduos de template e datas históricas;
- inferências proibidas, como transformar 8 mil pessoas presentes no festival em 8 mil visitantes da ativação.

---

## Arquivos para substituir/adicionar no GitHub

Substituir:

- `file_analyst.py`
- `intelligence_graph_db.py`
- `project_batch_ingestion.py`
- `project_bundle_materializer.py`
- `pages/14_Importar_Projeto.py`
- `iq_bench_runner.py`
- `evals/suite.yaml`
- `tests/test_file_analyst_integration_v2821.py`
- `tests/test_iq_bench_runner_v1.py`

Adicionar:

- `entity_resolution.py`
- `cross_source_linker.py`
- `evals/cases/golden_chambinho_festivalzinho_2026_full_cycle.yaml`
- `tests/test_entity_resolution_v2822.py`
- `tests/test_cross_source_linker_v2822.py`
- `tests/test_chambinho_golden_v2822.py`
- `NAVE_IQ_V28_2_2_VALIDATION.md`
- `GUIA_NAVE_V28_2_2_ENTITY_RESOLUTION_CROSS_SOURCE.md`

---

## SQL

**NÃO executar SQL novo para esta versão.**

Pré-requisito: a **NAVE Intelligence Foundation v1** da etapa 03A precisa já estar instalada. Se ainda não estiver, o dual-write/linker é fail-open e o Workspace legado continua funcionando, mas o novo Graph não terá onde persistir as conexões.

---

## Reboot

**SIM.**

Depois de subir os arquivos:

`Manage app → Reboot app`

---

## Teste de aceitação — Chambinho

Depois do deploy e do reboot, **agora sim importe Chambinho pela primeira vez**.

Envie os quatro arquivos juntos, sem correção manual inicial:

1. `VOE _Briefing Interno_Chambinho_no_Festivalzinho (1).docx`
2. `PDF_PROJETO_FESTIVALZINHO_CHAMBINHO_27.05_compressed.pdf`
3. `Evento - FESTIVALZINHO - CHAMBINHO 25.06.2026 (1).xlsm`
4. `RELATORIO_LACTALIS_FESTIVALZINHO26 (1).pptx`

Papéis esperados antes de salvar:

- DOCX → **Briefing original**
- PDF → **Apresentação de proposta**
- XLSM → **Planilha detalhada de custos**
- PPTX → **Relatório pós-evento / encerramento**

Se esses quatro papéis aparecerem corretamente, não ajuste manualmente. Salve o lote para avaliarmos a inteligência produzida pela própria NAVE.

Depois da importação, observe o expander:

**`Intelligence Graph · conexões entre arquivos`**

Ele expõe inicialmente:

- entidades unificadas;
- vínculos solução ↔ custo;
- evidências de execução;
- revisões sugeridas.

---

## O que NÃO esperar ainda

A V28.2.2 **não é ainda o Project Analyst V2**.

Ela prepara o grafo conectado e já produz algumas conclusões conservadoras, mas ainda não deve ser julgada pela capacidade de redigir sozinha toda a análise executiva que fizemos manualmente para Chambinho.

O próximo passo arquitetural é usar este grafo resolvido para construir o **Project Analyst V2**, que poderá raciocinar de forma sistemática sobre:

briefing → estratégia → solução → custo → execução/feedback → resultado → aprendizado.

A regra continua sendo: nenhuma conclusão forte sem evidência rastreável.
