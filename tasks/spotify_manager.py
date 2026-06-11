import spotipy
from spotipy.oauth2 import SpotifyOAuth
import config


def cliente():
    try:
        return spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=config.SPOTIFY_ID,
                client_secret=config.SPOTIFY_SECRET,
                redirect_uri=config.SPOTIFY_REDIRECT_URI,
                scope="user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private",
                cache_path=str(config.BASE_DIR / "api" / ".spotify_cache"),
            )
        )
    except:
        return None


sp = cliente()


def tocar_musica(termo):
    if not sp:
        return False
    try:
        i = sp.search(q=termo, type="track", limit=1).get("tracks", {}).get("items", [])
        if not i:
            return False
        sp.start_playback(uris=[i[0]["uri"]])
        return True
    except:
        return False


def tocar_playlist(nome=""):
    if not sp:
        return "Offline"
    try:
        uri, nf = "spotify:collection", "Músicas Curtidas"
        if nome:
            for p in sp.current_user_playlists(limit=50).get("items", []):
                if nome.lower() in p["name"].lower():
                    uri, nf = p["uri"], p["name"]
                    break
        sp.start_playback(context_uri=uri)
        return f"Tocando: {nf}"
    except:
        return "Erro ao tocar"


def controle(acao):
    if not sp:
        return "Offline"
    try:
        a = acao.lower()
        if a in ["next", "proximo"]:
            sp.next_track()
            return "Próxima"
        if a in ["prev", "anterior"]:
            sp.previous_track()
            return "Anterior"
        if a in ["pause", "pausar"]:
            sp.pause_playback()
            return "Pausado"
        if a in ["play", "continuar"]:
            sp.start_playback()
            return "Executando"
        e = sp.current_playback()
        if e and e.get("is_playing"):
            sp.pause_playback()
            return "Pausado"
        sp.start_playback()
        return "Executando"
    except:
        return "Erro"


def buscar(termo):
    return f"Tocando {termo}" if tocar_musica(termo) else "Não encontrado"
