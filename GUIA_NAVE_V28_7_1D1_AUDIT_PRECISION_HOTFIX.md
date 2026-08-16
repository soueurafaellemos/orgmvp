# NAVE by VOE · V28.7.1D1 — Audit Precision Hotfix

## Motivo

A primeira execução real da V28.7.1D provou que o Truth Gate central está funcionando, mas também revelou três problemas de precisão nos analistas determinísticos:

1. `item_results` logísticos do relatório pós-evento estavam sendo tratados como candidatos a Project Solution Instance, gerando falsos Coverage Gaps.
2. Identity Audit interpretava itens irmãos na mesma Evidence Unit como possível identidade duplicada e, ao mesmo tempo, deixava escapar o caso de controle `Chaveiro ↔ Pelúcia`.
3. O briefing Chambinho usa checkbox (`☐SIM / ☒NÃO`) para concorrência; o matcher de processo comercial não reconhecia esse formato e, por isso, `direct / not_applicable` não era promovido.

## O que muda

### Coverage Audit

- `item_results` continuam preservados como resultados/logística, mas não geram automaticamente `missing_solution_instance`.
- Somente `activation_result` entra como candidato de cobertura nesta fase.
- Matching de nomes recebe uma tolerância determinística de alias para casos de baixo risco, sem full entity resolution.
- Casos esperados no Golden após rerun:
  - gaps reais: `Amarelinha`, `Pescaria`, `Distribuição de Produtos`, `Folhas para colorir`;
  - não devem permanecer como gaps: `Mascote Chambinho (Chambão)`, `Oficina de Origami`, `Tatuagem`;
  - materiais como `Bola de sabão`, `Garrafinhas`, `Pouchs`, `Polpas`, `Petit Morango`, `Petit Banana e Maçã`, `Lápis coração` não são tratados como solution gaps só por aparecerem na tabela logística.

### Identity Audit

- Compartilhar página/slide/Evidence Unit deixa de ser suficiente para gerar conflito.
- O audit exige um sinal de identidade real: alias forte ou composição nominal explícita, como `Chaveiro de pelúcia`.
- Casos esperados no Golden:
  - `Chaveiro ↔ Pelúcia` deve aparecer;
  - `Meias ↔ Asas`, `Munhequeira ↔ Adesivos`, `Munhequeira ↔ Faixa para Cabelo` e `Adesivos ↔ Faixa para Cabelo` não devem aparecer apenas por coocorrência na mesma página.

### Commercial semantics

- Reconhece briefings com checkbox: `CONCORRENCIA: ☐SIM ... ☒NÃO`.
- Quando o mesmo fato aparece em wrapper de documento e em fragmento atômico, seleciona a Evidence Unit mais atômica.
- Esperado no Golden:
  - `process_type = direct` current truth;
  - `commercial_result = not_applicable` current truth;
  - `commercial_result = won` legado permanece `legacy_unverified` e nunca current.

## GitHub

Substituir:

- `project_domain_normalization.py`
- `project_domain_truth_audit.py`

Adicionar/substituir testes:

- `tests/test_v28_7_1d_domain_audits.py`
- `tests/test_v28_7_1d_requirement_binding.py`

## SQL

**NÃO.** A camada SQL da V28.7.1D permanece válida.

## Reboot

**SIM.** Após subir os arquivos.

## Depois do reboot

1. Abrir o mesmo Festivalzinho Chambinho.
2. Clicar novamente em `Atualizar domínio e auditar verdade`.
3. Não reprocessar os masters.
4. Executar novamente `NAVE_V28_7_1D_VERIFY_GOLDEN_CHAMBINHO.sql`.
5. Enviar o painel e o resultado/export do SQL antes de aprovar a V28.7.1D.

## Testes locais

18 testes específicos V28.7.1D/D1 passaram após o hotfix.
