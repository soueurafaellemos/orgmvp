# NAVE by VOE · V28.7.2C0.2.4H1

## Resolution Action Contract Hotfix

### Por que este hotfix existe

A V28.7.2C0.2.4 introduziu papéis semânticos no runtime de Requirements que resolvem objetos no-domain com ações explícitas como `preserve_context`, `preserve_suggestion`, `preserve_example`, `attach_parameter` e `attach_constraint_qualifier`.

O banco, porém, ainda estava com o `CHECK semantic_observations_resolution_action_check` da geração anterior, que não aceitava essas ações. No JOVI isso apareceu como PostgreSQL `23514` ao tentar persistir `preserve_context`.

O run falhou corretamente e a V28.7.2B foi bloqueada. A materialização anterior permaneceu válida.

Durante a revisão do mesmo patch foi encontrado um segundo defeito latente no Python: após um RPC bem-sucedido, o diagnóstico tentaria acessar `blocked_existing_ids` fora do seu escopo. O H1 corrige isso antes que o próximo run possa encontrá-lo.

### O que muda

- Expande somente o contrato `resolution_action` de `semantic_observations` para todo o vocabulário já emitido pelo runtime C0.2.4.
- Corrige a passagem de `blocked_existing_ids` do planner para os diagnostics.
- Atualiza o rótulo operacional para `V28.7.2C0.2.4H1`.
- Atualiza o verifier do Golden JOVI para exigir um run H1 concluído.

### O que NÃO muda

- Não muda o classificador semântico da C0.2.4.
- Não altera `project_requirement_identity.py`.
- Não altera `project_requirement_semantic_extractor.py`.
- Não limpa Requirements existentes.
- Não reprocessa masters.
- Não reconstrói Graph V28.6.
- Não promove `domain_primary`.

### Arquivos para substituir no GitHub

- `project_requirement_reconciliation.py`
- `pages/14_Importar_Projeto.py`
- `tests/test_v28_7_2c0_2_evidence_first.py`

### SQL para executar no Supabase

- `NAVE_V28_7_2C0_2_4H1_RESOLUTION_ACTION_CONTRACT_HOTFIX.sql`

### Verifier depois do novo run JOVI

- `NAVE_V28_7_2C0_2_4H1_VERIFY_GOLDEN_JOVI.sql`

### Ordem operacional

1. Executar o SQL H1 no Supabase uma única vez.
2. Substituir os três arquivos de código acima no GitHub.
3. Commit/push.
4. Manage app → Reboot app.
5. Não reenviar nem reprocessar masters.
6. Abrir `Lançamento Jovi X300`.
7. Clicar uma única vez em `Reconciliar Requirements + Core Semantics · V28.7.2C0.2.4H1`.
8. Se o Semantic Gate passar, B deve rodar pela própria orquestração. Não rode B manualmente.
9. Tirar prints dos painéis.
10. Rodar o verifier H1 e exportar a única linha CSV.

### Sobre o run que falhou

Não é necessário rollback/cleanup manual. O erro ocorreu dentro do writer transacional e o painel já informa que a materialização anterior permaneceu válida. O registro de `intelligence_runs` com status `error` deve permanecer como auditoria histórica.
