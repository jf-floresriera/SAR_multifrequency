# -*- coding: utf-8 -*-
"""
Estilo común de figuras para SRL / Q1 (minimalismo analítico) · Common figure style for SRL / Q1.

Uso / Usage
    from estilo_figuras import *
    aplicar_estilo()
    fig, axs = nueva_figura("2col", 1, 3)          # 180 mm de ancho, tamaño final real
    ...
    etiqueta_panel(axs[0], "a")                    # (a) fuera, arriba-izquierda
    exportar(fig, "fig05_este_vertical_es")        # PDF + EPS + TIFF(LZW) + PNG

Reglas aplicadas / rules applied
  · Ancho final real (sin reducir después): 1 columna 88 mm, 2 columnas 180 mm. VERIFICAR con SRL.
  · Arial (sustituye a Helvetica), 7 pt base, sin cursivas, sin título interno, (a)(b) fuera arriba-izquierda.
  · Paletas perceptuales (Crameri / viridis / Okabe-Ito), nunca jet; legibles en gris.
  · Ticks externos con EPSG declarado, sin rejilla sobre el ráster, barra de escala métrica, norte discreto.
  · Estiramiento por percentiles 2–98 % (declararlo en el pie).
  · Texto editable: fonttype 42 (PDF/EPS), svg.fonttype none.
"""
import os
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

MM = 1 / 25.4
ANCHOS_MM = {"1col": 88, "1.5col": 130, "2col": 180}   # SRL: confirmar en las guías finales / confirm

# Okabe-Ito (daltónicos): clases discretas, p. ej. daño / discrete classes, e.g. damage
OKABE_ITO = ["#000000", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7"]
CLASES_DANIO = {"no-damage": "#56B4E9", "minor-damage": "#F0E442", "major-damage": "#E69F00", "destroyed": "#D55E00"}

def recortar(cmap, a=0.15, b=0.85, n=256):
    """Recorta los extremos oscuros de una paleta (declarar en el pie: 'colormap truncated 15–85 %')."""
    return ListedColormap(cmap(np.linspace(a, b, n)))


try:
    from cmcrameri import cm as _cm
    CMAPS = {
        "divergente": recortar(_cm.vik),  # LOS, L − C, residuos (centro en 0); vik recortada 15–85 % = más clara / lighter
        "secuencial": _cm.batlow,    # coherencia, retrodispersión, elevación
        "ciclico": _cm.romaO,        # fase interferométrica envuelta
        "relieve": _cm.grayC,        # sombreado / mapa base tenue
    }
except Exception:                    # respaldo si falta cmcrameri / fallback
    CMAPS = {"divergente": mpl.colormaps["RdBu_r"], "secuencial": mpl.colormaps["viridis"],
             "ciclico": mpl.colormaps["twilight"], "relieve": mpl.colormaps["gray"]}


def aplicar_estilo(base=7):
    """rcParams globales / global rcParams."""
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
        "font.size": base, "axes.labelsize": base, "axes.titlesize": base,
        "xtick.labelsize": base - 1, "ytick.labelsize": base - 1, "legend.fontsize": base - 1,
        "axes.linewidth": 0.5, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
        "xtick.major.size": 2.5, "ytick.major.size": 2.5, "xtick.direction": "out", "ytick.direction": "out",
        "axes.grid": False, "axes.spines.top": True, "axes.spines.right": True,
        "lines.linewidth": 0.8, "figure.dpi": 150, "savefig.dpi": 600,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",   # texto editable
        "image.interpolation": "nearest", "image.cmap": "gray",
    })


def nueva_figura(ancho="2col", filas=1, cols=1, alto_mm=None, relacion=0.62, **kw):
    """Figura a tamaño final real (pulgadas = mm/25.4) / figure at true final size."""
    w = ANCHOS_MM[ancho] if isinstance(ancho, str) else ancho
    h = alto_mm if alto_mm else w * relacion
    return plt.subplots(filas, cols, figsize=(w * MM, h * MM), **kw)


def etiqueta_panel(ax, letra, dx=-0.02, dy=1.02):
    """(a) en negrita FUERA del panel, arriba-izquierda / bold label outside, top-left."""
    ax.text(dx, dy, f"({letra})", transform=ax.transAxes, ha="right", va="bottom",
            fontsize=mpl.rcParams["font.size"] + 1, fontweight="bold")


def estirar(arr, p=(2, 98)):
    """Límites por percentiles (ignora NaN). Devuelve (vmin, vmax) / percentile stretch limits."""
    a = np.asarray(arr, dtype=float)
    return tuple(np.nanpercentile(a[np.isfinite(a)], p))


def limites_simetricos(arr, p=98):
    """Para mapas divergentes: ±percentil de |valor|, centro neutro exacto en 0."""
    m = np.nanpercentile(np.abs(np.asarray(arr, dtype=float)[np.isfinite(arr)]), p)
    return -m, m


def ejes_utm(ax, epsg="32619", km=True, etiquetas=("x", "y")):
    """Ticks externos en km UTM, sin rejilla; el EPSG va en el pie de figura / external km ticks."""
    f = (lambda v, _: f"{v/1000:.0f}") if km else None
    if f:
        ax.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(f))
        ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(f))
    ax.set_aspect("equal")
    ax.tick_params(length=2.5, pad=1.5)
    return ax


def barra_escala(ax, longitud_m, texto=None, loc=(0.06, 0.06), color="k"):
    """Barra métrica simple en coordenadas proyectadas (m) / simple metric scale bar (projected m)."""
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    x = x0 + loc[0] * (x1 - x0); y = y0 + loc[1] * (y1 - y0)
    ax.plot([x, x + longitud_m], [y, y], color=color, lw=1.6, solid_capstyle="butt", zorder=9)
    ax.text(x + longitud_m / 2, y + 0.035 * (y1 - y0), texto or f"{longitud_m/1000:g} km",
            ha="center", va="bottom", fontsize=mpl.rcParams["font.size"] - 1, color=color, zorder=9)


def flecha_norte(ax, loc=(0.93, 0.84), largo=0.12, color="k"):
    """Flecha de norte discreta (solo si el mapa no tiene meridianos) / discreet north arrow."""
    ax.annotate("", xy=(loc[0], loc[1]), xytext=(loc[0], loc[1] - largo), xycoords="axes fraction",
                arrowprops=dict(arrowstyle="->", color=color, lw=1.0, mutation_scale=7, shrinkA=0, shrinkB=0), zorder=9)
    ax.text(loc[0], loc[1] + 0.02, "N", transform=ax.transAxes, ha="center", va="bottom",
            fontsize=mpl.rcParams["font.size"] - 1, color=color, zorder=9)


def barra_color(fig, mappable, ax, etiqueta, **kw):
    """Barra de color compartida y delgada, con unidad en la etiqueta / thin shared colour bar."""
    cb = fig.colorbar(mappable, ax=ax, pad=0.015, fraction=0.035, aspect=30, **kw)
    cb.set_label(etiqueta, labelpad=2)
    cb.outline.set_linewidth(0.4)
    cb.ax.tick_params(length=2, width=0.4)
    return cb


def prueba_gris(cmap, n=256):
    """Legibilidad en gris: ¿la luminancia (Rec.709) crece o decrece MONÓTONAMENTE en todo el rango?
    Secuenciales: sí. Divergentes (vik, roma, berlin...): NO, porque ambos signos quedan igual de oscuros
    (o claros) en gris. Para esos mapas SRL en papel exige contornos con signo o anotaciones (ver contornos_signo).
    Devuelve (ok, |Spearman|) / Returns (ok, |Spearman|) for the WHOLE range."""
    from scipy.stats import spearmanr
    rgb = cmap(np.linspace(0, 1, n))[:, :3]
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    lum = lin @ np.array([0.2126, 0.7152, 0.0722])
    rho = abs(spearmanr(np.arange(n), lum)[0])
    return bool(rho > 0.95), round(float(rho), 3)


def contornos_signo(ax, X, Y, Z, niveles=(-10, -5, 5, 10), cero=True):
    """Contornos con signo para que un mapa divergente se lea en gris: continuo (+), discontinuo (−), cero grueso.
    Signed contours so a diverging map stays readable in grey: solid (+), dashed (−), thick zero."""
    cs = ax.contour(X, Y, Z, levels=list(niveles), colors="k", linewidths=0.35,
                    linestyles=[("--" if v < 0 else "-") for v in niveles])
    ax.clabel(cs, fmt=lambda v: f"{v:+g}", fontsize=5, inline=True, inline_spacing=1)
    if cero:
        ax.contour(X, Y, Z, levels=[0], colors="k", linewidths=0.7)
    return cs


def exportar(fig, base, carpeta=".", formatos=("pdf", "eps", "tiff", "png")):
    """Un archivo por formato. EPS no admite transparencia: se evita alfa en capas vectoriales.
    TIFF con compresión LZW a 600 dpi; PNG a 300 dpi para vista previa / one file per format."""
    os.makedirs(carpeta, exist_ok=True)
    rutas = []
    for f in formatos:
        ruta = os.path.join(carpeta, f"{base}.{f}")
        kw = {}
        if f == "tiff":
            kw = dict(dpi=600, pil_kwargs={"compression": "tiff_lzw"})
        elif f == "png":
            kw = dict(dpi=300)
        fig.savefig(ruta, format=("tiff" if f == "tiff" else f), **kw)
        rutas.append((ruta, round(os.path.getsize(ruta) / 1e6, 2)))
    return rutas
