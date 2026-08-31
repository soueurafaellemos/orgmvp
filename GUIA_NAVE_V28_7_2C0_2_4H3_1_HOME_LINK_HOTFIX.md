# NAVE V28.7.2C0.2.4H3.1 — Home Link Hotfix

## Motivo
A página `pages/33_Requirement_Semantic_Truth_Repair.py` foi adicionada corretamente no patch H3.1,
mas `streamlit_app.py` não foi incluído no pacote. Como a Home lista os diagnósticos manualmente,
o Requirement Semantic Truth Repair não aparecia em "Diagnósticos temporários".

## Alteração
Substituir apenas:
- `streamlit_app.py`

A hotfix adiciona o link:
- `Requirement Semantic Truth Repair` → `pages/33_Requirement_Semantic_Truth_Repair.py`

Nenhuma lógica H3.1 foi alterada.
Nenhum SQL é necessário.
Nenhuma alteração em Supabase.
Nenhum reprocessamento de master.

## Depois de subir
1. Commit/push de `streamlit_app.py`.
2. Manage app → Reboot app.
3. Abrir a Home.
4. Confirmar que `Requirement Semantic Truth Repair` aparece abaixo de `Automated Adjudication Recommendations`.
5. Só então executar o Golden Chambinho conforme o guia H3.1 principal.
