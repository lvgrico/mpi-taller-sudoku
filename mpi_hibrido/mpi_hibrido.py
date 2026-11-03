"""MPI híbrido: reparto de IDs entre grupos y de ramas dentro de cada grupo.

Los N procesos se dividen en G = N // tam_grupo grupos (los procesos sobrantes
se suman al último grupo). El primer proceso de cada grupo es su líder:
  - pide tableros al despachador global (el líder del grupo 0, proceso 0),
  - divide el tablero en ramas y las reparte entre los procesos de su grupo,
  - cancela al grupo cuando se halla la solución.
Los líderes también exploran ramas, así que trabajan los N procesos.
tam_grupo = 1 equivale a "por tableros" y tam_grupo = N a "por ramas".
"""

import argparse
import sys
import time
from collections import deque
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mpi4py import MPI  # noqa: E402

from baseline_secuencial import leer_seeds  # noqa: E402
from mpi_comun import (PAUSA, T_ASIGNA, T_PEDIR, bucle_trabajador,  # noqa: E402
                       es_solucion_valida, esperar, finalizar_trabajadores,
                       lider_resolver)


def resolver_en_grupo(grupo, tablero, epoca, minimo, extra=None):
    inicio = time.perf_counter()
    solucion = lider_resolver(grupo, tablero, epoca, minimo, extra)
    segundos = time.perf_counter() - inicio
    return solucion is not None and es_solucion_valida(solucion), segundos


def imprimir(nombre, resuelto, segundos, grupo, parcial):
    etiqueta = "Tiempo parcial" if parcial else "Tiempo"
    print(f"\nID: {nombre}  (grupo {grupo})")
    print("Resuelto" if resuelto else "Sin solución")
    print(f"{etiqueta}: {segundos:.6f} segundos", flush=True)


def main():
    mundo = MPI.COMM_WORLD
    parser = argparse.ArgumentParser(description="Sudoku MPI híbrido (grupos).")
    parser.add_argument("--archivo", type=Path, default=RAIZ / "seeds.txt")
    parser.add_argument("--tam-grupo", type=int, default=2,
                        help="procesos por grupo (def. 2); 1 = solo tableros")
    parser.add_argument("--ramas-por-proceso", type=int, default=8,
                        help="mínimo de ramas por proceso del grupo (def. 8)")
    seleccion = parser.add_mutually_exclusive_group()
    seleccion.add_argument("--id", "--seed", dest="id", help="resolver solo este ID")
    seleccion.add_argument("--all", action="store_true", help="resolver todos los IDs")
    args = parser.parse_args()

    tam = max(1, min(args.tam_grupo, mundo.size))
    grupos = mundo.size // tam
    color = min(mundo.rank // tam, grupos - 1)
    grupo = mundo.Split(color, mundo.rank)
    mundo.Barrier()  # todos los procesos listos antes de medir
    es_lider = grupo.rank == 0
    minimo = max(1, args.ramas_por_proceso * grupo.size)

    if not es_lider:
        bucle_trabajador(grupo)
        return

    parcial = not args.id
    if mundo.rank != 0:
        # Líder de un grupo distinto del 0: pide tableros al despachador.
        resultado, epoca = None, 0
        while True:
            mundo.send(resultado, dest=0, tag=T_PEDIR)
            _, _, asignacion = esperar(mundo, 0, T_ASIGNA)
            if asignacion is None:
                break
            nombre, tablero = asignacion
            resuelto, segundos = resolver_en_grupo(grupo, tablero, epoca, minimo)
            resultado = (nombre, resuelto, segundos, color)
            epoca += 1
        finalizar_trabajadores(grupo)
        return

    # ---- Proceso 0: despachador global y líder del grupo 0 ----
    seeds = leer_seeds(args.archivo)
    error = None
    if args.id and args.id not in seeds:
        error = f"ID '{args.id}' no existe. Disponibles: {', '.join(seeds)}"
        ids = []  # nadie recibe trabajo; todos terminan limpiamente
    elif args.id:
        ids = [args.id]
    else:
        ids = list(seeds)

    cola = deque(ids)
    resultados = {}
    lideres_despedidos = set()
    otros_lideres = grupos - 1

    def registrar(res):
        nombre, resuelto, segundos, g = res
        resultados[nombre] = resuelto
        imprimir(nombre, resuelto, segundos, g, parcial)

    def atender_global():
        estado = MPI.Status()
        while mundo.iprobe(source=MPI.ANY_SOURCE, tag=T_PEDIR, status=estado):
            origen = estado.source
            previo = mundo.recv(source=origen, tag=T_PEDIR)
            if previo is not None:
                registrar(previo)
            if cola:
                nombre = cola.popleft()
                mundo.send((nombre, [f[:] for f in seeds[nombre]]), dest=origen, tag=T_ASIGNA)
            else:
                mundo.send(None, dest=origen, tag=T_ASIGNA)
                lideres_despedidos.add(origen)

    inicio_total = time.perf_counter()
    epoca = 0
    while cola:
        nombre = cola.popleft()
        tablero = [fila[:] for fila in seeds[nombre]]
        resuelto, segundos = resolver_en_grupo(grupo, tablero, epoca, minimo, atender_global)
        epoca += 1
        registrar((nombre, resuelto, segundos, color))
        atender_global()
    while len(lideres_despedidos) < otros_lideres or len(resultados) < len(ids):
        atender_global()
        time.sleep(PAUSA)
    total = time.perf_counter() - inicio_total
    finalizar_trabajadores(grupo)
    if error:
        parser.error(error)

    if not args.id:
        print(f"\nTableros procesados: {len(resultados)} de {len(ids)} "
              f"(resueltos: {sum(resultados.values())})")
        print(f"Procesos: {mundo.size}; grupos: {grupos}; tamaño de grupo: {tam}")
        print(f"\nTiempo total: {total:.6f} segundos")


if __name__ == "__main__":
    main()
