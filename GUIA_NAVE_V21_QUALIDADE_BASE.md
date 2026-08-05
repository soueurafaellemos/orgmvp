# NAVE by VOE — V21

## Fase 8 — Qualidade e prontidão da base

Esta versão ajuda a amadurecer a base antes de validar o motor
de recomendações.

## Atualização no GitHub

Adicione:

- `base_quality.py`
- `pages/8_Qualidade_da_Base.py`

Substitua:

- `supabase_db.py`
- `branding.py`
- `README.md`

Depois faça:

`Manage app -> Reboot app`

Não é necessário executar SQL.

O patch não contém arquivos de logo e não substitui o SVG de login
corrigido manualmente.

## Novo menu

Abra:

**Qualidade da base -> Prontidão da base**

## O que o painel mostra

- prontidão média;
- quantidade de cadastros avaliados;
- registros prontos para recomendação;
- registros prioritários;
- possíveis duplicidades pendentes;
- cobertura por tipo de cadastro;
- percentual com mídia;
- percentual com preço ou logística;
- campos mais ausentes.

## Status

### Pronto para recomendação

Pontuação a partir de 70 e nenhum campo crítico ausente.

### Em evolução

Pontuação a partir de 50, mas ainda com lacunas relevantes.

### Prioritário

Pontuação inferior a 50.

## Uso recomendado

1. Abra a lista de prioridades.
2. Filtre por brindes, ativações, locais ou fornecedores.
3. Identifique os campos críticos mais frequentes.
4. Adicione documentos que preencham essas lacunas.
5. Clique em **Atualizar diagnóstico**.
6. Acompanhe a evolução da prontidão.
