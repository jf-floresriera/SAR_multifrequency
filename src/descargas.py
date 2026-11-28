# -*- coding: utf-8 -*-
"""
Descarga a Drive: NISAR (GUNW cosísmicos), Umbra (GEC) y Sentinel-1 HyP3. Se puede volver a correr.
Download to Drive: NISAR (coseismic GUNW), Umbra (GEC) and Sentinel-1 HyP3. Safe to re-run.
Usar con %run -i (necesita `session`, `usuario`, `clave`). ESPERAR_HYP3 = False para no bloquear.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import T, csv_bilingue, guardar_bilingue
import os, shutil
from datetime import date
import asf_search as asf
import boto3
import pandas as pd
from botocore import UNSIGNED
from botocore.config import Config

ESPERAR_HYP3 = globals().get("ESPERAR_HYP3", True)
BASE = "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR/01_datos_crudos"
DOC = "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR/05_documentacion"
for d in ["sentinel1_hyp3", "nisar_gunw", "umbra_gec", "auxiliares"]:
    os.makedirs(f"{BASE}/{d}", exist_ok=True)
os.makedirs(DOC, exist_ok=True)
registro = []

nz = pd.read_csv("nisar_filtrado/nisar_productos.csv")
cos = nz[(nz.nivel == "GUNW") & (nz.tipo == "COSISMICO")]
if os.path.isdir("./datos_nisar_vargas"):
    for f in os.listdir("./datos_nisar_vargas"):
        if f.endswith(".h5") and not os.path.exists(f"{BASE}/nisar_gunw/{f}"):
            shutil.copy(f"./datos_nisar_vargas/{f}", f"{BASE}/nisar_gunw/{f}")
pend = [u for u in cos.url if not os.path.exists(f"{BASE}/nisar_gunw/{os.path.basename(u)}")]
print(f"NISAR: {len(cos)} cosísmicos / coseismic, faltan / missing {len(pend)}")
if pend:
    asf.download_urls(urls=pend, path=f"{BASE}/nisar_gunw", session=session, processes=3)
registro += [("NISAR GUNW (ASF DAAC)", n) for n in cos.nombre]

s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED), region_name="us-west-2")
lst = pd.read_csv("umbra_inventario/umbra_listado_completo.csv")
gec = lst[lst.key.str.contains("GEC", case=False) & lst.key.str.lower().str.endswith((".tif", ".tiff"))]
print(f"Umbra: {len(gec)} GEC, {gec.bytes.sum()/1e9:.2f} GB")
for k in gec.key:
    dst = f"{BASE}/umbra_gec/{os.path.basename(k)}"
    if not os.path.exists(dst):
        s3.download_file("umbra-open-data-catalog", k, dst)
registro += [("Umbra GEC (s3://umbra-open-data-catalog)", os.path.basename(k)) for k in gec.key]

import hyp3_sdk
hyp3 = hyp3_sdk.HyP3(username=usuario, password=clave)
for nombre in ["S1_025D_cosismico", "S1_033A_cosismico"]:
    jobs = hyp3.find_jobs(name=nombre)
    if len(jobs) == 0:
        print(f"[!] No existe / does not exist: {nombre}"); continue
    if ESPERAR_HYP3:
        jobs = hyp3.watch(jobs)
    ok = jobs.filter_jobs(succeeded=True, running=False, failed=False)
    if len(ok):
        import re as _re
        _d = f"{BASE}/sentinel1_hyp3"
        _hay = set(os.listdir(_d)) | (set(os.listdir(f"{_d}/_duplicados")) if os.path.isdir(f"{_d}/_duplicados") else set())
        _claves = {_re.sub(r"_[0-9A-Fa-f]{4}\.zip$", "", j.files[0]["filename"]) for j in ok if j.files}
        if all(any(f.startswith(c) for f in _hay) for c in _claves):
            # mismo par de escenas + resolución ya en Drive (o en _duplicados): no se vuelve a bajar (el 025D se envió 4 veces)
            print(f"   {nombre}: ya en Drive / already on Drive ({len(ok)} trabajo(s) del mismo par: no se redescarga)")
        else:
            list(ok)[-1].download_files(_d)          # un solo trabajo por par / a single job per pair
        registro.append(("Sentinel-1 HyP3 INSAR_GAMMA (ASF)", nombre))
    else:
        print(f"   {nombre}: aún no terminado / not finished yet -> {jobs}")

csv_bilingue(pd.DataFrame(registro, columns=["fuente", "producto"]).assign(fecha_acceso=date.today().isoformat()),
             f"{DOC}/registro_descargas.csv")
print("Listo / Done -> 05_documentacion/registro_descargas.csv")
