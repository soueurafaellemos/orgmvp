# NAVE by VOE — V25.7

## Correção do salvamento da Memória

A mensagem genérica não permitia identificar se a falha acontecia na criação do projeto, nas tabelas da Memória, no armazenamento do PDF, nos slides ou nos conteúdos.

A V25.7 divide o salvamento em etapas visíveis e deixa erros não críticos — como um recorte ou slide isolado — sem cancelar o projeto inteiro.

## Atualização

Substitua no GitHub:

- `memory_db.py`
- `pages/10_Memoria.py`
- `README.md`

Depois:

`Manage app -> Reboot app`

Não é necessário executar SQL para atualizar da V25.6 para a V25.7.

Caso a nova verificação informe que a estrutura da Memória não existe no Supabase, execute novamente o arquivo original `supabase_patch_memoria_v1.sql`.

## Melhorias técnicas

- preflight das tabelas `memory_documents`, `memory_pages` e `memory_items`;
- verificação/criação do bucket privado `nave-memory`;
- upload com tentativas automáticas;
- PDF original tratado como parte crítica;
- slides e recortes tratados como complementos recuperáveis;
- imagens comprimidas em JPEG;
- conteúdos salvos em lotes;
- limpeza de projeto órfão em falhas;
- mensagem específica para a etapa interrompida.
