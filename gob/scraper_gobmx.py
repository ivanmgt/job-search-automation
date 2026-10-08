# scraper_gobmx.py
import requests
import time

SEARCH_URL = "https://www.empleo.gob.mx/api/Login/busqueda/empleos"

HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.empleo.gob.mx",
    "Referer": "https://www.empleo.gob.mx/PortalDigital",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
}


def buscar_pagina(que: str, page: int, items: int = 50) -> dict:
    payload = {
        "que": que,
        "donde": {},
        "items": items,
        "page": page,
        "orden": "fecha_publicacion desc",
        "filter": {},
    }
    response = requests.post(SEARCH_URL, json=payload, headers=HEADERS)
    if response.status_code == 403:
        print(f" 403 en página {page} — revisar headers, pudieron cambiar")
        return {}
    response.raise_for_status()
    return response.json()


def buscar_todas(que: str, items_por_pagina: int = 50) -> list[dict]:
    resultados = []
    page = 0

    while True:
        data = buscar_pagina(que, page, items_por_pagina)
        if not data or "content" not in data:
            break

        resultados.extend(data["content"])
        print(
            f"Página {page}: {len(data['content'])} vacantes ({len(resultados)}/{data.get('totalElements', '?')})"
        )

        if data.get("last", True):
            break

        page += 1
        time.sleep(3)

    return resultados


if __name__ == "__main__":
    vacantes = buscar_todas("ingeniero")
    print(f"\nTotal recolectado: {len(vacantes)}")
