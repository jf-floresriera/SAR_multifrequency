# -*- coding: utf-8 -*-
"""
FIGURA DE COMPARACIÓN DE TODOS LOS MODELOS · una sola ventana, una sola escala · comparison of ALL models in one figure
=======================================================================================================================
Filas = familia de sensor (Sentinel-1 C · NISAR L propio · NISAR L UCSD · ALOS-2 L UCSD); columnas = ASC | DESC.
Cada panel es el MOSAICO de la familia y dirección (si hay uno solo, ese producto), producido por el paso `mosaico`.
Misma ventana, misma escala de color (± LIM_MM), mismo contexto (costa, fallas, epicentros, sitios de daño). Paleta Crameri «bam».
Pensada como figura PRINCIPAL del artículo (6–8 paneles); los productos individuales, frames y QC van al SUPLEMENTO.
Salida: 04_figuras/borradores/comparacion_modelos_{es,en}.{pdf,eps,tiff,png}
Variables: LIM_MM (por defecto 400), VENTANA = (lon0, lon1, lat0, lat1).
"""
import glob
import os
import re
import sys as _sys

import matplotlib
import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import T, TXT
from estilo_figuras import CMAPS, aplicar_estilo, etiqueta_panel, exportar, sin_etiquetas
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
LIM = float(globals().get("LIM_MM") or 400)       # LIM_MM puede ser None si lo definió otro script
WIN = globals().get("VENTANA", (-68.20, -66.20, 10.20, 10.85))
DEG = 0.0008
ESC = 1000.0
FIG = f"{RAIZ}/04_figuras/borradores"
os.makedirs(FIG, exist_ok=True)
FAM = [("S1", "Sentinel-1 (C)"), ("NISAR", "NISAR (L)"), ("NISARUCSD", "NISAR (L) · UCSD"), ("ALOS2UCSD", "ALOS-2 (L) · UCSD")]
TXT.update({"c_los": {"es": "LOS (mm); + = acercamiento al satélite", "en": "LOS (mm); + = toward satellite"},
            "c_sin": {"es": "sin dato", "en": "no data"}})
n_x, n_y = int(round((WIN[1] - WIN[0]) / DEG)), int(round((WIN[3] - WIN[2]) / DEG))
TR = from_origin(WIN[0], WIN[3], DEG, DEG)


def a_ll(ruta):
    dst = np.full((n_y, n_x), np.nan, "float32")
    with rasterio.open(ruta) as s:
        reproject(rasterio.band(s, 1), dst, src_transform=s.transform, src_crs=s.crs, src_nodata=s.nodata, dst_transform=TR,
                  dst_crs="EPSG:4326", dst_nodata=np.nan, resampling=Resampling.bilinear)
    return dst * ESC


mos = {}
for f in sorted(glob.glob(f"{RAIZ}/02_procesados/mosaicos/*_MOSAICO_*_los_m.tif")):
    nom = os.path.basename(f)
    m = re.match(r"(S1|NISARUCSD|NISAR|ALOS2UCSD)_MOSAICO_(ASC|DESC)_(\d{8})_(\d{8})_los_m\.tif", nom)
    if m:
        mos[(m.group(1), m.group(2))] = (f, m.group(3), m.group(4))
if not mos:
    raise SystemExit("Sin mosaicos: ejecute el paso `mosaico` / no mosaics: run step `mosaico`")

CTX = {}
try:
    import geopandas as gpd
    g = f"{RAIZ}/01_datos_crudos/mapas_base/mapas_base.gpkg"
    for c in ("venezuela_estados", "fallas_activas_gem", "epicentros_usgs", "sitios_danio"):
        try:
            CTX[c] = gpd.read_file(g, layer=c)
        except Exception:
            CTX[c] = None
except Exception:
    pass


def _fecha(a, b, idioma):
    mes = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    f = lambda s: f"{int(s[6:8])} {(mes if idioma == 'es' else en)[int(s[4:6]) - 1]}"
    return f"{f(a)}→{f(b)}"


def _fig(idioma):
    aplicar_estilo(7)
    filas = [k for k, _ in FAM if any((k, d) in mos for d in ("ASC", "DESC"))]
    asp = (WIN[1] - WIN[0]) * np.cos(np.radians((WIN[2] + WIN[3]) / 2)) / (WIN[3] - WIN[2])
    w = 84.0; h = w / asp
    H = len(filas) * (h + 8.0) + 18.0
    fig, axs = plt.subplots(len(filas), 2, figsize=(180 / 25.4, H / 25.4), squeeze=False)
    nombres = dict(FAM)
    im = None
    k = 0
    for i, fam in enumerate(filas):
        for j, d in enumerate(("ASC", "DESC")):
            ax = axs[i, j]
            ax.set_facecolor("#e8f0f7")
            ext = [WIN[0], WIN[1], WIN[2], WIN[3]]
            if (fam, d) in mos:
                f, r0, r1 = mos[(fam, d)]
                a = a_ll(f)
                im = ax.imshow(a, extent=ext, cmap=CMAPS["divergente"], norm=TwoSlopeNorm(0, -LIM, LIM), interpolation="nearest", zorder=2)
                ax.set_title(f"{nombres[fam]} · {d} · {_fecha(r0, r1, idioma)}", fontsize=6.2, loc="left", pad=2)
            else:
                ax.set_title(f"{nombres[fam]} · {d}", fontsize=6.2, loc="left", pad=2)
                ax.text(0.5, 0.5, T("c_sin", idioma), transform=ax.transAxes, ha="center", va="center", fontsize=7, color="0.45")
            if CTX.get("venezuela_estados") is not None:
                CTX["venezuela_estados"].boundary.plot(ax=ax, color="#444444", lw=0.35, zorder=3)
            if CTX.get("fallas_activas_gem") is not None:
                CTX["fallas_activas_gem"].plot(ax=ax, color="#222222", lw=0.5, zorder=4)
            if CTX.get("sitios_danio") is not None:
                CTX["sitios_danio"].plot(ax=ax, color="#0072B2", markersize=5, edgecolor="white", linewidth=0.3, zorder=5)
            if CTX.get("epicentros_usgs") is not None:
                CTX["epicentros_usgs"].plot(ax=ax, color="#F0E442", marker="*", markersize=45, edgecolor="k", linewidth=0.5, zorder=6)
            sin_etiquetas(ax)
            ax.set_xlim(WIN[0], WIN[1]); ax.set_ylim(WIN[2], WIN[3]); ax.set_aspect(1 / np.cos(np.radians((WIN[2] + WIN[3]) / 2)))
            ax.tick_params(length=2.5, pad=1.5, labelsize=6)
            if i < len(filas) - 1:
                ax.set_xticklabels([])
            else:
                ax.set_xlabel(T("longitud", idioma), fontsize=6.5)
            if j == 1:
                ax.set_yticklabels([])
            else:
                ax.set_ylabel(T("latitud", idioma), fontsize=6.5)
            etiqueta_panel(ax, "abcdefgh"[k], dx=-0.13 if j == 0 else -0.05, dy=1.0); k += 1
    cax = fig.add_axes([0.30, 0.02, 0.40, 0.012])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal")
    cb.set_label(T("c_los", idioma), fontsize=6.5); cb.ax.tick_params(labelsize=6, length=2)
    fig.subplots_adjust(left=0.08, right=0.99, top=0.97, bottom=0.09, hspace=0.30, wspace=0.06)
    return fig


for idioma in ("es", "en"):
    f = _fig(idioma)
    print(exportar(f, f"comparacion_modelos_{idioma}", FIG, formatos=("pdf", "tiff", "png")))
    plt.close(f)
print(f"\nFigura / figure: {FIG}/comparacion_modelos_{{es,en}}.*  (escala ±{LIM:g} mm)")
