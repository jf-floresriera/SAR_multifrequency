# -*- coding: utf-8 -*-
"""
Filtro de escenas NISAR (banda L) para el sismo de Venezuela del 24/06/2026
-------------------------------------------------------------------------------
Problema que resuelve: en el notebook original se descargaban TODOS los GUNW de
las fechas y se abría archivos[0], sin verificar que ese par cruzara el sismo.
Este script clasifica cada producto y deja solo lo que es realmente útil.

Clasificación de cada GUNW (interferograma geocodificado):
  COSISMICO   : fecha_ref < sismo < fecha_sec          -> el que necesitamos
  PRE-SISMICO : ambas fechas antes del sismo           -> control de ruido / atmósfera
  POST-SISMICO: ambas fechas después del sismo         -> postsísmico, deslizamientos

Además:
  - Agrupa por track (pathNumber), frame y dirección (ASC/DESC).
  - Calcula qué % de La Guaira cubre cada escena y si toca las escenas Umbra.
  - Compara con los tracks usados por Scripps/UCSD (T162A, T061A, T054D, T126D).
  - Lista también RSLC (por si quieres formar tus propios pares con ISCE3/GMTSAR).

Uso en Colab (después de autenticar `session` como en el notebook):
  !pip install -q asf_search shapely geopandas pandas contextily matplotlib
  %run nisar_filtrar.py
Salidas en ./nisar_filtrado/: nisar_productos.csv, nisar_cosismicos.csv,
  nisar_lista_descarga.txt, nisar_huellas.geojson, nisar_mapa_cobertura.png
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import T, csv_bilingue, guardar_bilingue
import json
import os
import re

import asf_search as asf
import geopandas as gpd
import pandas as pd
from shapely.geometry import box, shape

SALIDA = "./nisar_filtrado"
os.makedirs(SALIDA, exist_ok=True)

SISMO = pd.Timestamp("2026-06-24T22:04:33Z")            # Mw 7.2 (USGS)
# Zona completa de ruptura (Yumare -> Caracas) y zona de detalle (La Guaira)
ROI_RUPTURA = box(-68.6, 10.0, -66.4, 11.0)
ROI_GUAIRA = box(-67.3, 10.4, -66.7, 10.8)               # mismo polígono del notebook
FECHA_INI, FECHA_FIN = "2026-05-15", "2026-08-15"

# Tracks publicados por Scripps/UCSD (para comparar con nuestro resultado)
TRACKS_UCSD = {"162A", "061A", "054D", "126D"}

# Footprints de Umbra (generados por umbra_inventario.py), opcional
UMBRA_GEOJSON = "./umbra_inventario/umbra_huellas.geojson"


def fechas_del_nombre(nombre):
    """Extrae todas las fechas YYYYMMDDTHHMMSS del nombre del producto."""
    f = re.findall(r"(\d{8}T\d{6})", nombre)
    return sorted({pd.Timestamp(x, tz="UTC") for x in f})


def clasificar(ref, sec):
    if ref is None or sec is None:
        return "SIN_FECHAS"
    if ref < SISMO < sec:
        return "COSISMICO"
    return "PRE-SISMICO" if sec < SISMO else "POST-SISMICO"


def tamano_mb(b):
    """En Sentinel-1 'bytes' es un número; en NISAR es un dict {archivo: {'bytes': n, ...}}."""
    if b is None:
        return None
    if isinstance(b, (int, float)):
        return round(b / 1e6, 1)
    if isinstance(b, dict):
        total = 0
        for v in b.values():
            if isinstance(v, dict):
                total += v.get("bytes", 0) or 0
            elif isinstance(v, (int, float)):
                total += v
        return round(total / 1e6, 1) if total else None
    return None


def buscar_nisar(nivel):
    try:
        return asf.geo_search(platform=[asf.PLATFORM.NISAR], intersectsWith=ROI_RUPTURA.wkt,
                              start=FECHA_INI, end=FECHA_FIN, processingLevel=nivel)
    except Exception as e:
        print(f"[!] Búsqueda {nivel} falló: {e}")
        return []


# ---------------------------------------------------------------------------
# 1. Búsqueda
# ---------------------------------------------------------------------------
umbra = None
if os.path.exists(UMBRA_GEOJSON):
    umbra = gpd.read_file(UMBRA_GEOJSON)
    print(f"Umbra: {len(umbra)} huellas cargadas para cruzar.")

filas = []
for nivel in ["GUNW", "RSLC"]:
    res = buscar_nisar(nivel)
    print(f"NISAR {nivel}: {len(res)} productos en la zona de ruptura")
    for r in res:
        p = r.properties
        nombre = p.get("sceneName") or p.get("fileID") or p.get("fileName", "")
        geom = shape(r.geometry)
        fechas = fechas_del_nombre(nombre)

        if nivel == "GUNW":
            # El GUNW lleva fecha de referencia y secundaria en el nombre (inicio/fin de cada una)
            ref = fechas[0] if fechas else None
            sec = fechas[-1] if len(fechas) > 1 else None
            if ref is not None and sec is not None and (sec - ref).days < 1:
                sec = None                       # solo encontró una adquisición -> revisar
        else:
            ref = pd.Timestamp(p["startTime"]) if p.get("startTime") else None
            sec = None

        direccion = (p.get("flightDirection") or "").upper()[:1]  # A / D
        track = f"{int(p['pathNumber']):03d}{direccion}" if p.get("pathNumber") is not None else None
        inter_guaira = geom.intersection(ROI_GUAIRA).area / ROI_GUAIRA.area * 100

        toca_umbra = None
        if umbra is not None:
            toca_umbra = int(umbra.intersects(geom).sum())

        filas.append({
            "nivel": nivel,
            "nombre": nombre,
            "track": track,
            "frame": p.get("frameNumber"),
            "direccion": p.get("flightDirection"),
            "fecha_ref": ref,
            "fecha_sec": sec,
            "dias": (sec - ref).days if (ref is not None and sec is not None) else None,
            "tipo": clasificar(ref, sec) if nivel == "GUNW" else
                    ("PRE" if ref is not None and ref < SISMO else "POST"),
            "cubre_LaGuaira_%": round(inter_guaira, 1),
            "escenas_Umbra_que_toca": toca_umbra,
            "en_UCSD": track in TRACKS_UCSD if track else None,
            "MB": tamano_mb(p.get("bytes")),
            "url": p.get("url"),
            "geometry": geom,
        })

if not filas:
    raise SystemExit("No se encontraron productos NISAR. Revise autenticación / fechas.")

gdf = gpd.GeoDataFrame(filas, geometry="geometry", crs="EPSG:4326")
gdf = gdf.sort_values(["nivel", "track", "fecha_ref"]).reset_index(drop=True)
csv_bilingue(gdf.drop(columns="geometry"), f"{SALIDA}/nisar_productos.csv")
gdf[["nivel", "nombre", "track", "tipo", "geometry"]].to_file(
    f"{SALIDA}/nisar_huellas.geojson", driver="GeoJSON")

# ---------------------------------------------------------------------------
# 2. Resumen y filtro
# ---------------------------------------------------------------------------
gunw = gdf[gdf.nivel == "GUNW"]
print("\n=== GUNW por tipo ===")
print(gunw.groupby(["tipo", "track"]).size().to_string())

cos = gunw[(gunw.tipo == "COSISMICO") & (gunw["cubre_LaGuaira_%"] > 0)].copy()
cos = cos.sort_values(["dias", "cubre_LaGuaira_%"], ascending=[True, False])
csv_bilingue(cos.drop(columns="geometry"), f"{SALIDA}/nisar_cosismicos.csv")

print(f"\n=== {len(cos)} GUNW COSÍSMICOS que tocan La Guaira ===")
cols = ["track", "frame", "fecha_ref", "fecha_sec", "dias", "cubre_LaGuaira_%",
        "escenas_Umbra_que_toca", "en_UCSD", "nombre"]
print(cos[cols].to_string(index=False))

# Mejor par por track: menor línea base temporal y mayor cobertura
mejor = cos.groupby("track", as_index=False).first()
with open(f"{SALIDA}/nisar_lista_descarga.txt", "w") as f:
    for u in mejor.url.dropna():
        f.write(u + "\n")
print(f"\nMejor GUNW por track ({len(mejor)}) -> {SALIDA}/nisar_lista_descarga.txt")
print(mejor[["track", "fecha_ref", "fecha_sec", "dias", "cubre_LaGuaira_%"]].to_string(index=False))

asc = mejor.direccion.str.upper().str.startswith("A").any()
desc = mejor.direccion.str.upper().str.startswith("D").any()
print(f"\n¿Geometría ascendente y descendente? ASC={asc}  DESC={desc}"
      + ("  -> se puede descomponer en Este/Vertical" if asc and desc else
         "  -> falta una geometría para la descomposición 2D"))
faltan = TRACKS_UCSD - set(mejor.track.dropna())
if faltan:
    print(f"Tracks usados por UCSD que NO aparecen como cosísmicos aquí: {sorted(faltan)}"
          " (puede que solo existan como RSLC: habría que formar el par uno mismo)")

sin_f = gunw[gunw.tipo == "SIN_FECHAS"]
if len(sin_f):
    print(f"\n[!] {len(sin_f)} GUNW sin dos fechas legibles en el nombre: revisarlos a mano.")

# ---------------------------------------------------------------------------
# 3. Mapa de cobertura
# ---------------------------------------------------------------------------
try:
    import contextily as cx
    import matplotlib.pyplot as plt

    g3857 = gdf.to_crs("EPSG:3857")
    colores = {"COSISMICO": "#d62728", "PRE-SISMICO": "#7f7f7f", "POST-SISMICO": "#1f77b4"}

    def _mapa(idioma):
        fig, ax = plt.subplots(figsize=(13, 7))
        for tipo, color in colores.items():
            sub = g3857[(g3857.nivel == "GUNW") & (g3857.tipo == tipo)]
            if len(sub):
                sub.boundary.plot(ax=ax, color=color, linewidth=1.2, label=T(f"gunw_{tipo}", idioma))
        gpd.GeoSeries([ROI_GUAIRA], crs="EPSG:4326").to_crs("EPSG:3857").boundary.plot(
            ax=ax, color="yellow", linewidth=2.5, label=T("roi_guaira", idioma))
        if umbra is not None:
            umbra.to_crs("EPSG:3857").plot(ax=ax, color="cyan", alpha=0.6, label="Umbra (X)")
        cx.add_basemap(ax, source=cx.providers.Esri.WorldImagery, attribution_size=6)
        ax.legend(loc="lower left", fontsize=9)
        ax.set_title(T("nisar_mapa_tit", idioma))
        ax.set_axis_off()
        fig.tight_layout()
        return fig

    print("Mapas / maps:", guardar_bilingue(_mapa, f"{SALIDA}/nisar_mapa_cobertura"))
except Exception as e:
    print(f"(Mapa omitido: {e})")

# ---------------------------------------------------------------------------
# 4. Descarga SOLO de los cosísmicos seleccionados (descomentar)
# ---------------------------------------------------------------------------
# urls = open(f"{SALIDA}/nisar_lista_descarga.txt").read().split()
# asf.download_urls(urls=urls, path="./datos_nisar_vargas", session=session, processes=4)
