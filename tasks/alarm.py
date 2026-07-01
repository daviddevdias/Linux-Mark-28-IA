import json, threading, time
import re
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pygame

    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

DB_ALARMES = Path(__file__).resolve().parent.parent / "api" / "alarme.json"


class AlarmManager:
    def __init__(self):
        self.lock, self.alarme_ativo, self.falar_callback, self.alarm_loop_ativo = (
            threading.Lock(),
            False,
            None,
            None,
        )
        self.sound_alarme, self.snooze_minutos = None, 10
        DB_ALARMES.parent.mkdir(parents=True, exist_ok=True)

    def registrar_callbacks(self, fn, loop):
        self.falar_callback, self.alarm_loop_ativo = fn, loop
        threading.Thread(target=self.checagem_temporizador_loop, daemon=True, name="Alarmes").start()

    def _carregar_alarmes(self):
        if not DB_ALARMES.exists():
            return []
        with self.lock:
            try:
                return json.load(open(DB_ALARMES, "r", encoding="utf-8"))
            except:
                return []

    def _salvar_alarmes(self, alarmes):
        with self.lock:
            json.dump(
                alarmes,
                open(DB_ALARMES, "w", encoding="utf-8"),
                indent=2,
                ensure_ascii=False,
            )

    def limpar_alarmes_concluidos(self):
        a = self._carregar_alarmes()
        at = [x for x in a if x.get("status") != "concluido"]
        if len(at) != len(a):
            self._salvar_alarmes(at)
        return len(a) - len(at)

    def adicionar_alarme(
        self, hora, missao, repetir=False, musica="", data=None, dias_semana=None
    ):
        a = self._carregar_alarmes()
        a.append(
            {
                "hora": hora,
                "missao": missao,
                "status": "pendente",
                "repetir": repetir or bool(dias_semana),
                "musica": musica,
                "criado_em": datetime.now().isoformat(),
                "data": data,
                "dias_semana": dias_semana,
            }
        )
        self._salvar_alarmes(a)
        return "Despertador agendado."

    def remover_alarme(self, hora, missao, data=None):
        a, n, r = self._carregar_alarmes(), [], False
        for x in a:
            if not r and x.get("hora") == hora and x.get("missao") == missao:
                r = True
                continue
            n.append(x)
        self._salvar_alarmes(n)
        return "Removido" if r else "Não encontrado"

    def listar_alarmes(self):
        return [x for x in self._carregar_alarmes() if x.get("status") == "pendente"]

    def snooze_alarme(self):
        n = datetime.now() + timedelta(minutes=self.snooze_minutos)
        self.adicionar_alarme(n.strftime("%H:%M"), "Soneca")
        return f"Soneca para {n.strftime('%H:%M')}"

    def invocar_som_alarme(self):
        if not PYGAME_AVAILABLE:
            return
        try:
            pygame.mixer.init()
            self.sound_alarme = pygame.mixer.Sound("assets/despertar.wav")
            self.sound_alarme.play(-1)
            while self.alarme_ativo:
                time.sleep(0.3)
            pygame.mixer.stop()
        except:
            pass

    def parar_alarme_total(self):
        self.alarme_ativo = False
        try:
            pygame.mixer.stop()
        except:
            pass
        return "Encerrado."

    def deflagrar_rotina_alarme(self, alarme):
        self.alarme_ativo = True
        threading.Thread(target=self.invocar_som_alarme, daemon=True).start()

    def checagem_temporizador_loop(self):
        while True:
            h = datetime.now().strftime("%H:%M")
            alarmes = self._carregar_alarmes()
            alterado = False
            for a in alarmes:
                if a.get("status") == "pendente" and a.get("hora") == h:
                    threading.Thread(
                        target=self.deflagrar_rotina_alarme, args=(a,), daemon=True
                    ).start()
                    a["status"] = "concluido"
                    alterado = True
            if alterado:
                self._salvar_alarmes(alarmes)
            time.sleep(1)


gerenciador_alarmes = AlarmManager()


def adicionar_alarme(hora, missao="Lembrete", repetir=False, musica="", data=None, dias_semana=None):
    return gerenciador_alarmes.adicionar_alarme(
        hora=hora,
        missao=missao,
        repetir=repetir,
        musica=musica,
        data=data,
        dias_semana=dias_semana,
    )


def listar_alarmes():
    return gerenciador_alarmes.listar_alarmes()


def remover_alarme(hora, missao="", data=None):
    return gerenciador_alarmes.remover_alarme(hora, missao, data=data)


def carregar_alarmes():
    return gerenciador_alarmes._carregar_alarmes()


def parar_alarme_total():
    return gerenciador_alarmes.parar_alarme_total()


def parse_alarme_voz(cmd: str):
    texto = (cmd or "").lower()
    data_iso = None
    hora = None
    m_hora = re.search(r"(\d{1,2})\s*[:h]\s*(\d{2})", texto)
    if m_hora:
        hora = f"{int(m_hora.group(1)):02d}:{int(m_hora.group(2)):02d}"
    m_data = re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", texto)
    if m_data:
        ano = int(m_data.group(3) or datetime.now().year)
        if ano < 100:
            ano += 2000
        data_iso = f"{ano:04d}-{int(m_data.group(2)):02d}-{int(m_data.group(1)):02d}"
    missao = re.sub(r"\b(criar|agendar|alarme|despertar|para|as|às|hoje|amanha|amanhã)\b", " ", texto)
    missao = re.sub(r"\d{1,2}\s*[:h]\s*\d{2}", " ", missao)
    missao = re.sub(r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?", " ", missao)
    missao = re.sub(r"\s+", " ", missao).strip() or "Alarme agendado"
    return data_iso, hora, missao, None
