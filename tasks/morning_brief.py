from __future__ import annotations

import logging
import config
from tasks.news import noticias_para_fala

log = logging.getLogger("jarvis.morning_brief")

async def gerar_briefing(ativo: bool | None = None) -> str:
    if ativo is None:
        ativo = getattr(config, "BRIEFING_AUTO", True)
    if not ativo:
        return "Briefing desativado nas configurações."

    partes = ["Bom dia, Senhor. Aqui está seu briefing matinal."]

    clima = getattr(config, "cidade_padrao", "")
    if clima:
        try:
            from tasks.weather import obter_previsao_hoje
            info = obter_previsao_hoje(clima)
            if info:
                partes.append(info)
        except Exception as e:
            log.warning(f"Falha ao obter clima no briefing: {e}")

    news_ativo = getattr(config, "NEWS_ATIVO", True)
    if news_ativo:
        try:
            noticias = await noticias_para_fala(3)
            if noticias:
                partes.append(noticias)
        except Exception as e:
            log.warning(f"Falha ao obter notícias no briefing: {e}")

    cal_ativo = getattr(config, "CALENDAR_ATIVO", False)
    if cal_ativo:
        try:
            from datetime import date
            from tasks.calendar_integration import eventos_para_fala
            ev = eventos_para_fala(date.today().isoformat())
            if ev:
                partes.append(ev)
        except Exception as e:
            log.warning(f"Falha ao obter eventos no briefing: {e}")

    email_ativo = getattr(config, "EMAIL_ATIVO", False)
    if email_ativo:
        try:
            from tasks.email_checker import emails_para_fala
            emails = await emails_para_fala(3)
            if emails:
                partes.append(emails)
        except Exception as e:
            log.warning(f"Falha ao obter e-mails no briefing: {e}")

    return ". ".join(partes)