# NAVE V28.7.3B2.10.1 — Canonical Obligation Atom Calibration

B2.10 Golden CSVs exposed a real bug: canonical requirement atoms were built from
`title + description + source_excerpt`.

In JOVI this created impossible atom sets. Examples:
- `A agência deve propor insights relevantes e incluir os resultados no relatório`
  became `gifts | guests | plenary`.
- `Pesquisa curta ao final do evento...` also became `gifts | guests | plenary`.
- `Espaço para plenária` inherited unrelated atoms such as promoter, reception,
  registration, screen and stage.

This made some `HIGH_CONFIDENCE_REVIEW_CANDIDATE` rows false.

B2.10.1 fixes this:
1. requirement atoms = canonical TITLE only;
2. explicit generic obligation qualifiers are recognized;
3. BRIEF RECAP / OUR GOAL are rejected as non-response source roles;
4. long requirements cannot become high-confidence from only two generic atoms;
5. HIGH_CONFIDENCE remains REVIEW ONLY;
6. max 2 candidates per requirement.

Expected stable cases:
- Chambinho Press Kit / Seeding => HIGH_CONFIDENCE REVIEW.
- Chambinho Promotores e monitores => PARTIAL.
- Chambinho foto e vídeo with photo only => PARTIAL.
- JOVI convite + STD + Reminder => HIGH_CONFIDENCE REVIEW.
- JOVI Storytelling detalhado => HIGH_CONFIDENCE REVIEW.
- JOVI Gift Out 3+ without 3/options => PARTIAL.
- BRIEF RECAP overlaps => REJECT_SOURCE_ROLE_NON_RESPONSE.

No SQL. No writes. No Truth/readiness/read_mode/domain_primary changes.
No matcher/threshold changes. No Unified served consumer changes.
