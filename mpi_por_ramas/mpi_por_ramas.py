"""MPI por ramas: los tableros se resuelven uno tras otro y las ramas de cada
tablero se reparten entre todos los procesos.

El proceso 0 (coordinador) lee los IDs en orden, divide cada tablero en ramas
(opciones válidas de sus primeras casillas vacías), las reparte bajo demanda y,
cuando alguien halla la solución, cancela al resto. Hasta que todos los
procesos terminan o cancelan, no empieza el siguiente tablero. El coordinador
también explora ramas, por lo que trabajan los N procesos.
"""

import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mpi4py import MPI  # noqa: E402

from baseline_secuencial import leer_seeds  # noqa: E402
from mpi_comun import (bucle_trabajador, es_solucion_valida,  # noqa: E402
                       finalizar_trabajadores, lider_resolver)


def main():
    comm = MPI.COMM_WORLD
    parser = argparse.ArgumentParser(description="Sudoku MPI: reparto de ramas.")
    parser.add_argument("--archivo", type=Path, default=RAIZ / "seeds.txt")
    parser.add_argument("--ramas-por-proceso", type=int, default=8,
                        help="mínimo de ramas por proceso en cada tablero (def. 8)")
    seleccion = parser.add_mutually_exclusive_group()
    seleccion.add_argument("--id", "--seed", dest="id", help="resolver solo este ID")
    seleccion.add_argument("--all", action="store_true", help="resolver todos los IDs")
    args = parser.parse_args()

    if comm.rank != 0:
        bucle_trabajador(comm)
        return

    seeds = leer_seeds(args.archivo)
    if args.id:
        if args.id not in seeds:
            finalizar_trabajadores(comm)
            parser.error(f"ID '{args.id}' no existe. Disponibles: {', '.join(seeds)}")
        ids = [args.id]
    else:
        ids = list(seeds)

    minimo = max(1, args.ramas_por_proceso * comm.size)
    resueltos = 0
    inicio_total = time.perf_counter()
    for epoca, nombre in enumerate(ids):
        tablero = [fila[:] for fila in seeds[nombre]]
        inicio = time.perf_counter()
        solucion = lider_resolver(comm, tablero, epoca, minimo)
        segundos = time.perf_counter() - inicio
        ok = solucion is not None and es_solucion_valida(solucion)
        resueltos += ok
        print(f"\nID: {nombre}")
        print("Resuelto" if ok else "Sin solución")
        etiqueta = "Tiempo" if args.id else "Tiempo parcial"
        print(f"{etiqueta}: {segundos:.6f} segundos", flush=True)
    total = time.perf_counter() - inicio_total
    finalizar_trabajadores(comm)

    if not args.id:
        print(f"\nTableros procesados: {len(ids)} de {len(ids)} (resueltos: {resueltos})")
        print(f"Procesos: {comm.size}")
        print(f"\nTiempo total: {total:.6f} segundos")


if __name__ == "__main__":
    main()
