import sqlite3
import sys
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROYECTO))
from db_schema import inicializar_db


def guardar_vacantes(vacantes: list[dict], termino: str = ""):
    conn = inicializar_db()
    nuevas = 0
    for v in vacantes:
        id_dedup = f"gobmx-{v['id']}"

        salario_min = v.get("salarioOfrecido") or None
        salario_max = v.get("salarioOfrecidoMaximo") or None
        if salario_min == 0:
            salario_min = None
        if salario_max == 0:
            salario_max = None

        try:
            conn.execute(
                """INSERT INTO vacantes
                   (id_dedup, fuente, empresa, titulo, ubicacion, descripcion, anios_experiencia,
                    termino_busqueda, salario_min, salario_max)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    id_dedup,
                    "gob.mx",
                    v.get("nombreEmpresa", ""),
                    v.get("tituloOferta", ""),
                    f"{v.get('municipio', '')}, {v.get('entidad', '')}",
                    v.get("descripcion", ""),
                    v.get("aniosExperiencia", ""),
                    termino,
                    salario_min,
                    salario_max,
                ),
            )
            nuevas += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    print(f"{nuevas} nuevas vacantes guardadas de {len(vacantes)} procesadas")
    conn.close()
