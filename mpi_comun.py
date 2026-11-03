"""Utilidades compartidas por las implementaciones MPI del taller de Sudoku.

Contiene:
  - esperar(): recepción que duerme entre sondeos (no consume CPU al esperar).
  - resolver_cancelable(): el mismo backtracking de sudoku.py, pero que
    consulta cada cierto número de nodos si debe abandonar la búsqueda.
  - generar_ramas(): divide un tablero en ramas (opciones válidas de las
    primeras casillas vacías, en el mismo orden que el backtracking serial).
  - lider_resolver() / bucle_trabajador(): protocolo líder-trabajadores que
    reparte las ramas de UN tablero entre los procesos de un comunicador.
"""

import time
from collections import deque

from mpi4py import MPI

from sudoku import puede_colocar

# Etiquetas de mensajes dentro de un grupo
T_TASK, T_RES, T_CANCEL, T_SALIR = 11, 12, 13, 14
# Etiquetas entre líderes de grupo y el despachador global (híbrido)
T_PEDIR, T_ASIGNA = 21, 22

PAUSA = 0.0003        # segundos de espera entre sondeos
INTERVALO_CHEQUEO = 100  # nodos de backtracking entre consultas de mensajes


class Cancelado(Exception):
    """Se lanza para abandonar una rama cuando otro proceso ya halló la solución."""


# ---------------------------------------------------------------- utilidades
def esperar(comm, fuente=MPI.ANY_SOURCE, etiqueta=MPI.ANY_TAG, extra=None):
    """Espera un mensaje durmiendo entre sondeos. Devuelve (fuente, etiqueta, dato).

    `extra` es una función opcional que se invoca mientras se espera
    (por ejemplo, para seguir atendiendo peticiones de otros procesos).
    """
    estado = MPI.Status()
    while not comm.iprobe(source=fuente, tag=etiqueta, status=estado):
        if extra is not None:
            extra()
        time.sleep(PAUSA)
    dato = comm.recv(source=estado.source, tag=estado.tag)
    return estado.source, estado.tag, dato


def es_solucion_valida(tablero):
    """Comprueba que el tablero completo cumple filas, columnas y bloques."""
    objetivo = set(range(1, 10))
    for i in range(9):
        if set(tablero[i]) != objetivo:
            return False
        if {tablero[f][i] for f in range(9)} != objetivo:
            return False
    for bf in range(0, 9, 3):
        for bc in range(0, 9, 3):
            bloque = {tablero[f][c] for f in range(bf, bf + 3) for c in range(bc, bc + 3)}
            if bloque != objetivo:
                return False
    return True


# ------------------------------------------------------- solver cancelable
def resolver_cancelable(tablero, chequear, intervalo=INTERVALO_CHEQUEO):
    """Backtracking idéntico a sudoku.resolver (mismo orden de búsqueda).

    Cada `intervalo` nodos llama a chequear(); si esa función lanza
    Cancelado, la búsqueda se abandona. Resuelve in situ.
    """
    nodos = 0

    def buscar():
        nonlocal nodos
        nodos += 1
        if nodos % intervalo == 0:
            chequear()
        for fila in range(9):
            for columna in range(9):
                if tablero[fila][columna] != 0:
                    continue
                for valor in range(1, 10):
                    if puede_colocar(tablero, fila, columna, valor):
                        tablero[fila][columna] = valor
                        if buscar():
                            return True
                        tablero[fila][columna] = 0
                return False
        return True

    return buscar()


# --------------------------------------------------------- generar ramas
def _primera_vacia(tablero):
    for fila in range(9):
        for columna in range(9):
            if tablero[fila][columna] == 0:
                return fila, columna
    return None


def generar_ramas(tablero, minimo):
    """Divide el tablero en al menos `minimo` ramas (si es posible).

    Se expande, nivel a nivel, la primera casilla vacía de cada rama con sus
    valores válidos. Se conserva el orden lexicográfico del backtracking
    serial, de modo que las primeras ramas son las que el serial exploraría
    primero. Cada rama es un tablero parcial independiente.
    """
    frontera = [[fila[:] for fila in tablero]]
    while len(frontera) < minimo:
        nueva, expandido = [], False
        for rama in frontera:
            posicion = _primera_vacia(rama)
            if posicion is None:
                nueva.append(rama)  # ya está completa
                continue
            expandido = True
            fila, columna = posicion
            for valor in range(1, 10):
                if puede_colocar(rama, fila, columna, valor):
                    hija = [f[:] for f in rama]
                    hija[fila][columna] = valor
                    nueva.append(hija)
        frontera = nueva
        if not expandido:
            break
    return frontera


# ------------------------------------------------- protocolo por grupos
def bucle_trabajador(comm):
    """Bucle de un trabajador: resuelve ramas que le envía el líder (rango 0)."""
    while True:
        _, etiqueta, dato = esperar(comm, 0, MPI.ANY_TAG)
        if etiqueta == T_SALIR:
            return
        if etiqueta != T_TASK:
            continue  # cancelación atrasada de un tablero ya terminado
        epoca, rama = dato

        def chequear():
            if comm.iprobe(source=0, tag=T_CANCEL):
                if comm.recv(source=0, tag=T_CANCEL) == epoca:
                    raise Cancelado()

        try:
            ok = resolver_cancelable(rama, chequear)
            respuesta = ("ok" if ok else "no", rama if ok else None, epoca)
        except Cancelado:
            respuesta = ("cancelado", None, epoca)
        comm.send(respuesta, dest=0, tag=T_RES)


def finalizar_trabajadores(comm):
    """El líder indica a sus trabajadores que terminen."""
    for destino in range(1, comm.size):
        comm.send(None, dest=destino, tag=T_SALIR)


def lider_resolver(comm, tablero, epoca, minimo_ramas, extra=None):
    """Resuelve un tablero repartiendo sus ramas entre los procesos de `comm`.

    Se ejecuta en el líder (rango 0 del comunicador). El líder también explora
    ramas y, cada pocos nodos, atiende a los trabajadores. Devuelve la
    solución (lista de listas) o None si el tablero no tiene solución.
    `extra` se invoca periódicamente (lo usa el híbrido para atender al
    despachador global desde el proceso 0).
    """
    cola = deque(generar_ramas(tablero, minimo_ramas))
    ocupados = set()
    estado = {"solucion": None}

    def despachar(trabajador):
        if cola and estado["solucion"] is None:
            comm.send((epoca, cola.popleft()), dest=trabajador, tag=T_TASK)
            ocupados.add(trabajador)

    def cancelar_todos():
        for trabajador in ocupados:
            comm.send(epoca, dest=trabajador, tag=T_CANCEL)

    def atender():
        estatus = MPI.Status()
        while comm.iprobe(source=MPI.ANY_SOURCE, tag=T_RES, status=estatus):
            trabajador = estatus.source
            veredicto, solucion, _ = comm.recv(source=trabajador, tag=T_RES)
            ocupados.discard(trabajador)
            if veredicto == "ok" and estado["solucion"] is None:
                estado["solucion"] = solucion
                cancelar_todos()
            elif estado["solucion"] is None:
                despachar(trabajador)
        if extra is not None:
            extra()

    def chequear():
        atender()
        if estado["solucion"] is not None:
            raise Cancelado()

    for trabajador in range(1, comm.size):
        despachar(trabajador)

    # El líder también explora ramas.
    while cola and estado["solucion"] is None:
        rama = cola.popleft()
        try:
            if resolver_cancelable(rama, chequear):
                estado["solucion"] = rama
                cancelar_todos()
        except Cancelado:
            break

    # Esperar a que todos los trabajadores ocupados respondan (terminen o cancelen).
    while ocupados:
        atender()
        if ocupados:
            time.sleep(PAUSA)
    return estado["solucion"]
