# NAVE IQ · V28.2.2 — Validation Note

## Escopo validado offline

A validação desta versão mede a nova camada determinística de Entity Resolution / Cross-Source Linking e regressões focadas da linha V28.

### Testes automatizados

**60 testes focados passaram.**

Incluem:

- regressões V28.1.5 / V28.1.6 / V28.1.7;
- Intelligence Core V28.2.0;
- Golden JOVI;
- File Analyst / Dual-Write V28.2.1;
- IQ Bench Runner;
- Entity Resolution V28.2.2;
- Cross-Source Linker V28.2.2;
- Golden Chambinho V28.2.2.

### Fixtures reais Chambinho

Os quatro arquivos reais foram resolvidos por basename + SHA-256:

**4/4 encontrados · 4/4 hashes corretos.**

Validação determinística sobre os arquivos reais:

- DOCX → `briefing_original` · confiança 0,97;
- PDF 41 páginas → `proposal_presentation` · confiança 0,98;
- XLSM → `detailed_costs` · confiança 0,98;
- PPTX 41 slides → `post_event_report` · confiança 0,97.

Do briefing real, sem Gemini:

- `budget_max = R$ 400.000,00`;
- `expected_attendees = 8.000` como limite superior da faixa declarada do festival;
- requisito `Pagamento direto pelo cliente — cenografia` extraído com evidência.

Da planilha real, sem Gemini:

- `proposed_total = R$ 554.310,85`;
- nenhuma claim de `actual_total` é criada apenas por ser uma planilha de proposta.

### Entity Resolution — casos de controle

- `Cinemateca` ↔ `Cinemateca Brasileira` → AUTO_MERGE;
- `ON TOUR` ↔ `JOVI X300 Series ON TOUR` → AUTO_MERGE;
- `Oficina de Origami` ↔ `Origami coração` → REVIEW, sem merge silencioso;
- entidades de tipos diferentes → DISTINCT;
- `EVENT JOURNEY` ↔ `PRESS KIT` → DISTINCT.

### Limitação deliberada

Não foi atribuído um novo **NAVE IQ Overall** offline para a V28.2.2 porque a principal evolução agora depende do Graph persistido e da leitura semântica do deploy para medir relações reais entre todos os arquivos.

A comparação de score deve ser feita após o primeiro ingest limpo do Golden Chambinho no ambiente com Gemini + Intelligence Foundation.

Essa escolha evita fabricar uma melhora numérica antes de a nova inteligência ter sido observada de ponta a ponta.
