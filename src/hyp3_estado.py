# -*- coding: utf-8 -*-
"""
Estado de los trabajos HyP3 y descarga de los terminados / HyP3 job status and download of finished jobs.
Usar con %run -i (necesita `usuario` y `clave`).
"""
import os
from datetime import date

import hyp3_sdk
import pandas as pd

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import csv_bilingue

DESCARGAR = globals().get("DESCARGAR", True)
BASE = "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR"
DESTINO = f"{BASE}/01_datos_crudos/sentinel1_hyp3"
os.makedirs(DESTINO, exist_ok=True)

hyp3 = hyp3_sdk.HyP3(username=usuario, password=clave)
trabajos = hyp3.find_jobs()
filas = []
for j in trabajos:
    filas.append(dict(nombre=j.name, estado=j.status_code, tipo=j.job_type,
                      enviado=str(j.request_time)[:19], terminado=str(j.processing_times)[:40] if j.processing_times else "",
                      expira=str(j.expiration_time)[:10] if j.expiration_time else "",
                      escenas=", ".join(j.job_parameters.get("granules", [])) if j.job_parameters else ""))
tabla = pd.DataFrame(filas).sort_values("enviado", ascending=False)
print(tabla[["nombre", "estado", "enviado", "expira"]].to_string(index=False))
csv_bilingue(tabla, f"{BASE}/05_documentacion/hyp3_estado_{date.today()}")

print("\nSUCCEEDED = listo/ready · RUNNING = procesando/processing · PENDING = en cola/queued · FAILED = falló/failed")
if DESCARGAR:
    listos = trabajos.filter_jobs(succeeded=True, running=False, failed=False)
    # solo el trabajo MÁS RECIENTE de cada nombre / only the MOST RECENT job per name
    por_nombre = {}
    for j in sorted(listos, key=lambda j: j.request_time):
        por_nombre[j.name] = j
    existentes = set(os.listdir(DESTINO))
    for nombre, j in por_nombre.items():
        zipname = j.files[0]["filename"] if j.files else None
        if zipname and (zipname in existentes or zipname.replace(".zip", "") in existentes):
            print(f"   ya descargado / already downloaded: {nombre} ({zipname})")
            continue
        j.download_files(DESTINO)
        print(f"   ✓ descargado / downloaded: {nombre} ({zipname})")
    print(f"\nProductos en / products in: {DESTINO}")
    print("⚠️  HyP3 borra los productos ~14 días después / HyP3 deletes products after ~14 days (ver columna 'expira').")

# Mover duplicados (mismo par, distinto sufijo) a _duplicados / move duplicates to _duplicados
import re, shutil
grupos = {}
for f in sorted(os.listdir(DESTINO)):
    if f.endswith(".zip"):
        grupos.setdefault(re.sub(r"_[0-9A-F]{4}\.zip$", "", f), []).append(f)
dup = {k: v for k, v in grupos.items() if len(v) > 1}
if dup:
    os.makedirs(f"{DESTINO}/_duplicados", exist_ok=True)
    for k, v in dup.items():
        for f in v[1:]:
            shutil.move(f"{DESTINO}/{f}", f"{DESTINO}/_duplicados/{f}")
            if os.path.isdir(f"{DESTINO}/{f[:-4]}"):
                shutil.move(f"{DESTINO}/{f[:-4]}", f"{DESTINO}/_duplicados/{f[:-4]}")
        print(f"   duplicados movidos / duplicates moved: {k} -> se conserva / kept {v[0]}")
    print(f"   Puede borrar / you may delete: {DESTINO}/_duplicados")
