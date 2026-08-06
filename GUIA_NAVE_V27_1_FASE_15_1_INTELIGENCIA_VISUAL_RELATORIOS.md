# NAVE by VOE — V27.1

## Fase 15.1 — Inteligência Visual e Fechamento do Projeto

Esta correção preserva a interface aprovada da Fase 15 e recupera a inteligência que existia na Memória.

## O que muda

### Cenografia, ativações e brindes

Essas áreas voltam a ser visuais:

- cards em grade horizontal;
- recorte visual do item, quando disponível;
- slide completo como fallback;
- recuperação automática de imagens antigas usando o inventário da apresentação;
- título, tipo, situação e resumo;
- custo relacionado na própria ficha;
- abertura da ficha completa com briefing, aderência, custos, resultado, evidência e origem.

A indicação do número do slide foi removida da interface de negócio.

### Estratégia e conceito

Permanece textual. Imagens não são exibidas nessa área por padrão.

### Relatórios de encerramento e pós-execução

O upload deixa de ser apenas armazenamento. Antes de salvar, a NAVE analisa o arquivo e aplica ao projeto:

- resumo executivo;
- participantes;
- custo previsto e realizado;
- indicadores;
- resultados por ativação ou entrega;
- feedbacks;
- ocorrências;
- avaliação de fornecedores;
- aprendizados;
- recomendações futuras;
- resultado e execução das fichas correspondentes.

## Instalação

### 1. Supabase

Execute:

`supabase_patch_fase_15_1_inteligencia_visual_relatorios_v1.sql`

### 2. GitHub

Adicione:

- `project_report_extractor.py`
- `project_workspace_visuals.py`
- `project_workspace_reports.py`

Substitua:

- `project_workspace_db.py`
- `project_workspace_ui.py`

Os demais arquivos da Fase 15 permanecem iguais.

### 3. Reinicie

`Manage app → Reboot app`

Não é necessário alterar `requirements.txt`.

## Teste com Chambinho

1. Abra **Projetos** e selecione Chambinho.
2. Entre em **Cenografia e ativações**.
3. Confirme que os materiais visuais aparecem em cards horizontais.
4. Confirme que Amarelinha, Jogo da memória e Pescaria exibem imagem quando a apresentação possui recorte ou slide preservado.
5. Abra cada ficha e confirme custos relacionados, briefing, aderência e resultado.
6. Abra **Brindes e press kits** e confirme a mesma visualização.
7. Entre em **Resultados e aprendizados**.
8. Se o relatório já estiver anexado, clique em **Analisar arquivo já anexado**. Também é possível enviar uma nova versão.
9. Confirme que a NAVE mostra a leitura estruturada e preenche resultados, indicadores, feedbacks e aprendizados.

## Dados antigos

Não é necessário reenviar a apresentação final. A V27.1 recupera páginas visuais ausentes a partir do PDF original e do inventário já salvo na Memória, quando esses dados estiverem disponíveis.
