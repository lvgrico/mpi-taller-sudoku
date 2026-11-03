# Tarea 1: repartir tableros

`mpi_por_tableros.py` convierte cada ID en una tarea. El proceso 0 es el **coordinador**: asigna IDs bajo demanda (el primer proceso libre recibe el siguiente tablero, lo que compensa que unos tableros tarden 2 s y otros 10 s) y reúne los estados. Los demás procesos resuelven con `resolver_con_tiempo` de `../sudoku.py`. El coordinador solo duerme esperando mensajes, así que trabajan `N-1` procesos. Con `N = 1` resuelve en serie.

Al final imprime `Tableros procesados: 30 de 30`, y el **tiempo total real** (reloj de pared del coordinador desde que reparte hasta que llegan los 30 resultados).

## Ejecutar con el contenedor

Cambia `8` por el `N` elegido con `detectar_procesos_mpi.py`. En PowerShell usa `"${PWD}:/app"`; en macOS `"$(pwd):/app"`.

```bash
# Todos los tableros
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n 8 python /app/mpi_por_tableros/mpi_por_tableros.py --all

# Un tablero (ID 7)
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n 8 python /app/mpi_por_tableros/mpi_por_tableros.py --id 7
```

Resultados: ver `../INFORME.md`.
