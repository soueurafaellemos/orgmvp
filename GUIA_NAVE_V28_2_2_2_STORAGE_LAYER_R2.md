# NAVE by VOE · V28.2.2.2 — Storage Layer R2

## Objetivo

Transformar o Cloudflare R2 no **storage canônico de todos os novos arquivos da NAVE**, mantendo o Supabase como banco relacional / Intelligence Graph.

A partir desta versão:

- todo novo master de projeto vai para o R2;
- novos arquivos de workspace vão para o R2;
- novos documentos e derivados da Memória (original, páginas e crops) vão para o R2;
- novas planilhas de custos vão para o R2;
- novos media assets / imagens geradas vão para o R2;
- novos visuais recuperados pelo workspace vão para o R2;
- arquivos antigos que ainda estejam no Supabase Storage continuam legíveis e excluíveis durante a transição.

Nenhum dado antigo é migrado ou apagado automaticamente nesta versão.

---

## Arquitetura

```text
NAVE
  ├── Supabase
  │     └── banco, projetos, metadados, Intelligence Graph, claims, relações etc.
  │
  └── Cloudflare R2 · nave-project-files
        ├── projects/...
        ├── media/...
        └── demais prefixes privados gerados pela NAVE
```

O restante da aplicação não acessa boto3/R2 diretamente. A nova abstração `nave_storage.py` centraliza:

- upload;
- download;
- URL privada temporária;
- exclusão;
- verificação de existência;
- healthcheck;
- multipart para arquivos grandes;
- integridade SHA-256;
- fallback de leitura/exclusão para objetos legados no Supabase Storage.

---

## Secrets necessários

Já devem existir no Streamlit:

```toml
R2_ACCOUNT_ID = "..."
R2_ACCESS_KEY_ID = "..."
R2_SECRET_ACCESS_KEY = "..."
R2_BUCKET = "nave-project-files"
```

Não colocar nenhuma dessas credenciais no GitHub.

Opcionais — **não precisam ser configurados agora**:

```toml
R2_MULTIPART_THRESHOLD_MB = "100"
R2_MULTIPART_CHUNK_MB = "16"
```

O padrão é usar multipart a partir de 100 MB. Assim, o relatório Chambinho de ~128,7 MB já segue o caminho multipart.

---

## Integridade e rollback

Todo objeto novo recebe o SHA-256 como metadata privada do R2.

Após o upload a NAVE faz `HEAD` no objeto e valida:

- tamanho armazenado;
- SHA-256 registrado.

Se a integridade não conferir, o objeto é removido e a importação falha.

Se o upload terminar mas o registro no banco falhar, a NAVE remove do R2 os objetos criados naquela transação antes de reverter o lote.

---

## Compatibilidade com legado

Os registros novos usam no campo `storage_bucket` um marcador como:

```text
r2:nave-project-files
```

Registros antigos continuam com buckets como:

```text
nave-project-files
nave-memory
nave-project-costs
nave-media
```

`nave_storage.py` reconhece os dois formatos:

- `r2:*` → Cloudflare R2;
- bucket sem prefixo → Supabase Storage legado.

Isso permite migrar os arquivos históricos depois, com hash e sem big bang.

---

## Arquivos a substituir/adicionar no GitHub

### Adicionar

- `nave_storage.py`
- `tests/test_nave_storage_r2_v28222.py`
- `GUIA_NAVE_V28_2_2_2_STORAGE_LAYER_R2.md`

### Substituir

- `requirements.txt`
- `project_batch_ingestion.py`
- `project_bundle_materializer.py`
- `project_workspace_db.py`
- `project_workspace_ui.py`
- `project_workspace_visuals.py`
- `project_workspace_reports.py`
- `memory_db.py`
- `memory_learning_db.py`
- `memory_ui.py`
- `media_library.py`
- `nave_delete.py`
- `nave_table_utils.py`
- `knowledge_specialized.py`
- `selection_pdf.py`
- `supabase_db.py`
- `pages/10_Memoria.py`
- `pages/14_Importar_Projeto.py`
- `tests/test_v28_1_7_1_upload_resiliente.py`

---

## Dependência nova

`requirements.txt` passa a incluir:

```text
boto3>=1.40,<2
```

---

## SQL

**NÃO executar SQL.**

Esta versão utiliza os campos de storage que já existem no banco. O provider fica explícito no valor de `storage_bucket`.

---

## Reboot

**SIM.**

Depois de subir os arquivos:

1. Streamlit → Manage app;
2. Reboot app;
3. aguardar a instalação da nova dependência `boto3`;
4. abrir `Importar projeto completo`.

---

## Teste de aceitação imediato — Golden Chambinho

Enviar juntos, como **novo projeto**, os quatro arquivos Golden:

1. briefing DOCX;
2. proposta PDF;
3. orçamento XLSM;
4. relatório pós-evento PPTX (~128,7 MB).

Antes de importar, manter:

- Projeto: `Festivalzinho Chambinho`
- Cliente / marca: `Chambinho`
- Evento: `Festivalzinho 2026`
- Destino: **Um novo projeto**

Resultado mínimo esperado para esta versão de infraestrutura:

- os quatro arquivos passam do upload;
- nenhum erro de limite de 50 MB do Supabase aparece;
- o PPTX de ~128,7 MB usa multipart no R2;
- o lote é criado no Supabase DB;
- `source_files.storage_bucket` dos novos masters começa com `r2:`;
- os quatro objetos aparecem dentro do bucket privado `nave-project-files`;
- a materialização e o Intelligence Graph continuam executando normalmente.

Não corrigir manualmente a materialização antes de avaliarmos o resultado do Golden Project.

---

## O que esta versão ainda NÃO faz

- não migra automaticamente objetos antigos do Supabase Storage;
- não remove buckets antigos;
- não muda o limite de 300 MB do uploader do Streamlit;
- não implementa upload direto browser → R2 por presigned URL;
- não muda Entity Resolution / Project Analyst.

Depois que Chambinho estiver estável no R2, a migração de legado pode ser feita em uma etapa própria:

**copiar → verificar SHA-256 → atualizar referência → confirmar → apagar objeto legado**.

---

## Validação local

Regressão focada executada sobre Storage Layer + linha Intelligence:

**56 testes passando.**

Inclui:

- upload R2 simples;
- multipart;
- SHA-256;
- download;
- presigned URL;
- delete;
- healthcheck;
- compatibilidade com Supabase Storage legado;
- import hotfix;
- Entity Resolution;
- Cross-Source Linker;
- Golden JOVI;
- Golden Chambinho;
- File Analyst;
- materialização resiliente.

A suíte total do repositório continua não coletando neste container por ausência local de dependências de runtime (`streamlit` e `google-genai`) em módulos antigos; isso é uma limitação do ambiente de teste local e não foi contado como aprovação integral.
