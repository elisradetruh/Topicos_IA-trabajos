"""Asignación de cada tienda al CEDIS más cercano según distancia."""

import numpy as np
import pandas as pd


def Zonificar(Cedis, Tiendas, Dis):
    if not Cedis:
        raise ValueError("No hay CEDIS para formar zonas.")
    distancias = np.asarray(Dis, dtype=float)
    zonas = {int(cedis): [] for cedis in Cedis}
    for tienda in Tiendas:
        asignado = int(Cedis[int(np.argmin(distancias[tienda, Cedis]))])
        zonas[asignado].append(int(tienda))
    for cedis, tiendas in zonas.items():
        print(f"Zona del CEDIS {cedis}: {len(tiendas)} tiendas")
    return zonas


def asignar_zonas(dist, n_cedis=10):
    """API del proyecto de referencia; asigna cada tienda al CEDIS más cercano."""
    distancias = np.asarray(dist, dtype=float)
    if distancias.ndim != 2 or distancias.shape[0] != distancias.shape[1]:
        raise ValueError("La matriz de distancias debe ser cuadrada")
    if not 0 < n_cedis < distancias.shape[0]:
        raise ValueError("El número de CEDIS debe estar entre 1 y el total de nodos")
    return {
        cedis: [tienda for tienda in range(n_cedis, distancias.shape[0])
                if int(np.argmin(distancias[tienda, :n_cedis])) == cedis]
        for cedis in range(n_cedis)
    }


def resumen_zonas(zonas, tabla):
    """Resume cantidades y capacidades por CEDIS como en el proyecto de referencia."""
    venta = "Capacidad_Venta" if "Capacidad_Venta" in tabla else "cap_venta"
    almacen = ("Capacidad_Almacenamiento" if "Capacidad_Almacenamiento" in tabla
               else "cap_almacen")
    faltantes = {venta, almacen}.difference(tabla.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas para el resumen de capacidades: {sorted(faltantes)}")
    filas = []
    for cedis, tiendas in zonas.items():
        sub = tabla.iloc[tiendas]
        filas.append({
            "cedis": cedis + 1,
            "tiendas": len(tiendas),
            "cap_venta": sub[venta].sum(),
            "cap_almacen": sub[almacen].sum(),
        })
    return pd.DataFrame(filas)
