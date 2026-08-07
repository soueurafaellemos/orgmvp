from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Iterable


# Fallback sem dependência externa. A lista existe apenas para distinguir
# claramente país de cidade quando dados antigos vieram para campos errados.
# O próprio base_country do cadastro também é sempre usado como sinal forte.
_COUNTRY_ALIASES = {
    "afeganistao", "afghanistan", "africa do sul", "south africa", "albania",
    "alemanha", "germany", "andorra", "angola", "antigua e barbuda", "arabia saudita",
    "saudi arabia", "argelia", "algeria", "argentina", "armenia", "australia",
    "austria", "azerbaijao", "azerbaijan", "bahamas", "bahrein", "bahrain",
    "bangladesh", "barbados", "belarus", "belgica", "belgium", "belize", "benin",
    "bolivia", "bosnia e herzegovina", "bosnia and herzegovina", "botsuana", "botswana",
    "brasil", "brazil", "brunei", "bulgaria", "burkina faso", "burundi", "butao", "bhutan",
    "cabo verde", "camaroes", "cameroon", "camboja", "cambodia", "canada", "catar", "qatar",
    "cazaquistao", "kazakhstan", "chade", "chad", "chile", "china", "chipre", "cyprus",
    "colombia", "comores", "comoros", "congo", "coreia do norte", "north korea",
    "coreia do sul", "south korea", "costa do marfim", "ivory coast", "cote d ivoire",
    "costa rica", "croacia", "croatia", "cuba", "dinamarca", "denmark", "djibuti", "djibouti",
    "dominica", "egito", "egypt", "el salvador", "emirados arabes unidos", "united arab emirates",
    "equador", "ecuador", "eritreia", "eritrea", "eslovaquia", "slovakia", "eslovenia", "slovenia",
    "espanha", "spain", "estados unidos", "estados unidos da america", "united states", "usa", "eua",
    "estonia", "eswatini", "etiopia", "ethiopia", "fiji", "filipinas", "philippines", "finlandia",
    "finland", "franca", "france", "gabao", "gabon", "gambia", "gana", "ghana", "georgia",
    "granada", "grenada", "grecia", "greece", "guatemala", "guiana", "guyana", "guine", "guinea",
    "guine bissau", "guinea bissau", "guine equatorial", "equatorial guinea", "haiti", "holanda",
    "netherlands", "paises baixos", "honduras", "hungria", "hungary", "iemen", "yemen", "ilhas marshall",
    "marshall islands", "ilhas salomao", "solomon islands", "india", "indonesia", "ira", "iran", "iraque",
    "iraq", "irlanda", "ireland", "islandia", "iceland", "israel", "italia", "italy", "jamaica", "japao",
    "japan", "jordania", "jordan", "kiribati", "kuwait", "laos", "lesoto", "lesotho", "letonia", "latvia",
    "libano", "lebanon", "liberia", "libia", "libya", "liechtenstein", "lituania", "lithuania", "luxemburgo",
    "luxembourg", "macedonia do norte", "north macedonia", "madagascar", "malasia", "malaysia", "malaui",
    "malawi", "maldivas", "maldives", "mali", "malta", "marrocos", "morocco", "mauricio", "mauritius",
    "mauritania", "mexico", "micronesia", "micronesia federated states of", "mocambique", "mozambique",
    "moldavia", "moldova", "monaco", "mongolia", "montenegro", "myanmar", "birmania", "namibia", "nauru",
    "nepal", "nicaragua", "niger", "nigeria", "noruega", "norway", "nova zelandia", "new zealand", "oma", "oman",
    "palau", "palestina", "palestine", "panama", "papua nova guine", "papua new guinea", "paquistao", "pakistan",
    "paraguai", "paraguay", "peru", "polonia", "poland", "portugal", "quenia", "kenya", "quirguistao", "kyrgyzstan",
    "reino unido", "united kingdom", "uk", "inglaterra", "england", "republica centro africana", "central african republic",
    "republica democratica do congo", "democratic republic of the congo", "republica dominicana", "dominican republic",
    "republica tcheca", "czech republic", "tchequia", "czechia", "romenia", "romania", "ruanda", "rwanda", "russia",
    "russia federacao russa", "federacao russa", "samoa", "san marino", "santa lucia", "saint lucia",
    "sao cristovao e nevis", "saint kitts and nevis", "sao tome e principe", "sao vicente e granadinas",
    "saint vincent and the grenadines", "senegal", "serra leoa", "sierra leone", "servia", "serbia", "seicheles",
    "seychelles", "singapura", "singapore", "siria", "syria", "somalia", "sri lanka", "sudao", "sudan",
    "sudao do sul", "south sudan", "suecia", "sweden", "suica", "switzerland", "suriname", "tailandia", "thailand",
    "tajiquistao", "tajikistan", "tanzania", "timor leste", "timor leste east timor", "togo", "tonga", "trinidad e tobago",
    "trinidad and tobago", "tunisia", "turcomenistao", "turkmenistan", "turquia", "turkey", "turkiye", "tuvalu",
    "ucrania", "ukraine", "uganda", "uruguai", "uruguay", "uzbequistao", "uzbekistan", "vanuatu", "vaticano",
    "vatican city", "venezuela", "vietna", "vietnam", "zambia", "zimbabue", "zimbabwe",
}

_MISSING = {"", "none", "null", "nan", "n a", "na", "nao informado", "nao se aplica", "-", "."}


def normalize_geo(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).casefold().strip()
    return " ".join(text.split())


def list_values(value: Any) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                loaded = json.loads(text)
                if isinstance(loaded, list):
                    return [str(item).strip() for item in loaded if str(item).strip()]
            except Exception:
                pass
        parts = [item.strip() for item in re.split(r"[;|\n]+", text) if item.strip()]
        if len(parts) > 1:
            return parts
        comma = [item.strip() for item in text.split(",") if item.strip()]
        if len(comma) > 1 and not (len(comma[-1]) == 2 and comma[-1].isalpha()):
            return comma
        return [text]
    return [str(value).strip()]


def country_keys(extra_countries: Iterable[Any] = ()) -> set[str]:
    values = set(_COUNTRY_ALIASES)
    for value in extra_countries:
        key = normalize_geo(value)
        if key and key not in _MISSING:
            values.add(key)
    return values


def is_country_name(value: Any, extra_countries: Iterable[Any] = ()) -> bool:
    key = normalize_geo(value)
    return bool(key and key in country_keys(extra_countries))


def city_state(value: Any, fallback_state: str = "", *, extra_countries: Iterable[Any] = ()) -> tuple[str, str]:
    """Interpreta um valor territorial somente quando ele parece ser cidade.

    Países jamais são devolvidos como cidade. Valores vazios, sentinelas e UFs
    isoladas também não entram no filtro municipal.
    """
    text = str(value or "").strip()
    key = normalize_geo(text)
    if not key or key in _MISSING or is_country_name(text, extra_countries):
        return "", ""
    if len(text) == 2 and text.isalpha():
        return "", ""

    for pattern in (
        r"^(.+?)\s*[—–]\s*([A-Za-z]{2})$",
        r"^(.+?)\s+-\s+([A-Za-z]{2})$",
        r"^(.+?)\s*[,/]\s*([A-Za-z]{2})$",
    ):
        match = re.match(pattern, text)
        if match:
            city = match.group(1).strip()
            if is_country_name(city, extra_countries):
                return "", ""
            return city, match.group(2).upper()
    return text, str(fallback_state or "").strip().upper()


def supplier_city_presence(row: dict) -> dict[tuple[str, str], str]:
    """Presença municipal real: base, equipe local ou atendimento declarado."""
    result: dict[tuple[str, str], str] = {}
    countries = [row.get("base_country"), row.get("country")]
    base_state = str(row.get("base_state") or "").strip().upper()

    base_city, base_city_state = city_state(
        row.get("base_city"), base_state, extra_countries=countries
    )
    if base_city:
        result[(normalize_geo(base_city), normalize_geo(base_city_state))] = "Base local"

    served_states = [
        item.upper()
        for item in list_values(row.get("served_states"))
        if len(item.strip()) == 2 and item.strip().isalpha()
    ]
    fallback_state = served_states[0] if len(served_states) == 1 else ""

    for value in list_values(row.get("local_team_locations")):
        city, state = city_state(value, fallback_state, extra_countries=countries)
        if city:
            result.setdefault((normalize_geo(city), normalize_geo(state)), "Equipe local")

    for value in list_values(row.get("served_cities")):
        city, state = city_state(value, fallback_state, extra_countries=countries)
        if city:
            result.setdefault((normalize_geo(city), normalize_geo(state)), "Atendimento declarado")
    return result


def city_label(city: str, state: str = "") -> str:
    city = str(city or "").strip()
    state = str(state or "").strip().upper()
    return f"{city} — {state}" if city and state else city


def supplier_city_options(rows: list[dict]) -> dict[str, tuple[str, str]]:
    options: dict[str, tuple[str, str]] = {}
    for row in rows:
        presence = supplier_city_presence(row)
        # Recupera a grafia humana a partir dos campos, mas só para chaves
        # validadas como cidade. Isso impede países de reaparecerem na UI.
        countries = [row.get("base_country"), row.get("country")]
        base_state = str(row.get("base_state") or "").strip().upper()
        served_states = [
            item.upper() for item in list_values(row.get("served_states"))
            if len(item.strip()) == 2 and item.strip().isalpha()
        ]
        fallback = served_states[0] if len(served_states) == 1 else ""
        entries: list[tuple[str, str]] = []
        entries.append(city_state(row.get("base_city"), base_state, extra_countries=countries))
        for field in ("local_team_locations", "served_cities"):
            for value in list_values(row.get(field)):
                entries.append(city_state(value, fallback, extra_countries=countries))
        for city, state in entries:
            if not city:
                continue
            key = (normalize_geo(city), normalize_geo(state))
            if key not in presence:
                continue
            options.setdefault(city_label(city, state), key)
    return dict(sorted(options.items(), key=lambda item: normalize_geo(item[0])))


def real_city_values(value: Any, *, extra_countries: Iterable[Any] = ()) -> set[str]:
    result: set[str] = set()
    for item in list_values(value):
        city, _state = city_state(item, extra_countries=extra_countries)
        if city:
            result.add(normalize_geo(city))
    return result
