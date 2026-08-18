# NAVE by VOE · V28.7.2C0.2.2 — Template Prompt Guard & Lifecycle Alignment

## Diagnóstico do Golden Chambinho

A C0.2/C0.2.1 executou corretamente do ponto de vista transacional e todos os gates técnicos do Verify ficaram verdadeiros.

Também houve melhorias semânticas corretas:

- `Objetivo principal` deixou de ser Requirement truth e virou contexto estratégico;
- `Público-alvo` deixou de ser Requirement truth e virou contexto de audiência;
- a restrição de verba/estrutura foi reconhecida pela rota Evidence-first e reconciliada à identity existente;
- a necessidade de pagamento direto da cenografia antes do evento foi descoberta como nova Requirement evidence-led;
- Solutions, Execution Truth, Finance e Graph congelado não regrediram.

Mas o Golden revelou um falso positivo evidence-led:

`Qual mensagem principal precisa ser transmitida: (O que as pessoas devem sentir, entender e lembrar após a ação)`

No briefing, isso é um campo/template sem resposta preenchida, não uma obrigação do projeto.

O detector de obrigação capturou a palavra `devem` dentro do texto auxiliar entre parênteses e promoveu o prompt inteiro como Requirement.

## Causa estrutural

Evidence-first estava correto ao não depender do inventário legado, mas ainda não distinguia:

- obrigação explícita do projeto;
- pergunta/instrução de formulário;
- prompt parentético de preenchimento.

Isso é um problema genérico de documentos de briefing, não específico de Chambinho.

## Correção runtime

A C0.2.2 adiciona um `Template Prompt Guard`.

Uma linha é tratada como prompt vazio quando:

- possui label interrogativo/form-like antes de `:`;
- e o conteúdo após `:` está vazio ou contém apenas orientação parentética.

Exemplo bloqueado:

`Qual mensagem principal precisa ser transmitida: (O que as pessoas devem sentir...)`

Exemplo NÃO bloqueado:

`Qual mensagem principal precisa ser transmitida: Conhecer ambas as marcas e atributos`

A regra não contém nomes de clientes ou Goldens.

Também foi adicionada a classe semântica `form_prompt` para o caso de um prompt semelhante já existir como Requirement legado. Ele vira `no_domain_object`, nunca current Requirement truth.

## Lifecycle Alignment

A C0.2 já supersedia observation, occurrence e governance quando uma identity evidence-led desaparecia da fonte canônica.

A C0.2.2 completa o lifecycle:

- `project_requirements.status -> superseded`;
- `knowledge_entities.status -> inactive`;
- `domain_object_governance.lifecycle_status -> superseded`.

Se a mesma obrigação evidence-led voltar legitimamente numa run futura, o writer pode reativá-la.

Não há DELETE.

## Resultado esperado no Chambinho

Depois de uma nova run:

- Legacy rows: 14
- Current Requirement identities: 13
- Verified: 13
- Legacy unverified: 2
- Occurrences com Evidence: 13
- Semantic observations: 16
- Legacy recall: 14
- Evidence-first: 2
- Reconciled: 14
- No-domain: 2
- Context: 2
- Novos evidence-led current: 1
- Constraints: 2
- Open: 0
- Review required: 0
- Conflicted: 0

O único Requirement evidence-led novo que deve permanecer current neste Golden é:

`Precisamos organizar para pagarem a cenografia de forma direta antes do evento acontecer para evitar bitributação.`

A observation Evidence-first da restrição de verba/estrutura continua existindo, mas converge para a identity legado já existente.

## Regressões obrigatórias

Devem continuar:

- Solutions 19
- Solution Occurrences 36
- Execution Truth verified 8
- Financial lines 54/54 com Evidence
- Truth Gate PASS
- Graph V28.6 congelado
- migration_mode = legacy_shadow
- nenhum auto-merge entre Requirement identities existentes

## SQL

SIM.

Executar uma única vez:

`NAVE_V28_7_2C0_2_2_TEMPLATE_PROMPT_GUARD.sql`

Não executar novamente C0, C0.1, C0.2 ou C0.2.1.

## GitHub

Substituir exatamente:

- `project_requirement_semantic_extractor.py`
- `project_requirement_reconciliation.py`
- `pages/14_Importar_Projeto.py`
- `tests/test_v28_7_2c0_2_evidence_first.py`

Nenhum outro arquivo precisa ser alterado.

## Reboot

SIM.

Depois do SQL e do commit GitHub:

`Streamlit → Manage app → Reboot app`

## Teste

1. Não reprocessar os masters.
2. Abrir `Festivalzinho Chambinho`.
3. Executar uma única vez `Reconciliar Requirements + Core Semantics · V28.7.2C0.2.2`.
4. Rodar `NAVE_V28_7_2C0_2_2_VERIFY_GOLDEN_CHAMBINHO.sql`.
5. Exportar o CSV.
6. Enviar print completo + CSV.
7. Ainda não rodar JOVI.

## Validação local

- `py_compile`: PASS
- suíte focada C0.2/C0.2.2: 14 PASS
- regressões adicionais:
  - prompt parentético vazio não vira Requirement;
  - prompt com resposta substantiva não é descartado pelo guard;
  - formulário `Números: (...)` não vira Requirement;
  - prompt legado é classificado como `form_prompt/no_domain`;
  - lifecycle evidence-led superseded é preservado sem DELETE.

## Estado

- migration_mode: legacy_shadow
- domain_primary: NÃO
- Graph V28.6: congelado
- C1 Decision/Feedback: bloqueada
