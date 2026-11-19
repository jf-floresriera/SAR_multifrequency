# -*- coding: utf-8 -*-
"""
Inventario multisensor reproducible – Sismo de Venezuela (Mw 7.2 + 7.5, 24/06/2026)
====================================================================================
Une en UNA tabla todos los datos libres del proyecto:
  Sentinel-1 (C)  -> búsqueda ASF (SLC)          + su par procesado en HyP3
  NISAR-L (L)     -> búsqueda ASF (GUNW)         (o ./nisar_filtrado/nisar_productos.csv)
  Umbra (X)       -> ./umbra_inventario/umbra_inventario.csv (de umbra_inventario.py)
  Planet (óptico) -> catálogo STAC-GeoParquet público en source.coop
  NISAR-S (S)     -> NO está en ASF: se agrega a mano desde Bhoonidhi (ver abajo)

Salidas (./inventario/):
  inventario_multisensor.csv     -> tabla maestra (una fila por escena / par)
  resumen_sensores.csv           -> conteos por sensor, banda, pre/post
  fig_linea_tiempo_sensores.png  -> figura para el artículo (300 dpi) + .pdf vectorial

Uso en Colab (con `session` de asf ya autenticada, como en el notebook):
  !pip install -q asf_search duckdb pandas matplotlib
  %run inventario_multisensor.py
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import T, csv_bilingue, guardar_bilingue
import os

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

SALIDA = "./inventario"
os.makedirs(SALIDA, exist_ok=True)

SISMO = pd.Timestamp("2026-06-24T22:04:33Z")
ROI_WKT = "POLYGON((-68.6 10.0, -66.4 10.0, -66.4 11.0, -68.6 11.0, -68.6 10.0))"  # zona de ruptura
INI, FIN = "2026-06-01", "2026-07-31"

# Par Sentinel-1 ya procesado por usted en HyP3 (del notebook)
S1_PAR_PROCESADO = ("S1A_IW_SLC__1SDV_20260618T224250_20260618T224320_065030_083236_48BF",
                    "S1D_IW_SLC__1SDV_20260625T224209_20260625T224239_003399_005FB5_8B0A")

PLANET_PARQUET = ("https://data.source.coop/planet/disasterdata/"
                  "venezuela-earthquake-2026-06-24/{col}/items.parquet")

COLUMNAS = ["sensor", "banda", "lambda_cm", "tipo_producto", "id", "fecha", "fecha_sec",
            "relacion_sismo", "track_o_sitio", "direccion", "resolucion_m", "licencia",
            "fuente", "usado_en_notebook"]
filas = []


def rel(fecha, fecha_sec=None):
    """PRE / POST / COSISMICO respecto al sismo."""
    if fecha_sec is not None and pd.notna(fecha_sec):
        if fecha < SISMO < fecha_sec:
            return "COSISMICO"
        return "PRE" if fecha_sec < SISMO else "POST"
    return "PRE" if fecha < SISMO else "POST"


# ---------------------------------------------------------------------------
# 1. Sentinel-1 (banda C)
# ---------------------------------------------------------------------------
try:
    import asf_search as asf
    res = asf.geo_search(platform=[asf.PLATFORM.SENTINEL1], intersectsWith=ROI_WKT,
                         start=INI, end=FIN, processingLevel=asf.PRODUCT_TYPE.SLC)
    for r in res:
        p = r.properties
        f = pd.Timestamp(p["startTime"])
        filas.append(dict(
            sensor=p.get("platform", "Sentinel-1"), banda="C", lambda_cm=5.55,
            tipo_producto="SLC", id=p["sceneName"], fecha=f, fecha_sec=pd.NaT,
            relacion_sismo=rel(f), track_o_sitio=f"T{int(p['pathNumber']):03d}",
            direccion=p.get("flightDirection"), resolucion_m=20,
            licencia="Copernicus (libre)", fuente="ASF",
            usado_en_notebook=p["sceneName"] in S1_PAR_PROCESADO))
    print(f"Sentinel-1: {len(res)} escenas SLC")
except Exception as e:
    print(f"[!] Sentinel-1 omitido: {e}")

# Par interferométrico procesado (HyP3, 80 m)
ref = pd.Timestamp("2026-06-18T22:42:50Z")
sec = pd.Timestamp("2026-06-25T22:42:09Z")
filas.append(dict(sensor="Sentinel-1 (par HyP3)", banda="C", lambda_cm=5.55,
                  tipo_producto="INSAR_GAMMA (unw, corr, dem, inc)",
                  id="Sismo_LaGuaira_S1_Path33", fecha=ref, fecha_sec=sec,
                  relacion_sismo=rel(ref, sec), track_o_sitio="T033", direccion="ASCENDING",
                  resolucion_m=80, licencia="Copernicus (libre)", fuente="ASF HyP3",
                  usado_en_notebook=True))

# ---------------------------------------------------------------------------
# 2. NISAR banda L (GUNW)
# ---------------------------------------------------------------------------
csv_nisar = "./nisar_filtrado/nisar_productos.csv"
if os.path.exists(csv_nisar):
    nz = pd.read_csv(csv_nisar, parse_dates=["fecha_ref", "fecha_sec"])
    nz = nz[nz.nivel == "GUNW"]
    descargados = set(os.listdir("./datos_nisar_vargas")) if os.path.isdir("./datos_nisar_vargas") else set()
    for _, r in nz.iterrows():
        filas.append(dict(
            sensor="NISAR-L", banda="L", lambda_cm=23.84, tipo_producto="GUNW (HH)",
            id=r.nombre, fecha=r.fecha_ref, fecha_sec=r.fecha_sec,
            relacion_sismo=rel(r.fecha_ref, r.fecha_sec), track_o_sitio=f"T{r.track}",
            direccion=r.direccion, resolucion_m=80, licencia="NASA (libre)", fuente="ASF",
            usado_en_notebook=any(str(r.nombre) in d for d in descargados)))
    print(f"NISAR-L: {len(nz)} GUNW (desde {csv_nisar})")
else:
    print("[!] NISAR-L: ejecute primero nisar_filtrar.py para clasificar los GUNW.")

# ---------------------------------------------------------------------------
# 3. NISAR banda S (manual, Bhoonidhi)
# ---------------------------------------------------------------------------
# Si encuentra escenas en https://bhoonidhi.nrsc.gov.in, agréguelas aquí:
NISAR_S = [
    # ("NISAR_S2_PR_GCOV_...", "2026-07-xxTxx:xx:xxZ", "TxxxA"),
]
for nombre, fecha, track in NISAR_S:
    f = pd.Timestamp(fecha)
    filas.append(dict(sensor="NISAR-S", banda="S", lambda_cm=9.4, tipo_producto="GCOV/GSLC",
                      id=nombre, fecha=f, fecha_sec=pd.NaT, relacion_sismo=rel(f),
                      track_o_sitio=track, direccion=None, resolucion_m=None,
                      licencia="ISRO (registro)", fuente="Bhoonidhi", usado_en_notebook=False))

# ---------------------------------------------------------------------------
# 4. Umbra banda X
# ---------------------------------------------------------------------------
csv_umbra = "./umbra_inventario/umbra_inventario.csv"
if os.path.exists(csv_umbra):
    um = pd.read_csv(csv_umbra, parse_dates=["inicio_utc"])
    for _, r in um.iterrows():
        filas.append(dict(
            sensor=f"Umbra ({r.satelite})" if pd.notna(r.satelite) else "Umbra",
            banda="X", lambda_cm=3.1, tipo_producto=r.productos, id=r.task_id,
            fecha=r.inicio_utc, fecha_sec=pd.NaT, relacion_sismo=rel(r.inicio_utc),
            track_o_sitio=f"{r.lat_centro:.3f},{r.lon_centro:.3f}" if pd.notna(r.lat_centro) else None,
            direccion=r.direccion_mirada, resolucion_m=r.res_rango_m,
            licencia="CC BY 4.0", fuente="Umbra Open Data (AWS)", usado_en_notebook=False))
    print(f"Umbra: {len(um)} adquisiciones")
else:
    print("[!] Umbra: ejecute primero umbra_inventario.py")

# ---------------------------------------------------------------------------
# 5. Planet (óptico) – STAC-GeoParquet en source.coop
# ---------------------------------------------------------------------------
try:
    import duckdb
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    for col in ["post-event", "pre-event"]:
        df = con.execute(f"SELECT * FROM read_parquet('{PLANET_PARQUET.format(col=col)}')").df()
        # El índice puede traer las propiedades como columnas o dentro de 'properties'
        if "properties" in df.columns:
            df = pd.concat([df.drop(columns="properties"),
                            pd.json_normalize(df["properties"])], axis=1)
        for _, r in df.iterrows():
            f = pd.Timestamp(r.get("datetime") or r.get("start_datetime"))
            if f.tzinfo is None:
                f = f.tz_localize("UTC")
            filas.append(dict(
                sensor=f"Planet {r.get('constellation') or ('PlanetScope mosaico' if col == 'pre-event' else '')}".strip(),
                banda="Óptico", lambda_cm=None,
                tipo_producto="visual/analytic/udm2" if col == "post-event" else "mosaico trimestral RGB",
                id=r.get("id"), fecha=f, fecha_sec=pd.NaT,
                relacion_sismo="PRE" if col == "pre-event" else rel(f),
                track_o_sitio=r.get("location") or r.get("location_slug") or r.get("collection"),
                direccion=None, resolucion_m=r.get("gsd"),
                licencia="CC BY-NC 4.0 (no comercial)", fuente="Planet Crisis Response / source.coop",
                usado_en_notebook=False))
        print(f"Planet {col}: {len(df)} ítems")
except Exception as e:
    print(f"[!] Planet omitido: {e}")

# ---------------------------------------------------------------------------
# 6. Tabla maestra y resumen
# ---------------------------------------------------------------------------
inv = pd.DataFrame(filas, columns=COLUMNAS)
for c in ["fecha", "fecha_sec"]:
    inv[c] = pd.to_datetime(inv[c], utc=True, errors="coerce")
inv["dias_desde_sismo"] = ((inv.fecha - SISMO).dt.total_seconds() / 86400).round(2)
inv = inv.sort_values(["banda", "sensor", "fecha"]).reset_index(drop=True)
csv_bilingue(inv, f"{SALIDA}/inventario_multisensor.csv")

resumen = (inv.assign(familia=inv.sensor.str.replace(r"^Sentinel-1\w?", "Sentinel-1", regex=True).str.split(" ").str[0])
           .pivot_table(index=["familia", "banda"], columns="relacion_sismo",
                        values="id", aggfunc="count", fill_value=0))
csv_bilingue(resumen, f"{SALIDA}/resumen_sensores.csv", index=True)
print("\n=== RESUMEN ===")
print(resumen.to_string())

# ---------------------------------------------------------------------------
# 7. Figura: línea de tiempo de adquisiciones por sensor (para el artículo)
# ---------------------------------------------------------------------------
orden = ["Umbra", "Sentinel-1", "NISAR-S", "NISAR-L", "ALOS-2", "Planet"]
color = {"X": "#4C72B0", "C": "#DD8452", "S": "#8172B3", "L": "#55A868", "Óptico": "#937860"}
inv["familia"] = inv.sensor.str.split(" ").str[0].replace({"Sentinel-1A": "Sentinel-1",
                                                           "Sentinel-1C": "Sentinel-1",
                                                           "Sentinel-1D": "Sentinel-1"})
familias = [f for f in orden if f in set(inv.familia)]
ypos = {f: i for i, f in enumerate(familias)}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
ventana = inv[(inv.fecha > SISMO - pd.Timedelta(days=30)) & (inv.fecha < SISMO + pd.Timedelta(days=30))]


def _linea(idioma):
    fig, ax = plt.subplots(figsize=(10, 0.7 * len(familias) + 1.6))
    for _, r in ventana.iterrows():
        y = ypos[r.familia]
        c = color.get(r.banda, "k")
        if pd.notna(r.fecha_sec):
            ax.plot([r.fecha, r.fecha_sec], [y + 0.18, y + 0.18], color=c, lw=2.2, alpha=0.8,
                    solid_capstyle="round")
        else:
            ax.plot(r.fecha, y, "o", ms=6, mfc=c, mec="white", mew=0.6, alpha=0.9)
    ax.axvline(SISMO, color="#C44E52", lw=1.5, ls="--")
    ax.text(SISMO, len(familias) - 0.4, "  " + T("sismo", idioma).replace("\n", "\n  "), color="#C44E52",
            va="top", fontsize=9)
    ax.set_yticks(range(len(familias)))
    banda_en = {"Óptico": "Optical"}
    ax.set_yticklabels([f"{f}  ({(banda_en.get(b, b) if idioma == 'en' else b)})" for f, b in
                        ((f, ventana[ventana.familia == f].banda.iloc[0] if (ventana.familia == f).any() else "")
                         for f in familias)])
    ax.set_ylim(-0.6, len(familias) - 0.3)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.grid(axis="x", color="0.9")
    for sp in ["top", "right", "left"]:
        ax.spines[sp].set_visible(False)
    ax.set_title(T("linea_tit", idioma), fontsize=11, loc="left")
    fig.tight_layout()
    return fig


print(guardar_bilingue(_linea, f"{SALIDA}/fig_linea_tiempo_sensores", formatos=("png", "pdf")))
print(f"\nTablas y figuras (ES/EN) en / tables and figures (ES/EN) in {SALIDA}/")
