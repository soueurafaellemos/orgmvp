# NAVE by VOE · V28.7.2B1 — Strategy Evidence Recovery

## Diagnóstico

A V28.7.2B materializou Creative Platform corretamente, mas Strategy ficou vazia no Golden Chambinho.

O diagnóstico read-only confirmou que a evidência estratégica existe e está current:

- proposal page 5: `MEMÓRIA AFETIVA CONEXÃO PRESENÇA E ATENÇÃO PONTOS DE PARTIDA ...`
- proposal page 9: `NOSTALGIA ... vamos nos apropriar desse território ...`
- briefing DOCX: `Pilares:` em um parágrafo e os conteúdos dos pilares em parágrafos seguintes.

A falha estava no formato da Evidence, não na ausência documental:

1. o extrator histórico de PDF persiste uma Evidence Unit por página com `content_text` achatado em uma única linha;
2. o parser V28.7.2B é propositalmente sensível a headings/linhas para não inventar Strategy;
3. portanto os três títulos de `PONTOS DE PARTIDA` e o título `NOSTALGIA` deixaram de ser reconhecidos;
4. no DOCX, `Pilares:` fica separado dos parágrafos seguintes e o recovery adjacente da B cobria objetivos estratégicos, mas ainda não cobria grupos explícitos de `Pilares` / `Pontos de partida`.

## O que muda

### PDF semantic-read recovery

Para Source Assets PDF já armazenados, a B1 reabre o mesmo master no storage e recupera as linhas visuais da página com PyMuPDF.

Isso:

- NÃO cria nova Evidence Unit;
- NÃO altera a Evidence histórica;
- NÃO reprocessa o master;
- mantém a observation vinculada à Evidence Unit original da página;
- registra `semantic_text_recovery_method = stored_pdf_layout_lines`.

O recovery só é usado quando o texto recuperado possui sobreposição suficiente com o `content_text` já persistido. Se o master não puder ser recuperado ou o conteúdo parecer incompatível, o pipeline continua fail-closed usando o texto antigo.

### DOCX explicit-group recovery

Quando a Evidence contém um heading explícito em parágrafo separado, como:

- `Pilares:`
- `Pontos de partida`

os parágrafos seguintes podem ser materializados como Strategy source-explicit enquanto permanecerem dentro do grupo documental.

Quando a linha possui estrutura `rótulo – explicação`, apenas o rótulo original vira `title`; a explicação permanece como `statement`.

## Arquivos a substituir no GitHub

- `project_core_semantic_extractor.py`
- `tests/test_v28_7_2b_core_extractor.py`

## SQL

NÃO.

A estrutura V28.7.2B já instalada continua válida.

## Reboot

SIM.

## Masters

NÃO reprocessar e NÃO reenviar.

## Reteste Chambinho

Depois do reboot:

1. abrir o Golden canônico Festivalzinho Chambinho;
2. clicar uma vez em `Reconciliar Core Semantic Domains · V28.7.2B`;
3. verificar o painel;
4. rodar novamente `NAVE_V28_7_2B_VERIFY_GOLDEN_CHAMBINHO.sql`;
5. exportar o CSV e enviar para auditoria.

### Resultado esperado

A 7.2A deve continuar intacta.

Na B, esperamos ao menos:

- Strategy > 0;
- `NOSTALGIA` como `territory`, source-explicit;
- `MEMÓRIA AFETIVA` como `strategic_principle`, source-explicit;
- `CONEXÃO` como `strategic_principle`, source-explicit;
- `PRESENÇA E ATENÇÃO` como `strategic_principle`, source-explicit;
- Creative Platform `A CASA CHAMBINHO MAIS NOSTALGICA DE TODAS` preservada;
- relação Strategy → Creative tipada e grounded;
- Experience Architecture = 0 e Journey Moments = 0 continuam aceitáveis no Chambinho;
- nenhuma Journey genérica deve ser inventada;
- Graph V28.6 continua congelado;
- migration_mode continua `legacy_shadow`.

## Validação local

- `py_compile`: PASS
- testes focados V28.7.2B: 24 PASS
- B + regressões A/A1/D/D2 selecionadas: 49 PASS
- nenhum nome Golden foi codificado no runtime da correção.

## Cutover

NÃO.

A V28.7.2B continua em shadow até Chambinho e JOVI passarem os gates sem regressão.
