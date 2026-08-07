# NAVE by VOE — V28.0.3.4

## Correção — ingestão resiliente de Locais

Este patch corrige os dois erros observados ao processar o Volume 03 de Locais:

1. JSON de `VenueBatch` truncado pelo Gemini (`EOF while parsing a string`);
2. `source_page` chegando ao histórico de enriquecimento como texto decimal, por exemplo `"2.0"`, apesar de a coluna no Supabase ser inteira.

## O que muda

### 1. Retry compacto automático para Locais

Quando uma extração `VenueBatch` falha especificamente por JSON truncado/inválido, a NAVE repete uma única vez o mesmo lote com regras de resposta compacta:

- evidência limitada;
- descrições curtas;
- listas limitadas;
- sem transcrição de rodapés, URLs repetidas ou páginas fora do lote;
- páginas de capa/índice/créditos podem retornar `venues=[]`.

Outros tipos de documento não ganham retry automático nesta versão.

### 2. Página de origem normalizada

Antes de registrar `knowledge_enrichment_events`, valores como:

- `"2.0"` → `2`;
- `2.0` → `2`;
- `"2.5"` → `null` em vez de provocar erro de inteiro no Postgres.

A normalização reaproveita a função `_integer_or_none` que já existe no `supabase_db.py` atual.

## GitHub

### Adicionar

- `nave_runtime_fixes.py`
- `tests/test_nave_runtime_fixes_v28_0_3_4.py`

### Substituir

- `nave_table_utils.py`

### Excluir

- nenhum arquivo

Depois faça:

`Manage app → Reboot app`

## Supabase

**Não executar SQL.**

O schema atual já está correto; o problema estava na normalização do valor antes do insert do histórico.

## Teste operacional recomendado

Após o reboot:

1. abra `Upload de Conhecimento`;
2. envie novamente o PDF do Volume 03;
3. organize como `Locais e espaços`;
4. confirme que a extração ultrapassa a antiga página/lote 13 sem `EOF while parsing`;
5. salve/enriqueça a base;
6. confirme que não aparece mais `invalid input syntax for type integer: "2.0"`.

Se o Gemini truncar a primeira resposta, o retry compacto acontece automaticamente e a interface pode levar alguns segundos extras naquele lote.
