# -*- coding: utf-8 -*-
"""
PUNTO B · ¿El GUNW de NISAR ya trae la ionosfera (y la troposfera) aplicadas a la fase? / Is the ionosphere already applied?
=============================================================================================================================
Dos pruebas independientes / two independent tests:
 1) METADATOS: lee en cada GUNW las banderas «...CorrectionApplied» con su RUTA completa. Si la bandera está bajo
    `.../pixelOffsets` o `.../geocoding` se refiere a los desplazamientos de píxel o a la geocodificación, NO a `unwrappedPhase`.
 2) PRUEBA EMPÍRICA: compara en el CAMPO LEJANO (> 20 km de las fallas, solo tierra) la LOS sin corregir (`*_los_m.tif`) con la LOS
    a la que le restamos la pantalla ionosférica (`*_los_iono_m.tif`):
      · si restar la ionosfera REDUCE la dispersión y la rampa de gran escala → NO venía aplicada: hay que restarla (lo que hacemos);
      · si las AUMENTA claramente → YA venía aplicada: la estaríamos restando dos veces → USAR_IONO = False.
    Medidas: MAD robusta (mm) y amplitud del plano ajustado (mm en 100 km) en el campo lejano.
Salida: 05_documentacion/verificacion_ionosfera_{es,en}.csv y una recomendación impresa.
"""
import glob
import os
import sys as _sys

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
GUNW = [f"{RAIZ}/01_datos_crudos/nisar_gunw"]
DOC = f"{RAIZ}/05_documentacion"
WIN, DEG, KM = (-69.5, -65.8, 9.6, 11.2), 0.002, 20.0

# ---------------------------------------------------------------- 1) metadatos con ruta completa
try:
    import h5py
    filas_m = []
    for d in GUNW:
        for f in sorted(glob.glob(f"{d}/*GUNW*.h5")):
            with h5py.File(f, "r") as h:
                def _v(n, o):
                    if isinstance(o, h5py.Dataset) and n.lower().endswith("applied") and any(k in n.lower() for k in ("iono", "tropo")):
                        try:
                            val = o[()]; val = val.decode() if isinstance(val, bytes) else val
                        except Exception:
                            val = "?"
                        filas_m.append(dict(producto=os.path.basename(f)[:46], bandera=n.split("/")[-1], valor=str(val), ruta=n))
                h.visititems(_v)
    M = pd.DataFrame(filas_m)
    if len(M):
        print("=== 1) BANDERAS CON SU RUTA / FLAGS WITH THEIR PATH ===")
        print(M.drop_duplicates(["bandera", "valor", "ruta"])[["bandera", "valor", "ruta"]].to_string(index=False))
        print("   → si la ruta contiene 'pixelOffsets' o 'geocoding', la bandera NO se refiere a la fase desenvuelta.")
except Exception as e:
    print("[!] no se pudieron leer los GUNW / could not read GUNW:", e)

# ---------------------------------------------------------------- 2) prueba empírica en campo lejano
nx, ny = int((WIN[1] - WIN[0]) / DEG), int((WIN[3] - WIN[2]) / DEG)
TR = from_origin(WIN[0], WIN[3], DEG, DEG)


def leer(r):
    o = np.full((ny, nx), np.nan, "float32")
    with rasterio.open(r) as s:
        reproject(rasterio.band(s, 1), o, src_transform=s.transform, src_crs=s.crs, src_nodata=s.nodata, dst_transform=TR,
                  dst_crs="EPSG:4326", dst_nodata=np.nan, resampling=Resampling.average)
    return o * 1000.0


from mascaras import mascara_tierra
TIERRA = mascara_tierra(RAIZ, TR, (ny, nx))
LEJOS = None
try:
    import geopandas as gpd
    from rasterio.features import rasterize
    from scipy.ndimage import distance_transform_edt
    fl = gpd.read_file(f"{RAIZ}/01_datos_crudos/mapas_base/mapas_base.gpkg", layer="fallas_activas_gem")
    m = rasterize([(g, 1) for g in fl.geometry if g is not None], out_shape=(ny, nx), transform=TR, all_touched=True)
    LEJOS = distance_transform_edt(m == 0, sampling=(DEG * 111.32, DEG * 111.32 * np.cos(np.radians(10.5)))) > KM
except Exception as e:
    print("[!] sin capa de fallas: se usa toda la tierra / no faults layer:", e)
yy, xx = np.mgrid[0:ny, 0:nx]
X, Y = xx * DEG * 109.5, yy * DEG * 110.6                     # km


def medidas(a, base):
    v = np.isfinite(a) & base
    if v.sum() < 2000:
        return np.nan, np.nan, int(v.sum())
    z = a[v]; mad = 1.4826 * np.median(np.abs(z - np.median(z)))
    A = np.c_[X[v], Y[v], np.ones(v.sum())]
    cx, cy, _ = np.linalg.lstsq(A, z, rcond=None)[0]
    return float(mad), float(np.hypot(cx, cy) * 100.0), int(v.sum())       # mm, mm por 100 km


filas = []
for f in sorted(glob.glob(f"{RAIZ}/02_procesados/nisar/NISAR_T*_los_m.tif")):
    fi = f.replace("_los_m.tif", "_los_iono_m.tif")
    if not os.path.exists(fi):
        continue
    a, b = leer(f), leer(fi)
    base = (TIERRA if TIERRA is not None else np.ones((ny, nx), bool)) & (LEJOS if LEJOS is not None else True)
    base = base & np.isfinite(a) & np.isfinite(b)
    m0, r0, n0 = medidas(a, base); m1, r1, _ = medidas(b, base)
    if np.isnan(m0):
        veredicto = "pocos píxeles de campo lejano: no concluyente"
    elif m1 < 0.85 * m0 or r1 < 0.85 * r0:
        veredicto = "restar la ionosfera MEJORA → NO venía aplicada (correcto restarla)"
    elif m1 > 1.15 * m0 and r1 > 1.15 * r0:
        veredicto = "restar la ionosfera EMPEORA → probablemente YA venía aplicada (no restarla)"
    else:
        veredicto = "efecto pequeño (< 15 %): la ionosfera apenas cambia el resultado"
    filas.append(dict(producto=os.path.basename(f)[:-10], pix_campo_lejano=n0, mad_sin_iono_mm=round(m0, 1), mad_con_iono_mm=round(m1, 1),
                      rampa_sin_iono_mm_100km=round(r0, 1), rampa_con_iono_mm_100km=round(r1, 1), veredicto=veredicto))
V = pd.DataFrame(filas)
os.makedirs(DOC, exist_ok=True)
V.to_csv(f"{DOC}/verificacion_ionosfera_es.csv", index=False)
V.rename(columns={"producto": "product", "pix_campo_lejano": "far_field_px", "mad_sin_iono_mm": "mad_without_iono_mm",
                  "mad_con_iono_mm": "mad_with_iono_mm", "rampa_sin_iono_mm_100km": "ramp_without_iono_mm_100km",
                  "rampa_con_iono_mm_100km": "ramp_with_iono_mm_100km", "veredicto": "verdict"}).to_csv(f"{DOC}/verificacion_ionosfera_en.csv", index=False)
pd.set_option("display.width", 220, "display.max_colwidth", 80)
print("\n=== 2) PRUEBA EMPÍRICA EN CAMPO LEJANO / FAR-FIELD TEST ===")
print(V.to_string(index=False) if len(V) else "(sin pares *_los_m / *_los_iono_m: ejecute nisar_tif)")
if len(V):
    peor = V.veredicto.str.contains("EMPEORA").sum(); mejor = V.veredicto.str.contains("MEJORA").sum()
    print("\nRECOMENDACIÓN / RECOMMENDATION:",
          "mantener USAR_IONO=True (restar la ionosfera)" if mejor >= peor else "usar USAR_IONO=False (la ionosfera ya viene aplicada)",
          f"· {mejor} productos mejoran, {peor} empeoran")
