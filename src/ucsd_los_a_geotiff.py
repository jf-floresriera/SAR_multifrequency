# -*- coding: utf-8 -*-
"""
Desplazamientos LOS procesados por UCSD/Scripps (ALOS-2 T040A, T134D, T135D; NISAR T162A, T061A, T054D, T126D) → GeoTIFF
UCSD/Scripps processed LOS displacements → GeoTIFF on our common lon/lat grid, so they can be compared with our products.

Fuente / Source: https://topex.ucsd.edu/VNZ_7.5/index.html (sección "Processed InSAR data for Modelers", actualizada 14-ago-2026).
Formato (texto) / format: #lon #lat #look_E #look_N #look_U #displacement(mm). Procesados con GMTSAR; ALOS-2 SIN corrección
ionosférica (lo dicen los autores). La página NO declara: licencia, convención de signo ni método de remuestreo.
IMPORTANTE: los archivos se llaman "500 m" pero la malla es de ~1" (≈ 30 m): cada .tar.gz pesa ~445 MB (1,45 GB de texto).
Se leen en streaming y se promedian en celdas de 0,0008° (≈ 88 m) sin descomprimir a disco.

Convención de signo: se decide comparando con NUESTRO producto NISAR del mismo track y par (correlación); si no existe, se asume
+ (hacia el satélite) y se avisa. Se puede forzar con SIGNO_UCSD = +1 / −1.
Licencia: no declarada → citar la fuente, NO redistribuir los archivos (no subir a GitHub).
Salida / Output: <RAIZ>/02_procesados/ucsd/UCSD_{ALOS2|NISAR}_T<track>_<ref>_<sec>_los_m.tif (+ _losE/_losN/_losU) y ucsd_resumen.csv
Variables: SOLO_TRACKS (lista, p. ej. ["NSR_T162A"]) para probar con uno; SIGNO_UCSD.
"""
import glob
import os
import sys as _sys
import tarfile

import numpy as np
import pandas as pd
import requests
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
SOLO = globals().get("SOLO_TRACKS", None)
SIGNO_UCSD = globals().get("SIGNO_UCSD", None)
DIR_BAJADA = globals().get("DIR_UCSD", f"{RAIZ}/01_datos_crudos/ucsd_los")
OUT = f"{RAIZ}/02_procesados/ucsd"
os.makedirs(DIR_BAJADA, exist_ok=True); os.makedirs(OUT, exist_ok=True)
BASE = "https://topex.ucsd.edu/VNZ_7.5/web/los_files/sat_look_disp_{k}_500m_mask_clean.tar.gz"
H = {"User-Agent": "GUAIRA-SAR research (github.com/jf-floresriera/SAR_multifrequency)"}
# (clave en el archivo, sensor, track, fecha_ref, fecha_sec): pares según la página de UCSD / pairs as stated on the UCSD page
PRODUCTOS = [("NSR_T162A", "NISAR", "162A", "20260613", "20260625"), ("NSR_T61A", "NISAR", "061A", "20260618", "20260630"),
             ("NSR_T54D", "NISAR", "054D", "20260617", "20260629"), ("NSR_T126D", "NISAR", "126D", "20260622", "20260704"),
             ("ALOS2_T040A", "ALOS2", "040A", "20250114", "20260630"), ("ALOS2_T134D", "ALOS2", "134D", "20260610", "20260708"),
             ("ALOS2_T135D", "ALOS2", "135D", "20260615", "20260629")]
LON0, LON1, LAT0, LAT1, DEG = -69.25, -66.80, 9.80, 11.05, 0.0008
NX, NY = int(round((LON1 - LON0) / DEG)), int(round((LAT1 - LAT0) / DEG))
TR = from_origin(LON0, LAT1, DEG, DEG)


def bajar(k):
    ruta = f"{DIR_BAJADA}/sat_look_disp_{k}_500m_mask_clean.tar.gz"
    if os.path.exists(ruta) and os.path.getsize(ruta) > 1e8:
        return ruta
    print(f"   descargando / downloading {k} (~445 MB)…")
    with requests.get(BASE.format(k=k), headers=H, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(ruta + ".part", "wb") as f:
            for ch in r.iter_content(1 << 20):
                f.write(ch)
    os.replace(ruta + ".part", ruta)
    return ruta


def a_celdas(ruta_tgz):
    """Promedia las columnas en celdas DEG (streaming desde el .tar.gz). Devuelve dict de arreglos (NY, NX) y n filas."""
    S = {c: np.zeros(NY * NX, "float64") for c in ("E", "N", "U", "d")}
    C = np.zeros(NY * NX, "int32"); n = 0
    with tarfile.open(ruta_tgz, "r:*") as t:     # el T054D no está comprimido con gzip / T054D is not gzip-compressed
        m = next(x for x in t.getmembers() if x.isfile())
        fh = t.extractfile(m)
        for ch in pd.read_csv(fh, sep=r"\s+", header=None, comment="#", dtype="float32", chunksize=2_000_000):
            a = ch.values; n += len(a)
            ix = ((a[:, 0] - LON0) / DEG).astype(np.int64); iy = ((LAT1 - a[:, 1]) / DEG).astype(np.int64)
            ok = (ix >= 0) & (ix < NX) & (iy >= 0) & (iy < NY) & np.isfinite(a[:, 5])
            idx = (iy * NX + ix)[ok]
            C += np.bincount(idx, minlength=NY * NX).astype("int32")
            for col, key in ((2, "E"), (3, "N"), (4, "U"), (5, "d")):
                S[key] += np.bincount(idx, weights=a[ok, col], minlength=NY * NX)
    with np.errstate(all="ignore"):
        R = {k: np.where(C > 0, v / C, np.nan).reshape(NY, NX).astype("float32") for k, v in S.items()}
    return R, n


def escribir(arr, ruta):
    with rasterio.open(ruta, "w", driver="GTiff", height=NY, width=NX, count=1, dtype="float32", crs="EPSG:4326",
                       transform=TR, nodata=np.nan, compress="deflate") as d:
        d.write(arr, 1)


def _nuestro(track, ref, sec):
    """Nuestro producto NISAR del mismo track y par, remuestreado a esta malla / our NISAR product, resampled to this grid."""
    out = None
    for f in sorted(glob.glob(f"{RAIZ}/02_procesados/nisar/NISAR_T{track}_*{ref}_{sec}_los_m.tif")):    # todos los frames / all frames
        dst = np.full((NY, NX), np.nan, "float32")
        with rasterio.open(f) as s:
            reproject(rasterio.band(s, 1), dst, src_transform=s.transform, src_crs=s.crs, src_nodata=s.nodata,
                      dst_transform=TR, dst_crs="EPSG:4326", dst_nodata=np.nan, resampling=Resampling.average)
        out = dst if out is None else np.where(np.isfinite(out), out, dst)
    return out


filas = []
signos = []
tareas = [p for p in PRODUCTOS if (SOLO is None or p[0] in SOLO)]
for k, sensor, track, ref, sec in tareas:
    try:
        R, n = a_celdas(bajar(k))
    except Exception as e:
        print(f"[!] {k}: {e}"); continue
    los_m = R["d"] / 1000.0
    nuestro = _nuestro(track, ref, sec) if sensor == "NISAR" else None
    corr = np.nan
    if nuestro is not None:
        v = np.isfinite(los_m) & np.isfinite(nuestro)
        if v.sum() > 1000:
            corr = float(np.corrcoef(los_m[v], nuestro[v])[0, 1])
            signos.append(np.sign(corr))
    nombre = f"UCSD_{sensor}_T{track}_{ref}_{sec}"
    filas.append(dict(producto=nombre, clave=k, sensor=sensor, track=track, ref=ref, sec=sec, n_filas=n,
                      celdas_validas=int(np.isfinite(los_m).sum()), cobertura_pct=round(100 * float(np.isfinite(los_m).mean()), 1),
                      p2_cm=round(float(np.nanpercentile(los_m, 2)) * 100, 1), p98_cm=round(float(np.nanpercentile(los_m, 98)) * 100, 1),
                      corr_con_nuestro_NISAR=round(corr, 3) if np.isfinite(corr) else np.nan))
    cache = (nombre, los_m, R)
    globals().setdefault("_CACHE_UCSD", []).append(cache)
    print(f"✓ {nombre}: {n:,} filas → {np.isfinite(los_m).sum():,} celdas de {DEG}° · LOS p2/p98 = "
          f"{filas[-1]['p2_cm']}/{filas[-1]['p98_cm']} cm · corr. con el nuestro = {filas[-1]['corr_con_nuestro_NISAR']}")

# convención de signo / sign convention
if SIGNO_UCSD is not None:
    s_final = float(SIGNO_UCSD); print(f"\nSigno forzado / forced sign: {s_final:+.0f}")
elif signos:
    s_final = float(np.sign(np.sum(signos))); print(f"\nSigno decidido por correlación con NISAR propio / sign from correlation with our NISAR: {s_final:+.0f}")
else:
    s_final = 1.0
    print("\n[!] Sin NISAR propio con el que comparar: se asume + = hacia el satélite (UCSD no declara la convención). "
          "Verifique con SIGNO_UCSD / without our NISAR to compare, assuming + = toward satellite (UCSD does not state it).")
for nombre, los_m, R in globals().get("_CACHE_UCSD", []):
    escribir(s_final * los_m, f"{OUT}/{nombre}_los_m.tif")
    for k in ("E", "N", "U"):
        escribir(R[k], f"{OUT}/{nombre}_los{k}.tif")
globals()["_CACHE_UCSD"] = []
res = pd.DataFrame(filas); res["signo_aplicado"] = s_final
res.to_csv(f"{OUT}/ucsd_resumen.csv", index=False)
print(res.drop(columns=["clave"]).to_string(index=False))
print(f"\nSalida / output: {OUT}  (citar UCSD/Scripps; no redistribuir / cite, do not redistribute)")
