# Agente Organizador de Insumos para Brindes

Protótipo embrionário para:

1. receber PDF, Word, Excel, PowerPoint, CSV, texto e e-mail `.eml`;
2. transformar catálogos em uma tabela padronizada de produtos;
3. consolidar e-mails e documentos em um briefing estruturado;
4. permitir revisão humana;
5. exportar Excel, CSV e JSON para alimentar o MVP recomendador.

## Por que este protótipo é separado do recomendador?

O recomendador precisa receber dados minimamente confiáveis. Este app funciona
como uma camada de ingestão e limpeza:

`documentos desorganizados -> dados estruturados -> revisão -> MVP`

## Instalação local

Requisitos:

- Python 3.11 ou superior
- uma OpenAI API key com faturamento habilitado

```bash
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows

pip install -r requirements.txt
export OPENAI_API_KEY="sua-chave"
streamlit run streamlit_app.py
```

## Deploy rápido no Streamlit Community Cloud

1. Crie um repositório no GitHub.
2. Envie todos os arquivos deste projeto.
3. No Streamlit Community Cloud, crie um app apontando para
   `streamlit_app.py`.
4. Em **Secrets**, cadastre:

```toml
OPENAI_API_KEY = "sua-chave"
```

## Primeiro teste com um catálogo grande

Para reduzir custo e tempo:

1. selecione o modo **Catálogo de brindes**;
2. envie o PDF;
3. processe primeiro um intervalo curto, como páginas 6 a 13;
4. use quatro páginas por lote;
5. revise a tabela;
6. só depois processe o documento completo.

## Campos de produto

- arquivo e página de origem
- categoria
- SKU
- nome
- descrição
- capacidade
- dimensões
- material
- acabamento
- decoração
- origem
- produto regular ou conceito
- pedido mínimo
- possibilidade de personalização
- observações de licenciamento
- tags
- confiança da extração
- campos ausentes
- evidência textual

## Limitações desta versão

- `.msg` do Outlook ainda não é processado; use `.eml` ou cole o corpo.
- a leitura de catálogos extensos gera várias chamadas à API;
- preços e prazos não são inferidos quando não aparecem;
- imagens dos produtos ainda não são recortadas e armazenadas individualmente;
- a revisão humana continua obrigatória;
- o app não possui login, banco de dados ou permissões.

## Próximas evoluções recomendadas

- armazenar produtos aprovados em PostgreSQL/Supabase;
- recortar automaticamente a imagem de cada produto;
- criar histórico de versões e fornecedores;
- importar diretamente o arquivo revisado no recomendador;
- integrar Gmail/Outlook;
- criar validações de duplicidade, unidade, moeda e prazo;
- usar uma fila assíncrona para catálogos muito grandes.
