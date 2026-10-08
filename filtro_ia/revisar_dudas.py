import sqlite3
import sys
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROYECTO))
from db_schema import inicializar_db

OPCIONES_VALIDAS = {"a": "aplicar", "d": "descartar", "s": None, "q": "SALIR"}


def obtener_ids_pendientes(conn) -> list[str]:
    filas = conn.execute(
        "SELECT id_dedup FROM vacantes WHERE requiere_revision = 1 AND decision_manual IS NULL"
    ).fetchall()
    return [f[0] for f in filas]


def obtener_vacante(conn, id_dedup):
    return conn.execute(
        """SELECT id_dedup, titulo, empresa, ubicacion, link, fit_razon, vetting_razon, pregunta_revision
           FROM vacantes WHERE id_dedup = ?""",
        (id_dedup,),
    ).fetchone()


def contar_pendientes(conn) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM vacantes WHERE requiere_revision = 1 AND decision_manual IS NULL"
    ).fetchone()[0]


def mostrar_vacante(v, restantes):
    _, titulo, empresa, ubicacion, link, fit_razon, vetting_razon, pregunta = v
    print("\n" + "=" * 60)
    print(f"Quedan {restantes} por revisar")
    print("=" * 60)
    print(f"Puesto:    {titulo}")
    print(f"Empresa:   {empresa}")
    print(f"Ubicacion: {ubicacion or 'no especificada'}")
    print(f"Link:      {link}")
    print(f"\nPor que encajo (fit):  {fit_razon}")
    print(f"Duda del vetting:      {vetting_razon}")
    if pregunta:
        print(f"Pregunta especifica:   {pregunta}")
    print("=" * 60)


def pedir_decision() -> str:
    while True:
        resp = (
            input("\n[a]plicar / [d]escartar / [s]altar por ahora / [q] salir: ")
            .strip()
            .lower()
        )
        if resp in OPCIONES_VALIDAS:
            return resp
        print("Opcion no valida, intenta de nuevo.")


def guardar_decision(conn, id_dedup, decision, notas):
    conn.execute(
        "UPDATE vacantes SET decision_manual = ?, notas_decision = ? WHERE id_dedup = ?",
        (decision, notas, id_dedup),
    )
    conn.commit()


def main():
    conn = inicializar_db()

    ids_pendientes = obtener_ids_pendientes(conn)
    if not ids_pendientes:
        print("No hay vacantes pendientes de revisar. Todo al dia.")
        conn.close()
        return

    print(f"Tienes {len(ids_pendientes)} vacantes por revisar.")

    try:
        i = 0
        while i < len(ids_pendientes):
            vacante = obtener_vacante(conn, ids_pendientes[i])
            mostrar_vacante(vacante, len(ids_pendientes) - i)

            respuesta = pedir_decision()

            if respuesta == "q":
                print("\nSaliendo. Tu progreso ya quedo guardado.")
                break
            if respuesta == "s":
                i += 1
                continue

            decision = OPCIONES_VALIDAS[respuesta]
            notas = input("Notas (opcional, Enter para omitir): ").strip()
            guardar_decision(conn, vacante[0], decision, notas or None)
            print(f"Guardado: {decision}")
            i += 1

    except KeyboardInterrupt:
        print("\n\nInterrumpido. Todo lo decidido hasta ahora ya quedo guardado.")

    finally:
        print(
            f"\nResumen de esta sesion: {contar_pendientes(conn)} vacantes siguen sin decision."
        )
        conn.close()


if __name__ == "__main__":
    main()
