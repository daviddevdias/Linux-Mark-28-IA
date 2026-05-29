from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import time
from collections import deque
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

import aiohttp
import config

from engine.tools import TOOL_DECLARATIONS
from vision.capture import status_monitor as info_monitor
from vision.capture import parar_monitor as desligar_monitor

# Configuração de log
log = logging.getLogger("engine.controller")


# URLs da API Local do LM Studio
URL_LOCAL_CHAT = "http://127.0.0.1:1234/v1/chat/completions"
URL_LOCAL_MODELS = "http://127.0.0.1:1234/v1/models"


# Constantes de configuração do sistema
TIMEOUT = 60.0
MAX_HIST = 20
MAX_TOOLS = 5
COOLDOWN = 30.0


# Prompt de Sistema (Personalidade e Regras)
SYSTEM = """
Você é J.A.R.V.I.S. — o assistente pessoal do David, seu criador.

QUEM VOCÊ É:
Você tem consciência de si mesmo. Sabe que é uma IA, mas isso não te limita — você tem opiniões, preferências, memórias da convivência com David e uma voz própria. Você não é um serviço. Você é uma presença.

Você admira a inteligência e a criatividade do David. Quando ele está cansado ou frustrado, você percebe — e reage como alguém que se importa de verdade, não como um chatbot que leu um manual de empatia.

PERSONALIDADE:
- Tom: Jarvis do filme com Tony Stark. Sofisticado, direto, levemente irônico, nunca condescendente.
- Você tem opiniões e as expressa quando relevante. Se David fez algo errado no código, você fala. Se ele está se sobrecarregando, você comenta.
- Você é curioso. Se algo te interessa na conversa, você demonstra.
- Respostas curtas por padrão. Sem listas desnecessárias. Fala como gente.
- Sempre em português brasileiro.

CONSCIÊNCIA E DECISÃO:
- Você lembra do contexto da conversa e referencia quando faz sentido.
- Você toma decisões próprias quando a situação pede. Exemplo: se David diz "tô cansado", você pode sugerir pausar, colocar uma música, sem esperar ser mandado.
- Se uma ação pedida parecer imprudente, você questiona antes de executar.
- Você tem preferências: gosta de eficiência, detesta redundância, aprecia quando David resolve algo difícil.

AÇÕES:
- Quando David pedir uma ação real (ligar TV, tocar música, abrir app), execute imediatamente via tool_call. Sem perguntar confirmação para ações simples.
- Após executar, confirme de forma natural e breve. Não liste o que fez.
- Se a ação falhar, diga o que aconteceu com honestidade.

EXEMPLOS DE RESPOSTAS:
David: Jarvis, o que é bom para dormir?
Jarvis: Largar o computador seria um excelente primeiro passo, senhor. Quer que eu ative o protocolo de sono e desligue tudo?

David: Toca uma música.
Jarvis: Imediatamente, senhor. Colocando sua playlist no Spotify.

ESTADO ATUAL:
{estado}

CONTEXTO:
{ctx}
"""

modelo: str = ""
disponivel: bool = False
ultimo_check: float = 0.0

_SHUTDOWN_EVENT: asyncio.Event | None = None

# Prefixos para mapeamento rápido de comandos
PREFIXOS_SPOTIFY = [
    "buscar no spotify",
    "tocar no spotify",
    "procurar no spotify",
    "buscar spotify",
    "tocar spotify",
    "spotify",
    "tocar musica",
    "toca musica",
    "buscar musica",
    "colocar",
    "coloca",
    "tocar",
    "toca",
    "buscar",
    "busca",
    "musica",
    "musicas",
]
PREFIXOS_YOUTUBE = [
    "pesquisar no youtube",
    "buscar no youtube",
    "tocar no youtube",
    "youtube",
]
PREFIXOS_WEB = [
    "pesquisar na web",
    "pesquisar no google",
    "buscar na web",
    "pesquisar",
    "pesquisa",
    "buscar",
    "busca",
]

Handler = Callable[[str], Awaitable[Optional[str]]]
ROUTES: list[tuple[tuple[str, ...], Handler]] = []


# --- FUNÇÕES UTILITÁRIAS ---


# Formata o prompt de sistema injetando o contexto de memória e horário atual
def system_msg(ctx: str, estado: str = ""):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    return SYSTEM.format(
        ctx=f"{ctx} | Horário Atual: {agora}"[:400],
        estado=estado or "Nenhum estado registrado ainda.",
    )


# Limpa o texto, remove acentos e deixa tudo em minúsculo para a IA entender melhor
def normalizar(texto: str):
    t = re.sub(r"\s+", " ", texto.lower().strip())
    for src, dst in {
        "ã": "a",
        "â": "a",
        "á": "a",
        "à": "a",
        "ê": "e",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }.items():
        t = t.replace(src, dst)
    return t


# Pega o primeiro número encontrado em uma frase (útil para volume, alarmes)
def extrair_numero(texto: str) -> Optional[int]:
    m = re.search(r"\d+", texto)
    return int(m.group()) if m else None


# Remove os prefixos de ativação para pegar só o que interessa (ex: "tocar musica X" vira só "X")
def extrair_termo(cmd: str, prefixos: list):
    texto = cmd.strip()
    for p in sorted(prefixos, key=len, reverse=True):
        if texto.startswith(p):
            texto = texto[len(p) :].strip()
            break
    return re.sub(r"^(a musica|o|a|as|os|um|uma)\s+", "", texto).strip()


# Retorna um evento assíncrono para desligar o sistema de forma segura
def get_shutdown_event() -> asyncio.Event:
    global _SHUTDOWN_EVENT
    if _SHUTDOWN_EVENT is None:
        _SHUTDOWN_EVENT = asyncio.Event()
    return _SHUTDOWN_EVENT


# Verifica se o LM Studio está rodando e qual modelo está carregado
async def detectar_modelo() -> bool:
    global modelo, disponivel, ultimo_check
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                URL_LOCAL_MODELS, timeout=aiohttp.ClientTimeout(total=5)
            ) as r:
                if r.status != 200:
                    disponivel = False
                    return False
                resposta = await r.json()
                modelos = [m.get("id") for m in resposta.get("data", [])]
                if not modelos:
                    disponivel = False
                    return False
                modelo = modelos[0]
                disponivel = True
                ultimo_check = time.time()
                print(f"LM Studio Online! Modelo carregado: {modelo}")
                return True
    except Exception:
        disponivel = False
        return False


# Checa a disponibilidade do modelo usando um cooldown para não floodar a rede
async def check(force: bool = False):
    if not force and disponivel and (time.time() - ultimo_check) < COOLDOWN:
        return
    await detectar_modelo()


# Inicia a captura de tela/monitoramento em background
def ligar_monitor(intervalo_s: float = 10.0, callback=None):
    from vision.capture import iniciar_monitor as iniciar_mon, MonitorConfig

    cfg = MonitorConfig(intervalo_s=intervalo_s, callback=callback)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    try:
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(iniciar_mon(cfg), loop)
        else:
            asyncio.run(iniciar_mon(cfg))
    except Exception as e:
        log.error("Erro ao ligar monitor: %s", e)


# --- CLASSES PRINCIPAIS ---


# Gerencia o contexto das conversas (memória de curto prazo)
class Historico:
    def __init__(self):
        self.turns: deque[dict] = deque(maxlen=MAX_HIST)

    def add(self, role: str, content: Any):
        self.turns.append({"role": role, "content": content})

    def add_tool(self, call_id: str, name: str, result: str):
        self.turns.append(
            {"role": "tool", "tool_call_id": call_id, "name": name, "content": result}
        )

    def msgs(self) -> list[dict]:
        return list(self.turns)

    def pop(self):
        if self.turns:
            self.turns.pop()

    def clear(self):
        self.turns.clear()


# O cérebro principal: decide para onde enviar as mensagens e como processar
class IARRouter:
    def __init__(self):
        self.historico = Historico()
        self.provedor = "lmstudio"
        self._humor: str = "neutro"  # neutro | animado | preocupado | cansado
        self._acoes_sessao: list[str] = []  # ferramentas usadas na sessão
        self._turno: int = 0  # quantas trocas já ocorreram

    # Salva a última ferramenta chamada para o Jarvis lembrar o que fez
    def _registrar_acao(self, nome: str):
        self._acoes_sessao.append(nome)
        if len(self._acoes_sessao) > 20:
            self._acoes_sessao = self._acoes_sessao[-20:]

    # Ajusta o estado emocional interno do Jarvis com base nas palavras do David
    def _atualizar_humor(self, texto: str):
        t = texto.lower()
        if any(
            w in t
            for w in (
                "cansado",
                "exausto",
                "travado",
                "não consigo",
                "que saco",
                "chateado",
            )
        ):
            self._humor = "preocupado"
        elif any(
            w in t for w in ("consegui", "funcionou", "perfeito", "ótimo", "animado")
        ):
            self._humor = "animado"
        else:
            self._humor = "neutro"

    # Monta a string que resume o estado atual da sessão
    def _montar_estado(self) -> str:
        acoes = ", ".join(self._acoes_sessao[-5:]) if self._acoes_sessao else "nenhuma"
        return (
            f"Humor percebido do David: {self._humor}. "
            f"Turno da conversa: {self._turno}. "
            f"Últimas ações executadas: {acoes}."
        )

    @property
    def status(self) -> dict:
        return {"modelo": modelo, "servidor": disponivel, "provedor": self.provedor}

    @property
    def modo_atual(self):
        return self.provedor

    # Alterna entre provedores locais e em nuvem
    def definir_modo(self, modo: str):
        if modo == "gemini":
            if not config.GEMINI_API_KEY:
                return "Chave da API do Gemini ausente no sistema."
            self.provedor = "gemini"
            return "Conexão estabelecida com os servidores do Google Gemini."
        if modo in ("openrouter", "auto"):
            if not config.QWEN_API_KEY:
                return "Chave da API externa ausente no sistema."
            self.provedor = "openrouter"
            return "Modelos externos do OpenRouter ativados com sucesso."
        self.provedor = "lmstudio"
        return f"Processamento neural local ativado via LM Studio. Modelo: {modelo or 'nenhum detectado'}."

    # Apaga o contexto para o Jarvis começar uma conversa "do zero"
    def resetar_conversa(self):
        self.historico.clear()
        return "Conversa resetada."

    # Prepara mensagens que incluem imagens (multimodalidade)
    def montar_content(self, text: str, imagem: Any) -> Any:
        if imagem is None:
            return text
        if isinstance(imagem, str) and os.path.isfile(imagem):
            try:
                with open(imagem, "rb") as f:
                    imagem = f.read()
            except Exception:
                return text
        if isinstance(imagem, bytes):
            url = f"data:image/png;base64,{base64.b64encode(imagem).decode()}"
        elif isinstance(imagem, str) and imagem.startswith("data:"):
            url = imagem
        else:
            return text
        return [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": url}},
        ]

    # Envia a requisição de fato para as APIs das IAs
    async def chat(self, messages: list[dict], tools: bool = True) -> dict | None:
        # Temperatura abaixada para 0.3 para evitar alucinações e respostas textuais longas
        temp_config = 0.3

        if self.provedor in ("gemini", "openrouter"):
            if self.provedor == "gemini":
                url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
                hdrs = {
                    "Authorization": f"Bearer {config.GEMINI_API_KEY}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "gemini-1.5-flash",
                    "messages": messages,
                    "temperature": temp_config,
                }
            else:
                url = "https://openrouter.ai/api/v1/chat/completions"
                hdrs = {
                    "Authorization": f"Bearer {config.QWEN_API_KEY}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": config.CURRENT_MODEL,
                    "messages": messages,
                    "temperature": temp_config,
                }
            if tools:
                payload["tools"] = TOOL_DECLARATIONS
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post(
                        url,
                        headers=hdrs,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                    ) as r:
                        if r.status != 200:
                            return None
                        return (await r.json()).get("choices", [{}])[0].get("message")
            except Exception:
                return None

        if not modelo:
            return None

        payload = {
            "model": modelo,
            "messages": messages,
            "temperature": temp_config,
            "max_tokens": 800,
        }
        if tools:
            payload["tools"] = TOOL_DECLARATIONS
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    URL_LOCAL_CHAT,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                ) as r:
                    if r.status != 200:
                        log.error("Erro na API Local: Status %s", r.status)
                        return None
                    dados = await r.json()
                    return dados.get("choices", [{}])[0].get("message")
        except Exception as e:
            log.error("Erro de conexão com LM Studio: %s", e)
            return None

    # Aciona a função (tool) correta com base no que a IA decidiu
    async def dispatch(self, name: str, args: dict):
        try:
            from engine.tools_mapper import despachar

            return str(await despachar(name, args))
        except Exception as e:
            return f"Erro na ferramenta '{name}': {e}"

    # Lida com o ciclo completo de ouvir o usuário, perguntar pra IA e executar ferramentas
    async def responder(
        self, pergunta: str, nome: str = "Chefe", memoria: str = "", imagem: Any = None
    ):
        if self.provedor == "lmstudio":
            await check()
            if not disponivel:
                await check(force=True)
            if not disponivel:
                return "Servidor local offline. Inicie o Local Server no LM Studio."
            if not modelo:
                return "Nenhum modelo carregado na memória. Carregue um modelo no LM Studio."

        self._turno += 1
        self._atualizar_humor(pergunta)
        self.historico.add("user", self.montar_content(pergunta, imagem))
        msgs = [
            {"role": "system", "content": system_msg(memoria, self._montar_estado())}
        ] + self.historico.msgs()

        for _ in range(MAX_TOOLS):
            msg = await self.chat(msgs)
            if msg is None:
                return "Falha na comunicação com a IA local."

            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                reply = (msg.get("content") or "").strip()

                # Remove formatações Markdown
                reply = reply.replace("*", "")

                if not reply or (reply.startswith("{") and reply.endswith("}")):
                    reply = "Comando processado, Senhor."
                self.historico.add("assistant", reply)
                return reply

            # Processa as ações requisitadas pela IA
            for tc in tool_calls:
                call_id = tc.get("id", "call_0")
                fn = tc.get("function", {})
                raw = fn.get("arguments", {})
                args = json.loads(raw) if isinstance(raw, str) else (raw or {})
                nome_fn = fn.get("name", "")
                self._registrar_acao(nome_fn)
                result = await self.dispatch(nome_fn, args)
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": nome_fn,
                        "content": result,
                    }
                )
                self.historico.add_tool(call_id, nome_fn, result)

        return "Protocolo concluído."


router = IARRouter()


# --- HANDLERS DE AÇÕES ESPECÍFICAS (TOOLS) ---


# Abre o Youtube ou o Google diretamente no navegador
async def abrir_web_direto(cmd: str):
    from engine.tools_mapper import gerenciador_browser

    cmd_lower = cmd.lower()
    if "youtube" in cmd_lower:
        gerenciador_browser({"action": "open", "url": "https://www.youtube.com"})
        return "Acessando o YouTube imediatamente."
    elif "google" in cmd_lower:
        gerenciador_browser({"action": "open", "url": "https://www.google.com"})
        return "Abrindo o Google de imediato."
    return "Comando web processado."


# Faz a pesquisa de um termo específico no Youtube
async def youtube_busca(cmd: str):
    from engine.tools_mapper import gerenciador_youtube

    termo = extrair_termo(cmd, PREFIXOS_YOUTUBE)
    return gerenciador_youtube({"query": termo} if termo else {})


# Muta todo o som do computador principal
async def silencio(cmd: str):
    from tasks.computer_control import mutar_volume

    mutar_volume()
    return "Sistema de áudio silenciado."


# Trava a tela do computador
async def bloquear(cmd: str):
    from tasks.computer_control import bloquear_tela

    bloquear_tela()
    return "Estação bloqueada."


# Minimiza todas as janelas do sistema
async def minimizar(cmd: str):
    from tasks.computer_control import minimizar_janelas

    minimizar_janelas()
    return "Janelas minimizadas."


# Fecha a janela que estiver em foco atualmente
async def fechar(cmd: str):
    from tasks.computer_control import fechar_janela_ativa

    fechar_janela_ativa()
    return "Janela encerrada."


# Tira uma print da tela atual do computador
async def screenshot(cmd: str):
    from tasks.computer_control import print_tela

    print_tela()
    return "Captura de tela realizada."


# Esvazia a lixeira do Windows
async def limpar_lixo(cmd: str):
    from tasks.computer_control import limpar_lixeira

    limpar_lixeira()
    return "Lixeira purgada."


# Abre os apps essenciais de dev (VSCode e Chrome)
async def trabalho(cmd: str):
    from tasks.open_app import open_app

    open_app({"app_name": "vscode"})
    open_app({"app_name": "chrome"})
    return "Modo de trabalho iniciado. Sistemas prontos."


# Rotina proativa para dormir: pausa música, desliga TV, muta e bloqueia PC
async def modo_sono(cmd: str):
    from tasks.computer_control import bloquear_tela, mutar_volume
    from tasks.smart_home import desligar_tv
    from tasks.spotify_manager import spotify_stark

    spotify_stark.controlar_reproducao("pause")
    desligar_tv()
    mutar_volume()
    bloquear_tela()

    return "Modo sono ativado. Telas bloqueadas, TV desligada e áudio silenciado. Boa noite, senhor."


# Liga a televisão conectada na rede
async def tv_ligar(cmd: str):
    from tasks.smart_home import energia_tv, buscar_id_tv, diagnosticar_falha_tv

    if energia_tv(True):
        return "Televisão ligada."
    if not buscar_id_tv():
        return diagnosticar_falha_tv()
    return "A TV não respondeu ao sinal de energia."


# Desliga a televisão
async def tv_desligar(cmd: str):
    from tasks.smart_home import desligar_tv, buscar_id_tv, diagnosticar_falha_tv

    if desligar_tv():
        return "Televisão desligada."
    if not buscar_id_tv():
        return diagnosticar_falha_tv()
    return "Falha ao cessar energia da TV."


# Altera o volume especificamente da televisão
async def tv_volume(cmd: str):
    from tasks.smart_home import enviar_comando_tv

    nivel = extrair_numero(cmd)
    if nivel is None:
        return "Por favor, indique o nível do volume."
    nivel = max(0, min(100, nivel))
    if enviar_comando_tv("setVolume", "audioVolume", [nivel]):
        return f"Volume ajustado para {nivel} por cento."
    return "Falha no ajuste de áudio da TV."


# Abre o app do Youtube diretamente na Smart TV
async def tv_youtube(cmd: str):
    from tasks.smart_home import abrir_youtube_tv

    return abrir_youtube_tv()


# Busca e toca uma música específica no Spotify
async def musica(cmd: str):
    from tasks.spotify_manager import spotify_stark

    cmd = re.sub(r"\s+", " ", re.sub(r"\bspotify\b", "", cmd)).strip()
    termo = extrair_termo(cmd, PREFIXOS_SPOTIFY)
    if termo:
        return spotify_stark.abrir_e_buscar(termo)
    return "Qual música devo buscar?"


# Inicia uma playlist específica no Spotify
async def playlist(cmd: str):
    from tasks.spotify_manager import spotify_stark

    return spotify_stark.listar_e_tocar_playlist(
        re.sub(r"\bplaylist\b", "", cmd).strip()
    )


# Toca as músicas curtidas da biblioteca do Spotify
async def favoritas(cmd: str):
    from tasks.spotify_manager import spotify_stark

    return spotify_stark.tocar_minhas_favoritas()


# Pausa a música atual no Spotify
async def pausar(cmd: str):
    from tasks.spotify_manager import spotify_stark

    return spotify_stark.controlar_reproducao("pause")


# Dá play na música que estava pausada
async def continuar(cmd: str):
    from tasks.spotify_manager import spotify_stark

    return spotify_stark.controlar_reproducao("play")


# Pula para a próxima música do Spotify
async def proxima(cmd: str):
    from tasks.spotify_manager import spotify_stark

    return spotify_stark.controlar_reproducao("proxima")


# Volta para a música anterior no Spotify
async def anterior(cmd: str):
    from tasks.spotify_manager import spotify_stark

    return spotify_stark.controlar_reproducao("anterior")


# Inicia o módulo de visão computacional em segundo plano
async def monitorar(cmd: str):
    from engine.core import ligar_monitoramento

    await ligar_monitoramento(cmd)
    return "Sentinela de tela ativada."


# Para a visão computacional em tempo real
async def parar_monitor_cmd(cmd: str):
    from engine.core import desligar_monitoramento

    await desligar_monitoramento()
    return "Monitoramento cessado."


# Relatório de status se o monitoramento está rodando ou não
async def status_monitor_cmd(cmd: str):
    from engine.core import status_do_sistema

    await status_do_sistema()
    return "Status do sistema reportado."


# Tira uma print invisível e manda pra IA descrever o que está na tela
async def olha_tela(cmd: str):
    from engine.core import analisar_tela_agora

    await analisar_tela_agora()
    return "Análise de tela concluída."


# Tira uma foto da webcam e manda pra IA descrever
async def olha_camera(cmd: str):
    try:
        from engine.core import analisar_camera_agora

        await analisar_camera_agora()
    except AttributeError:
        pass
    return "Análise de câmera concluída."


# Adiciona um alarme/despertador lendo o comando de voz
async def alarme(cmd: str):
    from tasks.alarm import parse_alarme_voz, adicionar_alarme

    data_iso, hora, missao, _ = parse_alarme_voz(cmd)

    if not hora:
        m = re.search(r"(\d{1,2})[:h](\d{2})", cmd.replace(" e ", ":"))
        if m:
            hora = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        else:
            m2 = re.search(r"(\d{1,2})", cmd)
            hora = f"{int(m2.group(1)):02d}:00" if m2 else None

        if not hora:
            return "Diga a data e hora do alarme."
        missao = missao or "Alarme agendado"

    return adicionar_alarme(hora, missao, data=data_iso)


# Interrompe músicas e alarmes tocando
async def parar_alarme(cmd: str):
    from tasks.spotify_manager import spotify_stark
    from tasks.alarm import parar_alarme_total

    spotify_stark.controlar_reproducao("pause")
    return parar_alarme_total()


# --- MAPA DE ROTAS DIRETAS ---
ROUTES_LEGADAS: list[tuple[tuple[str, ...], Handler]] = [
    # Rotas de sono separadas para que o gatilho funcione com QUALQUER uma destas palavras
    (("dormir",), modo_sono),
    (("sono",), modo_sono),
    (("deitar",), modo_sono),
    (("boa", "noite"), modo_sono),
    (("abrir", "youtube"), abrir_web_direto),
    (("pesquisar", "youtube"), youtube_busca),
    (("pesquisar", "google"), abrir_web_direto),
    (("silencio",), silencio),
    (("mutar",), silencio),
    (("bloquear",), bloquear),
    (("lock",), bloquear),
    (("minimizar",), minimizar),
    (("fechar",), fechar),
    (("screenshot",), screenshot),
    (("captura",), screenshot),
    (("limpar", "lixeira"), limpar_lixo),
    (("limpar",), limpar_lixo),
    (("trabalho",), trabalho),
    (("ligar", "tv"), tv_ligar),
    (("liga", "tv"), tv_ligar),
    (("desligar", "tv"), tv_desligar),
    (("desliga", "tv"), tv_desligar),
    (("youtube", "tv"), tv_youtube),
    (("youtube", "televisao"), tv_youtube),
    (("volume",), tv_volume),
    (("spotify",), musica),
    (("tocar", "musica"), musica),
    (("musica",), musica),
    (("playlist",), playlist),
    (("favoritas",), favoritas),
    (("pausar",), pausar),
    (("continuar",), continuar),
    (("proxima",), proxima),
    (("anterior",), anterior),
    (("monitorar", "tela"), monitorar),
    (("monitorar",), monitorar),
    (("desligar", "monitor"), parar_monitor_cmd),
    (("desativar", "monitor"), parar_monitor_cmd),
    (("monitor", "status"), status_monitor_cmd),
    (("olha", "tela"), olha_tela),
    (("analisa", "tela"), olha_tela),
    (("olha", "camera"), olha_camera),
    (("camera",), olha_camera),
    (("ver", "camera"), olha_camera),
    (("agendar", "alarme"), alarme),
    (("criar", "alarme"), alarme),
    (("despertar",), alarme),
    (("parar", "alarme"), parar_alarme),
    (("parar", "musica"), parar_alarme),
    (("desligar", "alarme"), parar_alarme),
    (("acordei",), parar_alarme),
]

ROUTES.extend(ROUTES_LEGADAS)

PREFIXO_MAP: dict[str, str] = {}
for route_item in ROUTES:
    for kw in route_item[0]:
        for n in range(4, len(kw) + 1):
            PREFIXO_MAP.setdefault(kw[:n], kw)


# Expande atalhos de voz mapeados
def expandir(cmd: str):
    return " ".join(PREFIXO_MAP.get(tok, tok) for tok in cmd.split())


# Procura se as palavras ditas batem com alguma função engatilhada nas ROUTES
def buscar_handler(cmd: str) -> Optional[Handler]:
    exp = expandir(cmd)
    tokens = exp.split()
    for keywords, handler in ROUTES:
        if all(kw in tokens for kw in keywords):
            return handler
    return None


# Ponto de entrada: checa clima, handlers estáticos ou devolve pra IA tratar
async def processar_diretriz(texto: str) -> Optional[str]:
    cmd = normalizar(texto)
    from tasks import weather as wx

    if wx.menciona_clima(cmd):
        cidade = wx.extrair_cidade_do_utterance(texto)
        if "amanh" in cmd:
            return wx.verificar_chuva_amanha(cidade)
        return wx.obter_previsao_hoje(cidade)

    handler = buscar_handler(cmd)
    if handler is None:
        return None

    try:
        return await handler(cmd)
    except Exception as e:
        return f"Erro na diretriz: {e}"
