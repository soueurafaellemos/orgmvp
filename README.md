# Agente Organizador de Insumos para Brindes — Gemini

Protótipo em Streamlit para transformar materiais desorganizados em uma base
estruturada para o futuro recomendador de brindes.

## Atualização da versão anterior

Esta versão troca a OpenAI API pela Gemini API.

Substitua no GitHub os arquivos do projeto pelos arquivos deste pacote.
O arquivo antigo `ai_extractor.py` foi removido e substituído por:

```text
gemini_extractor.py
```

O `requirements.txt` também precisa ser substituído.

## Configuração no Streamlit

Crie uma chave no Google AI Studio e salve nos Secrets do app:

```toml
GEMINI_API_KEY = "SUA-CHAVE"
```

Nunca coloque a chave diretamente no GitHub.

## Primeiro teste recomendado

1. Escolha **Catálogo de brindes**.
2. Envie o catálogo PDF.
3. Modelo: `gemini-3.5-flash`.
4. Página inicial: `6`.
5. Página final: `7`.
6. Páginas por lote: `2`.
7. Clique em **Organizar informações**.

## Formatos previstos nesta versão

PDF, TXT, Markdown, JSON, HTML, XML, Word, PowerPoint, planilhas, CSV e e-mail
`.eml`. A leitura mais confiável nesta fase é de PDF e texto. Outros formatos
devem ser testados antes de entrar no fluxo oficial.

## Privacidade

Na faixa gratuita da Gemini API, conteúdos enviados podem ser usados pelo
Google para melhorar produtos. Use materiais não confidenciais durante a prova
de conceito.

## Limitações

- revisão humana continua obrigatória;
- ainda não recorta imagens de produtos;
- ainda não possui banco de dados, login ou permissões;
- PDFs extensos geram várias chamadas;
- a faixa gratuita possui limites de uso;
- documentos binários antigos podem exigir conversão para formatos modernos.
