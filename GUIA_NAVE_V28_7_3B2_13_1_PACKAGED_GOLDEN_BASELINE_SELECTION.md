# NAVE V28.7.3B2.13.1 — Packaged Golden Baseline Selection

## Why this hotfix exists

The first B2.13 UI was upload-driven. That was technically workable but operationally wrong
for a governed Golden checkpoint: the operator had no explicit project selection and could
accidentally upload the wrong historical artifact.

## Fix

The page now has a `Projeto` selector with exactly:
- Festivalzinho Chambinho
- Lançamento Jovi X300

The corresponding approved B2.12.2.2 Golden baseline is bundled in:
- `goldens/b2_12_2_2/0d9f1608-4bf7-4fd0-81ab-f303fdb0c136.json`
- `goldens/b2_12_2_2/01415104-72f2-4b8e-aeca-2dd24c231a7d.json`

Each baseline has a pinned SHA-256 in code. The page refuses to run if:
- the file is missing;
- its hash changed;
- its baseline version changed;
- its project_id does not match the selected project.

No upload is required in the Golden path.

## SQL
NO.

## Reboot
YES.

## Run order
1. Deploy + reboot.
2. Open `Response Truth Impact Shadow`.
3. Select `Festivalzinho Chambinho`.
4. Run `Executar B2.13.1 — READ ONLY`.
5. Download/send JSON.
6. Only after approval, select `Lançamento Jovi X300`.

No write or Truth effect is authorized by this phase.
