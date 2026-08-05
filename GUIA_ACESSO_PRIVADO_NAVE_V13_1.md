# NAVE by VOE — acesso privado V13.1

## Proteção recomendada em duas camadas

### Camada 1 — privacidade do Streamlit Cloud

No Streamlit Community Cloud:

1. Abra o workspace.
2. Clique nos três pontos do aplicativo.
3. Abra **Settings**.
4. Entre em **Sharing**.
5. Em **Who can view this app**, selecione:
   **Only specific people can view this app**.
6. Convide os usuários autorizados pelo e-mail.

Essa é a proteção principal da hospedagem.

### Camada 2 — senhas internas da NAVE

Adicione aos Secrets:

```toml
NAVE_APP_PASSWORD = "senha-para-entrar-na-nave"
NAVE_ADMIN_PASSWORD = "senha-diferente-para-administracao"
```

- `NAVE_APP_PASSWORD` bloqueia todas as páginas.
- `NAVE_ADMIN_PASSWORD` é uma segunda senha, solicitada apenas
  ao abrir a Administração.
- As duas senhas devem ser diferentes.

Depois de salvar os Secrets, faça **Reboot app**.

## Teste correto

1. Abra a NAVE em uma janela anônima.
2. A primeira tela deve pedir **Senha de acesso**.
3. Entre com `NAVE_APP_PASSWORD`.
4. Abra **Acesso administrativo**.
5. A página deve pedir **Senha de administração**.
6. Entre com `NAVE_ADMIN_PASSWORD`.
7. Use **Sair da NAVE** para encerrar a sessão.
