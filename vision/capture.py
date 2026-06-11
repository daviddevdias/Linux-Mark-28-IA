from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from io import BytesIO
from typing import Callable, Optional

import config
from mss import mss
from openai import OpenAI
from PIL import Image

log = logging.getLogger("vision")

MAX_WIDTH = 1280
JPEG_QUALITY = 42
MONITOR_INDEX = 1

client: Optional[OpenAI] = None


SYSTEM_RAPIDO = (
    "Você é o sensor visual do J.A.R.V.I.S. "
    "Responda apenas JSON puro sem markdown. "
    '{"ok": true/false, "tipo": "normal|erro|aviso|crash|travado|instalacao|compilacao|terminal|codigo|outro", '
    '"resumo": "curto", "problema": "", "sugestao_rapida": ""}'
)

SYSTEM_DICA = (
    "Assistente técnico. Diagnóstico direto. JSON puro."
    '{"ok": true/false, "tipo": "...", "resumo": "", "problema": "", "sugestao_rapida": ""}'
)


@dataclass
class ResultadoAnalise:
    ok: bool = True
    tipo: str = "normal"
    resumo: str = ""
    problema: str = ""
    sugestao_rapida: str = ""
    img_b64: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class MonitorConfig:
    intervalo_s: float = 8.0
    apenas_mudancas: bool = True
    gerar_dica_auto: bool = True
    cooldown_s: float = 45.0
    pergunta: str = "Analise esta tela."
    callback: Optional[Callable] = None


@dataclass
class Estado:
    rodando: bool = False
    ultimo_hash: str = ""
    ultima_analise: str = ""
    ultimo_resultado: Optional[ResultadoAnalise] = None
    capturas: int = 0
    chamadas_api: int = 0
    problemas: int = 0
    economizados: int = 0
    ultimo_alerta: float = 0.0


estado = Estado()
cfg_mon: Optional[MonitorConfig] = None
task: Optional[asyncio.Task] = None


def get_client() -> Optional[OpenAI]:
    global client

    if client:
        return client

    if not getattr(config, "QWEN_API_KEY", None):
        log.error("QWEN_API_KEY ausente")
        return None

    client = OpenAI(api_key=config.QWEN_API_KEY, base_url=config.BASE_URL)
    return client


def capturar_frame_base64() -> Optional[str]:
    try:
        with mss() as sct:
            idx = MONITOR_INDEX if len(sct.monitors) > MONITOR_INDEX else 0
            shot = sct.grab(sct.monitors[idx])

            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

            if img.width > MAX_WIDTH:
                img.thumbnail((MAX_WIDTH, 720), Image.LANCZOS)

            buf = BytesIO()
            img.save(buf, format="JPEG", quality=JPEG_QUALITY)

            return base64.b64encode(buf.getvalue()).decode()

    except Exception as e:
        log.error("captura falhou: %s", e)
        return None


def hash_frame(b64: str) -> str:
    return hashlib.md5(b64[:4096].encode()).hexdigest()


def parse(raw: str, img_b64: str) -> ResultadoAnalise:
    try:
        limpo = re.sub(r"```(?:json)?|```", "", raw).strip()
        start, end = limpo.find("{"), limpo.rfind("}") + 1
        limpo = limpo[start:end] if start >= 0 and end > start else limpo

        data = json.loads(limpo)

        return ResultadoAnalise(
            ok=bool(data.get("ok", True)),
            tipo=str(data.get("tipo", "normal")),
            resumo=str(data.get("resumo", "")),
            problema=str(data.get("problema", "")),
            sugestao_rapida=str(data.get("sugestao_rapida", "")),
            img_b64=img_b64,
        )

    except Exception:
        return ResultadoAnalise(
            ok=False,
            tipo="erro",
            resumo=raw[:120],
            problema=raw[:120],
            img_b64=img_b64,
        )


async def chamar_qwen(system: str, prompt: str, img_b64: str, max_tokens=150) -> str:
    c = get_client()

    if not c:
        return json.dumps(
            {
                "ok": False,
                "tipo": "erro",
                "resumo": "cliente ausente",
                "problema": "QWEN_API_KEY não configurada",
                "sugestao_rapida": "configurar API key",
            }
        )

    try:
        resp = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: c.chat.completions.create(
                model=config.CURRENT_MODEL,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_b64}"
                                },
                            },
                        ],
                    },
                ],
            ),
        )

        return resp.choices[0].message.content.strip()

    except Exception as e:
        log.exception("erro API visão: %s", e)
        return json.dumps(
            {
                "ok": False,
                "tipo": "erro",
                "resumo": "falha API",
                "problema": str(e),
                "sugestao_rapida": "verificar conexão",
            }
        )


async def analisar_tela(prompt: str) -> str:
    await asyncio.sleep(0.3)

    loop = asyncio.get_event_loop()
    img = await loop.run_in_executor(None, capturar_frame_base64)

    if not img:
        return json.dumps(
            {
                "ok": False,
                "tipo": "erro",
                "resumo": "sem captura",
                "problema": "frame vazio",
                "sugestao_rapida": "verificar permissões",
            }
        )

    raw = await chamar_qwen(SYSTEM_RAPIDO, prompt, img, 250)
    return json.dumps(parse(raw, img).__dict__)


async def gerar_dica(img_b64: str, problema: str, tipo: str) -> str:
    prompt = f"{tipo}: {problema}"
    raw = await chamar_qwen(SYSTEM_DICA, prompt, img_b64, 180)
    return parse(raw, img_b64).sugestao_rapida


async def loop_monitor():
    loop = asyncio.get_event_loop()

    while estado.rodando:
        t0 = time.monotonic()

        img = await loop.run_in_executor(None, capturar_frame_base64)
        estado.capturas += 1

        if img:
            h = hash_frame(img)

            if h != estado.ultimo_hash or not cfg_mon.apenas_mudancas:
                estado.ultimo_hash = h
                estado.chamadas_api += 1

                raw = await chamar_qwen(cfg_mon.pergunta, cfg_mon.pergunta, img)
                result = parse(raw, img)

                estado.ultima_analise = result.resumo
                estado.ultimo_resultado = result

                now = time.time()
                cooldown = now - estado.ultimo_alerta < cfg_mon.cooldown_s

                if not result.ok and not cooldown:
                    estado.problemas += 1
                    estado.ultimo_alerta = now

                    if cfg_mon.gerar_dica_auto:
                        result.sugestao_rapida = await gerar_dica(
                            img, result.problema, result.tipo
                        )

                if cfg_mon.callback:
                    try:
                        cfg_mon.callback(result)
                    except Exception as e:
                        log.warning("callback erro: %s", e)

        else:
            estado.economizados += 1

        await asyncio.sleep(max(0.5, cfg_mon.intervalo_s - (time.monotonic() - t0)))


async def iniciar_monitor(cfg: Optional[MonitorConfig] = None) -> bool:
    global cfg_mon, task, estado

    if task and not task.done():
        task.cancel()

    cfg_mon = cfg or MonitorConfig()
    estado = Estado(rodando=True)

    task = asyncio.create_task(loop_monitor())
    return True


def parar_monitor() -> dict:
    global estado, task

    estado.rodando = False

    if task:
        task.cancel()

    return {
        "capturas": estado.capturas,
        "chamadas_api": estado.chamadas_api,
        "problemas": estado.problemas,
        "economizados": estado.economizados,
        "ultima": estado.ultima_analise,
    }


def status_monitor() -> dict:
    return {
        "rodando": estado.rodando,
        "problemas": estado.problemas,
        "chamadas_api": estado.chamadas_api,
        "ultima": estado.ultima_analise,
    }
