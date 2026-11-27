# -*- coding: utf-8 -*-
"""
MAPA DE COBERTURA Y GEOMETRÍA DE ADQUISICIÓN (Fig. 2a o S1) · ES/EN / Coverage and acquisition-geometry map
=========================================================================================================
Inspirado en las figuras de contexto de artículos InSAR (p. ej. hielo fijo en Cambridge Bay, Remote Sensing): fondo de relieve en gris,
huella REAL de cada producto usado (contorno de los píxeles con dato, no el rectángulo nominal), zona de estudio, recuadro de ubicación y
un panel de GEOMETRÍA por sensor/dirección con la dirección de vuelo (heading), la dirección de mirada (look) y el ángulo de incidencia
medio, calculados de los vectores de mirada de cada producto.
  (a) Ubicación (Sudamérica/Caribe) · (b) Huellas sobre relieve · (c) Geometría por sensor y dirección
Lee: 02_procesados/{sentinel1,nisar,ucsd}/*_los_m.tif (+ _losE/_losN/_losU), 01_datos_crudos/sentinel1_hyp3/*/*_dem.tif (relieve),
     inventario_2026/umbra_inventario/umbra_huellas.geojson (Umbra), 01_datos_crudos/mapas_base/mapas_base.gpkg (países, fallas, epicentros)
Salida: 04_figuras/borradores/fig_cobertura_{es,en}.{pdf,tiff,png}
"""
import glob
import os
import re
import sys as _sys

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import shapes
from rasterio.transform import from_origin
from rasterio.warp import reproject

_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import T, TXT
from estilo_figuras import aplicar_estilo, etiqueta_panel, exportar, contexto_mapa, OKABE_ITO
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from shapely.geometry import shape
from shapely.ops import unary_union

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
TRAB = globals().get("TRABAJO", os.path.join(os.path.dirname(RAIZ), "inventario_2026"))
FIG = f"{RAIZ}/04_figuras/borradores"
os.makedirs(FIG, exist_ok=True)
WIN = globals().get("VENTANA_COBERTURA", None)          # None = se ajusta a todas las huellas (+ margen)
ZONA = (-67.32, -66.62, 10.46, 10.70)                       # costa de La Guaira (zona de estudio)
TXT.update({
    "cv_rel": {"es": "Relieve (DEM GLO-30, sombreado)", "en": "Relief (GLO-30 DEM, hillshade)"},
    "cv_zona": {"es": "Zona de estudio (La Guaira)", "en": "Study area (La Guaira)"},
    "cv_vuelo": {"es": "vuelo", "en": "flight"}, "cv_mira": {"es": "mirada", "en": "look"},
    "cv_inc": {"es": "incidencia", "en": "incidence"},
    "cv_umbra": {"es": "Umbra (X) · spotlight", "en": "Umbra (X) · spotlight"},
})
# familia → (etiqueta, color, estilo)
FAM = {"S1": ("Sentinel-1 (C)", OKABE_ITO[6], "-"), "NISAR": ("NISAR (L)", OKABE_ITO[3], "-"),
       "ALOS2": ("ALOS-2 (L) · UCSD", OKABE_ITO[1], "--")}


def huella(ruta, dec=12):
    """Polígono de los píxeles con dato (lectura submuestreada) en lon/lat / footprint of valid pixels."""
    with rasterio.open(ruta) as s:
        h, w = max(s.height // dec, 1), max(s.width // dec, 1)
        a = s.read(1, out_shape=(h, w), resampling=Resampling.nearest)
        tr = s.transform * s.transform.scale(s.width / w, s.height / h)
        m = np.isfinite(a) & (a != 0) if np.issubdtype(a.dtype, np.floating) else (a != (s.nodata or 0))
        polys = [shape(g) for g, v in shapes(m.astype("uint8"), mask=m, transform=tr) if v == 1]
        if not polys:
            return None
        g = gpd.GeoSeries([unary_union(polys).buffer(0)], crs=s.crs).to_crs(4326)
    return g.iloc[0].convex_hull          # huella de la escena (incluye mar sin dato) / scene footprint


def geometria(pref):
    """Heading, dirección de mirada (acimut, grados desde el N) e incidencia media a partir de los vectores suelo→satélite."""
    try:
        v = {}
        for k in "ENU":
            with rasterio.open(f"{pref}_los{k}.tif") as s:
                a = s.read(1, out_shape=(64, 64)).astype(float)
            v[k] = np.nanmean(np.where(np.isfinite(a) & (a != 0), a, np.nan))
        mira = (np.degrees(np.arctan2(-v["E"], -v["N"])) + 360) % 360          # desde el satélite hacia el suelo
        inc = float(np.degrees(np.arccos(np.clip(v["U"], -1, 1))))
        izquierda = "NISAR" in pref                                              # NISAR mira a la izquierda; S-1 y ALOS-2 a la derecha
        vuelo = (mira + (90 if izquierda else -90)) % 360
        return vuelo, mira, inc
    except Exception:
        return None


# ---------------------------------------------------------------- inventario de huellas
items = []
for fam, carpeta, patron in (("S1", "sentinel1", "S1_*_los_m.tif"), ("NISAR", "nisar", "NISAR_T*_los_m.tif"), ("ALOS2", "ucsd", "UCSD_ALOS2_*_los_m.tif")):
    for f in sorted(glob.glob(f"{RAIZ}/02_procesados/{carpeta}/{patron}")):
        pref = f[:-len("_los_m.tif")]
        nom = os.path.basename(pref)
        g = huella(f)
        if g is None:
            continue
        geo = geometria(pref)
        tr_ = re.search(r"_T(\d{3}[AD])", nom)
        direc = ("ASC" if tr_.group(1).endswith("A") else "DESC") if tr_ else (("ASC" if geo and geo[1] < 180 else "DESC") if geo else "?")   # S-1 (mira a la derecha): ASC mira al este
        fr_ = re.search(r"_F(\d{3})_", nom)
        etq = (tr_.group(1) if tr_ else direc) + (" F" + fr_.group(1) if fr_ else "")
        items.append(dict(fam=fam, nombre=nom, geom=g, direc=direc, etq=etq, geo=geo))
print(f"{len(items)} huellas / footprints:", [i["etq"] for i in items])
if WIN is None:
    if items:
        b_ = unary_union([i["geom"] for i in items]).bounds
        WIN = (max(b_[0] - 0.15, -72.5), min(b_[2] + 0.15, -63.0), max(b_[1] - 0.15, 7.5), min(b_[3] + 0.15, 12.8))
    else:
        WIN = (-69.5, -65.5, 9.5, 11.5)
UMBRA = None
for r in (f"{TRAB}/umbra_inventario/umbra_huellas.geojson", "./umbra_inventario/umbra_huellas.geojson"):
    if os.path.exists(r):
        try:
            UMBRA = gpd.read_file(r).to_crs(4326); break
        except Exception:
            pass

# ---------------------------------------------------------------- relieve (sombreado del DEM de HyP3)
DEG = 0.003
nx, ny = int((WIN[1] - WIN[0]) / DEG), int((WIN[3] - WIN[2]) / DEG)
TRW = from_origin(WIN[0], WIN[3], DEG, DEG)
dem = np.full((ny, nx), np.nan, "float32")
for f in sorted(glob.glob(f"{RAIZ}/01_datos_crudos/sentinel1_hyp3/*/*_dem.tif")):
    tmp = np.full((ny, nx), np.nan, "float32")
    with rasterio.open(f) as s:
        reproject(rasterio.band(s, 1), tmp, src_transform=s.transform, src_crs=s.crs, src_nodata=s.nodata,
                  dst_transform=TRW, dst_crs="EPSG:4326", dst_nodata=np.nan, resampling=Resampling.average)
    dem = np.where(np.isfinite(dem), dem, tmp)
SOMBRA = None
if np.isfinite(dem).any():
    from matplotlib.colors import LightSource
    d = np.where(np.isfinite(dem) & (dem > 0), dem, 0.0)
    SOMBRA = LightSource(azdeg=315, altdeg=40).hillshade(d, vert_exag=0.02, dx=DEG * 111e3, dy=DEG * 111e3)
    SOMBRA = np.where(d > 0, SOMBRA, np.nan)

CTX = {}
g_ = f"{RAIZ}/01_datos_crudos/mapas_base/mapas_base.gpkg"
for c in ("venezuela_estados", "fallas_activas_gem", "epicentros_usgs", "sitios_danio", "paises_sudamerica_ne50"):
    try:
        CTX[c] = gpd.read_file(g_, layer=c)
    except Exception:
        CTX[c] = None


def _flecha(ax, x, y, az, largo, **kw):
    dx, dy = largo * np.sin(np.radians(az)), largo * np.cos(np.radians(az))
    ax.annotate("", xy=(x + dx, y + dy), xytext=(x, y), arrowprops=dict(arrowstyle="-|>", mutation_scale=7, **kw))


def _fig(idioma):
    aplicar_estilo(7)
    asp = (WIN[1] - WIN[0]) * np.cos(np.radians((WIN[2] + WIN[3]) / 2)) / (WIN[3] - WIN[2])
    h_map = 168.0 / asp                                     # mm: mapa a todo el ancho (figura de suplemento)
    H = h_map + 72.0
    fig = plt.figure(figsize=(180 / 25.4, H / 25.4))
    b = fig.add_axes([9 / 180, 62 / H, 168 / 180, h_map / H])
    c = fig.add_axes([4 / 180, 2 / H, 172 / 180, 36 / H])
    a = b.inset_axes([0.005, 0.62, 0.21, 0.37])            # ubicación incrustada en la esquina / embedded locator

    # (a) ubicación
    a.set_facecolor("#dfe9f2")
    if CTX.get("paises_sudamerica_ne50") is not None:
        CTX["paises_sudamerica_ne50"].plot(ax=a, facecolor="#efefec", edgecolor="#8a8a8a", lw=0.3)
        p = CTX["paises_sudamerica_ne50"]; p[p.ADMIN == "Venezuela"].plot(ax=a, facecolor="#f6dcc0", edgecolor="#8a3a00", lw=0.5)
    a.add_patch(Rectangle((WIN[0], WIN[2]), WIN[1] - WIN[0], WIN[3] - WIN[2], fill=False, ec="k", lw=0.8))
    a.set_xlim(-80, -56); a.set_ylim(-2, 15); a.set_aspect(1 / np.cos(np.radians(7)))
    a.set_xticks([]); a.set_yticks([]); a.set_xlabel(""); a.set_ylabel("")
    a.text(0.03, 0.97, "(a)", transform=a.transAxes, fontsize=8, fontweight="bold", va="top")

    # (b) huellas sobre relieve
    b.set_facecolor("#dfe9f2")
    if SOMBRA is not None:
        b.imshow(SOMBRA, extent=[WIN[0], WIN[1], WIN[2], WIN[3]], cmap="gray", vmin=0, vmax=1, alpha=0.9, zorder=1, interpolation="bilinear")
    elif CTX.get("venezuela_estados") is not None:
        CTX["venezuela_estados"].plot(ax=b, facecolor="#efefec", edgecolor="none", zorder=1)
    contexto_mapa(b, CTX, sitios=False)
    vistos = set()
    for it in items:
        lab, col, ls = FAM[it["fam"]]
        geoms = getattr(it["geom"], "geoms", [it["geom"]])
        for gg in geoms:
            x, y = gg.exterior.xy
            b.plot(x, y, color=col, lw=1.2 if it["direc"] == "ASC" else 1.2, ls=ls if it["direc"] == "ASC" else ":", zorder=5)
        cx, cy = it["geom"].representative_point().coords[0]
        if WIN[0] < cx < WIN[1] and WIN[2] < cy < WIN[3]:
            b.text(cx, cy, it["etq"], fontsize=5.2, color=col, ha="center", va="center", zorder=7,
                   bbox=dict(fc="white", ec="none", pad=0.3, alpha=0.85))
    if UMBRA is not None:
        UMBRA.plot(ax=b, facecolor="#56B4E9", edgecolor="#0072B2", lw=0.4, alpha=0.7, zorder=6)
    b.add_patch(Rectangle((ZONA[0], ZONA[2]), ZONA[1] - ZONA[0], ZONA[3] - ZONA[2], fill=False, ec="#F0E442", lw=1.6, zorder=8))
    b.add_patch(Rectangle((ZONA[0], ZONA[2]), ZONA[1] - ZONA[0], ZONA[3] - ZONA[2], fill=False, ec="k", lw=0.4, zorder=8))
    b.set_xlim(WIN[0], WIN[1]); b.set_ylim(WIN[2], WIN[3]); b.set_aspect(1 / np.cos(np.radians(10.5)))
    b.set_xlabel(T("longitud", idioma)); b.set_ylabel(T("latitud", idioma)); b.tick_params(labelsize=6, length=2.5)
    h = [Line2D([], [], color=FAM[k][1], lw=1.2, ls=FAM[k][2], label=FAM[k][0]) for k in FAM if any(i["fam"] == k for i in items)]
    h += [Line2D([], [], color="0.3", lw=1.2, ls="-", label="ASC"), Line2D([], [], color="0.3", lw=1.2, ls=":", label="DESC")]
    if UMBRA is not None:
        h.append(plt.Rectangle((0, 0), 1, 1, fc="#56B4E9", ec="#0072B2", label=T("cv_umbra", idioma)))
    h += [plt.Rectangle((0, 0), 1, 1, fc="none", ec="#F0E442", lw=1.6, label=T("cv_zona", idioma)),
          Line2D([], [], color="#B2182B", lw=0.8, ls="--", label=T("u_fallas", idioma) if "u_fallas" in TXT else "Faults (GEM)")]
    b.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=4, fontsize=6.2, frameon=False)
    etiqueta_panel(b, "b", dx=-0.02, dy=1.01)

    # (c) geometría por sensor y dirección: una «rosa» por familia y dirección
    c.set_xlim(0, 12); c.set_ylim(0, 3.0); c.set_aspect("equal"); c.axis("off")
    grupos = {}
    for it in items:
        if it["geo"]:
            grupos.setdefault((it["fam"], it["direc"]), it["geo"])
    for k, ((fam, direc), (vuelo, mira, inc)) in enumerate(sorted(grupos.items())):
        x0, y0 = 1.0 + k * 2.0, 1.75
        col = FAM[fam][1]
        c.add_patch(plt.Circle((x0, y0), 0.75, fc="none", ec="0.8", lw=0.5))
        c.text(x0, y0 + 0.82, "N", fontsize=5, ha="center", color="0.5")
        _flecha(c, x0, y0, vuelo, 0.7, color=col, lw=1.4)
        _flecha(c, x0, y0, mira, 0.5, color="0.25", lw=0.8, ls="--")
        texto = FAM[fam][0].split(" ·")[0] + "\n" + direc + " · " + T("cv_inc", idioma) + f" {inc:.0f}°"
        c.text(x0, y0 - 0.9, texto, fontsize=5.6, va="top", ha="center")
    c.text(11.9, 2.8, "— " + T("cv_vuelo", idioma) + "    - - " + T("cv_mira", idioma), fontsize=5.8, color="0.25", ha="right")
    etiqueta_panel(c, "c", dx=0.0, dy=1.0)
    return fig


TXT.setdefault("u_fallas", {"es": "Fallas activas (GEM)", "en": "Active faults (GEM)"})
for idioma in ("es", "en"):
    f = _fig(idioma)
    print(exportar(f, f"fig_cobertura_{idioma}", FIG, formatos=("pdf", "tiff", "png")))
    plt.close(f)
