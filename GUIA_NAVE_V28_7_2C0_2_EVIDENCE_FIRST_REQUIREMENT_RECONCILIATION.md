# NAVE by VOE · V28.7.2C0.2
## Evidence-First Requirement Reconciliation

### O que esta versão corrige

O Golden JOVI provou três falhas estruturais da C0 anterior:

1. **Evidence existente estava funcionando como passe semântico.**
   Um legacy Requirement que já possuía `domain_object_evidence` era tratado como `requirement_mention` sem passar novamente pelo classificador.

2. **O inventário legado estava sendo tratado como universo de Requirements.**
   No diagnóstico JOVI, o briefing possui 195 Evidence Units; 52 unidades apresentaram sinal forte de obrigação e 37 dessas ainda não possuíam nenhuma Requirement Observation. A C0 anterior observava exatamente as 63 linhas legadas, portanto não conseguia descobrir obrigações que o parser antigo nunca criou.

3. **Occurrence e provenance antigos podiam manter um falso Requirement verificado.**
   Um `domain_object_evidence` histórico provava que um texto existe na fonte, mas não que aquele texto é uma Requirement Identity correta.

A C0.2 implementa duas rotas independentes antes da reconciliação:

`Legacy Requirement recall → Semantic Gate`

`Current briefing Evidence → explicit obligation discovery`

As duas convergem em Identity Reconciliation. Duas Requirement identities existentes continuam **nunca sendo auto-merged**.

---

## Mudanças principais

### 1. Todo legacy Requirement passa pelo mesmo Semantic Gate

A regra antiga `already_bound → requirement_mention` foi removida.

Ter Evidence previamente ligada não protege mais uma identity de reclassificação como:

- scope / canal;
- product attribute;
- context;
- strategy context;
- reference;
- constraint;
- Requirement.

### 2. Evidence-first discovery

A C0.2 varre somente Evidence atual do briefing e identifica obrigações explícitas sem depender de `memory_briefing_requirements`.

Reconhece genericamente estruturas como:

- `deve / deverá / devemos`;
- `é necessário / não é necessário`;
- `temos que`;
- `considerar`;
- `apresentar`;
- `incluir`;
- `reservar`;
- `criar / desenvolver / desenhar / garantir / entregar`;
- equivalentes em inglês.

Sugestões como `vale sugerir`, `podemos considerar` e `recomenda-se` não são automaticamente promovidas a Requirement truth.

### 3. Atomização estrutural

Listas explicitamente obrigatórias podem gerar atoms verificáveis. Exemplos genéricos:

- `O local deve contemplar:` + itens;
- `A ativação deve explorar:` + itens;
- `A proposta deverá contemplar ... para:` + itens;
- `Considerar:` + itens.

Referências/filenames não viram Requirement identities.

### 4. Truth Gate corrigido

`domain_object_evidence` histórico continua preservado para auditoria, mas **não verifica sozinho** uma Requirement.

Current truth passa a depender de:

- Current Requirement Occurrence com Evidence; ou
- Human Review confirmado/corrigido.

Se a latest semantic observation do legacy row disser scope/attribute/context/reference, ele permanece `legacy_unverified`, mesmo que exista um binding antigo.

### 5. Supersession sem DELETE

Observations e occurrences C0 antigas que não pertencem mais à geração canônica são marcadas como `superseded`.

Nada é apagado.

Uma extração vazia em projeto que já possui legacy Requirements é **fail-closed** e não substitui o estado anterior.

### 6. Occurrence identity estabilizada

Occurrence agora é deduplicada por:

`project + requirement identity + evidence unit + occurrence role`

O texto observado deixou de participar do hash. Assim, legacy recall e evidence-first podem convergir para a mesma occurrence.

---

## Arquivos a substituir no GitHub

Substitua exatamente:

- `project_requirement_semantic_extractor.py`
- `project_requirement_reconciliation.py`
- `project_requirement_identity.py`
- `pages/14_Importar_Projeto.py`

Adicione:

- `tests/test_v28_7_2c0_2_evidence_first.py`

Os SQLs e este guia não precisam ir para uma pasta Python específica; mantenha-os na raiz do repositório se você já versiona migrations/verificadores no GitHub.

---

## SQL — obrigatório

Execute no Supabase SQL Editor, inteiro:

`NAVE_V28_7_2C0_2_EVIDENCE_FIRST_REQUIREMENT_RECONCILIATION.sql`

É um patch incremental sobre V28.7.2C0 + C0.1.

Não reexecute a migration C0 original.

---

## Ordem de instalação

1. Execute `NAVE_V28_7_2C0_2_EVIDENCE_FIRST_REQUIREMENT_RECONCILIATION.sql` no Supabase.
2. Suba os arquivos Python acima para os respectivos caminhos no GitHub.
3. Faça **Manage app → Reboot app**.
4. Abra o projeto Golden **Festivalzinho Chambinho**.
5. Reprocesse/reconcilie pelo botão **Reconciliar Requirements + Core Semantics · V28.7.2C0.2**.
6. Não altere masters nem reenvie arquivos.
7. Execute `NAVE_V28_7_2C0_2_VERIFY_GOLDEN_CHAMBINHO.sql` e exporte o resultado como CSV.
8. Envie os prints da C0.2 + o CSV para auditoria.

**Não rode o Golden JOVI ainda.** Ele só entra depois da validação semântica do Chambinho nesta nova lógica.

---

## O que deve permanecer congelado

- `migration_mode = legacy_shadow`;
- Graph V28.6;
- nenhum `domain_primary`;
- nenhuma reconstrução de Graph V2;
- nenhum auto-merge de Requirement identities existentes;
- nenhuma exclusão destrutiva de legacy knowledge.

---

## Critério de aprovação do Golden Chambinho

Não existe mais requisito de preservar artificialmente a cardinalidade antiga de Requirements.

O Golden passa somente se:

- todos os legacy rows tiverem passado pelo Semantic Gate;
- Evidence-first realmente tiver sido exercitado;
- não houver observation aberta por falha de pipeline;
- todo current Requirement tiver occurrence/evidence válida ou Human Review;
- no-domain semantic signals não continuarem `verified` apenas por Evidence histórica;
- nenhum shadow permanecer sem explicação;
- Solution / Execution / Finance não regredirem;
- Graph V28.6 não for reconstruído.

Se a cardinalidade mudar porque um antigo “Requirement” era na verdade Context/Scope/Reference, isso é **correção semântica**, não regressão.

---

## Validação local antes da entrega

- `py_compile`: OK nos arquivos alterados.
- Suite C0 + contratos adjacentes: **41 testes aprovados**.
- Testes novos cobrem:
  - removal do semantic bypass por Evidence antiga;
  - channel/platform scope;
  - product attributes;
  - filename/reference rejection;
  - evidence-first recall;
  - negative obligations;
  - suggestion suppression;
  - atomic list extraction;
  - role-independent observation identity;
  - convergence legacy + evidence-first em uma occurrence;
  - Truth Gate sem Evidence-bypass;
  - supersession sem DELETE.
