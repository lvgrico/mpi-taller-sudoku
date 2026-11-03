"""MPI por tableros: cada ID es una tarea que se asigna a un proceso libre.

El proceso 0 es el coordinador: reparte IDs bajo demanda (el primer trabajador
que queda libre recibe el siguiente tablero) y reúne los estados. Los demás
procesos resuelven con el resolvedor serial de ../sudoku.py.
"""

import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mpi4py import MPI  # noqa: E402

from baseline_secuencial import leer_seeds  # noqa: E402
from mpi_comun import PAUSA, es_solucion_valida, esperar  # noqa: E402
from sudoku import resolver_con_tiempo  # noqa: E402

T_PEDIR, T_ID, T_FIN = 1, 2, 3


def imprimir(nombre, resuelto, segundos, parcial):
    etiqueta = "Tiempo parcial" if parcial else "Tiempo"
    print(f"\nID: {nombre}")
    print("Resuelto" if resuelto else "Sin solución")
    print(f"{etiqueta}: {segundos:.6f} segundos", flush=True)


def coordinador(comm, seeds, ids, parcial):
    resultados = {}
    pendientes = list(ids)
    trabajadores_activos = comm.size - 1
    inicio = time.perf_counter()

    while len(resultados) < len(ids):
        origen, _, mensaje = esperar(comm, MPI.ANY_SOURCE, T_PEDIR)
        if mensaje is not None:  # el trabajador entrega un resultado
            nombre, resuelto, segundos = mensaje
            resultados[nombre] = (resuelto, segundos)
            imprimir(nombre, resuelto, segundos, parcial)
        if pendientes:
            comm.send(pendientes.pop(0), dest=origen, tag=T_ID)
        else:
            comm.send(None, dest=origen, tag=T_FIN)
            trabajadores_activos -= 1

    total = time.perf_counter() - inicio
    # Los trabajadores que aún no recibieron T_FIN lo reciben con su último pedido.
    while trabajadores_activos > 0:
        origen, _, _ = esperar(comm, MPI.ANY_SOURCE, T_PEDIR)
        comm.send(None, dest=origen, tag=T_FIN)
        trabajadores_activos -= 1
    return resultados, total


def trabajador(comm, seeds):
    mensaje = None
    while True:
        comm.send(mensaje, dest=0, tag=T_PEDIR)
        _, etiqueta, nombre = esperar(comm, 0, MPI.ANY_TAG)
        if etiqueta == T_FIN:
            return
        tablero = [fila[:] for fila in seeds[nombre]]
        resuelto, segundos = resolver_con_tiempo(tablero)
        resuelto = resuelto and es_solucion_valida(tablero)
        mensaje = (nombre, resuelto, segundos)


def main():
    comm = MPI.COMM_WORLD
    parser = argparse.ArgumentParser(description="Sudoku MPI: reparto de tableros.")
    parser.add_argument("--archivo", type=Path, default=RAIZ / "seeds.txt")
    seleccion = parser.add_mutually_exclusive_group()
    seleccion.add_argument("--id", "--seed", dest="id", help="resolver solo este ID")
    seleccion.add_argument("--all", action="store_true", help="resolver todos los IDs")
    args = parser.parse_args()

    seeds = leer_seeds(args.archivo)
    if args.id:
        if args.id not in seeds:
            if comm.rank == 0:
                parser.error(f"ID '{args.id}' no existe. Disponibles: {', '.join(seeds)}")
            return
        ids = [args.id]
    else:
        ids = list(seeds)

    if comm.size == 1:  # sin trabajadores: el único proceso resuelve en serie
        inicio = time.perf_counter()
        for nombre in ids:
            tablero = [fila[:] for fila in seeds[nombre]]
            resuelto, segundos = resolver_con_tiempo(tablero)
            imprimir(nombre, resuelto and es_solucion_valida(tablero), segundos, not args.id)
        total = time.perf_counter() - inicio
        resultados = {n: None for n in ids}
    else:
        comm.Barrier()
        if comm.rank == 0:
            resultados, total = coordinador(comm, seeds, ids, not args.id)
        else:
            trabajador(comm, seeds)
            return

    if not args.id:
        resueltos = sum(1 for r in resultados.values() if r is None or r[0])
        print(f"\nTableros procesados: {len(resultados)} de {len(ids)} "
              f"(resueltos: {resueltos})")
        print(f"Procesos: {comm.size}")
        print(f"\nTiempo total: {total:.6f} segundos")


if __name__ == "__main__":
    main()
