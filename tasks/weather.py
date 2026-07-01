from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta

import requests
import config

TIMEOUT = 10
CACHE_TTL = timedelta(minutes=10)

OWM_BASE = "https://api.openweathermap.org/data/2.5"

HEADERS = {
    "Accept-Language": "pt-BR",
    "User-Agent": "CORE-Assistant/1.0",
}

cache: dict[str, tuple[str, datetime]] = {}

CIDADE_ALIAS = {
    "porto alegre": "Porto Alegre,BR",
    "poa": "Porto Alegre,BR",
    "sao paulo": "Sao Paulo,BR",
    "sp": "Sao Paulo,BR",
    "rio de janeiro": "Rio de Janeiro,BR",
    "rj": "Rio de Janeiro,BR",
    "belo horizonte": "Belo Horizonte,BR",
    "bh": "Belo Horizonte,BR",
    "curitiba": "Curitiba,BR",
    "brasilia": "Brasilia,BR",
    "salvador": "Salvador,BR",
    "fortaleza": "Fortaleza,BR",
    "manaus": "Manaus,BR",
    "recife": "Recife,BR",
    "esteio": "Esteio,BR",
    "canoas": "Canoas,BR",
    "pelotas": "Pelotas,BR",
    "caxias do sul": "Caxias do Sul,BR",
}


def norm(txt: str) -> str:
    txt = unicodedata.normalize("NFD", txt.lower())
    return "".join(c for c in txt if unicodedata.category(c) != "Mn")


def get_city_config() -> str:
    return getattr(config, "cidade_padrao", "Esteio,BR")


def get_cidade_painel() -> str:
    return get_city_config()


def cache_get(key: str):
    if key in cache:
        data, ts = cache[key]
        if datetime.now() - ts < CACHE_TTL:
            return data
        del cache[key]
    return None


def cache_set(key: str, value: str):
    cache[key] = (value, datetime.now())


def request(url: str, params: dict):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def city(city_name: str = "") -> str:
    c = norm(city_name or get_city_config())
    return CIDADE_ALIAS.get(c, city_name.title() + ",BR")



def obter_previsao_hoje(cidade: str = "") -> str:
    alvo = city(cidade)
    key = f"now:{alvo}"

    cached = cache_get(key)
    if cached:
        return cached

    data = request(
        f"{OWM_BASE}/weather",
        {
            "q": alvo,
            "appid": getattr(config, "OPENWEATHER_API_KEY", ""),
            "units": "metric",
            "lang": "pt_br",
        },
    )

    if not data:
        return f"Não foi possível obter clima de {alvo}. Verifique a API Key."

    try:
        resultado = (
            f"{data['name']}: {data['weather'][0]['description']}, "
            f"{round(data['main']['temp'])}°C, "
            f"sensação {round(data['main']['feels_like'])}°C, "
            f"umidade {data['main']['humidity']}%"
        )
        cache_set(key, resultado)
        return resultado
    except Exception:
        return "Erro ao processar clima."


def verificar_chuva_amanha(cidade: str = "") -> str:
    alvo = city(cidade)
    key = f"rain:{alvo}"

    cached = cache_get(key)
    if cached:
        return cached

    data = request(
        f"{OWM_BASE}/forecast",
        {
            "q": alvo,
            "appid": getattr(config, "OPENWEATHER_API_KEY", ""),
            "units": "metric",
            "lang": "pt_br",
        },
    )

    if not data:
        return "Previsão indisponível."

    try:
        target = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        items = [i for i in data.get("list", []) if i["dt_txt"].startswith(target)]

        if not items:
            return "Sem dados para amanhã."

        temps = [i["main"]["temp"] for i in items]
        rain = sum(i.get("rain", {}).get("3h", 0) for i in items)
        desc = items[len(items) // 2]["weather"][0]["description"]

        result = (
            f"Amanhã em {alvo.split(',')[0]}: {desc}, "
            f"min {round(min(temps))}°C, max {round(max(temps))}°C, "
            f"chuva {round(rain, 1)}mm"
        )

        cache_set(key, result)
        return result

    except Exception:
        return "Erro na previsão."


def obter_clima_raw(cidade: str) -> str:
    alvo = city(cidade)
    dados = request(
        f"{OWM_BASE}/weather",
        {
            "q": alvo,
            "appid": getattr(config, "OPENWEATHER_API_KEY", ""),
            "units": "metric",
        },
    )
    return json.dumps(dados or {"error": "falha"})


def menciona_clima(cmd: str) -> bool:
    return any(
        p in cmd.lower()
        for p in (
            "clima",
            "tempo",
            "chover",
            "previsão",
            "previsao",
            "graus",
            "frio",
            "calor",
            "chuva",
        )
    )


def extrair_cidade_do_utterance(texto: str) -> str:
    m = re.search(r"em\s+([a-zA-ZÀ-ÿ\s]+)", texto.lower())
    if m:
        c = (
            m.group(1)
            .replace("hoje", "")
            .replace("amanha", "")
            .replace("amanhã", "")
            .strip()
        )
        if c:
            return c
    return get_city_config()


clima_agora = obter_previsao_hoje
chuva_amanha = verificar_chuva_amanha
clima_raw = obter_clima_raw
