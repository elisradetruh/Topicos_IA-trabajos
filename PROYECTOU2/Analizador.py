"""Resumen, exportación y gráficas del proceso de búsqueda tabú."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def Calcular_Distancia(Ruta, Distancias):
    return float(sum(Distancias[Ruta[i]][Ruta[i + 1]] for i in range(len(Ruta) - 1)))


def Tabla_Resultados(Resultados, Distancias):
    filas = []
    historial = []
    for cedis, dato in Resultados.items():
        ruta_ini, ruta = dato["Ruta_Inicial"], dato["Ruta"]
        costo_ini, costo = dato["Costo_Inicial"], dato["Costo"]
        distancia_ini = Calcular_Distancia(ruta_ini, Distancias)
        distancia = Calcular_Distancia(ruta, Distancias)
        mejora = costo_ini - costo
        es_global = str(dato.get("Algoritmo", "")).startswith("Tabú global")
        filas.append({
            "CEDIS": cedis,
            "Algoritmo": dato.get("Algoritmo", "Búsqueda tabú"),
            "Ruta Inicial": "->".join(map(str, ruta_ini)),
            "Ruta Tabu": "->".join(map(str, ruta)),
            "Tiendas": len(ruta) - 2,
            "Distancia Inicial": distancia_ini,
            "Distancia Final": distancia,
            "Costo Inicial": costo_ini,
            "Costo Final": costo,
            # En el método global las tiendas cambian de CEDIS: el ahorro por CEDIS no es
            # comparable (la ruta inicial y la final no tienen las mismas tiendas). Solo el
            # total lo es.
            "Ahorro": None if es_global else mejora,
            "Ahorro %": None if es_global else ((100 * mejora / costo_ini) if costo_ini else 0.0),
            "Iteraciones": dato["Iteraciones"],
            "Tenure": dato["Tenure"],
        })
        for punto in dato["Historial"]:
            historial.append({"CEDIS": cedis, **punto})
    tabla = pd.DataFrame(filas)
    if not tabla.empty:
        todo_global = tabla["Algoritmo"].astype(str).str.startswith("Tabú global").all()
        ahorro_total = tabla["Costo Inicial"].sum() - tabla["Costo Final"].sum()
        total = {
            "CEDIS": "TOTAL", "Algoritmo": "—", "Ruta Inicial": "—", "Ruta Tabu": "—",
            "Tiendas": int(tabla["Tiendas"].sum()),
            "Distancia Inicial": tabla["Distancia Inicial"].sum(),
            "Distancia Final": tabla["Distancia Final"].sum(),
            "Costo Inicial": tabla["Costo Inicial"].sum(),
            "Costo Final": tabla["Costo Final"].sum(),
            "Ahorro": ahorro_total,
            "Ahorro %": (100 * ahorro_total / tabla["Costo Inicial"].sum())
            if tabla["Costo Inicial"].sum() else 0.0,
            # en el método global la búsqueda es una sola: las iteraciones no se suman por CEDIS
            "Iteraciones": int(tabla["Iteraciones"].max() if todo_global else tabla["Iteraciones"].sum()),
            "Tenure": "—",
        }
        tabla = pd.concat([tabla, pd.DataFrame([total])], ignore_index=True)
    return tabla, pd.DataFrame(historial)


def Imprimir_Resultados(Resultados, Distancias, archivo="Resultados.xlsx",
                        historial_global=None):
    resumen, historial = Tabla_Resultados(Resultados, Distancias)
    if resumen.empty:
        raise ValueError("No hay resultados para exportar.")
    destino = Path(archivo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(destino, engine="openpyxl") as escritor:
        resumen.round(3).to_excel(escritor, sheet_name="Resumen", index=False)
        historial.to_excel(escritor, sheet_name="Historial", index=False)
        rutas = resumen[resumen["CEDIS"] != "TOTAL"][["CEDIS", "Ruta Tabu"]]
        rutas.to_excel(escritor, sheet_name="Rutas", index=False)
        if historial_global:
            pd.DataFrame(historial_global).to_excel(
                escritor, sheet_name="Historial Global", index=False
            )
    print(resumen.round(2).to_string(index=False))
    print(f"Resultados guardados en: {destino}")
    return resumen


def Graficar_Costo(Resultado, Cedis, guardar_en=None):
    historial = Resultado["Historial"]
    if not historial:
        print("La ruta tiene menos de dos tiendas; no hay iteraciones que graficar.")
        return
    plt.figure(figsize=(9, 5))
    x = [p["Iteracion"] for p in historial]
    plt.plot(x, [p["Costo_Actual"] for p in historial], label="Costo del vecino elegido", alpha=0.65)
    plt.plot(x, [p["Mejor_Costo"] for p in historial], label="Mejor costo acumulado", linewidth=2)
    plt.title(f"Búsqueda tabú — CEDIS {Cedis}")
    plt.xlabel("Iteración")
    plt.ylabel("Costo acumulado")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    if guardar_en:
        plt.savefig(guardar_en, dpi=160)
    plt.show()


def Graficar_Costo_Global(Historial, guardar_en=None):
    """Grafica el costo conjunto del modo global de búsqueda tabú."""
    if not Historial:
        print("No hay historial global para graficar.")
        return
    plt.figure(figsize=(9, 5))
    x = [p["Iteracion"] for p in Historial]
    plt.plot(x, [p["Costo_Actual"] for p in Historial],
             label="Costo actual global", alpha=0.65)
    plt.plot(x, [p["Mejor_Costo"] for p in Historial],
             label="Mejor costo global", linewidth=2)
    plt.title("Búsqueda tabú global — costo total")
    plt.xlabel("Iteración")
    plt.ylabel("Costo acumulado")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    if guardar_en:
        plt.savefig(guardar_en, dpi=160)
    plt.show()
