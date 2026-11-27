# -*- coding: utf-8 -*-
"""
PARES PRE-SÍSMICOS (control) para medir el daño como PÉRDIDA DE COHERENCIA en banda C y banda L
Pre-seismic pairs (control) to map damage as COHERENCE LOSS in C- and L-band
================================================================================================
Idea: un edificio dañado deja de ser coherente entre una imagen antes y una después del sismo. Para separar ese efecto de la
decorrelación normal (vegetación, tiempo), se compara la coherencia de un par PRE-sísmico (ambas imágenes antes) con la del par
COSÍSMICO de la MISMA geometría: ΔCOH = coh_pre − coh_co (lo calcula `danio_coherencia.py`).

1) Sentinel-1 (C): por cada track que cubre La Guaira toma las DOS últimas escenas antes del sismo (misma órbita y frame) y, solo si
   CONFIRMAR=True y el par no existe ya (en Drive o en HyP3, `registro_datos.decidir_envio`), lo envía a HyP3 (INSAR_GAMMA, 10x2,
   look vectors, DEM). Costo: 15 créditos por par. Luego `hyp3_estado` lo descarga; `s1_tif` lo manda a 02_procesados/sentinel1_pre.
2) NISAR (L): del inventario `nisar_productos.csv` (paso inv_nisar) toma los GUNW PRE-sísmicos de los mismos tracks cosísmicos que cubren
   La Guaira, los descarga (sin costo, Earthdata) a 01_datos_crudos/nisar_gunw_pre y los convierte a 02_procesados/nisar_pre.
Los productos pre-sísmicos van a carpetas APARTE: no entran en mosaicos ni mapas de desplazamiento.
Variables: CONFIRMAR (False), TRACKS_S1 (None = todos los que cubren), N_PRE_NISAR (1 por track y frame).
"""
import glob
import os
import runpy
import sys as _sys

import pandas as pd
from shapely.geometry import box, shape

_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import csv_bilingue

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
TRAB = globals().get("TRABAJO", os.path.join(os.path.dirname(RAIZ), "inventario_2026"))
CONFIRMAR = bool(globals().get("CONFIRMAR", False))
TRACKS_S1 = globals().get("TRACKS_S1", None)
N_PRE = int(globals().get("N_PRE_NISAR", 1))
SISMO = pd.Timestamp("2026-06-24T22:04:33Z")
ROI = box(-67.3, 10.4, -66.7, 10.8)
S1_ZIP = f"{RAIZ}/01_datos_crudos/sentinel1_hyp3"
NIS_PRE = f"{RAIZ}/01_datos_crudos/nisar_gunw_pre"
os.makedirs(NIS_PRE, exist_ok=True)
DOC = f"{RAIZ}/05_documentacion"
import asf_search as asf

# ------------------------------------------------------------------ 1) Sentinel-1: par pre-sísmico por track
res = asf.geo_search(platform=[asf.PLATFORM.SENTINEL1], intersectsWith=ROI.wkt, start="2026-05-20", end="2026-06-24T22:00:00Z",
                     processingLevel=asf.PRODUCT_TYPE.SLC)
s1 = pd.DataFrame([dict(escena=r.properties["sceneName"], fecha=pd.Timestamp(r.properties["startTime"]), track=int(r.properties["pathNumber"]),
                        dir=r.properties["flightDirection"], geom=shape(r.geometry)) for r in res])
pares = []
if len(s1):
    s1["cubre_%"] = s1.geom.map(lambda g: round(g.intersection(ROI).area / ROI.area * 100, 1))
    for (t, d), g in s1[s1["cubre_%"] > 20].groupby(["track", "dir"]):
        if TRACKS_S1 and t not in TRACKS_S1:
            continue
        g = g[g.fecha < SISMO].sort_values("fecha")
        if len(g) < 2:
            continue
        b = g.iloc[-1]                                        # última escena antes del sismo
        a = g[(g.fecha < b.fecha - pd.Timedelta(days=3)) & g.geom.map(lambda x: x.intersection(b.geom).area / b.geom.area > 0.5)]
        if a.empty:
            continue
        a = a.iloc[-1]
        pares.append(dict(track=f"{t:03d}{d[0]}", ref=a.escena, sec=b.escena, fecha_ref=a.fecha.date(), fecha_sec=b.fecha.date(),
                          dias=round((b.fecha - a.fecha).total_seconds() / 86400), cubre_LaGuaira=min(a["cubre_%"], b["cubre_%"])))
P_S1 = pd.DataFrame(pares)
print("=== Sentinel-1: pares PRE-sísmicos candidatos / pre-seismic candidate pairs ===")
print(P_S1.to_string(index=False) if len(P_S1) else "(ninguno / none)")
if len(P_S1):
    csv_bilingue(P_S1, f"{DOC}/s1_pares_presismicos.csv")
    import hyp3_sdk
    from registro_datos import trabajos_por_par, decidir_envio
    try:
        from google.colab import userdata
        hyp3 = hyp3_sdk.HyP3(username=userdata.get("EARTHDATA_USER"), password=userdata.get("EARTHDATA_PASS"))
    except Exception:
        hyp3 = hyp3_sdk.HyP3()
    print(f"\nCréditos HyP3 restantes / remaining credits: {hyp3.check_credits()} · costo por par / cost per pair (10x2): 15")
    existentes = trabajos_por_par(hyp3)
    for p in P_S1.itertuples():
        nombre = f"S1_{p.track}_presismico"
        accion, job, motivo = decidir_envio(existentes, p.ref, p.sec, S1_ZIP)
        if accion != "enviar":
            print(f"   {nombre}: NO se envía / not submitted → {motivo}")
        elif not CONFIRMAR:
            print(f"   {nombre}: listo para enviar ({p.fecha_ref}→{p.fecha_sec}); repita con CONFIRMAR=True / ready, re-run with CONFIRMAR=True")
        else:
            hyp3.submit_insar_job(p.ref, p.sec, name=nombre, looks="10x2", include_inc_map=True, include_dem=True, include_look_vectors=True)
            print(f"   {nombre}: ENVIADO / SUBMITTED ({p.fecha_ref}→{p.fecha_sec}). Descárguelo luego con `hyp3_estado` (~40 min).")

# ------------------------------------------------------------------ 2) NISAR: GUNW pre-sísmicos de los mismos tracks
inv = None
for r in (f"{TRAB}/nisar_filtrado/nisar_productos.csv", "./nisar_filtrado/nisar_productos.csv"):
    if os.path.exists(r):
        inv = pd.read_csv(r); break
if inv is None:
    print("\n[!] Falta nisar_productos.csv: ejecute P('inv_nisar', forzar=True) / run inv_nisar first")
else:
    inv = inv[(inv.nivel == "GUNW") & (inv.tipo.astype(str).str.upper().str.startswith("PRE")) & (inv["cubre_LaGuaira_%"] > 0)]
    co_tracks = {os.path.basename(f).split("_")[1][1:] for f in glob.glob(f"{RAIZ}/02_procesados/nisar/NISAR_T*_los_m.tif")}
    if co_tracks:
        inv = inv[inv.track.isin(co_tracks)]
    inv = inv.sort_values("fecha_sec").groupby(["track", "frame"]).tail(N_PRE)
    print("\n=== NISAR: GUNW PRE-sísmicos elegidos / chosen pre-seismic GUNW ===")
    print(inv[["nombre", "track", "frame", "fecha_ref", "fecha_sec", "cubre_LaGuaira_%", "MB"]].to_string(index=False) if len(inv) else "(ninguno / none)")
    faltan = [u for u, n in zip(inv.url, inv.nombre) if isinstance(u, str) and not os.path.exists(f"{NIS_PRE}/{os.path.basename(u)}")]
    if faltan:
        ses = globals().get("session")
        if ses is None:
            print("[!] Sin sesión Earthdata: ejecute la celda de credenciales (#2) / run the credentials cell")
        else:
            print(f"   descargando / downloading {len(faltan)} GUNW (~2,3 GB c/u)…")
            asf.download_urls(urls=faltan, path=NIS_PRE, session=ses, processes=2)
    if glob.glob(f"{NIS_PRE}/*GUNW*.h5"):
        runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."),
                                    "nisar_gunw_a_geotiff.py"),
                       init_globals={"NISAR_ENTRADA": NIS_PRE, "NISAR_SALIDA": f"{RAIZ}/02_procesados/nisar_pre"})
        print(f"✓ NISAR pre-sísmico convertido / converted → {RAIZ}/02_procesados/nisar_pre")
