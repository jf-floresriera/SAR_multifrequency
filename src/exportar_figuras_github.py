# -*- coding: utf-8 -*-
"""Prepara figuras de Drive para docs/img del repositorio / Prepares Drive figures for the repo docs/img."""
import glob, os
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
RAIZ_R = "/content/drive/My Drive/InSAR_LaGuaira_Resultados"
OUT = f"{RAIZ_R}/para_github/docs/img"
os.makedirs(OUT, exist_ok=True)
FIGURAS = {   # nombre en Drive -> nombre en GitHub / Drive name -> GitHub name
    "Sentinel1_Analisis_Suite.png": "prelim_s1_coherencia_fase_los.jpg",
    "Sentinel1_Composicion_Detallada.png": "prelim_s1_zooms_guaira.jpg",
    "Sentinel1_Correlacion_Dem.png": "prelim_s1_correlacion_dem.jpg",
    "Sentinel1_Monitoreo_Viaducto.png": "prelim_s1_viaducto.jpg",
}
for idioma in ("es", "en"):
    FIGURAS.update({
        f"nisar_mapa_cobertura_{idioma}.png": f"cobertura_nisar_umbra_{idioma}.jpg",
        f"umbra_mapa_adquisiciones_{idioma}.png": f"mapa_umbra_{idioma}.jpg",
        f"fig_linea_tiempo_sensores_{idioma}.png": f"linea_tiempo_{idioma}.jpg",
        f"Catia_La_Mar_v2_{idioma}.png": f"sitio_catia_la_mar_{idioma}.jpg",
        f"Playa_Grande_Urimare_v2_{idioma}.png": f"sitio_playa_grande_{idioma}.jpg",
        f"La_Guaira_v2_{idioma}.png": f"sitio_la_guaira_{idioma}.jpg",
        f"Caraballeda_v2_{idioma}.png": f"sitio_caraballeda_{idioma}.jpg",
    })
for origen, destino in FIGURAS.items():
    h = glob.glob(f"{RAIZ_R}/**/{origen}", recursive=True)
    if not h:
        print("[–] no encontrado / not found:", origen); continue
    im = Image.open(sorted(h)[-1]).convert("RGB"); im.thumbnail((1800, 1800))
    im.save(f"{OUT}/{destino}", "JPEG", quality=85, optimize=True)
    print(f"✓ {destino} {im.size}")
print("Subir a GitHub docs/img / Upload to GitHub docs/img:", OUT)
