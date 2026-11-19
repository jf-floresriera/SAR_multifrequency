# -*- coding: utf-8 -*-
# =============================================================================
# BLOQUE A · Sentinel-1 HyP3 (INSAR_GAMMA) -> GeoTIFF con la convención común
# =============================================================================
import glob, os, zipfile, json
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.transform import from_origin

RAIZ = "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR"
S1_IN = f"{RAIZ}/01_datos_crudos/sentinel1_hyp3"
S1_OUT = f"{RAIZ}/02_procesados/sentinel1"
os.makedirs(S1_OUT, exist_ok=True)

LAMBDA_S1 = 0.055465763          # m (5.405 GHz)
SIGNO_S1 = -1                    # + = acercamiento al satélite; verificar con GNSS CCS1

for z in glob.glob(f"{S1_IN}/*.zip"):
    destino = z[:-4]
    if not os.path.isdir(destino):
        zipfile.ZipFile(z).extractall(os.path.dirname(z))

for carpeta in sorted(glob.glob(f"{S1_IN}/S1*_INT*")):
    if not os.path.isdir(carpeta):
        continue
    unw = glob.glob(f"{carpeta}/*_unw_phase.tif")
    if not unw:
        continue
    base = os.path.basename(carpeta)
    fechas = [t[:8] for t in base.split("_") if len(t) == 15 and t[8] == "T"]
    # track desde los metadatos (*.txt de HyP3)
    meta = {}
    for t in glob.glob(f"{carpeta}/*.txt"):
        for linea in open(t, errors="ignore"):
            if ":" in linea:
                k, v = linea.split(":", 1)
                meta[k.strip()] = v.strip()
    nombre = f"S1_{fechas[0]}_{fechas[-1]}_{base[-4:]}" if fechas else base
    with rasterio.open(unw[0]) as s:
        fase = s.read(1).astype("float32"); perfil = s.profile
    fase[fase == 0] = np.nan
    perfil.update(dtype="float32", nodata=np.nan, compress="deflate")
    with rasterio.open(f"{S1_OUT}/{nombre}_los_m.tif", "w", **perfil) as d:
        d.write(SIGNO_S1 * fase * LAMBDA_S1 / (4 * np.pi), 1)
    for suf, sal in (("_corr.tif", "_coh.tif"),):
        f = glob.glob(f"{carpeta}/*{suf}")
        if f:
            with rasterio.open(f[0]) as s:
                with rasterio.open(f"{S1_OUT}/{nombre}{sal}", "w", **perfil) as d:
                    d.write(s.read(1).astype("float32"), 1)
    # Vectores de mirada HyP3: lv_theta (elevación desde horizontal), lv_phi (desde el Este, antihorario)
    th, ph = glob.glob(f"{carpeta}/*_lv_theta.tif"), glob.glob(f"{carpeta}/*_lv_phi.tif")
    if th and ph:
        with rasterio.open(th[0]) as s: theta = s.read(1).astype("float32")
        with rasterio.open(ph[0]) as s: phi = s.read(1).astype("float32")
        theta[theta == 0] = np.nan
        comps = {"E": np.cos(theta) * np.cos(phi), "N": np.cos(theta) * np.sin(phi), "U": np.sin(theta)}
        for k, v in comps.items():
            with rasterio.open(f"{S1_OUT}/{nombre}_los{k}.tif", "w", **perfil) as d:
                d.write(v.astype("float32"), 1)
    else:
        print(f"[!] {nombre}: sin lv_theta/lv_phi (reenviar a HyP3 con include_look_vectors=True)")
    print("✓", nombre)


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
