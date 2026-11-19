# -*- coding: utf-8 -*-
"""Descomposición Este/Vertical (C y L), validación GNSS y figura borrador / East/Up decomposition (C and L), GNSS check and draft figure.
Fijar CCS1_LON, CCS1_LAT antes de %run -i para validar con GNSS."""
import os
RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
import glob
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.transform import from_origin
# =============================================================================
# BLOQUE B · Descomposición Este/Vertical (asc + desc) en una grilla común
#            Se aplica IGUAL a Sentinel-1, NISAR y ALOS-2
# =============================================================================
GRILLA_EPSG = 32619
RES = 80.0                                   # m (resolución común de comparación)
XMIN, XMAX, YMIN, YMAX = 640000, 790000, 1140000, 1200000   # UTM 19N: Yumare..Guatire
COH_MIN = 0.3


def a_grilla(ruta, metodo=Resampling.bilinear):
    n_x, n_y = int((XMAX - XMIN) / RES), int((YMAX - YMIN) / RES)
    dst = np.full((n_y, n_x), np.nan, dtype="float32")
    tr = from_origin(XMIN, YMAX, RES, RES)
    with rasterio.open(ruta) as s:
        reproject(rasterio.band(s, 1), dst, src_transform=s.transform, src_crs=s.crs,
                  src_nodata=s.nodata, dst_transform=tr, dst_crs=f"EPSG:{GRILLA_EPSG}",
                  dst_nodata=np.nan, resampling=metodo)
    return dst, tr


def descomponer(pares, nombre_banda, salida):
    """pares: lista de prefijos (asc y desc) con archivos *_los_m, *_coh, *_losE/N/U.
    Resuelve por mínimos cuadrados d_LOS = E·e + U·u (N≈0; GNSS CCS1 da dN≈-1 cm)."""
    os.makedirs(salida, exist_ok=True)
    G, d = [], []
    for pref in pares:
        los, tr = a_grilla(f"{pref}_los_m.tif")
        coh, _ = a_grilla(f"{pref}_coh.tif")
        e, _ = a_grilla(f"{pref}_losE.tif"); u, _ = a_grilla(f"{pref}_losU.tif")
        los[coh < COH_MIN] = np.nan
        G.append(np.stack([e, u], -1)); d.append(los)
    G = np.stack(G, -2)                       # (y, x, n_obs, 2)
    d = np.stack(d, -1)                       # (y, x, n_obs)
    ok = np.all(np.isfinite(d), -1) & np.all(np.isfinite(G), (-1, -2))
    E = np.full(ok.shape, np.nan, "float32"); U = E.copy()
    Gv, dv = G[ok], d[ok][..., None]
    sol = np.linalg.pinv(Gv) @ dv             # (n, 2, 1)
    E[ok], U[ok] = sol[:, 0, 0], sol[:, 1, 0]
    perfil = dict(driver="GTiff", height=E.shape[0], width=E.shape[1], count=1, dtype="float32",
                  crs=f"EPSG:{GRILLA_EPSG}", transform=tr, nodata=np.nan, compress="deflate")
    for k, v in (("E", E), ("U", U)):
        with rasterio.open(f"{salida}/{nombre_banda}_{k}_m.tif", "w", **perfil) as dst:
            dst.write(v, 1)
    print(f"{nombre_banda}: {ok.sum()} píxeles resueltos | E p2-p98 = "
          f"{np.nanpercentile(E, 2):.2f}..{np.nanpercentile(E, 98):.2f} m")
    return E, U, tr


def valor_en(arr, tr, x, y, ventana=2):
    c, f = int((x - tr.c) / tr.a), int((y - tr.f) / tr.e)
    return np.nanmedian(arr[f - ventana:f + ventana + 1, c - ventana:c + ventana + 1])


import glob
# --- NISAR: 2 ascendentes (061A, 162A) + 1 descendente (126D)
pref_n = sorted({p.rsplit("_los_m.tif", 1)[0] for p in glob.glob(f"{RAIZ}/02_procesados/nisar/*_los_m.tif")
                 if any(t in p for t in ("T061A", "T162A", "T126D"))})
print("NISAR:", [os.path.basename(p) for p in pref_n])
E_L, U_L, tr = descomponer(pref_n, "NISAR_L", f"{RAIZ}/02_procesados/descomposicion")

# --- Sentinel-1: 033A + 025D
pref_c = sorted({p.rsplit("_los_m.tif", 1)[0] for p in glob.glob(f"{RAIZ}/02_procesados/sentinel1/*_los_m.tif")})
print("Sentinel-1:", [os.path.basename(p) for p in pref_c])
E_C, U_C, _ = descomponer(pref_c, "S1_C", f"{RAIZ}/02_procesados/descomposicion")

# --- Validación con GNSS CCS1 (dE = -0.464 m, dN = -0.011 m, dU = +0.021 m; Arenas & Suárez 2026)
# Coloque las coordenadas exactas de CCS1 (de la ficha de estación NGL o IGVSB):
CCS1_LON, CCS1_LAT = globals().get("CCS1_LON"), globals().get("CCS1_LAT")
if CCS1_LON is not None:
    from pyproj import Transformer
    x, y = Transformer.from_crs(4326, GRILLA_EPSG, always_xy=True).transform(CCS1_LON, CCS1_LAT)
    for nombre, E, U in (("NISAR L", E_L, U_L), ("Sentinel-1 C", E_C, U_C)):
        print(f"{nombre}: E = {valor_en(E, tr, x, y):+.3f} m (GNSS -0.464) | U = {valor_en(U, tr, x, y):+.3f} m (GNSS +0.021)")
    print("Si E sale POSITIVO (~+0.46), cambie SIGNO / SIGNO_S1 a +1 y vuelva a correr las celdas 4 y 5.")


import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
ext = [XMIN/1e3, XMAX/1e3, YMIN/1e3, YMAX/1e3]
fig, axs = plt.subplots(2, 3, figsize=(16, 6.5), constrained_layout=True)
paneles = [(E_C, "Sentinel-1 (C) · Este"), (E_L, "NISAR (L) · Este"), (E_L - E_C, "L − C · Este"),
           (U_C, "Sentinel-1 (C) · Vertical"), (U_L, "NISAR (L) · Vertical"), (U_L - U_C, "L − C · Vertical")]
for ax, (a, t) in zip(axs.flat, paneles):
    lim = np.nanpercentile(np.abs(a), 98) if np.isfinite(a).any() else 1
    im = ax.imshow(a, extent=ext, cmap="RdBu_r", norm=TwoSlopeNorm(0, -lim, lim))
    ax.set_title(t, loc="left", fontsize=10); ax.set_xlabel("Este UTM 19N (km)"); ax.set_ylabel("Norte (km)")
    fig.colorbar(im, ax=ax, shrink=0.8, label="m")
os.makedirs(f"{RAIZ}/04_figuras/borradores", exist_ok=True)
plt.savefig(f"{RAIZ}/04_figuras/borradores/descomposicion_C_vs_L.png", dpi=200)
plt.show()
