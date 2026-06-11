from __future__ import annotations
import re, logging
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger("jarvis.model_selector")


class NivelModelo(Enum):
    RAPIDO = "rapido"
    INTERMEDIARIO = "intermediario"
    PESADO = "pesado"


@dataclass
class PerfilModelo:
    nome: str
    nivel: NivelModelo
    max_tokens: int
    adequado_para: list[str]


PERFIS: dict[str, PerfilModelo] = {
    "phi3": PerfilModelo(
        "phi3", NivelModelo.RAPIDO, 512, ["saudacao", "comando_simples", "status"]
    ),
    "llama3": PerfilModelo(
        "llama3", NivelModelo.INTERMEDIARIO, 1024, ["busca", "clima", "spotify", "app"]
    ),
    "qwen/qwen2.5-vl-72b-instruct": PerfilModelo(
        "qwen/qwen2.5-vl-72b-instruct",
        NivelModelo.PESADO,
        2048,
        ["visao", "codigo", "plano", "analise", "agente"],
    ),
}

RAPIDO_REGEX = re.compile(
    r"^(oi|ol[aá]|ei|ok|sim|n[aã]o|obrigado|tchau|status|volume|parar|continuar|pr[oó]xim[ao]|anterior|pausar|ligar|desligar|horas?|data|dia)\b",
    re.IGNORECASE,
)
VISAO_REGEX = re.compile(
    r"\b(veja|olha|analis[ea]|tela|c[aâ]mera|imagem|foto|l[eê]|descreva)\b",
    re.IGNORECASE,
)
PESADO_REGEX = re.compile(
    r"\b(c[oó]digo|programe|script|planeje|resuma|escreva|traduza|explique detalhadamente|agente)\b",
    re.IGNORECASE,
)


def modelo_atual() -> str:
    import config

    return (
        getattr(config, "CURRENT_MODEL", "qwen/qwen2.5-vl-72b-instruct")
        or "qwen/qwen2.5-vl-72b-instruct"
    )


def complexidade_heuristica(comando: str) -> float:
    palavras = comando.split()
    n = len(palavras)
    if n == 0:
        return 0.0
    return round(
        (
            min(n / 20, 1.0) * 0.5
            + (len(set(palavras)) / n) * 0.3
            + min(comando.count(",") / 3, 1.0) * 0.2
        ),
        3,
    )


def escolher_modelo(contexto: dict):
    comando = contexto.get("comando", "")
    if contexto.get("modelo_forcado", "") in PERFIS:
        return contexto["modelo_forcado"]
    if bool(contexto.get("imagem")) or VISAO_REGEX.search(comando):
        return "qwen/qwen2.5-vl-72b-instruct"
    if (
        PESADO_REGEX.search(comando)
        or complexidade_heuristica(comando) >= 0.65
        or contexto.get("historico_len", 0) > 10
    ):
        return modelo_atual()
    if RAPIDO_REGEX.match(comando.strip()) and contexto.get("historico_len", 0) < 3:
        return "phi3" if "phi3" in PERFIS else modelo_atual()
    return "llama3" if "llama3" in PERFIS else modelo_atual()
