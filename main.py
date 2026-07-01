from __future__ import annotations
import os, sys, faulthandler, asyncio, logging, threading
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
import config
from painel import PainelCore, set_loop
from audio.voz import ouvir_comando, falar
from engine.controller import processar_comando, get_shutdown_event
from tasks.alarm import gerenciador_alarmes
from tasks.monitor import registrar_falar, registrar_loop_monitor_voz
from app_ul.interface import JarvisUI
from tasks.wake import processar_wake, resposta_ativacao_aleatoria
from integrations.telegram_bridge_auth_patch import iniciar_telegram

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --log-level=3"

faulthandler.enable()
os.environ.update({
    "PYGAME_HIDE_SUPPORT_PROMPT": "1",
    "QT_LOGGING_RULES": "qt.qpa.window=false",
    "QTWEBENGINE_CHROMIUM_FLAGS": "--disable-logging --disable-gpu --no-sandbox --disable-software-rasterizer --disable-dev-shm-usage --log-level=3",
})

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jarvis")
for mod in ["httpx", "httpcore", "telegram", "urllib3"]:
    logging.getLogger(mod).setLevel(logging.WARNING)

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)


async def executar(cmd: str):
    await processar_comando(cmd)


async def main_loop(ui: PainelCore):
    try:
        threading.Thread(target=iniciar_telegram, daemon=True, name="telegram").start()
    except Exception as e:
        log.warning(f"Telegram não inicializado: {e}")

    shutdown = get_shutdown_event()
    while not shutdown.is_set():
        try:
            config.recarregar_identidade_painel()
            audio = await ouvir_comando()
            if not isinstance(audio, str) or not audio:
                await asyncio.sleep(0.1)
                continue
            ativo, cmd = processar_wake(audio)
            if not ativo:
                continue
            if not cmd:
                await falar(resposta_ativacao_aleatoria())
                continue
            await executar(cmd.strip())
        except Exception:
            log.exception("Erro no loop principal")
            await asyncio.sleep(0.3)


def engine_thread(ui: PainelCore):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    set_loop(loop)
    try:
        gerenciador_alarmes.registrar_callbacks(falar, loop)
    except Exception as e:
        log.warning(f"Aviso ao registrar alarmes: {e}")
    try:
        registrar_loop_monitor_voz(loop)
    except Exception as e:
        log.warning(f"Aviso ao registrar monitor de voz: {e}")
    try:
        loop.run_until_complete(main_loop(ui))
    except Exception as e:
        log.exception(f"Erro no engine thread: {e}")
    finally:
        loop.close()


def iniciar_sistema():
    ui = PainelCore()
    hud = JarvisUI()
    hud.btn_code.clicked.connect(lambda: (ui.show(), ui.raise_(), ui.activateWindow()))
    hud.show()
    registrar_falar(falar)
    threading.Thread(target=engine_thread, args=(ui,), daemon=True, name="core").start()
    sys.exit(app.exec())


if __name__ == "__main__":
    iniciar_sistema()
