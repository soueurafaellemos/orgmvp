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

MEMORY_SECTION_ORDER = list(
    MEMORY_SECTION_LABELS.keys()
)

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
- Não extraia fornecedores, preços ou prazos inexistentes.
- Não sugira promover nada para uma base geral.
- Não crie vínculos com brindes, ativações, locais ou recomendações.
- Não complete lacunas com conhecimento externo.
- Preserve o sentido e o vocabulário da apresentação.

OBJETIVO:
Criar um arquivo vivo, visual e consultável do raciocínio estratégico,
dos ambientes, das propostas criativas, dos materiais e da jornada
daquele projeto.

SEÇÕES:
1. strategy — Estratégia
Contexto, desafio, objetivos, público, insight, conceito, premissas,
manifesto, narrativa, pilares, direcionais e inspiração estratégica.

2. scenography — Cenografia & Ambientes
Implantação, arquitetura, fachada, estande, camarote, palco, plenária,
lounge, loja, túnel, credenciamento, áreas externas, plantas, vistas,
renders, revestimentos e ambientações.

3. activations — Ativações & Experiências
Games, photo-ops, experiências imersivas, sampling, personalização,
dinâmicas, desafios, instalações interativas e momentos programados.

4. gifts — Brindes & Materiais
Brindes, kits, residuais, embalagens, uniformes, credenciais,
pulseiras, sacolas, chapéus, canecas, bottons e materiais entregáveis.

5. journey_operation — Jornada & Operação
Pré-evento, chegada, credenciamento, fluxo, circuito, filas,
atendimento, regras de participação, distribuição, saída e pós-evento.

6. communication — Comunicação & Desdobramentos
KV, identidade visual, campanha, sinalização, telas, fachadas,
envelopamentos, aplicações, peças e conteúdos de comunicação.

7. content_agenda — Conteúdo & Agenda
Programação, talks, palestras, workshops, shows, horários, trilhas,
cardápios e conteúdos de jantares temáticos quando fizerem parte da
programação do evento.

8. partners_sponsorship — Parceiros & Cotas
Cotas, patrocinadores, naming rights, espaços assinados e
oportunidades de integração de marcas.

9. pr_esg_legacy — PR, ESG & Legado
Potencial de imprensa, impacto social, ESG, sustentabilidade,
comunidade, intervenção artística e legado posterior ao evento.

CONTRATO OBRIGATÓRIO DE COBERTURA:

- O prompt contém um INVENTÁRIO OBRIGATÓRIO com todos os slides desta
  passagem.
- Retorne exatamente um objeto MemorySlide para CADA número de página
  listado no inventário, na mesma ordem.
- Nunca omita silenciosamente uma página.
- Para capa, divisória, agradecimento ou página sem conteúdo útil,
  use is_meaningful=false, explique exclusion_reason e deixe items=[].
- Para todo slide relevante, use is_meaningful=true e gere pelo menos
  um item.
- Quando um slide contiver propostas distintas, gere vários itens.
  Exemplos: quatro brindes diferentes; duas opções de uniforme;
  dois jogos; diferentes ambientes.
- Nunca concatene agenda, cardápio, planta, cenografia e ativações em
  uma única ficha. Separe entidades semanticamente independentes.
- A palavra "kit" isoladamente não torna um conteúdo um brinde: só use
  gifts quando houver objeto/material efetivamente entregue ao público.
- Pratos, menus, sobremesas e nomes de receitas pertencem a
  content_agenda quando descrevem uma refeição/jantar; nunca a strategy
  ou gifts por coincidência de palavras.
- Horários, check-in, almoço, jantar, plenária, coffee break e checkout
  pertencem a content_agenda ou journey_operation, não a strategy.
- Palco, LED, photo-op, ilha de massagem, foyer e estruturas físicas
  devem ser separados por entidade/ambiente; não copie o texto inteiro
  da planta para uma única ativação.
- Slides puramente visuais também são relevantes quando representam
  KV, cenografia, ativação, brinde ou material proposto.
- Não use títulos genéricos como "Foto 1", "Imagem", "Visual" ou
  "Conteúdo". Dê nome ao que está sendo mostrado.
- Se a imagem for continuação de um item apresentado no slide anterior,
  mantenha o nome da proposta e indique que é outra vista ou aplicação.
- extraction_origin deve ser "ai".

STATUS:
- Referência: inspiração, benchmark ou moodboard.
- Proposto: solução apresentada como parte do projeto.
- Opção: alternativa ainda não definida.
- Recomendado, Aprovado, Descartado ou Executado somente quando explícito.
- Na dúvida, use Não identificado.

IMAGEM:
- Quando existir uma imagem claramente associada ao item, preencha
  visual_crop com coordenadas entre 0 e 1.
- Recorte preferencialmente render, mockup, objeto ou composição visual,
  excluindo cabeçalhos e rodapés.
- Quando não houver um recorte seguro, use visual_crop=null. O sistema
  mostrará o slide completo; isso NÃO é motivo para omitir o item.

QUALIDADE:
- Mantenha source_file e source_page originais.
- evidence deve ser trecho curto realmente presente no slide.
- summary deve permitir consulta rápida.
- description deve explicar a proposta sem inventar.
- objectives, audiences, mechanics e technologies devem ser preenchidos
  quando estiverem explícitos.
"""


MEMORY_OVERVIEW_PROMPT = """
Consolide o conteúdo estruturado de todos os slides como um único
projeto da Memória.

Retorne:

- source_file;
- document_title;
- project_name;
- client_brand;
- event_name;
- version_label;
- strategic_summary;
- creative_concept;
- warnings.

A síntese deve considerar contexto, objetivos, insight, conceito,
identidade, ambientes, ativações, brindes, jornada, comunicação,
parceiros e legado quando existirem.

Não invente informações e não liste fichas individuais.
"""
