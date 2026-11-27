# -*- coding: utf-8 -*-
"""
E · EXPLORACIÓN SEMIAUTOMÁTICA DEL ÓPTICO (Vantor/WorldView y Planet SkySat) EN LAS ZONAS MÁS DAÑADAS — el autor decide
E · Semi-automatic exploration of optical imagery (Vantor/WorldView, Planet SkySat) over the most damaged areas — the author decides
=============================================================================================================================
1) ZONAS: a partir del daño de referencia (`danio_referencia.gpkg`, capa `edificios_danio`) cuenta edificios destruidos/dañados en celdas
   de 500 m y elige las N_ZONAS celdas con más daño (separadas ≥ 1 km). Cada zona = recuadro de LADO_M (por defecto 600 m).
2) CANDIDATAS: todas las escenas Vantor (antes y después) y Planet SkySat (después) + el mosaico Planet Q1-2026 (antes) que cubren la zona.
3) HOJA DE CONTACTO por zona (PNG): un recorte por escena, con sensor, fecha, fase, nubes del catálogo, ángulo fuera de nadir,
   elevación solar y dos índices medidos en el recorte: % de píxeles «nube/saturado» (muy brillantes) y % «sombra» (muy oscuros).
4) TABLA DE DECISIÓN `05_documentacion/seleccion_optico.csv`: una fila por zona y escena, con una columna `sugerido` (la mejor según
   nubes, sombra, sol y nadir) y una columna `usar` VACÍA que llena el AUTOR con «si» en las escenas que quiere para la figura
   (una «antes» y una «después» por zona). Si el archivo ya existe, se conservan las decisiones del autor.
   Las figuras de daño (`danio_sitios`) usarán solo las filas con usar = si.
Licencias: Vantor y Planet CC BY-NC 4.0 → no subir recortes a GitHub.
Variables: N_ZONAS (5), LADO_M (600), MAX_POR_FASE (6).
"""
import glob
import io
import json
import os
import sys as _sys

import numpy as np
import pandas as pd
import requests

_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import T, TXT
from estilo_figuras import aplicar_estilo, exportar
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import box

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
TRAB = globals().get("TRABAJO", os.path.join(os.path.dirname(RAIZ), "inventario_2026"))
N_ZONAS = int(globals().get("N_ZONAS") or 5)
LADO = float(globals().get("LADO_M") or 600)
MAXF = int(globals().get("MAX_POR_FASE") or 6)
FIG = f"{RAIZ}/04_figuras/borradores/optico_exploracion"
DOC = f"{RAIZ}/05_documentacion"
os.makedirs(FIG, exist_ok=True); os.makedirs(DOC, exist_ok=True)
SISMO = pd.Timestamp("2026-06-24")
VANTOR = "https://vantor-opendata.s3.amazonaws.com/events/Venezuela-Earthquake-Jun-2026/"
PLANET = "https://data.source.coop/planet/disasterdata/venezuela-earthquake-2026-06-24"
TXT.update({"oe_ant": {"es": "ANTES", "en": "BEFORE"}, "oe_des": {"es": "DESPUÉS", "en": "AFTER"},
            "oe_nub": {"es": "nubes", "en": "clouds"}, "oe_som": {"es": "sombra", "en": "shadow"}})

# ---------------------------------------------------------------- 1) zonas con más daño
gp = f"{RAIZ}/01_datos_crudos/danio_referencia/danio_referencia.gpkg"
d = gpd.read_file(gp, layer="edificios_danio")
cl = d.columns[[c.lower() in ("clase", "clase_danio", "dano", "damage") for c in d.columns]]
col = cl[0] if len(cl) else None
if col is not None:
    d = d[d[col].astype(str).str.lower().str.contains("destru|dañ|dan|damag|destroy")]
d = d.to_crs(32619)
cen = d.geometry.centroid
celda = 500.0
ij = pd.DataFrame({"i": (cen.x // celda).astype(int), "j": (cen.y // celda).astype(int)})
cont = ij.value_counts().reset_index(name="n").sort_values("n", ascending=False)
zonas = []
for r in cont.itertuples():
    x, y = (r.i + 0.5) * celda, (r.j + 0.5) * celda
    if all(np.hypot(x - z["x"], y - z["y"]) >= 1000 for z in zonas):
        zonas.append(dict(x=x, y=y, n=int(r.n)))
    if len(zonas) >= N_ZONAS:
        break
Z = gpd.GeoDataFrame(zonas, geometry=[box(z["x"] - LADO / 2, z["y"] - LADO / 2, z["x"] + LADO / 2, z["y"] + LADO / 2) for z in zonas], crs=32619)
Z["zona"] = [f"Z{k + 1}" for k in range(len(Z))]
Zll = Z.to_crs(4326)
Z["lon"], Z["lat"] = Zll.geometry.centroid.x.values, Zll.geometry.centroid.y.values
print("=== ZONAS CON MÁS EDIFICIOS DAÑADOS / MOST DAMAGED ZONES ===")
print(Z[["zona", "n", "lat", "lon"]].round(5).to_string(index=False))
Zll.assign(n=Z.n.values).to_file(f"{DOC}/zonas_danio.geojson", driver="GeoJSON")

# ---------------------------------------------------------------- 2) candidatas
cand = []
cache_v = f"{TRAB}/vantor/vantor_items.json"
if os.path.exists(cache_v):
    items = json.load(open(cache_v))
else:
    col_ = requests.get(VANTOR + "collection.json", timeout=60).json()
    items = [requests.get(l["href"], timeout=60).json() for l in col_["links"] if l["rel"] == "item"]
    os.makedirs(os.path.dirname(cache_v), exist_ok=True); json.dump(items, open(cache_v, "w"))
for j in items:
    p = j["properties"]
    cand.append(dict(sensor="Vantor/WorldView", id=j["id"], fecha=p["datetime"][:10], fase="antes" if p.get("phase") == "pre" else "después",
                     nubes_catalogo=p.get("eo:cloud_cover"), fuera_nadir=p.get("view:off_nadir"), sol_elev=p.get("view:sun_elevation"),
                     gsd_m=p.get("pan_gsd"), url=j["assets"]["visual"]["href"], geom=box(*j["bbox"])))
try:
    import pyarrow  # noqa
    pq = None
    for r in glob.glob(f"{TRAB}/umbra_planet_sitios/planet_post_items.parquet") + glob.glob("./umbra_planet_sitios/planet_post_items.parquet"):
        pq = r; break
    pl = gpd.read_parquet(pq if pq else io.BytesIO(requests.get(f"{PLANET}/post-event/items.parquet", timeout=120).content)).to_crs(4326)
    urls = None
    for r in glob.glob(f"{TRAB}/umbra_planet_sitios/planet_urls.csv") + glob.glob("./umbra_planet_sitios/planet_urls.csv"):
        urls = pd.read_csv(r); break
    if urls is not None:
        pl = pl.merge(urls, on="id", how="left")
        for r in pl[pl.url.notna()].itertuples():
            cand.append(dict(sensor="Planet SkySat", id=r.id, fecha=str(r.datetime)[:10], fase="después",
                             nubes_catalogo=getattr(r, "cloud_cover", np.nan), fuera_nadir=getattr(r, "view_off_nadir", np.nan),
                             sol_elev=getattr(r, "view_sun_elevation", np.nan), gsd_m=0.5, url=r.url, geom=r.geometry))
    else:
        print("[!] faltan las URLs de Planet (planet_urls.csv): ejecute danio_sitios una vez / Planet URLs missing")
except Exception as e:
    print("[!] Planet no disponible / unavailable:", str(e)[:100])
cand.append(dict(sensor="Planet (mosaico Q1-2026)", id="quarterly-mosaic-2026Q1", fecha="2026-03-31", fase="antes", nubes_catalogo=np.nan,
                 fuera_nadir=np.nan, sol_elev=np.nan, gsd_m=4.8, url=f"{PLANET}/pre-event/quarterly-mosaic/quarterly-mosaic-2026Q1.tif",
                 geom=box(-70, 9, -64, 12)))
C = gpd.GeoDataFrame(cand, geometry="geom", crs=4326)


def recorte(url, lon, lat, lado):
    import rasterio
    from rasterio.windows import from_bounds
    from pyproj import Transformer
    dl, dn = lado / 2 / (111320 * np.cos(np.radians(lat))), lado / 2 / 111320
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
        with rasterio.open(url) as s:
            tr = Transformer.from_crs(4326, s.crs, always_xy=True)
            xs, ys = zip(*[tr.transform(lon + a * dl, lat + b * dn) for a in (-1, 1) for b in (-1, 1)])
            w = from_bounds(min(xs), min(ys), max(xs), max(ys), s.transform)
            a = s.read([1, 2, 3], window=w, out_shape=(3, 400, 400), boundless=True, fill_value=0)
    rgb = np.moveaxis(a, 0, -1).astype(float)
    if rgb.max() > 255:
        rgb = np.clip(rgb / np.percentile(rgb[rgb > 0], 99) * 255, 0, 255) if (rgb > 0).any() else rgb
    v = rgb.sum(2) > 0
    lum = rgb.mean(2)
    return rgb.astype("uint8"), float(v.mean()), float(((lum > 225) & v).sum() / max(v.sum(), 1)), float(((lum < 25) & v).sum() / max(v.sum(), 1))


# ---------------------------------------------------------------- 3) hojas de contacto y 4) tabla de decisión
filas = []
for z in Z.itertuples():
    g = box(z.lon - 0.002, z.lat - 0.002, z.lon + 0.002, z.lat + 0.002)
    cz = C[C.geometry.contains(g)].copy()
    cz["dt"] = pd.to_datetime(cz.fecha)
    sel = pd.concat([cz[cz.fase == "antes"].sort_values("dt", ascending=False).head(MAXF),
                     cz[cz.fase == "después"].sort_values("dt").head(MAXF)])
    if sel.empty:
        print(f"   {z.zona}: sin escenas ópticas / no optical scenes"); continue
    for idioma in ("es", "en"):
        aplicar_estilo(7)
        n = len(sel); ncol = min(n, 6); nfil = int(np.ceil(n / ncol))
        fig, axs = plt.subplots(nfil, ncol, figsize=(180 / 25.4, (34 * nfil + 10) / 25.4), squeeze=False)
        for ax in axs.flat:
            ax.axis("off")
        for k, r in enumerate(sel.itertuples()):
            ax = axs.flat[k]
            try:
                img, val, nub, som = recorte(r.url, z.lon, z.lat, LADO)
            except Exception as e:
                img, val, nub, som = None, 0, np.nan, np.nan
                print(f"   {z.zona} {r.id}: no se pudo leer / unreadable: {str(e)[:60]}")
            if img is not None:
                ax.imshow(img)
            fase = T("oe_ant", idioma) if r.fase == "antes" else T("oe_des", idioma)
            ax.set_title(f"{fase} · {r.sensor.split(' ')[0]}\n{r.fecha} · {T('oe_nub', idioma)} {nub * 100:.0f}% · {T('oe_som', idioma)} {som * 100:.0f}%",
                         fontsize=5.2, loc="left", color="#B2182B" if r.fase == "después" else "#0072B2")
            ax.text(0.02, 0.02, f"#{k + 1}", transform=ax.transAxes, fontsize=6, color="white", fontweight="bold")
            if idioma == "es":
                filas.append(dict(zona=z.zona, lat=round(z.lat, 5), lon=round(z.lon, 5), edificios_danados=z.n, num=k + 1, sensor=r.sensor,
                                  id=r.id, fecha=r.fecha, fase=r.fase, nubes_catalogo=r.nubes_catalogo, fuera_nadir=r.fuera_nadir,
                                  sol_elev=r.sol_elev, gsd_m=r.gsd_m, valido_pct=round(val * 100), nube_medida_pct=round(nub * 100, 1) if nub == nub else np.nan,
                                  sombra_medida_pct=round(som * 100, 1) if som == som else np.nan, url=r.url))
        fig.suptitle(f"{z.zona} · {z.n} edificios dañados / damaged buildings · {z.lat:.4f}, {z.lon:.4f} · {LADO:.0f} m", fontsize=6.5, x=0.01, ha="left")
        fig.subplots_adjust(left=0.01, right=0.99, top=0.9, bottom=0.01, wspace=0.05, hspace=0.35)
        exportar(fig, f"exploracion_{z.zona}_{idioma}", FIG, formatos=("png",))
        plt.close(fig)

D = pd.DataFrame(filas)
if len(D):
    pena = D.nube_medida_pct.fillna(50) + 0.5 * D.sombra_medida_pct.fillna(50) + 0.3 * D.fuera_nadir.fillna(30) - 0.2 * D.sol_elev.fillna(40) \
        + (100 - D.valido_pct)
    D["puntaje"] = pena.round(1)                                         # menor = mejor / lower = better
    D["sugerido"] = ""
    for (zn, fs), g in D.groupby(["zona", "fase"]):
        D.loc[g.puntaje.idxmin(), "sugerido"] = "si"
    D["usar"] = ""
    ruta = f"{DOC}/seleccion_optico.csv"
    if os.path.exists(ruta):                                              # conservar lo que ya decidió el autor
        prev = pd.read_csv(ruta, dtype=str)
        if "usar" in prev:
            D = D.drop(columns="usar").merge(prev[["zona", "id", "usar"]], on=["zona", "id"], how="left")
            D["usar"] = D["usar"].fillna("")
    D.to_csv(ruta, index=False)
    pd.set_option("display.width", 220)
    print("\n=== CANDIDATAS (sugerido = mejor según nubes, sombra, sol y nadir) ===")
    print(D[["zona", "num", "fase", "sensor", "fecha", "nube_medida_pct", "sombra_medida_pct", "fuera_nadir", "sol_elev", "sugerido", "usar"]].to_string(index=False))
    print(f"\n👉 Revise las hojas en {FIG}/exploracion_Z*_es.png y marque `usar = si` en {ruta}")
    print("   (una escena ANTES y una DESPUÉS por zona). Luego ejecute de nuevo este paso para comprobar la selección.")
    elegidas = D[D.usar.astype(str).str.lower().isin(["si", "sí", "yes", "x", "1"])]
    print(f"   Elegidas por el autor hasta ahora / chosen so far: {len(elegidas)}")
