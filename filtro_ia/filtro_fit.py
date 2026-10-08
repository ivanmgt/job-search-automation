import json
import sqlite3
import sys
import yaml
from pathlib import Path
from gemini_client import llamar_gemini

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROYECTO))
from db_schema import inicializar_db

TAMANO_LOTE = 15


def cargar_perfil() -> dict:
    with open(RAIZ_PROYECTO / "profile.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resumen_perfil(perfil: dict) -> str:
    obj = perfil["objetivo"]
    exp = perfil.get("experiencia", [])
    proyectos = perfil.get("proyectos", [])
    hab = perfil.get("habilidades", {})
    pref = perfil.get("preferencias_filtro", {})

    exp_items = [f"{e['puesto']} en {e['empresa']}" for e in exp]
    exp_txt = (
        "; ".join(exp_items)
        if exp_items
        else "Sin experiencia laboral formal en el área"
    )

    proyecto_items = [
        f"{p['nombre']}: {p.get('descripcion', '').strip()}" for p in proyectos
    ]
    proyectos_txt = "; ".join(proyecto_items)

    lineas = [
        f"Puesto objetivo: {obj['puesto_objetivo']}",
        f"Puestos alternativos aceptables: {', '.join(obj.get('puestos_alternativos', []))}",
        f"Modalidad preferida: {obj.get('modalidad', '')}",
        f"Ubicaciones de interés: {', '.join(obj.get('ubicaciones_de_interes', []))}",
        f"Experiencia laboral: {exp_txt}",
        f"Proyectos técnicos: {proyectos_txt}",
        f"Frameworks ML/DL: {', '.join(hab.get('ml_dl_frameworks', []))}",
        f"Lenguajes de programación: {', '.join(hab.get('lenguajes', []))}",
        f"Salario mínimo aceptable (MXN/mes): {pref.get('salario_minimo_mxn', 'no especificado')}",
        f"Años de experiencia máximos que puede cumplir como hard requirement: {pref.get('anios_experiencia_maximo_requerido', 'no especificado')}",
        f"Rechazar automáticamente si la descripción contiene: {', '.join(pref.get('rechazar_si_contiene', []))}",
        f"Evaluar con cautela (no rechazar de plano) si contiene: {', '.join(pref.get('aplicar_con_cautela_si_contiene', []))}",
        f"Sectores preferidos: {', '.join(pref.get('sectores_preferidos', []))}",
        f"Sectores de baja prioridad: {', '.join(pref.get('sectores_baja_prioridad', []))}",
    ]
    return "\n".join(lineas)


def excluir_por_titulo(titulo: str, excluir: list[str]) -> str | None:
    titulo_lower = (titulo or "").lower()
    for palabra in excluir:
        if palabra.lower() in titulo_lower:
            return palabra
    return None


def construir_prompt_lote(perfil_txt: str, lote: list[sqlite3.Row]) -> str:
    vacantes_txt = []
    for v in lote:
        vacantes_txt.append(
            f"ID: {v['id_dedup']}\n"
            f"Título: {v['titulo']}\n"
            f"Empresa: {v['empresa']}\n"
            f"Ubicación: {v['ubicacion'] or 'no especificada'}\n"
            f"Años de experiencia requeridos: {v['anios_experiencia'] or 'no especificado'}\n"
            f"Descripción: {(v['descripcion'] or '')[:500]}"
        )
    vacantes_bloque = "\n---\n".join(vacantes_txt)

    return f"""Eres un asistente que evalúa qué tan bien encajan vacantes con el perfil de un candidato.

PERFIL DEL CANDIDATO:
{perfil_txt}

VACANTES A EVALUAR:
{vacantes_bloque}

Para cada vacante, da un score de 0 a 100 de qué tan buen fit es, y una razón breve (máx 20 palabras).
- 80-100: excelente fit, aplicar con prioridad
- 50-79: fit razonable, considerar
- 0-49: mal fit, o cae en algo de "rechazar automáticamente"

Responde ÚNICAMENTE con un array JSON, sin texto adicional, formato exacto:
[{{"id": "...", "score": 0, "razon": "..."}}]"""


def procesar_lote(conn, perfil_txt: str, lote: list[sqlite3.Row]):
    prompt = construir_prompt_lote(perfil_txt, lote)
    respuesta = llamar_gemini(prompt, json_mode=True)

    if not respuesta:
        print("[ERROR] Sin respuesta de Gemini para este lote")
        return

    try:
        resultados = json.loads(respuesta)
    except json.JSONDecodeError:
        print(f"[ERROR] Respuesta no es JSON válido: {respuesta[:300]}")
        return

    for r in resultados:
        try:
            conn.execute(
                "UPDATE vacantes SET fit_score = ?, fit_razon = ? WHERE id_dedup = ?",
                (r["score"], r["razon"], r["id"]),
            )
        except KeyError as e:
            print(f"[AVISO] Resultado mal formado, se salta: falta {e}")
    conn.commit()
    print(f"Lote procesado: {len(resultados)} vacantes calificadas")


def main():
    perfil = cargar_perfil()
    perfil_txt = resumen_perfil(perfil)
    excluir = perfil.get("keywords_alertas", {}).get("excluir", [])

    conn = inicializar_db()
    conn.row_factory = sqlite3.Row
    pendientes = conn.execute(
        "SELECT * FROM vacantes WHERE fit_score IS NULL"
    ).fetchall()
    print(f"Vacantes pendientes de calificar: {len(pendientes)}")

    a_evaluar = []
    for v in pendientes:
        motivo = excluir_por_titulo(v["titulo"], excluir)
        if motivo:
            conn.execute(
                "UPDATE vacantes SET fit_score = 0, fit_razon = ? WHERE id_dedup = ?",
                (f"Excluido por título: contiene '{motivo}'", v["id_dedup"]),
            )
        else:
            a_evaluar.append(v)
    conn.commit()
    print(
        f"Excluidas por título (sin gastar cuota de IA): {len(pendientes) - len(a_evaluar)}"
    )
    print(f"A evaluar con Gemini: {len(a_evaluar)}")

    for i in range(0, len(a_evaluar), TAMANO_LOTE):
        lote = a_evaluar[i : i + TAMANO_LOTE]
        print(f"\nLote {i // TAMANO_LOTE + 1} ({len(lote)} vacantes)...")
        procesar_lote(conn, perfil_txt, lote)

    conn.close()


if __name__ == "__main__":
    main()
