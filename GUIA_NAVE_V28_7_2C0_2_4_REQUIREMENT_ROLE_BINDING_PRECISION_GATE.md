# NAVE by VOE · V28.7.2C0.2.4
## Requirement Role & Binding Precision Gate

### Objetivo

A C0.2.4 corrige a classe de erro exposta pelo Golden JOVI depois que a C0.2.3 já havia estabilizado provenance, rerun isolation e Evidence-first discovery.

A regra passa a ser:

**Evidence → Observation → semantic role → Requirement Identity/Occurrence**

Uma expressão encontrada em briefing não vira Requirement apenas por estar perto de um verbo obrigatório. Antes do binding, a NAVE distingue obrigação principal, scope/canal, atributo, contexto, referência, exemplo, sugestão, parâmetro e qualificador de constraint.

A versão continua integralmente em `legacy_shadow`. Não promove `domain_primary`, não reconstrói o Graph V28.6 e não faz auto-merge de duas Requirement identities existentes.

---

## O que muda

### 1. Two-pass Requirement reconciliation

A reconciliação classifica primeiro os sinais vindos do legado. Uma identity legada classificada pela Evidence atual como objeto `no_domain` continua preservada para recall/histórico, mas deixa de ser candidata a absorver uma obrigação Evidence-first.

Isso impede que um antigo falso-Requirement, por exemplo um nome de produto, capture uma cláusula obrigatória apenas por similaridade textual.

### 2. Nominal Fragment Guard

Bullets nominais recebem o papel do seu container semântico antes de qualquer promoção:

- `Foco do Produto` → `product_attribute`;
- `Público-Alvo` → `audience_context`;
- `Adequação à Plataforma` → `platform_scope`;
- exemplos depois de `como:` → `example_signal`.

Uma obrigação explícita completa continua sendo Requirement mesmo quando aparece dentro de uma seção descritiva.

### 3. Suggestion / Unconfirmed Guard

Sinais como:

- `vale sugerirmos`;
- `podemos sugerir / considerar / inserir`;
- `caso tenhamos alguma ideia`;
- `cliente não confirmou`;
- `sem confirmação`;

são preservados como `suggestion_signal`, nunca como current Requirement truth automático.

Exclusões explícitas como `não é necessário...` continuam sendo Requirements negativas legítimas.

### 4. Example, Parameter e Constraint Qualifier

A C0.2.4 adiciona os papéis:

- `example_signal`;
- `parameter_signal`;
- `constraint_qualifier`;
- `suggestion_signal`.

Exemplos ilustrativos não viram deliverables obrigatórios. Parâmetros e qualificadores permanecem auditáveis sem competir como Requirement Identity principal.

### 5. Binding Compatibility Gate

Evidence-first binding passa a ser title-first e conservador.

Uma Evidence Unit compartilhada não é evidência de identidade. Similaridade com uma descrição longa não é suficiente para ligar duas cláusulas semanticamente diferentes.

Exceção estreita: Requirement identities da família `constraint` podem usar descrição como apoio quando a identity é um rótulo abstrato que resume a mesma restrição.

### 6. Semantic Gate fail-closed

A V28.7.2B só roda quando o Requirement Semantic Gate estiver limpo.

Bloqueadores:

- `observations_open > 0`;
- `observations_review_required > 0`;
- `unexplained_legacy_shadow > 0`;
- Requirement identity `review_required > 0`;
- Requirement identity `conflicted > 0`.

O painel passa a mostrar `Observation review` e o estado `Semantic Gate PASS/BLOCK`. Assim, uma observação semanticamente pendente não fica escondida atrás de um contador de identities igual a zero.

---

## SQL

**SIM.** Executar uma única vez:

`NAVE_V28_7_2C0_2_4_REQUIREMENT_ROLE_BINDING_PRECISION_GATE.sql`

O SQL é incremental. Ele:

- amplia a lista de roles `no_domain` no Truth Status;
- preserva a ordem de todas as colunas já existentes nas views;
- apenas acrescenta as novas métricas ao final de `project_requirement_reconciliation_status`;
- adiciona `semantic_gate_blockers` e `semantic_gate_pass`;
- não executa `DELETE`;
- não promove `domain_primary`.

---

## Arquivos do GitHub

Substituir/adicionar exatamente:

```text
project_requirement_semantic_extractor.py
project_requirement_identity.py
project_requirement_reconciliation.py
pages/14_Importar_Projeto.py
tests/test_v28_7_2c0_2_evidence_first.py
NAVE_V28_7_2C0_2_4_REQUIREMENT_ROLE_BINDING_PRECISION_GATE.sql
NAVE_V28_7_2C0_2_4_VERIFY_GOLDEN_JOVI.sql
GUIA_NAVE_V28_7_2C0_2_4_REQUIREMENT_ROLE_BINDING_PRECISION_GATE.md
```

Não há alteração em `project_intelligence_pipeline.py`: a orquestração existente já é fail-closed para qualquer Requirement reconciliation cujo status não seja `completed`.

---

## Reboot

**SIM.**

Depois do commit:

`Manage app → Reboot app`

---

## Reprocessar masters

**NÃO.**

A C0.2.4 trabalha sobre Source Assets / Evidence já materializados.

---

## Teste obrigatório — Golden JOVI

1. Execute o SQL C0.2.4 uma vez no Supabase.
2. Suba o patch no GitHub.
3. Faça reboot.
4. Não reenvie e não reprocese os masters.
5. Abra `Importar projeto completo`.
6. Selecione `Lançamento Jovi X300` na correção/reconciliação de projeto existente.
7. Clique uma única vez em **Reconciliar Requirements + Core Semantics · V28.7.2C0.2.4**.
8. Se o Semantic Gate passar, a V28.7.2B roda automaticamente. Não execute B manualmente.
9. Execute `NAVE_V28_7_2C0_2_4_VERIFY_GOLDEN_JOVI.sql`.
10. Exporte a única linha como CSV e envie junto com prints completos dos painéis Truth Gate, A, C0.2.4 e B.

O verifier não fixa a cardinalidade final de Requirements. Ele valida os erros semânticos que o JOVI expôs: falsos Requirements de produto/audiência/plataforma/exemplo, sugestão não confirmada, binding MC × timing, blockers do Semantic Gate, provenance e regressões A/B.

---

## Critérios de aprovação desta etapa

A C0.2.4 só pode ser aprovada no Golden JOVI se, simultaneamente:

- o Requirement Semantic Gate estiver `PASS` com zero blockers;
- `observations_open = 0`;
- `observations_review_required = 0`;
- não houver legacy shadow sem explicação;
- nomes/atributos de produto, audiência, scope de plataforma e exemplos provados pelo Golden não estiverem como current verified Requirements;
- sugestão de press kit não confirmada não estiver como Requirement truth;
- exclusão de MC e obrigação de desenhar o timing estejam em identities distintas;
- todas as ocorrências ativas tenham Evidence atual;
- Solutions A e Core Semantics B permaneçam estáveis;
- Graph V28.6 continue congelado;
- migration mode continue `legacy_shadow`.

Só depois dessa aprovação voltamos ao Golden Chambinho como regressão cruzada antes de encerrar C0.

---

## Validação local do patch

- `py_compile` dos 4 arquivos Python alterados: **PASS**;
- suíte focada `test_v28_7_2c0_2_evidence_first.py`: **30 passed**;
- testes novos cobrem product/audience/platform/example role, suggestion guard, parameter/constraint qualifier, binding MC × timing, constraint exception, two-pass isolation e semantic gate fail-closed;
- SQL checado estaticamente para preservação de ordem de colunas, ausência de `DELETE` e ausência de `domain_primary`.
