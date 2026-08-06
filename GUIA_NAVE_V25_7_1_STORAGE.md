# NAVE by VOE — V25.7.1

## Correção do Storage da Memória

O log mostrou que a falha ocorria antes do upload do PDF, durante a criação do bucket privado `nave-memory`.

A aplicação tentava criar o bucket com limite próprio de 100 MB. O Supabase rejeita um limite de bucket superior ao limite global configurado no projeto, devolvendo erro 413.

A V25.7.1:

- cria o bucket privado sem impor limite próprio;
- herda o limite global do Storage do projeto;
- mantém a validação de tipo e tamanho na aplicação;
- mostra uma mensagem específica caso o PDF realmente ultrapasse o limite global durante o upload.

## Atualização

Substitua somente:

- `memory_db.py`

Depois:

`Manage app -> Reboot app`

Não execute SQL.

Após reiniciar, analise e salve novamente o projeto.

## Alternativa imediata pelo Supabase

Também é possível criar manualmente no Storage um bucket chamado exatamente `nave-memory`, privado, deixando a restrição de tamanho desativada ou abaixo do limite global do projeto. Com o bucket já existente, a aplicação não tenta criá-lo.
