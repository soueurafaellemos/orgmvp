# NAVE V28.7.3B2.11 — Governed Response Recall Review Projection

## Purpose

B2.11 combines the governed Current Domain response contract from B2.7.1 with the calibrated recall review signal from B2.10.1.

It is **read-only projection only**.

It does not:
- create or persist Human Review;
- change Truth;
- change `read_mode`;
- set or activate `domain_primary`;
- change matcher thresholds;
- alter active canaries;
- alter Unified served consumers;
- perform cutover.

## Golden evidence that unlocked B2.11

B2.10.1 Golden reruns materially reduced false-positive high-confidence review candidates.

### Chambinho

10 requirements were scanned in recall scope.
Best disposition per requirement:
- 1 `HIGH_CONFIDENCE_REVIEW_CANDIDATE`;
- 2 `PARTIAL_OBLIGATION_COVERAGE`;
- 7 `NO_CANDIDATE`.

Expected controls held:
- Press kit / Seeding → high-confidence review;
- Promotores e monitores → partial when only monitores are evidenced;
- Cobertura de foto e vídeo → partial when only foto is evidenced;
- Restrição de verba e estrutura → no candidate;
- direct cenography payment requirement → no candidate.

### JOVI

75 requirements were scanned in recall scope.
Best disposition per requirement:
- 3 `HIGH_CONFIDENCE_REVIEW_CANDIDATE`;
- 30 `PARTIAL_OBLIGATION_COVERAGE`;
- 8 `REJECT_SOURCE_ROLE_NON_RESPONSE`;
- 8 `REJECT_GENERIC_OVERLAP`;
- 26 `NO_CANDIDATE`.

The three high-confidence requirements were semantically defensible:
- Materiais Gráficos: convite + STD + Reminder;
- Espaço para plenária;
- Storytelling detalhado.

Important false-positive controls held:
- Gift Out requiring 3+ options remained partial because quantity was missing;
- registration/no-queue/foreign constraints remained partial;
- streaming/recording/next-day did not become high-confidence;
- satisfaction survey did not become high-confidence;
- generic creative/logistics overlap did not become high-confidence;
- insights/results/report did not recover from unrelated event agenda evidence;
- BRIEF RECAP / OUR GOAL candidates were rejected as source-role non-response.

## Projected statuses

B2.11 emits one projected status per Current Domain requirement:

- `verified_response`
- `response_review_high_confidence`
- `response_review_visual_or_structured_evidence`
- `response_review_partial`
- `response_review_existing_evidence`
- `false_positive_excluded`
- `no_safely_verified_response`

Critical rule:

> Only a response already verified by B2.7.1 remains `verified_response`.

B2.10.1 recall never creates new Truth. Even `STRICT_SAFE_AUTO_PRESERVED` remains review-only in B2.11.

## Cross-domain responses

Semantic cross-domain responses from the B2.7.1 contract remain preserved separately and are not converted into requirement compliance.

## Next decision after B2.11 Golden run

Run B2.11 for Chambinho and JOVI, export the CSV/JSON, and manually inspect every `response_review_high_confidence` row.

Only after that projection is semantically clean should a separate Human Review persistence/adjudication phase be designed.
