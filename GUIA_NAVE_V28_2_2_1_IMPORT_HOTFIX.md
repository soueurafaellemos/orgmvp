# NAVE by VOE · V28.2.2.1 — Import Hotfix

## O que corrige

1. **Falha `str object has no attribute table` na importação de projeto existente**
   - A página reutilizava o nome `client` dentro do loop que montava os rótulos dos projetos existentes.
   - Isso substituía, no escopo da página, o cliente Supabase por uma string como `Chambinho` ou `Lactalis`.
   - Ao clicar em **Importar projeto completo**, essa string era enviada ao pipeline como se fosse a conexão de banco.

2. **Estado antigo de “Novo projeto / Projeto existente”**
   - O destino agora possui uma chave explícita de sessão e é resetado quando muda o conjunto de uploads.
   - Um lote novo não herda silenciosamente a seleção de destino feita em um teste anterior.

3. **Proteção defensiva no backend**
   - `save_project_bundle()` valida a conexão antes de iniciar qualquer efeito colateral.
   - Se algo semelhante voltar a acontecer, a mensagem será clara e o lote nem começa.

## Arquivos para substituir/adicionar

- `pages/14_Importar_Projeto.py` — substituir
- `project_batch_ingestion.py` — substituir
- `tests/test_v28_2_2_1_import_hotfix.py` — adicionar

## SQL

**NÃO.**

## Reboot

**SIM.** Após o upload dos arquivos, execute **Manage app → Reboot app**.

## Reteste Golden Chambinho

Use os mesmos 4 arquivos, em um lote limpo.

Antes de importar, confira a identidade:

- Nome do projeto: `Festivalzinho Chambinho 2026`
- Cliente / marca: `Chambinho`
- Evento: `Festivalzinho 2026`
- Destino: **Um novo projeto**

O briefing original identifica o cliente como Lactalis / Chambinho. Para a camada atual de `client_brand`, usamos a marca **Chambinho**; a relação com Lactalis deve ser preservada depois no Intelligence Graph como organização/parent brand, sem fundir os dois conceitos num texto único.

Não associe este Golden ao projeto existente `Festivalzinho Chambinho — Chambinho · Festivalzinho` sem confirmar que ele é exatamente a edição 2026. A tela já mostrou conflito e apenas 63% de aderência, portanto ele não deve ser tratado como correspondência forte.
