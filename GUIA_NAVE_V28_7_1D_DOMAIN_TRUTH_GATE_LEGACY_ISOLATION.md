# NAVE by VOE · V28.7.1D — Domain Truth Gate & Legacy Isolation

## Objetivo desta versão

A V28.7.1D **não faz cutover para `domain_primary`** e não tenta concluir a Semantic Domain Reconciliation.

Ela corrige o problema encontrado na auditoria real do Golden Chambinho: o banco já preservava provenance e lifecycle, mas ainda permitia que outcomes legados sem Evidence Unit, Claim auditável ou Human Review fossem tratados como current truth.

A versão separa três problemas que não podem mais ser confundidos por um único contador:

1. **Truth** — o que pode ou não ser considerado verdade atual;
2. **Coverage** — o que aparece nas fontes, mas ainda não possui objeto de domínio reconciliado;
3. **Identity** — objetos do domínio que podem estar divididos/duplicados incorretamente.

O princípio é fail-closed:

> informação sem provenance continua preservada para auditoria, mas não decide estado atual.

---

## O que muda

### 1. Outcome Truth Gate

Cria a view:

`entity_outcome_truth_status`

Cada outcome ativo passa a ser classificado como:

- `verified` — possui Evidence Unit atual, Claim ativo sustentado por Evidence atual, ou Human Review explícito `confirm`;
- `inferred` — possui claim de inferência evidence-backed, mas não é promovido automaticamente a current truth nesta versão;
- `legacy_unverified` — legado preservado sem provenance auditável suficiente;
- `conflicted` — evidence/review conflitante ou dois estados verificados incompatíveis para o mesmo sujeito + outcome type.

`is_human_confirmed` legado não conta como Human Review. Review humana canônica vem de `intelligence_reviews`.

### 2. `entity_current_outcomes` passa a ser provenance-gated

A view mantém as mesmas 15 colunas e a mesma ordem da V28.7.1B por compatibilidade PostgreSQL/PostgREST.

Somente `truth_state = verified` pode entrar em current truth.

`authority_score` desempata candidatos **já elegíveis**. Ele nunca compensa ausência de provenance.

### 3. Legacy Isolation

`memory_item_outcomes` e `memory_project_outcomes` continuam preservados e continuam podendo gerar eventos históricos em `entity_outcomes`.

Mas, se não houver provenance nova válida, esses eventos ficam como `legacy_unverified` e deixam de projetar estado atual.

Consequência esperada no Golden:

- execuções legadas sem provenance deixam de projetar `executed`;
- `project_solution_instances.execution_status` volta a `not_confirmed` quando não existe execution outcome verificado;
- execução não gera aprovação;
- `won` legado sem provenance não pode ser current truth.

### 4. Projeto direto / sem concorrência

Quando o briefing possui Evidence Unit inequívoca com semântica de não-concorrência, a normalização cria outcomes evidence-backed:

- `process_type = direct`;
- `commercial_result = not_applicable`.

A regra é baseada na fonte, não no nome Chambinho.

### 5. Requirement Binding determinístico

O binder continua preferindo quote/reference exatos, mas ganha um fallback conservador dentro da **mesma fonte** para requisitos cujo título normalizado não aparece literalmente no DOCX.

Isso cobre os false negatives observados em:

- Público-alvo;
- Objetivo principal;
- Budget.

A V28.7.1D **não inventa** `constraint_operator`, `constraint_value` ou `unit` do budget. Essa semântica continua reservada para a V28.7.2.

### 6. Domain Coverage Audit

Novo módulo:

`project_domain_truth_audit.py`

O audit parte dos resultados estruturados de pós-evento e procura soluções ainda não reconciliadas no domínio, corroborando quando possível com Evidence Units do projeto e linhas financeiras.

Ele publica `intelligence_findings` do tipo:

`missing_solution_instance`

Ele **não cria** `Project Solution Instance`.

No Golden, deve sinalizar explicitamente pelo menos os gaps reais sustentados pelas fontes, incluindo Amarelinha e Pescaria quando presentes no material estruturado/evidence atual.

### 7. Domain Identity Audit

O mesmo módulo procura duas solution instances distintas compartilhando uma Evidence Unit compacta que sustenta materialmente os dois nomes.

Publica:

`possible_duplicate_identity`

No Golden, o caso de controle é:

`Chaveiro ↔ Pelúcia`

O audit **não faz merge, split nem reclassificação**.

### 8. Graph V28.6 congelado

`Atualizar domínio e auditar verdade` não executa mais:

- V28.6 canonical/occurrence graph rebuild;
- old Cross-Source Linker;
- Project Analyst / semantic synthesis dependente daquele graph.

O Graph legado continua no banco para inspeção histórica, mas não participa dos novos gates.

`intelligence_graph_db.py` **não precisa ser alterado nesta versão**.

### 9. Cutover continua bloqueado

`project_domain_migration_state.migration_mode` permanece obrigatoriamente:

`legacy_shadow`

A V28.7.1D não contém mecanismo de promoção para `domain_primary`.

---

# Arquivos do patch

## Substituir no GitHub

- `project_domain_normalization.py`
- `project_intelligence_pipeline.py`
- `pages/14_Importar_Projeto.py`

## Adicionar no GitHub

- `project_domain_truth_audit.py`
- `tests/test_v28_7_1d_truth_gate.py`
- `tests/test_v28_7_1d_requirement_binding.py`
- `tests/test_v28_7_1d_orchestration_freeze.py`
- `tests/test_v28_7_1d_domain_audits.py`

## Não substituir

- `intelligence_graph_db.py`

Ele foi revisado e permanece intacto; o freeze é feito na orquestração.

## SQL — não subir como runtime

Executar no Supabase SQL Editor:

`NAVE_V28_7_1D_DOMAIN_TRUTH_GATE_LEGACY_ISOLATION.sql`

## Diagnóstico read-only

Depois do deploy e da atualização do Golden, executar:

`NAVE_V28_7_1D_VERIFY_GOLDEN_CHAMBINHO.sql`

Esse arquivo não altera dados.

---

# Pré-requisito

A instalação atual precisa já conter:

- Intelligence Foundation v1;
- V28.7.1B Domain Integrity;
- hotfix V28.7.1C / RPC `apply_project_domain_normalization_v2871` funcional.

A V28.7.1D é aditiva e reutiliza o writer transacional já estabilizado na 7.1B/C.

Se o SQL acusar prerequisite missing, **não continue o deploy** e envie o erro integral.

---

# Ordem exata de deploy

## 1. Supabase — SIM, precisa executar SQL

No **Supabase → SQL Editor → New query**:

execute integralmente:

`NAVE_V28_7_1D_DOMAIN_TRUTH_GATE_LEGACY_ISOLATION.sql`

O script deve terminar sem erro.

Ele:

- cria o Truth Gate;
- substitui o current resolver preservando compatibilidade de colunas;
- cria a wrapper RPC V28.7.1D;
- amplia `project_domain_integrity_status`;
- mantém `legacy_shadow`;
- faz self-check e `NOTIFY pgrst, 'reload schema'`.

**Não rode novamente a ação da NAVE antes de concluir o passo GitHub.**

## 2. GitHub

Substitua/adicione exatamente os arquivos listados acima, preservando os caminhos do ZIP.

Não altere outros arquivos.

## 3. Reboot — SIM

Depois do SQL e da atualização do GitHub:

**Streamlit → Manage app → Reboot app**

## 4. Não reprocessar os masters

Para o Golden Chambinho:

- não reenviar os quatro masters;
- não executar nova importação;
- não apagar a materialização existente.

A validação deve ocorrer sobre o mesmo estado que revelou os problemas da V28.7.1.

## 5. Rodar a nova ação

Em:

**Importar projeto completo → Corrigir um projeto importado por uma versão anterior da V28 → Festivalzinho Chambinho**

marque a confirmação e clique:

**Atualizar domínio e auditar verdade**

A ação deve concluir Domain Normalization + Truth Gate + Coverage Audit + Identity Audit e parar ali.

---

# Golden Gate esperado

A versão **não deve ser aprovada olhando apenas números verdes**. Os itens abaixo precisam ser inspecionados semanticamente.

### A. Truth

- Outcomes legados sem Evidence/Claim-evidence/Review aparecem como `legacy_unverified`.
- Eles não aparecem em `entity_current_outcomes`.
- `authority_score` alto não os promove.

### B. Proposal

- Os proposal outcomes que já possuíam Evidence direta na proposta continuam verificáveis/current.

### C. Execution

- Execution outcomes legados sem provenance não permanecem current truth.
- `project_solution_instances.execution_status` não pode continuar `executed` apenas por herança de `memory_item_outcomes`.

### D. Approval

- `executed` não produz `approved`.

### E. Commercial

Com Evidence explícita de `CONCORRÊNCIA: NÃO`:

- `process_type = direct` deve aparecer como current truth;
- `commercial_result = not_applicable` deve aparecer como current truth;
- `commercial_result = won` legado sem provenance não pode aparecer como current truth.

### F. Requirements

Os três antigos false negatives devem receber binding de Evidence:

- Público-alvo;
- Objetivo principal;
- Respeitar o budget informado.

Objetivo esperado no Golden: **14/14 requisitos com provenance**, desde que as Evidence Units atuais do DOCX estejam materializadas como observado na auditoria anterior.

O budget pode continuar com operador/valor/unidade semânticos incompletos. Isso não reprova a 7.1D; pertence à 7.2.

### G. Coverage

O painel deve abrir os detalhes de **Possíveis soluções ausentes do domínio**.

Amarelinha e Pescaria devem aparecer se os resultados/evidências atuais do Golden continuarem iguais aos auditados.

Não deve ser criada nenhuma solution instance automaticamente.

### H. Identity

O painel deve abrir os **Conflitos de identidade para revisão**.

O caso de controle é:

`Chaveiro ↔ Pelúcia`

Não deve ocorrer merge automático.

### I. Financeiro — regressão zero

Preservar:

- 54 linhas financeiras;
- 54 Evidence Units distintas;
- 54 locators `sheet + row` distintos;
- total de **R$ 554.310,85**;
- zero linhas sem evidence direta.

### J. Graph freeze

A rodada V28.7.1D não pode criar nova execução do old Cross-Source Linker nem reconstruir o Graph V28.6.

### K. Migration

`migration_mode = legacy_shadow`

`domain_schema_version = 28.7.1d`

Nenhum cutover automático.

---

# Verificação técnica

Após a ação, execute no Supabase:

`NAVE_V28_7_1D_VERIFY_GOLDEN_CHAMBINHO.sql`

Ele retorna, em blocos:

1. projeto-alvo selecionado;
2. resumo do Truth Gate;
3. todos os active outcome candidates e seus `truth_state`;
4. current truth somente;
5. provenance dos requisitos;
6. Coverage/Identity Findings;
7. regressão financeira;
8. proxy de freeze do Cross-Source;
9. projeções de status das solution instances.

Envie o resultado/export do diagnóstico e o print do painel da NAVE antes de considerar a V28.7.1D aprovada.

---

# Testes locais executados no patch

Os quatro testes específicos da V28.7.1D passam:

- Truth Gate / view compatibility;
- Requirement Binding / direct commercial rule;
- Graph freeze / orchestration;
- Coverage & Identity Audits.

Também foi feita compilação Python dos arquivos alterados.

No teste legado `test_v28_7_1_domain_integrity_provenance.py`, **14 assertions de código passaram** e 6 não puderam rodar porque o ZIP recebido não contém o arquivo histórico `NAVE_V28_7_1B_DOMAIN_INTEGRITY_SQL_COMPAT.sql` que esses testes tentam abrir. Não adicionamos esse SQL histórico ao patch apenas para satisfazer a fixture.

A suíte completa do repositório também não pôde ser usada como gate neste ambiente porque a coleta global exige dependências de runtime ausentes aqui (`streamlit` e `google.genai`). Isso é independente das alterações V28.7.1D; por isso o gate desta entrega é a suíte específica + compilação + revisão estática das invariantes arquiteturais.

---

# SQL

**SIM.** Execute `NAVE_V28_7_1D_DOMAIN_TRUTH_GATE_LEGACY_ISOLATION.sql`.

# Reboot

**SIM.** Depois do SQL e dos arquivos GitHub.

# Cutover

**NÃO.** Mesmo que o Golden passe, a decisão de sair de `legacy_shadow` continua bloqueada até a revisão pós-auditoria e a Semantic Domain Reconciliation.
