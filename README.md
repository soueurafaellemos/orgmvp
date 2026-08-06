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


## V14.1 — Ajuste de legibilidade dos botões

- botões com fundo azul passam a usar texto branco;
- hover dos botões principais mantém contraste;
- link buttons passam a seguir o mesmo padrão visual dos botões.


## V14.2 — seleção de imagem principal

- substitui o checkbox instável por uma escolha Sim / Não;
- a escolha aparece somente para tipos de imagem;
- cada tipo de imagem possui estado independente;
- “Imagem principal” inicia com Sim;
- fotos de galeria e mapas iniciam com Não;
- formatos aceitos ficam visíveis abaixo do campo de upload.


## V14.3 — download do acervo

- imagens armazenadas passam a ter o botão “Baixar imagem”;
- documentos armazenados passam a ter “Abrir” e “Baixar”;
- o download usa endereço temporário e protegido;
- links externos continuam com “Abrir” e não oferecem download;
- não exige nova alteração no banco.


## V14.4 — padronização visual dos botões

- todos os botões passam a seguir o mesmo padrão visual;
- estado padrão: azul escuro com texto branco;
- hover: azul claro da marca com texto escuro;
- estado desabilitado: fundo cinza claro com texto cinza;
- ajuste aplicado a botões comuns, primários, downloads e links.


## V15 — Fase 5D: consulta visual e ficha completa

- miniatura de capa na tabela em linha de 64 px;
- imagem visual com referência aproximada de 56 × 56 px;
- filtro por itens com ou sem mídia;
- ficha completa por tipo de registro;
- campos vazios exibidos como “Não informado”;
- informações agrupadas por contexto;
- leitura do registro completo diretamente da tabela original;
- imagens e arquivos disponíveis para brindes, ativações e locais;
- upload de acervo expandido para os três tipos;
- exclusão de mídia continua restrita à Administração;
- não exige novo SQL.


## V16 — Fase 6: enriquecimento inteligente

- encontra brindes, ativações e locais já cadastrados;
- preenche automaticamente campos vazios;
- trata “Não informado” como campo vazio;
- une listas sem repetir valores;
- preserva valores conflitantes no modo recomendado;
- permite priorizar o arquivo mais recente;
- permite adicionar somente itens novos;
- registra histórico completo de cada enriquecimento;
- mostra diferenças encontradas após o salvamento;
- exibe histórico de enriquecimento na ficha do item;
- evita duplicar custos iguais em ativações;
- fornecedores passam a ser enriquecidos sem apagar dados existentes.

Antes de usar, execute:

`supabase_patch_enriquecimento_inteligente_v1.sql`


## V17 — Fase 6.1 integrada à Fase 6

- enriquecimento textual e estrutural da V16 incluído;
- extração automática de imagens representativas de PDFs;
- recorte por coordenadas visuais retornadas pela leitura inteligente;
- fallback por blocos de imagem embutidos no PDF;
- associação da imagem ao brinde, ativação ou local existente;
- primeira imagem vira capa quando o item ainda não possui imagem principal;
- deduplicação por SHA-256;
- rastreabilidade de arquivo, página, recorte, método e confiança;
- recortes ambíguos ficam pendentes para upload manual;
- use apenas `supabase_patch_fase_6_1_completa_v1.sql`; não execute antes o SQL isolado da V16.


## V17.1 — restauração dos controles de execução

- toolbar superior volta a aparecer em modo minimal;
- indicador de execução volta a aparecer;
- botão Stop volta a ficar disponível durante processamentos;
- menu principal, deploy e elementos técnicos desnecessários
  continuam ocultos;
- não exige SQL nem alteração no Supabase.


## V18 - consulta otimizada e exportação de possibilidades

- esclarece que oito páginas é o tamanho do lote, não o limite
  do documento;
- opção “Analisar o documento inteiro” ativada por padrão;
- configurações de faixa e lote movidas para área avançada;
- cache de dois minutos para contadores e listagem;
- paginação com 25, 50 ou 100 itens;
- URLs de miniaturas geradas em lote;
- contagens de mídia completas carregadas somente quando o filtro
  de acervo é utilizado;
- seleção múltipla na tabela;
- geração de PDF com várias possibilidades;
- imagem principal incluída no PDF quando disponível;
- exclusão de imagem ou arquivo disponível com confirmação;
- não exige novo SQL.


## V18.1 - identidade na tela de login

- o logo oficial NAVE by VOE passa a aparecer na tela de acesso;
- o logo é carregado do asset vetorial já utilizado pela interface;
- significado e tagline permanecem abaixo da assinatura;
- a atualização faz parte do mesmo pacote da V18.


## V18.2 — tela de login centralizada

- composição do login centralizada;
- logo reduzido e com largura controlada;
- significado e tagline aproximados do formulário;
- formulário estilizado diretamente, sem wrapper HTML quebrado;
- botão azul-marinho com texto branco;
- hover ciano com texto escuro;
- adaptação para desktop e telas menores;
- não exige SQL.


## V19 — Fase 6.2: correspondência inteligente

- mantém a correção da tela de login da V18.2;
- reconhece nomes equivalentes mesmo com pequenas variações;
- usa fornecedor, projeto, cidade, SKU, categoria e tipo como
  proteções adicionais;
- correspondências de alta confiança enriquecem o cadastro existente;
- correspondências intermediárias entram em uma fila de revisão;
- o registro novo e suas imagens permanecem preservados até a decisão;
- revisão protegida pela senha administrativa;
- permite unir cadastros ou confirmar que são itens distintos;
- ao unir, transfere imagens, arquivos e custos de ativações;
- remove mídias repetidas;
- mantém uma trilha da decisão na tabela de revisão.

Antes de usar, execute:

`supabase_patch_correspondencia_inteligente_v1.sql`


## V20 — Fase 7: shortlist visual de recomendações

- mantém todas as fases anteriores;
- corrige definitivamente o alinhamento do login;
- usa um SVG exclusivo e recortado para a tela de acesso;
- logo, significado, tagline e formulário ficam na mesma coluna;
- mostra a imagem principal dentro dos cards de recomendação;
- permite adicionar recomendações a uma shortlist;
- apresenta uma tabela comparativa da seleção;
- gera PDF da shortlist com imagem, justificativa e cobertura;
- permite incluir ou ocultar valores;
- permite incluir ou ocultar a pontuação da NAVE;
- não exige novo SQL.


## V20.1 — login resiliente

- corrige o FileNotFoundError do logo de login;
- tenta usar primeiro o logo recortado;
- usa o logo principal automaticamente como alternativa;
- usa assinatura textual caso nenhum asset esteja disponível;
- a ausência de um arquivo visual não derruba mais o aplicativo;
- não exige SQL.


## V21 — Fase 8: qualidade e prontidão da base

- painel de prontidão da base;
- avaliação de brindes, ativações, locais e fornecedores;
- pontuação de completude de 0 a 100;
- identificação de registros prontos para recomendação;
- lista priorizada de cadastros que precisam ser enriquecidos;
- campos críticos e campos complementares ausentes;
- indicadores de mídia, preço e logística;
- visão agregada por tipo de cadastro;
- filtro, busca e exportação do diagnóstico em CSV;
- acesso direto para organizar documentos e consultar a base;
- não altera ou substitui o SVG de login corrigido pelo usuário;
- não exige novo SQL.


## V22 — Fase 9: navegação unificada

- “Organizar conhecimento” passa a se chamar
  “Upload de Conhecimento”;
- botão principal passa a ser “Fazer Upload”;
- novo nome aplicado à sidebar, Home e painel de prontidão;
- Projetos passa a usar tabela com seleção de linha;
- filtros por busca e status nos projetos;
- paginação dos projetos;
- resumo do projeto selecionado antes das versões;
- Fornecedores passa a usar tabela com seleção de linha;
- filtros por busca e cobertura nos fornecedores;
- paginação dos fornecedores;
- detalhes e formulário aparecem somente após selecionar a linha;
- o patch não contém arquivos de logo;
- não exige novo SQL.


## V23 — Fase 10: curadoria e edição da base

- edição direta de brindes, ativações, locais e fornecedores;
- status: não revisado, em revisão, validado,
  precisa de atualização e arquivado;
- responsável e fonte da revisão;
- data da próxima revisão;
- observações internas;
- histórico campo a campo de todas as alterações;
- arquivamento retira o cadastro das recomendações;
- filtro de curadoria na Base e em Fornecedores;
- exclusão definitiva protegida pela senha administrativa;
- exclusão bloqueada quando houver vínculos;
- acesso direto aos itens prioritários pelo painel de prontidão;
- o patch não contém arquivos de logo.

Antes de usar, execute:

`supabase_patch_curadoria_base_v1.sql`


## V23.1 — curadoria simplificada para acesso compartilhado

- remove status de validação da interface;
- remove responsável pela revisão;
- remove próxima revisão;
- remove responsável do histórico exibido;
- mantém data automática das alterações;
- mantém fonte da informação;
- mantém observações internas;
- mantém situação Ativo / Arquivado;
- simplifica os filtros da Base e de Fornecedores;
- não exige novo SQL;
- não contém arquivos de logo.


## V24 — Fase 11: taxonomia e padronização

- dicionário canônico para brindes, ativações e locais;
- centenas de variações, abreviações, traduções e erros comuns;
- Photo-op reconhece photoop, photopp, phopp,
  photo opportunity, espaço instagramável e termos relacionados;
- preserva nome, descrição e documento de origem;
- padroniza categoria e enriquece tags;
- busca reconhece qualquer alias da mesma família;
- recomendações usam a categoria canônica;
- correspondência de duplicidades entende categorias equivalentes;
- novas extrações recebem instruções de taxonomia;
- edição manual usa listas canônicas;
- página administrativa para acrescentar aliases personalizados;
- auditoria e padronização da base existente;
- mudanças ficam registradas no histórico de curadoria;
- o patch não contém arquivos de logo.

Antes de usar, execute:

`supabase_patch_taxonomia_nave_v1.sql`


## V24.1 — Taxonomia pesquisada e hierárquica

- evolui diretamente a V24 instalada;
- preserva aliases personalizados já cadastrados;
- separa formato de evento, formato de experiência, mecânica,
  tecnologia, objetivo e serviço de produção;
- amplia categorias de brindes;
- amplia tipos e atributos de espaços;
- registra fonte, mercado, tipo e peso das referências;
- diferencia fontes setoriais de sinais visuais e sociais;
- mostra a fundamentação dos conceitos dentro da NAVE;
- acrescenta fonte opcional aos aliases criados pela VOE;
- preserva nomes, descrições, documentos, imagens e evidências;
- o patch não contém arquivos da pasta assets.

Antes de usar, execute:

`supabase_patch_taxonomia_pesquisada_v24_1.sql`


## V25 — Fase 12: Memória

- novo menu principal “Memória”;
- módulo isolado da Base de conhecimento;
- upload de apresentações estratégicas em PDF;
- seleção de projeto existente ou criação de projeto;
- preservação do PDF original;
- preservação dos slides completos usados como contexto;
- extração de imagens para galerias;
- revisão dos itens antes de salvar;
- classificação em estratégia, cenografia, ativações, brindes,
  jornada, comunicação, conteúdo, parceiros e legado;
- abas opcionais aparecem somente quando possuem conteúdo;
- status interno: referência, proposto, opção, recomendado,
  aprovado, descartado, executado ou não identificado;
- revisão manual da classificação na própria ficha;
- versões e documentos consultáveis por projeto;
- exclusão de apresentação protegida pela senha administrativa;
- nenhuma tabela da Memória alimenta produtos, ativações,
  locais, fornecedores ou recomendações;
- o patch não contém arquivos da pasta assets.

Antes de usar, execute:

`supabase_patch_memoria_v1.sql`


## V25.1 — análise integral e cadastro automático

- remove a configuração “Slides por etapa”;
- envia a apresentação inteira ao Gemini em uma única análise;
- preserva a leitura da narrativa completa do início ao fim;
- ao criar um projeto, exige somente o PDF;
- identifica automaticamente nome do projeto, cliente, evento,
  título da apresentação e versão;
- todos os dados identificados ficam editáveis antes de salvar;
- projeto, cliente e evento podem ser editados depois de salvos;
- título, versão e situação da apresentação podem ser editados
  depois de salvos;
- não exige novo SQL;
- não altera o isolamento da Memória;
- não contém arquivos da pasta assets.


## V25.3 — Memória resiliente

- corrige KeyError quando uma análise retorna zero itens;
- tabelas vazias preservam todas as colunas esperadas;
- a interface mostra uma mensagem recuperável em vez de travar;
- mantém um único clique para analisar a apresentação completa;
- primeira passagem lê o PDF inteiro e cria contexto global;
- passagens internas automáticas extraem todos os detalhes dos slides;
- o contexto global é enviado a cada passagem detalhada;
- não existe controle de lotes na interface;
- não exige novo SQL;
- não altera o isolamento da Memória;
- preserva o menu em ordem alfabética;
- não contém arquivos da pasta assets.


## V25.4 — Novo projeto e análise de apresentações grandes

- remove totalmente a seleção de projeto existente da Memória;
- a aba passa a se chamar “Adicionar novo projeto”;
- cada PDF cria sempre um novo projeto;
- nenhum projeto existente é pesquisado, atualizado ou reaproveitado;
- o envio representa a apresentação final já enviada ao cliente;
- remove a chamada inicial com o PDF completo, que podia falhar
  em apresentações grandes;
- todos os slides continuam sendo analisados automaticamente;
- os resultados de todos os slides são consolidados ao final em uma
  visão global única do projeto;
- falha em uma passagem não interrompe automaticamente as demais;
- corrige importações ausentes de json e Path na V25.3;
- não exige novo SQL;
- preserva o menu em ordem alfabética;
- não altera o isolamento da Memória;
- não contém arquivos da pasta assets.

## V25.6 — Memória decupada e diagnóstico universal

### Memória

- cria um inventário obrigatório de todos os slides antes da extração;
- nenhuma página pode desaparecer silenciosamente;
- capas, divisórias e encerramentos recebem justificativa de exclusão;
- todo slide relevante precisa gerar ao menos uma ficha;
- slides com vários itens podem gerar várias fichas;
- itens conhecidos em listas, como diferentes brindes, ambientes e
  ativações, são auditados individualmente;
- quando a resposta da IA omite um slide ou item, a cobertura automática
  preserva o conteúdo usando o slide completo como imagem;
- a revisão identifica se o item veio da IA ou da cobertura automática;
- mostra páginas relevantes cobertas, cobertura percentual e distribuição
  por seção;
- mantém Estratégia, Cenografia & Ambientes, Ativações & Experiências,
  Brindes & Materiais, Jornada & Operação, Comunicação & Desdobramentos,
  Conteúdo & Agenda, Parceiros & Cotas e PR, ESG & Legado;
- continua totalmente isolada da Base de conhecimento e recomendações.

### Diagnóstico universal de cobertura

- todo novo upload compara o conteúdo da fonte com o que a NAVE estruturou;
- funciona para catálogos, planilhas, brindes, fornecedores, ativações,
  locais, briefings, projetos e Memória;
- diferencia conteúdo não extraído de informação que realmente não possui
  campo ou área na plataforma;
- sugere aprimorar extração, adicionar campo, adicionar tipo, adicionar área,
  reclassificar ou revisar manualmente;
- o diagnóstico aparece antes do salvamento;
- o diagnóstico entra nos arquivos Excel e JSON exportados;
- nos uploads da Base de conhecimento, o diagnóstico fica armazenado no
  histórico da importação;
- na Memória, fica preservado no documento do projeto;
- a página Prontidão da base ganha a aba Evoluções sugeridas, que reúne e
  consolida lacunas recorrentes de todos os uploads;
- não exige novo SQL;
- preserva a ordem de menu da V25.5;
- o patch não contém arquivos da pasta assets.


## V25.7 — salvamento resiliente da Memória

- adiciona verificação automática das tabelas e do bucket antes de salvar;
- informa em qual etapa o salvamento foi interrompido;
- remove projetos órfãos quando o primeiro salvamento falha;
- usa o status seguro `rascunho` para projetos criados pela Memória;
- reduz o JSON duplicado armazenado no documento;
- comprime slides e recortes como JPEG;
- salva conteúdos em lotes e tenta novamente item a item quando necessário;
- falha em um slide ou recorte deixa de cancelar o projeto inteiro;
- preserva o PDF original como fonte principal;
- mantém a análise na tela em caso de falha;
- não exige novo SQL;
- não altera a Base de conhecimento nem o motor de recomendações;
- não contém arquivos da pasta assets.


## V25.7.2 — Diagnóstico retrocompatível

- corrige `ValidationError` ao abrir diagnósticos antigos da Memória;
- reconhece registros legados que não possuem o campo `mode`;
- usa `memory` como contexto explícito dentro da página Memória;
- novos salvamentos preservam `mode` no `raw_data`;
- um diagnóstico inválido não interrompe mais todo o projeto;
- apresentações, cards, imagens e documentos permanecem acessíveis;
- não exige SQL;
- não altera a Fase 14;
- não contém arquivos da pasta `assets`.
