# -*- coding: utf-8 -*-
"""Compara paletas científicas (Crameri) en color y en gris sobre el mismo campo sintético.
Compares scientific colour maps in colour and grey on the same synthetic field. Datos sintéticos / synthetic data."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib.pyplot as plt
from cmcrameri import cm
from estilo_figuras import aplicar_estilo, MM, exportar, prueba_gris

def campo():
    x = np.linspace(-1, 1, 220); X, Y = np.meshgrid(x, x * 0.55)
    return 15 * np.tanh((Y - 0.25 * X) / 0.12) * np.exp(-(X / 1.6) ** 2) + 3 * np.sin(6 * X) * np.cos(4 * Y)

def hoja(carpeta="."):
    aplicar_estilo(7)
    z = campo()
    div = ["vik", "roma", "berlin", "managua", "vanimo", "broc"]
    sec = ["batlow", "lajolla", "oslo", "turku", "bilbao", "lipari"]
    fig, axs = plt.subplots(4, 6, figsize=(180 * MM, 112 * MM), gridspec_kw=dict(hspace=0.55, wspace=0.08))
    for fila, (nombres, lim) in enumerate([(div, (-15, 15)), (sec, (-15, 15))]):
        for j, n in enumerate(nombres):
            cmap = getattr(cm, n); ax, ag = axs[2 * fila, j], axs[2 * fila + 1, j]
            ax.imshow(z, cmap=cmap, vmin=lim[0], vmax=lim[1]); ok, rho = prueba_gris(cmap)
            ax.set_title(f"{n}", fontsize=7, pad=2, fontweight="bold")
            g = cmap(np.linspace(0, 1, 256))[:, :3]; lum = (g @ np.array([0.299, 0.587, 0.114]))
            from matplotlib.colors import ListedColormap
            ag.imshow(z, cmap=ListedColormap(np.c_[lum, lum, lum]), vmin=lim[0], vmax=lim[1])
            ag.set_xlabel("signo legible en gris: " + ("sí" if ok else "no") + " / sign readable in grey: " + ("yes" if ok else "no"), fontsize=5, labelpad=1)
            for a in (ax, ag): a.set_xticks([]); a.set_yticks([])
    axs[0, 0].set_ylabel("divergentes\ndiverging", fontsize=7); axs[2, 0].set_ylabel("secuenciales\nsequential", fontsize=7)
    return exportar(fig, "paletas_comparacion", carpeta, formatos=("png", "pdf"))

if __name__ == "__main__":
    print(hoja(sys.argv[1] if len(sys.argv) > 1 else "."))
