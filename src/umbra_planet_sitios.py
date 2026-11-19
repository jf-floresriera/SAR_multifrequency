# -*- coding: utf-8 -*-
"""
Umbra (banda X) × Planet (óptico) en los SITIOS DE DAÑO · v2
Umbra (X-band) × Planet (optical) at DAMAGE SITES · v2

🇪🇸 Novedades v2
  · Elige la escena Umbra que MÁS cubre el sitio y rellena huecos con las demás de la misma mirada (mosaico).
  · Si la cobertura sigue < 90 %, desplaza el recorte hacia donde hay radar (y lo indica en la figura).
  · Reemplaza la composición multi-aspecto por el ÍNDICE NORMALIZADO DE DIFERENCIA DE MIRADAS (NDLI):
        NDLI = (I_izq − I_der) / (I_izq + I_der), cada mirada normalizada por su mediana.
  · Segunda fila con ACERCAMIENTO (300 m) en el centro del recorte.
  · Sitios sin Umbra: figura Planet antes/después + coherencia NISAR cosísmica si ya existe (notebook 03).
  · Bajo consumo de memoria: un sitio a la vez, se libera todo antes del siguiente.
🇬🇧 What's new in v2
  · Picks the Umbra scene with the LARGEST coverage of the site and fills gaps with the other scenes of the same look.
  · If coverage is still < 90 %, shifts the chip towards radar coverage (reported in the figure).
  · Replaces the multi-aspect RGB by the NORMALISED DIFFERENCE LOOK INDEX (NDLI), each look median-normalised.
  · Second row with a 300 m ZOOM at the chip centre.
  · Sites without Umbra: Planet before/after + NISAR coseismic coherence if already produced (notebook 03).
  · Low memory: one site at a time.

Variables que se pueden fijar ANTES de ejecutar (con %run -i) / Variables you can set BEFORE running (with %run -i):
  LADO_M (1000), RES_M (0.5), ZOOM_M (300), SITIOS_A_PROCESAR (None = todos / all)
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import T, csv_bilingue, guardar_bilingue
import gc
import glob
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
from matplotlib.patches import Rectangle
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from scipy.ndimage import uniform_filter
from shapely.geometry import Point, box
from shapely.ops import unary_union

# ---------------------------------------------------------------------------
# Configuración / Configuration
# ---------------------------------------------------------------------------
_g = globals()
LADO_M = _g.get("LADO_M", 1000)
RES_M = _g.get("RES_M", 0.5)
ZOOM_M = _g.get("ZOOM_M", 300)
SITIOS_A_PROCESAR = _g.get("SITIOS_A_PROCESAR", None)
# Centros de acercamiento manuales (lat, lon) sobre edificios colapsados conocidos; si no, automático
# Manual zoom centres (lat, lon) on known collapsed buildings; otherwise automatic
ZOOM_CENTROS = _g.get("ZOOM_CENTROS", {})
COBERTURA_MIN = 0.90
SALIDA = "./umbra_planet_sitios"
os.makedirs(SALIDA, exist_ok=True)
CRS = "EPSG:32619"
HORA_LOCAL = "America/Caracas"
UMBRA_DIR = "./umbra_inventario"
UMBRA_HTTPS = "https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/"
PLANET_BASE = "https://data.source.coop/planet/disasterdata/venezuela-earthquake-2026-06-24"
PLANET_PRE = f"{PLANET_BASE}/pre-event/quarterly-mosaic/quarterly-mosaic-2026Q1.tif"
PLANET_POST_PARQUET = f"{PLANET_BASE}/post-event/items.parquet"
NISAR_DIR = "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR/02_procesados/nisar"

SITIOS = {   # aprox. centro urbano / approx. town centre (refinar a edificios / refine to buildings)
    "Catia_La_Mar": (10.6055, -67.0324),
    "Playa_Grande_Urimare": (10.6100, -67.0103),
    "La_Guaira": (10.6000, -66.9331),
    "Caraballeda": (10.6122, -66.8519),
    "Tanaguarena": (10.6150, -66.8200),
    "Naiguata": (10.6200, -66.7400),
}

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.tiff")
matplotlib.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
A_UTM = Transformer.from_crs(4326, 32619, always_xy=True)


# ---------------------------------------------------------------------------
# Utilidades de imagen / Image utilities
# ---------------------------------------------------------------------------
def leer(url, cx, cy, bandas, lado, res=RES_M):
    n = int(lado / res)
    tr = from_origin(cx - lado / 2, cy + lado / 2, res, res)
    with rasterio.open(url) as src, WarpedVRT(src, crs=CRS, transform=tr, width=n, height=n,
                                              resampling=Resampling.bilinear) as vrt:
        b = [i for i in bandas if i <= vrt.count]
        a = np.ma.filled(vrt.read(b, masked=True).astype("float32"), np.nan)
    a[a == 0] = np.nan
    return a


def rgb(arr):
    out = np.ones(arr.shape[1:] + (3,), dtype="float32")
    for i in range(min(3, arr.shape[0])):
        b = arr[i]
        v = b[np.isfinite(b) & (b > 0)]
        if v.size:
            lo, hi = np.percentile(v, [2, 98])
            out[..., i] = np.where(np.isfinite(b), np.clip((b - lo) / max(hi - lo, 1e-6), 0, 1), 1)
    return out


def lee(amp, w=5):
    I = np.nan_to_num(amp, nan=0.0) ** 2
    m = uniform_filter(I, w); m2 = uniform_filter(I * I, w)
    var = np.maximum(m2 - m * m, 0)
    validos = np.isfinite(amp) & (m > 0)
    ruido = np.nanmedian((var / np.maximum(m * m, 1e-12))[validos]) if validos.any() else 1.0
    k = var / np.maximum(var + m * m * ruido, 1e-12)
    out = np.sqrt(np.maximum(m + k * (I - m), 0))
    out[~np.isfinite(amp)] = np.nan
    return out


def db(a):
    a = a.copy(); a[a <= 0] = np.nan
    return 20 * np.log10(a)


def cv_local(a, w=9):
    x = np.nan_to_num(a, nan=0.0)
    m = uniform_filter(x, w)
    s = np.sqrt(np.maximum(uniform_filter(x * x, w) - m * m, 0))
    cv = s / np.maximum(m, 1e-6); cv[~np.isfinite(a)] = np.nan
    return cv


def ndli(a_izq, a_der):
    """Índice normalizado de diferencia de miradas / normalised difference look index."""
    i1 = a_izq ** 2 / np.nanmedian(a_izq ** 2)
    i2 = a_der ** 2 / np.nanmedian(a_der ** 2)
    return (i1 - i2) / (i1 + i2)


def estirar(x, p=(2, 98)):
    v = x[np.isfinite(x)]
    if v.size == 0:
        return np.full_like(x, np.nan)
    lo, hi = np.percentile(v, p)
    return np.clip((x - lo) / max(hi - lo, 1e-6), 0, 1)


def barra(ax, n, res, metros):
    L = metros / res
    x0, y0 = n * 0.05, n * 0.92
    ax.add_patch(Rectangle((x0 - n * 0.02, y0 - n * 0.075), L + n * 0.04, n * 0.11, fc="white", ec="none",
                           alpha=0.85, zorder=4))
    ax.plot([x0, x0 + L], [y0, y0], color="black", lw=2, solid_capstyle="butt", zorder=5)
    ax.text(x0 + L / 2, y0 - n * 0.015, f"{metros} m", color="black", ha="center", va="bottom",
            fontsize=7, zorder=5)


def recorte(a, frac, centro=None):
    """Recorte de lado frac·n alrededor de `centro` (fila, col) / crop of side frac·n around `centro`."""
    n = a.shape[0]; k = int(n * frac / 2)
    r, c = centro if centro else (n // 2, n // 2)
    r = int(min(max(r, k), n - k)); c = int(min(max(c, k), n - k))
    return a[r - k:r + k, c - k:c + k]


def centro_zoom(pre, post, frac, paso=10):
    """Centro del acercamiento donde más aclara la imagen después del sismo (polvo/escombros),
    excluyendo mar y sombras. Center of the zoom where the after image brightens most (dust/debris)."""
    n = pre.shape[0]
    if post is None:
        return n // 2, n // 2
    a = np.nanmean(pre, axis=-1)[::paso, ::paso]
    b = np.nanmean(post, axis=-1)[::paso, ::paso]
    d = np.nan_to_num(b - a)
    d[(a < 0.18) | (b >= 0.999)] = 0           # mar/sombra y zonas sin dato / sea-shadow and no-data
    w = max(int(n * frac / paso), 3)
    sc = uniform_filter(np.clip(d, 0, None), w)
    m = w // 2 + 1
    sc[:m] = 0; sc[-m:] = 0; sc[:, :m] = 0; sc[:, -m:] = 0
    if sc.max() <= 0:
        return n // 2, n // 2
    rr, cc = np.nonzero(sc >= 0.95 * sc.max())      # centro de la meseta de máximos / plateau centre
    return int(rr.mean() * paso), int(cc.mean() * paso)


# ---------------------------------------------------------------------------
# Geometría: mejor cobertura y desplazamiento / Geometry: best coverage and shift
# ---------------------------------------------------------------------------
def centro_optimo(cx, cy, huellas_utm, lado, cobertura_min=COBERTURA_MIN):
    """Devuelve (cx, cy, cobertura, desplazamiento_m). Mueve el recorte hacia la zona con radar
    dentro de un radio de 1.5×lado si la cobertura es insuficiente."""
    union = unary_union(list(huellas_utm))
    chip = box(cx - lado / 2, cy - lado / 2, cx + lado / 2, cy + lado / 2)
    cob = union.intersection(chip).area / chip.area
    if cob >= cobertura_min:
        return cx, cy, cob, 0.0
    zona = union.intersection(Point(cx, cy).buffer(1.5 * lado))
    if zona.is_empty:
        return cx, cy, cob, 0.0
    nx, ny = zona.centroid.x, zona.centroid.y
    # acercar al sitio original lo más posible manteniendo cobertura / stay as close as possible
    mejor = (cx, cy, cob)
    for f in np.linspace(0, 1, 21):
        tx, ty = cx + f * (nx - cx), cy + f * (ny - cy)
        c = union.intersection(box(tx - lado / 2, ty - lado / 2, tx + lado / 2, ty + lado / 2)).area / chip.area
        if c > mejor[2] + 1e-6:
            mejor = (tx, ty, c)
        if c >= cobertura_min:
            break
    tx, ty, c = mejor
    return tx, ty, c, float(np.hypot(tx - cx, ty - cy))


def mosaico_mirada(escenas, cx, cy, lado):
    """Lee las escenas de UNA mirada ordenadas por cobertura y rellena huecos / fill gaps."""
    a, usadas = None, []
    for _, e in escenas.iterrows():
        x = leer(e.url, cx, cy, [1], lado)[0]
        if a is None:
            a = x
        else:
            hueco = ~np.isfinite(a) & np.isfinite(x)
            if not hueco.any():
                continue
            a[hueco] = x[hueco]
        usadas.append(e)
        if np.isfinite(a).mean() > 0.995:
            break
    return a, pd.DataFrame(usadas)


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
umbra = umbra[umbra.url.notna()]
umbra_utm = umbra.to_crs(CRS)

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


cache_urls = f"{SALIDA}/planet_urls.csv"
if os.path.exists(cache_urls):
    planet = planet.merge(pd.read_csv(cache_urls), on="id", how="left")
else:
    planet["url"] = [absoluta(f, href(a)) for f, a in zip(planet.to_dict("records"), planet["assets"])]
    planet[["id", "url"]].to_csv(cache_urls, index=False)
planet["fecha"] = pd.to_datetime(planet["datetime"], utc=True)
planet = planet[planet.url.notna()]
planet_utm = planet.to_crs(CRS)
print(f"Umbra: {len(umbra)} escenas · Planet: {len(planet)} escenas con URL")

coh_nisar = sorted(glob.glob(f"{NISAR_DIR}/*T126D*_coh.tif")) or sorted(glob.glob(f"{NISAR_DIR}/*_coh.tif"))


# ---------------------------------------------------------------------------
# 2. Un sitio a la vez / One site at a time
# ---------------------------------------------------------------------------
resumen = []
for nombre, (lat, lon) in SITIOS.items():
    if SITIOS_A_PROCESAR and nombre not in SITIOS_A_PROCESAR:
        continue
    cx0, cy0 = A_UTM.transform(lon, lat)
    chip0 = box(cx0 - LADO_M / 2, cy0 - LADO_M / 2, cx0 + LADO_M / 2, cy0 + LADO_M / 2)
    vecindad = Point(cx0, cy0).buffer(2 * LADO_M)
    cand = umbra_utm[umbra_utm.intersects(vecindad)].copy()
    pl_cand = planet_utm[planet_utm.intersects(vecindad)].copy()
    tiene_umbra = len(cand) > 0
    # Zona válida = donde hay Umbra Y Planet después (para que ningún panel quede en blanco)
    # Valid zone = where both Umbra AND Planet-after exist (so no panel is left blank)
    if tiene_umbra and len(pl_cand):
        zona = unary_union(list(cand.geometry)).intersection(unary_union(list(pl_cand.geometry)))
        huellas = [zona] if not zona.is_empty else list(cand.geometry)
    elif tiene_umbra:
        huellas = list(cand.geometry)
    elif len(pl_cand):
        huellas = list(pl_cand.geometry)
    else:
        huellas = []
    if huellas:
        cx, cy, cob, desp = centro_optimo(cx0, cy0, huellas, LADO_M)
    else:
        cx, cy, cob, desp = cx0, cy0, 0.0, 0.0
    chip = box(cx - LADO_M / 2, cy - LADO_M / 2, cx + LADO_M / 2, cy + LADO_M / 2)
    cand = cand[cand.intersects(chip)].copy()
    tiene_umbra = len(cand) > 0
    pl = pl_cand[pl_cand.intersects(chip)].copy()
    pl["cob"] = pl.geometry.intersection(chip).area / chip.area
    pl = pl.sort_values(["cob", "gsd" if "gsd" in pl else "fecha"], ascending=[False, True])

    paneles = []
    pre_rgb, post_rgb = None, None
    try:
        pre_rgb = rgb(leer(PLANET_PRE, cx, cy, [1, 2, 3], LADO_M))
        paneles.append((pre_rgb, None, None,
                        lambda i: T("pl_antes", i)))
        if len(pl):
            t = pl.fecha.iloc[0].tz_convert(HORA_LOCAL)
            g_ = pl["gsd"].iloc[0]
            post = leer(pl.url.iloc[0], cx, cy, [1, 2, 3], LADO_M)
            for u_ in pl.url.iloc[1:]:                     # rellenar huecos con otras escenas / fill gaps
                hueco = ~np.isfinite(post).any(axis=0)
                if not hueco.any():
                    break
                extra = leer(u_, cx, cy, [1, 2, 3], LADO_M)
                post[:, hueco] = extra[:, hueco]
            post_rgb = rgb(post)
            paneles.append((post_rgb, None, None,
                            lambda i, t=t, g_=g_: T("pl_despues", i, t=f"{t:%d %b %H:%M}", g=f"{g_:.2f}")))
        usadas_txt = ""
        if tiene_umbra:
            cand["cob"] = cand.geometry.intersection(chip).area / chip.area
            miradas = (cand.groupby("direccion_mirada").cob.max().sort_values(ascending=False).index.tolist())
            m1 = miradas[0]
            a1, us1 = mosaico_mirada(cand[cand.direccion_mirada == m1].sort_values("cob", ascending=False),
                                     cx, cy, LADO_M)
            a1f = lee(a1)
            t1 = us1.inicio_utc.iloc[0].tz_convert(HORA_LOCAL)
            usadas_txt = f"{m1}: " + ",".join(t[:8] for t in us1.task_id)
            paneles.append((estirar(db(a1f)), "gray", None,
                            lambda i, t1=t1, m1=m1: T("um_amp", i, t=f"{t1:%d %b %H:%M}", m=T(m1, i))))
            paneles.append((estirar(cv_local(a1f), (5, 95)), "magma", None, lambda i: T("um_tex", i)))
            if len(miradas) > 1:
                m2 = miradas[1]
                a2, us2 = mosaico_mirada(cand[cand.direccion_mirada == m2].sort_values("cob", ascending=False),
                                         cx, cy, LADO_M)
                a2f = lee(a2)
                izq, der = (a1f, a2f) if m1 == "left" else (a2f, a1f)
                paneles.append((ndli(izq, der), "RdBu_r", (-0.6, 0.6), lambda i: T("um_ndli", i)))
                usadas_txt += f" · {m2}: " + ",".join(t[:8] for t in us2.task_id)
                del a2, a2f
            del a1, a1f
        elif coh_nisar:
            c = leer(coh_nisar[0], cx, cy, [1], LADO_M, res=10)[0]
            f_ = os.path.basename(coh_nisar[0])[:24]
            paneles.append((c, "gray", (0, 1), lambda i, f_=f_: T("coh_nisar", i, f=f_)))
    except Exception as e:
        print(f"[!] {nombre}: {e}")
        continue

    # Centro del acercamiento: manual (ZOOM_CENTROS) o automático / zoom centre: manual or automatic
    frac = ZOOM_M / LADO_M
    npx = paneles[0][0].shape[0]
    if nombre in ZOOM_CENTROS:
        zlat, zlon = ZOOM_CENTROS[nombre]
        zx, zy = A_UTM.transform(zlon, zlat)
        zc = (int((cy + LADO_M / 2 - zy) / LADO_M * npx), int((zx - (cx - LADO_M / 2)) / LADO_M * npx))
        modo_zoom = "manual"
    else:
        zc = centro_zoom(pre_rgb, post_rgb, frac)
        modo_zoom = "auto"
    zx_m = cx - LADO_M / 2 + zc[1] / npx * LADO_M
    zy_m = cy + LADO_M / 2 - zc[0] / npx * LADO_M
    zlon_, zlat_ = Transformer.from_crs(32619, 4326, always_xy=True).transform(zx_m, zy_m)

    # Figura estilo SRL: cuadrícula compacta, etiquetas (a)(b)… fuera arriba-izquierda, sin título
    # SRL-style figure: compact grid, (a)(b)… labels outside top-left, no title (text goes in the caption)
    def _fig(idioma):
        n = len(paneles)
        ancho = 7.2                                  # pulgadas ≈ ancho de página / page width
        lado = (ancho - 0.1) / n
        fig = plt.figure(figsize=(ancho, 2 * lado + 0.70))
        gs = fig.add_gridspec(2, n, wspace=0.04, hspace=0.10, left=0.005, right=0.995,
                              top=1 - 0.18 / (2 * lado + 0.70), bottom=0.60 / (2 * lado + 0.70))
        letras = "abcdefghijklmnop"
        for j, (img, cmap, lim, tit) in enumerate(paneles):
            res_img = LADO_M / img.shape[1]
            kw = dict(cmap=cmap, interpolation="nearest")
            if lim:
                kw.update(vmin=lim[0], vmax=lim[1])
            for fila in (0, 1):
                ax = fig.add_subplot(gs[fila, j])
                dato = img if fila == 0 else recorte(img, frac, zc)
                im = ax.imshow(dato, **kw)
                ax.set_xticks([]); ax.set_yticks([])
                for sp in ax.spines.values():
                    sp.set_linewidth(0.5)
                ax.text(0.0, 1.015, f"({letras[fila * n + j]})", transform=ax.transAxes,
                        ha="left", va="bottom", fontsize=8, weight="bold")
                if fila == 0:
                    k = img.shape[0] * frac / 2
                    r0, c0 = min(max(zc[0], k), img.shape[0] - k), min(max(zc[1], k), img.shape[1] - k)
                    ax.add_patch(Rectangle((c0 - k, r0 - k), 2 * k, 2 * k, fill=False, ec="#FFD400", lw=1.0))
                    barra(ax, img.shape[1], res_img, 200)
                else:
                    barra(ax, dato.shape[1], res_img, 50)
                if fila == 1 and (cmap == "RdBu_r" or (lim and cmap == "gray")):
                    cax = ax.inset_axes([0.05, -0.10, 0.9, 0.045])
                    cb = fig.colorbar(im, cax=cax, orientation="horizontal")
                    cb.ax.tick_params(labelsize=6, length=2)
        fig.text(0.005, 0.005, "Umbra: CC BY 4.0 · Planet Labs PBC: CC BY-NC 4.0", fontsize=6, color="0.35")
        return fig

    rutas = guardar_bilingue(_fig, f"{SALIDA}/{nombre}_v3", formatos=("png", "pdf"), dpi=300)

    # Pie de figura bilingüe (SRL: la descripción va en el pie, no en la figura) / bilingual caption
    letras = "abcdefghijklmnop"
    for idioma in ("es", "en"):
        n = len(paneles)
        partes = [f"({letras[j]}) {p[3](idioma).split(') ', 1)[-1]}" for j, p in enumerate(paneles)]
        if idioma == "es":
            txt = (f"{nombre.replace('_', ' ')} ({lat:.4f}° N, {abs(lon):.4f}° O). Fila superior: recorte de "
                   f"{LADO_M} m × {LADO_M} m; fila inferior ({letras[n]})–({letras[2 * n - 1]}): acercamiento de "
                   f"{ZOOM_M} m (recuadro amarillo, centrado en {zlat_:.4f}° N, {abs(zlon_):.4f}° O, selección {modo_zoom}). "
                   + "; ".join(partes) + f". Cobertura Umbra {cob:.0%}"
                   + (f"; recorte desplazado {desp:.0f} m respecto al sitio" if desp else "") + ". "
                   + (f"Escenas Umbra: {usadas_txt}. " if usadas_txt else "")
                   + "Contiene datos abiertos de Umbra (CC BY 4.0); imágenes © Planet Labs PBC (CC BY-NC 4.0).")
        else:
            txt = (f"{nombre.replace('_', ' ')} ({lat:.4f}° N, {abs(lon):.4f}° W). Top row: {LADO_M} m × {LADO_M} m "
                   f"chip; bottom row ({letras[n]})–({letras[2 * n - 1]}): {ZOOM_M} m zoom (yellow box, centred at "
                   f"{zlat_:.4f}° N, {abs(zlon_):.4f}° W, {modo_zoom} selection). " + "; ".join(partes)
                   + f". Umbra coverage {cob:.0%}" + (f"; chip shifted {desp:.0f} m from the site" if desp else "")
                   + ". " + (f"Umbra scenes: {usadas_txt}. " if usadas_txt else "")
                   + "Contains Umbra open data (CC BY 4.0); imagery © Planet Labs PBC (CC BY-NC 4.0).")
        open(f"{SALIDA}/{nombre}_v3_pie_{idioma}.txt", "w", encoding="utf-8").write(txt + "\n")

    resumen.append(dict(sitio=nombre, umbra=tiene_umbra, cobertura=round(cob, 3),
                        desplazamiento_m=round(desp), escenas_umbra=usadas_txt,
                        planet=pl["id"].iloc[0] if len(pl) else None, figura=rutas[0],
                        zoom_lat=round(zlat_, 5), zoom_lon=round(zlon_, 5), zoom_modo=modo_zoom))
    del paneles, pre_rgb, post_rgb
    gc.collect()
    print(f"✓ {nombre}: cobertura {cob:.0%}" + (f", desplazado {desp:.0f} m" if desp else "")
          + f" · zoom {modo_zoom} ({zlat_:.4f}, {zlon_:.4f})")
    for r_ in rutas:
        print("    ", r_)

csv_bilingue(pd.DataFrame(resumen), f"{SALIDA}/resumen_sitios_v3.csv")
print(f"\nListo / Done → {SALIDA}/resumen_sitios_v3.csv · figuras _es/_en (.png, .pdf) y pies de figura _pie_es/_pie_en.txt")
