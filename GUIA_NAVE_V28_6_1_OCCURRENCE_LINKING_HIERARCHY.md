# NAVE by VOE · V28.6.1 — Occurrence Linking & Hierarchical Relations

## Objetivo

A V28.6.0 provou que a NAVE já consegue criar entidades canônicas do projeto, mas o Golden Chambinho terminou com:

- 14 entidades canônicas;
- 0 entidades unificadas;
- 1 vínculo solução ↔ custo;
- 1 execução ligada;
- 4 revisões.

Isso significa que o catálogo de entidades nasceu, mas as ocorrências dessas mesmas entidades dentro de proposta, planilha e pós-evento ainda não estavam sendo anexadas aos hubs canônicos.

A V28.6.1 corrige essa camada antes de qualquer avanço para Knowledge Across Projects.

---

## 1. Correção de bug real em aliases

Na V28.6.0, `project_entity_graph.py` tentava gravar aliases com:

`alias_type = "workspace_title"`

A tabela `entity_aliases` aceita apenas os tipos previstos pelo Intelligence Foundation (`name`, `abbreviation`, `translation`, `former_name`, `misspelling`, `campaign_name`, `other`). Como a gravação era best-effort, a exceção era silenciosamente absorvida.

Resultado: as entidades canônicas eram criadas, mas perdiam uma das principais pontes para o Entity Resolution.

A V28.6.1 grava esses aliases como `other` e adiciona poucas variantes editoriais conservadoras, por exemplo:

- `Oficina Origami de Coração` → `Origami de Coração`;
- `Ativação - Pescaria` → `Pescaria`.

Não são criados sinônimos inventados.

---

## 2. Canonical Occurrence Linking

Antes do resolver global, a NAVE agora executa uma etapa específica:

`entidade canônica → ocorrência extraída em uma fonte`

Ela combina:

- nome canônico;
- aliases;
- nome da entidade extraída;
- texto da menção;
- texto da página/slide onde a menção apareceu;
- papel da fonte (proposta, pós-evento etc.);
- compatibilidade de família semântica.

Isso permite reconhecer casos em que o extrator deu um nome genérico para a ocorrência, mas a página contém explicitamente `AMARELINHA`, `PESCARIA`, `ORIGAMI` etc.

### Regra de segurança

Uma evidência que contém várias soluções não força merge por contexto. O melhor match precisa ter margem sobre o segundo melhor candidato.

Ano, número ou palavra genérica continuam insuficientes para identidade.

---

## 3. O run agora recarrega o grafo depois dos merges

A V28.6.0 persistia `canonical_entity_id`, mas as etapas de custo e execução podiam continuar usando o snapshot carregado **antes** do merge.

A V28.6.1 recarrega o Intelligence Graph depois de:

1. occurrence linking;
2. entity resolution geral.

Só depois executa:

- solução ↔ custo;
- hierarquia;
- execução;
- findings.

Assim, custo e pós-evento passam a enxergar imediatamente a nova identidade canônica no mesmo run.

---

## 4. Cost Linking 2.1

O vínculo financeiro passa a considerar com mais força nomes distintivos explícitos dentro da linha financeira, além do token overlap.

Também ignora mais prefixos estruturais como `Oficina`, `Workshop` e `Atividade` no score lexical.

Exemplo esperado:

`Oficina Origami de Coração` ↔ `Ativação - Oficina de Origami`

sem depender de igualdade literal.

---

## 5. Execução ligada à solução, não apenas ao projeto

O card `Execução` da V28.6.0 podia ficar em 1 porque o único claim criado era o fato global de que o projeto foi executado.

Na V28.6.1:

- o fato global continua preservado internamente;
- o número exibido passa a representar **soluções/entregas ligadas a evidências pós-evento**;
- se uma entidade não recebeu `entity mention` no pós-evento, há um fallback conservador por nome/alias explícito na unidade de evidência.

Isso deve aproximar o quadro da realidade de Amarelinha, Pescaria, Origami, Mascote, Tatuagens etc.

---

## 6. Primeiras relações hierárquicas — Press Kit

A V28.6.1 inaugura relações `part_of` para casos em que a própria unidade de evidência da proposta contém contexto de:

- `PRESS KIT`;
- `SEEDING`;
- influenciadores;

junto de um item canônico de brinde/solução.

Exemplo conceitual:

`Meias` → `part_of` → `Press Kit`

A relação só é criada quando o item aparece na mesma evidência com contexto explícito de kit. A NAVE não transforma todos os brindes do projeto em componentes do press kit.

Isso é a base para corrigir no Dossiê e no workspace a pergunta: **“o que efetivamente compõe o Press Kit?”**

---

## 7. Quadro de validação atualizado

O quadro `Intelligence Graph · conexões entre arquivos` agora mostra:

- Entidades canônicas;
- Entidades unificadas;
- Solução ↔ custo;
- Execuções ligadas;
- Relações hierárquicas;
- Revisões.

`Execuções ligadas` deixa de usar o claim global do projeto como se fosse uma solução.

---

## Como testar no Golden Chambinho

Depois do deploy:

1. faça **Manage app → Reboot app**;
2. não reenvie arquivos;
3. não faça reprocessamento completo;
4. vá em **Importar projeto completo**;
5. expanda **Corrigir um projeto importado por uma versão anterior da V28**;
6. selecione **Festivalzinho Chambinho**;
7. clique em **Reconstruir apenas conexões inteligentes**;
8. envie o print do quadro atualizado.

### O que esperamos

Não vou definir um número artificial apenas para “passar o teste”. O critério é qualitativo e quantitativo:

- `Entidades unificadas` precisa sair de 0;
- `Solução ↔ custo` precisa superar o único vínculo atual se as linhas permitirem;
- `Execuções ligadas` deve reconhecer várias soluções comprovadas no relatório;
- `Relações hierárquicas` deve aparecer quando a proposta comprovar composição do Press Kit;
- nenhum vínculo pode nascer de `2026`, números, headings genéricos ou coocorrência vaga.

Se as entidades continuarem em 0 depois desta versão, não avançaremos: o próximo diagnóstico será diretamente sobre os registros persistidos no Intelligence Graph.

---

## Arquivos a substituir

- `project_entity_graph.py`
- `cross_source_linker.py`
- `project_bundle_materializer.py`
- `project_batch_ingestion.py`
- `pages/14_Importar_Projeto.py`
- `tests/test_file_analyst_integration_v2821.py`

## Arquivos a adicionar

- `tests/test_v28_6_1_occurrence_hierarchy.py`
- `GUIA_NAVE_V28_6_1_OCCURRENCE_LINKING_HIERARCHY.md`

## SQL

**NÃO.**

A correção usa o schema já existente do Intelligence Foundation, inclusive a relação `part_of`.

## Reboot

**SIM.**

## Validação local

Foram executados os testes focados de V28.4, V28.5, V28.6.0 e V28.6.1 em um repositório-base com os patches sobrepostos:

**33 testes passaram.**

A suíte integral não foi usada como critério porque este ambiente não possui dependências de runtime já conhecidas do deploy (`streamlit`, `google-genai` e a Storage Layer completa), o que interrompe a coleta de módulos legados não relacionados a esta alteração.
