import asyncio, inspect, os, sqlite3, psutil, socket, threading, time
from datetime import datetime

_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "logs", "monitor.db"
)
ALERTAS = {
    "tempo": False,
    "bateria": False,
    "temp": False,
    "cpu": False,
    "rede": False,
    "ram": False,
    "disco": False,
}
INTERVALO_S, TEMP_CRITICA, TEMP_OK, BAT_CRITICA, DISCO_CRITICO, DISCO_OK = (
    10,
    82,
    70,
    20,
    90.0,
    80.0,
)
falar_callback, monitor_async_loop = None, None


def conectar_banco_monitor() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    c = sqlite3.connect(_DB_PATH, check_same_thread=False, timeout=5)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute(
        "CREATE TABLE IF NOT EXISTS alertas (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, tipo TEXT NOT NULL, mensagem TEXT NOT NULL, valor REAL)"
    )
    c.commit()
    return c


def registrar_log_alerta(tipo: str, mensagem: str, valor: float = 0.0):
    try:
        with conectar_banco_monitor() as c:
            c.execute(
                "INSERT INTO alertas (ts, tipo, mensagem, valor) VALUES (?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), tipo, mensagem, valor),
            )
            c.commit()
    except:
        pass


def registrar_falar(fn):
    global falar_callback
    falar_callback = fn


def registrar_loop_monitor_voz(loop):
    global monitor_async_loop
    monitor_async_loop = loop


def falar(texto: str):
    if not falar_callback:
        return
    try:
        if inspect.iscoroutinefunction(falar_callback):
            if monitor_async_loop and not monitor_async_loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    falar_callback(texto), monitor_async_loop
                )
        else:
            falar_callback(texto)
    except:
        pass


def check_internet() -> bool:
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=3.0):
            return True
    except:
        return False


def obter_temperatura_cpu() -> float | None:
    try:
        t = psutil.sensors_temperatures()
        if t:
            for n in ("k10temp", "coretemp", "cpu_thermal", "acpitz", "zenpower"):
                if n in t and t[n]:
                    return t[n][0].current
            for n, e in t.items():
                if e and "cpu" in n.lower():
                    return e[0].current
    except:
        pass
    return None


def checar_rede():
    o = check_internet()
    if not o and not ALERTAS["rede"]:
        registrar_log_alerta("rede", "Conexão perdida.")
        falar("Atenção, Chefe. Perda de conexão detectada.")
        ALERTAS["rede"] = True
    elif o and ALERTAS["rede"]:
        registrar_log_alerta("rede", "Conexão restaurada.")
        falar("Conexão restaurada. Sistemas online.")
        ALERTAS["rede"] = False


def checar_temperatura():
    t = obter_temperatura_cpu()
    if t is None:
        return
    if t >= TEMP_CRITICA and not ALERTAS["temp"]:
        registrar_log_alerta("temperatura", f"CPU a {t}°C", t)
        falar(f"Alerta térmico. {int(t)} graus.")
        ALERTAS["temp"] = True
    elif t < TEMP_OK:
        ALERTAS["temp"] = False


def checar_bateria():
    b = psutil.sensors_battery()
    if not b:
        return
    if b.percent < BAT_CRITICA and not b.power_plugged and not ALERTAS["bateria"]:
        registrar_log_alerta("bateria", f"Bateria em {b.percent}%", b.percent)
        falar(f"Bateria em {int(b.percent)} por cento.")
        ALERTAS["bateria"] = True
    elif b.power_plugged:
        ALERTAS["bateria"] = False


def checar_disco():
    try:
        u = psutil.disk_usage("/").percent
    except:
        return
    if u >= DISCO_CRITICO and not ALERTAS["disco"]:
        registrar_log_alerta("disco", f"Disco em {u}%", u)
        falar(f"Disco em {int(u)} por cento. Libere espaço.")
        ALERTAS["disco"] = True
    elif u < DISCO_OK:
        ALERTAS["disco"] = False


def monitorar_proativo():
    while True:
        for fn in [checar_rede, checar_temperatura, checar_bateria, checar_disco]:
            try:
                fn()
            except:
                pass
        time.sleep(INTERVALO_S)


def iniciar_sentinela():
    threading.Thread(target=monitorar_proativo, daemon=True, name="Sentinela").start()


def status_hardware() -> dict:
    b = psutil.sensors_battery()
    t = obter_temperatura_cpu()
    try:
        d = psutil.disk_usage("/").percent
    except:
        d = None
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": psutil.virtual_memory().percent,
        "temp_cpu": round(t, 1) if t else None,
        "disco_percent": d,
        "bateria_percent": b.percent if b else None,
        "carregando": b.power_plugged if b else None,
        "alertas": {k: v for k, v in ALERTAS.items() if v},
    }


def alertas_recentes(limite: int = 50) -> list[dict]:
    try:
        with conectar_banco_monitor() as c:
            return [
                dict(zip(("ts", "tipo", "mensagem", "valor"), r))
                for r in c.execute(
                    "SELECT ts, tipo, mensagem, valor FROM alertas ORDER BY id DESC LIMIT ?",
                    (limite,),
                ).fetchall()
            ]
    except:
        return []
