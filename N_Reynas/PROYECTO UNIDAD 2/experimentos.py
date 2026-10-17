"""Experimentos reproducibles para comparar 2-opt y búsqueda tabú.

K es el número de mejores movimientos admisibles entre los que la búsqueda
tabú elige aleatoriamente en cada iteración. El costo se mide con la matriz de
combustible cargada por el proyecto (0.15 x km); las distancias se usan para
zonificar y construir el inicio cercano.

Importante: la búsqueda global necesita unas 200 a 600 iteraciones para
converger, así que los experimentos usan por defecto 1000 iteraciones máximas y
paran tras 150 sin mejora. Con límites muy bajos (por ejemplo 30 iteraciones) la
búsqueda se corta antes de terminar y la tabla compara velocidad de descenso,
no calidad final.

Con inicio "cercano" y K=1 el resultado es determinista (la semilla solo
desempata), por eso esa combinación se corre una sola vez. Las demás se repiten.

Uso desde la carpeta del proyecto:
    python experimentos.py
    python experimentos.py --repeticiones 3 --procesos 2
    python experimentos.py --max-iter 30 --sin-mejora 30      # corrida rápida de prueba
"""

from __future__ import annotations

import argparse
import itertools
import random
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from cargar_datos import cargar_datos
from rutas import FACTOR_COMBUSTIBLE, costo_ruta, dos_opt, vecino_mas_cercano
from tabu import busqueda_tabu_ruta
from tabu_global import busqueda_tabu_global
from Zonificar import asignar_zonas


BASE = Path(__file__).resolve().parent
ARCHIVO_NODOS = BASE / "datos_distribucion_tiendas.xlsx"
ARCHIVO_SALIDA = BASE / "Resultados_Experimentos.xlsx"
TENENCIAS = (10, 30, 60)
VALORES_K = (1, 10)
MINIMOS = (1, 3, 5)
INICIOS = ("cercano", "aleatorio")


def _cargar():
    nodos, distancias, costos, cedis, tiendas = cargar_datos(ARCHIVO_NODOS)
    zonas = asignar_zonas(distancias, n_cedis=len(cedis))
    return nodos, distancias, costos, zonas


def comparar_2opt_tabu(distancias, costos, zonas, max_iter=300, max_sin_mejora=100,
                       semilla=2026):
    """Compara 2-opt determinista y tabú 2-opt en zonas fijas.

    `mejora_vs_vecino_pct` mide contra el vecino más cercano (la referencia del informe);
    `ahorro_pct` mide contra el punto de partida de cada fila, que con inicio aleatorio
    es una ruta mala a propósito y por eso da porcentajes inflados.
    """
    referencia = sum(
        costo_ruta(distancias, c, vecino_mas_cercano(distancias, c, t), costos=costos)
        for c, t in zonas.items()
    )
    filas = []
    for inicio in INICIOS:
        rutas_inicio = {}
        rng = random.Random(semilla + (1 if inicio == "aleatorio" else 0))
        for cedis, tiendas in zonas.items():
            ruta = (vecino_mas_cercano(distancias, cedis, tiendas)
                    if inicio == "cercano" else rng.sample(list(tiendas), len(tiendas)))
            rutas_inicio[cedis] = ruta

        for metodo in ("2-opt", "Tabú 2-opt"):
            costo_inicial = 0.0
            costo_final = 0.0
            tiempo_total = 0.0
            iteraciones = 0
            for cedis, ruta in rutas_inicio.items():
                inicial = costo_ruta(distancias, cedis, ruta, costos=costos)
                t0 = time.perf_counter()
                if metodo == "2-opt":
                    resultado = dos_opt(distancias, cedis, ruta, costos=costos)
                    final = costo_ruta(distancias, cedis, resultado, costos=costos)
                else:
                    resultado = busqueda_tabu_ruta(
                        distancias, cedis, zonas[cedis], tenencia=10,
                        max_iter=max_iter, max_sin_mejora=max_sin_mejora,
                        semilla=semilla + cedis, ruta_inicial=ruta, costos=costos,
                    )
                    final = resultado.mejor_costo
                    iteraciones += resultado.iteraciones
                tiempo_total += time.perf_counter() - t0
                costo_inicial += inicial
                costo_final += final
            filas.append({
                "inicio": inicio,
                "metodo": metodo,
                "costo_inicial": costo_inicial,
                "costo_final": costo_final,
                "km_final": costo_final / FACTOR_COMBUSTIBLE,
                "ahorro_pct": (100 * (costo_inicial - costo_final) / costo_inicial
                               if costo_inicial else 0.0),
                "mejora_vs_vecino_pct": 100 * (referencia - costo_final) / referencia,
                "iteraciones_tabu": iteraciones,
                "tiempo_segundos": tiempo_total,
                "tenencia": 10 if metodo == "Tabú 2-opt" else None,
                "K": None,
            })
    return pd.DataFrame(filas)


def _corrida_global(argumentos):
    """Una corrida de la búsqueda global (función de nivel superior para poder paralelizarla)."""
    (distancias, costos, zonas, tenencia, k, minimo, inicio,
     repeticion, semilla_corrida, max_iter, max_sin_mejora) = argumentos
    resultado = busqueda_tabu_global(
        distancias, zonas, tenencia=tenencia, k=k,
        max_iter=max_iter, max_sin_mejora=max_sin_mejora,
        min_tiendas=minimo, inicio=inicio, semilla=semilla_corrida, costos=costos,
    )
    return {
        "tenencia": tenencia,
        "K": k,
        "min_tiendas": minimo,
        "inicio": inicio,
        "repeticion": repeticion + 1,
        "costo_inicial": resultado.costo_inicial,
        "costo_final": resultado.mejor_costo,
        "km_final": resultado.mejor_costo / FACTOR_COMBUSTIBLE,
        "ahorro_pct": (100 * (resultado.costo_inicial - resultado.mejor_costo)
                       / resultado.costo_inicial if resultado.costo_inicial else 0.0),
        "iteraciones": resultado.iteraciones,
        "iter_mejor": resultado.iter_mejor,
        "tiempo_segundos": resultado.tiempo,
    }


def sensibilidad_global(distancias, costos, zonas, max_iter=1000, max_sin_mejora=150,
                        repeticiones=5, semilla=2026, procesos=2):
    """Evalúa tenencia, K, mínimos por CEDIS y tipo de solución inicial."""
    trabajos = []
    configuraciones = itertools.product(TENENCIAS, VALORES_K, MINIMOS, INICIOS)
    for indice, (tenencia, k, minimo, inicio) in enumerate(configuraciones, 1):
        # con inicio cercano y K=1 no hay azar: una sola corrida basta
        veces = 1 if (k == 1 and inicio == "cercano") else repeticiones
        for repeticion in range(veces):
            trabajos.append((distancias, costos, zonas, tenencia, k, minimo, inicio,
                             repeticion, semilla + indice * 101 + repeticion,
                             max_iter, max_sin_mejora))
    print(f"Sensibilidad global: {len(trabajos)} corridas "
          f"(max_iter={max_iter}, sin mejora={max_sin_mejora}, procesos={procesos})")
    if procesos > 1:
        with ProcessPoolExecutor(procesos) as pool:
            filas = list(pool.map(_corrida_global, trabajos))
    else:
        filas = [_corrida_global(t) for t in trabajos]
    return pd.DataFrame(filas)


def ejecutar_experimentos(max_iter=1000, max_sin_mejora=150, repeticiones=5, semilla=2026,
                          salida=ARCHIVO_SALIDA, procesos=2):
    """Corre los experimentos y guarda resultados detallados y promedios."""
    _, distancias, costos, zonas = _cargar()
    comparacion = comparar_2opt_tabu(distancias, costos, zonas, semilla=semilla)
    sensibilidad = sensibilidad_global(
        distancias, costos, zonas, max_iter=max_iter, max_sin_mejora=max_sin_mejora,
        repeticiones=repeticiones, semilla=semilla, procesos=procesos,
    )
    columnas = ["tenencia", "K", "min_tiendas", "inicio"]
    promedios = (sensibilidad.groupby(columnas, as_index=False)
                 .agg(corridas=("costo_final", "size"),
                      km_promedio=("km_final", "mean"),
                      km_minimo=("km_final", "min"),
                      km_maximo=("km_final", "max"),
                      costo_final_promedio=("costo_final", "mean"),
                      ahorro_promedio_pct=("ahorro_pct", "mean"),
                      iteraciones_promedio=("iteraciones", "mean"),
                      tiempo_promedio_segundos=("tiempo_segundos", "mean")))
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(salida) as writer:
        comparacion.to_excel(writer, sheet_name="2-opt_vs_tabu", index=False)
        sensibilidad.to_excel(writer, sheet_name="Sensibilidad_detalle", index=False)
        promedios.to_excel(writer, sheet_name="Sensibilidad_promedios", index=False)
    print(f"Resultados guardados en: {salida}")
    return comparacion, sensibilidad, promedios


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-iter", type=int, default=1000,
                        help="máximo de iteraciones de la búsqueda global (default: 1000)")
    parser.add_argument("--sin-mejora", type=int, default=150,
                        help="iteraciones sin mejora para parar (default: 150)")
    parser.add_argument("--repeticiones", type=int, default=5,
                        help="repeticiones de cada configuración con azar (default: 5)")
    parser.add_argument("--procesos", type=int, default=2,
                        help="procesos en paralelo (default: 2; usa 1 si da problemas)")
    parser.add_argument("--semilla", type=int, default=2026)
    parser.add_argument("--salida", type=Path, default=ARCHIVO_SALIDA)
    args = parser.parse_args()
    ejecutar_experimentos(args.max_iter, args.sin_mejora, args.repeticiones, args.semilla,
                          args.salida, args.procesos)


if __name__ == "__main__":
    main()
