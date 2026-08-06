# NAVE by VOE — V25

## Fase 12 — Memória

A Memória é o arquivo vivo do repertório criativo e estratégico
dos projetos da VOE. Ela é totalmente separada da Base de conhecimento.

## 1. Execute o SQL

No Supabase:

1. Abra **SQL Editor**.
2. Clique em **New query**.
3. Cole o conteúdo de `supabase_patch_memoria_v1.sql`.
4. Clique em **Run**.

## 2. Atualize o GitHub

Adicione:

- `memory_models.py`
- `memory_prompts.py`
- `memory_extractor.py`
- `memory_db.py`
- `memory_ui.py`
- `pages/10_Memoria.py`

Substitua:

- `branding.py`
- `README.md`

Depois faça:

`Manage app -> Reboot app`

O patch não contém arquivos da pasta `assets`.

## Menu

No menu lateral aparece somente:

**Memória**

Dentro da página:

- Consultar Memória
- Adicionar apresentação

## Como adicionar

1. Abra **Memória**.
2. Entre em **Adicionar apresentação**.
3. Selecione um projeto ou crie um novo.
4. Envie a apresentação em PDF.
5. Informe versão e situação.
6. Clique em **Analisar apresentação**.
7. Revise os itens encontrados.
8. Ajuste seção, tipo, título, resumo ou status.
9. Desmarque o que não deve ser preservado.
10. Clique em **Salvar na Memória**.

## Seções internas

- Visão geral
- Estratégia
- Cenografia & Ambientes
- Ativações & Experiências
- Brindes & Materiais
- Jornada & Operação
- Comunicação & Desdobramentos
- Conteúdo & Agenda
- Parceiros & Cotas
- PR, ESG & Legado
- Documentos & Versões

As abas opcionais aparecem somente quando possuem conteúdo.

## Preservação

Para cada item, a NAVE mantém:

- imagem recortada, quando houver visual claro;
- slide completo;
- número do slide;
- documento e versão de origem;
- descrição, tags e evidência;
- PDF original para consulta.

## Isolamento técnico

A Memória usa somente:

- `memory_documents`
- `memory_pages`
- `memory_items`
- bucket privado `nave-memory`

Esses registros não são lidos pelo motor de recomendações e não
possuem processo ou botão para entrar na Base de conhecimento.
