# parser_alertas.py
import imaplib
import email
import hashlib
import sqlite3
import os
import re
import sys
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROYECTO))
from db_schema import inicializar_db

load_dotenv(RAIZ_PROYECTO / ".env")
IMAP_SERVER = "imap.gmail.com"
EMAIL_ACCOUNT = os.environ["GMAIL_ACCOUNT"]
APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
FUENTES = {
    "linkedin": "jobalerts-noreply@linkedin.com",  # confirmado — remitente exacto de alertas de empleo
    "occ": "alertas@occ.com.mx",
}


def obtener_html(msg) -> str:
    if msg.is_multipart():
        for parte in msg.walk():
            if parte.get_content_type() == "text/html":
                return parte.get_payload(decode=True).decode(errors="ignore")
    elif msg.get_content_type() == "text/html":
        return msg.get_payload(decode=True).decode(errors="ignore")
    return ""


CLASE_TITULO = "font-bold text-md leading-regular text-system-blue-50"


def parsear_linkedin(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    patron_job = re.compile(r"/jobs/view/(\d+)/")
    vacantes = []

    # Solo el <a> con esta clase específica es el título real — ignora logo y link oculto
    for enlace in soup.find_all("a", class_="font-bold"):
        clases = enlace.get("class", [])
        if "text-md" not in clases or "text-system-blue-50" not in clases:
            continue

        match_id = patron_job.search(enlace.get("href", ""))
        if not match_id:
            continue
        job_id = match_id.group(1)
        titulo = enlace.get_text(strip=True)

        # Empresa/ubicación: siguen viviendo en el <tr> siguiente, con el mismo patrón que ya confirmamos
        fila_actual = enlace.find_parent("tr")
        fila_siguiente = fila_actual.find_next_sibling("tr") if fila_actual else None
        parrafo = fila_siguiente.find("p") if fila_siguiente else None
        texto_parrafo = parrafo.get_text(strip=True) if parrafo else ""

        partes = texto_parrafo.split(" · ")
        empresa = partes[0] if partes else ""
        ubicacion = partes[1] if len(partes) > 1 else ""

        vacantes.append(
            {
                "job_id": job_id,
                "titulo": titulo,
                "empresa": empresa,
                "ubicacion": ubicacion,
                "link": enlace["href"].split("?")[0],
                "fuente": "linkedin-email",
            }
        )

    return vacantes


def extraer_job_id_occ(href: str) -> str | None:
    query = parse_qs(urlparse(href).query)
    url_interna = query.get("url", [""])[
        0
    ]  # parse_qs ya decodifica el %XX automáticamente
    match = re.search(r"jobid=(\d+)", url_interna)
    return match.group(1) if match else None


def parsear_occ(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    vacantes = []

    for enlace in soup.find_all("a", href=True):
        if "go/app/o_detail" not in enlace["href"]:
            continue

        job_id = extraer_job_id_occ(enlace["href"])

        td_titulo = enlace.find("td", style=lambda s: s and "underline" in s)
        titulo = td_titulo.get_text(separator=" ", strip=True) if td_titulo else ""

        td_empresa = enlace.find("td", style=lambda s: s and "#111827" in s)
        texto_empresa = (
            td_empresa.get_text(separator=" ", strip=True) if td_empresa else ""
        )
        partes = texto_empresa.split(" · ")
        empresa = partes[0].strip() if partes else ""
        ubicacion = partes[1].strip() if len(partes) > 1 else ""

        if not titulo:
            continue

        vacantes.append(
            {
                "job_id": job_id,
                "titulo": titulo,
                "empresa": empresa,
                "ubicacion": ubicacion,
                "link": enlace["href"],
                "fuente": "occ-email",
            }
        )

    return vacantes


PARSERS = {"linkedin": parsear_linkedin, "occ": parsear_occ}


def id_dedup(vacante: dict) -> str:
    if vacante.get("job_id"):
        return f"{vacante['fuente']}-{vacante['job_id']}"
    return (
        f"{vacante['fuente']}-" + hashlib.md5(vacante["link"].encode()).hexdigest()[:12]
    )


def guardar(vacantes: list[dict]):
    conn = inicializar_db()
    nuevas = 0
    for v in vacantes:
        try:
            conn.execute(
                """INSERT INTO vacantes (id_dedup, fuente, empresa, titulo, ubicacion, link)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    id_dedup(v),
                    v["fuente"],
                    v["empresa"],
                    v["titulo"],
                    v.get("ubicacion", ""),
                    v["link"],
                ),
            )
            nuevas += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    print(f"{nuevas} nuevas de {len(vacantes)} procesadas")
    conn.close()


DIAS_ATRAS = (
    int(sys.argv[1]) if len(sys.argv) > 1 else 2
)  # margen de seguridad por si el pipeline no corre un día


def main():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, timeout=30)
    mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
    mail.select('"[Gmail]/Todos"')

    fecha_desde = (datetime.now() - timedelta(days=DIAS_ATRAS)).strftime("%d-%b-%Y")

    todas = []
    for nombre, remitente in FUENTES.items():
        if remitente.startswith("REMITENTE_A"):
            print(f"[AVISO] Saltando '{nombre}' — remitente aún no confirmado")
            continue

        _, datos = mail.search(None, f'(FROM "{remitente}" SINCE "{fecha_desde}")')
        ids = datos[0].split()
        print(f"{nombre}: {len(ids)} correos desde {fecha_desde}")

        for id_ in ids:
            _, msg_data = mail.fetch(id_, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            vacantes = PARSERS[nombre](obtener_html(msg))

            if not vacantes:
                print(
                    f"  [AVISO] Correo {id_.decode()} de {nombre} no arrojó vacantes — revisar plantilla"
                )

            todas.extend(vacantes)

    mail.logout()
    guardar(todas)


if __name__ == "__main__":
    main()
