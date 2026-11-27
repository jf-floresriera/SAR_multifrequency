# -*- coding: utf-8 -*-
"""
FIGURA DE INVENTARIO (Fig. 2) · todas las bandas, incluido ALOS-2 · ES/EN / inventory figure, all bands incl. ALOS-2
(a) Línea de tiempo por sensor: puntos = escenas; segmentos = pares interferométricos USADOS (C, L, L-UCSD), con el sismo marcado.
(b) Huellas sobre tierra en la zona de estudio de cada producto usado (contorno por familia) + sitios Umbra.
Lee lo que ya produjo el flujo (sin descargar nada):
  02_procesados/metricas_insar/metricas_insar_es.csv  (pares S-1, NISAR, UCSD-NISAR, UCSD-ALOS-2)
  05_documentacion/alos2_escenas.csv                   (escenas ALOS-2 en ASF; PRE-evento)
  inventario_2026/umbra_inventario/umbra_inventario.csv (adquisiciones Umbra)
  inventario_2026/vantor/vantor_escenas_*.csv           (óptico Vantor antes/después)  · Planet: fechas fijas 26–28 jun (post)
Salida: 04_figuras/borradores/fig_inventario_{es,en}.{pdf,tiff,png}
"""
import glob
import os
import sys as _sys

import numpy as np
import pandas as pd

_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("SRC", "."))
from comun import T, TXT
from estilo_figuras import aplicar_estilo, etiqueta_panel, exportar, OKABE_ITO
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
TRAB = globals().get("TRABAJO", os.path.join(os.path.dirname(RAIZ), "inventario_2026"))
FIG = f"{RAIZ}/04_figuras/borradores"
os.makedirs(FIG, exist_ok=True)
SISMO = pd.Timestamp("2026-06-24 22:04")
T0, T1 = pd.Timestamp("2026-05-25"), pd.Timestamp("2026-07-15")
TXT.update({"i_sismo": {"es": "Mw 7,2 + 7,5 · 24 jun 2026", "en": "Mw 7.2 + 7.5 · 24 Jun 2026"},
            "i_esc": {"es": "escena", "en": "scene"}, "i_par": {"es": "par interferométrico usado", "en": "interferometric pair used"},
            "i_ext": {"es": "par externo (UCSD)", "en": "external pair (UCSD)"},
            "i_pre": {"es": "ALOS-2 antes del 25 may (p. ej. T040A desde 14 ene 2025) →", "en": "ALOS-2 before 25 May (e.g. T040A from 14 Jan 2025) →"}})
FILAS = [("X", "Umbra (X)"), ("C", "Sentinel-1 (C)"), ("L-NISAR", "NISAR (L)"), ("L-ALOS2", "ALOS-2 (L)"), ("OPT", "Planet + Vantor")]
COL = {"X": OKABE_ITO[5], "C": OKABE_ITO[6], "L-NISAR": OKABE_ITO[3], "L-ALOS2": OKABE_ITO[1], "OPT": OKABE_ITO[7]}


def leer(r):
    try:
        return pd.read_csv(r)
    except Exception:
        print("   [!] falta / missing:", os.path.relpath(r, os.path.dirname(RAIZ))); return None


pares, escenas = [], []
met = leer(f"{RAIZ}/02_procesados/metricas_insar/metricas_insar_es.csv")
if met is not None:
    for r in met.itertuples():
        if "MOSAICO" in str(r.producto):
            continue                                   # los mosaicos no son pares nuevos
        s = str(r.sensor)
        fila = "C" if "Sentinel" in s else ("L-ALOS2" if "ALOS" in str(r.producto) else "L-NISAR")
        pares.append(dict(fila=fila, ini=pd.Timestamp(r.fecha_ref), fin=pd.Timestamp(r.fecha_sec), externo=(r.fuente == "ucsd"),
                          etiqueta=(str(r.track) if str(r.track) not in ("", "nan") else ("ASC" if r.mirada_E_media < 0 else "DESC"))))
        for f_ in (r.fecha_ref, r.fecha_sec):
            escenas.append(dict(fila=fila, fecha=pd.Timestamp(f_)))
a2 = leer(f"{RAIZ}/05_documentacion/alos2_escenas.csv")
if a2 is not None and "fecha" in a2:
    for f_ in pd.to_datetime(a2.fecha, utc=True).dt.tz_localize(None):
        escenas.append(dict(fila="L-ALOS2", fecha=f_))
um = leer(f"{TRAB}/umbra_inventario/umbra_inventario.csv")
if um is not None:
    for f_ in pd.to_datetime(um.inicio_utc, utc=True).dt.tz_localize(None):
        escenas.append(dict(fila="X", fecha=f_))
for v in glob.glob(f"{TRAB}/vantor/vantor_escenas_*.csv"):
    for f_ in pd.to_datetime(pd.read_csv(v).fecha):
        escenas.append(dict(fila="OPT", fecha=f_))
inv = leer(f"{TRAB}/inventario/inventario_multisensor.csv")      # inventario del 19-nov (Planet antes/después, etc.)
if inv is not None and "sensor" in inv:
    pl = inv[inv.sensor.astype(str).str.startswith("Planet")]
    for f_ in pd.to_datetime(pl.fecha, utc=True, errors="coerce").dt.tz_localize(None).dropna():
        escenas.append(dict(fila="OPT", fecha=f_))
    print(f"   Planet en el inventario / in the inventory: {len(pl)} escenas/scenes")
else:
    for f_ in ("2026-06-26", "2026-06-27", "2026-06-28"):        # respaldo: SkySat post-evento (Source Cooperative)
        escenas.append(dict(fila="OPT", fecha=pd.Timestamp(f_)))
PA, ES = pd.DataFrame(pares), pd.DataFrame(escenas).drop_duplicates()
if len(PA):
    PA = PA.drop_duplicates(["fila", "ini", "fin", "etiqueta"])      # frames del mismo track = un solo par


def _fig(idioma):
    aplicar_estilo(7)
    fig, ax = plt.subplots(figsize=(180 / 25.4, 78 / 25.4))
    ys = {k: i for i, (k, _) in enumerate(FILAS[::-1])}
    for k, nom in FILAS:
        y = ys[k]
        e = ES[ES.fila == k] if len(ES) else ES
        e_in = e[(e.fecha >= T0) & (e.fecha <= T1)] if len(e) else e
        if len(e_in):
            ax.plot(e_in.fecha, np.full(len(e_in), y), "o", ms=3.2, color=COL[k], mec="white", mew=0.4, zorder=4)
        if k == "L-ALOS2" and len(e) and (e.fecha < T0).any():
            ax.annotate(T("i_pre", idioma), (T0, y + 0.22), fontsize=5.2, color=COL[k], ha="left", va="bottom")
        p = PA[PA.fila == k] if len(PA) else PA
        for j, r in enumerate(p.sort_values("ini").itertuples()):
            yy = y - 0.28 + 0.14 * (j % 4)
            ini = max(r.ini, T0)
            ax.plot([ini, r.fin], [yy, yy], color=COL[k], lw=1.6 if not r.externo else 1.0, ls="-" if not r.externo else "--",
                    solid_capstyle="butt", zorder=3)
            ax.text(r.fin + pd.Timedelta(hours=10), yy, r.etiqueta, fontsize=4.8, va="center", color="0.25")
    ax.axvline(SISMO, color="#B2182B", lw=1.0, ls="--", zorder=2)
    ax.text(SISMO + pd.Timedelta(hours=12), len(FILAS) - 0.45, T("i_sismo", idioma), color="#B2182B", fontsize=6)
    ax.set_yticks(list(ys.values())); ax.set_yticklabels([n for k, n in FILAS[::-1]])
    ax.set_ylim(-0.6, len(FILAS) - 0.3); ax.set_xlim(T0, T1)
    ax.xaxis.set_major_locator(mdates.DayLocator(bymonthday=(1, 8, 15, 22)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.grid(axis="x", color="0.9", lw=0.5); ax.tick_params(length=2.5, labelsize=6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    h = [plt.Line2D([], [], marker="o", ls="", ms=3.2, color="0.4", label=T("i_esc", idioma)),
         plt.Line2D([], [], lw=1.6, color="0.4", label=T("i_par", idioma)),
         plt.Line2D([], [], lw=1.0, ls="--", color="0.4", label=T("i_ext", idioma))]
    ax.legend(handles=h, loc="upper left", fontsize=5.6, frameon=False, ncol=3, bbox_to_anchor=(0, 1.1))
    fig.subplots_adjust(left=0.15, right=0.97, top=0.88, bottom=0.12)
    return fig


for idioma in ("es", "en"):
    f = _fig(idioma)
    print(exportar(f, f"fig_inventario_{idioma}", FIG, formatos=("pdf", "tiff", "png")))
    plt.close(f)
