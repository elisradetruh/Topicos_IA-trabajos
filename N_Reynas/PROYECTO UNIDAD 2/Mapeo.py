"""Generación opcional de un mapa HTML con nodos y rutas optimizadas."""

from pathlib import Path

import folium


def Generar_Mapa(Nodo, Resultados, archivo="Mapa_Rutas_Tabu.html"):
    if Nodo.empty:
        raise ValueError("No hay nodos para dibujar.")
    if "latitud" in Nodo.columns:
        latitud, longitud = "latitud", "longitud"
        nombre, tipo = "nombre", "tipo"
    else:
        latitud, longitud = "Latitud_WGS84", "Longitud_WGS84"
        nombre, tipo = "Nombre", "Tipo"
    centro = [Nodo[latitud].mean(), Nodo[longitud].mean()]
    mapa = folium.Map(location=centro, zoom_start=11, control_scale=True)
    colores = ["blue", "green", "purple", "orange", "darkred", "cadetblue", "darkgreen", "pink", "darkpurple", "beige"]
    for _, nodo in Nodo.iterrows():
        es_cedis = nodo[tipo] in {"CEDIS", "Centro de Distribución"}
        folium.Marker(
            [nodo[latitud], nodo[longitud]],
            tooltip=nodo[nombre],
            popup=nodo[tipo],
            icon=folium.Icon(color="red" if es_cedis else "gray", icon="home" if es_cedis else "shopping-cart", prefix="fa"),
        ).add_to(mapa)
    for indice, (cedis, resultado) in enumerate(Resultados.items()):
        coords = [[Nodo.iloc[i][latitud], Nodo.iloc[i][longitud]]
                  for i in resultado["Ruta"]]
        folium.PolyLine(coords, color=colores[indice % len(colores)], weight=3, opacity=0.8,
                        tooltip=f"CEDIS {cedis}: costo {resultado['Costo']:.2f}").add_to(mapa)
    destino = Path(archivo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    mapa.save(str(destino))
    return destino
