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
    existentes = set(os.listdir(DESTINO))
    for j in listos:
        zipname = j.files[0]["filename"] if j.files else None
        if zipname and (zipname in existentes or zipname.replace(".zip", "") in existentes):
            print(f"   ya descargado / already downloaded: {j.name} ({zipname})")
            continue
        j.download_files(DESTINO)
        print(f"   ✓ descargado / downloaded: {j.name} ({zipname})")
    print(f"\nProductos en / products in: {DESTINO}")
    print("⚠️  HyP3 borra los productos ~14 días después / HyP3 deletes products after ~14 days (ver columna 'expira').")
