# NAVE by VOE — Fase 4: White label técnico

## Endereço recomendado

Primeira opção:

`nave-voe.streamlit.app`

Alternativas, caso a primeira não esteja disponível:

- `navebyvoe.streamlit.app`
- `nave-inteligencia.streamlit.app`
- `plataforma-nave.streamlit.app`

## Troca do subdomínio no Streamlit Community Cloud

1. Acesse o workspace do Streamlit Community Cloud.
2. Localize o aplicativo da NAVE.
3. Abra o menu de três pontos.
4. Entre em **Settings**.
5. Na aba **General**, altere o campo **App URL**.
6. Digite `nave-voe`.
7. Clique em **Save**.

A mudança do subdomínio é feita no painel do Streamlit e não pelo código.

## Novo Secret obrigatório para a Administração

Adicione aos Secrets do aplicativo:

```toml
NAVE_ADMIN_PASSWORD = "defina-uma-senha-forte"
```

Opcionalmente, mantenha também:

```toml
GEMINI_MODEL = "gemini-3.5-flash-lite"
```

## O que a V13 esconde

- stack traces e detalhes de exceções;
- links externos de ajuda nos erros;
- menu automático das páginas;
- toolbar de desenvolvimento;
- nomes de provedores nas telas de trabalho;
- chaves, URLs e variáveis técnicas;
- identificadores internos de importação;
- termos JSON, Supabase, Gemini e Secrets fora da Administração.

## Padrão de títulos

- Organizar conhecimento
- Base de conhecimento
- Analisar e recomendar
- Projetos
- Fornecedores
- Administração
