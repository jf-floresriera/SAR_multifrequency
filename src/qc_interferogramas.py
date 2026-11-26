# -*- coding: utf-8 -*-
"""
CONTROL DE CALIDAD (QC) de cada interferograma ANTES de interpretarlo / per-interferogram QC BEFORE interpreting it
=====================================================================================================================
Qué responde / what it answers: «¿la señal cosísmica realmente se ve, o todo sale homogéneo?». Para cada producto propio
(Sentinel-1 y NISAR; *_los_m.tif / *_los_iono_m.tif + *_coh.tif) hace 4 paneles:
  (a) LOS en cm con estiramiento ROBUSTO (percentiles 2–98 centrados en la mediana, no en el máximo): un solo dato atípico
      (error de desenvolvimiento) aplana todo el mapa si se usa el máximo;
  (b) FRANJAS: la fase desenvuelta re-envuelta a 2π (cada franja = λ/2 de LOS: S-1 ≈ 2,8 cm, NISAR ≈ 11,9 cm). Un Mw 7,5 debe mostrar
      MUCHAS franjas cerca de la falla; si no hay, el producto no contiene la deformación (par equivocado, desenvolvimiento colapsado,
      máscara de coherencia demasiado agresiva, producto beta…);
  (c) coherencia; (d) histograma de LOS + ruido en campo lejano.
Salida: tabla qc_interferogramas.csv (ES/EN) con el diagnóstico en una columna y figuras en 04_figuras/borradores/qc/.
Variables opcionales: COH_MIN (0,3), REFERENCIAR (True).
"""
import glob
import os
import re
import sys as _sys

import matplotlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import T, TXT
from estilo_figuras import CMAPS, aplicar_estilo, etiqueta_panel, exportar
import matplotlib.pyplot as plt

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
COH_MIN = globals().get("COH_MIN", 0.3)
REFERENCIAR = globals().get("REFERENCIAR", True)
OUT = f"{RAIZ}/02_procesados/metricas_insar"
FIG = f"{RAIZ}/04_figuras/borradores/qc"
os.makedirs(OUT, exist_ok=True); os.makedirs(FIG, exist_ok=True)
WIN = (-68.20, -66.20, 10.10, 10.90)
DEG = 0.0008
LAMBDA = {"Sentinel-1": 0.055465763, "NISAR": 0.238403545}      # m (C: 5,405 GHz; L: 1,257 GHz)
KM_FALLA = 20.0
TXT.update({"q_a": {"es": "LOS (cm), estiramiento robusto", "en": "LOS (cm), robust stretch"},
            "q_b": {"es": "Franjas (fase re-envuelta, 1 ciclo = {c:.1f} cm)", "en": "Fringes (re-wrapped phase, 1 cycle = {c:.1f} cm)"},
            "q_c": {"es": "Coherencia", "en": "Coherence"}, "q_d": {"es": "Histograma de LOS (cm)", "en": "LOS histogram (cm)"},
            "q_n": {"es": "píxeles", "en": "pixels"}})

n_x, n_y = int(round((WIN[1] - WIN[0]) / DEG)), int(round((WIN[3] - WIN[2]) / DEG))
TR = from_origin(WIN[0], WIN[3], DEG, DEG)


def a_ll(ruta, metodo=Resampling.bilinear):
    dst = np.full((n_y, n_x), np.nan, "float32")
    if not os.path.exists(ruta):
        return dst
    with rasterio.open(ruta) as s:
        reproject(rasterio.band(s, 1), dst, src_transform=s.transform, src_crs=s.crs, src_nodata=s.nodata,
                  dst_transform=TR, dst_crs="EPSG:4326", dst_nodata=np.nan, resampling=metodo)
    return dst


try:
    import geopandas as gpd
    from rasterio.features import rasterize
    from scipy.ndimage import distance_transform_edt
    FALLAS = gpd.read_file(f"{RAIZ}/01_datos_crudos/mapas_base/mapas_base.gpkg", layer="fallas_activas_gem")
    msk = rasterize([(g, 1) for g in FALLAS.geometry if g is not None], out_shape=(n_y, n_x), transform=TR, all_touched=True)
    DIST = distance_transform_edt(msk == 0, sampling=(DEG * 111.32, DEG * 111.32 * np.cos(np.radians(10.5))))
except Exception as e:
    print("[!] sin capa de fallas: no se puede referenciar ni medir el campo lejano / no faults layer:", e)
    DIST = None

prods = []
for sensor, carpeta in (("Sentinel-1", "sentinel1"), ("NISAR", "nisar")):
    for f in sorted(glob.glob(f"{RAIZ}/02_procesados/{carpeta}/*_los_m.tif")):
        pref = f[:-len("_los_m.tif")]
        iono = os.path.exists(pref + "_los_iono_m.tif") and sensor == "NISAR"
        prods.append((sensor, os.path.basename(pref), pref, pref + ("_los_iono_m.tif" if iono else "_los_m.tif"), iono))
if not prods:
    raise SystemExit("Sin productos en 02_procesados: ejecute s1_tif / nisar_tif / no products found")

filas = []
for sensor, nombre, pref, ruta, iono in prods:
    los = a_ll(ruta) * 100.0
    coh = a_ll(pref + "_coh.tif")
    bruto = los.copy()
    if np.isfinite(coh).any():
        los = np.where(coh >= COH_MIN, los, np.nan)
    v = np.isfinite(los)
    off = 0.0
    lejos = (v & (DIST > KM_FALLA)) if DIST is not None else None
    if REFERENCIAR and lejos is not None and lejos.sum() > 500:
        off = float(np.nanmedian(los[lejos])); los = los - off
    if v.sum() < 100:
        filas.append(dict(producto=nombre, sensor=sensor, cobertura_pct=round(100 * float(v.mean()), 2),
                          diagnostico="CASI SIN DATOS tras la máscara de coherencia: bajar COH_MIN o revisar el producto"))
        print(f"[!] {nombre}: {100 * v.mean():.2f}% de píxeles válidos")
        continue
    p2, p50, p98 = np.nanpercentile(los, [2, 50, 98])
    ruido = float(1.4826 * np.nanmedian(np.abs(los[lejos] - np.nanmedian(los[lejos])))) if lejos is not None and lejos.sum() > 500 else np.nan
    rango = float(p98 - p2)
    fr = rango / (LAMBDA[sensor] * 100 / 2)                       # franjas entre p2 y p98
    snr = rango / (2 * ruido) if np.isfinite(ruido) and ruido > 0 else np.nan
    maxabs = float(np.nanmax(np.abs(los)))
    dx = []
    if np.isfinite(snr) and snr < 5:
        dx.append("la señal NO destaca del ruido (rango p2–p98 < 5× ruido; ojo: una señal muy localizada puede no verse en percentiles): revisar par/desenvolvimiento/máscara")
    if maxabs > 6 * max(abs(p2), abs(p98)):
        dx.append("hay valores atípicos enormes (¿errores de desenvolvimiento?): enmascarar o usar la máscara de componentes conexas")
    if fr < 1:
        dx.append("menos de 1 franja entre p2 y p98: para un Mw 7,5 se esperan decenas cerca de la falla")
    if not iono and sensor == "NISAR":
        dx.append("NISAR SIN ionosfera restada")
    filas.append(dict(producto=nombre, sensor=sensor, ionosfera_restada=bool(iono), offset_referencia_cm=round(off, 2),
                      cobertura_pct=round(100 * float(v.mean()), 1), los_p2_cm=round(float(p2), 2), los_p98_cm=round(float(p98), 2),
                      max_abs_cm=round(maxabs, 1), ruido_campo_lejano_cm=round(ruido, 2) if np.isfinite(ruido) else np.nan,
                      franjas_p2_p98=round(fr, 1), relacion_senal_ruido=round(snr, 1) if np.isfinite(snr) else np.nan,
                      diagnostico="; ".join(dx) if dx else "OK: la señal se distingue del ruido"))
    print(f"{nombre}: p2/p98 = {p2:+.1f}/{p98:+.1f} cm · franjas ≈ {fr:.1f} · SNR ≈ {snr:.1f} · {filas[-1]['diagnostico']}")

    for idioma in ("es", "en"):
        aplicar_estilo(7)
        fig, axs = plt.subplots(2, 2, figsize=(180 / 25.4, 88 / 25.4))
        ext = [WIN[0], WIN[1], WIN[2], WIN[3]]
        asp = 1 / np.cos(np.radians((WIN[2] + WIN[3]) / 2))
        lim = max(abs(p2), abs(p98), 1.0)
        im = axs[0, 0].imshow(los, extent=ext, cmap=CMAPS["divergente"], vmin=-lim, vmax=lim, interpolation="nearest")
        cb = fig.colorbar(im, ax=axs[0, 0], pad=0.01, fraction=0.03); cb.ax.tick_params(labelsize=6, length=2)
        c_cm = LAMBDA[sensor] * 100 / 2
        fase = np.angle(np.exp(1j * (los / c_cm) * 2 * np.pi))
        axs[0, 1].imshow(fase, extent=ext, cmap=CMAPS.get("ciclico", "twilight"), vmin=-np.pi, vmax=np.pi, interpolation="nearest")
        ic = axs[1, 0].imshow(coh, extent=ext, cmap=CMAPS.get("secuencial", "viridis"), vmin=0, vmax=1, interpolation="nearest")
        cb = fig.colorbar(ic, ax=axs[1, 0], pad=0.01, fraction=0.03); cb.ax.tick_params(labelsize=6, length=2)
        for ax, k in zip((axs[0, 0], axs[0, 1], axs[1, 0]), ("q_a", "q_b", "q_c")):
            ax.set_aspect(asp); ax.tick_params(length=2.5, pad=1.5, labelsize=6)
            ax.set_title(T(k, idioma, c=c_cm) if k == "q_b" else T(k, idioma), fontsize=6.5, loc="left", pad=2)
            if FALLAS is not None:
                FALLAS.plot(ax=ax, color="k", lw=0.4)
            ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        h = axs[1, 1]
        x = los[np.isfinite(los)]
        h.hist(np.clip(x, -3 * lim, 3 * lim), bins=120, color="#0072B2", alpha=0.85)
        for q in (p2, p98):
            h.axvline(q, color="#D55E00", lw=0.8)
        h.set_yscale("log"); h.tick_params(length=2.5, labelsize=6)
        h.set_title(T("q_d", idioma), fontsize=6.5, loc="left", pad=2)
        h.text(0.98, 0.95, f"{T('q_n', idioma)}: {x.size:,}\np2/p98: {p2:+.1f}/{p98:+.1f} cm\nσ(far): {ruido:.2f} cm\n"
                           f"≈{fr:.1f} {'franjas' if idioma == 'es' else 'fringes'}",
               transform=h.transAxes, ha="right", va="top", fontsize=6)
        for ax, l in zip(axs.flat, "abcd"):
            etiqueta_panel(ax, l, dx=-0.12, dy=1.0)
        fig.suptitle(f"{nombre}" + (" · ion ✓" if iono else ""), fontsize=6.5, x=0.01, ha="left", y=0.995)
        fig.subplots_adjust(left=0.07, right=0.98, top=0.9, bottom=0.08, hspace=0.35, wspace=0.22)
        exportar(fig, f"qc_{nombre}_{idioma}", FIG, formatos=("pdf", "png"))
        plt.close(fig)

Q = pd.DataFrame(filas)
Q.to_csv(f"{OUT}/qc_interferogramas_es.csv", index=False)
Q.to_csv(f"{OUT}/qc_interferogramas_en.csv", index=False)
pd.set_option("display.width", 240, "display.max_colwidth", 120)
print("\n=== DIAGNÓSTICO / DIAGNOSIS ===")
print(Q[["producto", "ionosfera_restada", "offset_referencia_cm", "cobertura_pct", "franjas_p2_p98", "relacion_senal_ruido", "diagnostico"]].to_string(index=False)
      if "franjas_p2_p98" in Q else Q.to_string(index=False))
print(f"\nFiguras / figures: {FIG}")
