"""Operaciones de rutas incorporadas del proyecto de referencia.

Las distancias físicas se usan para construir rutas iniciales. Cuando se entrega
una matriz ``costos``, esa matriz define el objetivo que se optimiza; omitirla
mantiene la compatibilidad con el comportamiento original (optimizar distancia).
"""

from itertools import permutations

import numpy as np

FACTOR_COMBUSTIBLE = 0.15  # Constante documentada en el proyecto de referencia.


def costo_ruta(dist, cedis, ruta, costos=None):
    """Costo de un recorrido cerrado, incluidos salida y regreso al CEDIS."""
    if not ruta:
        return 0.0
    matriz = dist if costos is None else costos
    total = matriz[cedis, ruta[0]] + matriz[ruta[-1], cedis]
    for a, b in zip(ruta, ruta[1:]):
        total += matriz[a, b]
    return float(total)


def vecino_mas_cercano(dist, cedis, tiendas):
    """Construye una ruta inicial eligiendo cada vez la tienda más cercana."""
    pendientes = list(tiendas)
    ruta = []
    actual = cedis
    while pendientes:
        siguiente = min(pendientes, key=lambda tienda: dist[actual, tienda])
        pendientes.remove(siguiente)
        ruta.append(siguiente)
        actual = siguiente
    return ruta


def dos_opt(dist, cedis, ruta, costos=None):
    """Mejora una ruta invirtiendo tramos mientras baje su costo."""
    ruta = list(ruta)
    matriz = dist if costos is None else costos
    mejoro = True
    while mejoro:
        mejoro = False
        mejor = costo_ruta(dist, cedis, ruta, costos=matriz)
        for i in range(len(ruta) - 1):
            for j in range(i + 1, len(ruta)):
                nueva = ruta[:i] + ruta[i:j + 1][::-1] + ruta[j + 1:]
                costo = costo_ruta(dist, cedis, nueva, costos=matriz)
                if costo < mejor - 1e-9:
                    ruta, mejor, mejoro = nueva, costo, True
    return ruta


def optimo_fuerza_bruta(dist, cedis, tiendas, costos=None):
    """Busca el orden óptimo por fuerza bruta; solo viable para zonas pequeñas."""
    mejor_ruta, mejor_costo = None, float("inf")
    for orden in permutations(tiendas):
        costo = costo_ruta(dist, cedis, list(orden), costos=costos)
        if costo < mejor_costo:
            mejor_ruta, mejor_costo = list(orden), costo
    return mejor_ruta, mejor_costo


def optimo_held_karp(dist, cedis, tiendas, costos=None):
    """Costo óptimo de la ruta de un CEDIS por programación dinámica (Held-Karp).

    Memoria y tiempo crecen como 2^n, así que sirve para zonas de hasta unas 20 tiendas
    (la zona más grande del proyecto tiene 19). Se usa como referencia exacta para medir
    qué tan cerca queda la búsqueda tabú; no es parte de la optimización.
    """
    m = len(tiendas)
    if m == 0:
        return 0.0
    matriz = np.asarray(dist if costos is None else costos, dtype=float)
    d = matriz[np.ix_(tiendas, tiendas)]
    d0 = matriz[cedis, tiendas]
    n = 1 << m
    dp = np.full((n, m), np.inf)                 # dp[S, j]: mínimo para visitar S terminando en j
    for j in range(m):
        dp[1 << j, j] = d0[j]
    mascaras = np.arange(n, dtype=np.int64)
    bits = np.zeros(n, dtype=np.int8)
    for k in range(m):
        bits += ((mascaras >> k) & 1).astype(np.int8)
    for p in range(1, m):
        capa = mascaras[bits == p]
        for k in range(m):
            sel = capa[((capa >> k) & 1) == 0]
            dp[sel | (1 << k), k] = (dp[sel, :] + d[:, k][None, :]).min(axis=1)
    return float((dp[n - 1] + d0).min())
