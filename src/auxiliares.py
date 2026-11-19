# -*- coding: utf-8 -*-
"""Datos auxiliares: réplicas USGS y ESA WorldCover / Ancillary data: USGS aftershocks and ESA WorldCover."""
import os
RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
os.makedirs(f"{RAIZ}/05_documentacion", exist_ok=True)
import requests, os
AUX = f"{RAIZ}/01_datos_crudos/auxiliares"; os.makedirs(AUX, exist_ok=True)

# 1) Réplicas: catálogo USGS ComCat (M>=2.5, desde el sismo hasta hoy)
url = ("https://earthquake.usgs.gov/fdsnws/event/1/query?format=csv&starttime=2026-06-24"
       "&minlatitude=9.8&maxlatitude=11.2&minlongitude=-69.2&maxlongitude=-65.8&minmagnitude=2.5")
open(f"{AUX}/usgs_replicas_2026.csv", "wb").write(requests.get(url, timeout=120).content)
print("Réplicas USGS guardadas")

# 2) Cobertura del suelo ESA WorldCover 2021 (10 m) – tesela N09W069 cubre Yumare..Guatire
wc = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N09W069_Map.tif"
dst = f"{AUX}/ESA_WorldCover_10m_2021_N09W069.tif"
if not os.path.exists(dst):
    with requests.get(wc, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dst, "wb") as f:
            for ch in r.iter_content(1 << 20): f.write(ch)
print("WorldCover guardado")

# 3) Descarga manual (citar con fecha de acceso en Data and Resources):
#    - Copernicus EMS EMSR884 (mapas de daño): https://mapping.emergency.copernicus.eu/activations/EMSR884/
#    - Desplazamientos GNSS cosísmicos del Nevada Geodetic Laboratory: https://geodesy.unr.edu/
#    - Modelo de falla finita y trazas: páginas USGS us6000t7zc y us6000t7zp
#    - LOS ALOS-2 / NISAR procesados por Scripps/UCSD: https://topex.ucsd.edu/VNZ_7.5/
