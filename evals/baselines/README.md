# Baselines do NAVE IQ Bench

Quando uma versão da NAVE tiver um run completo e aceito, copie o JSON do run para esta pasta com nome versionado, por exemplo:

`nave_iq_v28_2_1_file_analyst_v1.json`

O runner compara blind cases com um baseline via `--baseline` e bloqueia regressões materiais acima da tolerância configurada.

Nunca use um baseline fabricado para fazer gates passarem. Um baseline precisa vir de uma execução real do pipeline candidato.
