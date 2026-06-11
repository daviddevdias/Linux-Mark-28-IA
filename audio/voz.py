import asyncio, os, queue, threading, time, tempfile, re
import edge_tts, pygame, speech_recognition as sr, sounddevice as sd, numpy as np, scipy.io.wavfile as wav
import config

audio_io_lock, mic_lock = threading.RLock(), threading.Lock()
mic_cmd, mic_rpy = queue.Queue(), queue.Queue()
mic_thread, sleep_event = None, threading.Event()
falando, interrompido = False, False
barge_stop_event, barge_thread = threading.Event(), None
_device_cache, _device_lock = None, threading.Lock()


def _encontrar_device_valido():
    global _device_cache
    with _device_lock:
        if _device_cache is not None:
            return _device_cache
        idx_config = getattr(config, "DEVICE_INDEX", None)
        candidatos = [idx_config] if idx_config is not None else []
        if None not in candidatos:
            candidatos.append(None)
        for idx in candidatos:
            try:
                info = (
                    sd.query_devices(idx, "input")
                    if idx is not None
                    else sd.query_devices(kind="input")
                )
                max_ch = int(info.get("max_input_channels", 0))
                if max_ch < 1:
                    continue
                channels = min(1, max_ch)
                sd.rec(
                    int(0.1 * 16000),
                    samplerate=16000,
                    channels=channels,
                    dtype="int16",
                    device=idx,
                )
                sd.wait()
                _device_cache = (idx, channels)
                return _device_cache
            except:
                continue
        _device_cache = (None, 1)
        return _device_cache


def criar_reconhecedor():
    r = sr.Recognizer()
    r.pause_threshold, r.dynamic_energy_threshold = 0.55, False
    return r


reconhecedor = criar_reconhecedor()
_whisper_model, _whisper_lock = None, threading.Lock()


def get_whisper_model():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    with _whisper_lock:
        if _whisper_model is not None:
            return _whisper_model
        try:
            from faster_whisper import WhisperModel

            _whisper_model = WhisperModel(
                getattr(config, "WHISPER_MODEL", "small"),
                device="cpu",
                compute_type="int8",
            )
            return _whisper_model
        except:
            return None


def limpar_texto_stt(texto: str) -> str:
    return re.sub(
        r"\s+", " ", re.sub(r"[^\w\s]", " ", (texto or "").lower().strip())
    ).strip()


def ui_falar(on, vol=1.0):
    try:
        config.notificar_voz_painel(on, vol)
    except:
        pass


def reproduzir_sync(arquivo):
    global falando, interrompido
    with audio_io_lock:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(arquivo)
        pygame.mixer.music.play()
        falando, interrompido = True, False
        sleep_event.clear()
        iniciar_barge_in()
        while pygame.mixer.music.get_busy():
            if interrompido:
                break
            sleep_event.wait(0.1)
        pygame.mixer.music.stop()
    parar_barge_in()
    falando = False
    ui_falar(False)


async def falar(texto):
    if not texto.strip():
        return
    arquivo = os.path.join(config.ASSETS_DIR, "output.mp3")
    try:
        if os.path.exists(arquivo):
            pygame.mixer.music.unload()
            os.remove(arquivo)
    except:
        pass
    try:
        await edge_tts.Communicate(texto, config.voz_atual).save(arquivo)
    except:
        return
    await asyncio.get_running_loop().run_in_executor(None, reproduzir_sync, arquivo)


def reconhecer_google(audio):
    return reconhecedor.recognize_google(audio, language="pt-BR")


def reconhecer_whisper_file(path):
    model = get_whisper_model()
    if not model:
        return ""
    segments, _ = model.transcribe(path, language="pt", vad_filter=True)
    return " ".join(seg.text for seg in segments).strip()


def captura_sync():
    device_idx, channels = _encontrar_device_valido()
    try:
        fs, duration = 16000, 8
        audio = sd.rec(
            int(duration * fs),
            samplerate=fs,
            channels=channels,
            dtype="int16",
            device=device_idx,
        )
        sd.wait()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        if channels > 1:
            audio = audio[:, 0:1]
        wav.write(tmp.name, fs, audio)
        try:
            with sr.AudioFile(tmp.name) as source:
                audio_data = reconhecedor.record(source)
            texto = reconhecer_google(audio_data)
        except:
            texto = ""
        if not texto:
            texto = reconhecer_whisper_file(tmp.name)
        try:
            os.remove(tmp.name)
        except:
            pass
        return limpar_texto_stt(texto)
    except:
        global _device_cache
        with _device_lock:
            _device_cache = None
        return ""


def interromper_voz():
    global interrompido
    interrompido = True
    ui_falar(False)
    sleep_event.set()
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except:
        pass


def barge_loop():
    try:
        fs, duration = 16000, 1.2
        device_idx, channels = _encontrar_device_valido()
        while not barge_stop_event.is_set():
            if not falando or interrompido:
                break
            try:
                audio = sd.rec(
                    int(duration * fs),
                    samplerate=fs,
                    channels=channels,
                    dtype="int16",
                    device=device_idx,
                )
                sd.wait()
            except:
                break
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            if channels > 1:
                audio = audio[:, 0:1]
            wav.write(tmp.name, fs, audio)
            try:
                with sr.AudioFile(tmp.name) as source:
                    audio_data = reconhecedor.record(source)
                txt = reconhecer_google(audio_data)
            except:
                txt = ""
            txt = limpar_texto_stt(txt)
            try:
                os.remove(tmp.name)
            except:
                pass
            if txt:
                interromper_voz()
                break
    except:
        pass


def iniciar_barge_in():
    global barge_thread
    barge_stop_event.clear()
    if barge_thread and barge_thread.is_alive():
        return
    barge_thread = threading.Thread(target=barge_loop, daemon=True)
    barge_thread.start()


def parar_barge_in():
    barge_stop_event.set()


def run_mic_loop():
    while True:
        try:
            mic_cmd.get()
            mic_rpy.put(captura_sync())
        except:
            time.sleep(1)


def ensure_mic_thread():
    global mic_thread
    if mic_thread and mic_thread.is_alive():
        return
    mic_thread = threading.Thread(target=run_mic_loop, daemon=True)
    mic_thread.start()


def ouvir_sync():
    ensure_mic_thread()
    mic_cmd.put(True)
    try:
        return mic_rpy.get(timeout=40)
    except:
        return ""


async def ouvir_comando():
    loop = asyncio.get_running_loop()
    if loop.is_closed() or not loop.is_running():
        return ""
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, ouvir_sync), timeout=45
        )
    except:
        return ""
