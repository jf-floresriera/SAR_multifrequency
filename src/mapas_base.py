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
        # 403 = el servidor rechaza el lector por defecto de geopandas: bajar con requests + User-Agent
        # 403 = server rejects geopandas' default reader: download with requests + User-Agent
        import io
        cand = []
        try:
            meta = requests.get(f"https://www.geoboundaries.org/api/current/gbOpen/VEN/{nivel}/", headers=H, timeout=60).json()
            cand += [meta.get("gjDownloadURL"), meta.get("simplifiedGeometryGeoJSON")]
        except Exception as e:
            print(f"   (API geoBoundaries: {e})")
        cand.append(f"https://raw.githubusercontent.com/wmgeolab/geoBoundaries/main/releaseData/gbOpen/VEN/{nivel}/geoBoundaries-VEN-{nivel}.geojson")
        g = url = None
        for u in [c for c in cand if c]:
            try:
                r = requests.get(u, headers=H, timeout=120); r.raise_for_status()
                g = gpd.read_file(io.BytesIO(r.content)).to_crs(4326); url = u; break
            except Exception as e:
                print(f"   {u[:70]}… → {e}")
        if g is None:
            raise RuntimeError("ninguna URL de geoBoundaries respondió / no geoBoundaries URL worked")
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

# 5) Figura de ubicación bilingüe → mapa_ubicacion.py (estilo SRL, sin Esri) / location figure in its own script
import runpy
_aqui = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", ".")
runpy.run_path(os.path.join(_aqui, "mapa_ubicacion.py"), init_globals={"RAIZ": RAIZ, "SRC": _aqui})
print(f"Capas en / layers in: {GPKG}  (ábralo también en QGIS / also opens in QGIS)")
