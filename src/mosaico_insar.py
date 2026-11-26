# -*- coding: utf-8 -*-
"""
MOSAICO de frames / tracks adyacentes (MISMA familia de sensor y MISMA dirección de órbita) · mosaic of adjacent frames/tracks
================================================================================================================
¿Se puede unir? Sí, con cuidado: UCSD/Scripps muestra T162A + T061A (ascendentes) y T054D + T126D (descendentes) como un solo mapa
(https://topex.ucsd.edu/VNZ_7.5/index.html) y el apilado de frames adyacentes es práctica estándar (ISCE, ARIA). Pero cada producto desenvuelto tiene
un desfase constante ARBITRARIO (y cada componente conexa una ambigüedad de 2π), y los tracks vecinos tienen fechas distintas, ángulo de incidencia
algo distinto y atmósfera distinta → hay que **igualar el desfase en la zona de solape** y medir cuánto discrepan (costura).
Qué hace / what it does (por dirección, ASC y DESC):
  1) lee cada producto (LOS en mm; con ionosfera restada si existe) en una malla lon/lat común, con máscara de coherencia ≥ COH_MIN;
  2) toma el de mayor cobertura como ancla; a cada siguiente le RESTA la mediana de (producto − mosaico) en el solape (≥ N_MIN_SOLAPE píxeles)
     o, si no hay solape, la mediana de su campo lejano (> 20 km de fallas) si existe; si no, queda SIN referenciar y se avisa;
  3) en cada píxel toma el valor del producto con MAYOR coherencia;
  4) reporta por pareja: píxeles de solape, desfase aplicado (mm), RMS y MAD de la diferencia en el solape (= calidad de la costura).
PROCEDENCIA: se conservan los valores individuales de cada producto y se escribe mosaico_procedencia_{es,en}.csv (fechas, línea base, días posteriores al sismo,
vector de mirada medio, % de píxeles aportados, desfase aplicado) y el ráster *_fuente.tif (id del producto de cada píxel). Un mosaico NO es un
interferograma único: mezcla ventanas de fechas distintas (distinta cantidad de días tras el sismo), geometrías algo distintas y atmósferas distintas.
IMPORTANTE: el mosaico es para VER y comparar (misma ventana, misma escala). Para Este/Vertical se siguen usando los productos SEPARADOS
(cada uno con su vector de mirada), no el mosaico.
Salida: <RAIZ>/02_procesados/mosaicos/NISAR_MOSAICO_<ASC|DESC>_<ref>_<sec>_{los_m,coh}.tif, tabla mosaico_costuras_{es,en}.csv y figura en 04_figuras/borradores.
Variables: COH_MIN (0,3), N_MIN_SOLAPE (2000).
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
from estilo_figuras import CMAPS, aplicar_estilo, etiqueta_panel, exportar, sin_etiquetas
import matplotlib.pyplot as plt

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
COH_MIN = globals().get("COH_MIN", 0.3)
N_MIN = globals().get("N_MIN_SOLAPE", 2000)
WIN = (-68.60, -66.00, 10.00, 11.00)
DEG = 0.0008
ESC = 1000.0
KM_FALLA = 20.0
OUT = f"{RAIZ}/02_procesados/mosaicos"
FIG = f"{RAIZ}/04_figuras/borradores"
os.makedirs(OUT, exist_ok=True); os.makedirs(FIG, exist_ok=True)
n_x, n_y = int(round((WIN[1] - WIN[0]) / DEG)), int(round((WIN[3] - WIN[2]) / DEG))
TR = from_origin(WIN[0], WIN[3], DEG, DEG)
TXT.update({"mo_a": {"es": "Mosaico LOS (mm)", "en": "Mosaic LOS (mm)"}, "mo_b": {"es": "Producto que aporta cada píxel", "en": "Product supplying each pixel"},
            "mo_c": {"es": "Diferencia en el solape (mm)", "en": "Difference in the overlap (mm)"},
            "mo_leyenda": {"es": "Color = producto que aporta el píxel", "en": "Colour = product supplying the pixel"}})


def _f(s8, idioma):
    mes = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{int(s8[6:8])} {(mes if idioma == 'es' else en)[int(s8[4:6]) - 1]}"


def _corto(n_):
    return re.sub(r'_20[0-9]{6}.*', '', n_)


def a_ll(ruta, metodo=Resampling.bilinear):
    dst = np.full((n_y, n_x), np.nan, "float32")
    if not os.path.exists(ruta):
        return dst
    with rasterio.open(ruta) as s:
        reproject(rasterio.band(s, 1), dst, src_transform=s.transform, src_crs=s.crs, src_nodata=s.nodata,
                  dst_transform=TR, dst_crs="EPSG:4326", dst_nodata=np.nan, resampling=metodo)
    return dst


def escribir(arr, ruta):
    with rasterio.open(ruta, "w", driver="GTiff", height=n_y, width=n_x, count=1, dtype="float32", crs="EPSG:4326", transform=TR,
                       nodata=np.nan, compress="deflate") as d:
        d.write(arr.astype("float32"), 1)


DIST = None
FALLAS = None
try:
    import geopandas as gpd
    from rasterio.features import rasterize
    from scipy.ndimage import distance_transform_edt
    FALLAS = gpd.read_file(f"{RAIZ}/01_datos_crudos/mapas_base/mapas_base.gpkg", layer="fallas_activas_gem")
    _m = rasterize([(g, 1) for g in FALLAS.geometry if g is not None], out_shape=(n_y, n_x), transform=TR, all_touched=True)
    DIST = distance_transform_edt(_m == 0, sampling=(DEG * 111.32, DEG * 111.32 * np.cos(np.radians(10.5))))
except Exception as e:
    print("[!] sin capa de fallas: no habrá referencia de campo lejano / no faults layer:", e)

# ------------------------------------------------------------------ inventario por (familia, dirección)
# Regla: se unen SOLO productos de la MISMA familia (sensor/banda) y la MISMA dirección de órbita. Nunca entre sensores: C y L se COMPARAN, no se mezclan.
# Rule: only products of the SAME family (sensor/band) and SAME orbit direction are merged. Never across sensors: C vs L are COMPARED, not mixed.
prods = []


def _dir_por_mirada(pref):
    """Sentinel-1 no trae el track en el nombre: la dirección sale del signo del vector de mirada Este (suelo→satélite: ASC < 0, DESC > 0)."""
    e = a_ll(pref + "_losE.tif")
    return None if not np.isfinite(e).any() else ("ASC" if np.nanmean(e) < 0 else "DESC")


for fam, carpeta, patron in (("NISAR", "nisar", "NISAR_T*_los_m.tif"), ("Sentinel-1", "sentinel1", "S1_*_los_m.tif"),
                             ("UCSD", "ucsd", "UCSD_*_los_m.tif")):
    for f in sorted(glob.glob(f"{RAIZ}/02_procesados/{carpeta}/{patron}")):
        pref = f[:-len("_los_m.tif")]
        nombre = os.path.basename(pref)
        fechas = re.findall(r"(20\d{6})", nombre)
        if len(fechas) < 2:
            continue
        tr_ = re.search(r"_T(\d{3})([AD])_", nombre)
        if tr_:
            direc, track = ("ASC" if tr_.group(2) == "A" else "DESC"), tr_.group(1) + tr_.group(2)
        else:
            direc, track = _dir_por_mirada(pref), ""
        if direc is None:
            print(f"[!] {nombre}: sin vector de mirada, no se sabe si es ASC o DESC / no look vector")
            continue
        iono = pref + "_los_iono_m.tif"
        familia = ("ALOS-2 (UCSD)" if "ALOS2" in nombre else "NISAR (UCSD)") if fam == "UCSD" else fam
        prods.append(dict(nombre=nombre, fam=familia, dir=direc, track=track, pref=pref, ruta=iono if os.path.exists(iono) else f,
                          ref=fechas[0], sec=fechas[-1]))
PROD = pd.DataFrame(prods)       # NO llamar P: pisaba la función P() del cuaderno / must not be named P: it clobbered the notebook's P()
if PROD.empty:
    raise SystemExit("Sin productos en 02_procesados / no products")

filas = []
resumen = {}
prov = []          # procedencia: qué producto, fechas, geometría y aporte tiene cada pieza del mosaico / provenance of every mosaic piece
for (fam_, direc), G in PROD.groupby(["fam", "dir"]):
    datos = []
    for _, p in G.iterrows():
        los = a_ll(p.ruta) * ESC
        coh = a_ll(p.pref + "_coh.tif")
        if np.isfinite(coh).any():
            los = np.where(coh >= COH_MIN, los, np.nan)
        datos.append(dict(p=p, los=los, coh=coh))
    datos.sort(key=lambda d: -np.isfinite(d["los"]).sum())          # ancla = mayor cobertura
    print(f"\n== {fam_} {direc}: {[d['p'].nombre for d in datos]}")
    if len(datos) < 2:
        print("   (un solo producto: no hay vecino que unir / single product: nothing to merge)")
    for d_ in datos:
        if not np.isfinite(d_["coh"]).any():          # UCSD no trae coherencia: se trata como 1 donde hay dato
            d_["coh"] = np.where(np.isfinite(d_["los"]), 1.0, np.nan).astype("float32")
    mos = datos[0]["los"].copy(); cohm = np.where(np.isfinite(datos[0]["los"]), datos[0]["coh"], -1.0)
    fuente = np.where(np.isfinite(mos), 0, -1)
    # el ancla también se referencia al campo lejano si es posible
    if DIST is not None and (np.isfinite(mos) & (DIST > KM_FALLA)).sum() > 500:
        off0 = float(np.nanmedian(mos[np.isfinite(mos) & (DIST > KM_FALLA)])); mos = mos - off0
    else:
        off0 = 0.0
    filas.append(dict(familia=fam_, direccion=direc, producto=datos[0]["p"].nombre, rol="ancla", solape_pix=0, desfase_aplicado_mm=round(off0, 1),
                      rms_solape_mm=np.nan, mad_solape_mm=np.nan, metodo="campo lejano" if off0 else "sin cambio"))
    for k, d in enumerate(datos[1:], start=1):
        los, coh, nom = d["los"], d["coh"], d["p"].nombre
        ov = np.isfinite(los) & np.isfinite(mos)
        if ov.sum() >= N_MIN:
            dif = los[ov] - mos[ov]
            off = float(np.median(dif)); metodo = "solape"
        elif DIST is not None and (np.isfinite(los) & (DIST > KM_FALLA)).sum() > 500:
            off = float(np.nanmedian(los[np.isfinite(los) & (DIST > KM_FALLA)])); metodo = "campo lejano"
        else:
            off = 0.0; metodo = "SIN referenciar (ni solape ni campo lejano)"
        los = los - off
        if ov.sum() > 0:
            dif = los[ov] - mos[ov]
            rms = float(np.sqrt(np.mean(dif ** 2))); mad = float(1.4826 * np.median(np.abs(dif - np.median(dif))))
        else:
            rms = mad = np.nan
        filas.append(dict(familia=fam_, direccion=direc, producto=nom, rol="añadido", solape_pix=int(ov.sum()), desfase_aplicado_mm=round(off, 1),
                          rms_solape_mm=round(rms, 1) if np.isfinite(rms) else np.nan, mad_solape_mm=round(mad, 1) if np.isfinite(mad) else np.nan, metodo=metodo))
        print(f"   {nom}: solape {int(ov.sum()):,} px · desfase {off:+.0f} mm ({metodo}) · RMS solape {rms:.0f} mm")
        mejor = np.isfinite(los) & (~np.isfinite(mos) | (coh > cohm))
        mos = np.where(mejor, los, mos); cohm = np.where(mejor, coh, cohm); fuente = np.where(mejor, k, fuente)
    f0 = min(d["p"].ref for d in datos); f1 = max(d["p"].sec for d in datos)
    slug = {"NISAR": "NISAR", "Sentinel-1": "S1", "ALOS-2 (UCSD)": "ALOS2UCSD", "NISAR (UCSD)": "NISARUCSD"}[fam_]
    base = f"{slug}_MOSAICO_{direc}_{f0}_{f1}"
    escribir(np.where(np.isfinite(mos), mos / ESC, np.nan), f"{OUT}/{base}_los_m.tif")
    escribir(np.where(cohm >= 0, cohm, np.nan), f"{OUT}/{base}_coh.tif")
    # --- procedencia: un mosaico NO es un interferograma único; cada pieza tiene sus fechas, su línea base, su geometría y su desfase
    # --- provenance: a mosaic is NOT a single interferogram; every piece keeps its own dates, baseline, look geometry and offset
    info = []
    n_val = max(int((fuente >= 0).sum()), 1)
    escribir(np.where(fuente >= 0, fuente, np.nan), f"{OUT}/{base}_fuente.tif")
    for k, d in enumerate(datos):
        pp = d["p"]
        e_ = a_ll(pp.pref + "_losE.tif"); u_ = a_ll(pp.pref + "_losU.tif")
        fr = re.search(r"_F(\d{3})_", pp.nombre)
        d0, d1 = pd.Timestamp(pp.ref), pd.Timestamp(pp.sec)
        fila_c = next((f_ for f_ in filas if f_["producto"] == pp.nombre), {})
        info.append(dict(nombre=pp.nombre, ref=pp.ref, sec=pp.sec, dias=(d1 - d0).days))
        prov.append(dict(mosaico=base, id_en_mosaico=k, producto=pp.nombre, familia=fam_, direccion=direc, track=pp.track,
                         frame=fr.group(1) if fr else "", fecha_ref=d0.date(), fecha_sec=d1.date(), linea_base_dias=(d1 - d0).days,
                         dias_post_sismo_en_la_ventana=max((d1 - pd.Timestamp("2026-06-24")).days, 0),
                         mirada_E_media=round(float(np.nanmean(e_)), 3) if np.isfinite(e_).any() else np.nan,
                         mirada_U_media=round(float(np.nanmean(u_)), 3) if np.isfinite(u_).any() else np.nan,
                         pct_pixeles_del_mosaico=round(100 * float((fuente == k).sum()) / n_val, 1),
                         desfase_aplicado_mm=fila_c.get("desfase_aplicado_mm", np.nan), metodo_desfase=fila_c.get("metodo", "")))
    if len(datos) >= 2:
        resumen[(fam_, direc)] = (mos, fuente, [d["p"].nombre for d in datos], base, info)

PR = pd.DataFrame(prov)
PR.to_csv(f"{OUT}/mosaico_procedencia_es.csv", index=False)
PR.rename(columns={"mosaico": "mosaic", "id_en_mosaico": "id_in_mosaic", "producto": "product", "familia": "family", "direccion": "direction",
                   "fecha_ref": "ref_date", "fecha_sec": "sec_date", "linea_base_dias": "baseline_days",
                   "dias_post_sismo_en_la_ventana": "days_after_quake_in_window", "mirada_E_media": "look_E_mean", "mirada_U_media": "look_U_mean",
                   "pct_pixeles_del_mosaico": "pct_of_mosaic_pixels", "desfase_aplicado_mm": "applied_offset_mm",
                   "metodo_desfase": "offset_method"}).to_csv(f"{OUT}/mosaico_procedencia_en.csv", index=False)
print("\n=== PROCEDENCIA DE CADA PIEZA / PROVENANCE ===")
print(PR[["mosaico", "producto", "fecha_ref", "fecha_sec", "linea_base_dias", "dias_post_sismo_en_la_ventana", "mirada_E_media", "mirada_U_media",
          "pct_pixeles_del_mosaico"]].to_string(index=False))
M = pd.DataFrame(filas)
M.to_csv(f"{OUT}/mosaico_costuras_es.csv", index=False)
M.rename(columns={"familia": "family", "direccion": "direction", "producto": "product", "rol": "role", "solape_pix": "overlap_px", "desfase_aplicado_mm": "applied_offset_mm",
                  "rms_solape_mm": "overlap_rms_mm", "mad_solape_mm": "overlap_mad_mm", "metodo": "method"}).to_csv(f"{OUT}/mosaico_costuras_en.csv", index=False)
pd.set_option("display.width", 220)
print("\n=== COSTURAS / SEAMS ===")
print(M.to_string(index=False))

# ------------------------------------------------------------------ figura
for idioma in ("es", "en"):
    aplicar_estilo(7)
    n = len(resumen)
    if n == 0:
        break
    fig, axs = plt.subplots(n, 2, figsize=(180 / 25.4, (36 * n + 14) / 25.4), squeeze=False)
    for i, ((fam_, direc), (mos, fuente, nombres, base, info)) in enumerate(resumen.items()):
        v = mos[np.isfinite(mos)]
        lim = max(float(np.percentile(np.abs(v), 99)) if v.size else 100.0, 20.0)
        ext = [WIN[0], WIN[1], WIN[2], WIN[3]]
        im = axs[i, 0].imshow(mos, extent=ext, cmap=CMAPS["divergente"], vmin=-lim, vmax=lim, interpolation="nearest")
        cb = fig.colorbar(im, ax=axs[i, 0], pad=0.01, fraction=0.03); cb.ax.tick_params(labelsize=6, length=2)
        axs[i, 0].set_title(f"{fam_} {direc} · {T('mo_a', idioma)}", fontsize=6.5, loc="left", pad=2)
        from matplotlib.colors import ListedColormap
        from matplotlib.patches import Patch
        paleta = ["#E69F00", "#56B4E9", "#009E73", "#D55E00", "#CC79A7", "#F0E442", "#0072B2", "#999999"]    # Okabe-Ito
        axs[i, 1].imshow(np.where(fuente >= 0, fuente, np.nan), extent=ext, cmap=ListedColormap(paleta[:len(nombres)]),
                         vmin=-0.5, vmax=len(nombres) - 0.5, interpolation="nearest")
        axs[i, 1].set_title(f"{fam_} {direc} · {T('mo_b', idioma)}", fontsize=6.5, loc="left", pad=2)
        axs[i, 1].legend(handles=[Patch(facecolor=paleta[k], edgecolor="k", linewidth=0.3, label=f"{_corto(n_)} · {_f(info[k]['ref'], idioma)}→{_f(info[k]['sec'], idioma)} ({info[k]['dias']} d)") for k, n_ in enumerate(nombres)],
                         loc="lower left", fontsize=5.2, frameon=True, framealpha=1, edgecolor="0.6", handlelength=1.0, borderpad=0.4,
                         title=T("mo_leyenda", idioma), title_fontsize=5.2)
        for ax in axs[i]:
            ax.set_aspect(1 / np.cos(np.radians(10.5))); ax.tick_params(length=2.5, pad=1.5, labelsize=6)
            if FALLAS is not None:
                FALLAS.plot(ax=ax, color="k", lw=0.4)
            sin_etiquetas(ax)
            ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
            ax.set_ylabel(T('latitud', idioma) if ax is axs[i, 0] else '', fontsize=6.5)
            ax.set_xlabel(T('longitud', idioma) if i == n - 1 else '', fontsize=6.5)
        etiqueta_panel(axs[i, 0], "abcdefghij"[2 * i], dx=-0.1, dy=1.0)
        etiqueta_panel(axs[i, 1], "abcdefghij"[2 * i + 1], dx=-0.1, dy=1.0)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.94, bottom=0.07, hspace=0.35, wspace=0.42)
    exportar(fig, f"mosaico_nisar_{idioma}", FIG, formatos=("pdf", "png"))
    plt.close(fig)
print(f"\nMosaicos / mosaics: {OUT} · figura / figure: {FIG}/mosaico_nisar_{{es,en}}.*")
