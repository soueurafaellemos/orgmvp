# NAVE by VOE — V26.3

## Fase 14.1 — Briefing & Aderência

Esta versão adiciona o briefing inicial ao ciclo de aprendizado:

`briefing → proposta → orçamento → feedback → resultado → execução`

Também corrige:

- upload de planilhas XLSM;
- exclusão de projetos vinculados ao histórico de recomendações.

## 1. Execute o SQL

No Supabase:

1. abra **SQL Editor**;
2. clique em **New query**;
3. cole todo o conteúdo de:

`supabase_patch_fase_14_1_briefing_aderencia_v1.sql`

4. clique em **Run**.

Este SQL deve ser executado depois do SQL da Fase 14.

## 2. Atualize o GitHub

Adicione:

- `memory_briefing.py`

Substitua:

- `memory_learning_models.py`
- `memory_learning_db.py`
- `memory_learning_ui.py`
- `memory_ui.py`
- `pages/10_Memoria.py`
- `README.md`

Depois:

`Manage app → Reboot app`

Não é necessário alterar `requirements.txt`.

## Briefing & Aderência

Selecione um projeto em **Memória** e abra:

`Briefing & Aderência`

Formatos aceitos:

- PDF
- DOCX
- PPTX
- TXT
- MD

A NAVE identifica:

- objetivo;
- público;
- quantidade estimada;
- budget;
- data e local;
- entregáveis;
- obrigatoriedades;
- restrições;
- demandas operacionais;
- comunicação;
- indicadores e KPIs.

A revisão aparece antes de salvar.

## Matriz de aderência

Depois do salvamento, a NAVE sugere uma ficha da apresentação para
cada demanda.

É possível registrar:

- Cumprida
- Cumprida parcialmente
- Não cumprida
- Superada
- Alterada com justificativa
- Retirada por budget
- Retirada por prazo
- Não aplicável
- Não foi possível comprovar

A aderência pode ser salva mesmo quando nenhuma ficha da apresentação
foi associada. Isso permite registrar obrigatoriedades não cumpridas.

## Dentro da ficha

Em:

`Abrir ficha → Briefing, resultado & custo`

aparecem:

- demanda do briefing;
- situação da aderência;
- evidência;
- fonte;
- custo associado;
- decisão e feedback.

## Correção das planilhas XLSM

A V26 criava o bucket com o MIME oficial contendo `macroEnabled`,
enquanto o Storage comparava o valor normalizado como `macroenabled`.

A V26.3:

- atualiza o bucket já existente;
- adiciona os formatos normalizados;
- usa `application/vnd.ms-excel` para arquivos XLSM;
- tenta novamente com o MIME genérico caso o Storage ainda rejeite
  a primeira tentativa.

Não é necessário excluir e recriar o bucket manualmente.

## Correção da exclusão do projeto

A tabela `recommendation_versions` pode manter uma referência ao
projeto. Nesse caso, apagar a linha principal de `projects` gerava
erro de chave estrangeira.

Agora a NAVE:

1. remove PDF, slides, imagens, briefings, feedbacks e planilhas;
2. remove todos os registros da Memória;
3. tenta excluir o cadastro geral;
4. caso ele seja usado por recomendações, mantém o cadastro em
   **Projetos**, mas o remove da lista **Memória**.

Nenhuma versão de recomendação é apagada.
