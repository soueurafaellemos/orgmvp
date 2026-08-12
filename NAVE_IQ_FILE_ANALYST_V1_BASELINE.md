# NAVE IQ · File Analyst v1 — Baseline determinístico/offline

Pipeline: `file-analyst-v1`

Este baseline foi executado contra os quatro Golden fixtures reais do JOVI disponíveis na sessão, com SHA-256 validado pelo IQ Bench Runner. O ambiente local não possui uma GEMINI_API_KEY operacional; portanto este resultado mede deliberadamente a camada determinística do File Analyst, não o comportamento multimodal/semântico do deploy.

## Resultado

| Dimensão | Score |
|---|---:|
| Source Understanding | 100.0% |
| Entity Resolution | 50.0% |
| Claim Accuracy | 38.9% |
| Relation Precision | 0.0% |
| Cross-source Reasoning | 0.0% |
| Financial Intelligence | 93.3% |
| Feedback Linking | 0.0% |
| Generalization | 100.0% |

**Overall NAVE IQ: 49.8% — BLOCKED**

## Gates relevantes

- Golden Financial Total Accuracy: PASS
- Forbidden Inference Count: 0
- Critical Relation Precision: FAIL / ainda não existe linker semântico cross-source
- High/Critical Grounding: NOT_EVALUATED / File Analyst não produz findings de projeto high/critical

## Interpretação

Este score é a primeira régua objetiva da nova arquitetura. Ele não deve ser “melhorado” com regras específicas do JOVI. As lacunas apontam diretamente para as próximas camadas arquiteturais:

1. Entity Resolution;
2. Cross-Source Linker;
3. Project Analyst V2;
4. Hybrid Retrieval;
5. Recommendation Intelligence.

O benchmark também revelou que claim precision precisa ganhar rotulagem positiva/negativa mais completa: linhas financeiras adicionais corretas não devem ser tratadas automaticamente como falsos positivos apenas porque o Golden case enumera um subconjunto mínimo de claims esperados.
