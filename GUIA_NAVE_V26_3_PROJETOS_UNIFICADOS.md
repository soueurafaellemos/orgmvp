# NAVE by VOE — V26.3

## Projetos e Memória unificados

A Memória deixa de ser uma área independente no menu principal.

O menu passa a ter:

- Home
- Upload de Conhecimento
- Base de Conhecimento
- Analisar e Recomendar
- Fornecedores
- Projetos

## Lista única

A página Projetos reúne registros que tenham:

- briefing ou recomendações;
- apresentação final;
- conteúdos da Memória;
- ou ambos.

A tabela mostra:

- projeto;
- cliente;
- evento;
- versões de briefing/recomendação;
- apresentações finais;
- conteúdos;
- última atualização.

## Hub do projeto

Depois de selecionar uma linha, aparecem:

### Briefing & Recomendações

Abre o histórico já existente de:

- briefing;
- diagnóstico;
- recomendações gerais;
- recomendações por execução;
- comparação de versões;
- feedbacks do recomendador.

### Memória do Projeto

Abre:

- estratégia;
- cenografia;
- ativações;
- brindes;
- jornada;
- comunicação;
- resultados e aprendizados;
- orçamento e aderência;
- documentos e versões.

### Adicionar apresentação final

O PDF passa a ser anexado ao projeto selecionado.

Nenhum novo projeto é criado durante esse upload.

## Correção do XLSM

A mensagem:

`invalid_mime_type`

é corrigida com um novo bucket privado:

`nave-project-costs`

O bucket não usa uma lista frágil de MIME types.

- XLSX, XLSM, XLS e CSV continuam validados pela extensão;
- macros nunca são executadas;
- arquivos antigos continuam sendo lidos do bucket original;
- não é necessário alterar ou excluir o bucket anterior.

## Atualização no GitHub

Adicione:

- `project_hub.py`
- `pages/11_Briefing_e_Recomendacoes.py`

Substitua:

- `branding.py`
- `streamlit_app.py`
- `pages/4_Historico_de_Projetos.py`
- `pages/10_Memoria.py`
- `memory_learning_db.py`
- `memory_learning_ui.py`
- `README.md`

Depois:

`Manage app -> Reboot app`

Não é necessário executar SQL.

## Teste recomendado

1. Abra Projetos.
2. Confirme que Chambinho e Oktoberfest aparecem na lista única.
3. Selecione Chambinho.
4. Abra Memória do Projeto.
5. Abra Orçamento & Aderência.
6. Envie novamente a planilha XLSM.
7. Confirme que ela é salva sem erro de MIME.
8. Volte ao hub.
9. Use Adicionar apresentação final em um projeto existente e confirme
   que a lista não cria uma segunda linha.

## Próxima etapa

Depois da validação desta versão, a Fase 14.1 adicionará:

- upload do briefing inicial;
- demandas e obrigatoriedades;
- matriz briefing × proposta × custo × resultado;
- diagnóstico de aderência;
- evidências e lacunas por item.
