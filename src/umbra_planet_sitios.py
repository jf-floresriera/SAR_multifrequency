# -*- coding: utf-8 -*-
"""
Umbra (banda X) × Planet (óptico) en los SITIOS DE DAÑO – versión de bajo consumo de memoria
Umbra (X-band) × Planet (optical) at DAMAGE SITES – low-memory version

🇪🇸 Procesa UN sitio a la vez, guarda la figura en disco y libera la memoria antes del siguiente.
    Si Colab se queda sin RAM, reduzca LADO_M o procese los sitios por partes con SITIOS_A_PROCESAR.
🇬🇧 Processes ONE site at a time, writes the figure to disk and frees memory before the next one.
    If Colab runs out of RAM, reduce LADO_M or process sites in batches with SITIOS_A_PROCESAR.

Paneles por sitio / Panels per site:
  (a) Planet ANTES / before      – mosaico Q1-2026 (~4.8 m)
  (b) Planet DESPUÉS / after     – SkySat / PlanetScope (0.5–3 m)
  (c) Umbra amplitud / amplitude – dB con filtro Lee 5×5 (reduce el speckle)
  (d) Umbra textura / texture    – coeficiente de variación local (CV, ventana 9×9):
                                    edificios en pie = líneas brillantes y CV alto;
                                    escombros = dispersión difusa y CV más homogéneo
  (e) Umbra multi-aspecto / multi-aspect – SOLO si hay dos miradas (izq./der.) sobre el sitio:
                                    R = mirada 1, G = mirada 2, B = media.
                                    Colores = dispersores que cambian con la dirección (fachadas en pie).

Requiere / Requires: ./umbra_inventario/{umbra_huellas.geojson, umbra_inventario.csv, umbra_listado_completo.csv}
"""
import gc
import json
import os

import geopandas as gpd
import matplotlib
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from scipy.ndimage import uniform_filter
from shapely.geometry import Point

# ---------------------------------------------------------------------------
# Configuración / Configuration
# ---------------------------------------------------------------------------
SALIDA = "./umbra_planet_sitios"
os.makedirs(SALIDA, exist_ok=True)
CRS = "EPSG:32619"
LADO_M = 1000          # lado del recorte (m) / chip side (m)   -> bajar a 600 si falta RAM
RES_M = 0.5            # resolución común / common resolution (m)
HORA_LOCAL = "America/Caracas"
UMBRA_DIR = "./umbra_inventario"
UMBRA_HTTPS = "https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/"
PLANET_BASE = "https://data.source.coop/planet/disasterdata/venezuela-earthquake-2026-06-24"
PLANET_PRE = f"{PLANET_BASE}/pre-event/quarterly-mosaic/quarterly-mosaic-2026Q1.tif"
PLANET_POST_PARQUET = f"{PLANET_BASE}/post-event/items.parquet"

# Sitios de daño (coordenadas aproximadas del centro urbano; ajustar a edificios concretos)
# Damage sites (approximate town-centre coordinates; refine to specific buildings)
SITIOS = {
    "Catia_La_Mar":          (10.6055, -67.0324),
    "Playa_Grande_Urimare":  (10.6100, -67.0103),
    "La_Guaira":             (10.6000, -66.9331),
    "Caraballeda":           (10.6122, -66.8519),
    "Tanaguarena":           (10.6150, -66.8200),
    "Naiguata":              (10.6200, -66.7400),
}
EPICENTRO_MW75 = (10.622, -67.194)   # USGS, 17 km W de Catia La Mar
SITIOS_A_PROCESAR = None             # None = todos; o p. ej. ["Catia_La_Mar"] para ir por partes

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.tiff")
matplotlib.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})


# ---------------------------------------------------------------------------
# Utilidades / Utilities
# ---------------------------------------------------------------------------
def leer(url, cx, cy, bandas, lado=LADO_M, res=RES_M):
    n = int(lado / res)
    tr = from_origin(cx - lado / 2, cy + lado / 2, res, res)
    with rasterio.open(url) as src, WarpedVRT(src, crs=CRS, transform=tr, width=n, height=n,
                                              resampling=Resampling.bilinear) as vrt:
        b = [i for i in bandas if i <= vrt.count]
        return np.ma.filled(vrt.read(b, masked=True).astype("float32"), np.nan)


def rgb(arr):
    out = np.ones(arr.shape[1:] + (3,), dtype="float32")
    for i in range(min(3, arr.shape[0])):
        b = arr[i]
        v = b[np.isfinite(b) & (b > 0)]
        if v.size:
            lo, hi = np.percentile(v, [2, 98])
            out[..., i] = np.clip((b - lo) / max(hi - lo, 1e-6), 0, 1)
    return out


def lee(amp, w=5):
    """Filtro de Lee sobre intensidad / Lee filter on intensity."""
    I = np.nan_to_num(amp, nan=0.0) ** 2
    m = uniform_filter(I, w)
    m2 = uniform_filter(I * I, w)
    var = np.maximum(m2 - m * m, 0)
    ruido = np.nanmean(var / np.maximum(m * m, 1e-12))
    k = var / np.maximum(var + m * m * ruido, 1e-12)
    out = m + k * (I - m)
    out[~np.isfinite(amp)] = np.nan
    return np.sqrt(np.maximum(out, 0))


def db(amp):
    a = amp.copy()
    a[a <= 0] = np.nan
    return 20 * np.log10(a)


def cv_local(amp, w=9):
    """Coeficiente de variación local / local coefficient of variation."""
    a = np.nan_to_num(amp, nan=0.0)
    m = uniform_filter(a, w)
    s = np.sqrt(np.maximum(uniform_filter(a * a, w) - m * m, 0))
    cv = s / np.maximum(m, 1e-6)
    cv[~np.isfinite(amp)] = np.nan
    return cv


def estirar(x, p=(2, 98)):
    v = x[np.isfinite(x)]
    if v.size == 0:
        return np.zeros_like(x)
    lo, hi = np.percentile(v, p)
    return np.clip((x - lo) / max(hi - lo, 1e-6), 0, 1)


def barra(ax, n, metros=200):
    L = metros / RES_M
    x0, y0 = n * 0.05, n * 0.93
    ax.plot([x0, x0 + L], [y0, y0], color="white", lw=4, solid_capstyle="butt")
    ax.plot([x0, x0 + L], [y0, y0], color="black", lw=1.5, solid_capstyle="butt")
    ax.text(x0 + L / 2, y0 - n * 0.03, f"{metros} m", color="white", ha="center", fontsize=7.5,
            weight="bold", path_effects=[pe.withStroke(linewidth=2, foreground="black")])


# ---------------------------------------------------------------------------
# 1. Catálogos / Catalogues
# ---------------------------------------------------------------------------
umbra = gpd.read_file(f"{UMBRA_DIR}/umbra_huellas.geojson").set_crs("EPSG:4326", allow_override=True)
inv = pd.read_csv(f"{UMBRA_DIR}/umbra_inventario.csv", parse_dates=["inicio_utc"])
lst = pd.read_csv(f"{UMBRA_DIR}/umbra_listado_completo.csv")
gec = lst[lst.key.str.contains("GEC", case=False) & lst.key.str.lower().str.endswith((".tif", ".tiff"))]
umbra = umbra[["task_id", "geometry"]].merge(
    inv[["task_id", "inicio_utc", "satelite", "incidencia_deg", "direccion_mirada"]], on="task_id")
umbra["url"] = umbra.task_id.map(lambda t: UMBRA_HTTPS + gec[gec.key.str.contains(t)].key.iloc[0]
                                 if gec.key.str.contains(t).any() else None)

pq = f"{SALIDA}/planet_post_items.parquet"
if not os.path.exists(pq):
    r = requests.get(PLANET_POST_PARQUET, timeout=120); r.raise_for_status()
    open(pq, "wb").write(r.content)
planet = gpd.read_parquet(pq).to_crs("EPSG:4326")


def href(assets):
    if isinstance(assets, str):
        assets = json.loads(assets)
    for k in ("visual", "analytic"):
        a = assets.get(k) if isinstance(assets, dict) else None
        if a:
            return a.get("href") if isinstance(a, dict) else a


def absoluta(fila, rel):
    from urllib.parse import urljoin
    if not rel:
        return None
    if str(rel).startswith("http"):
        return rel
    cand = []
    links = fila.get("links")
    if isinstance(links, str):
        links = json.loads(links)
    if links is not None:
        for l in list(links):
            if isinstance(l, dict) and l.get("rel") == "self" and str(l.get("href", "")).startswith("http"):
                cand.append(urljoin(l["href"], rel))
    arch = str(rel).replace("./", "", 1)
    for lugar in (fila.get("location_slug"), fila.get("location"), fila.get("collection")):
        if isinstance(lugar, str) and lugar:
            cand += [f"{PLANET_BASE}/post-event/{lugar}/items/{fila['id']}/{arch}",
                     f"{PLANET_BASE}/post-event/{lugar}/{fila['id']}/{arch}"]
    cand.append(f"{PLANET_BASE}/post-event/items/{fila['id']}/{arch}")
    for u in dict.fromkeys(cand):
        try:
            if requests.head(u, timeout=20, allow_redirects=True).status_code == 200:
                return u
        except requests.RequestException:
            pass
    return None


planet["url"] = [absoluta(f, href(a)) for f, a in zip(planet.to_dict("records"), planet["assets"])]
planet["fecha"] = pd.to_datetime(planet["datetime"], utc=True)
print(f"Planet: {planet.url.notna().sum()}/{len(planet)} URLs válidas / valid URLs")
if planet.url.notna().any():
    print("  ej.:", planet.url.dropna().iloc[0])

# ---------------------------------------------------------------------------
# 2. Cobertura por sitio / Coverage per site
# ---------------------------------------------------------------------------
filas = []
for nombre, (lat, lon) in SITIOS.items():
    p = Point(lon, lat)
    u = umbra[umbra.contains(p)].sort_values("inicio_utc")
    pl = planet[planet.contains(p) & planet.url.notna()].sort_values("gsd" if "gsd" in planet else "fecha")
    filas.append(dict(sitio=nombre, lat=lat, lon=lon, n_umbra=len(u),
                      miradas=",".join(sorted(set(u.direccion_mirada.dropna()))),
                      n_planet_post=len(pl), umbra_tasks=",".join(t[:8] for t in u.task_id),
                      planet_ids=",".join(str(i)[:22] for i in pl["id"])))
cob = pd.DataFrame(filas)
cob.to_csv(f"{SALIDA}/cobertura_sitios.csv", index=False)
print("\n=== Cobertura por sitio / Coverage per site ===")
print(cob[["sitio", "n_umbra", "miradas", "n_planet_post"]].to_string(index=False))
gpd.GeoDataFrame(cob, geometry=gpd.points_from_xy(cob.lon, cob.lat), crs="EPSG:4326").to_file(
    f"{SALIDA}/sitios_danio.geojson", driver="GeoJSON")

# ---------------------------------------------------------------------------
# 3. Figuras por sitio (una a la vez) / Figures per site (one at a time)
# ---------------------------------------------------------------------------
from pyproj import Transformer
tf = Transformer.from_crs(4326, 32619, always_xy=True)
hechos = []
for nombre, (lat, lon) in SITIOS.items():
    if SITIOS_A_PROCESAR and nombre not in SITIOS_A_PROCESAR:
        continue
    p = Point(lon, lat)
    u = umbra[umbra.contains(p) & umbra.url.notna()].sort_values("inicio_utc")
    pl = planet[planet.contains(p) & planet.url.notna()]
    if "gsd" in pl:
        pl = pl.sort_values("gsd")
    if u.empty:
        print(f"[–] {nombre}: sin Umbra / no Umbra coverage"); continue
    cx, cy = tf.transform(lon, lat)
    try:
        pre = rgb(leer(PLANET_PRE, cx, cy, [1, 2, 3]))
        post = rgb(leer(pl.url.iloc[0], cx, cy, [1, 2, 3])) if len(pl) else None
        a1 = leer(u.url.iloc[0], cx, cy, [1])[0]
        a1f = lee(a1)
        dos_miradas = u.direccion_mirada.nunique() > 1
        if dos_miradas:
            u2 = u[u.direccion_mirada != u.direccion_mirada.iloc[0]].iloc[0]
            a2f = lee(leer(u2.url, cx, cy, [1])[0])
    except Exception as e:
        print(f"[!] {nombre}: {e}"); continue

    paneles = [(pre, None, "(a) Planet antes / before\nQ1-2026 · ~4.8 m")]
    if post is not None:
        t = pl.fecha.iloc[0].tz_convert(HORA_LOCAL)
        paneles.append((post, None, f"(b) Planet después / after\n{t:%d %b %H:%M} local · "
                                    f"{pl['gsd'].iloc[0] if 'gsd' in pl else ''} m"))
    tu = u.inicio_utc.iloc[0].tz_convert(HORA_LOCAL)
    paneles.append((estirar(db(a1f)), "gray", f"(c) Umbra X amplitud / amplitude (dB, Lee)\n"
                                              f"{tu:%d %b %H:%M} local · mirada/look {u.direccion_mirada.iloc[0]}"))
    paneles.append((estirar(cv_local(a1f), (5, 95)), "magma", "(d) Umbra textura / texture\nCV local 9×9"))
    if dos_miradas:
        comp = np.dstack([estirar(db(a1f)), estirar(db(a2f)), estirar(db((a1f + a2f) / 2))])
        comp[~np.isfinite(a1f) | ~np.isfinite(a2f)] = 1
        paneles.append((comp, None, "(e) Umbra multi-aspecto / multi-aspect\nR = izq./left · G = der./right"))

    fig, axs = plt.subplots(1, len(paneles), figsize=(4.2 * len(paneles), 4.6))
    for ax, (img, cmap, tit) in zip(np.atleast_1d(axs), paneles):
        ax.imshow(img, cmap=cmap, interpolation="nearest")
        ax.set_title(tit, loc="left", fontsize=8.5)
        ax.set_xticks([]); ax.set_yticks([])
        barra(ax, img.shape[1])
    fig.suptitle(f"{nombre.replace('_', ' ')}  ({lat:.4f}° N, {lon:.4f}° W) · {LADO_M} m × {LADO_M} m",
                 x=0.01, ha="left", fontsize=10.5, weight="bold")
    fig.text(0.01, 0.01, "Contains Umbra open data, CC BY 4.0 · Imagery © Planet Labs PBC, CC BY-NC 4.0",
             fontsize=6.5, color="0.35")
    plt.tight_layout(rect=(0, 0.03, 1, 0.94))
    ruta = f"{SALIDA}/{nombre}.png"
    plt.savefig(ruta, dpi=200)
    plt.show()
    plt.close(fig)
    hechos.append(ruta)
    print(f"✓ {nombre} -> {ruta}")
    # liberar memoria / free memory
    del pre, post, a1, a1f, paneles
    if dos_miradas:
        del a2f, comp
    gc.collect()

print(f"\nListo / Done: {len(hechos)} sitios. Figuras en {SALIDA}/")
