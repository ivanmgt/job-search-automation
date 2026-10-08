import os
import re
import smtplib
import sqlite3
import sys
from email.mime.text import MIMEText
from pathlib import Path
from dotenv import load_dotenv

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROYECTO))
from db_schema import inicializar_db

load_dotenv(RAIZ_PROYECTO / ".env")
EMAIL_ACCOUNT = os.environ["GMAIL_ACCOUNT"]
APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
LOG_PATH = RAIZ_PROYECTO / "log_pipeline.txt"


def contar_errores_hoy() -> int:
    if not LOG_PATH.exists():
        return 0
    texto = LOG_PATH.read_text(encoding="utf-8", errors="ignore")
    ultimo_bloque = texto.split("Iniciando pipeline")[-1]
    errores = len(re.findall(r"\[ERROR\]", ultimo_bloque))
    tracebacks = len(re.findall(r"Traceback \(most recent call last\)", ultimo_bloque))
    return errores + tracebacks


def construir_resumen() -> str:
    conn = inicializar_db()
    conn.row_factory = sqlite3.Row

    nuevas_hoy = conn.execute(
        "SELECT COUNT(*) FROM vacantes WHERE date(fecha_descubierta) = date('now')"
    ).fetchone()[0]
    pendientes_fit = conn.execute(
        "SELECT COUNT(*) FROM vacantes WHERE fit_score IS NULL"
    ).fetchone()[0]
    pendientes_dudas = conn.execute(
        "SELECT COUNT(*) FROM vacantes WHERE requiere_revision = 1 AND decision_manual IS NULL"
    ).fetchone()[0]
    listas_enviar = conn.execute(
        "SELECT COUNT(*) FROM vacantes WHERE sugerencias_cv IS NOT NULL AND estado_aplicacion = 'no_enviada'"
    ).fetchone()[0]
    conn.close()

    return f"""Resumen del pipeline — {nuevas_hoy} vacantes nuevas hoy

Pendientes de calificar (fit): {pendientes_fit}
Pendientes de tu revisión manual (dudas): {pendientes_dudas}
Listas con sugerencias, sin enviar: {listas_enviar}
Errores en esta corrida: {contar_errores_hoy()}
"""


def enviar_correo(cuerpo: str):
    msg = MIMEText(cuerpo)
    msg["Subject"] = "Resumen diario - Pipeline de busqueda de empleo"
    msg["From"] = EMAIL_ACCOUNT
    msg["To"] = EMAIL_ACCOUNT
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ACCOUNT, APP_PASSWORD)
        server.send_message(msg)


if __name__ == "__main__":
    resumen = construir_resumen()
    print(resumen)
    try:
        enviar_correo(resumen)
        print("Correo de resumen enviado.")
    except Exception as e:
        print(f"[ERROR] No se pudo enviar el correo de resumen: {e}")
