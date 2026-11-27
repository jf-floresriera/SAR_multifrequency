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
S1_OUT = S1_OUT_CO = f"{RAIZ}/02_procesados/sentinel1"
os.makedirs(S1_OUT, exist_ok=True)

LAMBDA_S1 = 0.055465763          # m (5.405 GHz)
SIGNO_S1 = -1                    # + = acercamiento al satélite; verificar con GNSS CCS1

for z in glob.glob(f"{S1_IN}/*.zip"):
    destino = z[:-4]
    if not os.path.isdir(destino):
        zipfile.ZipFile(z).extractall(os.path.dirname(z))

import re as _re
_vistos = set()
for carpeta in sorted(glob.glob(f"{S1_IN}/S1*_INT*")):
    if not os.path.isdir(carpeta):
        continue
    _par = _re.sub(r"_[0-9A-F]{4}$", "", os.path.basename(carpeta))
    # si existe la versión a 40 m del mismo par, se omite la de 80 m / skip 80 m when 40 m exists
    if "INT80" in _par and glob.glob(f"{S1_IN}/{_par.replace('INT80', 'INT40')}*"):
        print("   80 m omitido (hay 40 m) / 80 m skipped (40 m exists):", os.path.basename(carpeta)); continue
    if _par in _vistos:
        print("   duplicado omitido / duplicate skipped:", os.path.basename(carpeta)); continue
    _vistos.add(_par)
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
    S1_OUT = S1_OUT_CO
    if fechas and fechas[-1] < "20260624":                      # par PRE-sísmico (control) → carpeta aparte
        S1_OUT = f"{RAIZ}/02_procesados/sentinel1_pre"; os.makedirs(S1_OUT, exist_ok=True)
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


