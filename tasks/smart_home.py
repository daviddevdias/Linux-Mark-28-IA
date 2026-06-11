import time, requests, config

API_BASE, CACHE_TTL = "https://api.smartthings.com/v1", 60
tv_cache, tv_cache_time, dev_cache, dev_cache_time = None, 0, None, 0
PISTAS_TV = [
    "tv",
    "televis",
    "qled",
    "oled",
    "the frame",
    "crystal uhd",
    "smart tv",
    "4k",
    "8k",
    "tizen",
    "uhd",
]
EXCLUIR = [
    "sensor",
    "motion",
    "button",
    "lock",
    "thermostat",
    "temp",
    "vibration",
    "moisture",
    "siren",
    "dimmer",
]


def limpar(s):
    s = (s or "").lower()
    for a, b in {
        "ã": "a",
        "á": "a",
        "à": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ç": "c",
    }.items():
        s = s.replace(a, b)
    return s


def headers():
    return {"Authorization": "Bearer " + config.SMARTTHINGS_TOKEN}


def get_api(endp):
    try:
        r = requests.get(API_BASE + "/" + endp, headers=headers(), timeout=8)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def post_api(endp, p):
    try:
        return (
            200
            <= requests.post(
                API_BASE + "/" + endp, headers=headers(), json=p, timeout=8
            ).status_code
            < 300
        )
    except:
        return False


def carregar_devices(force=False):
    global dev_cache, dev_cache_time
    n = time.time()
    if dev_cache and not force and (n - dev_cache_time < CACHE_TTL):
        return dev_cache
    d = get_api("devices")
    if not d:
        return dev_cache or []
    dev_cache, dev_cache_time = d.get("items", []), n
    return dev_cache


def enviar_comando(dev_id, cmd, cap, args=None):
    return post_api(
        "devices/" + dev_id + "/commands",
        [{"component": "main", "command": cmd, "arguments": args or []}],
    )


def score_tv(dev):
    t = (
        limpar(dev.get("label"))
        + " "
        + limpar(dev.get("name"))
        + " "
        + limpar(str(dev.get("deviceTypeName", "")))
    )
    for x in EXCLUIR:
        if x in t:
            return 0
    s = 0
    for p in PISTAS_TV:
        if p in t:
            s += 10
    return s


def buscar_tv():
    global tv_cache
    if tv_cache:
        return tv_cache
    if config.SMARTTHINGS_TV_DEVICE_ID:
        return config.SMARTTHINGS_TV_DEVICE_ID
    b_id, b_sc = None, 0
    for d in carregar_devices():
        s = score_tv(d)
        if s > b_sc:
            b_sc, b_id = s, d.get("deviceId")
    if b_id:
        tv_cache = b_id
        return b_id
    return None


def ligar_tv():
    t = buscar_tv()
    return enviar_comando(t, "switch", "switch", []) if t else False


def desligar_tv():
    t = buscar_tv()
    return enviar_comando(t, "switch", "switch", []) if t else False


def status_tv():
    t = buscar_tv()
    if not t:
        return "TV não encontrada"
    d = get_api("devices/" + t + "/status")
    if not d:
        return "Sem resposta"
    try:
        return "TV " + d["components"]["main"]["switch"]["switch"]["value"].upper()
    except:
        return "Status indisponível"
