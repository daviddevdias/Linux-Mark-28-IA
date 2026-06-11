import subprocess, shutil, psutil

APP_ALIASES = {
    "whatsapp": "whatsapp-desktop",
    "chrome": "google-chrome",
    "google": "google-chrome",
    "firefox": "firefox",
    "spotify": "spotify",
    "vscode": "code",
    "discord": "discord",
    "telegram": "telegram-desktop",
    "instagram": "xdg-open https://instagram.com",
    "tiktok": "xdg-open https://tiktok.com",
    "notepad": "gedit",
    "calculator": "gnome-calculator",
    "terminal": "gnome-terminal",
    "cmd": "bash",
    "explorer": "nautilus",
    "paint": "gimp",
    "word": "libreoffice --writer",
    "excel": "libreoffice --calc",
    "powerpoint": "libreoffice --impress",
    "vlc": "vlc",
    "zoom": "zoom",
    "slack": "slack",
    "steam": "steam",
    "task manager": "gnome-system-monitor",
    "settings": "gnome-control-center",
    "edge": "microsoft-edge",
    "brave": "brave-browser",
    "postman": "postman",
    "figma": "xdg-open https://figma.com",
}


def verificar_processo(app: str) -> bool:
    tgt = app.lower().replace(".exe", "")
    for p in psutil.process_iter(["name"]):
        try:
            if tgt in p.info["name"].lower():
                return True
        except:
            pass
    return False


def padronizar(raw: str):
    k = raw.lower().strip()
    if k in APP_ALIASES:
        return APP_ALIASES[k]
    for a, cmd in APP_ALIASES.items():
        if a in k or k in a:
            return cmd
    return raw


def disparar(app: str) -> bool:
    p = app.split()
    if p[0] in ("xdg-open", "libreoffice"):
        try:
            subprocess.Popen(p, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except:
            return False
    bin = shutil.which(p[0]) or shutil.which(p[0].lower())
    if bin:
        try:
            subprocess.Popen(
                [bin] + p[1:], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True
        except:
            pass
    try:
        subprocess.Popen(
            ["xdg-open", app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True
    except:
        return False


def open_app(params=None, **kwargs):
    app = (params or {}).get("app_name", "").strip()
    if not app:
        return "Qual aplicativo?"
    if verificar_processo(app):
        return f"{app} já está ativo."
    norm = padronizar(app)
    s = disparar(norm)
    if not s and norm != app:
        s = disparar(app)
    return f"{app} iniciado." if s else f"Atalho não localizado."
