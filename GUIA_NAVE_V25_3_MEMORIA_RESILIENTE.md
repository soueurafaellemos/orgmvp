# NAVE by VOE — V25.3

## Correção da Memória

O erro `KeyError: Incluir` acontecia quando o Gemini concluía a
análise sem devolver fichas individuais. O DataFrame ficava sem
colunas e a página tentava acessar a coluna `Incluir`.

A V25.3 corrige esse comportamento e melhora a leitura de
apresentações grandes.

## Como a análise funciona

A pessoa continua clicando apenas em:

`Analisar apresentação completa`

Internamente, a NAVE:

1. lê o PDF completo para compreender projeto, narrativa, estratégia,
   conceito e jornada;
2. usa esse contexto global para organizar detalhadamente todos os
   slides em passagens automáticas;
3. combina os resultados em uma única revisão.

Não existe configuração “Slides por etapa” na interface.

## Atualização no GitHub

Substitua:

- `memory_models.py`
- `memory_prompts.py`
- `memory_extractor.py`
- `pages/10_Memoria.py`
- `README.md`

Depois:

`Manage app -> Reboot app`

Não é necessário executar SQL.

O patch não contém arquivos da pasta `assets`.
