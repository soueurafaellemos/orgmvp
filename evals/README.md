# NAVE IQ Bench v1

O **NAVE IQ Bench** é o contrato de qualidade da inteligência da NAVE. Ele existe para impedir que “parece melhor” seja usado como critério de evolução.

## Objetivo

Medir, de forma versionada e repetível, se uma alteração melhora ou piora:

- compreensão de fonte;
- proveniência;
- resolução de entidades;
- claims;
- relações;
- raciocínio cross-source;
- inteligência financeira;
- vínculo de feedback;
- granularidade de outcomes;
- retrieval;
- recomendação;
- calibração de incerteza;
- generalização;
- performance.

## Tipos de caso

### Golden real project
Usa material real validado. JOVI X300 é o primeiro. Os binários proprietários ficam fora do GitHub; o case identifica fixtures por `basename + sha256`.

### Blind synthetic / Blind real
Valida generalização. Nomes e conteúdos não podem virar regras no core.

### Adversarial
Força a NAVE a tratar conflito, falta de evidência, ambiguidade, versões e estados sem inventar conclusões.

### Retrieval
Mede se a NAVE encontra relevância sem depender de palavras iguais.

## Regra fundamental

**Casos podem conter nomes de clientes/projetos. O código de produção não pode.**

O runner futuro deve carregar `suite.yaml`, executar cada case contra uma versão de pipeline e persistir os resultados em `iq_bench_runs` / `iq_bench_case_results` quando essas tabelas forem criadas na fase de avaliação.

## Gates v1

1. 100% dos findings high/critical precisam de evidência;
2. 100% de exatidão dos totais financeiros em Golden Projects;
3. zero falso `executado` sem evidência;
4. zero propagação de `projeto perdido` para todas as soluções;
5. precisão mínima de 90% nas relações críticas antes de automação sem revisão;
6. Recall@20 mínimo de 95% para retrieval quando o dataset estiver disponível;
7. nenhum Blind Project pode regredir de forma material.

## JOVI como Golden Project, não como regra

O case JOVI exige, entre outras coisas:

- budget máximo de R$ 1,3M;
- total proposto de R$ 1.499.590,31;
- distinção entre proposta e gasto real;
- conceito ON TOUR preservado como aprendizado positivo;
- venue criticado por capacidade;
- críticas separadas para YouTube, Instagram e TikTok;
- resultado comercial perdido sem invalidar todo o projeto;
- findings cruzando briefing, proposta, custo e feedback com evidências.

Se isso funcionar apenas porque “JOVI” aparece em código de produção, o benchmark não está cumprindo sua função.

## Próxima implementação

O próximo passo técnico, depois de aplicar e verificar a Foundation, é criar o **runner mínimo do IQ Bench** antes do File Analyst/dual-write. O runner deve começar sem LLM obrigatório para as métricas determinísticas (financeiro, schemas, forbidden inferences) e incorporar avaliações semânticas versionadas somente onde necessário.
