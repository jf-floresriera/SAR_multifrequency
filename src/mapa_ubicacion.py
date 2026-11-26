# -*- coding: utf-8 -*-
"""
Figura de ubicación bilingüe (ES/EN) · candidata a Figura 1 / Bilingual location figure (candidate Fig. 1)

(a) Regional: fallas activas, epicentros, recuadro de (b).   (b) Costa de La Guaira: 6 sitios de daño, referencias.
Estilo / style: src/estilo_figuras.py (sin título interno, (a)(b) fuera, Okabe-Ito, SIN Esri / no Esri basemap).
Lee / reads: <RAIZ>/01_datos_crudos/mapas_base/mapas_base.gpkg (lo crea mapas_base.py / created by mapas_base.py)
Salida / output: <RAIZ>/04_figuras/borradores/mapa_ubicacion_{es,en}.{pdf,eps,tiff,png}
"""
import os
import sys as _sys

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import T, TXT
from estilo_figuras import aplicar_estilo, nueva_figura, etiqueta_panel, flecha_norte, exportar

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
GPKG = f"{RAIZ}/01_datos_crudos/mapas_base/mapas_base.gpkg"
FIG = f"{RAIZ}/04_figuras/borradores"
os.makedirs(FIG, exist_ok=True)

TXT.update({
    "u_estados": {"es": "Límite estatal", "en": "State boundary"},
    "u_vias": {"es": "Vías principales (OSM)", "en": "Main roads (OSM)"},
    "u_fallas": {"es": "Fallas activas (GEM)", "en": "Active faults (GEM)"},
    "u_epi": {"es": "Epicentro (USGS)", "en": "Epicentre (USGS)"},
    "u_sitios": {"es": "Sitios de daño", "en": "Damage sites"},
    "u_ref": {"es": "Referencias", "en": "Reference points"},
    "u_mar": {"es": "Mar Caribe", "en": "Caribbean Sea"},
    "u_Playa Grande": {"es": "Playa Grande", "en": "Playa Grande"},
})

REG = (-69.2, -65.9, 9.9, 11.0)          # (a)
ZOOM = (-67.32, -66.62, 10.46, 10.70)    # (b)
SITIOS = {  # nombre: (lat, lon, dx, dy en puntos / offsets in points) — escalonados para no solaparse / staggered
    "Catia La Mar": (10.6055, -67.0324, -34, 30), "Playa Grande": (10.6100, -67.0103, 24, 30),
    "La Guaira": (10.6000, -66.9331, -14, -22), "Caraballeda": (10.6122, -66.8519, -4, 30),
    "Tanaguarena": (10.6150, -66.8200, 6, -27), "Naiguatá": (10.6200, -66.7400, 0, 30)}
REFS = {"Caracas": (10.50, -66.91, 16, -2, "left"), "Aeropuerto SVMI / SVMI airport": (10.60, -66.99, -22, -36, "center"),
        "Macuto": (10.61, -66.89, -4, -26, "center")}
REFS_TXT = {"Caracas": {"es": "Caracas", "en": "Caracas"}, "Macuto": {"es": "Macuto", "en": "Macuto"},
            "Aeropuerto SVMI / SVMI airport": {"es": "Aerop. Maiquetía", "en": "Maiquetía airport"}}
CIUDADES = {"Valencia": (10.18, -68.00), "Puerto Cabello": (10.47, -68.01)}
C = dict(falla="#D55E00", sitio="#0072B2", via="#9a9a9a", estado="#555555", tierra="#f1f1ee", mar="#e8f0f7")


def _capa(c):
    try:
        return gpd.read_file(GPKG, layer=c)
    except Exception:
        return None


capas = {c: _capa(c) for c in ("venezuela_estados", "vias_principales_osm", "fallas_activas_gem", "epicentros_usgs")}


def _escala(ax, km, loc=(0.04, 0.07)):
    """Barra métrica en ejes geográficos (grados): 1° lon = 111.32·cos(lat) km."""
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    lat = (y0 + y1) / 2
    d = km / (111.32 * np.cos(np.radians(lat)))
    x = x0 + loc[0] * (x1 - x0); y = y0 + loc[1] * (y1 - y0)
    ax.plot([x, x + d], [y, y], color="k", lw=1.6, solid_capstyle="butt", zorder=9,
            path_effects=None)
    ax.text(x + d / 2, y + 0.04 * (y1 - y0), f"{km:g} km", ha="center", va="bottom", fontsize=6, zorder=9,
            bbox=dict(fc="white", ec="none", pad=0.6, alpha=1))


def _fondo(ax, ext):
    ax.set_facecolor(C["mar"])
    if capas["venezuela_estados"] is not None:
        capas["venezuela_estados"].plot(ax=ax, facecolor=C["tierra"], edgecolor=C["estado"], lw=0.35, zorder=1)
    if capas["vias_principales_osm"] is not None:
        capas["vias_principales_osm"].plot(ax=ax, color=C["via"], lw=0.35, zorder=2)
    if capas["fallas_activas_gem"] is not None:
        capas["fallas_activas_gem"].plot(ax=ax, color=C["falla"], lw=1.1, zorder=3)
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    ax.set_aspect(1 / np.cos(np.radians((ext[2] + ext[3]) / 2)))
    ax.tick_params(length=2.5, pad=1.5)


def _nombres_fallas(ax, ext, min_frac=0.12, size=6, pos=0.5):
    """Un rótulo por sistema de falla (texto antes de ' - '), sobre el tramo visible más largo, girado según el rumbo.
    One label per fault system, on its longest visible piece, rotated to strike; white halo."""
    f = capas["fallas_activas_gem"]
    if f is None or "name" not in f:
        return
    from shapely.geometry import box as _box
    from shapely.ops import linemerge
    ventana = _box(ext[0], ext[2], ext[1], ext[3]); asp = np.cos(np.radians((ext[2] + ext[3]) / 2))
    mejor = {}
    for _, r in f.dropna(subset=["name"]).iterrows():
        nom = r["name"].split(" - ")[0].strip()
        nom = (nom.title() if nom.isupper() else nom).replace(" Fault", "").replace(" Faults", "")
        g = r.geometry.intersection(ventana)
        if g.is_empty:
            continue
        if g.geom_type == "MultiLineString":
            g = max(g.geoms, key=lambda x: x.length)
        if g.geom_type != "LineString":
            continue
        if nom not in mejor or g.length > mejor[nom].length:
            mejor[nom] = g
    umbral = min_frac * (ext[1] - ext[0])
    for nom, g in mejor.items():
        if g.length < umbral:
            continue
        p0, p1 = g.interpolate(pos - 0.05, normalized=True), g.interpolate(pos + 0.05, normalized=True)
        ang = np.degrees(np.arctan2((p1.y - p0.y), (p1.x - p0.x) * asp))
        ang = ang + 180 if ang > 90 else ang - 180 if ang < -90 else ang
        ax.annotate(nom, (g.interpolate(pos, normalized=True).x, g.interpolate(pos, normalized=True).y), ha="center",
                    va="center", rotation=ang, rotation_mode="anchor", fontsize=size, color="#8a3a00", zorder=7,
                    xytext=(0, 4), textcoords="offset points",
                    bbox=dict(fc="white", ec="none", pad=0.3, alpha=1))


def _epicentros(ax, ext, etiquetas=True):
    e = capas["epicentros_usgs"]
    if e is None:
        return
    for _, r in e.iterrows():
        x, y = r.geometry.x, r.geometry.y
        if ext[0] <= x <= ext[1] and ext[2] <= y <= ext[3]:
            ax.plot(x, y, "*", ms=11, mfc="#F0E442", mec="k", mew=0.6, zorder=8)
            if etiquetas:
                ax.annotate(r.magnitud, (x, y), xytext=(7, -10), textcoords="offset points", fontsize=7,
                            fontweight="bold", zorder=9, bbox=dict(fc="white", ec="none", pad=0.6, alpha=1))


def _mapa(idioma):
    aplicar_estilo(7)
    fig = plt.figure(figsize=(180 / 25.4, 128 / 25.4))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 0.82], hspace=0.28)
    a = fig.add_subplot(gs[0]); b = fig.add_subplot(gs[1])

    # (a) regional
    _fondo(a, REG); _nombres_fallas(a, REG); _epicentros(a, REG)
    for n, (la, lo) in CIUDADES.items():
        a.plot(lo, la, "s", ms=3, mfc="white", mec="k", mew=0.6, zorder=6)
        a.annotate(n, (lo, la), xytext=(4, -9), textcoords="offset points", fontsize=6, zorder=7)
    a.text(-67.9, 10.86, T("u_mar", idioma), fontsize=7, style="normal", color="#4a6f8a", ha="center")
    a.add_patch(Rectangle((ZOOM[0], ZOOM[2]), ZOOM[1] - ZOOM[0], ZOOM[3] - ZOOM[2], fill=False, ec="k", lw=0.8, zorder=7))
    a.annotate("(b)", (ZOOM[1], ZOOM[3]), xytext=(2, 3), textcoords="offset points", fontsize=7, fontweight="bold")
    _escala(a, 50); flecha_norte(a, loc=(0.96, 0.52), largo=0.14)
    a.set_xlabel(T("longitud", idioma)); a.set_ylabel(T("latitud", idioma))
    etiqueta_panel(a, "a", dx=-0.075)

    # (b) costa de La Guaira
    _fondo(b, ZOOM); _nombres_fallas(b, ZOOM, min_frac=0.25, pos=0.33); _epicentros(b, ZOOM)
    for n, (la, lo, dx, dy, ha) in REFS.items():
        b.plot(lo, la, "^", ms=3.5, mfc="white", mec="k", mew=0.6, zorder=6)
        b.annotate(REFS_TXT[n][idioma], (lo, la), xytext=(dx, dy), textcoords="offset points", ha=ha, va="center",
                   fontsize=6, zorder=7, bbox=dict(fc="white", ec="none", pad=0.5, alpha=1),
                   arrowprops=dict(arrowstyle="-|>", lw=0.6, color="k", mutation_scale=6, shrinkA=0, shrinkB=2))
    for n, (la, lo, dx, dy) in SITIOS.items():
        b.plot(lo, la, "o", ms=4.5, mfc=C["sitio"], mec="white", mew=0.7, zorder=8)
        b.annotate(TXT.get("u_" + n, {}).get(idioma, n), (lo, la), xytext=(dx, dy), textcoords="offset points",
                   ha="center", va="center", fontsize=6.5, zorder=9,
                   bbox=dict(fc="white", ec="none", pad=0.5, alpha=1),
                   arrowprops=dict(arrowstyle="-", lw=0.5, color="0.2", shrinkA=0, shrinkB=1.5))
    _escala(b, 10); flecha_norte(b, loc=(0.97, 0.80), largo=0.22)
    b.set_xlabel(T("longitud", idioma)); b.set_ylabel(T("latitud", idioma))
    etiqueta_panel(b, "b", dx=-0.075)

    h = [Line2D([], [], color=C["falla"], lw=1.2, label=T("u_fallas", idioma)),
         Line2D([], [], color=C["via"], lw=0.8, label=T("u_vias", idioma)),
         Line2D([], [], color=C["estado"], lw=0.6, label=T("u_estados", idioma)),
         Line2D([], [], marker="*", ls="", ms=9, mfc="#F0E442", mec="k", label=T("u_epi", idioma)),
         Line2D([], [], marker="o", ls="", ms=4.5, mfc=C["sitio"], mec="white", label=T("u_sitios", idioma)),
         Line2D([], [], marker="^", ls="", ms=4, mfc="white", mec="k", label=T("u_ref", idioma))]
    fig.legend(handles=h, loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(0.5, -0.03),
               handlelength=1.4, columnspacing=1.2, fontsize=6.5)
    return fig


for _i in ("es", "en"):
    _f = _mapa(_i)
    print(exportar(_f, f"mapa_ubicacion_{_i}", FIG, formatos=("pdf", "eps", "tiff", "png")))
    if _i == "es":
        plt.show()
    plt.close(_f)
