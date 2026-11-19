# -*- coding: utf-8 -*-
"""
Mapas base para el proyecto / Base maps for the project
  · Límites administrativos de Venezuela: país, estados, municipios (geoBoundaries, CC BY 4.0)
  · Fallas activas (GEM Global Active Faults Database, CC BY-SA 4.0)
  · Vías principales del área de estudio (OpenStreetMap vía Overpass, ODbL)
  · Epicentros USGS (Mw 7.2 y Mw 7.5) y sitios de daño
  · Figura de ubicación bilingüe (ES/EN) = candidata a Figura 1 del artículo

Salida / Output: <RAIZ>/01_datos_crudos/mapas_base/mapas_base.gpkg (una capa por tema / one layer per theme)
"""
import json
import os

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import requests
from shapely.geometry import LineString, Point, box

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import T, csv_bilingue, guardar_bilingue, TXT

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
OUT = f"{RAIZ}/01_datos_crudos/mapas_base"
FIG = f"{RAIZ}/04_figuras/borradores"
os.makedirs(OUT, exist_ok=True); os.makedirs(FIG, exist_ok=True)
GPKG = f"{OUT}/mapas_base.gpkg"
AREA = box(-69.2, 9.9, -65.9, 11.0)          # Yumare → Naiguatá, con margen / with margin
H = {"User-Agent": "GUAIRA-SAR research (github.com/jf-floresriera/SAR_multifrequency)"}
fuentes = []


def guardar(gdf, capa):
    gdf.to_file(GPKG, layer=capa, driver="GPKG")
    print(f"✓ {capa}: {len(gdf)} elementos / features")


# 1) Límites administrativos (geoBoundaries) -------------------------------------------
for nivel, capa in (("ADM0", "venezuela_pais"), ("ADM1", "venezuela_estados"), ("ADM2", "venezuela_municipios")):
    try:
        meta = requests.get(f"https://www.geoboundaries.org/api/current/gbOpen/VEN/{nivel}/", headers=H, timeout=60).json()
        url = meta.get("gjDownloadURL") or meta.get("simplifiedGeometryGeoJSON")
        g = gpd.read_file(url).to_crs(4326)
        guardar(g, capa)
        if nivel == "ADM2":
            guardar(g[g.intersects(AREA)], "municipios_area_estudio")
        fuentes.append((f"geoBoundaries VEN {nivel}", url, "CC BY 4.0"))
    except Exception as e:
        print(f"[!] geoBoundaries {nivel}: {e}")

# 2) Fallas activas (GEM GAF-DB) ------------------------------------------------------
for url in ("https://raw.githubusercontent.com/GEMScienceTools/gem-global-active-faults/master/geojson/gem_active_faults_harmonized.geojson",
            "https://raw.githubusercontent.com/cossatot/gem-global-active-faults/master/geojson/gem_active_faults.geojson"):
    try:
        f = gpd.read_file(url)
        f = f[f.intersects(AREA.buffer(1.0))].to_crs(4326)
        guardar(f, "fallas_activas_gem")
        fuentes.append(("GEM Global Active Faults (Styron & Pagani, 2020)", url, "CC BY-SA 4.0"))
        break
    except Exception as e:
        print(f"[!] GEM faults ({url.split('/')[3]}): {e}")

# 3) Vías principales (OpenStreetMap / Overpass) -------------------------------------
consulta = f"""[out:json][timeout:180];
way["highway"~"^(motorway|trunk|primary|secondary)$"]({AREA.bounds[1]},{AREA.bounds[0]},{AREA.bounds[3]},{AREA.bounds[2]});
out geom tags;"""
try:
    r = requests.post("https://overpass-api.de/api/interpreter", data={"data": consulta}, headers=H, timeout=300)
    r.raise_for_status()
    filas = [dict(osm_id=e["id"], tipo=e["tags"].get("highway"), nombre=e["tags"].get("name"),
                  ref=e["tags"].get("ref"), geometry=LineString([(p["lon"], p["lat"]) for p in e["geometry"]]))
             for e in r.json()["elements"] if e.get("type") == "way" and len(e.get("geometry", [])) > 1]
    vias = gpd.GeoDataFrame(filas, crs=4326)
    guardar(vias, "vias_principales_osm")
    fuentes.append(("OpenStreetMap contributors (Overpass API)", "https://overpass-api.de", "ODbL 1.0"))
except Exception as e:
    print(f"[!] Overpass / OSM: {e}")

# 4) Epicentros USGS y sitios de daño -------------------------------------------------
epi = []
for ev, mw in (("us6000t7zc", "Mw 7.2"), ("us6000t7zp", "Mw 7.5")):
    try:
        j = requests.get(f"https://earthquake.usgs.gov/fdsnws/event/1/query?eventid={ev}&format=geojson",
                         headers=H, timeout=60).json()
        lon, lat, z = j["geometry"]["coordinates"]
        epi.append(dict(evento=ev, magnitud=mw, prof_km=z, hora_utc=pd.to_datetime(j["properties"]["time"], unit="ms"),
                        geometry=Point(lon, lat)))
        fuentes.append((f"USGS ComCat {ev}", f"https://earthquake.usgs.gov/earthquakes/eventpage/{ev}", "public domain"))
    except Exception as e:
        print(f"[!] USGS {ev}: {e}")
if epi:
    guardar(gpd.GeoDataFrame(epi, crs=4326), "epicentros_usgs")
SITIOS = {"Catia La Mar": (10.6055, -67.0324), "Playa Grande": (10.6100, -67.0103), "La Guaira": (10.6000, -66.9331),
          "Caraballeda": (10.6122, -66.8519), "Tanaguarena": (10.6150, -66.8200), "Naiguatá": (10.6200, -66.7400)}
sitios = gpd.GeoDataFrame([dict(sitio=k, geometry=Point(v[1], v[0])) for k, v in SITIOS.items()], crs=4326)
guardar(sitios, "sitios_danio")

csv_bilingue(pd.DataFrame(fuentes, columns=["fuente", "url", "licencia"]).assign(
    fecha_acceso=pd.Timestamp.today().date().isoformat()), f"{RAIZ}/05_documentacion/fuentes_mapas_base.csv")

# 5) Figura de ubicación bilingüe -----------------------------------------------------
TXT.update({
    "ubic_tit": {"es": "Área de estudio · doblete sísmico del 24 de junio de 2026", "en": "Study area · 24 June 2026 earthquake doublet"},
    "ley_estados": {"es": "Límite estatal", "en": "State boundary"}, "ley_mun": {"es": "Límite municipal", "en": "Municipal boundary"},
    "ley_vias": {"es": "Vías principales (OSM)", "en": "Main roads (OSM)"}, "ley_fallas": {"es": "Fallas activas (GEM)", "en": "Active faults (GEM)"},
    "ley_epi": {"es": "Epicentro USGS", "en": "USGS epicentre"}, "ley_sitios": {"es": "Sitios de daño", "en": "Damage sites"},
})


def leer_capa(c):
    try:
        return gpd.read_file(GPKG, layer=c)
    except Exception:
        return None


capas = {c: leer_capa(c) for c in ("venezuela_estados", "municipios_area_estudio", "vias_principales_osm",
                                   "fallas_activas_gem", "epicentros_usgs", "sitios_danio")}


def _mapa(idioma):
    fig, ax = plt.subplots(figsize=(12, 5.2))
    ext = AREA.bounds
    if capas["municipios_area_estudio"] is not None:
        capas["municipios_area_estudio"].boundary.plot(ax=ax, color="0.75", lw=0.4, label=T("ley_mun", idioma))
    if capas["venezuela_estados"] is not None:
        capas["venezuela_estados"].boundary.plot(ax=ax, color="0.35", lw=0.9, label=T("ley_estados", idioma))
    if capas["vias_principales_osm"] is not None:
        capas["vias_principales_osm"].plot(ax=ax, color="#E07B39", lw=0.7, label=T("ley_vias", idioma))
    if capas["fallas_activas_gem"] is not None:
        capas["fallas_activas_gem"].plot(ax=ax, color="#B2182B", lw=1.6, label=T("ley_fallas", idioma))
    if capas["sitios_danio"] is not None:
        s = capas["sitios_danio"]
        s.plot(ax=ax, color="#2166AC", markersize=28, marker="o", edgecolor="white", zorder=5, label=T("ley_sitios", idioma))
        for _, r in s.iterrows():
            ax.annotate(r.sitio, (r.geometry.x, r.geometry.y), xytext=(3, 6), textcoords="offset points", fontsize=7.5)
    if capas["epicentros_usgs"] is not None:
        e = capas["epicentros_usgs"]
        e.plot(ax=ax, color="gold", marker="*", markersize=320, edgecolor="black", zorder=6, label=T("ley_epi", idioma))
        for _, r in e.iterrows():
            ax.annotate(r.magnitud, (r.geometry.x, r.geometry.y), xytext=(8, -12), textcoords="offset points",
                        fontsize=9, weight="bold")
    try:
        import contextily as cx
        cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.Esri.WorldShadedRelief, attribution_size=5, zorder=0)
    except Exception:
        pass
    ax.set_xlim(ext[0], ext[2]); ax.set_ylim(ext[1], ext[3])
    ax.set_xlabel(T("longitud", idioma)); ax.set_ylabel(T("latitud", idioma))
    ax.legend(loc="lower left", fontsize=8, framealpha=0.9)
    ax.set_title(T("ubic_tit", idioma), loc="left", fontsize=11)
    fig.tight_layout()
    return fig


print(guardar_bilingue(_mapa, f"{FIG}/mapa_ubicacion", formatos=("png", "pdf")))
print(f"\nCapas en / layers in: {GPKG}  (ábralo también en QGIS / also opens in QGIS)")
