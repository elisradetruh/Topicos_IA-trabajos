"""Búsqueda tabú por ruta (2-opt), preservada del proyecto de referencia."""

import random
import time
from dataclasses import dataclass, field

from rutas import costo_ruta, vecino_mas_cercano


@dataclass
class ResultadoRuta:
    """Datos de una ejecución sobre la ruta de un CEDIS."""

    ruta_inicial: list
    mejor_ruta: list
    costo_inicial: float
    mejor_costo: float
    iteraciones: int
    iter_mejor: int
    evaluaciones: int
    tiempo: float
    historial_actual: list = field(default_factory=list)
    historial_mejor: list = field(default_factory=list)


def movimientos_2opt(n):
    """Todos los segmentos invertibles, excepto invertir la ruta completa."""
    return [(i, j) for i in range(n - 1) for j in range(i + 1, n)
            if not (i == 0 and j == n - 1)]


def aristas_2opt(ruta, cedis, i, j):
    """Aristas quitadas y agregadas al invertir ``ruta[i:j+1]``."""
    antes = cedis if i == 0 else ruta[i - 1]
    despues = cedis if j == len(ruta) - 1 else ruta[j + 1]
    quita = (frozenset((antes, ruta[i])), frozenset((ruta[j], despues)))
    agrega = (frozenset((antes, ruta[j])), frozenset((ruta[i], despues)))
    return quita, agrega, antes, despues


def delta_2opt(dist, ruta, cedis, i, j):
    """Cambio de costo por 2-opt en una matriz simétrica."""
    _, _, antes, despues = aristas_2opt(ruta, cedis, i, j)
    return (dist[antes, ruta[j]] + dist[ruta[i], despues]
            - dist[antes, ruta[i]] - dist[ruta[j], despues])


def busqueda_tabu_ruta(dist, cedis, tiendas, tenencia=7, max_iter=200,
                       max_sin_mejora=60, semilla=None, ruta_inicial=None,
                       costos=None, k=None):
    """Optimiza una ruta fija con 2-opt, memoria de aristas y aspiración.

    ``dist`` conserva su función original para el inicio por vecino más cercano.
    ``costos`` opcional permite optimizar combustible sin cambiar la zonificación.
    Si se omite, se mantiene la compatibilidad con la versión original.
    ``k`` limita la selección aleatoria a los K mejores movimientos admisibles;
    con ``None`` solo se consideran los movimientos con mejor delta (original).
    """
    rng = random.Random(semilla)
    matriz = dist if costos is None else costos
    if k is not None and k < 1:
        raise ValueError("K debe ser un entero positivo o None")
    actual = (list(ruta_inicial) if ruta_inicial is not None
              else vecino_mas_cercano(dist, cedis, tiendas))
    movimientos = movimientos_2opt(len(actual))

    inicio = time.perf_counter()
    ruta_ini = actual[:]
    costo_actual = costo_ruta(dist, cedis, actual, costos=matriz)
    costo_ini = costo_actual
    mejor, mejor_costo = actual[:], costo_actual
    tabu_hasta = {}
    evaluaciones = 0
    hist_actual, hist_mejor = [costo_actual], [mejor_costo]
    iteracion = 0
    iter_mejor = 0

    while (iteracion < max_iter and iteracion - iter_mejor < max_sin_mejora
           and movimientos):
        iteracion += 1
        candidatos = []
        for i, j in movimientos:
            delta = delta_2opt(matriz, actual, cedis, i, j)
            evaluaciones += 1
            _, agrega, _, _ = aristas_2opt(actual, cedis, i, j)
            es_tabu = any(tabu_hasta.get(arista, 0) > iteracion for arista in agrega)
            if es_tabu and not (costo_actual + delta < mejor_costo - 1e-9):
                continue
            candidatos.append((delta, (i, j)))

        if not candidatos:
            break

        candidatos.sort(key=lambda candidato: candidato[0])
        if k is None:
            delta_elegido = candidatos[0][0]
            mejores = [mov for delta, mov in candidatos
                       if abs(delta - delta_elegido) <= 1e-9]
            i, j = rng.choice(mejores)
        else:
            lista_candidatos = candidatos[:k]
            delta_elegido, (i, j) = rng.choice(lista_candidatos)
        quita, _, _, _ = aristas_2opt(actual, cedis, i, j)
        actual[i:j + 1] = actual[i:j + 1][::-1]
        costo_actual += delta_elegido
        for arista in quita:
            tabu_hasta[arista] = iteracion + tenencia

        if costo_actual < mejor_costo - 1e-9:
            mejor, mejor_costo = actual[:], costo_actual
            iter_mejor = iteracion
        hist_actual.append(costo_actual)
        hist_mejor.append(mejor_costo)

    return ResultadoRuta(
        ruta_inicial=ruta_ini,
        mejor_ruta=mejor,
        costo_inicial=costo_ini,
        mejor_costo=costo_ruta(dist, cedis, mejor, costos=matriz),
        iteraciones=iteracion,
        iter_mejor=iter_mejor,
        evaluaciones=evaluaciones,
        tiempo=time.perf_counter() - inicio,
        historial_actual=hist_actual,
        historial_mejor=hist_mejor,
    )


def resolver_zonas(dist, zonas, semilla=None, costos=None, **parametros):
    """Ejecuta la búsqueda local 2-opt en cada zona fija."""
    resultados = {}
    for cedis, tiendas in zonas.items():
        sem = None if semilla is None else semilla * 100 + cedis
        resultados[cedis] = busqueda_tabu_ruta(
            dist, cedis, tiendas, semilla=sem, costos=costos, **parametros
        )
    total = sum(resultado.mejor_costo for resultado in resultados.values())
    return resultados, total
