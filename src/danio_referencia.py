# -*- coding: utf-8 -*-
"""
Daño de referencia y zonas de contraste (dañado vs. no dañado)
Reference damage and contrast zones (damaged vs. undamaged)

Fuentes / Sources
  1. HOTOSM · Hugging Face `hotosm/venezuela_eq_2026`: huellas de edificios y daño por edificio
     (fAIr + Microsoft AI for Good + OSU/CUNY Sentinel-1, validado con MapSwipe).
  2. Copernicus EMS EMSR884 (gradación de daño, 13 áreas de interés). Si la descarga automática falla,
     descargue el paquete vectorial desde https://mapping.emergency.copernicus.eu/activations/EMSR884/download/
     y descomprímalo en  <RAIZ>/01_datos_crudos/danio_referencia/cems/  (el script lo lee solo).

Salidas / Outputs (<RAIZ>/01_datos_crudos/danio_referencia/)
  · danio_referencia.gpkg  capa `edificios_danio` (clase normalizada: destruido / dañado / posible / sin_daño)
  · pares_contraste.csv (+ _en)  por sitio: centro de zona DAÑADA y centro de zona NO DAÑADA cercana
  · mapa de contraste por sitio (ES/EN) en 04_figuras/borradores
"""
import glob
import os
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import Point

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import csv_bilingue, guardar_bilingue, TXT, T

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
OUT = f"{RAIZ}/01_datos_crudos/danio_referencia"
CEMS_DIR = f"{OUT}/cems"
HF_DIR = f"{OUT}/hotosm"
FIG = f"{RAIZ}/04_figuras/borradores"
for d in (OUT, CEMS_DIR, HF_DIR, FIG):
    os.makedirs(d, exist_ok=True)
GPKG = f"{OUT}/danio_referencia.gpkg"
CRS = "EPSG:32619"
RADIO_SITIO_M = 1500
SITIOS = {
    "Catia_La_Mar": (10.6055, -67.0324), "Playa_Grande_Urimare": (10.6100, -67.0103),
    "La_Guaira": (10.6000, -66.9331), "Caraballeda": (10.6122, -66.8519),
    "Tanaguarena": (10.6150, -66.8200), "Naiguata": (10.6200, -66.7400),
}


# --------------------------------------------------------------------------
# Normalización de clases de daño / damage class normalisation
# --------------------------------------------------------------------------
def clase_normalizada(v):
    """Etiquetas tipo xView2/HOTOSM (no-damage, minor-damage, major-damage, destroyed), CEMS y booleanas."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = str(v).strip().lower().replace("-", " ").replace("_", " ")
    if s in ("", "nan", "none", "un classified", "unclassified", "unknown") or "no data" in s or "nodata" in s:
        return None
    if s.startswith("no ") or s in ("0", "0.0", "false", "intact") or "sin da" in s or "undamag" in s or "no visible" in s:
        return "sin_daño"
    if any(k in s for k in ("destroy", "destru", "collaps", "colaps")):
        return "destruido"
    if any(k in s for k in ("possib", "posib", "probabl")):
        return "posible"
    if s in ("1", "1.0", "true") or any(k in s for k in ("damag", "dañ", "major", "minor", "moderate", "severe")):
        return "dañado"
    return None


def columna_danio(df):
    prefer = [c for c in df.columns if any(k in c.lower() for k in ("damage_gra", "grading", "damage", "dmg", "dano", "daño"))]
    prefer += [c for c in df.columns if "class" in c.lower() or "label" in c.lower()]
    for c in prefer:
        vals = df[c].dropna().astype(str).map(clase_normalizada)
        if vals.notna().mean() > 0.5:
            return c
    return None


AREA_ESTUDIO = (-67.25, 10.50, -66.60, 10.70)          # costa de La Guaira (lon_min, lat_min, lon_max, lat_max)
ZONAS_HOT = globals().get("ZONAS_HOT", ["catia_la_mar", "la_guaira", "caraballeda", "naiguata", "carayaca"])


def leer_vector(f, fuente, columna=None, extra=None):
    """Lee UN archivo, recortado al área de estudio, solo con la columna de daño. Low-memory read."""
    try:
        g = gpd.read_file(f, bbox=AREA_ESTUDIO)
    except Exception as e:
        print(f"   [!] {os.path.basename(f)}: {e}"); return None
    if g.empty:
        return None
    col = columna if columna in g.columns else columna_danio(g)
    if col is None:
        print(f"   [–] {os.path.basename(f)}: sin columna de daño / no damage column"); return None
    vc = g[col].astype(str).value_counts().head(8)
    print(f"   {fuente}: {os.path.basename(f)} · '{col}' · {len(g)} · valores/values: {dict(vc)}")
    g = g.to_crs(4326)
    out = gpd.GeoDataFrame({"clase": g[col].map(clase_normalizada), "valor_original": g[col].astype(str),
                            "fuente": fuente, "archivo": os.path.basename(f)}, geometry=g.geometry, crs=4326)
    if extra:
        for k, v in extra.items():
            out[k] = v
    return out.dropna(subset=["clase"])


# --------------------------------------------------------------------------
# 1. HOTOSM (Hugging Face)
# --------------------------------------------------------------------------
capas = []
try:
    from huggingface_hub import snapshot_download
    patrones = [f"*{z}_damage_polygons.geojson" for z in ZONAS_HOT] + \
               [f"*{z}_osu_damaged_polygons.geojson" for z in ZONAS_HOT] + ["*venezuela_validated_damage.geojson", "*.md"]
    snapshot_download(repo_id="hotosm/venezuela_eq_2026", repo_type="dataset", local_dir=HF_DIR, allow_patterns=patrones)
except Exception as e:
    print(f"[!] HOTOSM Hugging Face: {e}  ->  pip install huggingface_hub")
for z in ZONAS_HOT:                                        # daño fusionado fAIr/Microsoft por edificio
    for f in glob.glob(f"{HF_DIR}/**/{z}_damage_polygons.geojson", recursive=True)[:1]:
        g = leer_vector(f, "HOTOSM", "damage", {"zona": z, "validado": False})
        if g is not None:
            capas.append(g)
# Validación MapSwipe: el significado de 'damaged' (0–7) se toma de SCHEMAS.md; se guarda aparte, sin clasificar
# MapSwipe validation: meaning of 'damaged' (0–7) comes from SCHEMAS.md; stored separately, not classified
for f in glob.glob(f"{HF_DIR}/**/SCHEMAS.md", recursive=True)[:1]:
    lineas = open(f, encoding="utf-8", errors="ignore").read().splitlines()
    rel = [l for i_, l in enumerate(lineas) if "damaged" in l.lower() or "validat" in l.lower() or "mapswipe" in l.lower()]
    print("\n[SCHEMAS.md] definición de la validación / validation definition:")
    print("\n".join("   " + l for l in rel[:25]) or "   (no encontrada / not found)")
for f in glob.glob(f"{HF_DIR}/**/venezuela_validated_damage.geojson", recursive=True)[:1]:
    try:
        v = gpd.read_file(f, bbox=AREA_ESTUDIO).to_crs(4326)
        keep = [c for c in v.columns if c in ("damaged", "sources", "h3", "h3_index", "total", "count", "agreement")]
        v[keep + ["geometry"]].to_file(GPKG, layer="validacion_mapswipe", driver="GPKG")
        print(f"   Validación MapSwipe guardada / saved: {len(v)} celdas · columnas {keep}")
    except Exception as e:
        print(f"   [!] validación / validation: {e}")
gc_ = __import__("gc"); gc_.collect()

# --------------------------------------------------------------------------
# 2. Copernicus EMS EMSR884 (automático si es posible; si no, manual en cems/)
# --------------------------------------------------------------------------
if not glob.glob(f"{CEMS_DIR}/**/*.shp", recursive=True) and not glob.glob(f"{CEMS_DIR}/**/*.zip", recursive=True):
    print("[i] CEMS: descargue el paquete vectorial (grading) de / download the vector package from:\n"
          "    https://mapping.emergency.copernicus.eu/activations/EMSR884/download/\n"
          f"    y póngalo en / and place it in: {CEMS_DIR}")
for z in glob.glob(f"{CEMS_DIR}/**/*.zip", recursive=True):
    if not os.path.isdir(z[:-4]):
        with zipfile.ZipFile(z) as zf:
            zf.extractall(z[:-4])
for f in glob.glob(f"{CEMS_DIR}/**/*.shp", recursive=True):
    if "built" in os.path.basename(f).lower() or "grading" in f.lower():       # capas de edificios graduados
        g = leer_vector(f, "Copernicus EMS EMSR884", None, {"zona": "cems", "validado": False})
        if g is not None:
            capas.append(g)

if not capas:
    raise SystemExit("No hay capas de daño todavía / no damage layers yet (ver mensajes arriba / see messages above).")

danio = gpd.GeoDataFrame(pd.concat(capas, ignore_index=True), crs=4326)
del capas
danio.to_file(GPKG, layer="edificios_danio", driver="GPKG")
csv_bilingue(pd.DataFrame([
    ("HOTOSM fAIr (daño por edificio / building damage)", "https://huggingface.co/datasets/hotosm/venezuela_eq_2026", "CC BY-NC-SA 4.0"),
    ("Microsoft AI for Good Lab", "https://huggingface.co/datasets/hotosm/venezuela_eq_2026", "CC BY 4.0"),
    ("OSU/CUNY Sentinel-1 (Scher & Van Den Hoek, experimental)", "https://huggingface.co/datasets/hotosm/venezuela_eq_2026", "citar / cite"),
    ("MapSwipe validation", "https://huggingface.co/datasets/hotosm/venezuela_eq_2026", "CC BY-SA 4.0"),
    ("Copernicus EMS EMSR884", "https://mapping.emergency.copernicus.eu/activations/EMSR884/", "Copernicus EMS"),
], columns=["fuente", "url", "licencia"]).assign(fecha_acceso=pd.Timestamp.today().date().isoformat()),
    f"{RAIZ}/05_documentacion/fuentes_danio_referencia.csv")
resumen = danio.groupby(["fuente", "clase"]).size().unstack(fill_value=0)
print("\nControl: valores originales → clase / original values → class")
print(danio.groupby(["valor_original", "clase"]).size().sort_values(ascending=False).head(15).to_string())
print("\n=== Edificios por clase / buildings per class ===\n" + resumen.to_string())
csv_bilingue(resumen, f"{OUT}/resumen_clases_danio.csv", index=True)

# --------------------------------------------------------------------------
# 3. Zonas de contraste por sitio / contrast zones per site
# --------------------------------------------------------------------------
d_utm = danio.to_crs(CRS)
d_utm["c"] = d_utm.geometry.centroid
# zona válida = Umbra ∩ Planet (si existen los inventarios) / valid zone = Umbra ∩ Planet
zona_valida = None
try:
    from shapely.ops import unary_union
    um = gpd.read_file("./umbra_inventario/umbra_huellas.geojson").set_crs(4326, allow_override=True).to_crs(CRS)
    zona_valida = unary_union(list(um.geometry))
    pq = "./umbra_planet_sitios/planet_post_items.parquet"
    if os.path.exists(pq):
        pl = gpd.read_parquet(pq).to_crs(CRS)
        zona_valida = zona_valida.intersection(unary_union(list(pl.geometry)))
except Exception as e:
    print(f"[i] Sin zona Umbra∩Planet (se usa todo) / no Umbra∩Planet zone: {e}")

from pyproj import Transformer
a_utm = Transformer.from_crs(4326, 32619, always_xy=True)
a_geo = Transformer.from_crs(32619, 4326, always_xy=True)
pares = []
for sitio, (lat, lon) in SITIOS.items():
    x0, y0 = a_utm.transform(lon, lat)
    cerca = d_utm[d_utm.c.distance(Point(x0, y0)) < RADIO_SITIO_M]
    if zona_valida is not None and not zona_valida.is_empty:
        cerca_v = cerca[cerca.c.within(zona_valida)]
        if len(cerca_v) >= 10:
            cerca = cerca_v
    D = cerca[cerca.clase.isin(["destruido", "dañado"])]
    U = cerca[cerca.clase == "sin_daño"]
    if D.empty or U.empty:
        print(f"[–] {sitio}: sin dañados y no dañados suficientes / not enough damaged and undamaged buildings")
        continue
    D = D.iloc[:3000]; U = U.iloc[:4000]                    # límite de memoria / memory cap
    xy_d = np.c_[D.c.x, D.c.y]; xy_u = np.c_[U.c.x, U.c.y]; xy_all_d = xy_d
    # zona dañada: centro con más edificios destruidos/dañados en 100 m (peso 2 a destruidos)
    peso = np.where(D.clase.values == "destruido", 2, 1)
    dist = np.hypot(xy_d[:, None, 0] - xy_d[None, :, 0], xy_d[:, None, 1] - xy_d[None, :, 1])
    i = int(np.argmax(((dist < 100) * peso[None, :]).sum(1)))
    cd = xy_d[i]
    # zona no dañada: 200–900 m de la dañada, sin dañados en 150 m, máxima densidad de edificios sanos
    du = np.hypot(xy_u[:, 0] - cd[0], xy_u[:, 1] - cd[1])
    dd = np.hypot(xy_u[:, None, 0] - xy_all_d[None, :, 0], xy_u[:, None, 1] - xy_all_d[None, :, 1]).min(1)
    ok = (du > 200) & (du < 900) & (dd > 150)
    if not ok.any():
        ok = (du > 150) & (dd > 100)
    if not ok.any():
        print(f"[–] {sitio}: no hay zona sana cercana / no nearby undamaged zone"); continue
    duu = np.hypot(xy_u[:, None, 0] - xy_u[None, :, 0], xy_u[:, None, 1] - xy_u[None, :, 1])
    dens = (duu < 100).sum(1).astype(float); dens[~ok] = -1
    cu = xy_u[int(np.argmax(dens))]
    lond, latd = a_geo.transform(*cd); lonu, latu = a_geo.transform(*cu)
    pares.append(dict(sitio=sitio, lat_danio=round(latd, 6), lon_danio=round(lond, 6),
                      n_danio_100m=int(((dist[i] < 100)).sum()), lat_sano=round(latu, 6), lon_sano=round(lonu, 6),
                      n_sano_100m=int(dens.max()), separacion_m=round(float(np.hypot(*(cd - cu)))),
                      fuentes=", ".join(sorted(cerca.fuente.unique()))))
    print(f"✓ {sitio}: dañado/damaged ({latd:.5f}, {lond:.5f}) · sano/undamaged ({latu:.5f}, {lonu:.5f}) · "
          f"{pares[-1]['separacion_m']} m")

pares = pd.DataFrame(pares)
COLS_EXTRA = {"lat_danio": "lat_damaged", "lon_danio": "lon_damaged", "n_danio_100m": "n_damaged_100m",
              "lat_sano": "lat_undamaged", "lon_sano": "lon_undamaged", "n_sano_100m": "n_undamaged_100m",
              "separacion_m": "separation_m", "fuentes": "sources", "clase": "class"}
import comun; comun.COLS_EN.update(COLS_EXTRA); comun.VALORES_EN.update(
    {"destruido": "destroyed", "dañado": "damaged", "posible": "possibly damaged", "sin_daño": "no visible damage"})
csv_bilingue(pares, f"{OUT}/pares_contraste.csv")
print(f"\nPares de contraste / contrast pairs -> {OUT}/pares_contraste.csv")
print("Se usan automáticamente en umbra_planet_sitios.py / used automatically by umbra_planet_sitios.py")
