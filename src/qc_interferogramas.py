# -*- coding: utf-8 -*-
"""
CONTROL DE CALIDAD (QC) de cada interferograma ANTES de modificar el procesamiento / per-interferogram QC BEFORE changing the processing
====================================================================================================================================
Responde: «¿la señal cosísmica realmente se ve y cómo se DISTRIBUYEN los datos?». Por cada producto propio (Sentinel-1 y NISAR):
  (a) LOS en **mm** (nivel de milímetro, como UCSD) con estiramiento robusto (percentiles 2–98 centrados en la mediana);
  (b) **fase desenvuelta en radianes** (referenciada): rad = 4π·LOS/λ;
  (c) **franjas**: la fase re-envuelta a 2π (1 franja = λ/2 de LOS: S-1 ≈ 27,7 mm, NISAR ≈ 119 mm). Un Mw 7,5 debe dar MUCHAS franjas cerca
      de la falla; si no, el producto no contiene la deformación (par equivocado, desenvolvimiento colapsado, máscara agresiva, producto beta…);
  (d) **coherencia** (mapa) y (e) **histograma de coherencia** con el umbral y el % de píxeles que sobrevive;
  (f) **histograma de la fase en radianes** y de la LOS (mm), con el ruido en campo lejano.
Salida: tabla qc_interferogramas_{es,en}.csv con un diagnóstico por producto y figuras en 04_figuras/borradores/qc/.
Paleta: NO la marrón–azul de UCSD sino Crameri «bam» (ver estilo_figuras.py; PALETA_DIV / PALETA_CICLICA).
Variables opcionales: COH_MIN (0,3), REFERENCIAR (True).
"""
import glob
import os
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
ESC = 1000.0                                                     # m → mm
LAMBDA = {"Sentinel-1": 0.055465763, "NISAR": 0.238403545}      # m (C: 5,405 GHz; L: 1,257 GHz)
KM_FALLA = 20.0
TXT.update({"q_a": {"es": "LOS (mm), estiramiento robusto", "en": "LOS (mm), robust stretch"},
            "q_b": {"es": "Fase desenvuelta (rad) = 4π·LOS/λ", "en": "Unwrapped phase (rad) = 4π·LOS/λ"},
            "q_c": {"es": "Franjas (fase re-envuelta; 1 ciclo = {c:.1f} mm)", "en": "Fringes (re-wrapped phase; 1 cycle = {c:.1f} mm)"},
            "q_d": {"es": "Coherencia", "en": "Coherence"},
            "q_e": {"es": "Histograma de coherencia", "en": "Coherence histogram"},
            "q_f": {"es": "Histograma de la fase (rad)", "en": "Phase histogram (rad)"},
            "q_n": {"es": "píxeles", "en": "pixels"}, "q_ret": {"es": "con coh ≥ {u}: {p:.0f} %", "en": "with coh ≥ {u}: {p:.0f} %"}})

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


FALLAS = None
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

# --- Máscara de TIERRA: hipótesis «la coherencia baja porque gran parte de la escena es mar (el agua no es coherente)».
# --- Land mask: hypothesis "coverage is low because much of the scene is sea (water is incoherent)".
LAND = None
try:
    from rasterio.features import rasterize as _ras
    for _capa in ("paises_sudamerica_ne50", "venezuela_estados"):
        try:
            _g = gpd.read_file(f"{RAIZ}/01_datos_crudos/mapas_base/mapas_base.gpkg", layer=_capa)
            LAND = _ras([(g, 1) for g in _g.geometry if g is not None], out_shape=(n_y, n_x), transform=TR, all_touched=False).astype(bool)
            print(f"Máscara de tierra desde la capa «{_capa}»: {100 * LAND.mean():.0f} % de la ventana es tierra")
            break
        except Exception:
            continue
except Exception as e:
    print("[!] sin máscara de tierra / no land mask:", e)

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
    los_raw = a_ll(ruta) * ESC
    coh = a_ll(pref + "_coh.tif")
    los = np.where(coh >= COH_MIN, los_raw, np.nan) if np.isfinite(coh).any() else los_raw.copy()
    v = np.isfinite(los)
    off = 0.0
    lejos = (v & (DIST > KM_FALLA)) if DIST is not None else None
    if REFERENCIAR and lejos is not None and lejos.sum() > 500:
        off = float(np.nanmedian(los[lejos])); los = los - off
    cob_coh = float(np.nanmean(coh >= COH_MIN)) * 100 if np.isfinite(coh).any() else np.nan
    tierra = {}
    if LAND is not None:
        foot = np.isfinite(coh) if np.isfinite(coh).any() else np.isfinite(los_raw)
        ok_coh = (coh >= COH_MIN) if np.isfinite(coh).any() else np.isfinite(los_raw)
        if (foot & LAND).sum() > 100:
            tierra["huella_en_tierra_pct"] = round(100 * float((foot & LAND).sum() / max(foot.sum(), 1)), 1)
            tierra["coh_sobre_umbral_en_tierra_pct"] = round(100 * float((ok_coh & foot & LAND).sum() / (foot & LAND).sum()), 1)
        if (foot & ~LAND).sum() > 100:
            tierra["coh_sobre_umbral_en_mar_pct"] = round(100 * float((ok_coh & foot & ~LAND).sum() / (foot & ~LAND).sum()), 1)
    if v.sum() < 100:
        filas.append(dict(producto=nombre, sensor=sensor, cobertura_pct=round(100 * float(v.mean()), 2), diagnostico=
                          "CASI SIN DATOS tras la máscara de coherencia: bajar COH_MIN o revisar el producto"))
        print(f"[!] {nombre}: {100 * v.mean():.2f}% de píxeles válidos")
        continue
    lam_mm = LAMBDA[sensor] * ESC
    rad = los / lam_mm * 4 * np.pi                                      # fase desenvuelta (rad), 4π/λ · LOS
    p2, p50, p98 = np.nanpercentile(los, [2, 50, 98])
    ruido = float(1.4826 * np.nanmedian(np.abs(los[lejos] - np.nanmedian(los[lejos])))) if lejos is not None and lejos.sum() > 500 else np.nan
    rango = float(p98 - p2)
    fr = rango / (lam_mm / 2)
    snr = rango / (2 * ruido) if np.isfinite(ruido) and ruido > 0 else np.nan
    maxabs = float(np.nanmax(np.abs(los)))
    dx = []
    if np.isfinite(snr) and snr < 5:
        dx.append("la señal NO destaca del ruido (rango p2–p98 < 5× ruido; ojo: una señal muy localizada puede no verse en percentiles): revisar par/desenvolvimiento/máscara")
    if maxabs > 6 * max(abs(p2), abs(p98)):
        dx.append("hay valores atípicos enormes (¿errores de desenvolvimiento?): usar la máscara de componentes conexas")
    if fr < 1:
        dx.append("menos de 1 franja entre p2 y p98: para un Mw 7,5 se esperan decenas cerca de la falla")
    if sensor == "NISAR" and not iono:
        dx.append("NISAR SIN ionosfera restada")
    if tierra.get("huella_en_tierra_pct", 100) < 60:
        dx.append(f"{100 - tierra['huella_en_tierra_pct']:.0f} % de la huella es MAR (incoherente): la cobertura global subestima la de tierra "
                  f"({tierra.get('coh_sobre_umbral_en_tierra_pct', float('nan')):.0f} % de la tierra supera coh ≥ {COH_MIN})")
    if np.isfinite(cob_coh) and cob_coh < 30:
        dx.append(f"solo {cob_coh:.0f} % de los píxeles supera coh ≥ {COH_MIN}")
    # barrido del umbral de coherencia: cobertura vs ruido en campo lejano / coherence-threshold sweep: coverage vs far-field noise
    barrido = {}
    if np.isfinite(coh).any():
        for u in (0.1, 0.2, 0.3, 0.4):
            mu = np.isfinite(los_raw) & (coh >= u)
            barrido[f"cobertura_coh{u}_pct"] = round(100 * float(mu.mean()), 1)
            lj = mu & (DIST > KM_FALLA) if DIST is not None else None
            if lj is not None and lj.sum() > 500:
                z = los_raw[lj] - np.nanmedian(los_raw[lj])
                barrido[f"ruido_coh{u}_mm"] = round(float(1.4826 * np.nanmedian(np.abs(z))), 1)
        print("   barrido de coherencia / sweep:", {k: v for k, v in barrido.items()})
    filas.append(dict(**barrido, **tierra, producto=nombre, sensor=sensor, ionosfera_restada=bool(iono), offset_referencia_mm=round(off, 1),
                      cobertura_pct=round(100 * float(v.mean()), 1), pct_coh_sobre_umbral=round(cob_coh, 1),
                      los_p2_mm=round(float(p2), 1), los_p98_mm=round(float(p98), 1), max_abs_mm=round(maxabs, 0),
                      fase_p2_rad=round(float(np.nanpercentile(rad, 2)), 1), fase_p98_rad=round(float(np.nanpercentile(rad, 98)), 1),
                      ruido_campo_lejano_mm=round(ruido, 1) if np.isfinite(ruido) else np.nan,
                      franjas_p2_p98=round(fr, 1), relacion_senal_ruido=round(snr, 1) if np.isfinite(snr) else np.nan,
                      diagnostico="; ".join(dx) if dx else "OK: la señal se distingue del ruido"))
    print(f"{nombre}: p2/p98 = {p2:+.0f}/{p98:+.0f} mm · franjas ≈ {fr:.1f} · SNR ≈ {snr:.1f} · {filas[-1]['diagnostico']}")

    for idioma in ("es", "en"):
        aplicar_estilo(7)
        fig, axs = plt.subplots(3, 2, figsize=(180 / 25.4, 132 / 25.4))
        ext = [WIN[0], WIN[1], WIN[2], WIN[3]]
        asp = 1 / np.cos(np.radians((WIN[2] + WIN[3]) / 2))
        lim = max(abs(p2), abs(p98), 10.0)
        limr = lim / lam_mm * 4 * np.pi
        im = axs[0, 0].imshow(los, extent=ext, cmap=CMAPS["divergente"], vmin=-lim, vmax=lim, interpolation="nearest")
        cb = fig.colorbar(im, ax=axs[0, 0], pad=0.01, fraction=0.03); cb.ax.tick_params(labelsize=6, length=2)
        im = axs[0, 1].imshow(rad, extent=ext, cmap=CMAPS["divergente"], vmin=-limr, vmax=limr, interpolation="nearest")
        cb = fig.colorbar(im, ax=axs[0, 1], pad=0.01, fraction=0.03); cb.ax.tick_params(labelsize=6, length=2)
        axs[1, 0].imshow(np.angle(np.exp(1j * rad)), extent=ext, cmap=CMAPS["ciclico"], vmin=-np.pi, vmax=np.pi, interpolation="nearest")
        ic = axs[1, 1].imshow(coh, extent=ext, cmap=CMAPS["secuencial"], vmin=0, vmax=1, interpolation="nearest")
        cb = fig.colorbar(ic, ax=axs[1, 1], pad=0.01, fraction=0.03); cb.ax.tick_params(labelsize=6, length=2)
        for ax, k in zip((axs[0, 0], axs[0, 1], axs[1, 0], axs[1, 1]), ("q_a", "q_b", "q_c", "q_d")):
            ax.set_aspect(asp); ax.tick_params(length=2.5, pad=1.5, labelsize=6)
            ax.set_title(T(k, idioma, c=lam_mm / 2) if k == "q_c" else T(k, idioma), fontsize=6.5, loc="left", pad=2)
            if FALLAS is not None:
                FALLAS.plot(ax=ax, color="k", lw=0.4)
            ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        # (e) histograma de coherencia
        h = axs[2, 0]
        cc = coh[np.isfinite(coh)]
        h.hist(cc, bins=60, range=(0, 1), color="#56B4E9")
        h.axvline(COH_MIN, color="#D55E00", lw=0.9)
        h.set_title(T("q_e", idioma), fontsize=6.5, loc="left", pad=2); h.tick_params(length=2.5, labelsize=6)
        h.text(0.98, 0.95, T("q_ret", idioma, u=COH_MIN, p=cob_coh), transform=h.transAxes, ha="right", va="top", fontsize=6)
        # (f) histograma de la fase (rad) y de la LOS (mm)
        h = axs[2, 1]
        x = rad[np.isfinite(rad)]
        h.hist(np.clip(x, -3 * limr, 3 * limr), bins=120, color="#009E73")
        for q in (np.nanpercentile(rad, 2), np.nanpercentile(rad, 98)):
            h.axvline(q, color="#D55E00", lw=0.8)
        h.set_yscale("log"); h.tick_params(length=2.5, labelsize=6)
        h.set_title(T("q_f", idioma), fontsize=6.5, loc="left", pad=2)
        h.text(0.98, 0.95, f"{T('q_n', idioma)}: {x.size:,}\nLOS p2/p98: {p2:+.0f}/{p98:+.0f} mm\nσ(far): {ruido:.1f} mm\n"
                           f"≈{fr:.1f} {'franjas' if idioma == 'es' else 'fringes'}", transform=h.transAxes, ha="right", va="top", fontsize=6)
        for ax, l in zip(axs.flat, "abcdef"):
            etiqueta_panel(ax, l, dx=-0.12, dy=1.0)
        fig.suptitle(f"{nombre}" + (" · ion OK" if iono else " · sin ion."), fontsize=6.5, x=0.01, ha="left", y=0.995)
        fig.subplots_adjust(left=0.07, right=0.98, top=0.93, bottom=0.06, hspace=0.42, wspace=0.22)
        exportar(fig, f"qc_{nombre}_{idioma}", FIG, formatos=("pdf", "png"))
        plt.close(fig)

Q = pd.DataFrame(filas)
Q.to_csv(f"{OUT}/qc_interferogramas_es.csv", index=False)
Q.to_csv(f"{OUT}/qc_interferogramas_en.csv", index=False)
pd.set_option("display.width", 250, "display.max_colwidth", 110)
print("\n=== DIAGNÓSTICO / DIAGNOSIS ===")
cols = [c for c in ("producto", "ionosfera_restada", "offset_referencia_mm", "cobertura_pct", "pct_coh_sobre_umbral", "huella_en_tierra_pct",
                    "coh_sobre_umbral_en_tierra_pct", "coh_sobre_umbral_en_mar_pct", "franjas_p2_p98",
                    "relacion_senal_ruido", "diagnostico") if c in Q]
print(Q[cols].to_string(index=False))
print(f"\nFiguras / figures: {FIG}")
