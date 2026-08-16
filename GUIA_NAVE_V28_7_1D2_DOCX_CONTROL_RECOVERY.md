# NAVE by VOE · V28.7.1D2 — DOCX Control-State Recovery

## Motivo

O diagnóstico real da V28.7.1D1 isolou o último gate comercial.

No arquivo-fonte, o briefing contém explicitamente:

`CONCORRENCIA: ☐SIM, Quais agências: ☒NÃO`

Mas a Evidence Unit já persistida contém:

`CONCORRENCIA: SIM, Quais agências: NÃO`

A perda acontece porque `python-docx Paragraph.text` não inclui texto aninhado em alguns controles de conteúdo Word (`w:sdt`). Os símbolos de checkbox existem no DOCX, mas desapareceram durante a extração antiga.

A D1, portanto, estava correta ao se recusar a inferir `direct` apenas pela ordem `SIM ... NÃO`: sem o estado do checkbox, isso seria chute.

## O que a D2 corrige

### 1. Extração DOCX preserva controles de conteúdo

Novo helper `docx_control_text.py` percorre o OOXML em ordem e preserva:

- texto em runs normais;
- texto aninhado em `w:sdt`;
- tabs e quebras;
- símbolos;
- estado explícito de checkbox quando disponível.

Assim, novos Evidence Units e novas materializações deixam de perder `☐ / ☒`.

### 2. Recuperação transitória para projetos já importados

A D2 NÃO exige reprocessar os masters.

Quando a Domain Normalization encontra uma Evidence Unit antiga e ambígua como:

`CONCORRENCIA: SIM ... NÃO`

ela:

1. localiza o mesmo briefing pelo `content_sha256`;
2. lê o arquivo original já armazenado em R2/Supabase Storage;
3. recupera o texto visível do parágrafo diretamente do OOXML;
4. exige checkbox explícito — não infere por posição;
5. mapeia o resultado de volta à Evidence Unit corrente pelo `paragraph_index`;
6. só então permite a regra comercial.

Se o arquivo não puder ser lido ou o checkbox não for comprovado, continua fail-closed.

### 3. Commercial semantics

Com `☐SIM / ☒NÃO` comprovado:

- `process_type = direct` recebe provenance;
- `commercial_result = not_applicable` recebe provenance;
- `commercial_result = won` legado permanece preservado como `legacy_unverified` e não vira current truth.

## Outro ponto encerrado pelo diagnóstico

`proposal 16/17` versus `proposal_status current = 15` não é bug do resolver.

O diagnóstico mostra:

- 17 candidatos `proposal_status` ativos;
- 16 são `proposed + verified`;
- 1 é `approved + legacy_unverified` no entity do projeto;
- os 16 eventos verificados pertencem a 15 solution entities, pois uma solution instance possui duas ocorrências/eventos de proposta.

O resolver corretamente produz 15 current proposal truths, uma por solution entity + outcome type.

## Arquivos do GitHub

### Substituir

- `project_domain_normalization.py`
- `file_analyst.py`
- `project_batch_ingestion.py`

### Adicionar

- `docx_control_text.py`
- `tests/test_v28_7_1d2_docx_controls.py`

### Teste atualizado

- `tests/test_v28_7_1d_requirement_binding.py`

## SQL

**NÃO.**

A camada SQL V28.7.1D permanece válida.

## Reprocessar masters

**NÃO.**

A D2 lê o briefing original já armazenado apenas para recuperar o estado do controle Word que a extração anterior perdeu.

## Reboot

**SIM.**

Depois de subir os arquivos, execute `Manage app → Reboot app`.

## Reteste Golden Chambinho

1. Abra o mesmo Festivalzinho Chambinho.
2. Clique uma vez em `Atualizar domínio e auditar verdade`.
3. Não reimporte os quatro masters.
4. Confira o painel.
5. Rode novamente `NAVE_V28_7_1D2_DIAGNOSTICO_COMMERCIAL.sql` ou o verify Golden já utilizado.

## Resultado esperado

A cardinalidade exata pode variar se houver outro evento legítimo adicionado entre execuções, mas para o estado atual do Golden esperamos aproximadamente:

- Current truth: **17**;
- Verified: **18**;
- Legacy unverified: **11**;
- candidatos ativos: **29**;
- proposal: **16/17 verified**;
- execution: **0/9 verified**;
- commercial_result: **1/2 verified**;
- current truth por tipo: `proposal_status 15 · process_type 1 · commercial_result 1`;
- Coverage gaps: **4**;
- Identity conflicts: **1**;
- migration mode: `legacy_shadow`;
- Truth Gate: `PASS`.

Os resultados semanticamente obrigatórios são mais importantes que os números:

- `process_type = direct` current/verified;
- `commercial_result = not_applicable` current/verified;
- `won` legado não-current;
- `approved` legado não-current;
- execution legado continua não-current;
- Coverage continua: Amarelinha, Pescaria, Distribuição de Produtos, Folhas para colorir;
- Identity continua: Pelúcia ↔ Chaveiro;
- Graph V28.6 continua congelado.

## Testes locais

- 27 testes diretamente ligados a D/D1/D2 + File Analyst passaram.
- 14 testes adicionais de provenance/runtime passaram; os únicos testes não executáveis integralmente continuam sendo fixtures que tentam abrir o SQL histórico `NAVE_V28_7_1B_DOMAIN_INTEGRITY_SQL_COMPAT.sql`, ausente do ZIP do repositório fornecido.
