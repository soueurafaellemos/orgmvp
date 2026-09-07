# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed
- H3.1.3 Chambinho/JOVI: GOLDEN APPROVED.
- B2.12.2.2 Chambinho/JOVI: GOLDEN APPROVED.
- B2.12.3 Chambinho/JOVI: GOLDEN APPROVED.
- B2.12.4.1 Chambinho/JOVI: GOLDEN APPROVED.
- H3.1.3P1 normal pipeline promotion:
  - Chambinho: GOLDEN APPROVED.
  - JOVI: GOLDEN APPROVED.
  - normal Requirement entrypoint = project_requirement_reconciliation_h31.
  - requirements remain shadow_compare.
  - no pipeline/A/B/Graph rerun caused by promotion.

## Active checkpoint

**V28.7.3B2.12.5 — Governed Transactional Requirement Identity Supersession**

This is the first real write in the B2.12.x identity-collision sequence.

## Writer invariants
- fresh B2.12.4.1 is rebuilt immediately before RPC;
- H3.1.3P1 contract must still be active;
- explicit confirmation token required;
- PostgreSQL advisory transaction lock per project;
- no DELETE;
- superseded Requirement -> status superseded;
- superseded Governance -> lifecycle superseded + superseded_by_entity_id;
- superseded Knowledge Entity -> merged + canonical_entity_id;
- duplicate occurrence -> superseded, or unique occurrence -> rebind with dry-run target hash;
- Legacy alias preserved structurally;
- historical Domain Evidence links preserved;
- no new occurrence evidence links;
- at most coalesced source Evidence link inserted;
- historical semantic observations untouched;
- survivor business metadata unchanged;
- Human Review not synthesized;
- response Truth unchanged;
- requirements read_mode remains shadow_compare;
- postcondition failure raises and rolls back the entire RPC.

## Verification
Independent page `Requirement Supersession Post-Transaction Verifier` must pass after write:
- Current count expected;
- old identity historical;
- survivor Current;
- lineage complete;
- no active occurrence on old identity;
- canonical collision count 0;
- B2.1 compatibility PASS;
- aliases uniquely resolve to survivor;
- historical Evidence/Semantic counts preserved;
- no occurrence Evidence written by B2.12.5;
- H3.1.3P1 still active;
- shadow_compare unchanged.

## Execution order
1. Apply B2.12.5 SQL migration.
2. Deploy code + reboot.
3. Run B2.12.5 PRE-FLIGHT on Chambinho only.
4. Expected: NO_TRANSACTION_REQUIRED; no write button.
5. Send preflight JSON for Golden control approval.
6. Only after approval prepare JOVI preflight.
7. Explicitly execute JOVI transactional write once.
8. Do not rerun writer.
9. Run independent post-transaction verifier and send JSON.
10. B2.13 remains blocked until post-transaction Golden closes.
