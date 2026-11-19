# -*- coding: utf-8 -*-
"""
Inventario de datos Umbra (banda X) - Sismo de Venezuela 24/06/2026
Bucket público: s3://umbra-open-data-catalog/sar-data/tasks/Venezuela_Earthquake_Support/
Licencia de los datos: CC BY 4.0 -> citar "Contains Umbra open data, licensed under CC BY 4.0."

Qué hace:
  1. Recorre las 26 tareas y lista TODOS los archivos (sin descargar los pesados).
  2. Lee cada *METADATA.json y extrae fecha, satélite, geometría, resolución y centro.
  3. Marca qué productos hay en cada adquisición (GEC, SICD, SIDD, CPHD).
  4. Busca pares con geometría repetida (aptos para detección de cambio coherente).
  5. Guarda: umbra_inventario.csv, umbra_pares_candidatos.csv, umbra_huellas.geojson
     y un mapa umbra_mapa_adquisiciones.png.

Uso en Colab:
  !pip install -q boto3 pandas geopandas shapely contextily matplotlib
  !python umbra_inventario.py
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import T, csv_bilingue, guardar_bilingue
import json
import os
from collections import defaultdict
from itertools import combinations

import boto3
import numpy as np
import pandas as pd
from botocore import UNSIGNED
from botocore.config import Config

BUCKET = "umbra-open-data-catalog"
PREFIJO = "sar-data/tasks/Venezuela_Earthquake_Support/"
SALIDA = "./umbra_inventario"
os.makedirs(SALIDA, exist_ok=True)

# Umbrales para considerar dos adquisiciones "misma geometría" (detección de cambio coherente)
MAX_DIST_CENTRO_KM = 1.0
MAX_DIF_INCIDENCIA = 1.0   # grados
MAX_DIF_SQUINT = 1.0       # grados

s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED), region_name="us-west-2")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def listar_todo(prefijo):
    """Devuelve todas las claves (key, tamaño, fecha) bajo un prefijo."""
    claves = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefijo):
        for o in page.get("Contents", []):
            claves.append((o["Key"], o["Size"], o["LastModified"]))
    return claves


def aplanar(d, padre=""):
    """Aplana un JSON anidado: {'a': {'b': 1}} -> {'a.b': 1}. Las listas usan índice."""
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(aplanar(v, f"{padre}.{k}" if padre else k))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out.update(aplanar(v, f"{padre}[{i}]"))
    else:
        out[padre] = d
    return out


def buscar(plano, *patrones):
    """Primer valor cuya clave (en minúsculas) contenga todos los fragmentos de algún patrón.
    Robusto ante cambios de nombre entre versiones del esquema de metadatos de Umbra."""
    for patron in patrones:
        frag = [p.lower() for p in patron.split("&")]
        for k, v in plano.items():
            kl = k.lower()
            if all(f in kl for f in frag):
                return v
    return None


def tipo_producto(key):
    k = key.lower()
    if k.endswith((".tif", ".tiff")) and "gec" in k:
        return "GEC"
    if "sicd" in k:
        return "SICD"
    if "sidd" in k:
        return "SIDD"
    if k.endswith(".cphd") or "cphd" in k:
        return "CPHD"
    if k.endswith(".json"):
        return "JSON"
    return "OTRO"


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


# ---------------------------------------------------------------------------
# 1. Listado completo
# ---------------------------------------------------------------------------
print("Listando archivos del bucket...")
todas = listar_todo(PREFIJO)
print(f"  {len(todas)} objetos encontrados")

# Agrupar archivos por carpeta de adquisición (directorio que contiene el archivo)
por_carpeta = defaultdict(list)
for key, size, fecha in todas:
    por_carpeta[os.path.dirname(key)].append((key, size, fecha))

csv_bilingue(pd.DataFrame(todas, columns=["key", "bytes", "last_modified"]),
             f"{SALIDA}/umbra_listado_completo.csv")

# ---------------------------------------------------------------------------
# 2-3. Leer metadatos de cada adquisición
# ---------------------------------------------------------------------------
filas, huellas = [], []
for carpeta, archivos in sorted(por_carpeta.items()):
    jsons = [a for a in archivos if a[0].lower().endswith("metadata.json")] or \
            [a for a in archivos if a[0].lower().endswith(".stac.v2.json")] or \
            [a for a in archivos if a[0].lower().endswith(".json")]
    if not jsons:
        continue
    key_json = jsons[0][0]
    try:
        meta = json.loads(s3.get_object(Bucket=BUCKET, Key=key_json)["Body"].read())
    except Exception as e:
        print(f"  [!] No se pudo leer {key_json}: {e}")
        continue
    p = aplanar(meta)

    productos = sorted({tipo_producto(a[0]) for a in archivos} - {"JSON", "OTRO"})
    gb = sum(a[1] for a in archivos) / 1e9
    partes = carpeta.replace(PREFIJO, "").split("/")

    lat = buscar(p, "scenecenter&lat", "center&lat", "lla[0]")
    lon = buscar(p, "scenecenter&lon", "center&lon", "lla[1]")

    # --- Formato STAC (los archivos *.stac.v2.json de esta carpeta) ---
    es_stac = isinstance(meta, dict) and "properties" in meta and "geometry" in meta
    if es_stac:
        from shapely.geometry import shape
        pr = meta["properties"]
        try:
            c = shape(meta["geometry"]).centroid
            lon, lat = c.x, c.y
        except Exception:
            pass
        huellas.append({"type": "Feature", "geometry": meta["geometry"],
                        "properties": {"task_id": partes[0],
                                       "inicio_utc": pr.get("datetime") or pr.get("start_datetime")}})
        stac_vals = {
            "inicio_utc": pr.get("start_datetime") or pr.get("datetime"),
            "fin_utc": pr.get("end_datetime"),
            "satelite": pr.get("platform") or pr.get("constellation"),
            "modo": pr.get("sar:instrument_mode"),
            "incidencia_deg": pr.get("view:incidence_angle"),
            "azimut_deg": pr.get("view:azimuth"),
            "direccion_mirada": pr.get("sar:observation_direction"),
            "orbita": pr.get("sat:orbit_state"),
            "res_rango_m": pr.get("sar:resolution_range"),
            "res_azimut_m": pr.get("sar:resolution_azimuth"),
            "polarizacion": str(pr.get("sar:polarizations")),
            "squint_deg": buscar(aplanar(pr), "squint"),
            "graze_deg": buscar(aplanar(pr), "graz"),
        }
    fila = {
        "task_id": partes[0],
        "carpeta": "/".join(partes[1:]),
        "inicio_utc": buscar(p, "startatutc", "start&utc", "starttime"),
        "fin_utc": buscar(p, "endatutc", "end&utc", "endtime"),
        "satelite": buscar(p, "satellitename", "satellite"),
        "modo": buscar(p, "imagingmode", "mode"),
        "incidencia_deg": buscar(p, "angleincidence", "incidence"),
        "squint_deg": buscar(p, "anglesquint", "squint"),
        "graze_deg": buscar(p, "graze"),
        "azimut_deg": buscar(p, "angleazimuth", "azimuth&angle"),
        "direccion_mirada": buscar(p, "observationdirection", "lookdirection", "sideoftrack"),
        "orbita": buscar(p, "orbitdirection", "passdirection"),
        "res_rango_m": buscar(p, "resolutionrange", "range&resolution"),
        "res_azimut_m": buscar(p, "resolutionazimuth", "azimuth&resolution"),
        "polarizacion": str(buscar(p, "polarization")),
        "lat_centro": lat,
        "lon_centro": lon,
        "productos": ",".join(productos),
        "tamano_GB": round(gb, 2),
        "metadata_key": key_json,
    }
    if es_stac:
        fila.update({k: v for k, v in stac_vals.items() if v is not None})
        fila["lat_centro"], fila["lon_centro"] = lat, lon
    filas.append(fila)
    if es_stac:
        continue

    # Huella (polígono) si viene en los metadatos como lista de [lon, lat] o GeoJSON
    for k in ("footprintPolygonLla", "footprint", "geometry"):
        if k in meta or any(k.lower() in kk.lower() for kk in p):
            try:
                geo = meta.get(k) or meta["collects"][0].get(k)
                if geo:
                    huellas.append({"type": "Feature", "geometry": geo,
                                    "properties": {"task_id": fila["task_id"], "inicio_utc": fila["inicio_utc"]}})
            except Exception:
                pass
            break

df = pd.DataFrame(filas)
for c in ["incidencia_deg", "squint_deg", "graze_deg", "azimut_deg", "res_rango_m",
          "res_azimut_m", "lat_centro", "lon_centro"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df["inicio_utc"] = pd.to_datetime(df["inicio_utc"], errors="coerce", utc=True)
df = df.sort_values("inicio_utc").reset_index(drop=True)

csv_bilingue(df, f"{SALIDA}/umbra_inventario.csv")
print(f"\n{len(df)} adquisiciones con metadatos -> {SALIDA}/umbra_inventario.csv")
print(df[["task_id", "inicio_utc", "satelite", "incidencia_deg", "squint_deg",
          "direccion_mirada", "lat_centro", "lon_centro", "productos"]].to_string())

if huellas:
    with open(f"{SALIDA}/umbra_huellas.geojson", "w") as f:
        json.dump({"type": "FeatureCollection", "features": huellas}, f)

sismo = pd.Timestamp("2026-06-24T22:04:33Z")
n_pre = (df["inicio_utc"] < sismo).sum()
print(f"\nAdquisiciones ANTES del sismo: {n_pre} | DESPUÉS: {len(df) - n_pre}")
if n_pre == 0:
    print("  -> Todo es post-evento: el 'antes' debe venir de otro sensor "
          "(Planet Q1-2026, Sentinel-1/NISAR) o de comparaciones post-post (remoción de escombros).")

# ---------------------------------------------------------------------------
# 4. Pares con geometría repetida
# ---------------------------------------------------------------------------
pares = []
ok = df.dropna(subset=["lat_centro", "lon_centro", "incidencia_deg"])
for (i, a), (j, b) in combinations(ok.iterrows(), 2):
    d = haversine_km(a.lat_centro, a.lon_centro, b.lat_centro, b.lon_centro)
    dinc = abs(a.incidencia_deg - b.incidencia_deg)
    dsq = abs(np.nan_to_num(a.squint_deg) - np.nan_to_num(b.squint_deg))  # sin squint -> se ignora
    misma_mirada = (a.direccion_mirada == b.direccion_mirada) or pd.isna(a.direccion_mirada)
    # azimut de vista parecido (misma "pasada"); si no hay dato, no se filtra
    if not (pd.isna(a.azimut_deg) or pd.isna(b.azimut_deg)):
        daz = abs((a.azimut_deg - b.azimut_deg + 180) % 360 - 180)
        if daz > 5:
            continue
    if d <= MAX_DIST_CENTRO_KM and dinc <= MAX_DIF_INCIDENCIA and dsq <= MAX_DIF_SQUINT and misma_mirada:
        pares.append({
            "task_a": a.task_id, "fecha_a": a.inicio_utc,
            "task_b": b.task_id, "fecha_b": b.inicio_utc,
            "dias": abs((b.inicio_utc - a.inicio_utc).days),
            "dist_km": round(d, 3), "d_incid": round(dinc, 2), "d_squint": round(dsq, 2),
            "ambos_SICD": "SICD" in a.productos and "SICD" in b.productos,
        })
pares = pd.DataFrame(pares)
csv_bilingue(pares, f"{SALIDA}/umbra_pares_candidatos.csv")
print(f"\nPares con geometría repetida (candidatos a coherencia/CCD): {len(pares)}")
if len(pares):
    print(pares.to_string())

# ---------------------------------------------------------------------------
# 5. Mapa de adquisiciones
# ---------------------------------------------------------------------------
try:
    import contextily as cx
    import geopandas as gpd
    import matplotlib.pyplot as plt

    g = gpd.GeoDataFrame(ok, geometry=gpd.points_from_xy(ok.lon_centro, ok.lat_centro),
                         crs="EPSG:4326").to_crs("EPSG:3857")
    dias = (ok["inicio_utc"] - sismo).dt.total_seconds() / 86400

    def _mapa(idioma):
        fig, ax = plt.subplots(figsize=(12, 7))
        sc = ax.scatter(g.geometry.x, g.geometry.y, c=dias, cmap="viridis", s=90,
                        edgecolor="k", linewidth=0.6, zorder=3)
        for _, r in g.iterrows():
            ax.annotate(r.task_id[:8], (r.geometry.x, r.geometry.y), xytext=(4, 4),
                        textcoords="offset points", fontsize=7, zorder=4)
        cx.add_basemap(ax, source=cx.providers.Esri.WorldImagery, attribution_size=6)
        fig.colorbar(sc, ax=ax, label=T("dias_desde_sismo", idioma))
        ax.set_title(T("umbra_mapa_tit", idioma) + "\nContains Umbra open data, licensed under CC BY 4.0", fontsize=11)
        ax.set_axis_off()
        fig.tight_layout()
        return fig

    rutas = guardar_bilingue(_mapa, f"{SALIDA}/umbra_mapa_adquisiciones")
    print("\nMapas / maps:", rutas)
except Exception as e:
    print(f"(Mapa omitido: {e})")
