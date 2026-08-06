# NAVE by VOE — V25.1

## Memória com análise integral

A apresentação agora é analisada inteira em uma única chamada.
Não existe mais o controle “Slides por etapa”.

## Novo fluxo para criar um projeto

1. Abra **Memória**.
2. Entre em **Adicionar apresentação**.
3. Escolha **Criar novo projeto automaticamente**.
4. Envie o PDF.
5. Clique em **Analisar apresentação completa**.

Nenhum campo precisa ser preenchido antes da análise.

A NAVE tentará identificar:

- nome do projeto;
- cliente ou marca;
- evento;
- título da apresentação;
- versão.

Na revisão, todos esses campos podem ser corrigidos antes de salvar.

## Edição posterior

Depois de salvar:

- **Visão geral → Editar informações do projeto**
  permite corrigir projeto, cliente e evento;
- **Documentos & Versões → Editar informações da apresentação**
  permite corrigir título, versão e situação.

## Atualização no GitHub

Substitua:

- `memory_models.py`
- `memory_prompts.py`
- `memory_extractor.py`
- `memory_db.py`
- `pages/10_Memoria.py`
- `README.md`

Depois:

`Manage app -> Reboot app`

Não é necessário executar SQL.

O patch não contém arquivos da pasta `assets`.
