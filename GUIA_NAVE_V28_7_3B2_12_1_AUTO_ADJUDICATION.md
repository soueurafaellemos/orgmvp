# NAVE V28.7.3B2.12.1 — Automated Response Adjudication Recommendations

## Why
B2.12 proved the provenance contract, but a row-by-row human workflow is not acceptable as the default operating model. B2.12.1 therefore automates the disposition recommendation for the entire B2.12 review queue.

## Governance
This phase is machine-only and read-only.

`recommend_confirm` is NOT `verified_response`.
It is NOT Human Review.
It has no Truth effect.
Nothing is persisted.
No cutover is approved.

## Output
Every review candidate receives one of:
- `recommend_confirm`
- `recommend_partial`
- `recommend_reject`
- `recommend_visual_review`
- `recommend_defer`

The output also carries:
- machine confidence;
- machine rule id;
- rationale;
- full candidate/provenance snapshot from B2.12.

## Rationale
The recommendation engine first applies high-precision semantic guards for core obligations that lexical overlap commonly misreads (survey, direct payment, co-investment, recap video, VIP mailing, independence without partners, bilingual promoters, day/night scenarios, travel activation vs press kit, backstage, platform-format constraints). It then applies the governed obligation coverage/anchor signals.

## Human work
No row-by-row human decision is required for B2.12.1.

The old B2.12 Human Response Adjudication Contract remains available only as an optional/manual provenance mechanism. It is not the default path for migration.

## Next
Run B2.12.1 on both Goldens. Inspect the machine recommendation distribution and obvious controls. Only after that should any persistence or Truth-effect phase be designed.
