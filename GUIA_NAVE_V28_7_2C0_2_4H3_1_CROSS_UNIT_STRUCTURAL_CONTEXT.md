# NAVE by VOE · V28.7.2C0.2.4H3.1
## Cross-Unit Structural Context & Golden Verifier Repair

## Por que esta correção existe

O Golden B2.12.2.1 do JOVI provou que uma garantia antiga de Requirement Truth tinha
passado com falso verde.

Itens como:

- `Frequentadores de festivais de música;`
- `Universo da moda e lifestyle.`
- `Storytelling detalhado.`
- `Mini show ao vivo;`
- `Performance com muito movimento;`

continuavam `verified` como Requirements atuais, apesar de a fonte os apresentar como
filhos de containers semânticos de público, plataforma ou exemplo.

O problema tinha duas causas independentes.

### 1. Contexto estrutural atravessando Evidence Units

No legacy recall H3, `_nearest_section_role()` só usava `surrounding_text` quando o
título não era encontrado dentro da Evidence Unit atual.

Quando o parser produzia uma Evidence Unit contendo apenas o bullet, o título era
encontrado em `hit = 0`. O algoritmo então não enxergava o parent que estava na Evidence
Unit anterior.

Consequência: um item nominal podia cair nos fallbacks legados de deliverable/mandatory
e virar `requirement_candidate`.

### 2. Verifier vulnerável a pontuação terminal

O H3 Golden comparava `lower(trim(title))` contra títulos sem `.` / `;` finais.

Assim, por exemplo:

- banco: `Storytelling detalhado.`
- verifier: `storytelling detalhado`

não eram iguais. O gate `product_audience_platform_examples_not_current_requirements`
podia retornar `true` mesmo com o falso Requirement presente.

---

## O que H3.1 muda

### A. Reparo upstream, antes de Requirement Truth

O novo `project_requirement_semantic_h31.py` reutiliza o collector H3 e corrige somente
o legacy-recall estrutural antes do planner/writer.

A Evidence-first continua intacta.

A regra agora monta o contexto como:

`Evidence Units anteriores + Evidence Unit atual`

mas localiza prioritariamente o item na Evidence Unit atual. O lookback H3.1 é bounded
em até **32 Evidence Units anteriores / 20 mil caracteres**, e a busca estrutural recua no
máximo **64 linhas**. Isso corrige o limite H3 de três unidades, que não alcançava o parent
de um quarto/quinto bullet. Headings mais próximos continuam interrompendo a herança,
evitando que contexto antigo contamine uma seção nova.

São preservados os papéis H3 existentes:

- `audience_context`
- `product_attribute`
- `platform_scope`
- `strategy_context`
- `example_signal`
- `requirement_parent`

Não existe lista de títulos JOVI dentro do classificador.

### B. Human confirmation tem precedência

H3.1 consulta `project_requirement_truth_status` antes de aplicar o reparo estrutural.

Uma identity `human_confirmed` não é demovida pela regra automática. Se a Truth view não
puder ser consultada, H3.1 **falha fechado** e não executa a correção.

### C. Writer/reconciliation continua o mesmo contrato

`project_requirement_reconciliation_h31.py` reutiliza:

- o planner H3;
- o RPC já instalado `apply_project_requirement_reconciliation_v2872c0`;
- o schema `28.7.2c0.2.4`;
- as regras de no auto-merge;
- lifecycle/provenance já aprovados.

A única diferença é que o bundle e o `intelligence_run` são versionados como:

`V28.7.2C0.2.4H3.1`

### D. H3.1 fica isolado do pipeline normal durante a prova Golden

A nova página `pages/33_Requirement_Semantic_Truth_Repair.py` chama diretamente
`project_requirement_reconciliation_h31.reconcile_project_requirements()`.

Nesta etapa, H3.1 **não reroda**:

- Domain Normalization / Truth Gate materialization;
- Solution Reconciliation A;
- Coverage / Identity Audits;
- Core Semantic Domains B;
- Graph V28.6.

O pipeline normal e o botão legado continuam em H3 até a aprovação Chambinho + JOVI.
Isso reduz o blast radius e impede uma mudança global silenciosa enquanto testamos a
correção upstream. Depois dos Goldens, a promoção de H3.1 para o pipeline normal será
uma decisão governada separada.

### E. Verifier Golden normaliza pontuação

O novo verifier read-only usa:

```sql
regexp_replace(
  lower(trim(coalesce(title,''))),
  '[[:space:][:punct:]]+$',
  '',
  'g'
)
```

A lista de títulos continua sendo somente **controle de regressão Golden**. A regra de
produção permanece estrutural e genérica.

O verifier exige ainda prova positiva das classificações:

- festival de música → `audience_context / no_domain_object`;
- moda/lifestyle → `audience_context / no_domain_object`;
- storytelling → `platform_scope / no_domain_object`;
- mini show → `example_signal / no_domain_object`;
- performance com movimento → `example_signal / no_domain_object`.

---

## Arquivos do patch

### ADICIONAR

```text
project_requirement_semantic_h31.py
project_requirement_reconciliation_h31.py
pages/33_Requirement_Semantic_Truth_Repair.py
tests/test_v28_7_2c0_2_4h3_1_cross_unit_context.py
NAVE_V28_7_2C0_2_4H3_1_VERIFY_GOLDEN_JOVI.sql
GUIA_NAVE_V28_7_2C0_2_4H3_1_CROSS_UNIT_STRUCTURAL_CONTEXT.md
```

### SUBSTITUIR

```text
NAVE_V28_7_3_CURRENT_CHECKPOINT.md
```

### NÃO ALTERAR

```text
project_requirement_semantic_extractor.py
project_requirement_reconciliation.py
project_requirement_identity.py
project_domain_reader.py
project_requirement_auto_adjudication_hardening.py
project_intelligence_pipeline.py
pages/32_Automated_Adjudication_Recommendations.py
```

Os módulos H3 originais e o pipeline normal ficam preservados como baseline auditável.
H3.1 é acionado somente pela nova página governada durante esta validação.

---

## SQL

### Migration / write SQL

**NÃO.**

Não execute novamente C0.2.4/H1 ou qualquer migration antiga.

### Verifier read-only

**SIM**, mas somente depois do run H3.1 do JOVI:

`NAVE_V28_7_2C0_2_4H3_1_VERIFY_GOLDEN_JOVI.sql`

---

## Validação executada antes da entrega

- `py_compile` dos módulos/runtime/page/test: **PASS**;
- simulação específica do resolver cross-unit: **10/10 PASS**;
- simulação do lookback ampliado além de três Evidence Units: **PASS**;
- verificação lexical do SQL: quotes e parênteses balanceados;
- nenhum arquivo contém write SQL de migration;
- nenhum auto-merge novo;
- `domain_primary` não é promovido;
- Graph V28.6 continua congelado.

A simulação cobre:

1. parent de audience em Evidence Unit anterior;
2. parent de platform em Evidence Unit anterior;
3. primeiro child de `como:`;
4. segundo child de `como:` com sibling intermediário;
5. `requirement_parent` atravessando Evidence Unit;
6. parent mais próximo vencendo contexto antigo;
7. heading intermediário bloqueando herança stale;
8. audience parent após mais de três sibling Evidence Units;
9. platform parent após três bullets intermediários;
10. parent estrutural embutido na mesma Evidence Unit do child.

O Golden real continua sendo a prova de integração com a base.

---

## Ordem operacional

### 1. Deploy

1. Suba/adicione os arquivos exatamente nos caminhos acima.
2. Commit/push.
3. **Manage app → Reboot app.**
4. Não reenvie nem reprocese masters.
5. Não rode A, B ou Graph manualmente.

### 2. Golden Chambinho primeiro

1. Abra a nova página **Requirement Semantic Truth Repair**.
2. Selecione `Festivalzinho Chambinho`.
3. Marque a confirmação.
4. Execute uma única vez:

   `Requirement Truth Repair · V28.7.2C0.2.4H3.1`

5. Baixe `NAVE_H3_1_REQUIREMENT_TRUTH_REPAIR_<project_id>.json`.
6. Envie o JSON para revisão.

Esperado: sem regressão estrutural e, em princípio, zero cross-unit overrides novos no
Chambinho. Não usar essa expectativa como substituto da auditoria.

### 3. JOVI somente depois da aprovação Chambinho

1. Rode a mesma ação H3.1 no JOVI.
2. Baixe o JSON H3.1.
3. Execute no Supabase, **read-only**:

   `NAVE_V28_7_2C0_2_4H3_1_VERIFY_GOLDEN_JOVI.sql`

4. Exporte a única linha para CSV.
5. Envie JSON + CSV.

No JOVI, os cinco pseudo-requirements acima precisam ser classificados no-domain e não
podem continuar Current Requirements apenas por terem Evidence/Occurrence histórica.

---

## O que NÃO fazer agora

- não rerodar B2.12.2.1 antes de H3.1 ser aprovado nos dois Goldens;
- não avançar para B2.13;
- não alterar canaries;
- não promover `domain_primary`;
- não editar as 75 identities manualmente;
- não apagar Requirement history;
- não auto-mergear a colisão de co-investimento;
- não reprocessar masters.

Depois do H3.1 aprovado, B2.12.2.1 será rerodado como prova downstream sobre a Truth
corrigida.
