# -*- coding: utf-8 -*-
"""
ÍNDICES DE BANDA X POR EDIFICIO (Umbra, una sola fecha posterior al sismo) — Fig. 9 y Tabla 3
X-BAND PER-BUILDING INDICES (Umbra, single post-event date) — Fig. 9 and Table 3
=============================================================================================
Por qué una sola fecha: todas las Umbra del catálogo abierto son POSTERIORES al sismo (26-jun a 2-jul-2026), así que no hay
log-ratio antes/después en banda X. Se caracteriza cada edificio con estadísticas de su retrodispersión y textura y se prueba
si separan destruido / dañado / sin daño (referencia HOTOSM + Copernicus EMS).
Why single date: every open Umbra scene is post-event, so no X-band log-ratio; we test whether per-building backscatter and
texture separate destroyed / damaged / undamaged buildings.

Objetos = huellas de edificios (clasificación basada en objetos, OBIA). Por edificio (polígono + margen `MARGEN_M`):
  media, mediana y p90 de σ (dB, tras filtro de Lee 5×5) · CV local (desv/media, lineal) · fracción brillante (> p95 de la
  ventana: dobles rebotes de fachadas intactas) · fracción de sombra (< p10) · textura GLCM de Haralick (entropía, contraste,
  homogeneidad, disimilitud; 32 niveles, distancias 1–2 px, 4 direcciones).
Estadística: Kruskal–Wallis (Kruskal y Wallis, 1952) entre las 3 clases; Cliff's delta (Cliff, 1993) destruido vs sin daño y
dañado vs sin daño, con IC 95 % por bootstrap (Efron, 1979). |δ| < 0,147 despreciable, < 0,33 pequeño, < 0,474 mediano, ≥ grande.

Entradas: 05_documentacion/seleccion_zonas_danio.csv (las composiciones elegidas, con escena Umbra, desfase y corrección).
Variables: CONFIGS (lista; None = todas las del lote), MARGEN_M (10), PIXEL_M (0,5), UMBRAS (("umbra",) = solo la 1; añadir "umbra2").
Salidas: 03_resultados/banda_x/indices_edificios.csv · tabla3_kruskal_cliff_{es,en}.csv · 04_figuras/fig9_indices_banda_x_{es,en}.png/pdf/eps
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
import os
import json

import numpy as np
import pandas as pd

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
TRAB = globals().get("TRABAJO", os.path.join(os.path.dirname(RAIZ), "inventario_2026"))
CONFIGS = globals().get("CONFIGS", None)
MARGEN_M = float(globals().get("MARGEN_M", 10.0))
PIXEL_M = float(globals().get("PIXEL_M", 0.5))
UMBRAS = tuple(globals().get("UMBRAS", ("umbra",)))
N_BOOT = int(globals().get("N_BOOT", 2000))
SALIDA = f"{RAIZ}/03_resultados/banda_x"
FIG = f"{RAIZ}/04_figuras"
os.makedirs(SALIDA, exist_ok=True); os.makedirs(FIG, exist_ok=True)

CLASES = ["destruido", "dañado", "sin_daño"]
CLASES_EN = {"destruido": "destroyed", "dañado": "damaged", "sin_daño": "undamaged"}
INDICES = {  # clave: (es, en)
    "media_db": ("σ medio (dB)", "mean σ (dB)"), "p90_db": ("σ p90 (dB)", "σ p90 (dB)"),
    "cv": ("CV local", "local CV"), "frac_brillante": ("fracción brillante", "bright fraction"),
    "frac_sombra": ("fracción de sombra", "shadow fraction"), "glcm_entropia": ("GLCM entropía", "GLCM entropy"),
    "glcm_contraste": ("GLCM contraste", "GLCM contrast"), "glcm_homogeneidad": ("GLCM homogeneidad", "GLCM homogeneity"),
    "glcm_disimilitud": ("GLCM disimilitud", "GLCM dissimilarity"),
}


def lee(intensidad, k=5):
    """Filtro de Lee (Lee, 1980) sobre intensidad lineal / Lee speckle filter."""
    from scipy.ndimage import uniform_filter
    m = uniform_filter(intensidad, k); m2 = uniform_filter(intensidad ** 2, k)
    v = np.maximum(m2 - m ** 2, 0)
    cu2 = np.nanmedian(v / np.maximum(m ** 2, 1e-12))                 # ruido estimado en la ventana / noise estimate
    w = np.clip(1 - cu2 * m ** 2 / np.maximum(v, 1e-12), 0, 1)
    return m + w * (intensidad - m)


def glcm(parche_db, mascara):
    from skimage.feature import graycomatrix, graycoprops
    v = parche_db[mascara]
    if v.size < 30:
        return {k: np.nan for k in ("glcm_entropia", "glcm_contraste", "glcm_homogeneidad", "glcm_disimilitud")}
    lo, hi = np.percentile(v, (2, 98))
    q = np.clip((parche_db - lo) / max(hi - lo, 1e-6) * 31, 0, 31).astype(np.uint8)
    q = np.where(mascara, q, 0)
    P = graycomatrix(q, distances=[1, 2], angles=[0, np.pi / 4, np.pi / 2, 3 * np.pi / 4], levels=32, symmetric=True, normed=False)
    P[0, :, :, :] = 0; P[:, 0, :, :] = 0                              # fuera del edificio (nivel 0) no cuenta / ignore outside
    P = P.astype(float); P /= np.maximum(P.sum(axis=(0, 1), keepdims=True), 1)
    ent = float(np.mean([-(P[:, :, i, j][P[:, :, i, j] > 0] * np.log2(P[:, :, i, j][P[:, :, i, j] > 0])).sum()
                         for i in range(P.shape[2]) for j in range(P.shape[3])]))
    return {"glcm_entropia": ent, "glcm_contraste": float(graycoprops(P, "contrast").mean()),
            "glcm_homogeneidad": float(graycoprops(P, "homogeneity").mean()),
            "glcm_disimilitud": float(graycoprops(P, "dissimilarity").mean())}


def cliff_delta(a, b, n_boot=N_BOOT, semilla=0):
    """δ de Cliff = P(a > b) − P(a < b), con IC 95 % bootstrap / Cliff's delta with bootstrap CI."""
    from scipy.stats import mannwhitneyu
    a, b = np.asarray(a, float), np.asarray(b, float); a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 5 or len(b) < 5:
        return np.nan, np.nan, np.nan
    d = lambda x, y: 2 * mannwhitneyu(x, y).statistic / (len(x) * len(y)) - 1
    r = np.random.default_rng(semilla)
    bs = [d(r.choice(a, len(a)), r.choice(b, len(b))) for _ in range(n_boot)]
    return d(a, b), *np.percentile(bs, (2.5, 97.5))


def magnitud(dl):
    x = abs(dl)
    return ("despreciable", "negligible") if x < 0.147 else ("pequeño", "small") if x < 0.33 else \
        ("mediano", "medium") if x < 0.474 else ("grande", "large")


# ------------------------------------------------------------------ 1) edificios y composiciones elegidas
import geopandas as gpd
from shapely.geometry import box
from explorador_optico import Explorador

sel = pd.read_csv(f"{RAIZ}/05_documentacion/seleccion_zonas_danio.csv")
if CONFIGS:
    sel = sel[sel.config.isin(CONFIGS)]
print(f"Composiciones usadas / compositions used: {', '.join(sel.config)}")
ed = gpd.read_file(f"{RAIZ}/01_datos_crudos/danio_referencia/danio_referencia.gpkg", layer="edificios_danio").to_crs(32619)
ed = ed[ed.clase.isin(CLASES)]
ed = ed[[g.geom_type in ("Polygon", "MultiPolygon") and not (g.geom_type == "Polygon" and len(g.exterior.coords) == 7)
         for g in ed.geometry]]                                         # solo huellas (sin hexágonos de cuadrícula)
ed = ed[(ed.area > 20) & (ed.area < 20000)].reset_index(drop=True)
ed["id_edificio"] = ed.index
ex = Explorador(RAIZ, TRAB)

# ------------------------------------------------------------------ 2) índices por edificio
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin
a_utm = Transformer.from_crs(4326, 32619, always_xy=True)
filas = []
for _, f in sel.iterrows():
    lado = float(f.ventana_m); n = int(round(lado / PIXEL_M))
    cx, cy = a_utm.transform(f.lon, f.lat)
    tr = from_origin(cx - lado / 2, cy + lado / 2, PIXEL_M, PIXEL_M)
    en_v = ed[ed.intersects(box(cx - lado / 2, cy - lado / 2, cx + lado / 2, cy + lado / 2))]
    for pre_ in UMBRAS:
        url = f.get(f"url_{pre_}")
        if not (isinstance(url, str) and url):
            continue
        al = dict(dE=float(f.get(f"{pre_}_dE_m", 0) or 0), dN=float(f.get(f"{pre_}_dN_m", 0) or 0),
                  variante="sin" if not Explorador._si(f.get(f"{pre_}_relieve_corregido", f.get("umbra_relieve_corregido")), True)
                  else ("dem_inv" if Explorador._si(f.get(f"{pre_}_invertido", f.get("umbra_invertido")), False) else "dem"))
        amp, _ = ex._leer_umbra(url, f.lon, f.lat, lado, al, n=n)
        I = lee(np.where(amp > 0, amp.astype("float64") ** 2, np.nan))
        db = 10 * np.log10(np.where(I > 0, I, np.nan))
        p95, p10 = np.nanpercentile(db, 95), np.nanpercentile(db, 10)
        for _, e in en_v.iterrows():
            g = e.geometry.buffer(MARGEN_M)
            m = rasterize([(g, 1)], out_shape=(n, n), transform=tr, fill=0, dtype="uint8").astype(bool) & np.isfinite(db)
            if m.sum() < 30:
                continue
            fi, co = np.where(m); s_ = (slice(fi.min(), fi.max() + 1), slice(co.min(), co.max() + 1))
            v = db[m]; vl = I[m]
            fila = dict(config=f.config, umbra=pre_, mirada=f.get(f"{pre_}_mirada", ""), id_edificio=e.id_edificio, clase=e.clase,
                        fuente=e.get("fuente", ""), area_m2=float(e.geometry.area), n_pix=int(m.sum()),
                        media_db=float(np.nanmean(v)), mediana_db=float(np.nanmedian(v)), p90_db=float(np.nanpercentile(v, 90)),
                        cv=float(np.nanstd(vl) / max(np.nanmean(vl), 1e-12)), frac_brillante=float((v > p95).mean()),
                        frac_sombra=float((v < p10).mean()))
            fila.update(glcm(db[s_], m[s_]))
            filas.append(fila)
    print(f"   {f.config}: {len(en_v)} edificios en la ventana / buildings in window")
T = pd.DataFrame(filas)
# un edificio puede caer en varias ventanas: se promedia por edificio y escena / average duplicates
T = T.groupby(["id_edificio", "umbra", "mirada", "clase"], as_index=False).agg(
    {**{k: "mean" for k in list(INDICES) + ["mediana_db"]}, "area_m2": "first", "n_pix": "max", "config": lambda s: "|".join(sorted(set(s)))})
T.to_csv(f"{SALIDA}/indices_edificios.csv", index=False)
print("\nEdificios por clase / buildings per class:\n" + T.groupby(["umbra", "clase"]).size().unstack(fill_value=0).to_string())

# ------------------------------------------------------------------ 3) Kruskal–Wallis + Cliff's delta → Tabla 3
from scipy.stats import kruskal
tab = []
for pre_, Tu in T.groupby("umbra"):
    for k, (nes, nen) in INDICES.items():
        grupos = [Tu.loc[Tu.clase == c, k].dropna().values for c in CLASES]
        if min(len(x) for x in grupos) < 5:
            continue
        H, p = kruskal(*grupos)
        d1, l1, h1 = cliff_delta(grupos[0], grupos[2]); d2, l2, h2 = cliff_delta(grupos[1], grupos[2])
        tab.append(dict(umbra=pre_, indice=nes, index=nen, H=H, p=p,
                        n_destruido=len(grupos[0]), n_danado=len(grupos[1]), n_sin_dano=len(grupos[2]),
                        delta_destruido_vs_sin=d1, ic95_dest=f"[{l1:.2f}, {h1:.2f}]", magnitud_dest=magnitud(d1)[0],
                        delta_danado_vs_sin=d2, ic95_dan=f"[{l2:.2f}, {h2:.2f}]", magnitud_dan=magnitud(d2)[0]))
R = pd.DataFrame(tab).sort_values(["umbra", "delta_destruido_vs_sin"], key=lambda s: s.abs() if s.dtype != object else s, ascending=[True, False])
es = R.drop(columns=["index"]).round(4)
en = R.drop(columns=["indice"]).rename(columns={"n_destruido": "n_destroyed", "n_danado": "n_damaged", "n_sin_dano": "n_undamaged",
                                               "delta_destruido_vs_sin": "delta_destroyed_vs_undamaged", "ic95_dest": "ci95_destroyed",
                                               "magnitud_dest": "magnitude_destroyed", "delta_danado_vs_sin": "delta_damaged_vs_undamaged",
                                               "ic95_dan": "ci95_damaged", "magnitud_dan": "magnitude_damaged"}).round(4)
en["magnitude_destroyed"] = [magnitud(x)[1] for x in R.delta_destruido_vs_sin]
en["magnitude_damaged"] = [magnitud(x)[1] for x in R.delta_danado_vs_sin]
es.to_csv(f"{SALIDA}/tabla3_kruskal_cliff_es.csv", index=False); en.to_csv(f"{SALIDA}/tabla3_kruskal_cliff_en.csv", index=False)
print("\n=== Tabla 3 (borrador) / Table 3 (draft) ===\n" + es.to_string(index=False))

# ------------------------------------------------------------------ 4) Fig. 9: distribución por clase de los 6 mejores índices
import matplotlib.pyplot as plt
COL = {"destruido": "#D55E00", "dañado": "#E69F00", "sin_daño": "#0072B2"}
Tu = T[T.umbra == UMBRAS[0]]
mejores = R[R.umbra == UMBRAS[0]].reindex(R[R.umbra == UMBRAS[0]].delta_destruido_vs_sin.abs().sort_values(ascending=False).index).head(6)
claves = [k for k, (nes, _) in INDICES.items() if nes in set(mejores.indice)]
for idi in ("es", "en"):
    fig, axs = plt.subplots(2, 3, figsize=(7.2, 4.8))
    for ax, k in zip(axs.flat, claves):
        datos = [Tu.loc[Tu.clase == c, k].dropna() for c in CLASES]
        bp = ax.boxplot(datos, widths=0.6, showfliers=False, patch_artist=True, medianprops=dict(color="k", lw=1))
        for b_, c in zip(bp["boxes"], CLASES):
            b_.set_facecolor(COL[c]); b_.set_alpha(0.75)
        ax.set_xticks([1, 2, 3]); ax.set_xticklabels([c.replace("_", " ") if idi == "es" else CLASES_EN[c] for c in CLASES], fontsize=7)
        r_ = mejores[mejores.indice == INDICES[k][0]].iloc[0]
        ax.set_title(f"{INDICES[k][0 if idi == 'es' else 1]}\nδ = {r_.delta_destruido_vs_sin:+.2f} · p = {r_.p:.1e}", fontsize=7.5)
        ax.tick_params(labelsize=7)
    for ax in axs.flat[len(claves):]:
        ax.axis("off")
    fig.suptitle(("Índices de banda X (Umbra) por edificio — δ de Cliff: destruido vs sin daño" if idi == "es" else
                  "X-band (Umbra) per-building indices — Cliff's δ: destroyed vs undamaged"), fontsize=8.5, x=0.01, ha="left")
    fig.tight_layout()
    for ext_ in ("png", "pdf", "eps"):
        fig.savefig(f"{FIG}/fig9_indices_banda_x_{idi}.{ext_}", dpi=300 if ext_ == "png" else None)
    plt.close(fig)
print(f"\nFig. 9 → {FIG}/fig9_indices_banda_x_es|en.png/pdf/eps · Tabla 3 → {SALIDA}/tabla3_kruskal_cliff_es|en.csv")
