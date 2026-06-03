from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional

import requests

import config

TIMEOUT = 10
CACHE_TTL = timedelta(minutes=10)

OWM_BASE = "https://api.openweathermap.org/data/2.5"
WTTR_BASE = "https://wttr.in/{cidade}?format=j1&lang=pt"

HEADERS = {"Accept-Language": "pt-BR,pt;q=0.9", "User-Agent": "CORE-Assistant/1.0"}

cache: dict = {}

CIDADE_ALIAS = {
    "porto alegre": "Porto Alegre,BR",
    "porto alegre rs": "Porto Alegre,BR",
    "poa": "Porto Alegre,BR",
    "são paulo": "Sao Paulo,BR",
    "sao paulo": "Sao Paulo,BR",
    "sp": "Sao Paulo,BR",
    "rio de janeiro": "Rio de Janeiro,BR",
    "rj": "Rio de Janeiro,BR",
    "belo horizonte": "Belo Horizonte,BR",
    "bh": "Belo Horizonte,BR",
    "curitiba": "Curitiba,BR",
    "brasilia": "Brasilia,BR",
    "brasília": "Brasilia,BR",
    "salvador": "Salvador,BR",
    "fortaleza": "Fortaleza,BR",
    "manaus": "Manaus,BR",
    "recife": "Recife,BR",
    "esteio": "Esteio,BR",
    "esteio rs": "Esteio,BR",
    "novo hamburgo": "Novo Hamburgo,BR",
    "canoas": "Canoas,BR",
    "pelotas": "Pelotas,BR",
    "caxias do sul": "Caxias do Sul,BR",
}

PLACEHOLDER_LOCAL = frozenset({
    "este", "esta", "isto", "isso", "aqui", "mesma", "mesmo",
    "casa", "lar", "padrao", "minha", "cidade", "lugar", "moro",
    "vivo", "moramos", "onde", "eu", "o", "a",
})

def remover_acentos(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")

def get_cidade_painel() -> str:
    c = (getattr(config, "cidade_padrao", None) or "").strip()
    if c:
        return c
    try:
        from storage.memory_manager import get_cidade
        mem = (get_cidade() or "").strip()
        if mem:
            return mem
    except Exception:
        pass
    return "Esteio,BR"

def menciona_clima(texto_normalizado: str) -> bool:
    n = texto_normalizado
    if not n:
        return False
    # Aceita tanto texto com acentos quanto normalizado (sem acentos)
    # pois controller.py passa o texto já normalizado via normalizar()
    if any(x in n for x in (
        "clima", "previsao", "previsão", "temperatura",
        "meteorolog", "chuvisco", "chuva", "tempo",
    )):
        # evita falsos positivos com "tempo" isolado (ex: "quanto tempo")
        palavras_clima = (
            "clima", "previsao", "previsão", "temperatura",
            "meteorolog", "chuvisco",
        )
        if any(x in n for x in palavras_clima):
            return True
        # "tempo" só conta com contexto de clima
        if "tempo" in n and any(x in n for x in (
            "hoje", "amanha", "amanh", "semana", "chuva", "faz", "esta", "vai"
        )):
            return True
        # "chuva" com qualquer contexto
        if "chuva" in n:
            return True
    return False

def extrair_cidade_do_utterance(texto: str) -> str:
    raw = (texto or "").strip()
    if not raw:
        return ""
    low = remover_acentos(raw.lower())
    low = re.sub(r"[^\w\s,]", " ", low)
    low = re.sub(r"\s+", " ", low).strip()
    chaves = (
        " na cidade de ", " cidade de ", " em que cidade ",
        " na cidade ", " para a cidade de ", " para cidade de ",
        " para ", " em ", " no ", " na ",
    )
    for key in chaves:
        if key in low:
            tail = low.rsplit(key, 1)[-1].strip()
            toks = [t for t in tail.split() if t]
            if not toks or all(t in PLACEHOLDER_LOCAL for t in toks):
                return ""
            return tail.strip(" .,!?")[:80]
    lixo = {
        "jarvis", "qual", "e", "a", "o", "de", "da", "do", "das", "dos",
        "me", "diz", "informe", "quero", "saber", "por", "favor", "como",
        "esta", "hoje", "amanha", "agora", "previsao", "tempo", "clima",
        "temperatura", "que", "foi", "sera", "vai", "fazer", "mostre",
        "cidade", "no", "na", "em", "para",
    }
    toks = [t for t in low.split() if t and t not in lixo]
    tail = " ".join(toks).strip()
    if not tail or tail in PLACEHOLDER_LOCAL or len(tail) < 2 or len(tail) > 60:
        return ""
    return tail

def padronizar_nome_cidade(cidade: str) -> str:
    if not cidade:
        cidade = get_cidade_painel()
    cidade = cidade.strip().lower()
    alias = CIDADE_ALIAS.get(cidade) or CIDADE_ALIAS.get(remover_acentos(cidade))
    if alias:
        return alias
    cidade = re.sub(r"[^\w\s,]", " ", cidade).strip()
    if ",br" not in cidade.lower() and "brazil" not in cidade.lower():
        cidade = cidade + ",BR"
    return cidade

def carregar_chave_owm() -> str:
    return getattr(config, "OPENWEATHER_API_KEY", os.environ.get("OPENWEATHER_API_KEY", ""))

def requerer_clima_atual_owm(cidade: str) -> Optional[dict]:
    key = carregar_chave_owm()
    if not key:
        return None
    try:
        url = f"{OWM_BASE}/weather"
        r = requests.get(
            url,
            params={"q": cidade, "appid": key, "units": "metric", "lang": "pt_br"},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def requerer_previsao_owm(cidade: str) -> Optional[dict]:
    key = carregar_chave_owm()
    if not key:
        return None
    try:
        url = f"{OWM_BASE}/forecast"
        r = requests.get(
            url,
            params={"q": cidade, "appid": key, "units": "metric", "lang": "pt_br", "cnt": 40},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def requerer_dados_wttr(cidade: str) -> Optional[dict]:
    cidade_enc = cidade.replace(" ", "+")
    try:
        url = WTTR_BASE.format(cidade=cidade_enc)
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        dados = r.json()
        if isinstance(dados, dict) and "current_condition" in dados:
            return dados
    except Exception:
        pass
    return None

def recuperar_cache(chave: str) -> Optional[dict]:
    if chave in cache:
        dados, ts = cache[chave]
        if datetime.now() - ts < CACHE_TTL:
            return dados
        del cache[chave]
    return None

def registrar_cache(chave: str, dados: dict) -> None:
    cache[chave] = (dados, datetime.now())

def obter_previsao_hoje(cidade_alvo: str = "") -> str:
    alvo = padronizar_nome_cidade(cidade_alvo or get_cidade_painel())
    chave = f"hoje:{alvo}"
    cached = recuperar_cache(chave)

    if cached is None:
        dados_owm = requerer_clima_atual_owm(alvo)
        if dados_owm:
            cached = {"fonte": "owm", "dados": dados_owm}
            registrar_cache(chave, cached)
        else:
            dados_wttr = requerer_dados_wttr(alvo)
            if dados_wttr:
                cached = {"fonte": "wttr", "dados": dados_wttr}
                registrar_cache(chave, cached)

    if not cached:
        return f"Não consegui obter o clima para '{alvo}'."

    if cached["fonte"] == "owm":
        d = cached["dados"]
        try:
            temp = round(d["main"]["temp"])
            sensacao = round(d["main"]["feels_like"])
            umidade = d["main"]["humidity"]
            desc = d["weather"][0]["description"]
            vento = round(d["wind"]["speed"] * 3.6)
            regiao = d.get("name", alvo)
            return (
                f"Em {regiao}: {desc}, {temp}°C, "
                f"sensação de {sensacao}°C, "
                f"umidade {umidade}%, vento {vento} km/h."
            )
        except Exception:
            pass

    if cached["fonte"] == "wttr":
        try:
            d = cached["dados"]
            atual = d["current_condition"][0]
            temp = atual.get("temp_C", "??")
            sensacao = atual.get("FeelsLikeC", "??")
            desc = atual.get("lang_pt", [{}])[0].get("value", "Estável")
            umidade = atual.get("humidity", "??")
            vento = atual.get("windspeedKmph", "??")
            regiao = d.get("nearest_area", [{}])[0].get("areaName", [{}])[0].get("value", alvo)
            return (
                f"Em {regiao}: {desc.lower()}, {temp}°C, "
                f"sensação de {sensacao}°C, "
                f"umidade {umidade}%, vento {vento} km/h."
            )
        except Exception:
            pass

    return "Dados meteorológicos incompletos."

def verificar_chuva_amanha(cidade_alvo: str = "") -> str:
    alvo = padronizar_nome_cidade(cidade_alvo or get_cidade_painel())
    chave = f"amanha:{alvo}"
    cached = recuperar_cache(chave)

    if cached is None:
        dados_owm = requerer_previsao_owm(alvo)
        if dados_owm:
            cached = {"fonte": "owm", "dados": dados_owm}
            registrar_cache(chave, cached)
        else:
            dados_wttr = requerer_dados_wttr(alvo)
            if dados_wttr:
                cached = {"fonte": "wttr", "dados": dados_wttr}
                registrar_cache(chave, cached)

    if not cached:
        return "Previsão indisponível."

    amanha_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    if cached["fonte"] == "owm":
        try:
            lista = cached["dados"].get("list", [])
            amanha_items = [
                item for item in lista
                if item["dt_txt"].startswith(amanha_str)
            ]
            if not amanha_items:
                return "Previsão de amanhã indisponível."
            temps = [i["main"]["temp"] for i in amanha_items]
            chuvas = [i.get("rain", {}).get("3h", 0) for i in amanha_items]
            desc = amanha_items[len(amanha_items) // 2]["weather"][0]["description"]
            return (
                f"Amanhã em {alvo.split(',')[0].title()}: {desc}, "
                f"mínima {round(min(temps))}°C, máxima {round(max(temps))}°C, "
                f"chuva acumulada {round(sum(chuvas), 1)} mm."
            )
        except Exception:
            pass

    if cached["fonte"] == "wttr":
        try:
            weather = cached["dados"].get("weather", [])
            if len(weather) < 2:
                return "Previsão indisponível."
            amanha = weather[1]
            horario = amanha["hourly"][4]
            desc = horario.get("lang_pt", [{}])[0].get("value", "")
            chuva = horario.get("precipMM", "0")
            temp_max = amanha.get("maxtempC", "??")
            temp_min = amanha.get("mintempC", "??")
            return (
                f"{alvo.split(',')[0].title()}: {desc.lower()}, "
                f"{chuva} mm de chuva, "
                f"mínima {temp_min}°C e máxima {temp_max}°C."
            )
        except Exception:
            pass

    return "Erro ao montar a previsão."

def previsao_7_dias(cidade_alvo: str = "") -> str:
    alvo = padronizar_nome_cidade(cidade_alvo or get_cidade_painel())
    key = carregar_chave_owm()
    if not key:
        return "Configure OPENWEATHER_API_KEY para previsão de 7 dias."
    try:
        url = f"{OWM_BASE}/forecast/daily"
        r = requests.get(
            url,
            params={"q": alvo, "appid": key, "units": "metric", "lang": "pt_br", "cnt": 7},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return "Previsão de 7 dias indisponível (API gratuita não suporta)."
        lista = r.json().get("list", [])
        linhas = []
        for item in lista:
            data = datetime.fromtimestamp(item["dt"]).strftime("%d/%m")
            desc = item["weather"][0]["description"]
            tmin = round(item["temp"]["min"])
            tmax = round(item["temp"]["max"])
            chuva = round(item.get("rain", 0), 1)
            linhas.append(f"{data}: {desc}, {tmin}–{tmax}°C, chuva {chuva}mm")
        return "\n".join(linhas) if linhas else "Sem dados."
    except Exception as e:
        return f"Erro previsão 7 dias: {e}"

def limpar_cache_clima() -> None:
    cache.clear()

def obter_clima_raw(cidade_alvo: str) -> str:
    alvo = cidade_alvo if cidade_alvo else get_cidade_painel()
    alvo_norm = padronizar_nome_cidade(alvo)
    dados = requerer_clima_atual_owm(alvo_norm) or requerer_dados_wttr(alvo_norm)
    return json.dumps(dados if dados else {"error": f"Falha ao obter clima para '{alvo}'."})