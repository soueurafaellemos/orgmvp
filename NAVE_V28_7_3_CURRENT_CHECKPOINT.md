# NAVE V28.7.3 — Current Governed Checkpoint

## Goldens closed
- H3.1.3 Chambinho/JOVI.
- B2.12.2.2 Chambinho/JOVI.
- B2.12.3 Chambinho/JOVI.
- B2.12.4.1 Chambinho/JOVI.
- H3.1.3P1 normal pipeline promotion Chambinho/JOVI.
- B2.12.5.1 preflight Chambinho: GOLDEN APPROVED.
- B2.12.5.1 preflight JOVI: GOLDEN APPROVED / WRITE AUTHORIZED ONCE.

## Incident
The first JOVI B2.12.5.1 RPC invocation returned a redacted PostgREST APIError at the
RPC boundary. The UI does not expose the database error. No second invocation is allowed.

It is NOT yet proven whether the database transaction rolled back or completed before the
HTTP/API error surfaced.

## Active checkpoint
**V28.7.3B2.12.5.2 — Failed Supersession State Diagnostic**

Read-only only. It consumes the exact reviewed preflight and independently compares live
state against both expected models:
- pre-write state intact;
- transaction completed state.
Any mixed state is classified PARTIAL_OR_UNEXPECTED_STATE.

## Governance freeze
- DO NOT retry B2.12.5.x.
- DO NOT run H3 repair, A/B/Graph, or B2.13.
- Keep requirements shadow_compare.
- Diagnose persisted state first; only then investigate RPC root cause.
