# -*- coding: utf-8 -*-
"""
MUESTRA DE ESTILO con datos SINTÉTICOS (no son resultados) / STYLE SAMPLE with SYNTHETIC data (not results).
Sirve para aprobar el aspecto de las figuras antes de aplicarlo a los datos reales.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib.pyplot as plt
from estilo_figuras import *

TXT = {
    "es": dict(c="Desplazamiento LOS (cm)", e="Este UTM 19N (km)", n="Norte UTM 19N (km)", a="Sentinel-1 (banda C)",
               b="NISAR (banda L)", d="L − C (cm)", dist="Distancia a la falla (km)", perfil="LOS (cm)",
               falla="Falla San Sebastián", bandaC="C", bandaL="L"),
    "en": dict(c="LOS displacement (cm)", e="Easting UTM 19N (km)", n="Northing UTM 19N (km)", a="Sentinel-1 (C-band)",
               b="NISAR (L-band)", d="L − C (cm)", dist="Distance to fault (km)", perfil="LOS (cm)",
               falla="San Sebastián fault", bandaC="C", bandaL="L"),
}

def figura(idioma, carpeta):
    t = TXT[idioma]; rng = np.random.default_rng(1)
    x = np.linspace(700e3, 760e3, 240); y = np.linspace(1160e3, 1190e3, 120); X, Y = np.meshgrid(x, y)
    d = (Y - 1175e3 - 0.25 * (X - 730e3)) / 1e3                      # distancia firmada a una "falla" ficticia
    C = 14 * np.tanh(d / 3) + rng.normal(0, 0.8, d.shape)
    L = 15 * np.tanh(d / 3.4) + rng.normal(0, 0.5, d.shape)
    C[(d > 6) & (X < 715e3)] = np.nan                                   # zona sin coherencia
    aplicar_estilo(7)
    fig = plt.figure(figsize=(180 * MM, 118 * MM))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 0.62], width_ratios=[1, 1, 1], hspace=0.38, wspace=0.18,
                          left=0.06, right=0.985, top=0.95, bottom=0.09)
    ext = [x[0], x[-1], y[0], y[-1]]
    vmin, vmax = limites_simetricos(np.r_[C[np.isfinite(C)], L.ravel()], 98)
    axs = [fig.add_subplot(gs[0, i]) for i in range(3)]
    for ax, arr, nom, k in [(axs[0], C, t["a"], "a"), (axs[1], L, t["b"], "b")]:
        im = ax.imshow(arr, extent=ext, origin="lower", cmap=CMAPS["divergente"], vmin=vmin, vmax=vmax)
        ax.set_title(nom, fontsize=7, pad=2); etiqueta_panel(ax, k)
    imd = axs[2].imshow(L - C, extent=ext, origin="lower", cmap=CMAPS["divergente"], vmin=-5, vmax=5)
    axs[2].set_title(t["d"], fontsize=7, pad=2); etiqueta_panel(axs[2], "c")
    for i, ax in enumerate(axs):
        ax.plot([700e3, 760e3], [1175e3 + 0.25 * (700e3 - 730e3), 1175e3 + 0.25 * 30e3], color="k", lw=0.8, ls=(0, (4, 2)))
        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3]); ejes_utm(ax)
        ax.set_xlabel(t["e"]); ax.set_ylabel(t["n"] if i == 0 else "")
        if i: ax.set_yticklabels([])
    barra_escala(axs[0], 10e3, "10 km"); flecha_norte(axs[0])
    cb = fig.colorbar(im, ax=axs[:2], orientation="horizontal", pad=0.20, fraction=0.045, aspect=45)
    cb.set_label(t["c"], labelpad=1); cb.outline.set_linewidth(0.4); cb.ax.tick_params(length=2, width=0.4)
    cb2 = fig.colorbar(imd, ax=axs[2], orientation="horizontal", pad=0.20, fraction=0.045, aspect=22)
    cb2.set_label(t["d"], labelpad=1); cb2.outline.set_linewidth(0.4); cb2.ax.tick_params(length=2, width=0.4)
    # panel (d): perfil + (e) dispersión / profile + scatter
    axp = fig.add_subplot(gs[1, :2]); axs_ = fig.add_subplot(gs[1, 2])
    ds = np.linspace(-12, 12, 200)
    axp.plot(ds, 14 * np.tanh(ds / 3), color=OKABE_ITO[5], label=t["bandaC"])
    axp.plot(ds, 15 * np.tanh(ds / 3.4), color=OKABE_ITO[6], label=t["bandaL"], ls="--")
    axp.axvline(0, color="0.5", lw=0.5); axp.set_xlabel(t["dist"]); axp.set_ylabel(t["perfil"])
    axp.legend(frameon=False, loc="upper left", ncol=2, handlelength=1.6); etiqueta_panel(axp, "d")
    m = np.isfinite(C); cc, ll = C[m][::40], L[m][::40]
    axs_.scatter(cc, ll, s=1.2, c="0.35", alpha=1, edgecolors="none", rasterized=True)
    lim = [-18, 18]; axs_.plot(lim, lim, color="k", lw=0.5); axs_.set_xlim(lim); axs_.set_ylim(lim); axs_.set_aspect("equal")
    r2 = np.corrcoef(cc, ll)[0, 1] ** 2; rmse = np.sqrt(np.mean((ll - cc) ** 2))
    axs_.text(0.04, 0.96, f"$R^2$ = {r2:.2f}\nRMSE = {rmse:.1f} cm\nn = {len(cc):,}", transform=axs_.transAxes, va="top", fontsize=6)
    axs_.set_xlabel(f"{t['bandaC']} (cm)"); axs_.set_ylabel(f"{t['bandaL']} (cm)"); etiqueta_panel(axs_, "e")
    return exportar(fig, f"demo_estilo_{idioma}", carpeta)

if __name__ == "__main__":
    carpeta = sys.argv[1] if len(sys.argv) > 1 else "demo_estilo"
    for i in ("es", "en"):
        for r in figura(i, carpeta): print(r)
    for n in ("divergente", "secuencial", "ciclico"):
        print("prueba gris", n, prueba_gris(CMAPS[n]))
