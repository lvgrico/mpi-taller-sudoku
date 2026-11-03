# Tarea 2: repartir ramas de cada tablero

`mpi_por_ramas.py` recorre los IDs **en orden**. Para cada tablero, el proceso 0 (coordinador) lo divide en ramas: expande, nivel a nivel, las primeras casillas vacías con sus valores válidos hasta tener al menos `--ramas-por-proceso × N` ramas (por defecto 8 por proceso), conservando el orden del backtracking serial. Las reparte bajo demanda; cada proceso explora su rama con el mismo backtracking de `sudoku.py` (versión en `../mpi_comun.py` que consulta mensajes cada 100 nodos). Cuando un proceso halla la solución, el coordinador envía una cancelación y todos abandonan; el siguiente tablero no empieza hasta que todos hayan respondido. El coordinador también explora ramas, así que trabajan los `N` procesos.

Imprime estado y tiempo parcial de cada ID, y el tiempo total real de los 30.

## Ejecutar con el contenedor

```bash
# Todos los tableros (uno tras otro, ramas en paralelo)
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n 8 python /app/mpi_por_ramas/mpi_por_ramas.py --all

# Un tablero (ID 7)
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n 8 python /app/mpi_por_ramas/mpi_por_ramas.py --id 7
```

Resultados: ver `../INFORME.md`.
