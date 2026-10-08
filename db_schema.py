import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "vacantes.db"

COLUMNAS = {
    "id_dedup": "TEXT PRIMARY KEY",
    "fuente": "TEXT NOT NULL",
    "empresa": "TEXT",
    "titulo": "TEXT",
    "ubicacion": "TEXT",
    "descripcion": "TEXT",
    "anios_experiencia": "TEXT",
    "link": "TEXT",
    "termino_busqueda": "TEXT",
    "salario_min": "INTEGER",
    "salario_max": "INTEGER",
    "fecha_descubierta": "TEXT DEFAULT CURRENT_TIMESTAMP",
    "fit_score": "INTEGER",
    "fit_razon": "TEXT",
    "vetting_veredicto": "TEXT",
    "vetting_razon": "TEXT",
    "requiere_revision": "INTEGER DEFAULT 0",
    "pregunta_revision": "TEXT",
    "decision_manual": "TEXT",
    "notas_decision": "TEXT",
    "sugerencias_cv": "TEXT",
    "sugerencias_carta": "TEXT",
    "estado_aplicacion": "TEXT DEFAULT 'no_enviada'",
}


def inicializar_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    definicion = ",\n            ".join(
        f"{nombre} {tipo}" for nombre, tipo in COLUMNAS.items()
    )
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS vacantes (\n            {definicion}\n        )"
    )

    for nombre, tipo in COLUMNAS.items():
        tipo_alter = tipo.replace("PRIMARY KEY", "").replace("NOT NULL", "").strip()
        try:
            conn.execute(f"ALTER TABLE vacantes ADD COLUMN {nombre} {tipo_alter}")
        except sqlite3.OperationalError:
            pass  # la columna ya existe — comportamiento esperado en cada corrida

    conn.execute("""
        CREATE TABLE IF NOT EXISTS empresas_vetting (
            empresa TEXT PRIMARY KEY,
            veredicto TEXT,
            razon TEXT,
            fecha_vetting TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


if __name__ == "__main__":
    inicializar_db()
    print("Esquema inicializado/actualizado correctamente.")
