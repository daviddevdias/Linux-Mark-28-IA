from __future__ import annotations
import asyncio, logging, sqlite3, time
from datetime import datetime as dt
from pathlib import Path

log = logging.getLogger("jarvis.optimizer")
LOTE, MINIMO, TIMEOUT_IA = 100, 50, 30.0
DB_PATH = Path(__file__).resolve().parent.parent / "logs" / "audit.db"


def conectar_banco_auditoria() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS audit_resumos (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, periodo_de TEXT NOT NULL, periodo_ate TEXT NOT NULL, registros INTEGER NOT NULL, resumo TEXT NOT NULL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_resumos_ts ON audit_resumos(ts)")
    conn.commit()
    return conn


async def comprimir_banco_auditoria():
    conn = conectar_banco_auditoria()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM audit_log")
        total_antes = cur.fetchone()["total"]
        if total_antes < MINIMO:
            return f"O banco já está otimizado. Registros atuais: {total_antes}."
        cur.execute(
            "SELECT id, comando, resultado, ts FROM audit_log ORDER BY id ASC LIMIT ?",
            (LOTE,),
        )
        registros = cur.fetchall()
        ids = [r["id"] for r in registros]
        texto_logs = " ".join(
            f"[{r['ts']}] Cmd: {r['comando']} | Res: {r['resultado'][:50]}"
            for r in registros
        )

        from engine.ia_router import router

        prompt = f"Analise este bloco de logs antigos e crie um resumo técnico de 2 linhas. Logs: {texto_logs}"
        try:
            resumo = await asyncio.wait_for(
                router.responder(prompt), timeout=TIMEOUT_IA
            )
            if not resumo:
                raise ValueError("IA retornou vazio")
        except asyncio.TimeoutError:
            return f"Abortado: IA não respondeu em {TIMEOUT_IA:.0f}s."
        except Exception as exc:
            return f"Abortado: {exc}"

        ts_de = registros[0]["ts"] if registros else ""
        ts_ate = registros[-1]["ts"] if registros else ""
        conn.execute(
            "INSERT INTO audit_resumos (ts, periodo_de, periodo_ate, registros, resumo) VALUES (?, ?, ?, ?, ?)",
            (dt.now().isoformat(timespec="seconds"), ts_de, ts_ate, len(ids), resumo),
        )
        conn.execute(
            f"DELETE FROM audit_log WHERE id IN ({','.join('?' for _ in ids)})", ids
        )
        conn.commit()

        cur.execute("SELECT COUNT(*) AS total FROM audit_log")
        total_depois = cur.fetchone()["total"]
        return f"Reduzido de {total_antes} para {total_depois}. Resumo: {resumo}"
    except Exception as exc:
        conn.rollback()
        return f"Falha: {exc}"
    finally:
        conn.close()


def purgar_resumos_antigos(dias: int = 365) -> int:
    limite = time.time() - dias * 86400
    try:
        conn = conectar_banco_auditoria()
        cur = conn.execute(
            "DELETE FROM audit_resumos WHERE ts < datetime(?, 'unixepoch')", (limite,)
        )
        conn.commit()
        removidos = cur.rowcount
        conn.close()
        return removidos
    except:
        return 0
