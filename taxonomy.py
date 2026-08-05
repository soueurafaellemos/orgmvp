from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Iterable


DOMAIN_LABELS = {
    "product": "Brindes",
    "activation": "Soluções / ativações",
    "venue": "Locais / espaços",
}


TAXONOMY = {
    "activation": {
        "Photo-op": {
            "aliases": [
                "photo-op",
                "photo op",
                "photoop",
                "photoopp",
                "photo opp",
                "photopp",
                "phopp",
                "fotop",
                "fotopp",
                "foto op",
                "foto-op",
                "photo opportunity",
                "photo opportunity area",
                "photo opportunity activation",
                "photo opportunity space",
                "photo experience",
                "photo experience area",
                "photo point",
                "photo spot",
                "foto point",
                "foto spot",
                "ponto de foto",
                "ponto para foto",
                "ponto fotografico",
                "ponto fotográfico",
                "espaco para foto",
                "espaço para foto",
                "espaco de foto",
                "espaço de foto",
                "cenario para foto",
                "cenário para foto",
                "cenario para fotos",
                "cenário para fotos",
                "cenario fotografico",
                "cenário fotográfico",
                "instalacao fotografica",
                "instalação fotográfica",
                "espaco instagramavel",
                "espaço instagramável",
                "cenario instagramavel",
                "cenário instagramável",
                "parede instagramavel",
                "parede instagramável",
                "painel instagramavel",
                "painel instagramável",
                "ambiente instagramavel",
                "ambiente instagramável",
                "momento instagramavel",
                "momento instagramável",
                "photo backdrop",
                "backdrop para foto",
                "painel para foto",
                "parede para foto",
                "selfie point",
                "selfie spot",
                "selfie area",
                "selfie wall",
                "selfie station",
                "ponto de selfie",
                "espaco de selfie",
                "espaço de selfie",
            ],
            "semantic_tags": [
                "Fotografia",
                "Instagramável",
                "Conteúdo social",
            ],
        },
        "Cabine fotográfica": {
            "aliases": [
                "cabine fotografica",
                "cabine fotográfica",
                "cabine de fotos",
                "cabine de foto",
                "photo booth",
                "photobooth",
                "foto cabine",
                "fotocabine",
                "cabine selfie",
                "selfie booth",
                "cabine instantanea",
                "cabine instantânea",
                "cabine polaroid",
            ],
            "semantic_tags": [
                "Fotografia",
                "Impressão instantânea",
            ],
        },
        "Vídeo 360": {
            "aliases": [
                "video 360",
                "vídeo 360",
                "360 video",
                "360 booth",
                "360 photo booth",
                "plataforma 360",
                "camera 360",
                "câmera 360",
                "selfie 360",
                "slow motion 360",
                "spinner 360",
            ],
            "semantic_tags": [
                "Vídeo",
                "Conteúdo social",
            ],
        },
        "GIF / Boomerang": {
            "aliases": [
                "gif booth",
                "gifbooth",
                "gif station",
                "cabine gif",
                "boomerang",
                "boomerang booth",
                "boomerang station",
                "foto animada",
                "loop animado",
            ],
            "semantic_tags": [
                "Fotografia",
                "Vídeo",
                "Conteúdo social",
            ],
        },
        "Espelho interativo": {
            "aliases": [
                "espelho interativo",
                "espelho magico",
                "espelho mágico",
                "magic mirror",
                "mirror booth",
                "selfie mirror",
                "espelho selfie",
                "espelho digital",
            ],
            "semantic_tags": [
                "Interativo",
                "Fotografia",
            ],
        },
        "Realidade virtual": {
            "aliases": [
                "realidade virtual",
                "virtual reality",
                "vr",
                "oculos vr",
                "óculos vr",
                "headset vr",
                "experiencia vr",
                "experiência vr",
                "imersao vr",
                "imersão vr",
                "metaverso",
            ],
            "semantic_tags": [
                "Imersivo",
                "Tecnologia",
            ],
        },
        "Realidade aumentada": {
            "aliases": [
                "realidade aumentada",
                "augmented reality",
                "ar experience",
                "experiencia ar",
                "experiência ar",
                "filtro ar",
                "filtro de realidade aumentada",
                "web ar",
                "webar",
                "lente interativa",
            ],
            "semantic_tags": [
                "Interativo",
                "Tecnologia",
            ],
        },
        "Realidade mista": {
            "aliases": [
                "realidade mista",
                "mixed reality",
                "mr experience",
                "experiencia mr",
                "experiência mr",
                "xr",
                "extended reality",
                "realidade estendida",
            ],
            "semantic_tags": [
                "Imersivo",
                "Tecnologia",
            ],
        },
        "Experiência imersiva": {
            "aliases": [
                "experiencia imersiva",
                "experiência imersiva",
                "immersive experience",
                "imersao",
                "imersão",
                "ambiente imersivo",
                "sala imersiva",
                "túnel imersivo",
                "tunel imersivo",
                "instalacao imersiva",
                "instalação imersiva",
                "experiencia sensorial",
                "experiência sensorial",
                "ambiente sensorial",
                "tunel sensorial",
                "túnel sensorial",
            ],
            "semantic_tags": [
                "Imersivo",
                "Sensorial",
            ],
        },
        "Simulador": {
            "aliases": [
                "simulador",
                "simulator",
                "simulacao",
                "simulação",
                "simulador esportivo",
                "simulador de corrida",
                "simulador de voo",
                "simulador de direcao",
                "simulador de direção",
                "simulador automobilistico",
                "simulador automobilístico",
                "motion simulator",
                "simulador com movimento",
            ],
            "semantic_tags": [
                "Interativo",
                "Tecnologia",
            ],
        },
        "Game interativo": {
            "aliases": [
                "game",
                "jogo",
                "game interativo",
                "jogo interativo",
                "interactive game",
                "advergame",
                "brand game",
                "jogo de marca",
                "game digital",
                "jogo digital",
                "mini game",
                "minigame",
                "arcade",
                "fliperama",
                "jogo multiplayer",
                "multiplayer",
                "game touch",
            ],
            "semantic_tags": [
                "Gamificação",
                "Interativo",
            ],
        },
        "Quiz / Trivia": {
            "aliases": [
                "quiz",
                "trivia",
                "quizz",
                "perguntas e respostas",
                "jogo de perguntas",
                "quiz interativo",
                "quiz digital",
                "quiz de marca",
                "teste de conhecimento",
                "desafio de conhecimento",
            ],
            "semantic_tags": [
                "Gamificação",
                "Conteúdo",
            ],
        },
        "Roleta / Sorteio": {
            "aliases": [
                "roleta",
                "roleta digital",
                "roleta de premios",
                "roleta de prêmios",
                "wheel of fortune",
                "spin wheel",
                "gire a roleta",
                "sorteio",
                "sorteador",
                "sorteio digital",
                "premiacao instantanea",
                "premiação instantânea",
                "instant win",
            ],
            "semantic_tags": [
                "Gamificação",
                "Premiação",
            ],
        },
        "Máquina de garra": {
            "aliases": [
                "maquina de garra",
                "máquina de garra",
                "claw machine",
                "grua de pelucia",
                "grua de pelúcia",
                "pega pelucia",
                "pega pelúcia",
                "grab machine",
                "maquina pega brinde",
                "máquina pega brinde",
            ],
            "semantic_tags": [
                "Gamificação",
                "Premiação",
            ],
        },
        "Totem interativo": {
            "aliases": [
                "totem interativo",
                "totem touch",
                "totem touchscreen",
                "quiosque interativo",
                "kiosk interativo",
                "interactive kiosk",
                "mesa interativa",
                "display interativo",
                "tela interativa",
                "touch screen",
                "touchscreen",
            ],
            "semantic_tags": [
                "Interativo",
                "Tecnologia",
            ],
        },
        "Gamificação": {
            "aliases": [
                "gamificacao",
                "gamificação",
                "gamification",
                "mecanica de jogo",
                "mecânica de jogo",
                "sistema de pontos",
                "pontuacao",
                "pontuação",
                "ranking",
                "leaderboard",
                "placar digital",
                "missao",
                "missão",
                "desafio premiado",
            ],
            "semantic_tags": [
                "Engajamento",
                "Premiação",
            ],
        },
        "Desafio esportivo": {
            "aliases": [
                "desafio esportivo",
                "ativacao esportiva",
                "ativação esportiva",
                "experiencia esportiva",
                "experiência esportiva",
                "sports challenge",
                "desafio fisico",
                "desafio físico",
                "prova de habilidade",
                "desafio de habilidade",
                "basketball challenge",
                "desafio de basquete",
                "futebol interativo",
                "chute a gol",
                "skate challenge",
                "surf challenge",
                "ski challenge",
            ],
            "semantic_tags": [
                "Esporte",
                "Interativo",
            ],
        },
        "Personalização ao vivo": {
            "aliases": [
                "personalizacao ao vivo",
                "personalização ao vivo",
                "customizacao ao vivo",
                "customização ao vivo",
                "live customization",
                "live personalisation",
                "live personalization",
                "gravacao ao vivo",
                "gravação ao vivo",
                "bordado ao vivo",
                "silk ao vivo",
                "serigrafia ao vivo",
                "estamparia ao vivo",
                "lettering ao vivo",
                "caligrafia ao vivo",
                "pintura ao vivo",
                "patch bar",
                "charm bar",
                "pin bar",
            ],
            "semantic_tags": [
                "Personalização",
                "Brinde",
            ],
        },
        "Oficina / Workshop": {
            "aliases": [
                "oficina",
                "workshop",
                "masterclass",
                "aula pratica",
                "aula prática",
                "atividade mão na massa",
                "atividade mao na massa",
                "hands on",
                "hands-on",
                "laboratorio criativo",
                "laboratório criativo",
                "oficina criativa",
                "maker workshop",
            ],
            "semantic_tags": [
                "Conteúdo",
                "Participativo",
            ],
        },
        "Degustação": {
            "aliases": [
                "degustacao",
                "degustação",
                "tasting",
                "food tasting",
                "drink tasting",
                "prova de produto",
                "experiencia gastronomica",
                "experiência gastronômica",
                "harmonizacao",
                "harmonização",
                "sampling degustacao",
                "sampling degustação",
            ],
            "semantic_tags": [
                "Gastronomia",
                "Experimentação",
            ],
        },
        "Sampling / Distribuição": {
            "aliases": [
                "sampling",
                "sample",
                "amostragem",
                "distribuicao de amostras",
                "distribuição de amostras",
                "distribuicao de produto",
                "distribuição de produto",
                "entrega de amostra",
                "entrega de brindes",
                "distribuicao de brindes",
                "distribuição de brindes",
                "promocao com amostra",
                "promoção com amostra",
                "experimentacao de produto",
                "experimentação de produto",
            ],
            "semantic_tags": [
                "Experimentação",
                "Distribuição",
            ],
        },
        "Bar / Alimentação": {
            "aliases": [
                "bar",
                "bar cenografico",
                "bar cenográfico",
                "bar de drinks",
                "bar de bebidas",
                "open bar",
                "coffee bar",
                "cafe bar",
                "café bar",
                "food station",
                "estacao gastronomica",
                "estação gastronômica",
                "ilha gastronomica",
                "ilha gastronômica",
                "food truck",
                "carrinho de comida",
                "carrinho de bebidas",
            ],
            "semantic_tags": [
                "Gastronomia",
                "Hospitalidade",
            ],
        },
        "Cenografia": {
            "aliases": [
                "cenografia",
                "scenography",
                "cenografia de evento",
                "ambientacao",
                "ambientação",
                "decoracao cenografica",
                "decoração cenográfica",
                "cenario",
                "cenário",
                "instalacao cenografica",
                "instalação cenográfica",
                "estrutura cenografica",
                "estrutura cenográfica",
                "set design",
                "brand environment",
            ],
            "semantic_tags": [
                "Ambientação",
                "Produção",
            ],
        },
        "Palco": {
            "aliases": [
                "palco",
                "stage",
                "estrutura de palco",
                "stage design",
                "palco cenografico",
                "palco cenográfico",
                "palco baixo",
                "praticavel",
                "praticável",
                "tablado",
                "backstage",
            ],
            "semantic_tags": [
                "Cenografia",
                "Infraestrutura",
            ],
        },
        "Painel / Backdrop": {
            "aliases": [
                "painel",
                "backdrop",
                "painel cenografico",
                "painel cenográfico",
                "parede cenografica",
                "parede cenográfica",
                "fundo de palco",
                "stage backdrop",
                "painel de marca",
                "brand wall",
                "logo wall",
                "step and repeat",
                "step & repeat",
                "testeira",
            ],
            "semantic_tags": [
                "Cenografia",
                "Marca",
            ],
        },
        "Exposição / Vitrine": {
            "aliases": [
                "exposicao",
                "exposição",
                "exhibition",
                "display de produto",
                "vitrine",
                "showcase",
                "mostruario",
                "mostruário",
                "galeria",
                "museografia",
                "ilha de produto",
                "product display",
                "product showcase",
            ],
            "semantic_tags": [
                "Produto",
                "Conteúdo",
            ],
        },
        "Loja / Pop-up": {
            "aliases": [
                "loja",
                "shop",
                "store",
                "pop up store",
                "pop-up store",
                "popup store",
                "loja pop up",
                "loja pop-up",
                "brand store",
                "loja temporaria",
                "loja temporária",
                "merch store",
                "merchandising store",
            ],
            "semantic_tags": [
                "Varejo",
                "Produto",
            ],
        },
        "Credenciamento": {
            "aliases": [
                "credenciamento",
                "check in",
                "check-in",
                "checkin",
                "acreditacao",
                "acreditação",
                "registro de participantes",
                "recepcao",
                "recepção",
                "welcome desk",
                "registration desk",
                "badge printing",
                "impressao de credencial",
                "impressão de credencial",
            ],
            "semantic_tags": [
                "Operação",
                "Dados",
            ],
        },
        "Gestão de filas": {
            "aliases": [
                "gestao de filas",
                "gestão de filas",
                "fila virtual",
                "virtual queue",
                "queue management",
                "controle de fila",
                "unifila",
                "organizador de fila",
                "sistema de senhas",
                "agendamento de horario",
                "agendamento de horário",
                "controle de fluxo",
            ],
            "semantic_tags": [
                "Operação",
                "Fluxo",
            ],
        },
        "Captação de leads": {
            "aliases": [
                "captacao de leads",
                "captação de leads",
                "lead capture",
                "coleta de leads",
                "geracao de leads",
                "geração de leads",
                "cadastro de participantes",
                "coleta de dados",
                "data capture",
                "formulario digital",
                "formulário digital",
                "landing page",
                "crm activation",
            ],
            "semantic_tags": [
                "Dados",
                "CRM",
            ],
        },
        "RFID / NFC": {
            "aliases": [
                "rfid",
                "nfc",
                "pulseira rfid",
                "cartao rfid",
                "cartão rfid",
                "tag rfid",
                "pulseira nfc",
                "tag nfc",
                "tap experience",
                "interacao por aproximacao",
                "interação por aproximação",
                "cashless",
            ],
            "semantic_tags": [
                "Tecnologia",
                "Dados",
            ],
        },
        "Conteúdo audiovisual": {
            "aliases": [
                "conteudo audiovisual",
                "conteúdo audiovisual",
                "producao audiovisual",
                "produção audiovisual",
                "video",
                "vídeo",
                "filme",
                "motion graphics",
                "animacao",
                "animação",
                "conteudo digital",
                "conteúdo digital",
                "captação de vídeo",
                "captacao de video",
                "aftermovie",
            ],
            "semantic_tags": [
                "Conteúdo",
                "Vídeo",
            ],
        },
        "Projeção / Mapping": {
            "aliases": [
                "projection mapping",
                "video mapping",
                "vídeo mapping",
                "videomapping",
                "mapeamento de projecao",
                "mapeamento de projeção",
                "projecao mapeada",
                "projeção mapeada",
                "projecao",
                "projeção",
                "holografia",
                "holograma",
                "pepper's ghost",
            ],
            "semantic_tags": [
                "Audiovisual",
                "Imersivo",
            ],
        },
        "LED / Iluminação": {
            "aliases": [
                "led",
                "painel de led",
                "tela de led",
                "led wall",
                "ledwall",
                "iluminacao",
                "iluminação",
                "light design",
                "lighting design",
                "luz cenografica",
                "luz cenográfica",
                "neon",
                "pixel led",
            ],
            "semantic_tags": [
                "Audiovisual",
                "Cenografia",
            ],
        },
        "Áudio / Música": {
            "aliases": [
                "audio",
                "áudio",
                "sonorizacao",
                "sonorização",
                "sound system",
                "dj",
                "disc jockey",
                "banda",
                "show musical",
                "musica ao vivo",
                "música ao vivo",
                "trilha sonora",
                "sound design",
                "karaoke",
            ],
            "semantic_tags": [
                "Entretenimento",
                "Audiovisual",
            ],
        },
        "Streaming / Transmissão": {
            "aliases": [
                "streaming",
                "live streaming",
                "livestream",
                "transmissao ao vivo",
                "transmissão ao vivo",
                "broadcast",
                "webcast",
                "evento hibrido",
                "evento híbrido",
                "plataforma de evento online",
                "live commerce",
            ],
            "semantic_tags": [
                "Conteúdo",
                "Digital",
            ],
        },
        "Influenciadores / Creators": {
            "aliases": [
                "influenciadores",
                "influencer",
                "influencers",
                "creator",
                "creators",
                "criadores de conteudo",
                "criadores de conteúdo",
                "embaixadores",
                "brand ambassador",
                "ugc",
                "user generated content",
                "conteudo de creator",
                "conteúdo de creator",
            ],
            "semantic_tags": [
                "Conteúdo social",
                "Influência",
            ],
        },
        "Sustentabilidade": {
            "aliases": [
                "sustentabilidade",
                "sustentavel",
                "sustentável",
                "eco",
                "ecologico",
                "ecológico",
                "carbon neutral",
                "carbono neutro",
                "reciclagem",
                "coleta seletiva",
                "economia circular",
                "reuso",
                "upcycling",
                "compensacao de carbono",
                "compensação de carbono",
            ],
            "semantic_tags": [
                "ESG",
                "Impacto positivo",
            ],
        },
        "Hospitalidade": {
            "aliases": [
                "hospitalidade",
                "hospitality",
                "receptivo",
                "concierge",
                "welcome service",
                "atendimento vip",
                "lounge vip",
                "vip lounge",
                "guest experience",
                "experiencia do convidado",
                "experiência do convidado",
                "servico de sala",
                "serviço de sala",
            ],
            "semantic_tags": [
                "Atendimento",
                "Convidados",
            ],
        },
        "Mobilidade / Transporte": {
            "aliases": [
                "mobilidade",
                "transporte",
                "transfer",
                "shuttle",
                "van",
                "onibus",
                "ônibus",
                "carro executivo",
                "motorista",
                "valet",
                "estacionamento",
                "bike",
                "bicicleta",
                "mobilidade urbana",
            ],
            "semantic_tags": [
                "Logística",
                "Operação",
            ],
        },
    },
    "product": {
        "Bolsas e mochilas": {
            "aliases": [
                "bolsa",
                "bolsas",
                "mochila",
                "mochilas",
                "backpack",
                "bag",
                "tote bag",
                "totebag",
                "ecobag",
                "eco bag",
                "sacola",
                "sacochila",
                "shoulder bag",
                "pochete",
                "necessaire",
                "nécessaire",
                "mala",
                "mala de viagem",
                "bolsa termica",
                "bolsa térmica",
                "lunch bag",
            ],
            "semantic_tags": [
                "Utilidade",
                "Transporte",
            ],
        },
        "Copos, canecas e garrafas": {
            "aliases": [
                "copo",
                "copos",
                "caneca",
                "canecas",
                "mug",
                "cup",
                "tumbler",
                "garrafa",
                "garrafas",
                "squeeze",
                "squeezes",
                "bottle",
                "cantil",
                "copo termico",
                "copo térmico",
                "garrafa termica",
                "garrafa térmica",
                "travel mug",
                "taça",
                "taca",
                "shot",
            ],
            "semantic_tags": [
                "Bebidas",
                "Utilidade",
            ],
        },
        "Vestuário": {
            "aliases": [
                "vestuario",
                "vestuário",
                "roupa",
                "roupas",
                "camiseta",
                "t shirt",
                "t-shirt",
                "shirt",
                "polo",
                "jaqueta",
                "moletom",
                "hoodie",
                "colete",
                "calca",
                "calça",
                "shorts",
                "avental",
                "uniforme",
                "meia",
                "meias",
                "roupao",
                "roupão",
            ],
            "semantic_tags": [
                "Moda",
                "Uso pessoal",
            ],
        },
        "Bonés, chapéus e acessórios": {
            "aliases": [
                "bone",
                "boné",
                "bones",
                "bonés",
                "cap",
                "chapeu",
                "chapéu",
                "bucket",
                "bucket hat",
                "viseira",
                "touca",
                "gorro",
                "bandana",
                "lenco",
                "lenço",
                "gravata",
                "pulseira",
                "oculos",
                "óculos",
            ],
            "semantic_tags": [
                "Moda",
                "Acessório",
            ],
        },
        "Papelaria": {
            "aliases": [
                "papelaria",
                "caderno",
                "caderneta",
                "bloco",
                "bloco de notas",
                "notebook",
                "agenda",
                "planner",
                "caneta",
                "lapis",
                "lápis",
                "marca texto",
                "marcador",
                "estojo",
                "post it",
                "post-it",
                "pasta",
                "fichario",
                "fichário",
            ],
            "semantic_tags": [
                "Escritório",
                "Educação",
            ],
        },
        "Tecnologia e eletrônicos": {
            "aliases": [
                "tecnologia",
                "eletronico",
                "eletrônico",
                "eletronicos",
                "eletrônicos",
                "power bank",
                "powerbank",
                "carregador",
                "carregador sem fio",
                "wireless charger",
                "fone",
                "fone de ouvido",
                "headphone",
                "earbuds",
                "caixa de som",
                "speaker",
                "usb",
                "pen drive",
                "pendrive",
                "cabo",
                "hub usb",
                "mouse",
                "teclado",
                "webcam",
            ],
            "semantic_tags": [
                "Digital",
                "Utilidade",
            ],
        },
        "Casa e cozinha": {
            "aliases": [
                "casa",
                "cozinha",
                "home",
                "kitchen",
                "utensilio",
                "utensílio",
                "talher",
                "talheres",
                "prato",
                "bowl",
                "pote",
                "marmita",
                "lancheira",
                "abridor",
                "saca rolha",
                "saca-rolha",
                "tabua",
                "tábua",
                "avental de cozinha",
                "kit churrasco",
                "churrasco",
                "porta copo",
                "porta-copo",
            ],
            "semantic_tags": [
                "Utilidade",
                "Lar",
            ],
        },
        "Beleza e bem-estar": {
            "aliases": [
                "beleza",
                "bem estar",
                "bem-estar",
                "wellness",
                "beauty",
                "cosmetico",
                "cosmético",
                "necessaire de beleza",
                "espelho",
                "escova",
                "pente",
                "hidratante",
                "protetor solar",
                "sabonete",
                "alcool gel",
                "álcool gel",
                "kit spa",
                "vela aromatica",
                "vela aromática",
                "massageador",
            ],
            "semantic_tags": [
                "Cuidado pessoal",
                "Saúde",
            ],
        },
        "Alimentos e bebidas": {
            "aliases": [
                "alimento",
                "alimentos",
                "comida",
                "bebida",
                "bebidas",
                "food",
                "drink",
                "snack",
                "chocolate",
                "doce",
                "bala",
                "cookie",
                "biscoito",
                "cafe",
                "café",
                "cha",
                "chá",
                "cerveja",
                "vinho",
                "kit gourmet",
                "cesta",
                "cesta de alimentos",
            ],
            "semantic_tags": [
                "Consumo",
                "Gastronomia",
            ],
        },
        "Brinquedos e jogos": {
            "aliases": [
                "brinquedo",
                "brinquedos",
                "toy",
                "jogo",
                "jogos",
                "game",
                "pelucia",
                "pelúcia",
                "boneco",
                "action figure",
                "quebra cabeca",
                "quebra-cabeça",
                "puzzle",
                "baralho",
                "domino",
                "dominó",
                "jogo de tabuleiro",
                "tabuleiro",
                "bola",
            ],
            "semantic_tags": [
                "Entretenimento",
                "Lúdico",
            ],
        },
        "Chaveiros, pins e bottons": {
            "aliases": [
                "chaveiro",
                "chaveiros",
                "keychain",
                "pin",
                "pins",
                "broche",
                "botton",
                "button",
                "badge",
                "imã",
                "ima",
                "magnet",
                "patch",
                "adesivo",
                "sticker",
            ],
            "semantic_tags": [
                "Colecionável",
                "Acessório",
            ],
        },
        "Kits e caixas presenteáveis": {
            "aliases": [
                "kit",
                "kits",
                "gift kit",
                "welcome kit",
                "press kit",
                "influencer kit",
                "creator kit",
                "onboarding kit",
                "caixa presente",
                "caixa presenteavel",
                "caixa presenteável",
                "gift box",
                "box",
                "combo",
                "conjunto",
                "estojo presenteavel",
                "estojo presenteável",
            ],
            "semantic_tags": [
                "Presente",
                "Curadoria",
            ],
        },
        "Embalagens": {
            "aliases": [
                "embalagem",
                "embalagens",
                "packaging",
                "caixa",
                "sacola",
                "sleeve",
                "cinta",
                "faixa",
                "berco",
                "berço",
                "estojo",
                "lata",
                "pote",
                "envelope",
                "papel de seda",
                "cartucho",
            ],
            "semantic_tags": [
                "Apresentação",
                "Proteção",
            ],
        },
        "Viagem": {
            "aliases": [
                "viagem",
                "travel",
                "mala",
                "tag de mala",
                "etiqueta de mala",
                "porta passaporte",
                "porta-passaporte",
                "travesseiro de viagem",
                "mascara de dormir",
                "máscara de dormir",
                "organizador de mala",
                "necessaire de viagem",
                "adaptador de tomada",
            ],
            "semantic_tags": [
                "Mobilidade",
                "Utilidade",
            ],
        },
        "Esporte e lazer": {
            "aliases": [
                "esporte",
                "esportivo",
                "fitness",
                "academia",
                "lazer",
                "toalha esportiva",
                "garrafa esportiva",
                "bola",
                "corda",
                "elastico",
                "elástico",
                "tapete yoga",
                "yoga mat",
                "raquete",
                "frescobol",
                "skate",
                "prancha",
            ],
            "semantic_tags": [
                "Atividade física",
                "Lazer",
            ],
        },
        "Sustentáveis": {
            "aliases": [
                "sustentavel",
                "sustentável",
                "ecologico",
                "ecológico",
                "eco",
                "reciclado",
                "reciclavel",
                "reciclável",
                "biodegradavel",
                "biodegradável",
                "reutilizavel",
                "reutilizável",
                "bambu",
                "cortica",
                "cortiça",
                "papel semente",
                "algodao reciclado",
                "algodão reciclado",
                "rpet",
                "material reciclado",
            ],
            "semantic_tags": [
                "ESG",
                "Impacto positivo",
            ],
        },
        "Troféus e premiações": {
            "aliases": [
                "trofeu",
                "troféu",
                "trofeus",
                "troféus",
                "premio",
                "prêmio",
                "medalha",
                "medalhas",
                "placa de homenagem",
                "certificado",
                "award",
                "trophy",
                "reconhecimento",
            ],
            "semantic_tags": [
                "Reconhecimento",
                "Premiação",
            ],
        },
        "Ferramentas e utilidades": {
            "aliases": [
                "ferramenta",
                "ferramentas",
                "utilidade",
                "utilidades",
                "kit ferramenta",
                "canivete",
                "lanterna",
                "trena",
                "chave de fenda",
                "multitool",
                "multi tool",
                "organizador",
                "guarda chuva",
                "guarda-chuva",
                "sombrinha",
            ],
            "semantic_tags": [
                "Utilidade",
                "Praticidade",
            ],
        },
        "Pets": {
            "aliases": [
                "pet",
                "pets",
                "animal",
                "cachorro",
                "gato",
                "coleira",
                "bandana pet",
                "comedouro",
                "bebedouro pet",
                "brinquedo pet",
                "kit pet",
                "porta saquinho",
            ],
            "semantic_tags": [
                "Animais",
                "Uso pessoal",
            ],
        },
        "Infantil": {
            "aliases": [
                "infantil",
                "crianca",
                "criança",
                "kids",
                "baby",
                "bebe",
                "bebê",
                "kit infantil",
                "material escolar",
                "lancheira infantil",
                "brinquedo infantil",
                "roupa infantil",
            ],
            "semantic_tags": [
                "Crianças",
                "Família",
            ],
        },
    },
    "venue": {
        "Teatro / Auditório": {
            "aliases": [
                "teatro",
                "theater",
                "theatre",
                "auditorio",
                "auditório",
                "auditorium",
                "sala de espetaculos",
                "sala de espetáculos",
                "casa de espetaculos",
                "casa de espetáculos",
                "anfiteatro",
            ],
            "semantic_tags": [
                "Palco",
                "Plateia",
            ],
        },
        "Hotel": {
            "aliases": [
                "hotel",
                "resort",
                "pousada",
                "hotelaria",
                "centro de eventos de hotel",
                "sala de hotel",
                "ballroom de hotel",
            ],
            "semantic_tags": [
                "Hospedagem",
                "Hospitalidade",
            ],
        },
        "Centro de convenções / Pavilhão": {
            "aliases": [
                "centro de convencoes",
                "centro de convenções",
                "convention center",
                "pavilhao",
                "pavilhão",
                "exhibition center",
                "expo center",
                "centro de exposicoes",
                "centro de exposições",
                "feira",
                "fairground",
                "centro de eventos",
                "complexo de eventos",
            ],
            "semantic_tags": [
                "Grande porte",
                "Feiras e congressos",
            ],
        },
        "Casa de eventos": {
            "aliases": [
                "casa de eventos",
                "event venue",
                "event space",
                "espaco de eventos",
                "espaço de eventos",
                "salao de eventos",
                "salão de eventos",
                "casa de festas",
                "buffet",
                "espaco multiuso",
                "espaço multiuso",
            ],
            "semantic_tags": [
                "Eventos",
                "Flexível",
            ],
        },
        "Restaurante / Bar": {
            "aliases": [
                "restaurante",
                "restaurant",
                "bar",
                "pub",
                "cervejaria",
                "brewery",
                "cafe",
                "café",
                "bistro",
                "bistrô",
                "rooftop bar",
                "casa noturna",
                "nightclub",
                "balada",
            ],
            "semantic_tags": [
                "Gastronomia",
                "Hospitalidade",
            ],
        },
        "Shopping / Centro comercial": {
            "aliases": [
                "shopping",
                "shopping center",
                "mall",
                "centro comercial",
                "galeria comercial",
                "praca de alimentacao",
                "praça de alimentação",
                "mall aberto",
            ],
            "semantic_tags": [
                "Fluxo de público",
                "Varejo",
            ],
        },
        "Arena / Estádio": {
            "aliases": [
                "arena",
                "estadio",
                "estádio",
                "stadium",
                "ginasio",
                "ginásio",
                "gymnasium",
                "quadra",
                "complexo esportivo",
                "autodromo",
                "autódromo",
                "hipodromo",
                "hipódromo",
            ],
            "semantic_tags": [
                "Grande porte",
                "Esporte",
            ],
        },
        "Galpão / Espaço industrial": {
            "aliases": [
                "galpao",
                "galpão",
                "warehouse",
                "armazem",
                "armazém",
                "fabrica",
                "fábrica",
                "espaco industrial",
                "espaço industrial",
                "hangar",
                "deposito",
                "depósito",
                "loft industrial",
            ],
            "semantic_tags": [
                "Flexível",
                "Industrial",
            ],
        },
        "Rooftop / Terraço": {
            "aliases": [
                "rooftop",
                "terraco",
                "terraço",
                "cobertura",
                "laje",
                "sky lounge",
                "roof terrace",
                "deck elevado",
                "mirante",
            ],
            "semantic_tags": [
                "Área externa",
                "Vista",
            ],
        },
        "Parque / Praça / Área aberta": {
            "aliases": [
                "parque",
                "praca",
                "praça",
                "area aberta",
                "área aberta",
                "open area",
                "area externa",
                "área externa",
                "jardim",
                "garden",
                "bosque",
                "esplanada",
                "calcada",
                "calçada",
                "rua",
                "avenida",
            ],
            "semantic_tags": [
                "Área externa",
                "Espaço público",
            ],
        },
        "Praia / Orla": {
            "aliases": [
                "praia",
                "beach",
                "orla",
                "beira mar",
                "beira-mar",
                "quiosque de praia",
                "beach club",
                "arena de praia",
                "faixa de areia",
                "calçadão",
                "calcadao",
            ],
            "semantic_tags": [
                "Área externa",
                "Litoral",
            ],
        },
        "Museu / Centro cultural": {
            "aliases": [
                "museu",
                "museum",
                "centro cultural",
                "cultural center",
                "galeria de arte",
                "art gallery",
                "fundacao cultural",
                "fundação cultural",
                "instituto cultural",
                "biblioteca",
            ],
            "semantic_tags": [
                "Cultura",
                "Conteúdo",
            ],
        },
        "Universidade / Escola": {
            "aliases": [
                "universidade",
                "university",
                "faculdade",
                "college",
                "escola",
                "school",
                "campus",
                "centro academico",
                "centro acadêmico",
                "colegio",
                "colégio",
            ],
            "semantic_tags": [
                "Educação",
                "Campus",
            ],
        },
        "Clube": {
            "aliases": [
                "clube",
                "club",
                "clube social",
                "clube esportivo",
                "country club",
                "iate clube",
                "yacht club",
                "associacao",
                "associação",
            ],
            "semantic_tags": [
                "Lazer",
                "Esporte",
            ],
        },
        "Escritório / Coworking": {
            "aliases": [
                "escritorio",
                "escritório",
                "office",
                "coworking",
                "corporate office",
                "sede corporativa",
                "predio corporativo",
                "prédio corporativo",
                "business center",
                "sala de reuniao",
                "sala de reunião",
            ],
            "semantic_tags": [
                "Corporativo",
                "Reuniões",
            ],
        },
        "Estúdio": {
            "aliases": [
                "estudio",
                "estúdio",
                "studio",
                "estudio fotografico",
                "estúdio fotográfico",
                "estudio de video",
                "estúdio de vídeo",
                "estudio de tv",
                "estúdio de tv",
                "soundstage",
                "estudio de podcast",
                "estúdio de podcast",
            ],
            "semantic_tags": [
                "Produção",
                "Audiovisual",
            ],
        },
        "Cinema": {
            "aliases": [
                "cinema",
                "movie theater",
                "movie theatre",
                "sala de cinema",
                "complexo de cinema",
                "cine",
                "drive in",
                "drive-in",
            ],
            "semantic_tags": [
                "Audiovisual",
                "Plateia",
            ],
        },
        "Fazenda / Sítio": {
            "aliases": [
                "fazenda",
                "farm",
                "sitio",
                "sítio",
                "chacara",
                "chácara",
                "haras",
                "campo",
                "area rural",
                "área rural",
                "vinicola",
                "vinícola",
            ],
            "semantic_tags": [
                "Área externa",
                "Rural",
            ],
        },
        "Embarcação": {
            "aliases": [
                "embarcacao",
                "embarcação",
                "barco",
                "boat",
                "iate",
                "yacht",
                "navio",
                "ship",
                "cruzeiro",
                "ferry",
                "balsa",
            ],
            "semantic_tags": [
                "Mobilidade",
                "Náutico",
            ],
        },
        "Terminal / Aeroporto": {
            "aliases": [
                "aeroporto",
                "airport",
                "terminal",
                "terminal rodoviario",
                "terminal rodoviário",
                "rodoviaria",
                "rodoviária",
                "estacao",
                "estação",
                "metro",
                "metrô",
                "estacao de trem",
                "estação de trem",
            ],
            "semantic_tags": [
                "Fluxo de público",
                "Mobilidade",
            ],
        },
    },
}


def normalize_taxonomy_text(value: Any) -> str:
    text = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.casefold()
    text = text.replace("&", " e ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = re.split(r"[|,;\n]", str(value))

    return [
        str(item).strip()
        for item in values
        if str(item).strip()
    ]


def taxonomy_options(entity_type: str) -> list[str]:
    return list(
        TAXONOMY.get(
            entity_type,
            {},
        ).keys()
    )


def default_alias_rows() -> list[dict]:
    rows = []

    for entity_type, terms in TAXONOMY.items():
        for canonical, config in terms.items():
            aliases = [
                canonical,
                *config.get("aliases", []),
            ]

            for alias in dict.fromkeys(aliases):
                rows.append(
                    {
                        "entity_type": entity_type,
                        "canonical_term": canonical,
                        "alias": alias,
                        "normalized_alias": (
                            normalize_taxonomy_text(alias)
                        ),
                        "source": "default",
                        "is_active": True,
                    }
                )

    return rows


def _active_custom_rows(
    custom_aliases: Iterable[dict] | None,
) -> list[dict]:
    return [
        dict(row)
        for row in (custom_aliases or [])
        if row.get("is_active", True)
        and row.get("entity_type")
        in TAXONOMY
        and row.get("canonical_term")
        and row.get("alias")
    ]


def taxonomy_catalog_rows(
    custom_aliases: Iterable[dict] | None = None,
) -> list[dict]:
    rows = default_alias_rows()
    rows.extend(_active_custom_rows(custom_aliases))

    unique = {}

    for row in rows:
        key = (
            str(row["entity_type"]),
            str(row["normalized_alias"]),
        )
        unique[key] = row

    return list(unique.values())


def _alias_index(
    entity_type: str,
    custom_aliases: Iterable[dict] | None = None,
) -> dict[str, dict]:
    return {
        str(row["normalized_alias"]): row
        for row in taxonomy_catalog_rows(
            custom_aliases
        )
        if row["entity_type"] == entity_type
        and row["normalized_alias"]
    }


def aliases_for_canonical(
    entity_type: str,
    canonical_term: str,
    custom_aliases: Iterable[dict] | None = None,
) -> list[str]:
    aliases = [
        str(row["alias"])
        for row in taxonomy_catalog_rows(
            custom_aliases
        )
        if row["entity_type"] == entity_type
        and row["canonical_term"] == canonical_term
    ]

    return list(dict.fromkeys(aliases))


def _phrase_present(
    text: str,
    phrase: str,
) -> bool:
    if not text or not phrase:
        return False

    return bool(
        re.search(
            rf"(?:^|\s){re.escape(phrase)}(?:$|\s)",
            text,
        )
    )


def match_taxonomy(
    value: Any,
    entity_type: str,
    custom_aliases: Iterable[dict] | None = None,
    *,
    allow_fuzzy: bool = True,
) -> dict | None:
    normalized = normalize_taxonomy_text(value)

    if not normalized:
        return None

    index = _alias_index(
        entity_type,
        custom_aliases,
    )

    exact = index.get(normalized)

    if exact:
        return {
            "canonical": exact["canonical_term"],
            "matched_alias": exact["alias"],
            "confidence": 1.0,
            "method": "exact_alias",
        }

    phrase_matches = [
        row
        for alias, row in index.items()
        if len(alias) >= 4
        and _phrase_present(
            normalized,
            alias,
        )
    ]

    if phrase_matches:
        phrase_matches.sort(
            key=lambda row: len(
                str(row["normalized_alias"])
            ),
            reverse=True,
        )
        best = phrase_matches[0]

        return {
            "canonical": best["canonical_term"],
            "matched_alias": best["alias"],
            "confidence": 0.96,
            "method": "phrase_alias",
        }

    if not allow_fuzzy:
        return None

    if len(normalized) > 52:
        return None

    ranked = []

    for alias, row in index.items():
        if len(alias) < 4:
            continue

        score = SequenceMatcher(
            None,
            normalized,
            alias,
        ).ratio()

        if score >= 0.84:
            ranked.append(
                (
                    score,
                    row,
                )
            )

    if not ranked:
        return None

    ranked.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    best_score, best_row = ranked[0]
    second_score = (
        ranked[1][0]
        if len(ranked) > 1
        else 0.0
    )

    if (
        best_score < 0.87
        or best_score - second_score < 0.025
    ):
        return None

    return {
        "canonical": best_row["canonical_term"],
        "matched_alias": best_row["alias"],
        "confidence": round(best_score, 4),
        "method": "fuzzy_alias",
    }


def detect_taxonomy_terms(
    text: Any,
    entity_type: str,
    custom_aliases: Iterable[dict] | None = None,
    *,
    limit: int = 10,
) -> list[dict]:
    normalized = normalize_taxonomy_text(text)

    if not normalized:
        return []

    index = _alias_index(
        entity_type,
        custom_aliases,
    )
    matches = {}

    for alias, row in index.items():
        if len(alias) < 3:
            continue

        if _phrase_present(
            normalized,
            alias,
        ):
            canonical = str(
                row["canonical_term"]
            )
            current = matches.get(canonical)
            candidate = {
                "canonical": canonical,
                "matched_alias": row["alias"],
                "confidence": 0.94,
                "method": "text_alias",
                "_alias_length": len(alias),
            }

            if (
                current is None
                or candidate["_alias_length"]
                > current["_alias_length"]
            ):
                matches[canonical] = candidate

    ranked = sorted(
        matches.values(),
        key=lambda item: item["_alias_length"],
        reverse=True,
    )[:limit]

    for item in ranked:
        item.pop("_alias_length", None)

    return ranked


def semantic_tags_for(
    entity_type: str,
    canonical_terms: Iterable[str],
) -> list[str]:
    tags = []

    for canonical in canonical_terms:
        config = TAXONOMY.get(
            entity_type,
            {},
        ).get(
            canonical,
            {},
        )
        tags.extend(
            config.get(
                "semantic_tags",
                [],
            )
        )

    return list(dict.fromkeys(tags))


def normalize_record_taxonomy(
    record: dict,
    entity_type: str,
    custom_aliases: Iterable[dict] | None = None,
) -> dict:
    result = dict(record)

    if entity_type == "venue":
        category_field = "venue_type"
    else:
        category_field = "category"

    original_category = result.get(
        category_field
    )

    existing_tags = _as_list(
        result.get("tags")
    )

    context = " ".join(
        [
            str(result.get("name") or ""),
            str(original_category or ""),
            str(result.get("description") or ""),
            " ".join(existing_tags),
        ]
    )

    category_match = match_taxonomy(
        original_category,
        entity_type,
        custom_aliases,
    )

    detected = detect_taxonomy_terms(
        context,
        entity_type,
        custom_aliases,
    )

    if category_match:
        canonical = category_match[
            "canonical"
        ]
    elif detected:
        canonical = detected[0][
            "canonical"
        ]
        category_match = detected[0]
    else:
        canonical = (
            str(original_category).strip()
            if original_category is not None
            else None
        )

    detected_terms = [
        item["canonical"]
        for item in detected
    ]

    if canonical and canonical not in detected_terms:
        detected_terms.insert(0, canonical)

    semantic_tags = semantic_tags_for(
        entity_type,
        detected_terms,
    )

    merged_tags = list(
        dict.fromkeys(
            [
                *existing_tags,
                *detected_terms,
                *semantic_tags,
            ]
        )
    )

    if canonical:
        result[category_field] = canonical

    if entity_type in {
        "product",
        "activation",
        "venue",
    }:
        result["tags"] = merged_tags

    result["taxonomy_original_category"] = (
        original_category
    )
    result["taxonomy_canonical_category"] = (
        canonical
    )
    result["taxonomy_terms"] = detected_terms
    result["taxonomy_matched_aliases"] = [
        item["matched_alias"]
        for item in detected
    ]

    if category_match:
        result["taxonomy_category_match"] = (
            category_match
        )

    return result


def annotate_candidate_taxonomy(
    row: dict,
    custom_aliases: Iterable[dict] | None = None,
) -> dict:
    entity_type = str(
        row.get("item_type") or ""
    )

    if entity_type not in TAXONOMY:
        return {
            "category_nave": (
                row.get("category")
                or "Não informado"
            ),
            "taxonomy_terms": [],
            "taxonomy_search_text": "",
        }

    normalized = normalize_record_taxonomy(
        {
            "name": row.get("name"),
            "category": row.get("category"),
            "venue_type": row.get("category"),
            "description": row.get("description"),
            "tags": row.get("tags"),
        },
        entity_type,
        custom_aliases,
    )

    canonical = (
        normalized.get(
            "taxonomy_canonical_category"
        )
        or row.get("category")
        or "Não informado"
    )

    terms = normalized.get(
        "taxonomy_terms",
        [],
    )

    aliases = []

    for term in terms:
        aliases.extend(
            aliases_for_canonical(
                entity_type,
                term,
                custom_aliases,
            )
        )

    search_text = " ".join(
        [
            str(row.get("name") or ""),
            str(row.get("category") or ""),
            str(canonical or ""),
            str(row.get("description") or ""),
            str(row.get("supplier_name") or ""),
            str(row.get("location") or ""),
            " ".join(_as_list(row.get("tags"))),
            " ".join(terms),
            " ".join(aliases),
        ]
    )

    return {
        "category_nave": canonical,
        "taxonomy_terms": terms,
        "taxonomy_search_text": search_text,
    }


def taxonomy_prompt_block(
    entity_type: str,
) -> str:
    canonical_terms = taxonomy_options(
        entity_type
    )

    if not canonical_terms:
        return ""

    examples = {
        "activation": (
            "Considere equivalentes, por exemplo: photo-op, "
            "photoop, photopp, phopp, photo opportunity, "
            "espaço instagramável, cenário para fotos e selfie "
            "point. Quando representarem esse mesmo conceito, "
            "use a categoria canônica Photo-op."
        ),
        "product": (
            "Agrupe variações equivalentes: mochila, backpack, "
            "tote bag e ecobag em Bolsas e mochilas; squeeze, "
            "tumbler e garrafa em Copos, canecas e garrafas."
        ),
        "venue": (
            "Agrupe variações equivalentes: auditório, theater e "
            "anfiteatro em Teatro / Auditório; expo center, "
            "pavilhão e centro de eventos em Centro de "
            "convenções / Pavilhão."
        ),
    }

    return (
        "\n\nPADRONIZAÇÃO DE TAXONOMIA NAVE:\n"
        "Preserve o nome original do item. Para o campo de categoria "
        "ou tipo, prefira uma destas categorias canônicas quando "
        "houver correspondência clara:\n- "
        + "\n- ".join(canonical_terms)
        + "\n"
        + examples.get(entity_type, "")
        + "\nNão force uma categoria quando a fonte não permitir "
        "uma associação segura."
    )
