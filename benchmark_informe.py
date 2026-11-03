"""Mide secuencial y las tres versiones MPI (3 repeticiones, mediana) y
genera la tabla del informe. Ejecutar dentro del contenedor:

  python /app/benchmark_informe.py --n 8 [--tam-grupo 2]
"""

import argparse
import re
import statistics
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
MPI = ["mpiexec", "--allow-run-as-root", "--use-hwthread-cpus", "--oversubscribe"]


def tiempo_total(comando):
    salida = subprocess.run(comando, capture_output=True, text=True)
    if salida.returncode != 0:
        sys.exit(salida.stderr or salida.stdout)
    if "Tableros procesados: 30 de 30" not in salida.stdout and "baseline" not in " ".join(comando):
        sys.exit("No se procesaron los 30 tableros:\n" + salida.stdout[-500:])
    return float(re.search(r"Tiempo total: ([\d.]+)", salida.stdout).group(1))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, required=True, help="N elegido con detectar_procesos_mpi.py")
    p.add_argument("--tam-grupo", type=int, default=2)
    p.add_argument("--repeticiones", type=int, default=3)
    a = p.parse_args()
    py = sys.executable
    casos = [
        ("Secuencial", 1, [py, str(RAIZ / "baseline_secuencial.py"), "--all"]),
        ("MPI por tableros", a.n, MPI + ["-n", str(a.n), py, str(RAIZ / "mpi_por_tableros/mpi_por_tableros.py"), "--all"]),
        ("MPI por ramas", a.n, MPI + ["-n", str(a.n), py, str(RAIZ / "mpi_por_ramas/mpi_por_ramas.py"), "--all"]),
        ("MPI híbrido", a.n, MPI + ["-n", str(a.n), py, str(RAIZ / "mpi_hibrido/mpi_hibrido.py"), "--all", "--tam-grupo", str(a.tam_grupo)]),
    ]
    medianas = {}
    for nombre, procs, cmd in casos:
        tiempos = []
        for i in range(a.repeticiones):
            t = tiempo_total(cmd)
            tiempos.append(t)
            print(f"{nombre} (rep {i + 1}): {t:.2f} s", flush=True)
        medianas[nombre] = (procs, statistics.median(tiempos), tiempos)
    base = medianas["Secuencial"][1]
    print("\n| Implementación | Caso | Procesos | Mediana del tiempo total (s) | Aceleración frente a secuencial |")
    print("| --- | --- | ---: | ---: | ---: |")
    casos_txt = {"Secuencial": "Todos los IDs", "MPI por tableros": "Todos los IDs",
                 "MPI por ramas": "Todos los IDs, uno después de otro", "MPI híbrido": "Todos los IDs"}
    for nombre, (procs, med, _) in medianas.items():
        fila = f"| {nombre} | {casos_txt[nombre]} | {procs} | {med:.2f} | {base / med:.2f} |"
        print(fila.replace(".", ","))


if __name__ == "__main__":
    main()
