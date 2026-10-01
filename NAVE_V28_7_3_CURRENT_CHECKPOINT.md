# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed
- H3.1.3 Chambinho/JOVI.
- B2.12.2.2 Chambinho/JOVI.
- B2.12.3 identity collision shadow Chambinho/JOVI.
- B2.12.4.1 transaction integrity Chambinho/JOVI.
- H3.1.3P1 normal-pipeline promotion Chambinho/JOVI.
- B2.12.5.4 real transactional Requirement identity supersession JOVI.
- B2.12.5.4 independent post-transaction verification: PASS / all checks true.

## Active checkpoint
**V28.7.3B2.13.1 — Post-Supersession Response Projection Integrity Shadow / Packaged Golden Baselines**

B2.13 remains READ ONLY.

B2.13.1 corrects the operator contract: Golden projects are explicitly selectable in the
page and their original B2.12.2.2 baselines are packaged immutably in the repo, with
SHA-256 validation. Manual JSON upload is removed from the normal Golden path.

### Golden order
1. Festivalzinho Chambinho — control, no supersession.
2. Lançamento Jovi X300 — post-supersession.

### Governance
- no Requirement writer rerun;
- no Human Review synthesis;
- no Response Truth persistence;
- no cutover;
- no A/B/Graph rerun;
- no `domain_primary`;
- requirements remain `shadow_compare`.

Only after B2.13.1 Chambinho + JOVI Goldens may a later Truth-effect design be discussed.
