from __future__ import annotations
import asyncio, webbrowser, subprocess, os, json, urllib.parse, shutil, pathlib, threading
from typing import Any, Callable
from tasks.spotify_manager import spotify_stark
from tasks.open_app import open_app
from tasks.weather import obter_previsao_hoje, verificar_chuva_amanha
from tasks.alarm import adicionar_alarme, listar_alarmes, remover_alarme
from tasks.computer_control import computer_settings
from storage.memory_manager import load_memory, update_memory
from engine.cmd_security import avaliar, executar, audit_recente

log = __import__("logging").getLogger("jarvis.tools_mapper")


def executar_no_loop_atual(coro) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    if getattr(loop, "_thread_id", None) == threading.get_ident():
        raise RuntimeError("executar_no_loop_atual() na mesma thread. Use async.")
    return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=30)


def gerenciador_open_app(argumentos: dict):
    open_app(argumentos)
    return f"Inicializando {argumentos.get('app_name', 'app')}."


def gerenciador_computador(argumentos: dict):
    computer_settings(argumentos)
    return "Configurações de hardware atualizadas."


def gerenciador_cmd(argumentos: dict):
    comando = argumentos.get("command", "").strip()
    if not comando and argumentos.get("task", "").strip():
        from engine.ia_router import router

        try:
            comando = (
                executar_no_loop_atual(
                    router.responder(
                        f"Gere APENAS o comando de terminal para: {argumentos['task']}. Responda somente com o comando puro."
                    )
                )
                .strip()
                .strip("`")
                .strip()
            )
        except Exception as e:
            return f"Erro crítico: {e}"
    if not comando:
        return "Comando nulo."
    av = avaliar(comando)
    return (
        f"Bloqueado: {av.motivo}"
        if not av.permitido
        else f"Executado. Saída: {executar(comando, timeout=20, ferramenta='cmd_control')}"
    )


def gerenciador_web_search(argumentos: dict):
    q = argumentos.get("query", "").strip()
    if q:
        webbrowser.open(
            f"[https://www.google.com/search?q=](https://www.google.com/search?q=){urllib.parse.quote(q)}"
        )
    return f"Pesquisa enviada para o navegador." if q else "Falha: termo inválido."


def gerenciador_browser(argumentos: dict):
    acao, url, q = (
        argumentos.get("action", "open").lower(),
        argumentos.get("url", "").strip(),
        argumentos.get("query", "").strip(),
    )
    if acao == "open" and url:
        webbrowser.open(url)
        return f"Acessando {url}."
    if acao in ("search", "open") and q:
        webbrowser.open(
            f"[https://www.google.com/search?q=](https://www.google.com/search?q=){urllib.parse.quote(q)}"
        )
        return f"Buscando '{q}'."
    if url:
        webbrowser.open(url)
        return f"Direcionando para {url}."
    return "Falha nos parâmetros web."


def gerenciador_youtube(argumentos: dict):
    q = argumentos.get("query", "").strip()
    webbrowser.open(
        f"[https://www.youtube.com/results?search_query=](https://www.youtube.com/results?search_query=){urllib.parse.quote(q)}"
        if q
        else "[https://www.youtube.com](https://www.youtube.com)"
    )
    return f"Buscando '{q}' no YouTube." if q else "Acessando YouTube."


def gerenciador_spotify(argumentos: dict):
    if argumentos.get("playlist_name"):
        spotify_stark.listar_e_tocar_playlist(argumentos["playlist_name"])
        return "Reproduzindo playlist."
    if argumentos.get("search_query"):
        spotify_stark.abrir_e_buscar(argumentos["search_query"])
        return "Localizando faixa."
    spotify_stark.controlar_reproducao(argumentos.get("action", "playpause").lower())
    return "Spotify controlado."


def gerenciador_clima(argumentos: dict):
    cidade, prev = (
        argumentos.get("city", ""),
        argumentos.get("forecast", "hoje").lower(),
    )
    return (
        f"Clima amanhã: {verificar_chuva_amanha(cidade)}"
        if prev == "amanha"
        else f"Clima atual: {obter_previsao_hoje(cidade)}"
    )


def gerenciador_alarme(argumentos: dict):
    op = argumentos.get("op", "add").lower()
    if op == "list":
        return (
            "Alarmes ativos:\n"
            + "\n".join(f"• {i['hora']} — {i['missao']}" for i in listar_alarmes())
            if isinstance(listar_alarmes(), list)
            else str(listar_alarmes())
        )
    if op == "remove":
        remover_alarme(argumentos.get("hora", ""), argumentos.get("missao", ""))
        return "Alarme removido."
    h = argumentos.get("hora", "")
    if not h:
        return "Impossível criar sem horário."
    adicionar_alarme(
        h,
        argumentos.get("missao", "Lembrete"),
        data=(
            argumentos.get("data") if str(argumentos.get("data", "")).strip() else None
        ),
    )
    return f"Alarme para {h}."


def gerenciador_casa_inteligente(argumentos: dict):
    from tasks.smart_home import (
        abrir_youtube_tv,
        buscar_id_tv,
        energia_tv,
        diagnosticar_falha_tv,
        status_tv,
    )

    acao = argumentos.get("action", "").lower()
    if "tv" in argumentos.get("device", "").lower():
        if acao in ("youtube", "abrir_youtube", "app_youtube"):
            abrir_youtube_tv()
            return "Abrindo YouTube na TV."
        if acao == "on":
            return (
                "TV ligada."
                if energia_tv(True)
                else (
                    diagnosticar_falha_tv() if not buscar_id_tv() else "Falha ao ligar."
                )
            )
        if acao == "off":
            return (
                "TV desligada."
                if energia_tv(False)
                else (
                    diagnosticar_falha_tv()
                    if not buscar_id_tv()
                    else "Falha ao desligar."
                )
            )
        if acao == "status":
            return status_tv()
    return "Comando de automação ignorado."


def gerenciador_arquivos(argumentos: dict):
    acao, caminho, nome, conteudo, permanente = (
        argumentos.get("action", ""),
        argumentos.get("path", ""),
        argumentos.get("name", ""),
        argumentos.get("content", ""),
        argumentos.get("permanent", False),
    )
    atalhos = {
        "desktop": os.path.join(os.path.expanduser("~"), "Desktop"),
        "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
        "documentos": os.path.join(os.path.expanduser("~"), "Documents"),
        "home": os.path.expanduser("~"),
    }
    cam_resolvido = (
        atalhos.get(caminho.lower(), caminho) if caminho else os.path.expanduser("~")
    )
    alvo = os.path.join(cam_resolvido, nome) if nome else cam_resolvido
    try:
        if acao == "list":
            return "Itens: " + ", ".join(os.listdir(cam_resolvido)[:30])
        if acao == "create_file":
            pathlib.Path(alvo).write_text(conteudo, encoding="utf-8")
            return "Arquivo criado."
        if acao == "create_folder":
            os.makedirs(alvo, exist_ok=True)
            return "Pasta criada."
        if acao == "read":
            return pathlib.Path(alvo).read_text(encoding="utf-8", errors="replace")[
                :1000
            ]
        if acao == "delete":
            lixo = os.path.join(
                os.path.expanduser("~"), ".local", "share", "Trash", "files"
            )
            os.makedirs(lixo, exist_ok=True)
            if os.path.isdir(alvo):
                (
                    shutil.rmtree(alvo)
                    if permanente
                    else shutil.move(alvo, os.path.join(lixo, nome or "pasta"))
                )
            else:
                (
                    os.remove(alvo)
                    if permanente
                    else shutil.move(alvo, os.path.join(lixo, nome or "arquivo"))
                )
            return "Removido."
        if acao == "disk":
            return f"Disco: {shutil.disk_usage('/')[2] // (1024**3)} GB livres."
        return "Ação FS não reconhecida."
    except Exception as e:
        return f"Erro FS: {e}"


def gerenciador_memoria(argumentos: dict):
    return (
        "Dados gravados."
        if isinstance(
            update_memory(
                {
                    argumentos.get("category"): {
                        argumentos.get("key"): argumentos.get("value")
                    }
                }
            ),
            dict,
        )
        else "Falha na memória."
    )


def gerenciador_plano(argumentos: dict):
    from engine.ia_router import router

    obj = argumentos.get("goal", "").strip()
    if not obj:
        return "Objetivo vazio."
    return executar_no_loop_atual(
        router.responder(
            f"Crie um plano estruturado para: {obj}. Contexto extra: {argumentos.get('context', '')}"
        )
    )


def gerenciador_codigo(argumentos: dict):
    from engine.ia_router import router

    if not argumentos.get("description", ""):
        return "Impossível programar sem descrição."
    lang = argumentos.get("language", "python")
    cod = executar_no_loop_atual(
        router.responder(
            f"Gere APENAS código {lang}: {argumentos['description']}. {argumentos.get('code', '')}"
        )
    )
    if argumentos.get("execute", False) and cod:
        import shlex, re

        bt = "`" * 3
        match = re.search(rf"{bt}(?:\w+)?\n([\s\S]+?){bt}", cod)
        cmd = (
            f"python -c {shlex.quote(match.group(1).strip() if match else cod.strip())}"
            if lang == "python"
            else f"bash -c {shlex.quote(match.group(1).strip() if match else cod.strip())}"
        )
        av = avaliar(cmd)
        if not av.permitido:
            return f"Bloqueado: {av.motivo}"
        executar(cmd, timeout=15, ferramenta="code_helper")
        return "Código executado."
    return cod or "Falha gerando código."


def gerenciador_visao(argumentos: dict):
    from vision.capture import analisar_tela

    executar_no_loop_atual(
        analisar_tela(argumentos.get("question", "Descreva o ecrã."))
    )
    return "Análise ativada."


def gerenciador_troca_ia(argumentos: dict):
    from engine.ia_router import router

    router.definir_modo(argumentos.get("mode", "ollama").lower())
    return "IA alternada."


def gerenciador_agente_visual(argumentos: dict):
    return "Agente S necessita adaptação modular no Linux."


def gerenciador_visao_3d(argumentos: dict):
    try:
        from vision.capture import MotorVisaoEspacial
        import cv2

        motor, cap = MotorVisaoEspacial(), cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return "Câmera inacessível."
        res = motor.analisar_medida_cena(frame)
        return (
            f"Mapeamento OK. Escala: {res['pixels_por_cm']} px/cm."
            if res["status"] == "sucesso"
            else f"Erro 3D: {res['motivo']}"
        )
    except Exception as e:
        return f"Falha 3D: {e}"


def gerenciador_traducao_audio(argumentos: dict):
    return f"Escutando para traduzir ({argumentos.get('segundos', 10)}s)."


def gerenciador_otimizacao_dados(argumentos: dict):
    try:
        from storage.optimizer import comprimir_banco_auditoria

        executar_no_loop_atual(comprimir_banco_auditoria())
        return "Banco otimizado."
    except Exception as e:
        return f"Falha DB: {e}"


EXECUTOR_FERRAMENTAS = {
    "open_app": gerenciador_open_app,
    "computer_control": gerenciador_computador,
    "cmd_control": gerenciador_cmd,
    "web_search": gerenciador_web_search,
    "browser_control": gerenciador_browser,
    "youtube_video": gerenciador_youtube,
    "spotify_control": gerenciador_spotify,
    "weather_report": gerenciador_clima,
    "set_reminder": gerenciador_alarme,
    "smart_home": gerenciador_casa_inteligente,
    "file_controller": gerenciador_arquivos,
    "save_memory": gerenciador_memoria,
    "agent_task": gerenciador_plano,
    "code_helper": gerenciador_codigo,
    "screen_analysis": gerenciador_visao,
    "switch_ia_mode": gerenciador_troca_ia,
    "visual_gui_actuator": gerenciador_agente_visual,
    "medir_ambiente_3d": gerenciador_visao_3d,
    "traduzir_audio_ambiente": gerenciador_traducao_audio,
    "otimizar_banco_dados": gerenciador_otimizacao_dados,
}


async def despachar(nome: str, args: dict):
    func = EXECUTOR_FERRAMENTAS.get(nome)
    if not func:
        return f"Falha: Ferramenta '{nome}' inválida."
    try:
        return await asyncio.get_running_loop().run_in_executor(None, func, args)
    except Exception as e:
        return f"Erro na ferramenta {nome}: {e}"
