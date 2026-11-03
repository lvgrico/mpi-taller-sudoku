# Tarea 3: combinar tableros y ramas

`mpi_hibrido.py` divide los `N` procesos en `G = N // tam_grupo` grupos (los sobrantes se suman al último). El líder de cada grupo pide IDs al despachador global (el proceso 0, que además es líder del grupo 0), reparte las ramas del tablero entre los procesos de su grupo y cancela al grupo cuando se halla la solución. Todos los procesos, incluidos los líderes, exploran ramas.

## Cómo elegí el tamaño de grupo

`--tam-grupo` fija el equilibrio entre dos efectos. Con grupos pequeños (muchos grupos) se resuelven varios tableros a la vez y casi no se cancela trabajo, pero un tablero difícil puede dejar a los demás grupos esperando al final. Con grupos grandes cada tablero termina antes, pero hay más mensajes y se exploran ramas que luego se cancelan. `tam-grupo = 1` equivale a repartir solo tableros y `tam-grupo = N` a repartir solo ramas.

Con `N = 8` (valor elegido en la calibración) probé todos sus divisores, una ejecución con `--all` por valor:

| tam-grupo | grupos | Tiempo total (s) |
| ---: | ---: | ---: |
| 1 | 8 | 31,55 |
| 2 | 4 | 26,44 |
| 4 | 2 | 25,76 |
| 8 | 1 | 26,17 |

Elegí `tam-grupo = 4` porque obtuvo el menor tiempo total (25,76 s). Las diferencias entre 2, 4 y 8 son menores al 3 %, así que esos tres tamaños son prácticamente equivalentes; el tamaño 1 (solo repartir tableros) fue claramente peor porque los tableros más largos (por ejemplo, los IDs 3 y 8, de unos 16 s en esa ejecución) dejan al resto de procesos sin trabajo al final.

## Ejecutar con el contenedor

```bash
# Todos los tableros (N = 8, grupos de 4)
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n 8 python /app/mpi_hibrido/mpi_hibrido.py --all --tam-grupo 4

# Un tablero (ID 7)
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n 8 python /app/mpi_hibrido/mpi_hibrido.py --id 7 --tam-grupo 4
```

En PowerShell usa `"${PWD}:/app"` en lugar de `"$(pwd):/app"`.

Resultados comparados con las otras estrategias: ver `../INFORME.md`.
