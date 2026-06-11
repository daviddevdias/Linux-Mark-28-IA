import os, subprocess, shutil


def executar_linux(cmd: str):
    try:
        subprocess.run(
            cmd,
            shell=True,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except:
        pass


def mutar_volume():
    executar_linux("pactl set-sink-mute @DEFAULT_SINK@ toggle")


def definir_volume(nivel: int):
    executar_linux(f"pactl set-sink-volume @DEFAULT_SINK@ {nivel}%")


def bloquear_tela():
    executar_linux("loginctl lock-session")


def minimizar_janelas():
    executar_linux("xdotool key super+d")


def fechar_janela_ativa():
    executar_linux("xdotool key alt+f4")


def print_tela():
    if shutil.which("gnome-screenshot"):
        executar_linux("gnome-screenshot")
    elif shutil.which("grim"):
        executar_linux("grim ~/Pictures/screenshot_$(date +%s).png")


def limpar_lixeira():
    executar_linux("rm -rf ~/.local/share/Trash/files/* ~/.local/share/Trash/info/*")


def computer_settings(args: dict):
    acao = args.get("action", "")
    if acao == "fechar":
        fechar_janela_ativa()
    elif acao == "minimizar_tudo":
        minimizar_janelas()
    elif acao == "print":
        print_tela()
    elif acao == "bloqueio":
        bloquear_tela()
    elif acao == "limpar":
        limpar_lixeira()
    elif acao == "volume":
        definir_volume(args.get("nivel", 50))
    elif acao == "type":
        texto = args.get("text", "")
        if texto:
            executar_linux(f'xdotool type "{texto}"')
    elif acao == "hotkey":
        keys = args.get("keys", "")
        if keys:
            executar_linux(f"xdotool key {keys}")
