# -*- coding: utf-8 -*-
"""
DESCARGA COMPLETA del óptico abierto del evento (Vantor y Planet) a Google Drive, con TODOS sus archivos/bandas
Full download of the event's open optical data (Vantor and Planet) to Google Drive, all assets/bands
=====================================================================================================
Hasta ahora el flujo solo LEÍA ventanas por internet (COG); en Drive no había ninguna imagen óptica completa.
Este script baja, para cada escena que toca la zona de estudio, TODOS los activos GeoTIFF de su ficha STAC
(Vantor: visual RGB y, si existen, multiespectral y pancromática; Planet: los que traiga cada ítem) a:
    01_datos_crudos/vantor/<fase>_<fecha>_<id>/<activo>.tif   (+ item.json)
    01_datos_crudos/planet/<fecha>_<id>/<activo>.tif           (+ item.json)
y escribe 05_documentacion/inventario_optico_descargado.csv (ES) y _en.csv.

Uso en Colab (después de la celda 0) / usage:
    correr("descargar_opticos.py")                       # 1) SOLO lista y suma tamaños (no baja nada)
    DESCARGAR = True; correr("descargar_opticos.py")     # 2) baja lo que falte (se puede cortar y repetir: reanuda)
Variables: DESCARGAR (False) · FUENTES (("vantor", "planet")) · ROI_BBOX ((-67.3, 10.4, -66.7, 10.8)) · MAX_GB (300)
Licencia: Vantor y Planet CC BY-NC 4.0 → quedan SOLO en Drive; NUNCA subir a GitHub ni a Zenodo.
"""
import io
import json
import os

import pandas as pd
import requests

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
TRAB = globals().get("TRABAJO", os.path.join(os.path.dirname(RAIZ), "inventario_2026"))
DESCARGAR = bool(globals().get("DESCARGAR", False))
FUENTES = tuple(globals().get("FUENTES", ("vantor", "planet")))
ROI_BBOX = tuple(globals().get("ROI_BBOX", (-67.3, 10.4, -66.7, 10.8)))      # lon0, lat0, lon1, lat1 (La Guaira y Caracas)
MAX_GB = float(globals().get("MAX_GB", 300))
VANTOR = "https://vantor-opendata.s3.amazonaws.com/events/Venezuela-Earthquake-Jun-2026/"
PLANET = "https://data.source.coop/planet/disasterdata/venezuela-earthquake-2026-06-24"
DOC = f"{RAIZ}/05_documentacion"
EXT = (".tif", ".tiff", ".TIF", ".TIFF")


def _toca(b):
    x0, y0, x1, y1 = ROI_BBOX
    return not (b[2] < x0 or b[0] > x1 or b[3] < y0 or b[1] > y1)


def _abs(href, base):
    return href if href.startswith("http") else requests.compat.urljoin(base, href)


def _tam(url):
    try:
        r = requests.head(url, timeout=60, allow_redirects=True)
        return int(r.headers.get("Content-Length", 0))
    except Exception:
        return 0


def _bajar(url, destino):
    """Descarga por partes con reanudación (Range) / chunked download with resume."""
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    total = _tam(url)
    if os.path.exists(destino) and total and os.path.getsize(destino) == total:
        return "ya estaba / already there"
    tmp = destino + ".parcial"
    hecho = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    cab = {"Range": f"bytes={hecho}-"} if hecho else {}
    with requests.get(url, headers=cab, stream=True, timeout=600) as r:
        r.raise_for_status()
        modo = "ab" if hecho and r.status_code == 206 else "wb"
        with open(tmp, modo) as f:
            for trozo in r.iter_content(chunk_size=16 * 1024 * 1024):
                f.write(trozo)
    if total and os.path.getsize(tmp) != total:
        return f"INCOMPLETO / incomplete ({os.path.getsize(tmp)}/{total} B): repita / re-run"
    os.replace(tmp, destino)
    return "descargado / downloaded"


filas = []
# ------------------------------------------------------------------ Vantor (STAC estático del evento)
if "vantor" in FUENTES:
    cache = f"{TRAB}/vantor/vantor_items.json"
    if os.path.exists(cache):
        items = json.load(open(cache))
    else:
        col = requests.get(VANTOR + "collection.json", timeout=60).json()
        items = [requests.get(_abs(l["href"], VANTOR), timeout=60).json() for l in col["links"] if l["rel"] == "item"]
    for j in items:
        if not _toca(j["bbox"]):
            continue
        p = j.get("properties", {})
        carpeta = f"{RAIZ}/01_datos_crudos/vantor/{p.get('phase', 'na')}_{p.get('datetime', '')[:10]}_{j['id']}"
        base = next((l["href"] for l in j.get("links", []) if l.get("rel") == "self"), VANTOR)
        for k, a in j.get("assets", {}).items():
            href = _abs(a.get("href", ""), base)
            if href.split("?")[0].endswith(EXT):
                filas.append(dict(fuente="Vantor", id=j["id"], fase=p.get("phase"), fecha=p.get("datetime", "")[:10],
                                  nubes_pct=p.get("eo:cloud_cover"), activo=k, bandas=len(a.get("eo:bands", []) or []) or None,
                                  url=href, destino=f"{carpeta}/{k}.tif", item=j, carpeta=carpeta))

# ------------------------------------------------------------------ Planet (source.coop, ítems en parquet)
if "planet" in FUENTES:
    try:
        import geopandas as gpd
        for fase in ("post-event", "pre-event"):
            try:
                pq = gpd.read_parquet(io.BytesIO(requests.get(f"{PLANET}/{fase}/items.parquet", timeout=180).content))
            except Exception as e:
                print(f"Planet {fase}: sin items.parquet ({str(e)[:60]})"); continue
            pq = pq.to_crs(4326)
            for r in pq.itertuples():
                if not _toca(r.geometry.bounds):
                    continue
                fecha = str(getattr(r, "datetime", ""))[:10]
                carpeta = f"{RAIZ}/01_datos_crudos/planet/{fase}_{fecha}_{r.id}"
                assets = getattr(r, "assets", None)
                assets = json.loads(assets) if isinstance(assets, str) else (assets or {})
                for k, a in (assets.items() if isinstance(assets, dict) else []):
                    href = (a or {}).get("href", "") if isinstance(a, dict) else ""
                    if href and href.split("?")[0].endswith(EXT):
                        href = _abs(href, f"{PLANET}/{fase}/")
                        filas.append(dict(fuente="Planet", id=r.id, fase=fase, fecha=fecha, nubes_pct=getattr(r, "eo:cloud_cover", None),
                                          activo=k, bandas=None, url=href, destino=f"{carpeta}/{k}.tif", item=None, carpeta=carpeta))
        # respaldo: URLs ya resueltas por danio_sitios (una por ítem) / fallback: URLs resolved earlier
        f_urls = f"{TRAB}/umbra_planet_sitios/planet_urls.csv"
        if os.path.exists(f_urls) and not any(f["fuente"] == "Planet" for f in filas):
            for r in pd.read_csv(f_urls).dropna(subset=["url"]).itertuples():
                filas.append(dict(fuente="Planet", id=r.id, fase="post-event", fecha="", nubes_pct=None, activo="visual", bandas=None,
                                  url=r.url, destino=f"{RAIZ}/01_datos_crudos/planet/post-event_{r.id}/visual.tif", item=None,
                                  carpeta=f"{RAIZ}/01_datos_crudos/planet/post-event_{r.id}"))
    except ImportError:
        print("Falta geopandas / geopandas missing")

T = pd.DataFrame(filas)
if T.empty:
    print("No hay escenas ópticas en la zona / no optical scenes in the area")
    T = pd.DataFrame(columns=["fuente", "id", "fase", "fecha", "nubes_pct", "activo", "bandas", "url", "destino", "item", "carpeta"])
print(f"Calculando tamaños de {len(T)} archivos… / sizing files…")
T["GB"] = [round(_tam(u) / 1e9, 2) for u in T.url]
T["en_drive"] = [os.path.exists(d) and abs(os.path.getsize(d) / 1e9 - g) < 0.01 for d, g in zip(T.destino, T.GB)]
res = T.groupby(["fuente", "fase"]).agg(escenas=("id", "nunique"), archivos=("activo", "size"), GB=("GB", "sum"),
                                         ya_en_drive=("en_drive", "sum")).reset_index()
print(res.to_string(index=False))
falta = T[~T.en_drive]
print(f"\nTotal {T.GB.sum():.1f} GB · falta / missing {falta.GB.sum():.1f} GB ({len(falta)} archivos)")
print("Activos por fuente / assets per source:", T.groupby("fuente").activo.unique().map(list).to_dict())

if DESCARGAR and falta.GB.sum() > MAX_GB:
    print(f"🛑 Faltan {falta.GB.sum():.0f} GB > MAX_GB={MAX_GB:.0f}: suba MAX_GB o limite FUENTES/ROI_BBOX; no se baja nada")
elif DESCARGAR:
    for r in falta.itertuples():
        if r.item is not None:
            os.makedirs(r.carpeta, exist_ok=True)
            json.dump(r.item, open(f"{r.carpeta}/item.json", "w"), indent=1)
        try:
            print(f"   {r.fuente} {r.fecha} {r.id} · {r.activo} ({r.GB} GB): {_bajar(r.url, r.destino)}")
        except Exception as e:
            print(f"   ✗ {r.id} · {r.activo}: {str(e)[:100]} (repita la celda: reanuda / re-run resumes)")
    T["en_drive"] = [os.path.exists(d) for d in T.destino]
else:
    print("\nSolo inventario. Para bajar / to download:  DESCARGAR = True; correr(\"descargar_opticos.py\")")

os.makedirs(DOC, exist_ok=True)
sal = T.drop(columns=["item", "carpeta"])
sal.to_csv(f"{DOC}/inventario_optico_descargado.csv", index=False)
sal.rename(columns=dict(fuente="source", fase="phase", fecha="date", nubes_pct="cloud_pct", activo="asset", bandas="bands",
                        destino="path", en_drive="on_drive")).to_csv(f"{DOC}/inventario_optico_descargado_en.csv", index=False)
print(f"Inventario / inventory: {DOC}/inventario_optico_descargado.csv")
print("⚠️ CC BY-NC 4.0: no subir a GitHub ni a Zenodo / do not upload to GitHub or Zenodo")
