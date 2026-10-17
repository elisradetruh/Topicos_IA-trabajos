"""Interfaz para búsqueda tabú 2-opt local y global."""

from pathlib import Path
import random

from Analizador import Graficar_Costo, Graficar_Costo_Global, Imprimir_Resultados
from cargar_datos import cargar_datos, validar_matriz
from Mapeo import Generar_Mapa
from Zonificar import Zonificar, resumen_zonas
from rutas import costo_ruta, vecino_mas_cercano
from tabu import busqueda_tabu_ruta
from tabu_global import busqueda_tabu_global


BASE = Path(__file__).resolve().parent


def _leer_entero(texto, predeterminado, minimo=0):
    valor = input(f"{texto} [{predeterminado}]: ").strip()
    numero = int(valor) if valor else predeterminado
    if numero < minimo:
        raise ValueError(f"El valor debe ser al menos {minimo}.")
    return numero


def _adaptar_resultado_ruta(resultado, cedis, tenure):
    """Convierte el resultado del módulo de referencia al formato de reportes."""
    historial = [
        {
            "Iteracion": indice,
            "Costo_Actual": resultado.historial_actual[indice],
            "Mejor_Costo": resultado.historial_mejor[indice],
            "Movimiento": "2-opt",
            "Tenencia": tenure,
        }
        for indice in range(1, len(resultado.historial_actual))
    ]
    return {
        "Ruta": [cedis, *resultado.mejor_ruta, cedis],
        "Costo": resultado.mejor_costo,
        "Ruta_Inicial": [cedis, *resultado.ruta_inicial, cedis],
        "Costo_Inicial": resultado.costo_inicial,
        "Historial": historial,
        "Iteraciones": resultado.iteraciones,
        "Tenure": tenure,
        "Algoritmo": "Tabú 2-opt por CEDIS",
    }


def _historial_global(resultado):
    return [
        {
            "Iteracion": indice,
            "Costo_Actual": resultado.historial_actual[indice],
            "Mejor_Costo": resultado.historial_mejor[indice],
        }
        for indice in range(1, len(resultado.historial_actual))
    ]


def Main():
    datos = zonas = resultados = None
    historial_global = None
    algoritmo_actual = None

    while True:
        print("\n" + "=" * 52)
        print(" OPTIMIZACIÓN DE RUTAS — BÚSQUEDA TABÚ")
        print("=" * 52)
        print("1. Cargar datos y zonificar")
        print("2. Ejecutar optimización")
        print("3. Ver y exportar resultados")
        print("4. Graficar historial de costo")
        print("5. Generar mapa de rutas")
        print("6. Salir")
        opcion = input("Seleccione una opción: ").strip()

        try:
            if opcion == "1":
                datos = cargar_datos(BASE / "datos_distribucion_tiendas.xlsx")
                _, distancias, _, cedis, tiendas = datos
                zonas = Zonificar(cedis, tiendas, distancias)
                print("\nResumen de capacidades por zona:")
                print(resumen_zonas(zonas, datos[0]).to_string(index=False))
                resultados = None
                historial_global = None
                algoritmo_actual = None

            elif opcion == "2":
                if datos is None or zonas is None:
                    print("Primero carga los datos y zonifica.")
                    continue

                print("\nMétodos disponibles:")
                print("1. Tabú 2-opt por CEDIS, con zonas fijas")
                print("2. Tabú global: 2-opt y reubicación entre CEDIS")
                metodo = input("Elige el método [1]: ").strip() or "1"
                if metodo not in {"1", "2"}:
                    raise ValueError("Selecciona el método 1 o 2.")

                _, distancias, costos, _, _ = datos
                validar_matriz(costos, "costos de combustible")
                es_global = metodo == "2"
                max_iter = _leer_entero("Máximo de iteraciones", 1000 if es_global else 500, 0)
                tenure = _leer_entero("Tamaño de memoria tabú", 60 if es_global else 7, 0)
                limite = _leer_entero("Iteraciones sin mejora", 150 if es_global else 100, 1)
                semilla = _leer_entero("Semilla aleatoria", 42, 0)
                resultados = {}
                historial_global = None

                if metodo == "2":
                    minimo = _leer_entero("Mínimo de tiendas por CEDIS", 3, 0)
                    inicio = input(
                        "Asignación inicial: cercana o aleatoria [cercana]: "
                    ).strip().lower() or "cercana"
                    if inicio not in {"cercana", "aleatoria"}:
                        raise ValueError("La asignación debe ser cercana o aleatoria.")
                    resultado_global = busqueda_tabu_global(
                        distancias,
                        zonas,
                        tenencia=tenure,
                        max_iter=max_iter,
                        max_sin_mejora=limite,
                        min_tiendas=minimo,
                        inicio="aleatorio" if inicio == "aleatoria" else "cercano",
                        semilla=semilla,
                        costos=costos,
                    )
                    historial_global = _historial_global(resultado_global)
                    for cedis, ruta in resultado_global.mejores_rutas.items():
                        ruta_inicial = resultado_global.rutas_iniciales[cedis]
                        resultados[cedis] = {
                            "Ruta": [cedis, *ruta, cedis],
                            "Costo": costo_ruta(
                                distancias, cedis, ruta, costos=costos
                            ),
                            "Ruta_Inicial": [cedis, *ruta_inicial, cedis],
                            "Costo_Inicial": costo_ruta(
                                distancias, cedis, ruta_inicial, costos=costos
                            ),
                            "Historial": [],
                            "Iteraciones": resultado_global.iteraciones,
                            "Tenure": tenure,
                            "Algoritmo": "Tabú global 2-opt + reubicación",
                        }
                    print(
                        "Costo global: "
                        f"{resultado_global.costo_inicial:.2f} → "
                        f"{resultado_global.mejor_costo:.2f}"
                    )
                    algoritmo_actual = "global"

                else:
                    modo = input(
                        "Orden inicial: cercano, aleatorio o manual [cercano]: "
                    ).strip().lower() or "cercano"
                    if modo not in {"cercano", "aleatorio", "manual"}:
                        raise ValueError("El orden inicial debe ser cercano, aleatorio o manual.")
                    aleatorio = modo == "aleatorio"
                    manual = None
                    if modo == "manual":
                        cedis_manual = _leer_entero("Índice del CEDIS", min(zonas), 0)
                        if cedis_manual not in zonas:
                            raise ValueError("El índice indicado no corresponde a un CEDIS.")
                        texto = input("Índices de tiendas separados por coma: ")
                        orden_manual = [int(valor.strip()) for valor in texto.split(",")
                                        if valor.strip()]
                        zona_manual = zonas[cedis_manual]
                        if (len(set(orden_manual)) != len(orden_manual)
                                or set(orden_manual) != set(zona_manual)):
                            raise ValueError(
                                "La ruta manual debe incluir exactamente una vez "
                                "todas las tiendas de ese CEDIS."
                            )
                        manual = (cedis_manual, orden_manual)

                    for indice, (cedis, tiendas_zona) in enumerate(zonas.items()):
                        if manual and cedis != manual[0]:
                            continue
                        rng = random.Random(semilla + indice)
                        if manual:
                            orden = manual[1]
                        elif aleatorio:
                            orden = rng.sample(tiendas_zona, len(tiendas_zona))
                        else:
                            orden = vecino_mas_cercano(
                                distancias, cedis, tiendas_zona
                            )
                        resultado_ruta = busqueda_tabu_ruta(
                            distancias,
                            cedis,
                            tiendas_zona,
                            tenencia=tenure,
                            max_iter=max_iter,
                            max_sin_mejora=limite,
                            semilla=semilla + indice,
                            ruta_inicial=orden,
                            costos=costos,
                        )
                        resultados[cedis] = _adaptar_resultado_ruta(
                            resultado_ruta, cedis, tenure
                        )
                        print(
                            f"CEDIS {cedis}: "
                            f"{resultados[cedis]['Costo_Inicial']:.2f} → "
                            f"{resultados[cedis]['Costo']:.2f}"
                        )
                    algoritmo_actual = "ruta"
                print("Optimización terminada.")

            elif opcion == "3":
                if resultados is None:
                    print("Ejecuta primero la optimización.")
                    continue
                _, distancias, _, _, _ = datos
                Imprimir_Resultados(
                    resultados,
                    distancias,
                    BASE / "Resultados_Tabu.xlsx",
                    historial_global=historial_global,
                )

            elif opcion == "4":
                if not resultados:
                    print("Ejecuta primero la optimización.")
                    continue
                if algoritmo_actual == "global":
                    ruta_grafica = BASE / "Evolucion_Costo_Global.png"
                    Graficar_Costo_Global(historial_global, ruta_grafica)
                    print(f"Gráfica guardada en: {ruta_grafica.name}")
                else:
                    cedis = _leer_entero("CEDIS", min(resultados), 0)
                    if cedis not in resultados:
                        print("No existe una ruta calculada para ese CEDIS.")
                        continue
                    ruta_grafica = BASE / f"Evolucion_Costo_CEDIS_{cedis}.png"
                    Graficar_Costo(resultados[cedis], cedis, ruta_grafica)
                    print(f"Gráfica guardada en: {ruta_grafica.name}")

            elif opcion == "5":
                if not resultados or datos is None:
                    print("Ejecuta primero la optimización.")
                    continue
                Generar_Mapa(datos[0], resultados, BASE / "Mapa_Rutas_Tabu.html")
                print("Mapa guardado como Mapa_Rutas_Tabu.html")

            elif opcion == "6":
                print("Hasta luego.")
                break
            else:
                print("Opción no válida.")
        except (ValueError, FileNotFoundError) as error:
            print(f"No se pudo completar la operación: {error}")
        except KeyboardInterrupt:
            print("\nOperación cancelada.")


if __name__ == "__main__":
    Main()
