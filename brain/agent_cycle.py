from __future__ import annotations
import asyncio, json, logging, re, time
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger("jarvis.agent")
MAX_PASSOS, TIMEOUT_PASSO = 8, 30.0


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

    prompt = f"Analise este objetivo e descreva em 2-3 frases o que precisa ser feito: '{objetivo}'. Contexto: {contexto}"
    return await router.responder(prompt)


async def planejar(objetivo: str, pensamento: str) -> list[Passo]:
    from engine.ia_router import router

    prompt = f'Crie um plano JSON. Objetivo: \'{objetivo}\'. Análise: \'{pensamento}\'. Retorne apenas JSON no formato: {{"passos": [{{"numero": 1, "descricao": "...", "ferramenta": "...", "argumentos": {{}}}}]}}'
    resposta = await router.responder(prompt)
    try:
        match = re.search(r"\{[\s\S]*\}", resposta)
        if match:
            dados = json.loads(match.group())
            return [Passo(**p) for p in dados.get("passos", [])][:MAX_PASSOS]
    except Exception:
        pass
    return []


async def executar_passo(passo: Passo) -> str:
    from engine.tools_mapper import despachar

    if not passo.ferramenta:
        return "Nenhuma ferramenta especificada."
    return await asyncio.wait_for(
        despachar(passo.ferramenta, passo.argumentos), timeout=TIMEOUT_PASSO
    )


async def validar(objetivo: str, passos: list[Passo]) -> tuple[bool, str]:
    from engine.ia_router import router

    resumo = "\n".join(
        f"Passo {p.numero} ({p.sucesso}): {p.resultado[:100]}" for p in passos
    )
    prompt = f"Objetivo: '{objetivo}'. Resumo da execução:\n{resumo}\nO objetivo foi alcançado? Responda SIM ou NAO e dê uma breve justificativa."
    resposta = await router.responder(prompt)
    sucesso = "SIM" in resposta.upper()[:10]
    return sucesso, resposta


async def executar_plano(plano: PlanoAgente):
    try:
        from storage.state_manager import state

        state.set("ia_modo_agente", True)
    except Exception:
        pass

    plano.ts_inicio = time.time()
    try:
        plano.status = StatusAgente.PENSANDO
        pensamento = await pensar(plano.objetivo, plano.contexto)

        plano.status = StatusAgente.PLANEJANDO
        plano.passos = await planejar(plano.objetivo, pensamento)
        if not plano.passos:
            raise ValueError("Falha ao gerar o plano.")

        plano.status = StatusAgente.EXECUTANDO
        for passo in plano.passos:
            passo.ts_inicio = time.time()
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
            if not passo.sucesso:
                break

        plano.status = StatusAgente.VALIDANDO
        sucesso, sintese = await validar(plano.objetivo, plano.passos)
        plano.resultado_final = sintese
        plano.status = StatusAgente.CONCLUIDO if sucesso else StatusAgente.FALHOU

    except Exception as exc:
        plano.status = StatusAgente.FALHOU
        plano.resultado_final = f"Tarefa interrompida: {exc}"
    finally:
        plano.ts_fim = time.time()
        try:
            from storage.state_manager import state

            state.set("ia_modo_agente", False)
        except Exception:
            pass
