import json
import logging
import re
import threading
import time
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any, Callable

try:
    import pygame

    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# 1. LOGGING PROFISSIONAL: Nunca silenciamos erros. Nós os registramos.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AlarmSystem")

# 2. PATHLIB: Manipulação moderna e segura de caminhos de arquivos.
BASE_DIR = Path(__file__).resolve().parent
DB_ALARMES = BASE_DIR.parent / "api" / "alarme.json"

DIAS_SEMANA = {
    "segunda": 0,
    "segunda-feira": 0,
    "terca": 1,
    "terça": 1,
    "terca-feira": 1,
    "terça-feira": 1,
    "quarta": 2,
    "quarta-feira": 2,
    "quinta": 3,
    "quinta-feira": 3,
    "sexta": 4,
    "sexta-feira": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}

MESES = {
    "janeiro": 1,
    "jan": 1,
    "fevereiro": 2,
    "fev": 2,
    "marco": 3,
    "março": 3,
    "mar": 3,
    "abril": 4,
    "abr": 4,
    "maio": 5,
    "mai": 5,
    "junho": 6,
    "jun": 6,
    "julho": 7,
    "jul": 7,
    "agosto": 8,
    "ago": 8,
    "setembro": 9,
    "set": 9,
    "outubro": 10,
    "out": 10,
    "novembro": 11,
    "nov": 11,
    "dezembro": 12,
    "dez": 12,
}


class AlarmManager:
    """
    3. ENCAPSULAMENTO: Todo o estado do sistema agora vive dentro desta classe.
    Isso elimina a necessidade de variáveis 'global' espalhadas pelo código.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.alarme_ativo: bool = False
        self.falar_callback: Optional[Callable] = None
        self.alarm_loop_ativo = None
        self.ultimo_disparo: Dict[str, str] = {}
        self.canal_alarme = None
        self.sound_alarme = None
        self.snooze_minutos: int = 10

        DB_ALARMES.parent.mkdir(parents=True, exist_ok=True)

    def registrar_callbacks(self, fn: Callable, loop: Any) -> None:
        """Registra dependências externas (Inversão de Controle)."""
        self.falar_callback = fn
        self.alarm_loop_ativo = loop
        logger.info("Callbacks de áudio e loop de eventos registrados com sucesso.")

    def _carregar_alarmes(self) -> List[Dict[str, Any]]:
        """Método privado para leitura do banco (Data Access)."""
        if not DB_ALARMES.exists():
            return []

        with self.lock:
            try:
                with open(DB_ALARMES, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao decodificar JSON do banco de alarmes: {e}")
                return []
            except Exception as e:
                logger.error(f"Erro inesperado ao ler alarmes: {e}", exc_info=True)
                return []

    def _salvar_alarmes(self, alarmes: List[Dict[str, Any]]) -> None:
        """Método privado para escrita no banco (Data Access)."""
        with self.lock:
            try:
                with open(DB_ALARMES, "w", encoding="utf-8") as f:
                    json.dump(alarmes, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Erro ao salvar alarmes no banco: {e}", exc_info=True)

    def limpar_alarmes_concluidos(self) -> int:
        alarmes = self._carregar_alarmes()
        antes = len(alarmes)
        ativos = [a for a in alarmes if a.get("status") != "concluido"]

        if len(ativos) < antes:
            self._salvar_alarmes(ativos)
            logger.info(
                f"{antes - len(ativos)} alarmes concluídos foram limpos do banco."
            )

        return antes - len(ativos)

    def adicionar_alarme(
        self,
        hora: str,
        missao: str,
        repetir: bool = False,
        musica: str = "",
        data: Optional[str] = None,
        dias_semana: Optional[List[int]] = None,
    ) -> str:
        if not hora or ":" not in hora:
            logger.warning(f"Tentativa de criar alarme com hora inválida: {hora}")
            return "Senhor, o formato de tempo parece inconsistente. Poderia repetir?"

        alarmes = self._carregar_alarmes()
        novo_alarme = {
            "hora": hora,
            "missao": missao,
            "status": "pendente",
            "repetir": repetir or bool(dias_semana),
            "musica": musica,
            "criado_em": datetime.now().isoformat(),
            "ultimo_disparo": None,
            "data": data.strip() if data else None,
            "dias_semana": dias_semana,
        }

        alarmes.append(novo_alarme)
        self._salvar_alarmes(alarmes)
        logger.info(f"Novo alarme agendado: {hora} - Missão: {missao}")
        return "Despertador"

    def remover_alarme(self, hora: str, missao: str, data: Optional[str] = None) -> str:
        # Guarda-chuva: não permite deleção sem hora E missão identificadas
        hora = (hora or "").strip()
        missao = (missao or "").strip()

        if not hora and not missao:
            logger.warning("remover_alarme chamado sem hora nem missão — abortado.")
            return "Senhor, não posso remover sem identificar o alarme (hora ou missão ausentes)."

        alarmes = self._carregar_alarmes()
        removidos = 0
        novos: List[Dict[str, Any]] = []

        for a in alarmes:
            hora_match = (not hora) or (a.get("hora", "").strip() == hora)
            missao_match = (not missao) or (a.get("missao", "").strip() == missao)
            data_match = (data is None) or (
                (a.get("data") or "").strip() == data.strip()
            )

            # Remove apenas se TODOS os critérios fornecidos batem
            if hora_match and missao_match and data_match and (hora or missao):
                removidos += 1
                # Remove apenas o PRIMEIRO encontrado para não deletar duplicatas acidentalmente
                if removidos == 1:
                    continue  # pula este (remove)
            novos.append(a)

        if removidos == 0:
            return "Senhor, não encontrei esse alarme."

        self._salvar_alarmes(novos)
        logger.info(f"Alarme removido: {hora} - Missão: {missao}")
        return (
            f"Alarme das {hora} foi desativado."
            if hora
            else f"Alarme '{missao}' removido."
        )

    def listar_alarmes(self) -> List[Dict[str, Any]]:
        return [a for a in self._carregar_alarmes() if a.get("status") == "pendente"]

    def snooze_alarme(self) -> str:
        agora = datetime.now()
        nova_hora = agora + timedelta(minutes=self.snooze_minutos)
        hora_formatada = nova_hora.strftime("%H:%M")

        self.adicionar_alarme(hora_formatada, "Soneca", data=agora.date().isoformat())
        logger.info(f"Soneca ativada para {hora_formatada}")
        return f"Soneca ativada por {self.snooze_minutos} minutos. Voltarei a chamar às {hora_formatada}."

    def _buscar_arquivo_musica(self) -> str:
        candidatos = [
            BASE_DIR / "assets" / "despertar.wav",
            Path.cwd() / "assets" / "despertar.wav",
            BASE_DIR / "despertar.wav",
        ]
        for c in candidatos:
            if c.exists() and c.is_file():
                return str(c)

        logger.error(
            "Arquivo de música 'despertar.wav' não encontrado em nenhum dos caminhos previstos."
        )
        return ""

    def invocar_som_alarme(self) -> None:
        caminho = self._buscar_arquivo_musica()

        if not PYGAME_AVAILABLE:
            logger.warning("Pygame indisponível. Áudio suprimido.")
            return

        if not caminho:
            logger.warning("Arquivo de alarme não encontrado. Áudio suprimido.")
            return

        try:
            # Sempre reinicializa o mixer — pode ter sido fechado por outra instância
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.quit()
            except Exception:
                pass

            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            pygame.mixer.set_num_channels(8)

            self.sound_alarme = pygame.mixer.Sound(caminho)
            self.sound_alarme.set_volume(1.0)

            self.canal_alarme = pygame.mixer.find_channel(
                True
            )  # force=True garante um canal
            self.canal_alarme.play(self.sound_alarme, loops=-1)
            logger.info("Áudio do alarme disparado com sucesso.")

            # Loop de espera robusto — verifica mixer antes de chamar get_busy()
            while self.alarme_ativo:
                try:
                    if not pygame.mixer.get_init():
                        break
                    if not self.canal_alarme or not self.canal_alarme.get_busy():
                        break
                except Exception:
                    break
                time.sleep(0.3)

            try:
                if self.canal_alarme and pygame.mixer.get_init():
                    self.canal_alarme.stop()
            except Exception:
                pass

        except Exception as e:
            logger.error(
                f"Falha ao executar áudio do alarme via pygame: {e}", exc_info=True
            )
        finally:
            self.canal_alarme = None
            self.sound_alarme = None
            # Libera o mixer ao terminar para não bloquear outros usos de áudio
            try:
                if PYGAME_AVAILABLE and pygame.mixer.get_init():
                    pygame.mixer.quit()
            except Exception:
                pass

    def ligar_tela_tv(self) -> None:
        try:
            from tasks.smart_home import ligar_tv

            ligar_tv()
            logger.info("Comando para ligar a TV enviado com sucesso.")
        except ImportError:
            logger.warning("Módulo de smart_home não encontrado. Ignorando ligar_tv.")
        except Exception as e:
            logger.error(f"Erro ao tentar ligar a TV: {e}", exc_info=True)

    def avisar_voz_alarme(self, missao: str) -> None:
        import asyncio

        texto = f"Bom dia senhor. Eu sou Jarvis. Fui configurado para um alarme. {missao}. Despertando."

        if (
            self.falar_callback
            and self.alarm_loop_ativo
            and not self.alarm_loop_ativo.is_closed()
        ):
            try:
                fut = asyncio.run_coroutine_threadsafe(
                    self.falar_callback(texto), self.alarm_loop_ativo
                )
                fut.result(timeout=180)
            except Exception as e:
                logger.error(f"Erro ao disparar aviso de voz TTS: {e}", exc_info=True)

    def deflagrar_rotina_alarme(self, alarme: Dict[str, Any]) -> None:
        logger.info(f"Deflagrando rotina de alarme: {alarme.get('missao')}")
        self.alarme_ativo = True

        threading.Thread(
            target=self.ligar_tela_tv, daemon=True, name="Alarme_LigarTV"
        ).start()
        threading.Thread(
            target=self.avisar_voz_alarme,
            args=(str(alarme.get("missao", "Alarme")),),
            daemon=True,
            name="Alarme_Voz",
        ).start()
        threading.Thread(
            target=self.invocar_som_alarme, daemon=True, name="Alarme_Som"
        ).start()

    def parar_alarme_total(self) -> str:
        self.alarme_ativo = False
        try:
            if self.canal_alarme is not None:
                self.canal_alarme.stop()
        except Exception as e:
            logger.error(f"Erro ao tentar parar o canal de áudio: {e}")

        import random

        retorno = random.choice(
            [
                "Protocolo encerrado. Mantenha o foco, Senhor.",
                "Alarme desativado. Os sistemas continuam operacionais, Senhor.",
                "Sinal interrompido. À sua disposição, Senhor.",
            ]
        )
        logger.info("Alarme parado manualmente pelo usuário.")
        return retorno

    def checagem_temporizador_loop(self) -> None:
        ciclo = 0
        logger.info("Loop de monitoramento de alarmes iniciado.")

        while True:
            try:
                agora_dt = datetime.now()
                hoje_iso = agora_dt.date().isoformat()
                agora_hm = agora_dt.strftime("%H:%M")
                dia_semana_atual = agora_dt.weekday()

                alarmes = self._carregar_alarmes()
                modificados = False

                for alarme in alarmes:
                    if alarme.get("status") != "pendente":
                        continue

                    d = (alarme.get("data") or "").strip()
                    dias = alarme.get("dias_semana")

                    if dias is not None:
                        if dia_semana_atual not in dias:
                            continue
                    elif d and d != hoje_iso:
                        continue

                    if alarme.get("hora") != agora_hm:
                        continue

                    chave = f"{d or str(dia_semana_atual)}|{alarme['hora']}|{alarme['missao']}"

                    if self.ultimo_disparo.get(chave) == hoje_iso:
                        continue

                    self.ultimo_disparo[chave] = hoje_iso

                    threading.Thread(
                        target=self.deflagrar_rotina_alarme,
                        args=(alarme,),
                        daemon=True,
                        name=f"Disparo_{alarme['hora']}",
                    ).start()

                    if not alarme.get("repetir") and dias is None:
                        alarme["status"] = "concluido"
                        modificados = True

                if modificados:
                    self._salvar_alarmes(alarmes)

                ciclo += 1
                if ciclo >= 3600:
                    self.limpar_alarmes_concluidos()
                    self._executar_manutencao_externa()
                    ciclo = 0

            except Exception as e:
                logger.error(
                    f"Falha crítica no loop do temporizador: {e}", exc_info=True
                )

            time.sleep(1)

    def _executar_manutencao_externa(self) -> None:
        """4. SEPARAÇÃO (SRP): Isolamos as chamadas de manutenção em outro arquivo/módulo."""
        try:
            import asyncio
            from storage.optimizer import (
                comprimir_banco_auditoria,
                purgar_resumos_antigos,
            )

            asyncio.run(comprimir_banco_auditoria())
            purgar_resumos_antigos(dias=365)
            logger.info(
                "Manutenção externa de banco de auditoria executada com sucesso."
            )
        except ImportError:
            logger.debug(
                "Módulo storage.optimizer não encontrado. Manutenção ignorada."
            )
        except Exception as e:
            logger.error(f"Erro na manutenção externa do banco: {e}")


def limpar_acentos(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def parse_alarme_voz(
    cmd: str,
) -> Tuple[Optional[str], Optional[str], str, Optional[List[int]]]:
    """
    Parser de linguagem natural para alarmes.
    Retorna (data_iso, hora_hhmm, missao, dias_semana).
    Exemplos suportados:
      "alarme às 7h" → (None, "07:00", "Alarme", None)
      "acorda às 6:30 amanhã" → ("2025-...", "06:30", "Alarme", None)
      "lembrar de reunião às 15:00 toda segunda" → (None, "15:00", "reunião", [0])
    """
    texto = limpar_acentos(cmd.lower().strip())
    hoje = date.today()

    # ── 1. Extrair hora ──────────────────────────────────────────────────────
    hora: Optional[str] = None
    m = re.search(r"(\d{1,2})\s*[:hH]\s*(\d{2})", texto)
    if m:
        hora = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
    else:
        m2 = re.search(r"\b(\d{1,2})\s*h(?:oras?)?\b", texto)
        if m2:
            hora = f"{int(m2.group(1)):02d}:00"
        else:
            m3 = re.search(r"\bao?\s*meio[\s-]dia\b", texto)
            if m3:
                hora = "12:00"

    # ── 2. Extrair data ───────────────────────────────────────────────────────
    data_iso: Optional[str] = None

    if re.search(r"\bamanh[aã]\b", texto):
        data_iso = (hoje + timedelta(days=1)).isoformat()

    elif re.search(r"\bhoje\b", texto):
        data_iso = hoje.isoformat()

    else:
        # "dia 15/06" ou "15 de junho"
        m_data = re.search(r"\bdia\s+(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", texto)
        if m_data:
            dia = int(m_data.group(1))
            mes = int(m_data.group(2))
            ano = int(m_data.group(3)) if m_data.group(3) else hoje.year
            if ano < 100:
                ano += 2000
            try:
                data_iso = date(ano, mes, dia).isoformat()
            except ValueError:
                pass
        else:
            m_ext = re.search(
                r"\bdia\s+(\d{1,2})\s+de\s+([a-z]+)(?:\s+de\s+(\d{4}))?",
                texto,
            )
            if m_ext:
                dia = int(m_ext.group(1))
                mes_nome = limpar_acentos(m_ext.group(2))
                mes = MESES.get(mes_nome)
                ano = int(m_ext.group(3)) if m_ext.group(3) else hoje.year
                if mes:
                    try:
                        data_iso = date(ano, mes, dia).isoformat()
                    except ValueError:
                        pass

    # ── 3. Extrair dias da semana para alarmes recorrentes ───────────────────
    dias_semana: Optional[List[int]] = None
    encontrados: List[int] = []
    for nome_dia, idx in DIAS_SEMANA.items():
        if re.search(rf"\b{re.escape(nome_dia)}\b", texto) and idx not in encontrados:
            encontrados.append(idx)
    if encontrados:
        dias_semana = sorted(set(encontrados))
        data_iso = None  # recorrente não tem data fixa

    # ── 4. Extrair missão ────────────────────────────────────────────────────
    ruido = re.compile(
        r"\b(alarme|lembrete|acorda|me\s+acorda|agendar|criar|"
        r"as\s+|as|para\s+as|para|amanha|hoje|dia|de|todo[sa]?|"
        r"toda\s+|segunda[\s\-]feira|terca[\s\-]feira|quarta[\s\-]feira|"
        r"quinta[\s\-]feira|sexta[\s\-]feira|sabado|domingo|"
        r"\d{1,2}[:h]\d{0,2}|horas?|hora|ao\s+meio[\s\-]dia)\b"
    )
    missao = ruido.sub("", texto).strip(" .,!?-")
    missao = re.sub(r"\s{2,}", " ", missao).strip()
    if not missao or len(missao) < 2:
        missao = "Alarme"

    return data_iso, hora, missao, dias_semana


gerenciador_alarmes = AlarmManager()


def iniciar_sistema_alarmes():
    threading.Thread(
        target=gerenciador_alarmes.checagem_temporizador_loop,
        daemon=True,
        name="LoopPrincipalAlarmes",
    ).start()


# ─────────────────────────────────────────────────────────────────────────────
# WRAPPERS DE MÓDULO — mantém compatibilidade com painel.py e controller.py
# que acessam alarm.carregar_alarmes(), alarm.salvar_alarmes(), etc.
# ─────────────────────────────────────────────────────────────────────────────


def carregar_alarmes() -> List[Dict[str, Any]]:
    """Proxy de módulo: lê TODOS os alarmes (pendentes e concluídos)."""
    return gerenciador_alarmes._carregar_alarmes()


def salvar_alarmes(alarmes: List[Dict[str, Any]]) -> None:
    """Proxy de módulo: sobrescreve o banco com a lista fornecida."""
    gerenciador_alarmes._salvar_alarmes(alarmes)


def adicionar_alarme(
    hora: str,
    missao: str,
    repetir: bool = False,
    musica: str = "",
    data: Optional[str] = None,
    dias_semana: Optional[List[int]] = None,
) -> str:
    """Proxy de módulo: delega ao gerenciador singleton."""
    return gerenciador_alarmes.adicionar_alarme(
        hora, missao, repetir=repetir, musica=musica, data=data, dias_semana=dias_semana
    )


def remover_alarme(hora: str, missao: str, data: Optional[str] = None) -> str:
    """Proxy de módulo: delega ao gerenciador singleton."""
    return gerenciador_alarmes.remover_alarme(hora, missao, data)


def listar_alarmes() -> List[Dict[str, Any]]:
    """Proxy de módulo: retorna apenas alarmes pendentes."""
    return gerenciador_alarmes.listar_alarmes()


def limpar_alarmes_concluidos() -> int:
    """Proxy de módulo: remove alarmes com status 'concluido'."""
    return gerenciador_alarmes.limpar_alarmes_concluidos()


def parar_alarme_total() -> str:
    """Proxy de módulo: para o alarme em curso."""
    return gerenciador_alarmes.parar_alarme_total()


# Propriedades de módulo lidas diretamente pelo painel.py
@property  # type: ignore[misc]
def _falar_callback_prop():
    return gerenciador_alarmes.falar_callback


@property  # type: ignore[misc]
def _alarm_loop_ativo_prop():
    return gerenciador_alarmes.alarm_loop_ativo


# O painel lê "alarm.falar_callback" e "alarm.alarm_loop_ativo" como atributos
# simples de módulo — resolvemos com um getter dinâmico via __getattr__ do módulo.
import sys as _sys


class _ModuleProxy(_sys.modules[__name__].__class__):
    """Permite acesso a gerenciador_alarmes.falar_callback via alarm.falar_callback."""

    def __getattr__(self, name: str):
        if name == "falar_callback":
            return gerenciador_alarmes.falar_callback
        if name == "alarm_loop_ativo":
            return gerenciador_alarmes.alarm_loop_ativo
        raise AttributeError(f"module 'alarm' has no attribute {name!r}")


_sys.modules[__name__].__class__ = _ModuleProxy
