import json
import sqlite3
import sys
from pathlib import Path
from gemini_client import llamar_gemini

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROYECTO))
from db_schema import inicializar_db

UMBRAL_FIT_MINIMO = 50
DIAS_VIGENCIA_CACHE = 30


def construir_prompt_vetting(empresa: str) -> str:
    return f"""Evalúa la empresa "{empresa}" usando ÚNICAMENTE tu conocimiento general (no tienes
acceso a búsqueda en internet en este momento). Evalúa:

1. LEGITIMIDAD: ¿Reconoces esta empresa como una organización real y conocida? Si nunca has
   oído hablar de ella, dilo honestamente — no inventes información.
2. SEÑALES DE ESTAFA EN EL NOMBRE/CONTEXTO: ¿El nombre o lo que sabes de ella sugiere algún
   patrón sospechoso (nombre genérico tipo "Talento Startup SAPI", posible cascarón, etc.)?
3. CALIDAD LABORAL CONOCIDA: Solo si tienes conocimiento confiable y específico sobre su
   reputación laboral — no generalices ni supongas.

IMPORTANTE: Si no tienes información confiable sobre esta empresa específica, responde con
veredicto "dudas" y sé explícito en que no la reconoces — NO inventes ni asumas legitimidad
solo porque el nombre suena profesional.

Responde ÚNICAMENTE con JSON, sin texto adicional, en este formato exacto:
{{
  "veredicto": "legitima" | "alto_riesgo" | "dudas",
  "razon": "explicación breve, máx 40 palabras",
  "pregunta_para_ivan": "solo si veredicto es 'dudas' — pregunta específica, si no aplica deja string vacío"
}}"""


def obtener_de_cache(conn, empresa: str) -> dict | None:
    fila = conn.execute(
        """SELECT veredicto, razon FROM empresas_vetting
           WHERE empresa = ? AND fecha_vetting >= datetime('now', ?)""",
        (empresa, f"-{DIAS_VIGENCIA_CACHE} days"),
    ).fetchone()
    if fila:
        return {"veredicto": fila[0], "razon": fila[1]}
    return None


def guardar_en_cache(conn, empresa: str, resultado: dict):
    conn.execute(
        """INSERT INTO empresas_vetting (empresa, veredicto, razon, fecha_vetting)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(empresa) DO UPDATE SET
             veredicto = excluded.veredicto,
             razon = excluded.razon,
             fecha_vetting = excluded.fecha_vetting""",
        (empresa, resultado["veredicto"], resultado["razon"]),
    )
    conn.commit()


def investigar_empresa(empresa: str) -> dict:
    prompt = construir_prompt_vetting(empresa)
    respuesta = llamar_gemini(prompt, usar_grounding=False, json_mode=True)

    if not respuesta:
        return {
            "veredicto": "dudas",
            "razon": "Sin respuesta de Gemini",
            "pregunta_para_ivan": "No se pudo investigar esta empresa — ¿la conoces?",
        }

    try:
        return json.loads(respuesta)
    except json.JSONDecodeError:
        print(f"[ERROR] Respuesta de vetting no es JSON válido: {respuesta[:300]}")
        return {
            "veredicto": "dudas",
            "razon": "Error al interpretar respuesta",
            "pregunta_para_ivan": "Hubo un error técnico investigando esta empresa — revisar manualmente.",
        }


def main():
    conn = inicializar_db()
    conn.row_factory = sqlite3.Row

    vacantes = conn.execute(
        """SELECT id_dedup, empresa FROM vacantes
           WHERE fit_score >= ? AND vetting_veredicto IS NULL""",
        (UMBRAL_FIT_MINIMO,),
    ).fetchall()

    vacantes_por_empresa = {}
    for v in vacantes:
        vacantes_por_empresa.setdefault(v["empresa"], []).append(v["id_dedup"])

    print(
        f"Vacantes a procesar: {len(vacantes)} | Empresas únicas: {len(vacantes_por_empresa)}\n"
    )

    for empresa, ids in vacantes_por_empresa.items():
        cacheado = obtener_de_cache(conn, empresa)
        if cacheado:
            print(f"[CACHÉ] {empresa}: {cacheado['veredicto']}")
            resultado = {**cacheado, "pregunta_para_ivan": ""}
        else:
            print(f"[INVESTIGANDO] {empresa}...")
            resultado = investigar_empresa(empresa)
            guardar_en_cache(conn, empresa, resultado)
            print(f"  -> {resultado['veredicto']}: {resultado['razon']}")

        requiere_revision = (
            1 if resultado["veredicto"] in ("dudas", "alto_riesgo") else 0
        )
        for id_dedup in ids:
            conn.execute(
                """UPDATE vacantes SET vetting_veredicto = ?, vetting_razon = ?,
                   requiere_revision = ?, pregunta_revision = ? WHERE id_dedup = ?""",
                (
                    resultado["veredicto"],
                    resultado["razon"],
                    requiere_revision,
                    resultado.get("pregunta_para_ivan", ""),
                    id_dedup,
                ),
            )
        conn.commit()  # guarda inmediatamente, no espera a que termine todo

    conn.close()
    print(f"\nListo — {len(vacantes)} vacantes actualizadas con vetting")


if __name__ == "__main__":
    main()
