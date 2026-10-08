import sqlite3
import sys
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROYECTO))
from db_schema import inicializar_db


def main():
    conn = inicializar_db()
    conn.row_factory = sqlite3.Row

    vacantes = conn.execute(
        """SELECT * FROM vacantes
           WHERE sugerencias_cv IS NOT NULL AND estado_aplicacion = 'no_enviada'
           ORDER BY fit_score DESC"""
    ).fetchall()

    if not vacantes:
        print("No hay sugerencias pendientes de revisar/enviar.")
        conn.close()
        return

    print(f"Tienes {len(vacantes)} vacantes con sugerencias pendientes.\n")

    try:
        for v in vacantes:
            print("\n" + "=" * 60)
            print(f"[{v['fit_score']}] {v['titulo']} @ {v['empresa']}")
            print(f"Link: {v['link']}")
            print("-" * 60)
            print("CAMBIOS AL CV:")
            print(v["sugerencias_cv"])
            print("\nPUNTOS PARA LA CARTA:")
            print(v["sugerencias_carta"])
            print("=" * 60)

            resp = (
                input("\n[e]nviada / [d]escartada / [s]altar / [q]salir: ")
                .strip()
                .lower()
            )
            if resp == "q":
                break
            if resp == "e":
                conn.execute(
                    "UPDATE vacantes SET estado_aplicacion = 'enviada' WHERE id_dedup = ?",
                    (v["id_dedup"],),
                )
                conn.commit()
            elif resp == "d":
                conn.execute(
                    "UPDATE vacantes SET estado_aplicacion = 'descartada' WHERE id_dedup = ?",
                    (v["id_dedup"],),
                )
                conn.commit()

    except KeyboardInterrupt:
        print("\n\nInterrumpido. Lo marcado hasta ahora ya quedó guardado.")

    conn.close()


if __name__ == "__main__":
    main()
