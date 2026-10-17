# Sistema de enrutamiento para tienda: búsqueda tabú

Proyecto académico (Culiacán, 10 CEDIS y 90 tiendas). Se optimizan las rutas de reparto con búsqueda tabú y se comparan los resultados contra el vecino más cercano, 2-opt y el óptimo exacto.

## Datos y objetivo

- Las distancias se calculan con la fórmula de Haversine a partir de las **coordenadas del Excel** `datos_distribucion_tiendas.xlsx` (línea recta, en km).
- El costo es combustible = **0.15 × km**. Se optimiza el costo, que equivale a minimizar km.
- Los libros `matriz_distancias.xlsx` y `matriz_costos_combustible.xlsx` **no corresponden** a las coordenadas del Excel (correlación cercana a 0). Se conservan solo para comparar (`cargar_datos(..., fuente="matrices")`); no se usan en los resultados.
- Las columnas de capacidad no se usan como restricción (su significado no está confirmado); queda como limitación.

## Métodos

1. **Tabú 2-opt por CEDIS**: conserva la zona de cada CEDIS (cada tienda va al CEDIS más cercano) y reordena la ruta. Memoria tabú: aristas quitadas. Aspiración: se acepta un movimiento tabú si mejora el mejor costo conocido.
2. **Tabú global**: 2-opt dentro de cada ruta más **reubicar** una tienda en la ruta de otro CEDIS. Cada CEDIS conserva al menos `min_tiendas` tiendas (por defecto 3: sin esa regla el óptimo en km vacía casi todos los CEDIS).

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `Main.py` | Menú: cargar, optimizar, exportar a Excel, graficar, mapa |
| `cargar_datos.py` | Lectura de nodos, Haversine, validación de matrices |
| `Zonificar.py`, `zonas.py` | Zonas por CEDIS más cercano y resumen de capacidades |
| `rutas.py` | Costo de ruta, vecino más cercano, 2-opt, óptimo exacto (fuerza bruta y Held-Karp) |
| `tabu.py`, `tabu_global.py` | Los dos algoritmos tabú |
| `Analizador.py`, `Mapeo.py` | Tablas Excel, gráficas y mapa HTML |
| `experimentos.py` | Referencias y sensibilidad (tenencia, K, mínimo de tiendas, inicio) |
| `Analisis_Experimentos.ipynb` | Notebook con datos, referencias, mejor solución, mapa y experimentos |
| `test_proyecto.py` | 23 pruebas automáticas |

## Ejecución

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python Main.py                     # menú
python -m unittest -v              # pruebas (unos 7 s)
python experimentos.py             # experimentos completos (unos 8 min con 2 procesos)
jupyter notebook Analisis_Experimentos.ipynb
```

Valores recomendados en el menú: método 2, tenencia 60, 1000 iteraciones, 150 sin mejora, mínimo 3 tiendas, asignación cercana. El método 1 usa orden inicial cercano por defecto.

## Resultados principales (distancias en km con las coordenadas del Excel)

| Método | km | Combustible |
|---|---|---|
| Vecino más cercano (zonas fijas) | 216.50 | 32.47 |
| 2-opt (zonas fijas) | 198.39 | 29.76 |
| Tabú por CEDIS (zonas fijas, tenencia 7) | 197.16 | 29.57 |
| Óptimo exacto con zonas fijas | 196.86 | 29.53 |
| **Tabú global (tenencia 60, mínimo 3)** | **168.59** | **25.29** |

## Limitaciones

- Distancias en línea recta; por calles serían mayores.
- Sin restricciones de capacidad, flota ni ventanas horarias.
- Una sola instancia: la sensibilidad a tenencia, K y mínimo no debe generalizarse.
- Con inicio aleatorio la búsqueda se estanca (promedio cercano a 220 km): la memoria de largo plazo (diversificación) queda como trabajo futuro.
- Los experimentos necesitan 1000 iteraciones máximas: con 30 la búsqueda global se corta antes de converger.
