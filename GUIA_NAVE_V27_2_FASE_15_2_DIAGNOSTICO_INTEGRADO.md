# NAVE by VOE — V27.2

## Fase 15.2 — Diagnóstico Integrado e Matriz de Execução

Esta fase corrige a leitura fragmentada da V27.1 e transforma o workspace em um sistema realmente cumulativo.

A NAVE passa a cruzar automaticamente:

`briefing → apresentação → planilha de custos → pós-evento → feedbacks`

## O que muda

### 1. Visual horizontal

Cenografia, ativações, brindes e press kits deixam de aparecer em uma grade de blocos.

Cada entrega passa a ocupar uma linha horizontal:

- imagem ou slide à esquerda;
- título, situação, descrição e custos à direita;
- ficha completa abaixo;
- leitura melhor em apresentações com forte conteúdo visual.

Estratégia e conceito continuam textuais.

### 2. Recuperação de cenografia

A classificação não depende mais apenas do campo original `section_key`.

A NAVE considera:

- título;
- resumo;
- descrição;
- tipo do item;
- tags;
- evidências;
- inventário da apresentação;
- título e seção sugeridos para cada página.

Também reconhece vocabulário como:

- cenografia;
- ambientação;
- ambiente;
- estande;
- fachada;
- palco;
- lounge;
- mobiliário;
- marcenaria;
- implantação;
- layout;
- render;
- Casa Chambinho.

Quando um slide visual existe, mas não possui ficha estruturada, a V27.2 cria uma ficha visual vinculada ao projeto. Isso permite que a cenografia seja exibida, relacionada a custos e incluída no diagnóstico.

### 3. Custos dentro das entregas

A NAVE passa a sugerir automaticamente correlações entre:

- fichas da apresentação;
- linhas da planilha de custos.

As correlações existentes continuam preservadas:

- confirmadas não são substituídas;
- rejeitadas não são recriadas;
- novas relações entram como sugeridas.

Cada card mostra:

- custo direto confirmado;
- custo direto sugerido e percentual de correspondência;
- ou o total da seção ainda não rateado entre as fichas.

A expressão **custo da planilha** é usada para não confundir orçamento/proposta com custo realizado. O custo realizado continua vindo do relatório pós-evento.

### 4. Diagnóstico cumulativo

A página **Diagnóstico e recomendações** passa a reunir:

- cobertura das fontes;
- visão executiva;
- diagnóstico automático;
- recomendações;
- matriz briefing × proposta × custo × execução;
- proposta × execução;
- custos sem proposta;
- entregas registradas no relatório, mas ausentes da apresentação;
- demandas do briefing sem evidência;
- resultados e aprendizados do relatório;
- histórico de análises anteriores.

A NAVE diferencia:

- executado com evidência;
- explicitamente não executado;
- sem evidência de execução.

**Sem evidência não significa não executado.**

### 5. Atualização contínua

Cada nova combinação de fontes gera um snapshot.

Ao subir:

- nova apresentação;
- nova planilha;
- relatório pós-evento;
- relatório de encerramento;
- feedback;
- aprovação;

...o diagnóstico é recalculado e preservado sem apagar as consolidações anteriores.

## Instalação

### 1. Supabase

Execute:

`supabase_patch_fase_15_2_diagnostico_integrado_v1.sql`

### 2. GitHub

Adicione:

- `project_workspace_intelligence.py`

Substitua:

- `project_workspace_visuals.py`
- `project_workspace_ui.py`
- `project_workspace_db.py`

Os demais arquivos da V27.1 permanecem iguais.

### 3. Reinicie

`Manage app → Reboot app`

Não é necessário alterar `requirements.txt`.

## Teste obrigatório com Chambinho

1. Abra **Projetos** e selecione Chambinho.
2. Entre em **Cenografia e ativações**.
3. Confirme que a cenografia da apresentação aparece, mesmo quando a classificação original estava incompleta.
4. Confirme que os materiais aparecem em linhas horizontais, com imagem à esquerda e conteúdo à direita.
5. Confirme que custos aparecem como confirmados, sugeridos ou custos de seção não rateados.
6. Entre em **Brindes e press kits** e valide o mesmo formato horizontal.
7. Entre em **Diagnóstico e recomendações**.
8. Confirme a cobertura de briefing, apresentação, planilha, pós-evento e feedbacks.
9. Confira a matriz integrada.
10. Confira as abas:
    - Proposta × execução;
    - Custos sem proposta;
    - Entregas fora da apresentação;
    - Briefing sem evidência;
    - Resultados e aprendizados.
11. Confirme que o relatório pós-evento já analisado aparece na consolidação.
12. Adicione um feedback e confirme que uma nova consolidação é gerada.

## Resultado esperado

A NAVE deixa de apenas exibir arquivos lado a lado.

Ela passa a explicar:

- o que o briefing pediu;
- o que foi apresentado;
- o que recebeu custo;
- o que possui evidência de execução;
- o que surgiu depois;
- quais lacunas ainda precisam de confirmação;
- e quais aprendizados devem seguir para os próximos projetos.
