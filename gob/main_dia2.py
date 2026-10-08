import yaml
from pathlib import Path
from scraper_gobmx import buscar_todas
from almacenamiento import guardar_vacantes

RAIZ_PROYECTO = (
    Path(__file__).resolve().parent.parent
)  # sube un nivel desde gob/ a la raíz


def cargar_keywords() -> list[str]:
    with open(RAIZ_PROYECTO / "profile.yml", "r", encoding="utf-8") as f:
        perfil = yaml.safe_load(f)
    objetivo = perfil["objetivo"]
    terminos = [objetivo["puesto_objetivo"]] + objetivo.get(
        "puestos_alternativos_gobmx", []
    )
    return [t for t in terminos if t and t.strip()]


if __name__ == "__main__":
    keywords = cargar_keywords()
    print(f"Buscando {len(keywords)} términos: {keywords}\n")

    for kw in keywords:
        print(f"=== {kw} ===")
        resultados = buscar_todas(kw)
        guardar_vacantes(resultados, termino=kw)
