# NAVE by VOE — V25.7.2

## Correção do diagnóstico da Memória

O erro era:

`ValidationError: CoverageDiagnostic.mode — Field required`

A V25.7 compactava o diagnóstico antes de salvá-lo, mas não mantinha
o campo `mode`. Ao abrir o projeto, a interface tentava validar o
registro antigo como se ele tivesse a estrutura completa.

## O que a correção faz

- diagnósticos antigos sem `mode` passam a ser lidos como `memory`;
- novos diagnósticos preservam esse campo;
- uma estrutura de diagnóstico incompleta não derruba mais a página;
- o restante do projeto permanece visível normalmente.

## Atualização no GitHub

Substitua:

- `coverage_diagnostic.py`
- `coverage_diagnostic_ui.py`
- `memory_db.py`
- `pages/10_Memoria.py`
- `README.md`

Depois:

`Manage app -> Reboot app`

Não é necessário executar SQL.

Não é necessário excluir ou reenviar o projeto que já foi salvo.
O patch não contém arquivos da pasta `assets`.

A Fase 14 permanece pausada.
