import asyncio
import json
from pathlib import Path
import config
import psutil
from PyQt6.QtCore import QObject, QTimer, QUrl, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow

# ===== GLOBAL STATE =====
main_async_loop = None

# ===== CONSTANTES =====
CONFIG_CORE_FILE = "config_core.json"
SMART_FILE = "config_smart.json"
NOTAS_FILE = "notas.json"

CAMPOS_CONFIG_CORE = {
    "qwen", "gemini", "current_model",
    "spotify_id", "spotify_sec",
    "smartthings", "smartthings_tv_id",
    "telegram_token", "telegram_auth_token", "telegram_allowed_ids",
    "openweather_api_key", "deepgram_api_key", "whisper_model",
    "nome_mestre", "voz", "voz_atual", "device_index",
    "tema_ativo", "notas", "cidade_padrao",
}


def set_loop(loop):
    """Define o event loop global para operações assíncronas"""
    global main_async_loop
    main_async_loop = loop


def resolver_arquivo(chave: str) -> str:
    """Retorna o arquivo JSON onde a chave está armazenada"""
    if chave == "notas":
        return NOTAS_FILE
    if chave in CAMPOS_CONFIG_CORE:
        return CONFIG_CORE_FILE
    return SMART_FILE


def limpar_prefixo(cmd: str) -> str:
    """Remove prefixos 'core:' ou 'core' de um comando"""
    c = cmd.strip().lower()
    for prefixo in ("core,", "core"):
        if c.startswith(prefixo):
            c = c[len(prefixo):].strip()
    return c


def montar_biblioteca_comandos() -> list[dict]:
    """Monta a biblioteca de comandos disponíveis"""
    biblioteca = []
    
    try:
        from engine.controller import ROUTES
        visto = set()
        
        for keywords, handler in ROUTES:
            chave = "|".join(keywords)
            if chave in visto:
                continue
            visto.add(chave)
            
            biblioteca.append({
                "cmd": " ".join(keywords).strip().upper(),
                "cat": "VOZ",
                "desc": f"Reconhecimento: «{' '.join(keywords)}».",
                "passos": list(keywords),
                "handler": getattr(handler, "__name__", ""),
                "icon": "◈",
                "poder": "⚡",
            })
    except Exception as e:
        print(f"Erro ao carregar ROUTES: {e}")
    
    try:
        from engine.tools import TOOL_DECLARATIONS
        
        for t in TOOL_DECLARATIONS or []:
            nome = (t.get("function", {}).get("name") or "").strip()
            if not nome:
                continue
            
            params = t.get("function", {}).get("parameters", {}).get("properties", {})
            passos = [
                f"{k} ({v.get('type')})" if isinstance(v, dict) and v.get("type") else k
                for k, v in params.items()
            ]
            
            biblioteca.append({
                "cmd": f"TOOL: {nome}",
                "cat": "FERRAMENTAS",
                "desc": t.get("function", {}).get("description", "Ação Jarvis."),
                "passos": passos[:10],
                "handler": nome,
                "icon": "⚙",
                "poder": "◆",
            })
    except Exception as e:
        print(f"Erro ao carregar TOOL_DECLARATIONS: {e}")
    
    # Adiciona confirmações
    biblioteca.extend([
        {
            "cmd": "CONFIRMAR AJUDA",
            "cat": "CONFIRMAÇÃO",
            "desc": "Confirmação longa.",
            "passos": ["pedido aceito"],
            "handler": "confirm",
            "icon": "✓",
            "poder": "◆",
        },
        {
            "cmd": "NEGAR AJUDA",
            "cat": "CONFIRMAÇÃO",
            "desc": "Recusa longa.",
            "passos": ["negar"],
            "handler": "deny",
            "icon": "✗",
            "poder": "◆",
        }
    ])
    
    return biblioteca


async def run_test_voice():
    """Testa a voz (função auxiliar)"""
    from audio.voz import falar
    await falar("Painel JARVIS operacional.")


class JarvisBridge(QObject):
    """Bridge entre interface Qt e engine Jarvis"""
    
    dados_para_ui = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.cpu_atual = 0.0
        self.ram_atual = 0.0
        self.window_ref = None
    
    def bind_window(self, w: QMainWindow):
        """Vincula a janela principal"""
        self.window_ref = w
    
    @pyqtSlot()
    def ocultar_painel(self):
        """Oculta o painel"""
        if self.window_ref:
            self.window_ref.hide()
    
    @pyqtSlot(str)
    def executar_comando(self, cmd: str):
        """Executa comando da UI"""
        global main_async_loop
        
        diretriz = limpar_prefixo(cmd)
        
        if main_async_loop and not main_async_loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self.executar_e_emitir(diretriz),
                main_async_loop
            )
    
    async def executar_e_emitir(self, diretriz: str):
        """Executa comando e emite sinal com resposta"""
        try:
            from engine.core import processar_comando
            
            texto = await processar_comando(diretriz)
            if texto:
                self.dados_para_ui.emit(json.dumps({"resposta": texto}))
        except Exception as e:
            self.dados_para_ui.emit(json.dumps({"erro": str(e)}))
    
    @pyqtSlot(str, result=str)
    def alternar_ia(self, modo: str) -> str:
        """Alterna modelo de IA"""
        from engine.ia_router import router
        
        msg = router.definir_modo(modo)
        self.dados_para_ui.emit(
            json.dumps({"resposta": msg, "ia_status": router.status})
        )
        return json.dumps({"status": "ok"})
    
    @pyqtSlot(result=str)
    def obter_comandos(self) -> str:
        """Retorna biblioteca de comandos em JSON"""
        try:
            cmds = montar_biblioteca_comandos()
            return json.dumps(cmds)
        except Exception as e:
            return json.dumps({"erro": str(e)})


class PainelCore(QMainWindow):
    """Painel principal da UI"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jarvis Control Panel")
        self.bridge = JarvisBridge()
        self.bridge.bind_window(self)
        
        # Setup WebEngine para HTML/JavaScript
        self.web = QWebEngineView()
        self.setCentralWidget(self.web)
        
        # Setup WebChannel para comunicação
        channel = QWebChannel()
        channel.registerObject("bridge", self.bridge)
        self.web.page().setWebChannel(channel)
        
        # Timer para atualizar stats
        self.timer_stats = QTimer()
        self.timer_stats.timeout.connect(self.atualizar_stats)
        self.timer_stats.start(1000)
    
    def atualizar_stats(self):
        """Atualiza estatísticas do sistema"""
        self.bridge.cpu_atual = psutil.cpu_percent(interval=0.1)
        self.bridge.ram_atual = psutil.virtual_memory().percent
