# NAVE by VOE — V28.7.3B2.12.2.1
## Semantic Precedence Veto + Hard Qualifier Hotfix

### Por que esta hotfix existe

O Golden JOVI de B2.12.2 retornou `75 -> 75` no Semantic Eligibility Gate e manteve
`Storytelling detalhado.` como `requirement_candidate` + `recommend_confirm`.

Isso contradiz o Golden H3 já aprovado, que estabeleceu que sinais como:
- `Storytelling detalhado`
- `Mini show ao vivo`
- `Performance com muito movimento`
- `Frequentadores de festivais de música`
- `Universo da moda e lifestyle`

não podem existir como Current Requirement Truth quando a reconciliação semântica os
classifica como scope/context/example/no-domain.

A causa não era a ontologia H3. Era precedência no B2.12.2: uma observação selecionada
mais recente podia mascarar `legacy_explanation_role/status/action` já persistidos na
linha de `project_requirement_truth_status`.

### O que muda

1. **H3 no-domain vira veto semântico explícito**
   - `legacy_explanation_role/status/action` é avaliado antes da observação selecionada.
   - Uma identidade machine-verified com explicação H3 no-domain é removida da fila.
   - Somente `truth_state = human_confirmed` pode superar esse veto.

2. **Hard qualifiers deixam de depender de singular/morfologia estreita**
   - vegan / vegetarian em singular e plural;
   - bilingual em singular e plural;
   - direct payment na formulação real do briefing;
   - co-investment / sponsorship / shared investment;
   - recap video / vídeo memória;
   - horizontal / vertical;
   - budget/cost/quotation;
   - professional quality / ease.

   A augmentação é conservadora: pode rebaixar um candidato quando descobre um
   qualificador obrigatório ausente, mas nunca faz upgrade sozinha.

3. **Palco + LED passa a ser obrigação relacional**
   - menção isolada a `screen` ou `stage` não é resposta parcial suficiente;
   - `set the stage` continua ignorado como expressão idiomática.

4. **Experiência que demonstra capacidade do produto**
   - contexto de mercado/challenge não responde a uma obrigação que exige demonstrar
     capacidade/benefício por meio da experiência.

5. **Regra específica vence regra genérica**
   - direct payment, co-investment e recap-video preservam seus rule IDs específicos;
   - o guard financeiro genérico não mascara o motivo real da rejeição.

6. **Colisão de identidade canônica vira diagnóstico explícito**
   - duas Current Requirement identities com a mesma `canonical_obligation_text` são
     reportadas em `canonical_identity_collision_rows`;
   - nenhum auto-merge é realizado;
   - qualquer Truth-effect futuro permanece bloqueado até resolução governada.

### Governança

B2.12.2.1 continua:
- read-only;
- machine recommendation only;
- sem Human Review automático;
- sem Truth effect;
- sem persistência;
- sem mudança de `read_mode`;
- sem `domain_primary`;
- sem cutover;
- sem reprocessamento dos masters;
- sem auto-merge de identidades.

### SQL

**NÃO.** Nenhum SQL deve ser executado.

### Golden depois da instalação

1. Reboot da NAVE.
2. Abrir `Automated Adjudication Recommendations`.
3. Confirmar marcador `V28.7.3B2.12.2.1`.
4. Rodar Chambinho.
5. Exportar JSON completo e validar regressão.
6. Só então rodar JOVI.

No JOVI, os gates principais são:
- `semantic_unknown_count = 0`;
- os pseudo-requirements H3 acima devem aparecer em `semantic_excluded_rows`, não na fila;
- `Storytelling detalhado` não pode receber recommendation;
- `Performance com muito movimento` não pode receber recommendation;
- Travel activation não pode ser atendida por travel press kit;
- orçamento de alimentação sem valor/custo continua reject;
- palco + LED sem relação física local continua reject;
- formato horizontal continua qualificador obrigatório;
- câmera/market challenge não basta para obrigação de experiência demonstrar capacidade;
- colisões canônicas são apenas diagnosticadas, nunca auto-merged.

`queue_count` não é contrato fixo. A correção pode legitimamente reduzir o denominador.
