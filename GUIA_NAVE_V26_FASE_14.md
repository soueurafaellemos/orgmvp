# NAVE by VOE — V26

## Fase 14 — Resultados & Aprendizados

A Fase 14 registra o que aconteceu depois da apresentação e
relaciona o resultado do projeto com feedbacks, execução e custos.

Os dados permanecem vinculados ao projeto da Memória.

Eles não entram na Base de conhecimento e ainda não alteram
automaticamente o ranking das recomendações.

## 1. Execute o SQL

No Supabase:

1. Abra **SQL Editor**.
2. Clique em **New query**.
3. Cole todo o conteúdo de:

`supabase_patch_fase_14_resultados_aprendizados_v1.sql`

4. Clique em **Run**.

## 2. Atualize o GitHub

Adicione:

- `memory_learning_models.py`
- `memory_cost_parser.py`
- `memory_learning_db.py`
- `memory_learning_ui.py`

Substitua:

- `memory_ui.py`
- `pages/10_Memoria.py`
- `README.md`

Depois:

`Manage app -> Reboot app`

Não é necessário alterar `requirements.txt`.

## Resultados & Aprendizados

Selecione um projeto em **Memória** e abra:

`Resultados & Aprendizados`

É possível registrar:

- tipo de processo;
- ganho, perda, cancelamento ou ausência de retorno;
- aprovação integral ou parcial;
- execução;
- cliente contratante;
- parceiros envolvidos;
- motivos;
- contexto;
- fonte e confiança da informação.

### Feedbacks

Cada feedback possui:

- data;
- origem;
- etapa;
- tema;
- sentimento;
- comentário original;
- interpretação interna;
- ação decorrente;
- confiança.

## Resultado por ficha

Em qualquer seção da Memória:

1. clique em **Abrir ficha**;
2. abra **Resultado & custo**;
3. registre aprovação, rejeição, substituição, retirada por budget,
   retirada por prazo ou execução.

## Orçamento & Aderência

Abra:

`Orçamento & Aderência`

### Budget

Informe o budget registrado no briefing.

### Planilha

Formatos aceitos:

- XLSX
- XLSM
- XLS
- CSV

A NAVE:

- identifica a tabela de custos;
- estrutura categorias e itens;
- lê quantidades e valores;
- identifica opcionais, reservas e pendências;
- preserva o arquivo original;
- nunca executa macros;
- não recalcula a planilha.

### Correlação

Depois de salvar, a NAVE sugere ligações entre:

- linha da planilha;
- ficha da apresentação.

As sugestões são aproximadas e precisam ser revisadas.

## Dentro da ficha

Em **Resultado & custo**, a ficha passa a mostrar:

- resultado da proposta;
- motivo;
- feedback relacionado;
- observações de execução;
- custos associados;
- situação do item;
- linha de origem da planilha;
- indicação de correlação sugerida ou confirmada.

## Teste com a planilha de exemplo

A planilha `Evento - FESTIVALZINHO - CHAMBINHO 25.06.2026.xlsm`
foi usada na validação.

Resultado do teste:

- aba identificada: `Planilha VOE`;
- cabeçalho identificado na linha 15;
- 54 itens estruturados;
- custo-base: R$ 456.687,01;
- honorários: R$ 44.369,43;
- encargos: R$ 53.254,41;
- total da proposta: R$ 554.310,85;
- macros não executadas.

## Limites desta entrega

A V26 não inclui:

- elaboração de orçamento;
- edição de fórmulas;
- faturamento;
- contas a pagar;
- atualização automática de preços;
- alteração automática do ranking das recomendações.
