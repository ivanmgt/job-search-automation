import os
import time
import requests
from dotenv import load_dotenv
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ_PROYECTO / ".env")

API_KEY = os.environ["GEMINI_API_KEY"]
MODELO = "gemini-3.5-flash-lite"
BASE_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent"
)

MAX_REINTENTOS = 4
ESPERA_BASE_SEGUNDOS = 5


def llamar_gemini(
    prompt: str, usar_grounding: bool = False, json_mode: bool = False
) -> str:
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if usar_grounding:
        body["tools"] = [{"google_search": {}}]
    if json_mode:
        body["generationConfig"] = {"response_mime_type": "application/json"}

    for intento in range(1, MAX_REINTENTOS + 1):
        response = requests.post(f"{BASE_URL}?key={API_KEY}", json=body)

        if response.status_code == 200:
            data = response.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError):
                print(f"[ERROR] Respuesta sin texto utilizable: {data}")
                return ""

        if response.status_code in (503, 429):
            espera = ESPERA_BASE_SEGUNDOS * (2 ** (intento - 1))
            print(
                f"[AVISO] Gemini respondió {response.status_code} (intento {intento}/{MAX_REINTENTOS}) — reintentando en {espera}s..."
            )
            time.sleep(espera)
            continue

        print(f"[ERROR] Gemini respondió {response.status_code}: {response.text[:300]}")
        return ""

    print(
        f"[ERROR] Se agotaron los {MAX_REINTENTOS} reintentos, Gemini sigue sobrecargado"
    )
    return ""
