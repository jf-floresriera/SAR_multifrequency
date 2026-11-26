# -*- coding: utf-8 -*-
"""
Vantor (ex-Maxar) Open Data · evento Venezuela-Earthquake-Jun-2026 · escenas ANTES/DESPUÉS por sitio
Vantor (ex-Maxar) Open Data · Venezuela-Earthquake-Jun-2026 event · PRE/POST scenes per site

Para qué / Why: tener un "antes" óptico de ~0,4 m (en lugar del mosaico Planet de 4,8 m) sin pansharpening propio:
el archivo publicado ("visual") ya es color de alta resolución. / a ~0.4 m optical "before" (instead of the 4.8 m
Planet mosaic) with no pansharpening of our own: the published 'visual' file is already high-resolution colour.

Licencia / Licence: CC BY-NC 4.0 (igual que Planet: NO subir a GitHub; atribuir "Imagery © Vantor/Maxar, CC BY-NC 4.0").
Entrada / Input: SITIOS (nombre: (lat, lon)), LADO_M (1000). Salida / Output: <SALIDA>/vantor_escenas_<sitio>.csv y recortes PNG.
Sin descargas completas: lectura por ventana (COG) / no full downloads: windowed COG reads.
"""
import os
import sys

import numpy as np
import pandas as pd
import requests

BASE = "https://vantor-opendata.s3.amazonaws.com/events/Venezuela-Earthquake-Jun-2026/"
_g = globals()
LADO_M = _g.get("LADO_M", 1000)
SALIDA = _g.get("SALIDA_VANTOR", "./vantor")
GUARDAR_RECORTES = _g.get("GUARDAR_RECORTES", True)
SITIOS = _g.get("SITIOS_VANTOR", {"Caracas_Este_Petare": (10.4835, -66.8070)})   # (lat, lon) · verificar / verify
os.makedirs(SALIDA, exist_ok=True)


def _items():
    c = requests.get(BASE + "collection.json", timeout=60).json()
    out = []
    for l in c["links"]:
        if l["rel"] != "item":
            continue
        try:
            j = requests.get(l["href"], timeout=60).json()
            p = j["properties"]
            out.append(dict(id=j["id"], fecha=p["datetime"][:10], fase=p.get("phase"), nubes=p.get("eo:cloud_cover"),
                            fuera_nadir=p.get("view:off_nadir"), sol_elev=p.get("view:sun_elevation"),
                            gsd_pan=p.get("pan_gsd"), gsd_ms=p.get("multispectral_gsd"), bbox=j["bbox"],
                            href=j["assets"]["visual"]["href"]))
        except Exception as e:
            print("   (item omitido / skipped)", l["href"][-24:], e)
    return pd.DataFrame(out)


def _cubre(bb, lat, lon, lado_m):
    dlat = lado_m / 2 / 111320.0
    dlon = lado_m / 2 / (111320.0 * np.cos(np.radians(lat)))
    return bb[0] <= lon - dlon and bb[2] >= lon + dlon and bb[1] <= lat - dlat and bb[3] >= lat + dlat


def _recorte(href, lat, lon, lado_m):
    """Ventana lado×lado m centrada en (lat, lon). Devuelve (rgb uint8, fracción válida) / windowed chip."""
    import rasterio
    from rasterio.windows import from_bounds
    from pyproj import Transformer
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
        with rasterio.open(href) as ds:
            # ventana por las esquinas en lon/lat (sirve con CRS proyectado o geográfico) / corners in lon/lat
            dlat = lado_m / 2 / 111320.0
            dlon = lado_m / 2 / (111320.0 * np.cos(np.radians(lat)))
            tr = Transformer.from_crs(4326, ds.crs, always_xy=True)
            xs, ys = zip(*[tr.transform(lon + sx * dlon, lat + sy * dlat) for sx in (-1, 1) for sy in (-1, 1)])
            w = from_bounds(min(xs), min(ys), max(xs), max(ys), ds.transform)
            a = ds.read([1, 2, 3], window=w, boundless=True, fill_value=0)
    rgb = np.moveaxis(a, 0, -1)
    valido = float((rgb.sum(axis=2) > 0).mean())
    return rgb, valido


it = _items()
print(f"{len(it)} escenas en el evento / scenes in the event")
for nombre, (lat, lon) in SITIOS.items():
    c = it[[_cubre(b, lat, lon, LADO_M) for b in it.bbox]].copy()
    c["lado_m"] = LADO_M
    c = c.sort_values(["fase", "nubes", "fuera_nadir"]).drop(columns=["bbox"])
    c.to_csv(f"{SALIDA}/vantor_escenas_{nombre}.csv", index=False)
    print(f"\n{nombre} ({lat:.4f}, {lon:.4f}): {len(c)} escenas cubren {LADO_M} m × {LADO_M} m")
    print(c.drop(columns=["href", "lado_m"]).to_string(index=False))
    if GUARDAR_RECORTES:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        mejores = pd.concat([c[c.fase == "pre"].head(3), c[c.fase == "post"].head(2)])
        fig, axs = plt.subplots(1, len(mejores), figsize=(4 * len(mejores), 4.3), squeeze=False)
        for ax, (_, r) in zip(axs[0], mejores.iterrows()):
            try:
                rgb, v = _recorte(r.href, lat, lon, LADO_M)
                ax.imshow(rgb); ax.set_title(f"{r.fase.upper()} {r.fecha}\nnubes {r.nubes}% · nadir {r.fuera_nadir:.0f}° · válido {v:.0%}", fontsize=8)
                print(f"   recorte {r.id}: {rgb.shape[1]}×{rgb.shape[0]} px, válido {v:.0%}")
            except Exception as e:
                ax.set_title(f"{r.id}\nERROR {e}"[:60], fontsize=7)
            ax.axis("off")
        fig.tight_layout(); fig.savefig(f"{SALIDA}/vantor_recortes_{nombre}.png", dpi=110); plt.close(fig)
print("\nCréditos / credit: Imagery © Vantor (Maxar), CC BY-NC 4.0. NO subir los recortes a GitHub / do not commit the chips.")
