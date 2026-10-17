"""Búsqueda tabú global: 2-opt y reubicación de tiendas entre CEDIS."""

import random
import time
from dataclasses import dataclass, field

from rutas import costo_ruta, vecino_mas_cercano
from tabu import movimientos_2opt, aristas_2opt, delta_2opt


@dataclass
class ResultadoGlobal:
    """Datos de una ejecución conjunta sobre todas las rutas."""

    rutas_iniciales: dict
    mejores_rutas: dict
    costo_inicial: float
    mejor_costo: float
    iteraciones: int
    iter_mejor: int
    evaluaciones: int
    tiempo: float
    historial_actual: list = field(default_factory=list)
    historial_mejor: list = field(default_factory=list)


def costo_total(dist, rutas, costos=None):
    """Suma el objetivo de las rutas de todos los CEDIS."""
    return sum(costo_ruta(dist, cedis, ruta, costos=costos)
               for cedis, ruta in rutas.items())


def delta_quitar(dist, ruta, cedis, posicion):
    """Cambio de costo al quitar una tienda de una ruta."""
    tienda = ruta[posicion]
    antes = cedis if posicion == 0 else ruta[posicion - 1]
    despues = cedis if posicion == len(ruta) - 1 else ruta[posicion + 1]
    return dist[antes, despues] - dist[antes, tienda] - dist[tienda, despues]


def delta_insertar(dist, ruta, cedis, posicion, tienda):
    """Cambio de costo al insertar una tienda en una ruta."""
    antes = cedis if posicion == 0 else ruta[posicion - 1]
    despues = cedis if posicion == len(ruta) else ruta[posicion]
    return dist[antes, tienda] + dist[tienda, despues] - dist[antes, despues]


def reparar_minimos(dist, zonas, min_tiendas):
    """Reubica tiendas desde zonas con excedente para cumplir mínimos."""
    if min_tiendas * len(zonas) > sum(len(tiendas) for tiendas in zonas.values()):
        raise ValueError("No alcanzan las tiendas para el mínimo pedido por CEDIS")
    for cedis, tiendas in zonas.items():
        while len(tiendas) < min_tiendas:
            donantes = [
                (dist[tienda, cedis], tienda, otro_cedis)
                for otro_cedis, otras_tiendas in zonas.items()
                if len(otras_tiendas) > min_tiendas
                for tienda in otras_tiendas
            ]
            if not donantes:
                raise ValueError("No se pudo cumplir el mínimo de tiendas por CEDIS")
            _, tienda, donador = min(donantes)
            zonas[donador].remove(tienda)
            tiendas.append(tienda)
    return zonas


def busqueda_tabu_global(dist, zonas, tenencia=40, max_iter=1000,
                         max_sin_mejora=150, min_tiendas=1,
                         inicio="cercano", semilla=None, costos=None, k=None):
    """Busca conjuntamente rutas y asignaciones de tiendas.

    ``dist`` determina cercanía y reparaciones de zonas; ``costos`` determina
    la función objetivo. Omitir ``costos`` conserva el modo original por km.
    ``k`` limita la selección aleatoria a los K mejores movimientos admisibles;
    con ``None`` se conserva la elección de un movimiento con delta mínimo.
    """
    rng = random.Random(semilla)
    matriz = dist if costos is None else costos
    if k is not None and k < 1:
        raise ValueError("K debe ser un entero positivo o None")
    if inicio not in ("cercano", "aleatorio"):
        raise ValueError("inicio debe ser 'cercano' o 'aleatorio'")
    todas = sorted(tienda for tiendas in zonas.values() for tienda in tiendas)
    if inicio == "aleatorio":
        zonas = {cedis: [] for cedis in zonas}
        for tienda in todas:
            zonas[rng.choice(list(zonas))].append(tienda)
    else:
        zonas = {cedis: list(tiendas) for cedis, tiendas in zonas.items()}
    zonas = reparar_minimos(dist, zonas, min_tiendas)
    if inicio == "aleatorio":
        rutas = {cedis: rng.sample(tiendas, len(tiendas))
                 for cedis, tiendas in zonas.items()}
    else:
        rutas = {cedis: vecino_mas_cercano(dist, cedis, tiendas)
                 for cedis, tiendas in zonas.items()}

    inicio_tiempo = time.perf_counter()
    rutas_ini = {cedis: ruta[:] for cedis, ruta in rutas.items()}
    total = costo_total(dist, rutas, costos=matriz)
    costo_ini = total
    mejor_rutas = {cedis: ruta[:] for cedis, ruta in rutas.items()}
    mejor_total = total
    tabu_tienda = {}
    tabu_arista = {}
    evaluaciones = 0
    hist_actual, hist_mejor = [total], [mejor_total]
    iteracion = 0
    iter_mejor = 0

    while iteracion < max_iter and iteracion - iter_mejor < max_sin_mejora:
        iteracion += 1
        candidatos = []

        def considerar(delta, es_tabu, movimiento):
            if es_tabu and not (total + delta < mejor_total - 1e-9):
                return
            candidatos.append((delta, movimiento))

        for cedis, ruta in rutas.items():
            if len(ruta) <= min_tiendas:
                continue
            for posicion, tienda in enumerate(ruta):
                quita = delta_quitar(matriz, ruta, cedis, posicion)
                for otro_cedis, otra_ruta in rutas.items():
                    if otro_cedis == cedis:
                        continue
                    es_tabu = tabu_tienda.get((tienda, otro_cedis), 0) > iteracion
                    for lugar in range(len(otra_ruta) + 1):
                        evaluaciones += 1
                        delta = quita + delta_insertar(
                            matriz, otra_ruta, otro_cedis, lugar, tienda
                        )
                        considerar(delta, es_tabu,
                                   ("mover", cedis, posicion, otro_cedis, lugar))

        for cedis, ruta in rutas.items():
            for i, j in movimientos_2opt(len(ruta)):
                evaluaciones += 1
                delta = delta_2opt(matriz, ruta, cedis, i, j)
                _, agrega, _, _ = aristas_2opt(ruta, cedis, i, j)
                es_tabu = any(tabu_arista.get(arista, 0) > iteracion
                              for arista in agrega)
                considerar(delta, es_tabu, ("2opt", cedis, i, j))

        if not candidatos:
            break

        candidatos.sort(key=lambda candidato: candidato[0])
        if k is None:
            mejor_delta = candidatos[0][0]
            mejores = [mov for delta, mov in candidatos
                       if abs(delta - mejor_delta) <= 1e-9]
            movimiento = rng.choice(mejores)
        else:
            mejor_delta, movimiento = rng.choice(candidatos[:k])
        if movimiento[0] == "mover":
            _, cedis, posicion, otro_cedis, lugar = movimiento
            tienda = rutas[cedis].pop(posicion)
            rutas[otro_cedis].insert(lugar, tienda)
            tabu_tienda[(tienda, cedis)] = iteracion + tenencia
        else:
            _, cedis, i, j = movimiento
            quita, _, _, _ = aristas_2opt(rutas[cedis], cedis, i, j)
            rutas[cedis][i:j + 1] = rutas[cedis][i:j + 1][::-1]
            for arista in quita:
                tabu_arista[arista] = iteracion + tenencia
        total += mejor_delta

        if total < mejor_total - 1e-9:
            mejor_rutas = {cedis: ruta[:] for cedis, ruta in rutas.items()}
            mejor_total = total
            iter_mejor = iteracion
        hist_actual.append(total)
        hist_mejor.append(mejor_total)

    return ResultadoGlobal(
        rutas_iniciales=rutas_ini,
        mejores_rutas=mejor_rutas,
        costo_inicial=costo_ini,
        mejor_costo=costo_total(dist, mejor_rutas, costos=matriz),
        iteraciones=iteracion,
        iter_mejor=iter_mejor,
        evaluaciones=evaluaciones,
        tiempo=time.perf_counter() - inicio_tiempo,
        historial_actual=hist_actual,
        historial_mejor=hist_mejor,
    )
