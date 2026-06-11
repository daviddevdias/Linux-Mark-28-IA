from __future__ import annotations
import os, sys, faulthandler, asyncio, logging, threading
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
import config
from painel import PainelCore, set_loop
from audio.voz import ouvir_comando, falar
from engine.core import processar_comando, inicializar_ia
from engine.controller import get_shutdown_event
from storage.memory_bridge import sincronizar_config
from tasks.monitor import iniciar_sentinela, registrar_falar, registrar_loop_monitor_voz
from tasks.alarm import gerenciador_alarmes
from app_ul.interface import JarvisUI
from storage.wake import processar_wake, resposta_ativacao_aleatoria
from integrations.telegram_bridge_auth_patch import iniciar_telegram

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --log-level=3"

faulthandler.enable()
os.environ.update(
    {
        "PYGAME_HIDE_SUPPORT_PROMPT": "1",
        "QT_LOGGING_RULES": "qt.qpa.window=false",
        "QTWEBENGINE_CHROMIUM_FLAGS": "--disable-logging --disable-gpu --no-sandbox --disable-software-rasterizer --disable-dev-shm-usage --log-level=3",
    }
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jarvis")
for mod in ["httpx", "httpcore", "telegram", "urllib3"]:
    logging.getLogger(mod).setLevel(logging.WARNING)

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)


async def executar(cmd: str):
    await processar_comando(cmd)


async def engine_loop(ui: PainelCore):
    await inicializar_ia()
    iniciar_sentinela()
    sincronizar_config()
    try:
        from brain.event_bus import bus
        from brain.watchdog import watchdog, registrar_modulos_padrao

        bus.registrar_loop(asyncio.get_running_loop())
        registrar_modulos_padrao()
        watchdog.iniciar()
    except Exception as e:
        log.warning(f"Watchdog indisponível: {e}")
    try:
        from storage.observability import registrar_acao, purgar_antigos

        purgar_antigos(dias=7)
        registrar_acao("startup", modulo="main", descricao="inicializado", sucesso=True)
    except:
        pass

    threading.Thread(target=iniciar_telegram, daemon=True, name="telegram").start()
    shutdown = get_shutdown_event()

    while not shutdown.is_set():
        try:
            config.recarregar_identidade_painel()
            audio = await ouvir_comando()
            if not isinstance(audio, str) or not audio:
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
    registrar_loop_monitor_voz(loop)
    try:
        loop.run_until_complete(engine_loop(ui))
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
