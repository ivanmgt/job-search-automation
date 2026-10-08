import json
import sqlite3
import sys
import yaml
from pathlib import Path
from gemini_client import llamar_gemini

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROYECTO))
from db_schema import inicializar_db

UMBRAL_FIT_MINIMO = 50


def cargar_perfil() -> dict:
    with open(RAIZ_PROYECTO / "profile.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def contexto_cv(perfil: dict) -> str:
    edu_txt = []
    for e in perfil.get("educacion", []):
        tesis = e.get("tesis", {})
        edu_txt.append(
            f"{e.get('titulo', '')} — {e.get('institucion', '')} ({e.get('estado', '')})\n"
            f"Tesis: {tesis.get('titulo', '')} — {str(tesis.get('descripcion_breve', '')).strip()}\n"
            f"Resultado: {tesis.get('resultado_destacado', '')}"
        )

    exp_txt = []
    for e in perfil.get("experiencia", []):
        logros = "; ".join(e.get("logros", []))
        exp_txt.append(
            f"{e['puesto']} en {e['empresa']} ({e.get('fecha_inicio', '')} - {e.get('fecha_fin', '')}): {logros}"
        )

    proy_txt = []
    for p in perfil.get("proyectos", []):
        tecnologias = ", ".join(p.get("tecnologias", []))
        proy_txt.append(
            f"{p['nombre']}: {str(p.get('descripcion', '')).strip()} | Tecnologías: {tecnologias} | Resultado: {p.get('resultado_destacado', '')}"
        )

    hab = perfil.get("habilidades", {})
    hab_txt = "; ".join(
        f"{k}: {', '.join(v)}" for k, v in hab.items() if isinstance(v, list) and v
    )

    cert_txt = "; ".join(
        f"{c['nombre']} ({c.get('estado', '')})"
        for c in perfil.get("certificaciones", [])
    )

    return f"""EDUCACIÓN:
{chr(10).join(edu_txt)}

EXPERIENCIA:
{chr(10).join(exp_txt) if exp_txt else "Sin experiencia laboral formal en el área"}

PROYECTOS:
{chr(10).join(proy_txt)}

HABILIDADES:
{hab_txt}

CERTIFICACIONES:
{cert_txt}"""


def construir_prompt(perfil_cv: str, vacante: sqlite3.Row) -> str:
    return f"""Eres un asesor de carrera. NO inventes experiencia ni tecnologías que el candidato
no tiene — solo trabaja con lo que aparece abajo.

PERFIL REAL DEL CANDIDATO:
{perfil_cv}

VACANTE:
Puesto: {vacante["titulo"]}
Empresa: {vacante["empresa"]}
Descripción: {(vacante["descripcion"] or "")[:800]}
Por qué encajó (evaluación previa): {vacante["fit_razon"]}

Da sugerencias CONCRETAS de qué cambiar en el CV del candidato para esta vacante específica
(qué palabras clave del ATS incluir, qué logro/proyecto destacar primero, qué reformular) —
NO redactes un CV completo, solo los cambios puntuales a hacer.

También da 3-4 puntos clave que debería tocar en su carta de presentación para esta vacante
específica — NO redactes la carta completa, solo los puntos/ángulo a cubrir.

Responde ÚNICAMENTE con JSON, sin texto adicional, en este formato exacto:
{{
  "cambios_cv": ["cambio 1", "cambio 2"],
  "puntos_carta": ["punto 1", "punto 2"]
}}"""


def procesar_vacante(conn, perfil_cv: str, vacante: sqlite3.Row):
    prompt = construir_prompt(perfil_cv, vacante)
    respuesta = llamar_gemini(prompt, json_mode=True)

    if not respuesta:
        print(
            f"  [ERROR] Sin respuesta para {vacante['titulo']} @ {vacante['empresa']}"
        )
        return

    try:
        resultado = json.loads(respuesta)
    except json.JSONDecodeError:
        print(f"  [ERROR] JSON inválido: {respuesta[:300]}")
        return

    cambios_cv = "\n".join(f"- {c}" for c in resultado.get("cambios_cv", []))
    puntos_carta = "\n".join(f"- {p}" for p in resultado.get("puntos_carta", []))

    conn.execute(
        "UPDATE vacantes SET sugerencias_cv = ?, sugerencias_carta = ? WHERE id_dedup = ?",
        (cambios_cv, puntos_carta, vacante["id_dedup"]),
    )
    conn.commit()
    print(f"  Listo: {vacante['titulo']} @ {vacante['empresa']}")


def main():
    perfil_cv = contexto_cv(cargar_perfil())

    conn = inicializar_db()
    conn.row_factory = sqlite3.Row

    vacantes = conn.execute(
        f"""SELECT * FROM vacantes
            WHERE fit_score >= {UMBRAL_FIT_MINIMO}
              AND (vetting_veredicto = 'legitima' OR decision_manual = 'aplicar')
              AND (decision_manual IS NULL OR decision_manual != 'descartar')
              AND sugerencias_cv IS NULL
            ORDER BY fit_score DESC"""
    ).fetchall()

    print(f"Vacantes a procesar: {len(vacantes)}\n")
    for v in vacantes:
        print(f"[{v['fit_score']}] {v['titulo']} @ {v['empresa']}")
        procesar_vacante(conn, perfil_cv, v)

    conn.close()


if __name__ == "__main__":
    main()
