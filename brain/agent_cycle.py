from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger("jarvis.agent")

MAX_PASSOS = 8
TIMEOUT_PASSO = 30.0


class StatusAgente(Enum):
    OCIOSO = "ocioso"
    PENSANDO = "pensando"
    PLANEJANDO = "planejando"
    EXECUTANDO = "executando"
    VALIDANDO = "validando"
    CONCLUIDO = "concluido"
    FALHOU = "falhou"


@dataclass
class Passo:
    numero: int
    descricao: str
    ferramenta: str = ""
    argumentos: dict = field(default_factory=dict)
    resultado: str = ""
    sucesso: bool = False
    ts_inicio: float = 0.0
    ts_fim: float = 0.0


@dataclass
class PlanoAgente:
    objetivo: str
    passos: list[Passo] = field(default_factory=list)
    contexto: str = ""
    status: StatusAgente = StatusAgente.OCIOSO
    resultado_final: str = ""
    ts_inicio: float = 0.0
    ts_fim: float = 0.0


async def pensar(objetivo: str, contexto: str) -> str:
    from engine.ia_router import router

    prompt = (
        f"Analise este objetivo e descreva em 2-3 frases o que precisa ser feito: '{objetivo}'. "
        f"Contexto disponível: {contexto or 'nenhum'}. Seja conciso e direto."
    )
    try:
        return await asyncio.wait_for(router.responder(prompt), timeout=15.0) or ""
    except Exception:
        return objetivo


async def planejar(objetivo: str, analise: str) -> list[dict]:
    from engine.ia_router import router

    prompt = (
        f"Objetivo: '{objetivo}'. Análise: '{analise}'. "
        "Crie um plano com no máximo 4 passos numerados. "
        "Para cada passo, indique qual ferramenta usar (se aplicável) e o que fazer. "
        "Ferramentas disponíveis: web_search, weather_report, open_app, computer_control, "
        "spotify_control, set_reminder, cmd_control, code_helper, smart_home, screen_analysis. "
        'Responda APENAS em JSON: [{"passo": 1, "descricao": "...", "ferramenta": "...", "args": {}}]. '
        "Se não precisar de ferramentas, use ferramenta vazia."
    )
    try:
        raw = await asyncio.wait_for(router.responder(prompt), timeout=20.0) or "[]"
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as exc:
        log.warning("Planejamento falhou: %s", exc)
    return [{"passo": 1, "descricao": objetivo, "ferramenta": "", "args": {}}]


async def executar_passo(passo: Passo) -> str:
    if not passo.ferramenta:
        from engine.ia_router import router

        resposta = await asyncio.wait_for(
            router.responder(passo.descricao), timeout=TIMEOUT_PASSO
        )
        return resposta or "Concluído sem resultado textual."

    from engine.tools_mapper import despachar

    return await asyncio.wait_for(
        despachar(passo.ferramenta, passo.argumentos or {}),
        timeout=TIMEOUT_PASSO,
    )


async def validar(objetivo: str, passos: list[Passo]) -> tuple[bool, str]:
    resultados = [
        f"Passo {p.numero}: {p.resultado[:200]}" for p in passos if p.resultado
    ]
    if not resultados:
        return False, "Nenhum passo produziu resultado."

    from engine.ia_router import router

    prompt = (
        f"Objetivo original: '{objetivo}'. "
        f"Resultados obtidos:\n" + "\n".join(resultados) + "\n"
        "O objetivo foi alcançado? Responda com uma síntese em 1-2 frases."
    )
    try:
        sintese = await asyncio.wait_for(router.responder(prompt), timeout=15.0) or ""
        sucesso = not any(
            w in sintese.lower()
            for w in ("falhou", "erro", "impossível", "não consegui")
        )
        return sucesso, sintese
    except Exception:
        ultimo = passos[-1].resultado if passos else "Sem resultado."
        return True, ultimo


async def executar_tarefa_complexa(objetivo: str, contexto: str = "") -> str:
    plano = PlanoAgente(objetivo=objetivo, contexto=contexto, ts_inicio=time.time())

    try:
        from storage.state_manager import state

        state.set("ia_modo_agente", True)
    except Exception:
        pass

    try:
        plano.status = StatusAgente.PENSANDO
        log.info("[AGENTE] Pensando sobre: %s", objetivo[:60])
        analise = await pensar(objetivo, plano.contexto)

        plano.status = StatusAgente.PLANEJANDO
        log.info("[AGENTE] Planejando...")
        plano_raw = await planejar(objetivo, analise)

        for i, pd in enumerate(plano_raw[:MAX_PASSOS], 1):
            plano.passos.append(
                Passo(
                    numero=i,
                    descricao=str(pd.get("descricao", "")),
                    ferramenta=str(pd.get("ferramenta", "")),
                    argumentos=pd.get("args", {}),
                )
            )

        plano.status = StatusAgente.EXECUTANDO
        for passo in plano.passos:
            passo.ts_inicio = time.time()
            log.info(
                "[AGENTE] Executando passo %d: %s", passo.numero, passo.descricao[:50]
            )
            try:
                passo.resultado = await executar_passo(passo)
                passo.sucesso = True
            except asyncio.TimeoutError:
                passo.resultado = f"Timeout no passo {passo.numero}."
                passo.sucesso = False
            except Exception as exc:
                passo.resultado = f"Erro: {exc}"
                passo.sucesso = False
            passo.ts_fim = time.time()
            log.info(
                "[AGENTE] Passo %d concluído: %s", passo.numero, passo.resultado[:60]
            )

        plano.status = StatusAgente.VALIDANDO
        sucesso, sintese = await validar(objetivo, plano.passos)
        plano.resultado_final = sintese
        plano.status = StatusAgente.CONCLUIDO if sucesso else StatusAgente.FALHOU

    except Exception as exc:
        log.error("[AGENTE] Falha geral: %s", exc)
        plano.status = StatusAgente.FALHOU
        plano.resultado_final = f"Tarefa interrompida: {exc}"
    finally:
        plano.ts_fim = time.time()
        try:
            from storage.state_manager import state

            state.set("ia_modo_agente", False)
        except Exception:
            pass

    duracao = round(plano.ts_fim - plano.ts_inicio, 1)
    log.info("[AGENTE] Concluído em %.1fs — %s", duracao, plano.status.value)
    return plano.resultado_final or "Tarefa concluída sem resposta textual."
