# -*- coding: utf-8 -*-
"""Prepara figuras de Drive para docs/img del repositorio / Prepares Drive figures for the repo docs/img."""
import glob, os
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
RAIZ_R = "/content/drive/My Drive/InSAR_LaGuaira_Resultados"
OUT = f"{RAIZ_R}/para_github/docs/img"
os.makedirs(OUT, exist_ok=True)
FIGURAS = {
    "nisar_mapa_cobertura.png": "prelim_cobertura_nisar_umbra.jpg",
    "umbra_mapa_adquisiciones.png": "prelim_mapa_umbra.jpg",
    "Sentinel1_Analisis_Suite.png": "prelim_s1_coherencia_fase_los.jpg",
    "Sentinel1_Composicion_Detallada.png": "prelim_s1_zooms_guaira.jpg",
    "Sentinel1_Correlacion_Dem.png": "prelim_s1_correlacion_dem.jpg",
    "Sentinel1_Monitoreo_Viaducto.png": "prelim_s1_viaducto.jpg",
    "Catia_La_Mar_v2.png": "sitio_catia_la_mar.jpg",
    "Playa_Grande_Urimare_v2.png": "sitio_playa_grande.jpg",
    "La_Guaira_v2.png": "sitio_la_guaira.jpg",
    "Caraballeda_v2.png": "sitio_caraballeda.jpg",
}
for origen, destino in FIGURAS.items():
    h = glob.glob(f"{RAIZ_R}/**/{origen}", recursive=True)
    if not h:
        print("[–] no encontrado / not found:", origen); continue
    im = Image.open(sorted(h)[-1]).convert("RGB"); im.thumbnail((1800, 1800))
    im.save(f"{OUT}/{destino}", "JPEG", quality=85, optimize=True)
    print(f"✓ {destino} {im.size}")
print("Subir a GitHub docs/img / Upload to GitHub docs/img:", OUT)
