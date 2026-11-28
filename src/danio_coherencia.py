# -*- coding: utf-8 -*-
"""
DAÑO POR PÉRDIDA DE COHERENCIA, banda C (Sentinel-1) vs banda L (NISAR) — Fig. 8 y Tabla 4
DAMAGE FROM COHERENCE LOSS, C-band (Sentinel-1) vs L-band (NISAR) — Fig. 8 and Table 4
==========================================================================================
ΔCOH = coh_pre − coh_co (Yun et al., 2015, DPM; Fielding et al., 2005). Un par PRE-sísmico (control) y uno COSÍSMICO de la
MISMA geometría (mismo track/pasada y frame): la caída de coherencia que no se ve en el control se atribuye al sismo.
Para cada banda: mapa de ΔCOH (solo tierra) y valores en los edificios de referencia (HOTOSM + Copernicus EMS) por clase.
Métricas: Kruskal–Wallis, δ de Cliff (destruido/dañado vs sin daño, IC 95 % bootstrap) y AUC (ROC, dañado+destruido vs sin daño).

Emparejamiento: Sentinel-1 por hora de pasada (el nombre HyP3 lleva la hora; 10:16 = 025D, 22:42 = 033A);
NISAR por track y frame (NISAR_T<track>_F<frame>_…). Se re-muestrea el cosísmico a la malla del pre-sísmico.
Salidas: 03_resultados/coherencia/dcoh_<banda>_<par>.tif · tabla4_dcoh_{es,en}.csv · dcoh_edificios.csv
         04_figuras/fig8_dcoh_C_vs_L_{es,en}.png/pdf/eps
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
import glob
import os
import re

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import reproject, Resampling

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
OUT = f"{RAIZ}/03_resultados/coherencia"; FIG = f"{RAIZ}/04_figuras"
os.makedirs(OUT, exist_ok=True); os.makedirs(FIG, exist_ok=True)
BBOX = globals().get("BBOX_DANIO", (-67.10, 10.55, -66.80, 10.64))      # franja costera de La Guaira / coastal strip
SISMO = "20260624"
N_BOOT = int(globals().get("N_BOOT", 2000))
CLASES = ["destruido", "dañado", "sin_daño"]
CLASES_EN = {"destruido": "destroyed", "dañado": "damaged", "sin_daño": "undamaged"}

try:
    from mascaras import solo_tierra
except Exception:
    solo_tierra = None


# ------------------------------------------------------------------ 1) pares pre / co
def hora_s1():
    """sufijo de 4 letras del producto HyP3 → (fecha1, fecha2, hora de pasada HHMM)."""
    m = {}
    for c in glob.glob(f"{RAIZ}/01_datos_crudos/sentinel1_hyp3/S1*_INT*"):
        b = os.path.basename(c).replace(".zip", "")
        t = re.findall(r"_(\d{8})T(\d{6})", b)
        if len(t) >= 2:
            m[b[-4:]] = (t[0][0], t[1][0], t[1][1][:4])
    return m


pares = []
H = hora_s1()
s1 = {}
for carpeta, fase in ((f"{RAIZ}/02_procesados/sentinel1_pre", "pre"), (f"{RAIZ}/02_procesados/sentinel1", "co")):
    for f in glob.glob(f"{carpeta}/S1_*_coh.tif"):
        suf = os.path.basename(f).split("_")[3]
        if suf in H:
            hh = int(H[suf][2][:2])
            pasada = "025D" if hh < 12 else "033A"                           # 10:16 UTC desc. / 22:42 UTC asc.
            d1, d2 = os.path.basename(f).split("_")[1:3]
            if fase == "co" and not (d1 < SISMO <= d2):
                continue
            s1.setdefault(pasada, {}).setdefault(fase, []).append(f)
for pasada, d in s1.items():
    if "pre" in d and "co" in d:
        pares.append(dict(banda="C", sensor="Sentinel-1", geom=pasada, pre=sorted(d["pre"])[-1], co=sorted(d["co"])[-1]))
nis = {}
for carpeta, fase in ((f"{RAIZ}/02_procesados/nisar_pre", "pre"), (f"{RAIZ}/02_procesados/nisar", "co")):
    for f in glob.glob(f"{carpeta}/NISAR_T*_F*_coh.tif"):
        m = re.match(r"NISAR_T(\w+?)_F(\d+)_(\d{8})_(\d{8})_coh", os.path.basename(f))
        if not m:
            continue
        if fase == "co" and not (m.group(3) < SISMO <= m.group(4)):
            continue
        if fase == "pre" and m.group(4) >= SISMO:
            continue
        nis.setdefault((m.group(1), m.group(2)), {}).setdefault(fase, []).append(f)
for (tr, fr), d in nis.items():
    if "pre" in d and "co" in d:
        pares.append(dict(banda="L", sensor="NISAR", geom=f"{tr} F{fr}", pre=sorted(d["pre"])[-1], co=sorted(d["co"])[-1]))
print("=== Pares ΔCOH / ΔCOH pairs ===")
for p in pares:
    print(f"  {p['banda']} {p['sensor']} {p['geom']}: pre {os.path.basename(p['pre'])} · co {os.path.basename(p['co'])}")
if not pares:
    raise SystemExit("No hay pares pre+co de la misma geometría todavía / no matching pre+co pairs yet")


# ------------------------------------------------------------------ 2) ΔCOH en la malla del pre-sísmico
def leer(f):
    with rasterio.open(f) as s:
        return s.read(1).astype("float32"), s.transform, s.crs, s.profile


def dcoh(p):
    a, tr, crs, perf = leer(p["pre"])
    b0, tr_b, crs_b, _ = leer(p["co"])
    b = np.full_like(a, np.nan)
    reproject(b0, b, src_transform=tr_b, src_crs=crs_b, dst_transform=tr, dst_crs=crs, resampling=Resampling.bilinear,
              src_nodata=np.nan, dst_nodata=np.nan)
    a = np.where((a > 0) & (a <= 1), a, np.nan); b = np.where((b > 0) & (b <= 1), b, np.nan)
    d = a - b
    if solo_tierra is not None:
        try:
            d = solo_tierra(d, RAIZ, tr, crs)
        except Exception as e:
            print("   (máscara de tierra no aplicada:", str(e)[:60], ")")
    nombre = f"dcoh_{p['banda']}_{p['geom'].replace(' ', '')}"
    perf.update(dtype="float32", nodata=np.nan, compress="deflate", tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(f"{OUT}/{nombre}.tif", "w", **perf) as o:
        o.write(d, 1)
    return d, tr, crs, a, b


import geopandas as gpd
ed = gpd.read_file(f"{RAIZ}/01_datos_crudos/danio_referencia/danio_referencia.gpkg", layer="edificios_danio")
ed = ed[ed.clase.isin(CLASES)]
ed = ed[[g.geom_type in ("Polygon", "MultiPolygon", "Point") and not (g.geom_type == "Polygon" and len(g.exterior.coords) == 7)
         for g in ed.geometry]].reset_index(drop=True)

from scipy.stats import kruskal, mannwhitneyu


def cliff(x, y):
    x, y = x[np.isfinite(x)], y[np.isfinite(y)]
    if len(x) < 5 or len(y) < 5:
        return np.nan, np.nan, np.nan, np.nan
    U = mannwhitneyu(x, y).statistic
    d = 2 * U / (len(x) * len(y)) - 1
    r = np.random.default_rng(0)
    bs = [2 * mannwhitneyu(r.choice(x, len(x)), r.choice(y, len(y))).statistic / (len(x) * len(y)) - 1 for _ in range(N_BOOT)]
    auc = U / (len(x) * len(y))                                              # AUC = P(ΔCOH dañado > ΔCOH sin daño)
    return d, *np.percentile(bs, (2.5, 97.5)), auc


resultados, valores, mapas = [], [], {}
for p in pares:
    d, tr, crs, a, b = dcoh(p)
    mapas[(p["banda"], p["geom"])] = (d, tr, crs)
    pts = ed.to_crs(crs).geometry.representative_point()
    fil, col = rasterio.transform.rowcol(tr, pts.x.values, pts.y.values)
    fil, col = np.asarray(fil), np.asarray(col)
    ok = (fil >= 0) & (fil < d.shape[0]) & (col >= 0) & (col < d.shape[1])
    v = np.full(len(ed), np.nan); v[ok] = d[fil[ok], col[ok]]
    vp = np.full(len(ed), np.nan); vp[ok] = a[fil[ok], col[ok]]
    vc = np.full(len(ed), np.nan); vc[ok] = b[fil[ok], col[ok]]
    t = pd.DataFrame(dict(banda=p["banda"], sensor=p["sensor"], geom=p["geom"], clase=ed.clase, dcoh=v, coh_pre=vp, coh_co=vc))
    valores.append(t)
    g = {c: t.loc[t.clase == c, "dcoh"].dropna().values for c in CLASES}
    if min(len(x) for x in g.values()) >= 5:
        Hs, pv = kruskal(*g.values())
        d1, l1, h1, auc1 = cliff(g["destruido"], g["sin_daño"])
        d2, l2, h2, auc2 = cliff(np.concatenate([g["destruido"], g["dañado"]]), g["sin_daño"])
        resultados.append(dict(banda=p["banda"], sensor=p["sensor"], geometria=p["geom"],
                               n_destruido=len(g["destruido"]), n_danado=len(g["dañado"]), n_sin_dano=len(g["sin_daño"]),
                               dcoh_mediana_destruido=np.median(g["destruido"]), dcoh_mediana_danado=np.median(g["dañado"]),
                               dcoh_mediana_sin_dano=np.median(g["sin_daño"]), H=Hs, p=pv,
                               delta_destruido_vs_sin=d1, ic95_dest=f"[{l1:.2f}, {h1:.2f}]", auc_destruido=auc1,
                               delta_danado_o_destruido_vs_sin=d2, ic95_dan=f"[{l2:.2f}, {h2:.2f}]", auc_danado_o_destruido=auc2))
V = pd.concat(valores, ignore_index=True)
V.to_csv(f"{OUT}/dcoh_edificios.csv", index=False)
R = pd.DataFrame(resultados).round(4)
R.to_csv(f"{OUT}/tabla4_dcoh_es.csv", index=False)
R.rename(columns={"banda": "band", "geometria": "geometry", "n_destruido": "n_destroyed", "n_danado": "n_damaged", "n_sin_dano": "n_undamaged",
                  "dcoh_mediana_destruido": "dcoh_median_destroyed", "dcoh_mediana_danado": "dcoh_median_damaged",
                  "dcoh_mediana_sin_dano": "dcoh_median_undamaged", "delta_destruido_vs_sin": "delta_destroyed_vs_undamaged",
                  "ic95_dest": "ci95_destroyed", "auc_destruido": "auc_destroyed",
                  "delta_danado_o_destruido_vs_sin": "delta_damaged_or_destroyed_vs_undamaged", "ic95_dan": "ci95_damaged",
                  "auc_danado_o_destruido": "auc_damaged_or_destroyed"}).to_csv(f"{OUT}/tabla4_dcoh_en.csv", index=False)
print("\n=== Tabla 4 (borrador) / Table 4 (draft) ===\n" + (R.to_string(index=False) if len(R) else "(pocos edificios con dato)"))

# ------------------------------------------------------------------ 3) Fig. 8
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
try:
    from estilo_figuras import sin_etiquetas
except Exception:
    sin_etiquetas = lambda ax: None
COL = {"destruido": "#D55E00", "dañado": "#E69F00", "sin_daño": "#0072B2"}
claves = list(mapas)
for idi in ("es", "en"):
    es = idi == "es"
    from rasterio.warp import transform_bounds
    fig, AX = plt.subplots(len(claves), 2, figsize=(7.2, 2.3 * len(claves) + 0.2), squeeze=False,
                           gridspec_kw=dict(width_ratios=[2.7, 1]), constrained_layout=True)
    for i, k in enumerate(claves):
        d, tr, crs = mapas[k]
        ax, ax2 = AX[i]
        ext = rasterio.transform.array_bounds(d.shape[0], d.shape[1], tr)
        x0, y0, x1, y1 = transform_bounds("EPSG:4326", crs, *BBOX)
        im = ax.imshow(d, extent=[ext[0], ext[2], ext[1], ext[3]], cmap="RdBu_r", norm=TwoSlopeNorm(0, -0.6, 0.6), interpolation="nearest")
        dd = ed.to_crs(crs)
        for c in ("destruido", "dañado"):
            g_ = dd[dd.clase == c].geometry.representative_point()
            ax.scatter(g_.x, g_.y, s=1.5, c=COL[c], lw=0, label=(c if es else CLASES_EN[c]))
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_xticks([]); ax.set_yticks([]); sin_etiquetas(ax)
        b_, g_ = k
        ax.set_title(f"({'abcdefghijklmnop'[2 * i]}) ΔCOH {('banda' if es else 'band')} {b_} · {('Sentinel-1' if b_ == 'C' else 'NISAR')} {g_}",
                     fontsize=8, loc="left")
        cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01); cb.ax.tick_params(labelsize=6)
        cb.set_label("ΔCOH", fontsize=6.5)
        if i == 0:
            ax.legend(loc="lower left", fontsize=6, markerscale=4, frameon=True)
        t = V[(V.banda == b_) & (V.geom == g_)]
        datos = [t.loc[t.clase == c, "dcoh"].dropna() for c in CLASES]
        bp = ax2.boxplot(datos, widths=0.6, showfliers=False, patch_artist=True, medianprops=dict(color="k"))
        for bx, c in zip(bp["boxes"], CLASES):
            bx.set_facecolor(COL[c]); bx.set_alpha(0.75)
        ax2.axhline(0, color="0.5", lw=0.5)
        ax2.set_xticks([1, 2, 3]); ax2.set_xticklabels([c.replace("_", " ") if es else CLASES_EN[c] for c in CLASES], fontsize=6.5)
        ax2.tick_params(labelsize=6.5); ax2.set_ylabel("ΔCOH = coh pre − coh co", fontsize=6.5)
        r_ = R[(R.banda == b_) & (R.geometria == g_)]
        txt = f"δ = {r_.delta_destruido_vs_sin.iloc[0]:+.2f} · AUC = {r_.auc_destruido.iloc[0]:.2f}" if len(r_) else ""
        ax2.set_title(f"({'abcdefghijklmnop'[2 * i + 1]}) " + ("por clase" if es else "by class") + (f"\n{txt}" if txt else ""), fontsize=7, loc="left")
    from estilo_figuras import guardar_formatos
    print(guardar_formatos(fig, f"{FIG}/fig8_dcoh_C_vs_L_{idi}"))      # pdf, eps, tiff, png
    plt.close(fig)
print(f"\nFig. 8 → {FIG}/fig8_dcoh_C_vs_L_es|en.png/pdf/eps · Tabla 4 → {OUT}/tabla4_dcoh_es|en.csv")
