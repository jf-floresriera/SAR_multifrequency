# -*- coding: utf-8 -*-
"""
NISAR GUNW (HDF5) -> GeoTIFF listos para análisis multisensor
Extrae de cada GUNW cosísmico:
  *_los_m.tif          desplazamiento LOS en metros (signo armonizado: + = hacia el satélite)
  *_los_iono_m.tif     LOS con la pantalla ionosférica restada (si el producto la trae)
  *_coh.tif            coherencia (0-1)
  *_concomp.tif        componentes conectadas del desenrollado (0 = no confiable)
  *_losE.tif, *_losN.tif, *_losU.tif   vector unitario de mirada (para descomponer E/U)
y un resumen JSON con longitud de onda, fechas, track y EPSG.
"""
import glob
import json
import os
import re

import h5py
import numpy as np
import rasterio
from rasterio.transform import from_origin

ENTRADA = "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR/01_datos_crudos/nisar_gunw"
SALIDA = "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR/02_procesados/nisar"
os.makedirs(SALIDA, exist_ok=True)
C = 299_792_458.0

# Convención común del proyecto: LOS positivo = acercamiento al satélite (range decrease).
# Si la validación con GNSS CCS1 (dE ≈ -0.46 m, Suárez & Arenas 2026) sale con signo
# opuesto, cambiar SIGNO a +1. NISAR mira a la IZQUIERDA: en órbita ascendente mira al
# oeste, así que el movimiento al oeste de CCS1 debe verse como ACERCAMIENTO (+).
SIGNO = -1


def buscar(h5, termina, contiene=None):
    hits = []
    h5.visit(lambda n: hits.append(n) if n.endswith(termina) and (contiene is None or contiene in n) else None)
    return hits[0] if hits else None


def guardar(arr, x, y, epsg, ruta, nodata=np.nan):
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
    arr = np.asarray(arr, dtype="float32")
    if dy > 0:                      # filas de sur a norte -> voltear
        arr, dy = arr[::-1], -dy
        y = y[::-1]
    tr = from_origin(float(x[0]) - dx / 2, float(y[0]) - dy / 2, dx, -dy)
    with rasterio.open(ruta, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                       count=1, dtype="float32", crs=f"EPSG:{epsg}", transform=tr,
                       nodata=nodata, compress="deflate", tiled=True) as dst:
        dst.write(arr, 1)


resumen = []
for f in sorted(glob.glob(f"{ENTRADA}/*GUNW*.h5")):
    base = os.path.basename(f).replace(".h5", "")
    m = re.search(r"GUNW_\d+_(\d{3})_([AD])_(\d{3})", base)
    track = f"{m.group(1)}{m.group(2)}" if m else "NA"
    fechas = re.findall(r"(\d{8})T\d{6}", base)
    corto = f"NISAR_T{track}_{fechas[0]}_{fechas[-1]}" if fechas else base[:40]
    print(f"\n== {corto}")
    with h5py.File(f, "r") as h:
        p_unw = buscar(h, "unwrappedPhase", "unwrappedInterferogram")
        p_coh = buscar(h, "coherenceMagnitude", "unwrappedInterferogram")
        p_cc = buscar(h, "connectedComponents", "unwrappedInterferogram")
        p_ion = buscar(h, "ionospherePhaseScreen", "unwrappedInterferogram")
        grupo = p_unw.rsplit("/", 2)[0]                     # .../unwrappedInterferogram
        p_x = buscar(h, "xCoordinates", grupo) or buscar(h, "xCoordinates", "frequencyA")
        p_y = buscar(h, "yCoordinates", grupo) or buscar(h, "yCoordinates", "frequencyA")
        p_proj = buscar(h, "projection", grupo) or buscar(h, "projection", "frequencyA")
        p_f = buscar(h, "centerFrequency", "frequencyA")

        x, y = h[p_x][:], h[p_y][:]
        epsg = int(h[p_proj].attrs.get("epsg_code", h[p_proj][()]))
        f0 = float(np.ravel(h[p_f][()])[0]) if p_f else 1.257e9
        lam = C / f0
        fill = h[p_unw].attrs.get("_FillValue", 0)

        unw = h[p_unw][:].astype("float32")
        unw[(unw == fill) | ~np.isfinite(unw)] = np.nan
        los = SIGNO * unw * lam / (4 * np.pi)
        guardar(los, x, y, epsg, f"{SALIDA}/{corto}_los_m.tif")
        guardar(h[p_coh][:], x, y, epsg, f"{SALIDA}/{corto}_coh.tif")
        if p_cc:
            guardar(h[p_cc][:].astype("float32"), x, y, epsg, f"{SALIDA}/{corto}_concomp.tif", nodata=-1)
        if p_ion:
            ion = h[p_ion][:].astype("float32")
            if ion.shape == unw.shape:
                guardar(SIGNO * (unw - ion) * lam / (4 * np.pi), x, y, epsg,
                        f"{SALIDA}/{corto}_los_iono_m.tif")
            else:
                print(f"   ionosfera en otra grilla {ion.shape} vs {unw.shape}: se guarda aparte")
                xi = h[buscar(h, "xCoordinates", p_ion.rsplit('/', 1)[0])][:]
                yi = h[buscar(h, "yCoordinates", p_ion.rsplit('/', 1)[0])][:]
                guardar(SIGNO * ion * lam / (4 * np.pi), xi, yi, epsg, f"{SALIDA}/{corto}_iono_m.tif")

        # Vectores de mirada (cubo radarGrid: altura × y × x) -> capa más cercana a 0 m
        vec = {}
        for comp in ("X", "Y", "Z"):
            p = buscar(h, f"losUnitVector{comp}", "radarGrid")
            if p:
                vec[comp] = p
        if vec:
            rg = vec["X"].rsplit("/", 1)[0]
            xr, yr = h[buscar(h, "xCoordinates", rg)][:], h[buscar(h, "yCoordinates", rg)][:]
            pz = buscar(h, "heightAboveEllipsoid", rg)
            k = int(np.argmin(np.abs(h[pz][:]))) if pz else 0
            lx, ly = h[vec["X"]][k], h[vec["Y"]][k]
            lz = h[vec["Z"]][k] if "Z" in vec else np.sqrt(np.clip(1 - lx**2 - ly**2, 0, 1))
            # Vector suelo->satélite (E, N, U); con nuestra convención LOS+ = hacia el satélite
            for nombre, comp in (("E", lx), ("N", ly), ("U", lz)):
                guardar(comp, xr, yr, epsg, f"{SALIDA}/{corto}_los{nombre}.tif")
        else:
            print("   [!] No se encontraron vectores LOS en radarGrid")

        v = los[np.isfinite(los)]
        info = dict(producto=base, nombre_corto=corto, track=track, epsg=epsg,
                    lambda_m=round(lam, 5), fecha_ref=fechas[0] if fechas else None,
                    fecha_sec=fechas[-1] if fechas else None,
                    tiene_ionosfera=bool(p_ion), tiene_vectores_los=bool(vec),
                    los_p2_m=float(np.percentile(v, 2)) if v.size else None,
                    los_p98_m=float(np.percentile(v, 98)) if v.size else None,
                    coh_media=float(np.nanmean(h[p_coh][:])))
        resumen.append(info)
        print(json.dumps(info, indent=1))

json.dump(resumen, open(f"{SALIDA}/resumen_nisar.json", "w"), indent=1)
print(f"\n{len(resumen)} productos convertidos -> {SALIDA}")
