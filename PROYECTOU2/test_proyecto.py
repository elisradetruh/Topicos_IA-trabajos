"""Pruebas del proyecto: datos, zonificación, deltas, búsquedas tabú y resultados conocidos.

Se ejecutan desde la carpeta del proyecto con:  python -m unittest -v
"""

import contextlib
import io
import random
import unittest
from pathlib import Path

import numpy as np

from cargar_datos import (cargar_datos, cargar_nodos, distancias_desde_coordenadas,
                          matriz_desde_tabla, validar_matriz)
from rutas import (FACTOR_COMBUSTIBLE, costo_ruta, dos_opt, optimo_fuerza_bruta,
                   optimo_held_karp, vecino_mas_cercano)
from tabu import busqueda_tabu_ruta, delta_2opt, movimientos_2opt, resolver_zonas
from tabu_global import (busqueda_tabu_global, costo_total, delta_insertar, delta_quitar,
                         reparar_minimos)
from Zonificar import asignar_zonas

EXCEL = Path(__file__).resolve().parent / "datos_distribucion_tiendas.xlsx"


def _silencio(funcion, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return funcion(*args, **kwargs)


class DatosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tabla = cargar_nodos(EXCEL)
        cls.dist = matriz_desde_tabla(cls.tabla)

    def test_nodos_100_con_10_cedis_y_90_tiendas(self):
        self.assertEqual(len(self.tabla), 100)
        self.assertEqual(self.tabla["tipo"].value_counts().to_dict(), {"Tienda": 90, "CEDIS": 10})

    def test_archivo_inexistente_se_rechaza(self):
        with self.assertRaises(FileNotFoundError):
            cargar_nodos("no_existe.xlsx")

    def test_haversine_simetrica_con_diagonal_cero(self):
        self.assertEqual(validar_matriz(self.dist, "distancias"), 100)
        self.assertTrue(np.allclose(self.dist, self.dist.T))
        self.assertTrue(np.allclose(np.diag(self.dist), 0))

    def test_haversine_un_grado_de_latitud(self):
        d = distancias_desde_coordenadas([24.0, 25.0], [-107.0, -107.0])
        self.assertAlmostEqual(d[0, 1], 111.195, places=2)

    def test_cargar_datos_usa_excel_y_costo_proporcional(self):
        _, dist, costos, cedis, tiendas = _silencio(cargar_datos, EXCEL)
        self.assertTrue(np.allclose(dist, self.dist))
        self.assertTrue(np.allclose(costos, FACTOR_COMBUSTIBLE * dist))
        self.assertEqual((len(cedis), len(tiendas)), (10, 90))

    def test_fuente_invalida_se_rechaza(self):
        with self.assertRaises(ValueError):
            _silencio(cargar_datos, EXCEL, fuente="otra")


class ZonasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dist = matriz_desde_tabla(cargar_nodos(EXCEL))

    def test_cada_tienda_en_una_sola_zona(self):
        zonas = asignar_zonas(self.dist)
        todas = sorted(t for v in zonas.values() for t in v)
        self.assertEqual(todas, list(range(10, 100)))

    def test_tamanos_conocidos(self):
        zonas = asignar_zonas(self.dist)
        self.assertEqual([len(v) for v in zonas.values()], [2, 19, 5, 8, 8, 2, 12, 8, 13, 13])

    def test_reparar_minimos_conserva_tiendas_y_cumple_el_minimo(self):
        zonas = reparar_minimos(self.dist, asignar_zonas(self.dist), 3)
        self.assertTrue(all(len(v) >= 3 for v in zonas.values()))
        self.assertEqual(sorted(t for v in zonas.values() for t in v), list(range(10, 100)))

    def test_minimo_imposible_se_rechaza(self):
        with self.assertRaises(ValueError):
            reparar_minimos(self.dist, asignar_zonas(self.dist), 10)


class DeltaTests(unittest.TestCase):
    """Cada delta debe coincidir con recalcular la ruta completa."""

    @classmethod
    def setUpClass(cls):
        cls.dist = matriz_desde_tabla(cargar_nodos(EXCEL))

    def test_delta_2opt_coincide_con_recalculo(self):
        rng = random.Random(1)
        for _ in range(20):
            ruta = rng.sample(range(10, 100), 9)
            base = costo_ruta(self.dist, 0, ruta)
            for i, j in movimientos_2opt(len(ruta)):
                nueva = ruta[:i] + ruta[i:j + 1][::-1] + ruta[j + 1:]
                real = costo_ruta(self.dist, 0, nueva) - base
                self.assertAlmostEqual(delta_2opt(self.dist, ruta, 0, i, j), real, places=9)

    def test_delta_reubicar_coincide_con_recalculo(self):
        rng = random.Random(2)
        for _ in range(20):
            tiendas = rng.sample(range(10, 100), 12)
            a, b = tiendas[:6], tiendas[6:]
            base = costo_ruta(self.dist, 0, a) + costo_ruta(self.dist, 1, b)
            for p in range(len(a)):
                for k in range(len(b) + 1):
                    nueva_a = a[:p] + a[p + 1:]
                    nueva_b = b[:k] + [a[p]] + b[k:]
                    real = costo_ruta(self.dist, 0, nueva_a) + costo_ruta(self.dist, 1, nueva_b) - base
                    delta = delta_quitar(self.dist, a, 0, p) + delta_insertar(self.dist, b, 1, k, a[p])
                    self.assertAlmostEqual(delta, real, places=9)


class BusquedaRutaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dist = matriz_desde_tabla(cargar_nodos(EXCEL))
        cls.zonas = asignar_zonas(cls.dist)

    def test_conserva_tiendas_y_no_empeora(self):
        for cedis, tiendas in self.zonas.items():
            r = busqueda_tabu_ruta(self.dist, cedis, tiendas, semilla=3)
            self.assertCountEqual(r.mejor_ruta, tiendas)
            self.assertLessEqual(r.mejor_costo, r.costo_inicial + 1e-9)

    def test_misma_semilla_misma_ruta(self):
        a = busqueda_tabu_ruta(self.dist, 1, self.zonas[1], semilla=5)
        b = busqueda_tabu_ruta(self.dist, 1, self.zonas[1], semilla=5)
        self.assertEqual(a.mejor_ruta, b.mejor_ruta)
        self.assertEqual(a.historial_actual, b.historial_actual)

    def test_zona_pequena_alcanza_el_optimo_exacto(self):
        tiendas = self.zonas[2]                       # 5 tiendas: 5! = 120 órdenes
        _, optimo = optimo_fuerza_bruta(self.dist, 2, tiendas)
        r = busqueda_tabu_ruta(self.dist, 2, tiendas, semilla=1)
        self.assertAlmostEqual(r.mejor_costo, optimo, places=9)

    def test_held_karp_coincide_con_fuerza_bruta(self):
        tiendas = self.zonas[2]                       # 5 tiendas
        _, bruta = optimo_fuerza_bruta(self.dist, 2, tiendas)
        self.assertAlmostEqual(optimo_held_karp(self.dist, 2, tiendas), bruta, places=9)
        tiendas = self.zonas[0] + self.zonas[5] + self.zonas[2]   # 9 tiendas: 9! órdenes
        _, bruta = optimo_fuerza_bruta(self.dist, 0, tiendas)
        self.assertAlmostEqual(optimo_held_karp(self.dist, 0, tiendas), bruta, places=9)

    def test_tabu_no_baja_del_optimo_exacto(self):
        for cedis in (2, 3, 7):
            tiendas = self.zonas[cedis]
            optimo = optimo_held_karp(self.dist, cedis, tiendas)
            r = busqueda_tabu_ruta(self.dist, cedis, tiendas, semilla=1)
            self.assertGreaterEqual(r.mejor_costo, optimo - 1e-9)

    def test_dos_opt_no_empeora_al_vecino_mas_cercano(self):
        base = vecino_mas_cercano(self.dist, 3, self.zonas[3])
        mejor = dos_opt(self.dist, 3, base)
        self.assertLessEqual(costo_ruta(self.dist, 3, mejor), costo_ruta(self.dist, 3, base) + 1e-9)


class BusquedaGlobalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dist = matriz_desde_tabla(cargar_nodos(EXCEL))
        cls.zonas = asignar_zonas(cls.dist)

    def test_solucion_valida(self):
        r = busqueda_tabu_global(self.dist, self.zonas, min_tiendas=3, tenencia=60,
                                 max_iter=40, semilla=0)
        todas = sorted(t for ruta in r.mejores_rutas.values() for t in ruta)
        self.assertEqual(todas, list(range(10, 100)))
        self.assertTrue(all(len(ruta) >= 3 for ruta in r.mejores_rutas.values()))
        self.assertLessEqual(r.mejor_costo, r.costo_inicial + 1e-9)

    def test_costo_acumulado_coincide_con_recalculo(self):
        r = busqueda_tabu_global(self.dist, self.zonas, min_tiendas=3, tenencia=60,
                                 max_iter=40, semilla=0)
        self.assertAlmostEqual(r.historial_mejor[-1], costo_total(self.dist, r.mejores_rutas), places=6)

    def test_funciona_con_costos_no_proporcionales_a_la_distancia(self):
        rng = np.random.default_rng(0)
        factor = 0.5 + rng.random(self.dist.shape)
        factor = (factor + factor.T) / 2
        costos = self.dist * factor
        np.fill_diagonal(costos, 0)
        r = busqueda_tabu_global(self.dist, self.zonas, min_tiendas=3, tenencia=60,
                                 max_iter=40, semilla=0, costos=costos)
        self.assertAlmostEqual(r.historial_mejor[-1],
                               costo_total(self.dist, r.mejores_rutas, costos=costos), places=6)


class ResultadosConocidosTests(unittest.TestCase):
    """Regresión: cifras verificadas del proyecto (distancias en km con el Excel)."""

    @classmethod
    def setUpClass(cls):
        cls.dist = matriz_desde_tabla(cargar_nodos(EXCEL))
        cls.zonas = asignar_zonas(cls.dist)

    def test_zonas_fijas_tabu(self):
        _, total = resolver_zonas(self.dist, self.zonas, semilla=1)
        self.assertAlmostEqual(total, 197.16, places=1)

    def test_tabu_global_minimo_3(self):
        r = busqueda_tabu_global(self.dist, self.zonas, min_tiendas=3, tenencia=60, semilla=0)
        self.assertAlmostEqual(r.costo_inicial, 217.04, places=1)
        self.assertAlmostEqual(r.mejor_costo, 168.59, places=1)


if __name__ == "__main__":
    unittest.main()
