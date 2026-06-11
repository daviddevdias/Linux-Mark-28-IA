import hashlib, hmac, os, time
from functools import wraps
from typing import Callable

_ALLOWED_IDS: set[int] = set()
_AUTH_TOKEN: str = ""
_PENDING_AUTH: dict[int, float] = {}
_AUTH_TTL = 300


def carregar_config():
    global _ALLOWED_IDS, _AUTH_TOKEN
    ids_raw = os.environ.get("TELEGRAM_ALLOWED_IDS", "")
    if ids_raw:
        for part in ids_raw.split(","):
            if part.strip().isdigit():
                _ALLOWED_IDS.add(int(part.strip()))
    try:
        import config as cfg

        ids_cfg = getattr(cfg, "TELEGRAM_ALLOWED_IDS", [])
        if isinstance(ids_cfg, (list, set, tuple)):
            _ALLOWED_IDS.update(int(i) for i in ids_cfg if str(i).isdigit())
        token = getattr(cfg, "TELEGRAM_AUTH_TOKEN", "") or os.environ.get(
            "TELEGRAM_AUTH_TOKEN", ""
        )
        if token:
            _AUTH_TOKEN = token
    except:
        pass


def adicionar_id_autorizado(chat_id: int):
    _ALLOWED_IDS.add(chat_id)


def e_autorizado(chat_id: int) -> bool:
    return chat_id in _ALLOWED_IDS if _ALLOWED_IDS else False


def verificar_token(token_fornecido: str) -> bool:
    return (
        hmac.compare_digest(
            hashlib.sha256(token_fornecido.encode()).hexdigest(),
            hashlib.sha256(_AUTH_TOKEN.encode()).hexdigest(),
        )
        if _AUTH_TOKEN
        else False
    )


def marcar_pendente_auth(chat_id: int):
    _PENDING_AUTH[chat_id] = time.time()


def esta_pendente_auth(chat_id: int) -> bool:
    ts = _PENDING_AUTH.get(chat_id)
    if ts is None:
        return False
    if time.time() - ts > _AUTH_TTL:
        del _PENDING_AUTH[chat_id]
        return False
    return True


def limpar_pendente(chat_id: int):
    _PENDING_AUTH.pop(chat_id, None)


def requer_autorizacao(fn: Callable) -> Callable:
    @wraps(fn)
    async def wrapper(update, context, *args, **kwargs):
        chat_id = update.effective_chat.id
        if e_autorizado(chat_id):
            return await fn(update, context, *args, **kwargs)
        if esta_pendente_auth(chat_id):
            if verificar_token((update.message.text or "").strip()):
                adicionar_id_autorizado(chat_id)
                limpar_pendente(chat_id)
                await update.message.reply_text("Acesso autorizado.")
                return
            await update.message.reply_text("Token inválido. Tente novamente.")
            return
        marcar_pendente_auth(chat_id)
        await update.message.reply_text(
            "Acesso restrito. Envie o token de autenticação."
        )

    return wrapper


carregar_config()
