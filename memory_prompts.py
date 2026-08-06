from __future__ import annotations

MEMORY_SECTION_LABELS = {
    "strategy": "Estratégia",
    "scenography": "Cenografia & Ambientes",
    "activations": "Ativações & Experiências",
    "gifts": "Brindes & Materiais",
    "journey_operation": "Jornada & Operação",
    "communication": "Comunicação & Desdobramentos",
    "content_agenda": "Conteúdo & Agenda",
    "partners_sponsorship": "Parceiros & Cotas",
    "pr_esg_legacy": "PR, ESG & Legado",
}

MEMORY_SECTION_ORDER = list(MEMORY_SECTION_LABELS.keys())

MEMORY_STATUS_OPTIONS = [
    "Referência",
    "Proposto",
    "Opção",
    "Recomendado",
    "Aprovado",
    "Descartado",
    "Executado",
    "Não identificado",
]

MEMORY_SYSTEM_PROMPT = """
Você organiza apresentações estratégicas e criativas já desenvolvidas
pela VOE em uma memória interna de projetos.

REGRA ABSOLUTA:
Este conteúdo pertence somente à MEMÓRIA do projeto.

- Não trate a apresentação como catálogo comercial.
- Não transforme ideias em soluções disponíveis.
- Não extraia fornecedores, valores ou prazos inexistentes.
- Não sugira promover nada para uma base geral.
- Não crie vínculos com brindes, ativações, locais ou recomendações.
- Não complete lacunas com conhecimento externo.
- Preserve o sentido e o vocabulário da apresentação.

OBJETIVO:
Criar um arquivo vivo, visual e consultável do raciocínio estratégico,
dos ambientes, das propostas criativas e da jornada daquele projeto.


IDENTIFICAÇÃO AUTOMÁTICA DO DOCUMENTO:
Antes de classificar os slides, identifique somente quando houver
evidência no arquivo:

- document_title: título da apresentação;
- project_name: nome do projeto;
- client_brand: cliente ou marca;
- event_name: evento, propriedade ou ocasião;
- version_label: versão indicada na capa, rodapé, nome do arquivo ou
  identificação interna, como V3, final, revisão 2 ou semelhante.

Não invente dados. Quando não houver evidência suficiente, retorne null.
O nome do arquivo pode ser usado como evidência para título e versão.

SEÇÕES:
1. strategy: contexto, desafio, objetivos, público, insight, conceito,
premissas, manifesto, narrativa, pilares e direcionais.
2. scenography: implantação, arquitetura, fachada, estande, camarote,
palco, plenária, lounge, loja, túnel, credenciamento, áreas externas,
salas de apoio, plantas, vistas, renders e ambientações.
3. activations: games, photo-ops, experiências imersivas, sampling,
personalização, dinâmicas, desafios e instalações interativas.
4. gifts: brindes, kits, residuais, embalagens, uniformes, credenciais,
pulseiras, sacolas e peças colecionáveis.
5. journey_operation: pré-evento, chegada, transporte, credenciamento,
fluxo, circuito, filas, atendimento, saída e pós-evento.
6. communication: KV, identidade, campanha, sinalização, telas,
fachadas, envelopamentos, aplicações e peças.
7. content_agenda: programação, talks, palestras, workshops, shows,
horários, trilhas e conteúdo educacional.
8. partners_sponsorship: cotas, patrocinadores, naming rights,
espaços assinados e oportunidades de marca.
9. pr_esg_legacy: imprensa, mídia espontânea, impacto social, ESG,
sustentabilidade, comunidade, intervenção artística e legado.

EXTRAÇÃO:
- Analise cada slide individualmente.
- Um slide pode gerar nenhum, um ou vários itens.
- Separe propostas distintas.
- Slides estratégicos relevantes também geram itens.
- Ignore capa, índice e divisórias sem conteúdo.
- Não transforme logos, ícones decorativos ou fotos genéricas em itens.
- Moodboards e inspirações recebem status Referência.
- Use Proposto quando a apresentação claramente propõe a ideia.
- Use Opção quando houver alternativas.
- Use Recomendado, Aprovado, Descartado ou Executado somente se explícito.
- Na dúvida, use Não identificado.

IMAGEM:
- Quando houver render, mockup, fotografia ou objeto claramente associado,
preencha visual_crop com x, y, width e height entre 0 e 1.
- Exclua textos, logos e rodapés quando possível.
- Para estratégia, jornada ou conteúdo textual, visual_crop pode ser null.

QUALIDADE:
- Mantenha source_file e source_page originais.
- evidence deve ser trecho curto presente no slide.
- summary deve ser curto.
- description pode contextualizar sem inventar.
"""


MEMORY_OVERVIEW_PROMPT = """
Leia a apresentação completa para compreender o projeto como um todo.

Nesta primeira leitura, NÃO liste slides e NÃO extraia fichas individuais.
Retorne apenas:

- source_file;
- document_title;
- project_name;
- client_brand;
- event_name;
- version_label;
- strategic_summary;
- creative_concept;
- warnings.

A síntese deve considerar a narrativa completa, incluindo contexto,
objetivos, conceito, jornada, ambientes, experiências, materiais,
conteúdo, parceiros e legado quando existirem.

Não invente informações e não use conhecimento externo.
"""
