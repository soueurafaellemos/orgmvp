# NAVE by VOE · V28.7.2C0.2.4H3
## Bare Product Identity Guard

### Diagnóstico confirmado pelo CSV 47

O diagnóstico do Golden JOVI isolou finalmente o sobrevivente `JOVI X300 Ultra`.

A identidade atual incorreta é:

- `project_requirements.id = 554fa90b-9fbe-4d25-9713-ddaa6b43e80f`
- título: `JOVI X300 Ultra`
- origem: legacy `memory_briefing_requirements`
- `legacy_source_id = dc46dfb2-1178-4ac6-a102-53c770c75883`
- tipo legado: `deliverable`
- truth atual: `verified`

Ela está sobrevivendo por dois caminhos diferentes que acabaram convergindo indevidamente na mesma identidade:

1. Evidence Unit `dd02f611-0d25-41f5-9585-7209f34853f3` contém somente o rótulo nominal `JOVI X300 Ultra`.
2. Evidence Unit `0720d945-bfae-4590-98e7-70049c9a22b8` contém uma obrigação real de Hands-On Lab: após o reveal, deve existir uma área de exposição para testes práticos de JOVI X300 Ultra, X300 FE e Buds Pro.

O H2 já bloqueava produto quando o próprio container `Foco do Produto` / `testes práticos de:` estava disponível para a classificação. O survivor provou uma lacuna mais específica: quando o legacy row encontra uma Evidence Unit que é apenas o nome do modelo e o legacy `source_reference` diz `Entregáveis`, a regra genérica de deliverable ainda podia vencer e transformar o objeto em Requirement.

Depois disso, a obrigação real do Hands-On Lab enxergava uma identidade existente com o mesmo nome contido no texto e podia ser anexada à identidade errada.

Os 7 `domain_object_evidence` associados ao survivor são histórico acumulado de runs anteriores. Eles comprovam provenance, mas não tornam a identidade semanticamente correta.

---

## O que o H3 corrige

### 1. Bare product/model label não é Requirement por si só

Um Evidence Unit que contém apenas um rótulo nominal com código de modelo/SKU, por exemplo:

- `JOVI X300 Ultra`
- `Acme V70 Pro`
- `Galaxy S24 Ultra`

passa a ser classificado como:

```text
product_attribute / no_domain_object
```

A regra é estrutural e genérica. Não contém `JOVI`, `X300` ou outro nome de cliente/produto hardcoded.

O detector exige que:

- o Evidence Unit seja apenas o rótulo nominal;
- não exista modalidade/obrigação explícita na frase;
- exista um token de modelo compacto com letras + pelo menos dois dígitos, como `X300`, `S24`, `V70`.

### 2. Não demove um deliverable real só porque ele contém número

Casos como:

```text
Vídeo 30s
```

continuam elegíveis como Requirement quando o contexto de deliverable sustenta isso.

### 3. Obrigação explícita com produto continua Requirement

Exemplo:

```text
Entregar 3 unidades do X300 Ultra
```

continua `requirement_candidate`.

O H3 não elimina menções de produto; ele separa **objeto** de **obrigação**.

### 4. O two-pass isolation já existente faz o restante

Quando `JOVI X300 Ultra` passa a `product_attribute` no legacy recall:

1. sua Requirement identity entra em `blocked_existing_ids`;
2. Evidence-first não pode mais anexar a obrigação do Hands-On Lab a essa identidade;
3. a ocorrência antiga ligada ao produto deixa de fazer parte do canonical bundle e é superseded pelo RPC já instalado;
4. a obrigação real do Hands-On Lab cria ou encontra sua própria Requirement identity;
5. a identidade legacy `JOVI X300 Ultra` continua preservada para histórico/recall, mas não decide Requirement truth.

Nenhum DELETE e nenhum auto-merge de duas identities existentes.

---

## Arquivos a substituir no GitHub

Substitua somente:

```text
project_requirement_semantic_extractor.py
project_requirement_reconciliation.py
pages/14_Importar_Projeto.py
tests/test_v28_7_2c0_2_evidence_first.py
```

O arquivo abaixo é somente para validação no Supabase e **não precisa ir para o GitHub**:

```text
NAVE_V28_7_2C0_2_4H3_VERIFY_GOLDEN_JOVI.sql
```

---

## SQL de migration

**NÃO.**

O H3 reutiliza integralmente o contrato SQL já instalado em `28.7.2c0.2.4` / H1.

Não rode novamente migrations C0.2.4.

---

## Validação local executada

Suite C0.2/H3:

```text
42 passed
```

Inclui regressões para:

- bare product/model legacy row;
- regra genérica sem nome de cliente;
- `Vídeo 30s` como negative control;
- obrigação explícita que menciona modelo;
- reprodução do survivor real: legacy product identity é bloqueada antes do Evidence-first binding;
- todos os testes anteriores de suggestion/example/parameter/constraint/form prompt/identity isolation/fail-closed.

---

## Passo a passo operacional

1. Suba os quatro arquivos acima nos caminhos correspondentes do GitHub.
2. Commit/push.
3. Faça **Manage app → Reboot app**.
4. **Não reenvie nem reprocese os masters.**
5. Abra **Lançamento Jovi X300**.
6. Clique uma única vez em:

   `Reconciliar Requirements + Core Semantics · V28.7.2C0.2.4H3`

7. Não execute B manualmente.
8. Aguarde a materialização completa.
9. Envie prints dos quatro painéis principais e de qualquer aviso.
10. Rode no Supabase, read-only:

   `NAVE_V28_7_2C0_2_4H3_VERIFY_GOLDEN_JOVI.sql`

11. Exporte a única linha para CSV e envie.

---

## Gates específicos do H3

Além dos gates anteriores, o verifier exige:

```text
c024h3_run_completed = true
jovi_product_model_not_current_requirement = true
jovi_bare_model_legacy_recall_is_no_domain = true
hands_on_lab_not_bound_to_bare_product_identity = true
product_audience_platform_examples_not_current_requirements = true
semantic_gate_pass = true
semantic_gate_has_zero_blockers = true
no_open_requirement_observations = true
no_observation_review_required = true
no_conflicted_requirement_identity = true
no_unexplained_legacy_shadow = true
b_ran_after_c024_gate = true
```

A cardinalidade total de Requirement identities continua **não sendo gate**. Precisão semântica e provenance continuam sendo o critério.

---

### Operacional

**SQL de migration:** NÃO  
**Verifier SQL read-only:** SIM  
**Reboot:** SIM  
**Reprocessar masters:** NÃO  
**Rodar B manualmente:** NÃO  
**Graph V28.6:** permanece congelado  
**migration_mode:** permanece `legacy_shadow`
