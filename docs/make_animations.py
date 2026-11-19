# -*- coding: utf-8 -*-
"""
Genera las animaciones (GIF) del README a partir del inventario real del proyecto.
Uso:  python docs/make_animations.py      -> docs/img/*.gif
Datos: fechas y posiciones tomadas de las salidas de los notebooks (inventario 2026-11-19).
"""
import os
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import FancyBboxPatch, Rectangle

OUT = os.path.join(os.path.dirname(__file__), "img")
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})

SISMO = datetime(2026, 6, 24, 22, 4, 33)
COL = {"X": "#4C72B0", "C": "#DD8452", "L": "#55A868", "OPT": "#937860", "Q": "#C44E52"}

# --------------------------------------------------------------------------
# Inventario (UTC)
# --------------------------------------------------------------------------
S1_PARES = [("Sentinel-1 033A", datetime(2026, 6, 18, 22, 42), datetime(2026, 6, 25, 22, 42)),
            ("Sentinel-1 025D", datetime(2026, 6, 18, 10, 16), datetime(2026, 6, 25, 10, 16))]
NISAR_PARES = [("NISAR 162A", datetime(2026, 6, 13, 10, 7), datetime(2026, 6, 25, 10, 7)),
               ("NISAR 061A", datetime(2026, 6, 18, 9, 58), datetime(2026, 6, 30, 9, 59)),
               ("NISAR 126D", datetime(2026, 6, 22, 22, 54), datetime(2026, 7, 4, 22, 54))]
UMBRA = [  # (utc, lon, lat, satélite, mirada)
    ("2026-06-26 15:43", -67.793, 10.461, "U10", "R"), ("2026-06-26 15:43", -67.774, 10.428, "U10", "R"),
    ("2026-06-26 15:43", -67.755, 10.461, "U10", "R"), ("2026-06-27 01:15", -66.489, 10.454, "U07", "L"),
    ("2026-06-27 01:16", -66.508, 10.487, "U07", "L"), ("2026-06-27 01:16", -66.546, 10.487, "U07", "L"),
    ("2026-06-27 01:16", -66.527, 10.454, "U07", "L"), ("2026-06-27 03:40", -67.755, 10.395, "U10", "L"),
    ("2026-06-27 03:40", -67.736, 10.428, "U10", "L"), ("2026-06-27 03:40", -68.695, 10.628, "U09", "L"),
    ("2026-06-27 03:41", -68.656, 10.628, "U09", "L"), ("2026-06-27 03:41", -68.675, 10.595, "U09", "L"),
    ("2026-06-28 03:24", -66.566, 10.454, "U10", "L"), ("2026-06-28 03:24", -66.642, 10.455, "U09", "L"),
    ("2026-06-28 03:24", -66.584, 10.487, "U10", "L"), ("2026-06-28 03:24", -66.661, 10.488, "U09", "L"),
    ("2026-06-28 03:25", -66.604, 10.455, "U10", "L"), ("2026-06-28 03:25", -66.681, 10.455, "U09", "L"),
    ("2026-06-28 03:25", -66.700, 10.488, "U09", "L"), ("2026-06-30 16:11", -66.987, 10.589, "U10", "L"),
    ("2026-06-30 16:11", -67.025, 10.589, "U10", "L"), ("2026-06-30 16:11", -66.948, 10.588, "U10", "L"),
    ("2026-06-30 16:12", -66.796, 10.456, "U09", "L"), ("2026-06-30 16:12", -66.910, 10.588, "U10", "L"),
    ("2026-06-30 16:12", -66.776, 10.489, "U09", "L"), ("2026-07-02 03:52", -67.011, 10.610, "U10", "R"),
]
UMBRA = [(datetime.strptime(t, "%Y-%m-%d %H:%M"), lo, la, s, m) for t, lo, la, s, m in UMBRA]
PLANET = [datetime.strptime(s, "%Y%m%d_%H%M%S") for s in (
    "20260626_112057", "20260626_123541", "20260626_150535", "20260627_112621", "20260627_112651",
    "20260627_112722", "20260627_145824", "20260628_115115", "20260628_122047")]
LUGARES = {"Yumare": (-68.69, 10.62), "Puerto Cabello": (-68.01, 10.47), "Ocumare": (-67.77, 10.46),
           "Maracay": (-67.60, 10.25), "Catia La Mar": (-67.03, 10.60), "La Guaira": (-66.93, 10.60),
           "Caracas": (-66.90, 10.49), "Guarenas": (-66.61, 10.47), "Guatire": (-66.54, 10.47)}


# --------------------------------------------------------------------------
# 1. Línea de tiempo animada
# --------------------------------------------------------------------------
def anim_linea_tiempo():
    filas = ["Umbra (X)", "Sentinel-1 (C)", "NISAR (L)", "Planet (óptico)"]
    y = {f: i for i, f in enumerate(filas[::-1])}
    t0, t1 = datetime(2026, 6, 11), datetime(2026, 7, 6)
    pasos = [t0 + timedelta(hours=12 * i) for i in range(int((t1 - t0).total_seconds() / 43200) + 1)]
    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=100)

    def dibujar(k):
        ahora = pasos[k]
        ax.clear()
        ax.set_xlim(t0, t1); ax.set_ylim(-0.7, len(filas) - 0.3)
        ax.set_yticks(list(y.values())); ax.set_yticklabels(list(y.keys()))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        ax.grid(axis="x", color="0.92")
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        if ahora >= SISMO:
            ax.axvline(SISMO, color=COL["Q"], lw=1.8, ls="--")
            ax.text(SISMO, len(filas) - 0.45, " Mw 7.2 + 7.5", color=COL["Q"], fontsize=9, weight="bold")
        for i, (nom, a, b) in enumerate(S1_PARES):
            if ahora >= a:
                fin = min(ahora, b)
                ax.plot([a, fin], [y["Sentinel-1 (C)"] + 0.12 * (i - 0.5)] * 2, color=COL["C"], lw=3,
                        solid_capstyle="round")
        for i, (nom, a, b) in enumerate(NISAR_PARES):
            if ahora >= a:
                fin = min(ahora, b)
                ax.plot([a, fin], [y["NISAR (L)"] + 0.14 * (i - 1)] * 2, color=COL["L"], lw=3,
                        solid_capstyle="round")
        u = [t for t, *_ in UMBRA if t <= ahora]
        ax.plot(u, [y["Umbra (X)"]] * len(u), "o", color=COL["X"], ms=7, mec="white")
        p = [t for t in PLANET if t <= ahora]
        ax.plot(p, [y["Planet (óptico)"]] * len(p), "s", color=COL["OPT"], ms=6, mec="white")
        ax.set_title(f"Adquisiciones disponibles · {ahora:%d %b %Y}   "
                     f"(Umbra {len(u)}/26 · Planet {len(p)} · pares InSAR "
                     f"{sum(a <= ahora for _, a, _ in S1_PARES + NISAR_PARES)}/5)",
                     loc="left", fontsize=10)
        fig.tight_layout()

    an = FuncAnimation(fig, dibujar, frames=len(pasos), interval=180)
    an.save(f"{OUT}/linea_tiempo_sensores.gif", writer=PillowWriter(fps=6))
    plt.close(fig)


# --------------------------------------------------------------------------
# 2. Mapa animado de adquisiciones Umbra por día
# --------------------------------------------------------------------------
def anim_mapa_umbra():
    dias = sorted({t.date() for t, *_ in UMBRA})
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=100)

    def dibujar(k):
        ax.clear()
        ax.set_xlim(-68.85, -66.35); ax.set_ylim(10.15, 10.8)
        ax.set_aspect("equal")
        ax.set_facecolor("#F4F7FA")
        ax.add_patch(Rectangle((-67.3, 10.4), 0.6, 0.4, fill=False, ec="#999", ls=":", lw=1))
        ax.text(-67.29, 10.785, "ROI La Guaira", fontsize=7, color="#777")
        desp = {"Catia La Mar": (-0.16, 0.05), "La Guaira": (0.0, 0.05), "Guarenas": (-0.09, -0.06),
                "Guatire": (0.01, 0.04), "Caracas": (0.01, -0.05)}
        for n, (lo, la) in LUGARES.items():
            dx, dy = desp.get(n, (0.01, -0.035))
            ax.plot(lo, la, ".", color="0.3", ms=4)
            ax.text(lo + dx, la + dy, n, fontsize=7, color="0.25")
        for t, lo, la, s, m in UMBRA:
            if t.date() <= dias[k]:
                actual = t.date() == dias[k]
                ax.add_patch(Rectangle((lo - 0.023, la - 0.023), 0.046, 0.046,
                                       fc=COL["X"] if m == "L" else "#8172B3",
                                       alpha=0.85 if actual else 0.35, ec="white", lw=0.6))
        n = sum(t.date() <= dias[k] for t, *_ in UMBRA)
        ax.set_title(f"Umbra banda X · {dias[k]:%d %b %Y} · {n}/26 escenas  "
                     "(azul = mirada izq., morado = mirada der.)", loc="left", fontsize=10)
        ax.set_xlabel("Longitud (°)"); ax.set_ylabel("Latitud (°)")
        ax.text(-66.36, 10.16, "Contains Umbra open data, CC BY 4.0", ha="right", fontsize=6.5, color="0.4")
        fig.tight_layout()

    an = FuncAnimation(fig, dibujar, frames=len(dias), interval=900)
    an.save(f"{OUT}/mapa_umbra_por_dia.gif", writer=PillowWriter(fps=1.2))
    plt.close(fig)


# --------------------------------------------------------------------------
# 3. Diagrama animado del flujo de trabajo
# --------------------------------------------------------------------------
def anim_flujo():
    cajas = [
        ("Datos abiertos", "Sentinel-1 · NISAR · ALOS-2\nUmbra · Planet · GNSS", 0.5, 0.88, "#E8EEF7"),
        ("1 · Inventario", "filtro cosísmico · huellas\nlicencias · fechas de acceso", 0.5, 0.72, "#E8EEF7"),
        ("2a · InSAR C y L", "fase → LOS (m) · coherencia\nionosfera · grilla común 80 m", 0.25, 0.54, "#E9F4EC"),
        ("2b · Daño X + óptico", "Umbra GEC × Planet\nantes / después", 0.75, 0.54, "#F1ECF6"),
        ("3 · Este / Vertical", "asc + desc · banda C vs L\nvalidación GNSS CCS1", 0.25, 0.36, "#E9F4EC"),
        ("4 · Integración", "daño vs gradiente de deformación\ndistancia a la falla", 0.5, 0.20, "#FBEFE5"),
        ("5 · Publicación", "SRL Focus Section 2026\nGitHub + Zenodo (DOI)", 0.5, 0.05, "#FCE9EA"),
    ]
    flechas = [(0, 1), (1, 2), (1, 3), (2, 4), (4, 5), (3, 5), (5, 6)]
    orden = [0, 1, 2, 3, 4, 5, 6]
    fig, ax = plt.subplots(figsize=(8, 7), dpi=100)

    def dibujar(k):
        ax.clear(); ax.set_xlim(0, 1); ax.set_ylim(-0.03, 0.97); ax.axis("off")
        activos = set(orden[:k + 1])
        for a, b in flechas:
            if a in activos and b in activos:
                ax.annotate("", xy=(cajas[b][2], cajas[b][3] + 0.055), xytext=(cajas[a][2], cajas[a][3] - 0.055),
                            arrowprops=dict(arrowstyle="-|>", color="0.35", lw=1.4))
        for i, (t, sub, x, yy, c) in enumerate(cajas):
            on = i in activos
            ax.add_patch(FancyBboxPatch((x - 0.2, yy - 0.05), 0.4, 0.1, boxstyle="round,pad=0.01",
                                        fc=c if on else "#F5F5F5", ec="0.3" if on else "0.85",
                                        lw=1.6 if i == orden[min(k, len(orden) - 1)] else 0.8))
            ax.text(x, yy + 0.018, t, ha="center", va="center", fontsize=10.5, weight="bold",
                    color="0.1" if on else "0.75")
            ax.text(x, yy - 0.022, sub, ha="center", va="center", fontsize=8, color="0.3" if on else "0.8")
        ax.set_title("GUAIRA-SAR · flujo de trabajo reproducible", fontsize=12, weight="bold", loc="left")
        fig.tight_layout()

    an = FuncAnimation(fig, dibujar, frames=len(orden) + 3, interval=800)
    an.save(f"{OUT}/flujo_trabajo.gif", writer=PillowWriter(fps=1.25))
    plt.close(fig)


if __name__ == "__main__":
    anim_linea_tiempo()
    anim_mapa_umbra()
    anim_flujo()
    for f in sorted(os.listdir(OUT)):
        print(f, round(os.path.getsize(f"{OUT}/{f}") / 1e6, 2), "MB")
