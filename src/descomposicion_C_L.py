# -*- coding: utf-8 -*-
"""Descomposición Este/Vertical (C y L), validación GNSS y figura borrador / East/Up decomposition (C and L), GNSS check and draft figure.
Fijar CCS1_LON, CCS1_LAT antes de %run -i para validar con GNSS."""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import T, csv_bilingue, guardar_bilingue
import os
RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
import glob
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.transform import from_origin
# =============================================================================
# BLOQUE B · Descomposición Este/Vertical (asc + desc) en una grilla común
#            Se aplica IGUAL a Sentinel-1, NISAR y ALOS-2
# =============================================================================
GRILLA_EPSG = 32619
RES = 80.0                                   # m (resolución común de comparación)
XMIN, XMAX, YMIN, YMAX = 640000, 790000, 1140000, 1200000   # UTM 19N: Yumare..Guatire
COH_MIN = 0.3


USAR_IONO = globals().get("USAR_IONO", True)    # NISAR: usar *_los_iono_m.tif (división espectral del GUNW) si existe


def _ruta_los(pref):
    """OBSERVACIÓN: la ionosfera DEBE corregirse en banda L (NISAR/ALOS-2). Se usa la capa de pantalla ionosférica del GUNW
    (frecuencias A y B) cuando existe; si no, se avisa. / Ionosphere MUST be corrected in L-band; uses the GUNW screen when present."""
    c = f"{pref}_los_iono_m.tif"
    if USAR_IONO and os.path.exists(c):
        print(f"   ionosfera CORREGIDA / ionosphere CORRECTED: {os.path.basename(pref)}")
        return c
    if "NISAR" in os.path.basename(pref):
        print(f"   [!] SIN corrección ionosférica / NO ionospheric correction: {os.path.basename(pref)} "
              "(falta *_los_iono_m.tif: repita nisar_tif con forzar=True / missing: re-run nisar_tif)")
    return f"{pref}_los_m.tif"


REFERENCIAR = globals().get("REFERENCIAR", True)   # restar la mediana del campo lejano (> 25 km de fallas) a cada pasada
KM_LEJOS = 25.0


def _mascara_lejos():
    """Píxeles a > KM_LEJOS km de cualquier falla GEM (grilla UTM). None si no hay capa de fallas. / far-field mask."""
    try:
        import geopandas as gpd
        from rasterio.features import rasterize
        from scipy.ndimage import distance_transform_edt
        f = gpd.read_file(f"{RAIZ}/01_datos_crudos/mapas_base/mapas_base.gpkg", layer="fallas_activas_gem").to_crs(GRILLA_EPSG)
        n_x, n_y = int((XMAX - XMIN) / RES), int((YMAX - YMIN) / RES)
        m = rasterize([(g, 1) for g in f.geometry if g is not None], out_shape=(n_y, n_x),
                      transform=from_origin(XMIN, YMAX, RES, RES), all_touched=True)
        return distance_transform_edt(m == 0, sampling=RES / 1000.0) > KM_LEJOS
    except Exception as e:
        print("   [!] sin máscara de campo lejano (¿falta mapas_base?) / no far-field mask:", e)
        return None


def a_grilla(ruta, metodo=Resampling.bilinear):
    n_x, n_y = int((XMAX - XMIN) / RES), int((YMAX - YMIN) / RES)
    dst = np.full((n_y, n_x), np.nan, dtype="float32")
    tr = from_origin(XMIN, YMAX, RES, RES)
    with rasterio.open(ruta) as s:
        reproject(rasterio.band(s, 1), dst, src_transform=s.transform, src_crs=s.crs,
                  src_nodata=s.nodata, dst_transform=tr, dst_crs=f"EPSG:{GRILLA_EPSG}",
                  dst_nodata=np.nan, resampling=metodo)
    return dst, tr


LEJOS = None


def descomponer(pares, nombre_banda, salida):
    """pares: lista de prefijos (asc y desc) con archivos *_los_m, *_coh, *_losE/N/U.
    Resuelve por mínimos cuadrados d_LOS = E·e + U·u (N≈0; GNSS CCS1 da dN≈-1 cm)."""
    os.makedirs(salida, exist_ok=True)
    G, d = [], []
    for pref in pares:
        los, tr = a_grilla(_ruta_los(pref))
        coh, _ = a_grilla(f"{pref}_coh.tif")
        e, _ = a_grilla(f"{pref}_losE.tif"); u, _ = a_grilla(f"{pref}_losU.tif")
        los[coh < COH_MIN] = np.nan
        global LEJOS
        if REFERENCIAR:
            if LEJOS is None:
                LEJOS = _mascara_lejos()
            if LEJOS is not None and (np.isfinite(los) & LEJOS).sum() > 500:
                off = float(np.nanmedian(los[LEJOS]))
                los = los - off
                print(f"   referencia / reference: {os.path.basename(pref)}  desfase restado / offset removed = {off*1000:+.0f} mm")
            else:
                print(f"   [!] SIN referenciar / NOT referenced: {os.path.basename(pref)}")
        G.append(np.stack([e, u], -1)); d.append(los)
    G = np.stack(G, -2)                       # (y, x, n_obs, 2)
    d = np.stack(d, -1)                       # (y, x, n_obs)
    n = d.shape[-1]
    valido = np.isfinite(d) & np.all(np.isfinite(G), -1)          # (y, x, n_obs)
    print(f"  {nombre_banda}: píxeles válidos por pasada / valid pixels per track:",
          [f"{100 * valido[..., k].mean():.1f}%" for k in range(n)])
    E = np.full(d.shape[:2], np.nan, "float32"); U = E.copy(); NOBS = np.zeros(d.shape[:2], "uint8")
    import itertools
    # Cada píxel se resuelve con las pasadas que tenga (mínimo 2, con geometrías distintas: cond(G) < 15)
    # Each pixel is solved with the tracks it has (min 2, distinct geometry: cond(G) < 15)
    for k in range(n, 1, -1):
        for comb in itertools.combinations(range(n), k):
            m = np.all(valido[..., list(comb)], -1) & (NOBS == 0)
            if not m.any():
                continue
            Gv = G[m][:, list(comb), :]; dv = d[m][:, list(comb)][..., None]
            sv = np.linalg.svd(Gv, compute_uv=False)
            buena = (sv[:, 0] / np.maximum(sv[:, 1], 1e-9)) < 15
            idx = np.flatnonzero(m.ravel())[buena]
            if idx.size == 0:
                continue
            sol = np.linalg.pinv(Gv[buena]) @ dv[buena]
            E.ravel()[idx], U.ravel()[idx] = sol[:, 0, 0], sol[:, 1, 0]
            NOBS.ravel()[idx] = k
    ok = NOBS > 0
    print(f"  {nombre_banda}: píxeles resueltos / resolved pixels = {ok.sum()} "
          f"(2 pasadas: {(NOBS == 2).sum()}, 3+: {(NOBS >= 3).sum()})")
    perfil = dict(driver="GTiff", height=E.shape[0], width=E.shape[1], count=1, dtype="float32",
                  crs=f"EPSG:{GRILLA_EPSG}", transform=tr, nodata=np.nan, compress="deflate")
    for k, v in (("E", E), ("U", U)):
        with rasterio.open(f"{salida}/{nombre_banda}_{k}_m.tif", "w", **perfil) as dst:
            dst.write(v, 1)
    print(f"{nombre_banda}: {ok.sum()} píxeles resueltos | E p2-p98 = "
          f"{np.nanpercentile(E, 2):.2f}..{np.nanpercentile(E, 98):.2f} m")
    return E, U, tr


def valor_en(arr, tr, x, y, ventana=2):
    c, f = int((x - tr.c) / tr.a), int((y - tr.f) / tr.e)
    return np.nanmedian(arr[f - ventana:f + ventana + 1, c - ventana:c + ventana + 1])


import glob
# --- NISAR: 2 ascendentes (061A, 162A) + descendentes (054D, 126D); cada píxel usa las pasadas válidas que tenga (≥ 2).
# 126D salió casi sin coherencia (0,2 %) en el QC del 26-nov; 054D sí tiene señal. Cambiar con NISAR_TRACKS=(...)
pref_n = sorted({p.rsplit("_los_m.tif", 1)[0] for p in glob.glob(f"{RAIZ}/02_procesados/nisar/*_los_m.tif")
                 if any(t in p for t in globals().get("NISAR_TRACKS", ("T061A", "T162A", "T054D", "T126D")))})
print("NISAR:", [os.path.basename(p) for p in pref_n])
E_L, U_L, tr = descomponer(pref_n, "NISAR_L", f"{RAIZ}/02_procesados/descomposicion")

# --- Sentinel-1: 033A + 025D
pref_c = sorted({p.rsplit("_los_m.tif", 1)[0] for p in glob.glob(f"{RAIZ}/02_procesados/sentinel1/*_los_m.tif")})
print("Sentinel-1:", [os.path.basename(p) for p in pref_c])
E_C, U_C, _ = descomponer(pref_c, "S1_C", f"{RAIZ}/02_procesados/descomposicion")

# --- Validación con GNSS CCS1 (dE = -0.464 m, dN = -0.011 m, dU = +0.021 m; Arenas & Suárez 2026)
# Coloque las coordenadas exactas de CCS1 (de la ficha de estación NGL o IGVSB):
CCS1_LON, CCS1_LAT = globals().get("CCS1_LON"), globals().get("CCS1_LAT")
if CCS1_LON is not None:
    from pyproj import Transformer
    x, y = Transformer.from_crs(4326, GRILLA_EPSG, always_xy=True).transform(CCS1_LON, CCS1_LAT)
    for nombre, E, U in (("NISAR L", E_L, U_L), ("Sentinel-1 C", E_C, U_C)):
        print(f"{nombre}: E = {valor_en(E, tr, x, y):+.3f} m (GNSS -0.464) | U = {valor_en(U, tr, x, y):+.3f} m (GNSS +0.021)")
    print("Si E sale POSITIVO (~+0.46), cambie SIGNO / SIGNO_S1 a +1 y vuelva a correr las celdas 4 y 5.")


import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from rasterio.warp import reproject as _rep, Resampling as _R
from rasterio.transform import from_origin as _fo
from pyproj import Transformer as _Tr
from estilo_figuras import aplicar_estilo, etiqueta_panel, CMAPS, exportar

# --- reproyectar a lon/lat para dibujar con coordenadas geográficas y capas de contexto / to lon-lat for context layers
_t = _Tr.from_crs(GRILLA_EPSG, 4326, always_xy=True)
_xs, _ys = _t.transform([XMIN, XMAX, XMIN, XMAX], [YMIN, YMIN, YMAX, YMAX])
LON0, LON1, LAT0, LAT1 = min(_xs), max(_xs), min(_ys), max(_ys)
DEG = 0.0008
_ng, _nf = int(round((LON1 - LON0) / DEG)), int(round((LAT1 - LAT0) / DEG))
_tr_ll = _fo(LON0, LAT1, DEG, DEG)


def _a_ll(a):
    out = np.full((_nf, _ng), np.nan, "float32")
    _rep(a.astype("float32"), out, src_transform=tr, src_crs=f"EPSG:{GRILLA_EPSG}", dst_transform=_tr_ll,
         dst_crs="EPSG:4326", src_nodata=np.nan, dst_nodata=np.nan, resampling=_R.nearest)
    return out


def _capas():
    import geopandas as gpd
    g = f"{RAIZ}/01_datos_crudos/mapas_base/mapas_base.gpkg"
    out = {}
    for c in ("venezuela_estados", "fallas_activas_gem", "epicentros_usgs", "sitios_danio"):
        try:
            out[c] = gpd.read_file(g, layer=c)
        except Exception:
            out[c] = None
    return out


CAP = _capas()
datos = [("E_C", E_C), ("U_C", U_C), ("E_L", E_L), ("U_L", U_L), ("E_LC", E_L - E_C), ("U_LC", U_L - U_C)]
ll = {k: _a_ll(v) for k, v in datos}


def _fig(idioma):
    aplicar_estilo(7)
    fig, axs = plt.subplots(3, 2, figsize=(180 / 25.4, 128 / 25.4))
    cm = CMAPS["divergente"] if "CMAPS" in globals() and "divergente" in CMAPS else "RdBu_r"
    for k, (ax, (clave, _)) in enumerate(zip(axs.flat, datos)):
        a = ll[clave] * 1000.0                                 # m → mm
        lim = np.nanpercentile(np.abs(a), 98) if np.isfinite(a).any() else 1.0
        lim = max(lim, 10.0)
        im = ax.imshow(a, extent=[LON0, LON1, LAT0, LAT1], cmap=cm, norm=TwoSlopeNorm(0, -lim, lim),
                       interpolation="nearest", zorder=2)
        ax.set_facecolor("#e8f0f7")                            # mar / sea (los NaN dejan ver el fondo)
        if CAP["venezuela_estados"] is not None:
            CAP["venezuela_estados"].boundary.plot(ax=ax, color="#444444", lw=0.35, zorder=3)
        if CAP["fallas_activas_gem"] is not None:
            CAP["fallas_activas_gem"].plot(ax=ax, color="#222222", lw=0.6, zorder=4)
        if CAP["epicentros_usgs"] is not None:
            CAP["epicentros_usgs"].plot(ax=ax, color="#F0E442", marker="*", markersize=60, edgecolor="k", linewidth=0.5, zorder=6)
        if CAP["sitios_danio"] is not None:
            CAP["sitios_danio"].plot(ax=ax, color="#0072B2", markersize=7, edgecolor="white", linewidth=0.4, zorder=5)
        ax.set_xlim(LON0, LON1); ax.set_ylim(LAT0, LAT1)
        ax.set_aspect(1 / np.cos(np.radians((LAT0 + LAT1) / 2)))
        ax.tick_params(length=2.5, pad=1.5)
        ax.set_title(T(clave, idioma), fontsize=7, loc="left", pad=2)
        etiqueta_panel(ax, "abcdef"[k], dx=-0.11, dy=1.0)
        cb = fig.colorbar(im, ax=ax, pad=0.01, fraction=0.03, aspect=22)
        cb.ax.set_title("mm", fontsize=6.5, pad=2); cb.ax.tick_params(labelsize=6, length=2)
        if k >= 4:
            ax.set_xlabel(T("longitud", idioma))
        if k % 2 == 0:
            ax.set_ylabel(T("latitud", idioma))
    return fig


os.makedirs(f"{RAIZ}/04_figuras/borradores", exist_ok=True)
for _i in ("es", "en"):
    _f = _fig(_i)
    print(exportar(_f, f"descomposicion_C_vs_L_{_i}", f"{RAIZ}/04_figuras/borradores", formatos=("pdf", "eps", "tiff", "png")))
    plt.close(_f)
