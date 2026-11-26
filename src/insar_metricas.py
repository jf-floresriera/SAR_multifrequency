# -*- coding: utf-8 -*-
"""
Métricas y gráficos COMPARABLES de toda la interferometría (Sentinel-1 C, NISAR L) / comparable metrics and plots
=========================================================================================================
Lee todos los *_los_m.tif (+ *_coh.tif) de 02_procesados/{sentinel1,nisar} (los crean s1_tif y nisar_tif) y produce:
  1) Tabla de métricas por producto (CSV ES/EN): fechas, relación con el sismo (PRE/CO/POST), línea base, cobertura,
     coherencia, rango LOS, ruido en campo lejano (> 20 km de fallas), vector de mirada medio.
  2) Mapas con LA MISMA ventana, LA MISMA escala de color (± cm, común a todos) y el mismo contexto (costa, fallas,
     epicentros, sitios): se pueden comparar a ojo entre sensores y geometrías.   Ventanas: regional y costa de La Guaira.
  3) Perfil comparable: mediana LOS vs latitud a lo largo de un transecto común (lon −66,95).
Convención: LOS en cm, + = acercamiento al satélite. Máscara de coherencia ≥ COH_MIN.
Salida: <RAIZ>/02_procesados/metricas_insar/ y <RAIZ>/04_figuras/borradores/ (PDF, EPS, TIFF, PNG; ES y EN).
Variables opcionales (antes de %run -i): COH_MIN, LIM_CM (fija el límite de color), TRANSECTO_LON.
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
from estilo_figuras import CMAPS, aplicar_estilo, etiqueta_panel, exportar, OKABE_ITO

import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
COH_MIN = globals().get("COH_MIN", 0.3)
LIM_CM = globals().get("LIM_CM", None)
TRANSECTO_LON = globals().get("TRANSECTO_LON", -66.95)
SISMO = pd.Timestamp("2026-06-24")
OUT = f"{RAIZ}/02_procesados/metricas_insar"
FIG = f"{RAIZ}/04_figuras/borradores"
os.makedirs(OUT, exist_ok=True); os.makedirs(FIG, exist_ok=True)
VENT = {"region": (-68.20, -66.20, 10.10, 10.90), "costa": (-67.32, -66.62, 10.46, 10.70)}
DEG = 0.0008                                         # ≈ 88 m, de la misma escala que el producto de 80 m
KM_FALLA = 20.0

TXT.update({
    "m_los": {"es": "LOS (cm); + = acercamiento al satélite", "en": "LOS (cm); + = toward satellite"},
    "m_co": {"es": "cosísmico", "en": "coseismic"}, "m_pre": {"es": "pre-sísmico (control)", "en": "pre-seismic (control)"},
    "m_post": {"es": "post-sísmico", "en": "post-seismic"},
    "m_perfil": {"es": "Latitud (°)", "en": "Latitude (°)"},
    "m_perfil_y": {"es": "LOS mediana (cm)", "en": "Median LOS (cm)"},
    "m_costa": {"es": "costa", "en": "coast"},
})

# ---------------------------------------------------------------- inventario de productos
filas = []
for banda, sensor, carpeta in (("C", "Sentinel-1", "sentinel1"), ("L", "NISAR", "nisar")):
    for f in sorted(glob.glob(f"{RAIZ}/02_procesados/{carpeta}/*_los_m.tif")):
        pref = f[:-len("_los_m.tif")]; nombre = os.path.basename(pref)
        d = re.findall(r"(20\d{6})", nombre)
        if len(d) < 2:
            continue
        ref, sec = pd.Timestamp(d[0]), pd.Timestamp(d[-1])
        track = (re.search(r"_T(\w+?)_", nombre) or [None, ""])[1] if sensor == "NISAR" else ""
        rel = "PRE" if sec < SISMO else ("POST" if ref >= SISMO else "CO")
        filas.append(dict(sensor=sensor, banda=banda, track=track, nombre=nombre, pref=pref, ref=ref, sec=sec,
                          linea_base_d=(sec - ref).days, relacion=rel))
prod = pd.DataFrame(filas)
if prod.empty:
    raise SystemExit("No hay *_los_m.tif en 02_procesados/{sentinel1,nisar}: ejecute s1_tif y nisar_tif / run s1_tif and nisar_tif first")
prod = prod.sort_values(["relacion", "banda", "track", "ref"]).reset_index(drop=True)
print(prod[["sensor", "track", "ref", "sec", "relacion"]].to_string())


def _grilla(win):
    lon0, lon1, lat0, lat1 = win
    n_x, n_y = int(round((lon1 - lon0) / DEG)), int(round((lat1 - lat0) / DEG))
    return n_x, n_y, from_origin(lon0, lat1, DEG, DEG)


def _a_ll(ruta, win, metodo=Resampling.bilinear):
    n_x, n_y, tr = _grilla(win)
    dst = np.full((n_y, n_x), np.nan, "float32")
    if not os.path.exists(ruta):
        return dst
    with rasterio.open(ruta) as s:
        reproject(rasterio.band(s, 1), dst, src_transform=s.transform, src_crs=s.crs, src_nodata=s.nodata,
                  dst_transform=tr, dst_crs="EPSG:4326", dst_nodata=np.nan, resampling=metodo)
    return dst


def _contexto():
    import geopandas as gpd
    g = f"{RAIZ}/01_datos_crudos/mapas_base/mapas_base.gpkg"
    out = {}
    for c in ("venezuela_estados", "fallas_activas_gem", "epicentros_usgs", "sitios_danio"):
        try:
            out[c] = gpd.read_file(g, layer=c)
        except Exception:
            out[c] = None
    return out


CTX = _contexto()


def _dist_falla_km(win):
    """Distancia (km) a la falla GEM más cercana en la grilla de la ventana; None si no hay capa."""
    f = CTX["fallas_activas_gem"]
    if f is None:
        return None
    from rasterio.features import rasterize
    from scipy.ndimage import distance_transform_edt
    n_x, n_y, tr = _grilla(win)
    m = rasterize([(g, 1) for g in f.geometry if g is not None], out_shape=(n_y, n_x), transform=tr, all_touched=True)
    if not m.any():
        return None
    lat = (win[2] + win[3]) / 2
    return distance_transform_edt(m == 0, sampling=(DEG * 111.32, DEG * 111.32 * np.cos(np.radians(lat))))


# ---------------------------------------------------------------- lectura y métricas
VR = VENT["region"]
cache = {}
met = []
dist = _dist_falla_km(VR)
for i, p in prod.iterrows():
    los = _a_ll(p.pref + "_los_m.tif", VR) * 100.0                      # cm
    coh = _a_ll(p.pref + "_coh.tif", VR)
    if np.isfinite(coh).any():
        los = np.where(coh >= COH_MIN, los, np.nan)
    cache[p.nombre] = los
    v = np.isfinite(los)
    lejos = v & (dist > KM_FALLA) if dist is not None else v
    mad = lambda a: float(1.4826 * np.nanmedian(np.abs(a - np.nanmedian(a)))) if a.size else np.nan
    e = _a_ll(p.pref + "_losE.tif", VR); u = _a_ll(p.pref + "_losU.tif", VR)
    met.append(dict(
        sensor=p.sensor, banda=p.banda, track=p.track, fecha_ref=p.ref.date(), fecha_sec=p.sec.date(),
        linea_base_dias=p.linea_base_d, relacion_sismo=p.relacion,
        cobertura_pct=round(100 * v.mean(), 1),
        coh_media=round(float(np.nanmean(coh)), 3) if np.isfinite(coh).any() else np.nan,
        coh_ge_umbral_pct=round(100 * float(np.nanmean(coh >= COH_MIN)), 1) if np.isfinite(coh).any() else np.nan,
        los_p2_cm=round(float(np.nanpercentile(los[v], 2)), 2) if v.any() else np.nan,
        los_p98_cm=round(float(np.nanpercentile(los[v], 98)), 2) if v.any() else np.nan,
        los_abs_p99_cm=round(float(np.nanpercentile(np.abs(los[v]), 99)), 2) if v.any() else np.nan,
        ruido_campo_lejano_cm=round(mad(los[lejos]), 2) if lejos.any() else np.nan,
        n_pix_campo_lejano=int(lejos.sum()),
        mirada_E_media=round(float(np.nanmean(e)), 3) if np.isfinite(e).any() else np.nan,
        mirada_U_media=round(float(np.nanmean(u)), 3) if np.isfinite(u).any() else np.nan,
        producto=p.nombre))
M = pd.DataFrame(met)
COLS_EN = {"sensor": "sensor", "banda": "band", "track": "track", "fecha_ref": "ref_date", "fecha_sec": "sec_date",
           "linea_base_dias": "baseline_days", "relacion_sismo": "relation_to_quake", "cobertura_pct": "coverage_pct",
           "coh_media": "mean_coherence", "coh_ge_umbral_pct": f"coh_ge_{COH_MIN}_pct", "los_p2_cm": "los_p2_cm",
           "los_p98_cm": "los_p98_cm", "los_abs_p99_cm": "los_abs_p99_cm",
           "ruido_campo_lejano_cm": "far_field_noise_cm", "n_pix_campo_lejano": "n_far_field_pixels",
           "mirada_E_media": "look_E_mean", "mirada_U_media": "look_U_mean", "producto": "product"}
M.to_csv(f"{OUT}/metricas_insar_es.csv", index=False)
M.rename(columns=COLS_EN).to_csv(f"{OUT}/metricas_insar_en.csv", index=False)
print("\n=== MÉTRICAS / METRICS (ventana regional) ===")
print(M.drop(columns=["producto"]).to_string(index=False))

# límite de color común (± cm) a partir de los cosísmicos / common colour limit from coseismic products
co = [cache[n] for n, r in zip(prod.nombre, prod.relacion) if r == "CO"] or list(cache.values())
LIM = float(LIM_CM) if LIM_CM else float(np.ceil(np.nanpercentile(np.abs(np.concatenate([a[np.isfinite(a)] for a in co])), 99)))
LIM = max(LIM, 2.0)
print(f"\nLímite de color común / common colour limit: ±{LIM:g} cm")


# ---------------------------------------------------------------- figuras
def _titulo(p, idioma):
    f = lambda t: f"{t.day} {['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'][t.month-1] if idioma=='es' else t.strftime('%b').lower()}"
    tr = f" {p.track}" if p.track else ""
    dup = ((prod.ref == p.ref) & (prod.sec == p.sec) & (prod.sensor == p.sensor)).sum() > 1
    if dup and not p.track:
        tr = f" #{p.nombre[-4:]}"        # varios productos del mismo par (p. ej. 40 m y 80 m) / several products of the same pair
    return f"{p.sensor} ({p.banda}){tr} · {f(p.ref)}→{f(p.sec)} · {T('m_' + p.relacion.lower(), idioma)}"


def _fig_mapas(vent, idioma):
    aplicar_estilo(7)
    win = VENT[vent]; lon0, lon1, lat0, lat1 = win
    n = len(prod); cols = 2; filas_ = int(np.ceil(n / cols))
    asp = (lon1 - lon0) * np.cos(np.radians((lat0 + lat1) / 2)) / (lat1 - lat0)
    w_ax = 78.0; h_ax = w_ax / asp
    H = filas_ * (h_ax + 9.0) + 16.0
    fig, axs = plt.subplots(filas_, cols, figsize=(180 / 25.4, H / 25.4), squeeze=False)
    cm = CMAPS["divergente"]
    im = None
    for k, ax in enumerate(axs.flat):
        if k >= n:
            ax.axis("off"); continue
        p = prod.iloc[k]
        a = _a_ll(p.pref + "_los_m.tif", win) * 100.0
        c = _a_ll(p.pref + "_coh.tif", win)
        if np.isfinite(c).any():
            a = np.where(c >= COH_MIN, a, np.nan)
        ax.set_facecolor("#e8f0f7")
        im = ax.imshow(a, extent=[lon0, lon1, lat0, lat1], cmap=cm, norm=TwoSlopeNorm(0, -LIM, LIM),
                       interpolation="nearest", zorder=2)
        if CTX["venezuela_estados"] is not None:
            CTX["venezuela_estados"].boundary.plot(ax=ax, color="#444444", lw=0.35, zorder=3)
        if CTX["fallas_activas_gem"] is not None:
            CTX["fallas_activas_gem"].plot(ax=ax, color="#222222", lw=0.6, zorder=4)
        if CTX["sitios_danio"] is not None:
            CTX["sitios_danio"].plot(ax=ax, color="#0072B2", markersize=6, edgecolor="white", linewidth=0.4, zorder=5)
        if CTX["epicentros_usgs"] is not None:
            CTX["epicentros_usgs"].plot(ax=ax, color="#F0E442", marker="*", markersize=55, edgecolor="k", linewidth=0.5, zorder=6)
        ax.set_xlim(lon0, lon1); ax.set_ylim(lat0, lat1)
        ax.set_aspect(1 / np.cos(np.radians((lat0 + lat1) / 2)))
        ax.tick_params(length=2.5, pad=1.5, labelsize=6)
        ax.set_title(_titulo(p, idioma), fontsize=6.2, loc="left", pad=2)
        etiqueta_panel(ax, "abcdefghijklmnop"[k], dx=-0.13, dy=1.0)
        if k % cols == 0:
            ax.set_ylabel(T("latitud", idioma), fontsize=6.5)
        if k >= n - cols:
            ax.set_xlabel(T("longitud", idioma), fontsize=6.5)
    cax = fig.add_axes([0.30, 0.012 if filas_ > 2 else 0.02, 0.40, 0.012])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal")
    cb.set_label(T("m_los", idioma), fontsize=6.5); cb.ax.tick_params(labelsize=6, length=2)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.97, bottom=0.07 if filas_ > 2 else 0.12, hspace=0.38, wspace=0.18)
    return fig


def _fig_perfil(idioma):
    aplicar_estilo(7)
    fig, ax = plt.subplots(figsize=(180 / 25.4, 70 / 25.4))
    win = (TRANSECTO_LON - 0.012, TRANSECTO_LON + 0.012, 10.40, 10.74)
    lat = np.linspace(win[3], win[2], int(round((win[3] - win[2]) / DEG)))
    cols = [OKABE_ITO[k % len(OKABE_ITO)] for k in range(len(prod))] if isinstance(OKABE_ITO, (list, tuple)) else list(OKABE_ITO.values())
    for k, p in prod.iterrows():
        a = _a_ll(p.pref + "_los_m.tif", win) * 100.0
        c = _a_ll(p.pref + "_coh.tif", win)
        if np.isfinite(c).any():
            a = np.where(c >= COH_MIN, a, np.nan)
        with np.errstate(all="ignore"):
            perf = np.nanmedian(a, axis=1)
        n_ = min(len(perf), len(lat))
        ax.plot(lat[:n_], perf[:n_], color=cols[k % len(cols)], lw=0.9, ls="-" if p.banda == "C" else "--",
                alpha=0.35 if p.relacion == "PRE" else 1.0, label=_titulo(p, idioma))
    ax.axhline(0, color="0.5", lw=0.5)
    ax.set_xlabel(T("m_perfil", idioma)); ax.set_ylabel(T("m_perfil_y", idioma))
    ax.legend(fontsize=5.6, frameon=False, loc="upper left", ncol=1, bbox_to_anchor=(1.0, 1.0))
    ax.tick_params(length=2.5)
    return fig


for idioma in ("es", "en"):
    for vent in VENT:
        f = _fig_mapas(vent, idioma)
        print(exportar(f, f"insar_comparable_{vent}_{idioma}", FIG, formatos=("pdf", "eps", "tiff", "png")))
        plt.close(f)
    f = _fig_perfil(idioma)
    print(exportar(f, f"insar_perfil_comparable_{idioma}", FIG, formatos=("pdf", "eps", "tiff", "png")))
    plt.close(f)
print(f"\nTabla / table: {OUT}/metricas_insar_{{es,en}}.csv · figuras / figures: {FIG}/insar_*_{{es,en}}.*")
