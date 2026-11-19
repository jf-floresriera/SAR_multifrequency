# -*- coding: utf-8 -*-
"""
Cruce Umbra (banda X) × Planet (óptico) – Sismo de Venezuela 24/06/2026
=========================================================================
Para cada zona donde una escena Umbra se superpone con una escena Planet post-evento,
genera una figura de 3 paneles alineados en la MISMA grilla UTM 19N:

   [A] Planet ANTES  (mosaico trimestral Q1-2026, ~4.8 m)
   [B] Planet DESPUÉS (SkySat / Pelican, ~0.5 m, 26-28 jun)
   [C] Umbra DESPUÉS (GEC, amplitud en dB, sub-métrico, día o noche)

Requiere haber corrido antes umbra_inventario.py (usa sus CSV y GeoJSON).

Uso en Colab:
  !pip install -q rasterio geopandas shapely pyarrow matplotlib requests
  %run cruce_umbra_planet.py

Salidas en ./cruce_umbra_planet/:
  superposiciones.csv               -> tabla Umbra × Planet (área, fechas, desfase en horas)
  chips/<zona>_<umbra>_<planet>.png  -> figura de 3 paneles por superposición (300 dpi)
  mosaico_comparacion.png            -> figura resumen (una fila por zona) para el artículo

Licencias que se imprimen en cada figura:
  Umbra: CC BY 4.0  ·  Planet: CC BY-NC 4.0 © Planet Labs PBC
"""
import json
import os

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from shapely.geometry import box

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
SALIDA = "./cruce_umbra_planet"
os.makedirs(f"{SALIDA}/chips", exist_ok=True)

UMBRA_DIR = "./umbra_inventario"
UMBRA_BUCKET_HTTPS = "https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/"
PLANET_BASE = "https://data.source.coop/planet/disasterdata/venezuela-earthquake-2026-06-24"
PLANET_POST_PARQUET = f"{PLANET_BASE}/post-event/items.parquet"
PLANET_PRE_MOSAICO = f"{PLANET_BASE}/pre-event/quarterly-mosaic/quarterly-mosaic-2026Q1.tif"

CRS_TRABAJO = "EPSG:32619"   # UTM 19N (igual que el notebook)
LADO_CHIP_M = 1500           # tamaño del recorte (m)
RES_CHIP_M = 0.5             # resolución común de salida (m/píxel)
MIN_AREA_KM2 = 0.25          # superposición mínima para generar figura
MAX_CHIPS = 40               # límite de seguridad
HORA_LOCAL = "America/Caracas"

# Nombres aproximados de zona a partir de la longitud del centro (ajustar con el mapa)
ZONAS = [
    (-68.80, -68.50, "Yumare"),
    (-67.85, -67.65, "Ocumare_Henri_Pittier"),
    (-67.06, -66.88, "Costa_La_Guaira"),
    (-66.88, -66.74, "Caracas_Este_Petare"),
    (-66.74, -66.45, "Guarenas_Guatire"),
]

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.tiff")


def zona_de(lon):
    for lo, hi, nombre in ZONAS:
        if lo <= lon < hi:
            return nombre
    return f"lon{lon:.2f}"


# ---------------------------------------------------------------------------
# 1. Cargar Umbra (huellas + URL del GEC)
# ---------------------------------------------------------------------------
umbra = gpd.read_file(f"{UMBRA_DIR}/umbra_huellas.geojson").set_crs("EPSG:4326", allow_override=True)
inv = pd.read_csv(f"{UMBRA_DIR}/umbra_inventario.csv", parse_dates=["inicio_utc"])
listado = pd.read_csv(f"{UMBRA_DIR}/umbra_listado_completo.csv")
gecs = listado[listado.key.str.contains("GEC", case=False) &
               listado.key.str.lower().str.endswith((".tif", ".tiff"))]

umbra = umbra.merge(inv[["task_id", "inicio_utc", "satelite", "incidencia_deg", "squint_deg",
                         "direccion_mirada", "lon_centro"]], on="task_id", how="left",
                    suffixes=("_geo", ""))
umbra["gec_url"] = umbra.task_id.map(
    lambda t: UMBRA_BUCKET_HTTPS + gecs[gecs.key.str.contains(t)].key.iloc[0]
    if gecs.key.str.contains(t).any() else None)
umbra["zona"] = umbra.lon_centro.map(zona_de)
print(f"Umbra: {len(umbra)} huellas, {umbra.gec_url.notna().sum()} con GEC")

# ---------------------------------------------------------------------------
# 2. Cargar índice Planet post-evento (STAC-GeoParquet)
# ---------------------------------------------------------------------------
local_parquet = f"{SALIDA}/planet_post_items.parquet"
if not os.path.exists(local_parquet):
    r = requests.get(PLANET_POST_PARQUET, timeout=120)
    r.raise_for_status()
    open(local_parquet, "wb").write(r.content)
planet = gpd.read_parquet(local_parquet).to_crs("EPSG:4326")


def href_visual(assets):
    if isinstance(assets, str):
        assets = json.loads(assets)
    for k in ("visual", "analytic"):
        a = assets.get(k) if isinstance(assets, dict) else None
        if a:
            return a.get("href") if isinstance(a, dict) else a
    return None


def url_absoluta(fila, rel):
    """Los hrefs del índice son relativos ('./xxx_visual.tif'): se resuelven contra el ítem.
    Se prueban varias rutas candidatas y se queda la primera que responde 200."""
    from urllib.parse import urljoin
    if not rel:
        return None
    if str(rel).startswith("http"):
        return rel
    candidatos = []
    links = fila.get("links")
    if isinstance(links, str):
        links = json.loads(links)
    if links is not None:
        for l in list(links):
            if isinstance(l, dict) and l.get("rel") == "self" and str(l.get("href", "")).startswith("http"):
                candidatos.append(urljoin(l["href"], rel))
    archivo = str(rel).replace("./", "", 1)
    for lugar in (fila.get("location_slug"), fila.get("location"), fila.get("collection")):
        if isinstance(lugar, str) and lugar:
            candidatos.append(f"{PLANET_BASE}/post-event/{lugar}/items/{fila['id']}/{archivo}")
            candidatos.append(f"{PLANET_BASE}/post-event/{lugar}/{fila['id']}/{archivo}")
    candidatos.append(f"{PLANET_BASE}/post-event/items/{fila['id']}/{archivo}")
    for u in dict.fromkeys(candidatos):          # sin duplicados, en orden
        try:
            if requests.head(u, timeout=20, allow_redirects=True).status_code == 200:
                return u
        except requests.RequestException:
            pass
    print(f"  [!] No se encontró URL válida para {fila['id']} ({rel}). Probadas: {len(candidatos)}")
    return None


planet["visual_rel"] = planet["assets"].map(href_visual)
planet["visual_url"] = [url_absoluta(f, r) for f, r in zip(planet.to_dict("records"), planet.visual_rel)]
print(f"URLs Planet resueltas: {planet.visual_url.notna().sum()}/{len(planet)}")
if planet.visual_url.notna().any():
    print("  ejemplo:", planet.visual_url.dropna().iloc[0])
planet = planet[planet.visual_url.notna()]
planet["fecha"] = pd.to_datetime(planet["datetime"], utc=True)
col_lugar = next((c for c in ("location", "location_slug", "collection") if c in planet.columns), None)
print(f"Planet post-evento: {len(planet)} escenas")

# ---------------------------------------------------------------------------
# 3. Superposiciones Umbra × Planet
# ---------------------------------------------------------------------------
u_m = umbra.to_crs(CRS_TRABAJO)
p_m = planet.to_crs(CRS_TRABAJO)
sup = []
for _, u in u_m.iterrows():
    for _, p in p_m[p_m.intersects(u.geometry)].iterrows():
        inter = u.geometry.intersection(p.geometry)
        area = inter.area / 1e6
        if area < MIN_AREA_KM2:
            continue
        sup.append({
            "zona": u.zona, "umbra_task": u.task_id, "umbra_sat": u.satelite,
            "umbra_utc": u.inicio_utc, "umbra_local": u.inicio_utc.tz_convert(HORA_LOCAL),
            "umbra_mirada": u.direccion_mirada, "umbra_incid": u.incidencia_deg,
            "planet_id": p["id"], "planet_const": p.get("constellation"),
            "planet_lugar": p.get(col_lugar) if col_lugar else None,
            "planet_utc": p.fecha, "planet_gsd": p.get("gsd"),
            "desfase_h": round((p.fecha - u.inicio_utc).total_seconds() / 3600, 1),
            "area_km2": round(area, 2),
            "cx": inter.centroid.x, "cy": inter.centroid.y,
            "umbra_url": u.gec_url, "planet_url": p.visual_url,
        })
sup = pd.DataFrame(sup).sort_values(["zona", "area_km2"], ascending=[True, False])
sup.drop(columns=["cx", "cy"]).to_csv(f"{SALIDA}/superposiciones.csv", index=False)
print(f"\n{len(sup)} superposiciones ≥ {MIN_AREA_KM2} km²")
if sup.empty:
    raise SystemExit("No hay superposición Umbra × Planet post-evento.")
print(sup.groupby("zona").agg(n=("area_km2", "size"), area_max=("area_km2", "max"),
                             desfase_min_h=("desfase_h", lambda s: s.abs().min())).to_string())


# ---------------------------------------------------------------------------
# 4. Lectura alineada de un recorte (cualquier fuente -> grilla UTM común)
# ---------------------------------------------------------------------------
def leer_chip(url, cx, cy, bandas, lado=LADO_CHIP_M, res=RES_CHIP_M):
    n = int(lado / res)
    transform = from_origin(cx - lado / 2, cy + lado / 2, res, res)
    with rasterio.open(url) as src:
        with WarpedVRT(src, crs=CRS_TRABAJO, transform=transform, width=n, height=n,
                       resampling=Resampling.bilinear) as vrt:
            b = [i for i in bandas if i <= vrt.count]
            arr = vrt.read(b, masked=True).astype("float32")
    return arr


def a_rgb(arr):
    """uint8/uint16 -> RGB 0-1 con estiramiento 2-98 % (robusto a mosaicos y pansharpened)."""
    rgb = np.ma.filled(arr[:3], np.nan)
    out = np.zeros(rgb.shape[1:] + (3,), dtype="float32")
    for i in range(min(3, rgb.shape[0])):
        b = rgb[i]
        v = b[np.isfinite(b) & (b > 0)]
        if v.size == 0:
            continue
        lo, hi = np.percentile(v, [2, 98])
        out[..., i] = np.clip((b - lo) / max(hi - lo, 1e-6), 0, 1)
    out[np.all(~np.isfinite(rgb), axis=0)] = 1.0  # fuera de cobertura -> blanco
    return out


def a_db(arr):
    """Amplitud SAR -> dB con estiramiento 2-99 %."""
    a = np.ma.filled(arr[0], np.nan)
    a[a <= 0] = np.nan
    db = 20 * np.log10(a)
    v = db[np.isfinite(db)]
    if v.size == 0:
        return db, (0, 1)
    return db, tuple(np.percentile(v, [2, 99]))


def barra_escala(ax, n_px, res=RES_CHIP_M, metros=250):
    largo = metros / res
    x0, y0 = n_px * 0.05, n_px * 0.93
    ax.plot([x0, x0 + largo], [y0, y0], color="white", lw=4, solid_capstyle="butt")
    ax.plot([x0, x0 + largo], [y0, y0], color="black", lw=1.5, solid_capstyle="butt")
    ax.text(x0 + largo / 2, y0 - n_px * 0.025, f"{metros} m", color="white", ha="center",
            va="bottom", fontsize=8, weight="bold",
            path_effects=[pe.withStroke(linewidth=2, foreground="black")])


# ---------------------------------------------------------------------------
# 5. Figuras
# ---------------------------------------------------------------------------
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
mejores = sup.groupby("zona", as_index=False).first()   # la mayor superposición por zona
hechos = []
for _, s in sup.head(MAX_CHIPS).iterrows():
    nombre = f"{s.zona}_{s.umbra_task[:8]}_{str(s.planet_id)[:12]}"
    try:
        pre = leer_chip(PLANET_PRE_MOSAICO, s.cx, s.cy, [1, 2, 3])
        post = leer_chip(s.planet_url, s.cx, s.cy, [1, 2, 3])
        sar = leer_chip(s.umbra_url, s.cx, s.cy, [1])
    except Exception as e:
        print(f"  [!] {nombre}: {e}")
        continue
    db, (vmin, vmax) = a_db(sar)
    paneles = [
        (a_rgb(pre), None, "A · Planet ANTES\nmosaico Q1-2026 (~4.8 m)"),
        (a_rgb(post), None, f"B · Planet DESPUÉS ({s.planet_const or ''})\n"
                            f"{s.planet_utc:%d %b %H:%M} UTC · {s.planet_gsd} m"),
        (db, (vmin, vmax), f"C · Umbra banda X ({s.umbra_sat}, mirada {s.umbra_mirada})\n"
                           f"{s.umbra_local:%d %b %H:%M} hora local · incid. {s.umbra_incid:.0f}°"),
    ]
    fig, axs = plt.subplots(1, 3, figsize=(15, 5.4))
    for ax, (img, lim, titulo) in zip(axs, paneles):
        if lim is None:
            ax.imshow(img, interpolation="nearest")
        else:
            im = ax.imshow(img, cmap="gray", vmin=lim[0], vmax=lim[1], interpolation="nearest")
        ax.set_title(titulo, loc="left", fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
        barra_escala(ax, img.shape[1])
    cb = fig.colorbar(im, ax=axs[2], fraction=0.046, pad=0.02)
    cb.set_label("Amplitud (dB)")
    fig.suptitle(f"{s.zona.replace('_', ' ')} · superposición {s.area_km2} km² · "
                 f"desfase Planet–Umbra {s.desfase_h:+.0f} h", x=0.01, ha="left", fontsize=11,
                 weight="bold")
    fig.text(0.01, 0.01, "Contains Umbra open data, licensed under CC BY 4.0 · "
                         "Imagery © Planet Labs PBC, CC BY-NC 4.0", fontsize=7, color="0.35")
    plt.tight_layout(rect=(0, 0.03, 1, 0.95))
    plt.savefig(f"{SALIDA}/chips/{nombre}.png", dpi=300)
    plt.close(fig)
    hechos.append((s.zona, nombre, paneles))
    print(f"  ✓ {nombre}")

# Figura resumen: la mejor superposición de cada zona (una fila por zona)
filas = [h for h in hechos if h[1].startswith(tuple(mejores.zona))]
vistas, filas_resumen = set(), []
for z, nombre, paneles in filas:
    if z not in vistas:
        vistas.add(z)
        filas_resumen.append((z, paneles))
if filas_resumen:
    fig, axs = plt.subplots(len(filas_resumen), 3, figsize=(12, 4 * len(filas_resumen)),
                            squeeze=False)
    for i, (z, paneles) in enumerate(filas_resumen):
        for j, (img, lim, titulo) in enumerate(paneles):
            ax = axs[i, j]
            if lim is None:
                ax.imshow(img, interpolation="nearest")
            else:
                ax.imshow(img, cmap="gray", vmin=lim[0], vmax=lim[1], interpolation="nearest")
            ax.set_xticks([]); ax.set_yticks([])
            if i == 0:
                ax.set_title(["Planet antes", "Planet después (0.5 m)", "Umbra X después"][j],
                             fontsize=10, weight="bold")
            if j == 0:
                ax.set_ylabel(z.replace("_", " "), fontsize=10, weight="bold")
            barra_escala(ax, img.shape[1])
    fig.text(0.01, 0.005, "Contains Umbra open data, licensed under CC BY 4.0 · "
                          "Imagery © Planet Labs PBC, CC BY-NC 4.0", fontsize=7, color="0.35")
    plt.tight_layout(rect=(0, 0.015, 1, 1))
    plt.savefig(f"{SALIDA}/mosaico_comparacion.png", dpi=300)
    plt.show()
print(f"\nListo: {len(hechos)} figuras en {SALIDA}/chips/")
