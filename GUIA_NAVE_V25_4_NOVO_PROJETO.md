# NAVE by VOE — V25.4

## Novo fluxo da Memória

A área de upload agora serve exclusivamente para adicionar um
novo projeto final à Memória.

Não existe mais:

- selecionar projeto existente;
- atualizar projeto existente;
- escolher destino;
- reaproveitar projeto pelo nome.

Cada PDF cria um novo projeto.

## Análise de apresentações grandes

A V25.3 tentava enviar o PDF inteiro na primeira chamada para criar
o contexto global. Uma apresentação de 69 slides pode ultrapassar
limites de processamento ou falhar antes da leitura detalhada.

A V25.4 faz o fluxo mais seguro:

1. lê automaticamente todos os slides em passagens internas;
2. preserva a numeração original;
3. combina todos os conteúdos estruturados;
4. consolida o projeto completo ao final;
5. mostra tudo em uma única revisão.

Para a pessoa usuária, continua sendo um único botão:

`Analisar projeto completo`

Não existe configuração de lotes na interface.

## Atualização no GitHub

Substitua:

- `memory_extractor.py`
- `memory_db.py`
- `pages/10_Memoria.py`
- `README.md`

Depois:

`Manage app -> Reboot app`

Não é necessário executar SQL.

O patch não contém arquivos da pasta `assets`.
