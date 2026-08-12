# NAVE IQ Bench — Candidate Response Contract v1

O runner **não conhece clientes nem projetos de produção**. Ele recebe um case de avaliação e uma saída estruturada do pipeline candidato. Essa saída pode conter somente os blocos que o pipeline consegue produzir; métricas não observáveis ficam como `NOT_EVALUATED`, nunca são inventadas.

## Forma geral

```json
{
  "source_roles": {
    "briefing": "briefing_original",
    "proposal": "proposal_presentation"
  },
  "entities": [
    {"id": "cinemateca", "type": "venue", "canonical_name": "Cinemateca"}
  ],
  "claims": [
    {
      "subject": "project",
      "predicate": "budget_max",
      "value_numeric": 1300000,
      "currency": "BRL",
      "evidence_refs": ["briefing:p20"]
    }
  ],
  "relations": [
    {
      "source": "project",
      "relation": "uses_venue",
      "target": "cinemateca",
      "evidence_refs": ["proposal:p48"]
    }
  ],
  "financial": {
    "proposed_total": 1499590.31,
    "after_tax_total": 1499590.31,
    "actual_total": null,
    "top_categories_after_tax": [["Scenic & Event Production", 416586.36]]
  },
  "feedback_claims": [
    {
      "target": "cinemateca",
      "polarity": "negative",
      "topic": "venue_capacity",
      "evidence_refs": ["feedback:claim2"]
    }
  ],
  "findings": [
    {
      "kind": "risk",
      "severity": "high",
      "text": "A proposta excede o teto do briefing.",
      "evidence_roles": ["briefing", "budget"],
      "evidence_refs": ["briefing:p20", "budget:row94"]
    }
  ],
  "execution_state": "not_evidenced",
  "conflict_sets": [],
  "current_values": {},
  "facts": {},
  "retrieval": {
    "ranking": ["B", "D", "A", "C"]
  }
}
```

## Regras

- `orçado/proposto` nunca deve ser colocado em `actual_total` sem fonte de execução.
- Evidência deve ser identificável por uma referência estável. A v1 aceita strings; o Intelligence Graph depois usará UUIDs de `evidence_units`.
- `claims`, `relations` e `feedback_claims` devem preferir IDs/keys estáveis em `subject`, `source`, `target`.
- Um pipeline pode omitir campos ainda não implementados. O runner marcará as métricas dependentes como não avaliadas ou zero apenas quando o case exige explicitamente aquele resultado e há resposta candidata.
- O adapter deve retornar `None` quando deliberadamente não suporta um case; com `--require-all`, isso bloqueia o run.

## Adapter callable

Um adapter Python futuro deve expor:

```python
def run_case(case: Mapping[str, Any], fixture_status: Mapping[str, Any]) -> dict[str, Any] | None:
    ...
```

E pode ser executado com:

```bash
python scripts/run_iq_bench.py \
  --adapter meu_adapter:run_case \
  --fixtures /caminho/seguro/fixtures \
  --pipeline-version file-analyst-v1
```
