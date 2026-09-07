# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed
- H3.1.3 Chambinho: GOLDEN APPROVED.
- H3.1.3 JOVI: GOLDEN APPROVED.
- B2.12.2.2 Chambinho: GOLDEN APPROVED.
- B2.12.2.2 JOVI: GOLDEN APPROVED.
- B2.12.3 Chambinho: GOLDEN APPROVED — 0 collisions.
- B2.12.3 JOVI: GOLDEN APPROVED — 1 exact collision, survivor evidence-led/full-title/source_atom.

## Active checkpoint
**V28.7.3B2.12.4 — Transactional Requirement Identity Supersession · DRY RUN**

B2.13 remains blocked.

## Existing schema already supports supersession
- `project_requirements.status='superseded'`;
- `domain_object_governance.lifecycle_status='superseded'`;
- `domain_object_governance.superseded_by_entity_id`;
- `knowledge_entities.canonical_entity_id`;
- Requirement Truth maps superseded identities to historical.

## Critical occurrence invariant
`project_requirement_occurrences.occurrence_hash` includes requirement_id.
Rebinding requirement_id requires a recomputed hash. If that hash already exists, the old occurrence must be superseded.

## Governance freeze
No writes, Human Review synthesis, Truth effect, domain_primary, canary/read_mode change, master reprocessing or B2.13.

## Golden order
Chambinho first, then JOVI. Only after both pass may B2.12.5 be designed as the first real governed supersession transaction.
