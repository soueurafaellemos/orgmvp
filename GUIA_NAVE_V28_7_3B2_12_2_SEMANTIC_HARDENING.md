# NAVE V28.7.3B2.12.2 — Semantic Eligibility & Core Obligation Hardening

## Objetivo

B2.12.2 corrige os blockers revelados pelo Golden JOVI sem alterar Truth, sem persistir respostas e sem executar SQL.

O hardening é estrutural e reaproveita a classificação semântica já existente em C0/H3.

## O que muda

1. **Semantic Eligibility Gate**
   - Requirements Current com papel semântico explícito de scope, attribute, context, reference, suggestion, example, parameter ou constraint qualifier são retirados da fila de adjudicação.
   - Eles NÃO viram `recommend_reject`: deixam de ser tratados como Requirement.
   - Requirement `verified` sem papel semântico suficiente falha fechado como `semantic_eligibility_unknown`.
   - `human_confirmed` continua elegível, salvo quando existir sinal explícito de no-domain.

2. **Canonical Obligation Text**
   - O display title deixa de ser a única definição da obrigação.
   - A obrigação canônica é recuperada somente de:
     1. `semantic_observation.attributes.source_atom`; ou
     2. cláusula correspondente dentro do Evidence Unit atual da própria observação.
   - `description` e `source_excerpt` amplos não são usados para completar a obrigação.
   - Isso protege contra titles truncados sem reintroduzir contaminação contextual.

3. **B2.10.2 Canonical Atom Recalibration**
   - Os candidatos B2.9 são recalibrados usando `canonical_obligation_text`.
   - A fila B2.12.2 é reconstruída depois desse gate; portanto o `queue_count` do JOVI NÃO precisa continuar 33.

4. **Core Obligation Hardening com localidade**
   - obrigação financeira exige evidência financeira;
   - travel press kit não satisfaz travel product activation;
   - `PR activation` em outro segmento não neutraliza o guard;
   - `set the stage` não satisfaz palco físico;
   - palco + LED devem ter suporte semanticamente conjunto;
   - qualificadores horizontal/vertical são tratados como obrigatórios quando constam na obrigação canônica.

## Governança

B2.12.2 é **READ ONLY / SHADOW ONLY**.

- `recommend_confirm` NÃO é `verified_response`.
- nenhuma recomendação cria Human Review;
- `truth_changed=false`;
- `persistence_performed=false`;
- `cutover_approved=false`;
- não altera `read_mode`;
- não ativa `domain_primary`;
- não altera canaries;
- não reprocessa Golden masters.

## Arquivos

### ADICIONAR
- `project_requirement_semantic_eligibility.py`
- `project_requirement_auto_adjudication_hardening.py`
- `tests/test_v28_7_3b2_12_2_semantic_hardening.py`
- `GUIA_NAVE_V28_7_3B2_12_2_SEMANTIC_HARDENING.md`

### SUBSTITUIR
- `pages/32_Automated_Adjudication_Recommendations.py`
- `NAVE_V28_7_3_CURRENT_CHECKPOINT.md`

## SQL

**NÃO executar SQL.**

## Teste local opcional

```bash
pytest -q tests/test_v28_7_3b2_12_2_semantic_hardening.py
```

O patch contém regressões para:
- `platform_scope` e `example_signal` fora da fila;
- fail-closed de semantic eligibility;
- recuperação de obligation truncada;
- travel press kit ≠ travel activation;
- F&B ≠ resposta a redução de budget;
- `set the stage` ≠ palco físico;
- horizontal como qualificador obrigatório.

## Golden Verify

Após upload dos arquivos e reboot:

1. Abrir **Automated Adjudication Recommendations**.
2. Confirmar marker `V28.7.3B2.12.2`.
3. Rodar **Chambinho primeiro**.
4. Baixar o JSON completo `NAVE_B2_12_2_SEMANTIC_HARDENING_<project_id>.json`.
5. Enviar o JSON para revisão.
6. Somente após aprovação do Chambinho, rodar JOVI.

### Chambinho

Não existe obrigação de manter exatamente a distribuição B2.12.1. O ponto crítico é:
- Press kit / Seeding continuar semanticamente defensável;
- `Restrição de verba e estrutura` não reaparecer como resposta válida;
- nenhum `semantic_eligibility_unknown`.

### JOVI

O `queue_count` **deve poder cair abaixo de 33**. Isso é esperado se pseudo-requirements forem removidos.

Controles obrigatórios:
- `Storytelling detalhado` não pode entrar como Requirement adjudicável se C0/H3 o classifica como platform/scope/context;
- `Performance com muito movimento` não pode entrar como Requirement independente se é example signal;
- travel-inspired press kit não pode virar resposta parcial à travel product activation apenas por haver `PR activation` no window;
- F&B sem custo/verba não pode virar resposta parcial à obrigação financeira;
- `set the stage` não pode satisfazer palco físico;
- titles truncados devem expor `canonical_obligation_text` source-bounded;
- Gift Out 3+, registration qualifiers, survey, direct payment, co-investment, bilingual promoters, independence, platform format, backstage e recap video devem continuar conservadores.

## Critério para avançar

Só desenhar qualquer Truth-effect/persistence depois de:
- `semantic_unknown_count = 0` nos dois Goldens;
- ausência de falso `recommend_confirm` crítico;
- validação manual dos controles acima;
- exports preservando canonical obligation + provenance.
