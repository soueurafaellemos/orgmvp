# NAVE by VOE — V27

## Fase 15 — Workspace Unificado do Projeto

Esta fase executa a **Reestruturação do Workspace do Projeto**.

A tela intermediária de **Áreas do projeto** deixa de ser necessária.
Depois de selecionar um projeto, a pessoa entra diretamente em sua
**Visão geral** e permanece no mesmo ambiente.

## Base esperada

- V26 instalada;
- Fase 14 — Resultados & Aprendizados instalada;
- Fase 14.1 — Briefing & Aderência instalada;
- V26.3 — Projetos e Memória unificados instalada.

## 1. Execute o SQL

No Supabase:

1. abra **SQL Editor**;
2. clique em **New query**;
3. cole todo o conteúdo de:

`supabase_patch_fase_15_workspace_unificado_v1.sql`

4. clique em **Run**.

O SQL é idempotente.

Ele cria somente a tabela:

`project_files`

Essa tabela funciona como central versionada dos arquivos principais.
As tabelas já existentes de briefing, memória, custos, feedbacks e
resultados permanecem preservadas.

## 2. Atualize o GitHub

### Adicione

- `project_workspace_runtime.py`
- `project_workspace_db.py`
- `project_workspace_ui.py`

### Substitua

- `project_hub.py`
- `pages/4_Historico_de_Projetos.py`

Não substitua:

- `pages/10_Memoria.py`
- `memory_ui.py`
- `memory_learning_ui.py`
- `memory_briefing.py`
- arquivos da pasta `assets`

A página antiga da Memória continua existindo tecnicamente para preservar
as rotinas de análise já instaladas, mas não volta ao menu principal.

Depois:

`Manage app → Reboot app`

Não é necessário alterar `requirements.txt`.

## 3. Novo fluxo

### Antes

`Projetos → projeto → Áreas do projeto → Memória → Orçamento`

ou:

`Projetos → projeto → Memória → voltar → Projetos → projeto → Briefing`

### Agora

`Projetos → projeto → Visão geral`

Dentro do mesmo workspace:

- Visão geral
- Briefing original
- Diagnóstico e recomendações
- Estratégia e conceito
- Cenografia e ativações
- Brindes e press kits
- Orçamento e aderência
- Fornecedores e referências
- Apresentações finais
- Feedbacks e aprovações
- Resultados e aprendizados
- Documentos

O projeto permanece selecionado durante toda a navegação.

## 4. Visão geral

A Visão geral reúne:

- status;
- próxima ação;
- pendências automáticas;
- quantidade de briefings;
- apresentações;
- conteúdos;
- feedbacks;
- arquivos;
- briefing original;
- planilha de custos;
- apresentação final;
- feedbacks e aprovações;
- relatório de encerramento ou pós-execução.

Os uploads principais podem ser feitos sem entrar em outra seção.

## 5. Status do projeto

Os status disponíveis são:

- Rascunho
- Em briefing
- Em desenvolvimento
- Apresentado
- Em revisão
- Em negociação
- Aprovado / ganho
- Perdido
- Cancelado
- Em produção
- Executado
- Arquivado

O status altera as pendências e o fechamento exibido.

### Projeto perdido

A NAVE solicita:

- feedback;
- resultado;
- aprendizados;
- relatório de encerramento da concorrência.

### Projeto executado

A NAVE solicita:

- feedback final;
- resultados;
- aprendizados;
- relatório pós-execução.

## 6. Arquivos principais

A nova central aceita:

### Briefing original

- PDF
- DOCX
- PPTX
- TXT
- MD

### Planilha de custos

- XLSX
- XLSM
- XLS
- CSV

### Apresentação final

- PDF
- PPTX

### Feedbacks e aprovações

- PDF
- DOCX
- PPTX
- TXT
- MD
- EML
- MSG

### Relatórios

- PDF
- DOCX
- PPTX
- XLSX
- XLSM
- TXT
- MD

Os arquivos ficam em um bucket privado criado automaticamente:

`nave-project-files`

O limite da aplicação é 100 MB por arquivo.

## 7. Preservação da inteligência existente

A Fase 15 não duplica nem apaga as estruturas anteriores.

O workspace lê diretamente:

- `memory_briefing_documents`
- `memory_briefing_requirements`
- `recommendation_queries`
- `memory_documents`
- `memory_items`
- `memory_cost_documents`
- `memory_cost_items`
- `memory_feedback_entries`
- `memory_project_outcomes`

A nova tabela `project_files` complementa essas estruturas com arquivos
que precisam ser anexados de forma rápida e intuitiva.

## 8. Teste recomendado

1. abra **Projetos**;
2. confirme que a lista única continua aparecendo;
3. selecione Chambinho;
4. confirme que o projeto abre diretamente na **Visão geral**;
5. navegue por todas as áreas sem voltar à lista;
6. anexe um briefing original pela Visão geral;
7. anexe uma planilha de custos pela Visão geral;
8. abra **Orçamento e aderência** e confirme que o arquivo aparece;
9. abra **Brindes e press kits**;
10. registre um feedback em texto;
11. altere o status para **Perdido** e confirme a solicitação de
    relatório de encerramento;
12. altere para **Executado** e confirme a solicitação de relatório
    pós-execução;
13. use **Voltar para todos os projetos** e confirme o retorno à lista.

## Resultado esperado

A tela **Áreas do projeto** não aparece mais.

O projeto passa a ser o ambiente principal de trabalho.

> O usuário não entra na memória. A memória acompanha o usuário
> durante todo o projeto.
