# Organizador Universal de Pré-Produção — V4

Esta versão separa automaticamente três tipos de base:

- Base de brindes
- Base de soluções e ativações
- Base de projetos e briefings

## Novidades

### Imagem / fonte

Cada produto ou solução pode exibir a página original do PDF de onde os dados
foram extraídos. Nesta versão, o app mostra a página inteira. O recorte
automático exato da imagem do produto será uma evolução posterior.

### Fornecedores

O agente tenta extrair:

- nome do fornecedor
- site
- nome e cargo do contato
- e-mail
- telefone
- WhatsApp
- Instagram
- LinkedIn
- endereço
- observações

Quando a informação não existe no material, ela fica vazia e pode ser
complementada manualmente na aba Fornecedores.

### Soluções e ativações

Propostas de simuladores, software, fila virtual, cenografia, operação,
logística e outros serviços são direcionadas para uma base separada da base
de brindes.

## Atualização

Substitua no GitHub:

- models.py
- prompts.py
- gemini_extractor.py
- document_io.py
- exporters.py
- streamlit_app.py

O requirements.txt da V3 continua válido.


## V5 — correção e base de locais

### Correção

Corrige o erro `KeyError: 'confidence'` quando um documento não possui
contato de fornecedor. A tabela de contatos agora sempre cria a coluna de
confiança com valor padrão `0.0`.

### Base de locais e espaços

Foi incluído o modo:

- Locais / espaços

E a detecção automática agora pode direcionar documentos para:

- Base de locais e espaços

A estrutura inclui:

- nome e tipo do local
- endereço, cidade, estado, país e CEP
- link do site e mapa
- metragem e pé-direito
- capacidades em pé, sentada e auditório
- ambientes disponíveis
- estacionamento, acessibilidade e carga/descarga
- cozinha, energia, internet e audiovisual
- inclusões, exclusões e restrições
- disponibilidade e horários
- preço ou faixa de locação
- contatos
- imagem da página de origem


## V5.1 — extração de segurança para ativações

Quando a triagem reconhece um orçamento de ativação, mas o primeiro esquema
estruturado retorna zero soluções, o sistema agora executa automaticamente uma
segunda extração com um esquema simplificado.

A segunda tentativa prioriza a criação de uma linha para cada item comercial
identificado, como:

- sistema de pontuação
- fila virtual
- simulador de skate
- simulador BMX
- software
- cenografia
- operação
- logística

Os registros gerados pela extração de segurança recebem um aviso na aba
Alertas para revisão humana.


## V5.2 — qualidade de exportação

- Converte valores ausentes em `null` no JSON, sem `NaN`.
- Remove linhas completamente vazias do Excel e do JSON.
- Evita repetir condições gerais de negociação em todas as soluções.
- Explica na interface quando não há imagem porque a fonte foi texto colado.
- Para visualizar imagens, envie o PDF ou PowerPoint original junto com o
  conteúdo textual.


## V6 — integração com Supabase

A interface passa a testar a conexão com o Supabase e apresenta botões para:

- Salvar brindes na base
- Salvar soluções e ativações na base
- Salvar locais na base
- Salvar briefing e projeto na base

### Secrets do Streamlit

```toml
GEMINI_API_KEY = "sua-chave-gemini"
SUPABASE_URL = "https://seu-projeto.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_sua-chave"
```

A chave secreta do Supabase nunca deve ser enviada ao GitHub ou exibida no
front-end.

### Duplicidades

Durante a fase de testes, o app pode ignorar registros existentes por:

- produto: fornecedor + SKU ou nome;
- ativação: fornecedor + nome + projeto;
- local: operador + nome + cidade.

Cada salvamento também cria um registro em `imports` e associa os arquivos de
origem em `source_files`.


## V6.1 — correção de compatibilidade Streamlit / Starlette

Em 5 de agosto de 2026, o Starlette 1.4.0 alterou a assinatura interna do
GZipResponder. A versão atual do Streamlit ainda usa a assinatura anterior.

A dependência foi temporariamente fixada em:

```text
starlette==1.3.1
```

Após substituir o `requirements.txt`, faça um reboot completo do aplicativo
no Streamlit Community Cloud.


## V7 — consulta da base e recomendador embrionário

O Streamlit passa a ter páginas adicionais:

- Consultar base
- Nova recomendação

O recomendador:

1. interpreta o briefing com Gemini;
2. consulta a view `recommendation_candidates`;
3. filtra pelos tipos permitidos;
4. pontua relevância, budget, escala, prazo e localização;
5. explica a recomendação e os alertas;
6. pode salvar a consulta e seus resultados no Supabase.

Antes de usar, execute o arquivo:

```text
supabase_patch_recomendador_v1.sql
```

no SQL Editor do Supabase.


## V7.1 — preenchimento automático do formulário

Na página `Nova recomendação`, o usuário pode:

1. enviar briefing, e-mail, PDF, Word, PowerPoint, Excel ou texto;
2. clicar em `Ler briefing e preencher campos`;
3. revisar nome do projeto, objetivo, público, budget, quantidade, prazo,
   localização, data, tipos, atributos e restrições;
4. visualizar campos ausentes e perguntas abertas;
5. gerar a recomendação somente depois da revisão humana.

Os campos editados pelo usuário sempre têm prioridade sobre a interpretação
automática.


## V7.2 — leitura correta de Excel e arquivos Office

- Planilhas `.xlsx`, `.xls`, `.csv` e `.tsv` são convertidas localmente para
  texto tabulado antes da chamada ao Gemini.
- O nome original, as abas e a linha aproximada da planilha são preservados.
- Word `.docx`, PowerPoint `.pptx` e HTML também são convertidos para texto.
- Arquivos antigos `.doc`, `.ppt`, `.rtf` e `.odt` recebem uma mensagem clara
  solicitando conversão.
- O banco continua registrando o nome, MIME type e hash do arquivo original.


## V7.3 — Diagnóstico do Briefing

Após a leitura, a página `Nova recomendação` passa a apresentar:

- índice de completude de 0 a 100;
- status de prontidão;
- pendências críticas;
- pendências importantes;
- provocações de enriquecimento;
- responsável sugerido;
- impacto principal;
- indicação de bloqueio;
- próximo passo recomendado;
- pauta para atendimento em arquivo TXT.

O índice é calculado por regras transparentes sobre objetivo, público,
quantidade, budget, localização, data, prazo, escopo e restrições.

Os itens qualitativos combinam:
- leitura estruturada do Gemini;
- validações determinísticas do aplicativo.

O usuário pode corrigir os campos e clicar em `Atualizar diagnóstico` antes de
gerar a recomendação.


## V8 — histórico, versões, comparação e feedback

A página `Histórico de projetos` permite:

- consultar todos os projetos;
- visualizar versões salvas;
- comparar briefing, budget, público, prazo e diagnóstico;
- comparar itens que entraram, permaneceram ou saíram do ranking;
- reutilizar uma versão anterior como ponto de partida;
- registrar decisão e motivo por recomendação;
- formar histórico de favoritos, cotações, aprovações e rejeições.

Antes de usar a V8, execute no Supabase:

```text
supabase_patch_historico_projetos_v1.sql
```

Cada novo salvamento na página de recomendação passa a criar uma versão
incremental dentro do mesmo projeto.


## V9 — briefing adaptativo

A página de recomendação passa a detectar três perfis:

- Entrega simples
- Projeto único estruturado
- Programa multi-execução

Briefings simples continuam com os campos centrais e não são obrigados a
preencher operação, métricas ou praças.

Projetos estruturados liberam:

- agenda;
- requisitos operacionais;
- obrigatoriedades;
- entregáveis;
- métricas;
- produtos;
- referências.

Programas multi-execução também liberam uma tabela por praça, onda,
instituição ou unidade, contendo status, prioridade, data, produto, público,
budget e formato.

Antes de usar a V9, execute:

```text
supabase_patch_briefing_adaptativo_v1.sql
```

Os novos registros são salvos em tabelas normalizadas e também permanecem
no snapshot JSON da versão.


## V9.1 — correção de carregamento

O teste de conexão com Supabase deixou de ser executado automaticamente na abertura da página principal. O usuário pode acioná-lo pelo botão na barra lateral, evitando que instabilidades de rede deixem o aplicativo preso na tela de carregamento.


## V9.2 — proteção contra limite do Gemini

- Flash Lite passa a ser o modelo padrão na recomendação.
- Se outro modelo atingir o limite, o app tenta Flash Lite.
- Leituras idênticas são reaproveitadas durante a sessão.
- Erros 429 aparecem como aviso legível, sem traceback técnico.
- O app informa o tempo aproximado antes de uma nova tentativa.

## V9.3 - debriefing interno em PDF

A página de recomendação passa a gerar um PDF A4 inspirado no briefing interno padrão da agência, incluindo:

- identificação do job e atendimento;
- infos gerais com marcações;
- tipo de campanha;
- disciplinas da agência;
- briefing estruturado;
- entregáveis, métricas e execuções;
- logística, financeiro e budget;
- referências;
- diagnóstico, pendências e provocações para atendimento.

Briefings simples geram PDFs curtos; projetos estruturados e multi-execução incluem os blocos adicionais disponíveis.

### Observação visual

O PDF usa uma estrutura A4 inspirada no briefing interno padrão: identificação do job, blocos numerados, marcações de escopo, briefing, logística, financeiro e diagnóstico. Imagens incorporadas ao documento original ainda não são reproduzidas automaticamente nesta versão.


## V9.4 — abertura neutra do histórico

A página de histórico não abre mais automaticamente o primeiro projeto.

Ao entrar, o usuário vê:

- indicadores gerais;
- busca;
- seletor sem projeto pré-selecionado;
- tabela resumida de todos os projetos filtrados.

Os detalhes, versões e abas só aparecem depois da seleção consciente de um
projeto.


## V10 — recomendação por execução

Programas multi-execução agora geram:

- um ranking geral do projeto;
- um ranking separado para cada praça, unidade ou onda.

Cada ranking específico herda objetivo, público e diretrizes do projeto,
mas aplica os dados locais:

- cidade e estado;
- instituição e local;
- produto;
- data;
- quantidade;
- budget;
- formato.

Quando uma execução não possui budget próprio, o sistema não usa
automaticamente a verba global como verba daquela praça.

A geração por execução utiliza o motor local de pontuação depois que o
briefing já foi interpretado. Portanto, não consome uma nova chamada Gemini
para cada praça.

Antes de usar, execute:

```text
supabase_patch_recomendacao_por_execucao_v1.sql
```


## V11 — cobertura territorial e logística de fornecedores

A plataforma passa a registrar:

- cidade e estado-base;
- atendimento nacional;
- estados e cidades atendidos;
- equipes locais;
- política de deslocamento;
- estimativa padrão de deslocamento;
- política de frete;
- estimativa padrão de frete;
- dias adicionais de logística;
- necessidade de transporte de equipamento;
- necessidade de hospedagem.

A nova página `Cobertura de fornecedores` permite enriquecer manualmente
esses dados sem editar diretamente o Supabase.

O ranking passa a distinguir:

- fornecedor local;
- cobertura local confirmada;
- fornecedor regional;
- cobertura estadual;
- cobertura nacional;
- cobertura não cadastrada;
- fora da cobertura cadastrada.

Quando houver uma estimativa logística cadastrada, ela é somada ao valor
estimado antes da comparação com o budget.

Antes de usar a V11, execute:

```text
supabase_patch_cobertura_fornecedores_v1.sql
```


## V12 - identidade NAVE by VOE

A interface foi reposicionada como produto proprietário:

- nome oficial NAVE by VOE;
- Núcleo de Análise VOE para Experiências;
- tagline "Conectando briefing, repertório e decisão.";
- paleta azul-marinho, ciano, branco e cinza de superfície;
- sidebar azul-marinho inspirada nas aplicações digitais;
- símbolo e favicon próprios;
- navegação com linguagem de negócio;
- controles técnicos transferidos para Administração;
- toolbar do Streamlit em modo minimal;
- menu automático e rodapé técnico ocultos.

Esta atualização não exige alteração no Supabase, nos Secrets ou no
requirements.txt.


## V13 — white label técnico

- toolbar minimal;
- detalhes de erro ocultos;
- links técnicos de erro ocultos;
- navegação padrão do Streamlit desativada;
- linguagem técnica retirada das páginas de trabalho;
- área administrativa protegida por senha;
- perfis de processamento apresentados em linguagem de negócio;
- identificadores internos removidos da interface;
- títulos e mensagens padronizados;
- guia para alteração do subdomínio incluído no pacote.

Adicione aos Secrets:

```toml
NAVE_ADMIN_PASSWORD = "defina-uma-senha-forte"
```


## V13.1 — acesso privado em duas camadas

A NAVE agora exige:

```toml
NAVE_APP_PASSWORD = "senha-geral"
NAVE_ADMIN_PASSWORD = "senha-administrativa-diferente"
```

- A senha geral bloqueia todas as páginas.
- A Administração exige uma segunda senha.
- A sidebar só aparece depois do primeiro login.
- O botão "Sair da NAVE" encerra os dois níveis de acesso.
- Recomenda-se também tornar o app privado em Settings > Sharing
  no Streamlit Community Cloud.


## V13.2 — Home separada da organização

- A página inicial passa a ser exclusivamente institucional.
- Logo, significado, tagline, descriptor e os quatro pilares aparecem
  somente na Home.
- Organizar conhecimento passa a ser uma página operacional separada.
- A página de organização começa diretamente pelo cabeçalho e pelo upload.
- A sidebar ganha o item Início.


## V14 — Acervo visual e documental

Primeira implementação da camada visual da NAVE:

- estrutura genérica de mídias para brindes, ativações, locais,
  fornecedores e projetos;
- primeira experiência completa aplicada a locais;
- seleção de linha na Base de conhecimento;
- contador de imagens e documentos;
- galeria de imagens com acesso temporário;
- abertura de plantas, books, apresentações e fichas técnicas;
- upload de arquivos para locais;
- cadastro de links externos e tours virtuais;
- armazenamento privado;
- exclusão de materiais restrita a uma sessão administrativa;
- limite de 50 MB por arquivo.

Antes de usar, execute no Supabase:

`supabase_patch_acervo_visual_v1.sql`

O bucket privado `nave-media` é preparado automaticamente no primeiro
upload ou pelo botão da Administração.
