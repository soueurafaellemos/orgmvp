# NAVE by VOE · V28.7.2C0.2.4H2
## Structural Role Boundary Hotfix

### Por que este hotfix existe

O H1 concluiu tecnicamente com `Semantic Gate PASS`, mas o Golden JOVI ainda revelou três falhas semânticas de precisão:

1. `JOVI X300 Ultra` permaneceu como Requirement verificado, embora na fonte apareça como produto/alvo de teste, não como obrigação autônoma.
2. `É necessário desenharmos/sugerirmos o timing...` foi rebaixado para `suggestion_signal` porque o verbo **sugerir** venceu indevidamente a modalidade obrigatória **é necessário**.
3. O corpus contém exemplos explícitos após um container `...como:`, mas `classified_example` ficou em zero porque o parent e os exemplos estão em Evidence Units consecutivas.

O H2 corrige esses três limites de forma estrutural e generalizável. Não adiciona regras por nome de cliente ou produto.

---

## O que muda

### 1. Obrigação forte vence verbo de sugestão dentro da mesma cláusula

Exemplo:

`É necessário desenharmos/sugerirmos o timing dessa apresentação...`

Agora continua `requirement_candidate`.

Por outro lado:

`Vale sugerirmos também o presskit...`

continua `suggestion_signal` e não vira Requirement.

### 2. Produto listado como target não vira Requirement autônomo

Containers como:

- `Foco do Produto`
- `testes práticos de:`
- `produtos a testar`
- `products to test`

passam a classificar o item nominal listado como `product_attribute`, mesmo quando o parent é uma obrigação.

A regra olha para a estrutura da fonte, não para `JOVI`, `X300` ou qualquer nome específico.

### 3. Containers de exemplo atravessam a fronteira entre Evidence Units

Quando uma Evidence Unit termina em algo como:

`A experiência deve permitir testes em um ambiente dinâmico, como:`

os itens das Evidence Units seguintes, como:

- `Mini show ao vivo`
- `Performance com muito movimento`

são preservados como `example_signal`, sem virar Requirement.

### 4. Nada muda no contrato do banco

O H2 reutiliza o schema/contrato SQL instalado pelo H1 (`28.7.2c0.2.4`).

**Não há SQL de migration para executar neste hotfix.**

---

## Arquivos a substituir no GitHub

Substitua somente:

```text
project_requirement_semantic_extractor.py
project_requirement_reconciliation.py
pages/14_Importar_Projeto.py
tests/test_v28_7_2c0_2_evidence_first.py
```

Não substitua:

```text
project_requirement_identity.py
```

Não rode novamente o SQL do H1 se ele já está instalado e o smoke test anterior retornou:

```text
resolution_action_contract_ok = true
status_view_ok = true
```

---

## Validação local executada

Suite específica C0.2/H2:

```text
37 passed
```

Foram testados explicitamente:

- produto nominal dentro de `Foco do Produto`;
- produto nominal dentro de `testes práticos de:`;
- exemplo herdado entre Evidence Units consecutivas;
- obrigação com `é necessário ... sugerirmos`;
- sugestão real com `vale sugerirmos`;
- regressões anteriores de constraint, form prompt, no-domain, identity isolation e fail-closed.

---

## Passo a passo operacional

1. Suba os quatro arquivos acima para seus caminhos correspondentes no GitHub.
2. Commit/push.
3. Faça **Manage app → Reboot app**.
4. **Não reenvie nem reprocese os masters.**
5. Abra o projeto **Lançamento Jovi X300**.
6. Clique uma única vez em:

   `Reconciliar Requirements + Core Semantics · V28.7.2C0.2.4H2`

7. Não execute B manualmente.
8. Aguarde a materialização completa.
9. Envie prints dos painéis:
   - Domain Truth Gate;
   - Reconciliation Kernel A;
   - Requirement Semantic Reconciliation H2;
   - Core Semantic Domains B;
   - avisos, caso existam.
10. Rode no Supabase o verifier read-only:

   `NAVE_V28_7_2C0_2_4H2_VERIFY_GOLDEN_JOVI.sql`

11. Exporte a única linha resultante para CSV e envie.

---

## Critérios para aprovação do H2 no Golden JOVI

Além dos gates já existentes, esperamos:

```text
c024h2_run_completed = true
product_audience_platform_examples_not_current_requirements = true
jovi_product_model_not_current_requirement = true
example_role_exercised = true
example_boundary_exercised = true
mc_exclusion_is_requirement = true
mandatory_timing_is_requirement = true
mc_exclusion_and_timing_are_separate_requirement_identities = true
role_only_objects_are_no_domain = true
semantic_no_domain_legacy_identity_not_verified = true
semantic_gate_has_zero_blockers = true
no_open_requirement_observations = true
no_observation_review_required = true
no_conflicted_requirement_identity = true
no_unexplained_legacy_shadow = true
b_ran_after_c024_gate = true
```

Não fixamos cardinalidade final de Requirement identities como gate. O objetivo continua sendo precisão semântica + provenance + isolamento de identidade.

---

## O que o H2 NÃO resolve

O painel `Domain Truth Gate & Legacy Isolation · V28.7.1D` ainda pode exibir o snapshot de Requirements capturado antes da etapa C0, enquanto o painel de Requirement Reconciliation mostra o inventário corrente pós-C0. Isso é uma dívida de observabilidade/snapshot, não deve ser misturada à correção semântica deste hotfix.

Depois de aprovarmos o H2 no Golden JOVI, devemos corrigir essa leitura para que o dashboard não apresente cardinalidades aparentemente concorrentes.

---

### Operacional

**SQL de migration:** NÃO  
**Reboot:** SIM  
**Reprocessar masters:** NÃO  
**Rodar B manualmente:** NÃO  
**Graph V28.6:** permanece congelado  
**migration_mode:** permanece `legacy_shadow`
