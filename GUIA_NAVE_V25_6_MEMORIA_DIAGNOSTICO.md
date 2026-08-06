# NAVE by VOE — V25.6

## Memória decupada e diagnóstico universal

Esta versão corrige duas fragilidades diferentes:

1. apresentações podiam ter slides relevantes omitidos pela resposta do
   modelo, sem que a plataforma percebesse;
2. uploads podiam conter informações úteis que não apareciam na NAVE, sem
   indicar se o problema era de extração ou da estrutura de dados.

## 1. Nova regra da Memória

Antes de chamar a IA, a NAVE cria um inventário de todos os slides.

Para cada slide, registra:

- número da página;
- texto detectado;
- presença de imagens;
- seção provável;
- possíveis itens distintos;
- indicação de capa, divisória ou encerramento.

A resposta da IA é comparada com esse inventário.

### O que não pode mais acontecer

Um slide relevante não pode desaparecer porque a IA não o devolveu.

Se a resposta omitir um slide ou um item, a NAVE cria uma ficha de
**Cobertura automática**, preservando:

- título sugerido;
- seção provável;
- texto disponível;
- número do slide;
- slide completo como imagem de consulta.

Essas fichas ficam visíveis na revisão e podem ser corrigidas ou desmarcadas.

### Slides com vários conteúdos

A NAVE procura conteúdos distintos dentro do mesmo slide. Exemplos:

- caneca;
- tiara;
- chapéu;
- bottons;
- opções de uniforme;
- diferentes ativações;
- diferentes ambientes.

Quando identifica vários itens, cria fichas separadas.

## 2. Diagnóstico de cobertura do projeto

Na revisão da Memória aparecem:

- cobertura estimada;
- slides relevantes cobertos;
- registros estruturados;
- conteúdo que ficou de fora;
- pontos parcialmente estruturados;
- possíveis evoluções da NAVE.

O diagnóstico diferencia:

- **Aprimorar extração:** a área já existe, mas a leitura falhou;
- **Adicionar campo:** existe uma informação recorrente que não cabe nos
  campos atuais;
- **Adicionar área:** o conteúdo representa uma dimensão realmente nova;
- **Reclassificar:** a informação foi salva no lugar errado;
- **Revisar manualmente:** a fonte está ambígua.

## 3. Diagnóstico para todos os uploads

A mesma auditoria passa a existir em **Upload de Conhecimento** para:

- brindes e produtos;
- soluções e ativações;
- fornecedores;
- locais e espaços;
- planilhas;
- catálogos;
- briefings e projetos;
- documentos mistos encaminhados para uma das áreas suportadas.

O diagnóstico é exibido após a extração e antes do salvamento.

Ele também é incluído:

- na planilha Excel exportada;
- no JSON exportado;
- no histórico da importação salvo no Supabase.

## 4. Backlog de evolução da plataforma

Em:

`Prontidão da base -> Evoluções sugeridas`

A NAVE reúne os diagnósticos de uploads futuros e mostra:

- quantidade de uploads auditados;
- lacunas identificadas;
- lacunas críticas;
- sugestões de novos campos, tipos ou áreas;
- frequência de cada sugestão;
- documentos que originaram a sugestão;
- exemplos de evidência.

Assim, uma ocorrência isolada não precisa virar imediatamente uma nova área.
Quando a mesma necessidade aparece em diferentes projetos, planilhas ou
fornecedores, ela ganha prioridade no backlog.

## 5. Atualização no GitHub

Adicione:

- `coverage_diagnostic.py`
- `coverage_diagnostic_ui.py`

Substitua:

- `memory_models.py`
- `memory_prompts.py`
- `memory_extractor.py`
- `pages/10_Memoria.py`
- `pages/1_Organizar_Conhecimento.py`
- `base_quality.py`
- `pages/8_Qualidade_da_Base.py`
- `supabase_db.py`
- `exporters.py`
- `README.md`

Depois:

`Manage app -> Reboot app`

## 6. Supabase

Não é necessário executar SQL.

Os diagnósticos usam campos JSON já existentes:

- `imports.classification` para Upload de Conhecimento;
- `memory_documents.raw_data` para Memória.

A aba Evoluções sugeridas lê esses históricos e consolida as sugestões.

## 7. Projeto já salvo com poucos itens

A nova cobertura vale para análises feitas depois da instalação.

Para corrigir o projeto salvo pela versão anterior:

1. exclua a apresentação incompleta em **Documentos & Versões**;
2. adicione novamente o PDF em **Adicionar novo projeto**;
3. revise o diagnóstico e as fichas antes de salvar.

O patch não altera arquivos da pasta `assets`.
