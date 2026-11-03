# Informe de resultados

## Entorno

- Equipo: AMD Ryzen 7 7735HS (8 núcleos físicos / 16 hilos), unos 19,7 GB de RAM utilizable, Windows + Docker Desktop
- Versión del contenedor: `augustosalazar/slim-mpi:2`
- Cantidad de repeticiones por medición: 3
- Valor común de `N` elegido: **8** (calibración con `detectar_procesos_mpi.py`: `nproc = 16`, mediana más baja 1,692 s con N = 8)

## Cómo se midió

Todas las ejecuciones usan el mismo `seeds.txt` (30 tableros), el mismo equipo y el contenedor del taller. Cada caso se repitió tres veces con `benchmark_informe.py --n 8 --tam-grupo 4` y se reporta la mediana. Los tres programas MPI se lanzaron con `mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n 8`. El tiempo MPI es el reloj real del coordinador desde que empieza el reparto hasta que llegan los 30 resultados (no la suma de los tiempos de cada proceso). En las tres versiones MPI se confirmó `Tableros procesados: 30 de 30`.

El tamaño de grupo del híbrido se eligió probando los divisores de 8 (una sola ejecución por valor, ver `mpi_hibrido/README.md`): 1 → 31,55 s, 2 → 26,44 s, 4 → 25,76 s, 8 → 26,17 s. Se usó `tam-grupo = 4`, el de menor tiempo.

## Comparación final con el mismo `N`

| Implementación | Caso | Procesos | Mediana del tiempo total (s) | Aceleración frente a secuencial |
| --- | --- | ---: | ---: | ---: |
| Secuencial | Todos los IDs | 1 | 89,59 | 1,00 |
| MPI por tableros | Todos los IDs | 8 | 29,76 | 3,01 |
| MPI por ramas | Todos los IDs, uno después de otro | 8 | 25,90 | 3,46 |
| MPI híbrido | Todos los IDs | 8 | 26,94 | 3,33 |

Mediciones individuales (s): secuencial 89,45 / 90,02 / 89,59; por tableros 29,34 / 30,01 / 29,76; por ramas 26,39 / 25,62 / 25,90; híbrido 26,21 / 26,94 / 27,19.

La aceleración se calcula como `tiempo secuencial / tiempo MPI`.

## Conclusiones

- **Mejor estrategia.** MPI por ramas obtuvo el menor tiempo: 25,90 s frente a 89,59 s del secuencial, es decir, un 71 % menos de tiempo y una aceleración de 3,46. Le siguieron el híbrido (26,94 s, 3,33) y por tableros (29,76 s, 3,01). La diferencia entre ramas e híbrido es pequeña (alrededor de 4 %, y sus mediciones casi se solapan), así que se pueden considerar prácticamente equivalentes; por tableros sí quedó claramente detrás (alrededor de 15 % más lento que ramas).
- **Límite de la máquina.** Ninguna versión se acerca a una aceleración de 8. La calibración muestra por qué: contar primos, una tarea sin comunicación y perfectamente repartible, pasó de 5,644 s con N = 1 a 1,692 s con N = 8, una aceleración de solo 3,34. Las tres implementaciones (3,01 a 3,46) quedan en ese mismo orden, así que gran parte de lo que "falta" para 8× lo pone el equipo, no los algoritmos: el procesador tiene 8 núcleos físicos y 16 hilos (cada par de hilos comparte un núcleo), y además Docker comparte los recursos con Windows y el procesador de un portátil limita su potencia y temperatura al cargar todos los núcleos. Es coherente que el N óptimo sea 8, igual al número de núcleos físicos, aunque haya 16 hilos.
- **Comunicación y diferencias de duración entre tableros.** En "por tableros" la duración desigual pesa más: en la ejecución con grupos de tamaño 1 (ocho procesos resolviendo un tablero cada uno) los IDs 3 y 8 tardaron 17,1 s y 16,2 s, mientras que muchos otros tardaron entre 4 y 7 s, y el tiempo total no puede bajar de lo que tarda el tablero más largo. Además, el coordinador de esa versión no resuelve, por lo que trabajan 7 procesos y no 8. En "por ramas" cada tablero usa los 8 procesos y ningún tablero dura mucho (con grupo de tamaño 8, el más largo tardó 1,9 s), así que no queda un "cola" desbalanceada. A cambio, cada tablero paga el costo de dividir las ramas, repartirlas y cancelar al resto cuando aparece la solución, y todos los procesos esperan al último antes de pasar al siguiente tablero; con tableros muy rápidos (el ID 6 tomó 0,06 s) ese costo fijo es relativamente mayor, pero los resultados muestran que su efecto total fue pequeño.
- **Repartir tableros vs. resolverlos en orden vs. híbrido.** Repartir tableros tiene poca comunicación (un mensaje por tablero) pero es sensible al desbalance; resolverlos en orden y repartir ramas equilibra mejor la carga a costa de más mensajes y de explorar ramas que luego se cancelan; el híbrido intenta combinar ambas cosas. En los tamaños de grupo probados (1, 2, 4 y 8) los tiempos con 2, 4 y 8 quedaron entre 25,8 s y 26,4 s (diferencias menores al 3 %, comparables con la variación entre repeticiones), y solo el tamaño 1 (solo repartir tableros) fue claramente peor (31,55 s). Con 30 tableros y 8 procesos, en este equipo el híbrido no superó a "por ramas": su ventaja teórica (menos esperas entre tableros) quedó dentro del margen de ruido.
