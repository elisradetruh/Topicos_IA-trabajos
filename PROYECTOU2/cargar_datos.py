"""Carga y validación de datos siguiendo la organización del proyecto de referencia."""

from pathlib import Path

import numpy as np
import pandas as pd

from rutas import FACTOR_COMBUSTIBLE


def cargar_matriz(ruta):
    """Lee una matriz de Excel, valida sus valores y normaliza su diagonal."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(f"No se encontró el archivo: {ruta}")
    try:
        matriz = pd.read_excel(ruta, header=0).to_numpy(dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError(f"No se pudo leer la matriz en {ruta.name}: {error}") from error
    if matriz.ndim != 2 or matriz.shape[0] != matriz.shape[1]:
        raise ValueError(f"{ruta.stem}: la matriz debe ser cuadrada; se recibió {matriz.shape}")
    if not np.isfinite(matriz).all():
        raise ValueError(f"{ruta.stem}: contiene valores vacíos o no finitos")
    if (matriz < 0).any():
        raise ValueError(f"{ruta.stem}: contiene valores negativos")
    np.fill_diagonal(matriz, 0.0)
    validar_matriz(matriz, ruta.stem)
    return matriz


def validar_matriz(matriz, nombre="matriz"):
    """Comprueba que la matriz sea cuadrada, simétrica, finita y con diagonal cero."""
    matriz = np.asarray(matriz, dtype=float)
    if matriz.ndim != 2 or matriz.shape[0] != matriz.shape[1]:
        raise ValueError(f"{nombre}: debe ser cuadrada, tiene forma {matriz.shape}")
    if not np.isfinite(matriz).all():
        raise ValueError(f"{nombre}: contiene valores vacíos o no finitos")
    if (matriz < 0).any():
        raise ValueError(f"{nombre}: contiene valores negativos")
    if not np.allclose(matriz, matriz.T):
        raise ValueError(f"{nombre}: no es simétrica; el movimiento 2-opt lo requiere")
    if not np.allclose(np.diag(matriz), 0):
        raise ValueError(f"{nombre}: la diagonal debe ser cero")
    return matriz.shape[0]


def distancias_desde_coordenadas(latitud, longitud):
    """Calcula distancias haversine en kilómetros entre pares de coordenadas."""
    latitud = np.asarray(latitud, dtype=float)
    longitud = np.asarray(longitud, dtype=float)
    if latitud.shape != longitud.shape or latitud.ndim != 1:
        raise ValueError("Latitud y longitud deben ser vectores del mismo tamaño")
    if not np.isfinite(latitud).all() or not np.isfinite(longitud).all():
        raise ValueError("Las coordenadas contienen valores vacíos o no finitos")
    la, lo = np.radians(latitud), np.radians(longitud)
    dla = la[:, None] - la[None, :]
    dlo = lo[:, None] - lo[None, :]
    a = (np.sin(dla / 2) ** 2
         + np.cos(la)[:, None] * np.cos(la)[None, :] * np.sin(dlo / 2) ** 2)
    return 2 * 6371.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def cargar_nodos(ruta_excel):
    """Lee los nodos y devuelve las columnas normalizadas del proyecto de referencia."""
    ruta_excel = Path(ruta_excel)
    if not ruta_excel.is_file():
        raise FileNotFoundError(f"No se encontró el archivo: {ruta_excel}")
    excel = pd.read_excel(ruta_excel)
    columnas = {
        "Tipo", "Nombre", "Latitud_WGS84", "Longitud_WGS84",
        "Capacidad_Venta", "Capacidad_Almacenamiento", "Nivel_Tienda",
    }
    faltantes = columnas.difference(excel.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en el archivo de nodos: {sorted(faltantes)}")
    if excel.empty:
        raise ValueError("El archivo de nodos no contiene registros")

    tabla = pd.DataFrame({
        "nodo": np.arange(1, len(excel) + 1),
        "tipo": np.where(excel["Tipo"].eq("Tienda"), "Tienda", "CEDIS"),
        "nombre": excel["Nombre"].to_numpy(),
        "latitud": excel["Latitud_WGS84"].to_numpy(),
        "longitud": excel["Longitud_WGS84"].to_numpy(),
        "cap_venta": excel["Capacidad_Venta"].to_numpy(),
        "cap_almacen": excel["Capacidad_Almacenamiento"].to_numpy(),
        "nivel": excel["Nivel_Tienda"].to_numpy(),
    })
    if tabla[["latitud", "longitud"]].isna().any().any():
        raise ValueError("Hay coordenadas vacías en el Excel")
    tipos = tabla["tipo"]
    if not tipos.iloc[:10].eq("CEDIS").all() or not tipos.iloc[10:].eq("Tienda").all():
        raise ValueError("Se esperaban 10 CEDIS seguidos y después las tiendas")
    return tabla


def matriz_desde_tabla(tabla):
    """Calcula una matriz haversine desde las coordenadas de una tabla de nodos."""
    return distancias_desde_coordenadas(
        tabla["latitud"].to_numpy(), tabla["longitud"].to_numpy()
    )


def cargar_datos(ruta_nodos, ruta_distancias=None, ruta_costos=None, fuente="excel"):
    """Carga los nodos y construye las matrices de distancia y de costo.

    fuente="excel" (por omisión): las distancias (haversine, km) se calculan con las
    coordenadas del Excel, que es la fuente oficial de ubicaciones, y el costo de
    combustible es FACTOR_COMBUSTIBLE x km.
    fuente="matrices": usa las matrices entregadas por el profesor. Solo sirve para
    comparar: no corresponden a las coordenadas del Excel.
    """
    nodos = cargar_nodos(ruta_nodos)
    cantidad_nodos = len(nodos)
    if fuente == "excel":
        distancias = matriz_desde_tabla(nodos)
        costos = FACTOR_COMBUSTIBLE * distancias
    elif fuente == "matrices":
        if ruta_distancias is None or ruta_costos is None:
            raise ValueError("fuente='matrices' requiere las rutas de ambas matrices")
        distancias = cargar_matriz(ruta_distancias)
        costos = cargar_matriz(ruta_costos)
        for nombre, matriz in (("distancias", distancias), ("costos", costos)):
            if matriz.shape != (cantidad_nodos, cantidad_nodos):
                raise ValueError(
                    f"La matriz de {nombre} debe medir {cantidad_nodos}x{cantidad_nodos}; "
                    f"se recibió {matriz.shape}."
                )
    else:
        raise ValueError("fuente debe ser 'excel' o 'matrices'")
    validar_matriz(distancias, "distancias")
    validar_matriz(costos, "costos")

    cedis = nodos.index[nodos["tipo"].eq("CEDIS")].tolist()
    tiendas = nodos.index[nodos["tipo"].eq("Tienda")].tolist()
    if not cedis or not tiendas:
        raise ValueError("Se requiere al menos un CEDIS y una tienda")
    print(f"Nodos cargados: {cantidad_nodos} | CEDIS: {len(cedis)} | Tiendas: {len(tiendas)} "
          f"| distancias desde: {fuente}")
    return nodos, distancias, costos, cedis, tiendas
