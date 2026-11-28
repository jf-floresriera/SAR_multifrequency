# -*- coding: utf-8 -*-
"""
Utilidades comunes: salidas bilingües (ES/EN) y registro (logs).
Common utilities: bilingual outputs (ES/EN) and logging.

Convención de nombres / Naming convention
  · Tablas / tables : <nombre>.csv (español, la usa el flujo)  +  <nombre>_en.csv (inglés)
  · Figuras / figures: <nombre>_es.png  +  <nombre>_en.png   (y .pdf cuando se pide)
"""
import contextlib
import datetime
import io
import os
import sys
import traceback

IDIOMAS = ("es", "en")

# --------------------------------------------------------------------------
# Textos de figuras / Figure strings
# --------------------------------------------------------------------------
TXT = {
    # generales
    "sismo": {"es": "Mw 7.2 + 7.5\n24 jun 2026", "en": "Mw 7.2 + 7.5\n24 Jun 2026"},
    "dias_desde_sismo": {"es": "Días desde el sismo", "en": "Days since the earthquake"},
    "longitud": {"es": "Longitud (°)", "en": "Longitude (°)"},
    "latitud": {"es": "Latitud (°)", "en": "Latitude (°)"},
    "este_km": {"es": "Este UTM 19N (km)", "en": "Easting UTM 19N (km)"},
    "norte_km": {"es": "Norte (km)", "en": "Northing (km)"},
    # umbra_inventario
    "umbra_mapa_tit": {"es": "Adquisiciones Umbra (banda X) – Sismo de Venezuela 2026",
                       "en": "Umbra acquisitions (X-band) – 2026 Venezuela earthquake"},
    # nisar_filtrar
    "nisar_mapa_tit": {"es": "Cobertura NISAR (banda L) y Umbra (banda X) – Sismo de Venezuela 24/06/2026",
                       "en": "NISAR (L-band) and Umbra (X-band) coverage – Venezuela earthquake 24 Jun 2026"},
    "gunw_COSISMICO": {"es": "GUNW cosísmico", "en": "GUNW coseismic"},
    "gunw_PRE-SISMICO": {"es": "GUNW pre-sísmico", "en": "GUNW pre-seismic"},
    "gunw_POST-SISMICO": {"es": "GUNW post-sísmico", "en": "GUNW post-seismic"},
    "roi_guaira": {"es": "Zona de estudio La Guaira", "en": "La Guaira study area"},
    # inventario_multisensor
    "linea_tit": {"es": "Adquisiciones disponibles por sensor (±30 días del sismo)\nPuntos: escenas · Segmentos: pares interferométricos",
                  "en": "Available acquisitions per sensor (±30 days of the earthquake)\nDots: scenes · Segments: interferometric pairs"},
    # umbra_planet_sitios
    "pl_antes": {"es": "(a) Planet antes · Q1-2026 · 4.8 m", "en": "(a) Planet before · Q1-2026 · 4.8 m"},
    "pl_despues": {"es": "(b) Planet después · {t} · {g} m", "en": "(b) Planet after · {t} · {g} m"},
    "um_amp": {"es": "(c) Umbra X amplitud (dB, Lee) · {t} · mirada {m}",
               "en": "(c) Umbra X amplitude (dB, Lee) · {t} · {m} look"},
    "um_tex": {"es": "(d) Umbra textura · CV local 9×9", "en": "(d) Umbra texture · local CV 9×9"},
    "um_ndli": {"es": "(e) NDLI = (izq − der)/(izq + der)", "en": "(e) NDLI = (left − right)/(left + right)"},
    "coh_nisar": {"es": "(c) Coherencia NISAR · {f}", "en": "(c) NISAR coherence · {f}"},
    "zoom": {"es": "Acercamiento {z} m", "en": "Zoom {z} m"},
    "sitio_tit": {"es": "{s} ({lat:.4f}° N, {lon:.4f}° W) · {L} m · cobertura Umbra {c:.0%}{d}",
                  "en": "{s} ({lat:.4f}° N, {lon:.4f}° W) · {L} m · Umbra coverage {c:.0%}{d}"},
    "desplazado": {"es": " · recorte desplazado {m:.0f} m", "en": " · chip shifted {m:.0f} m"},
    "left": {"es": "izquierda", "en": "left"},
    "right": {"es": "derecha", "en": "right"},
    # descomposicion
    "E_C": {"es": "Sentinel-1 (C) · Este", "en": "Sentinel-1 (C) · East"},
    "E_L": {"es": "NISAR (L) · Este", "en": "NISAR (L) · East"},
    "E_LC": {"es": "L − C · Este", "en": "L − C · East"},
    "U_C": {"es": "Sentinel-1 (C) · Vertical", "en": "Sentinel-1 (C) · Up"},
    "U_L": {"es": "NISAR (L) · Vertical", "en": "NISAR (L) · Up"},
    "U_LC": {"es": "L − C · Vertical", "en": "L − C · Up"},
}


def T(clave, idioma, **kw):
    s = TXT[clave][idioma]
    return s.format(**kw) if kw else s


# --------------------------------------------------------------------------
# Tablas / Tables
# --------------------------------------------------------------------------
COLS_EN = {
    "sitio": "site", "lat": "lat", "lon": "lon", "n_umbra": "n_umbra", "miradas": "looks",
    "n_planet_post": "n_planet_post", "cobertura": "coverage", "desplazamiento_m": "shift_m",
    "escenas_umbra": "umbra_scenes", "figura": "figure", "umbra": "umbra",
    "nivel": "level", "nombre": "name", "direccion": "direction", "fecha_ref": "reference_date",
    "fecha_sec": "secondary_date", "dias": "days", "tipo": "type", "cubre_LaGuaira_%": "covers_LaGuaira_%",
    "escenas_Umbra_que_toca": "umbra_scenes_overlapping", "en_UCSD": "in_UCSD",
    "carpeta": "folder", "inicio_utc": "start_utc", "fin_utc": "end_utc", "satelite": "satellite",
    "modo": "mode", "incidencia_deg": "incidence_deg", "azimut_deg": "azimuth_deg",
    "direccion_mirada": "look_direction", "orbita": "orbit", "res_rango_m": "range_resolution_m",
    "res_azimut_m": "azimuth_resolution_m", "polarizacion": "polarization", "lat_centro": "center_lat",
    "lon_centro": "center_lon", "productos": "products", "tamano_GB": "size_GB",
    "sensor": "sensor", "banda": "band", "lambda_cm": "wavelength_cm", "tipo_producto": "product_type",
    "fecha": "date", "relacion_sismo": "relation_to_earthquake", "track_o_sitio": "track_or_site",
    "resolucion_m": "resolution_m", "licencia": "license", "fuente": "source",
    "usado_en_notebook": "used_in_notebook", "dias_desde_sismo": "days_since_earthquake",
    "ref": "reference", "sec": "secondary", "cubre_LaGuaira": "covers_LaGuaira_%",
    "producto": "product", "fecha_acceso": "access_date", "familia": "family",
    "task_a": "task_a", "fecha_a": "date_a", "task_b": "task_b", "fecha_b": "date_b",
    "dist_km": "dist_km", "d_incid": "d_incidence", "d_squint": "d_squint", "ambos_SICD": "both_SICD",
    "escena": "scene", "estado": "status", "enviado": "submitted", "terminado": "processing_times", "expira": "expires", "escenas": "scenes", "path": "path", "frame": "frame", "GB": "GB", "relacion": "relation",
}
VALORES_EN = {
    "COSISMICO": "COSEISMIC", "PRE-SISMICO": "PRE-SEISMIC", "POST-SISMICO": "POST-SEISMIC",
    "SIN_FECHAS": "NO_DATES", "Óptico": "Optical", "Copernicus (libre)": "Copernicus (free)",
    "NASA (libre)": "NASA (free)", "CC BY-NC 4.0 (no comercial)": "CC BY-NC 4.0 (non-commercial)",
    "ISRO (registro)": "ISRO (registration)", "mosaico trimestral RGB": "quarterly RGB mosaic",
    "PlanetScope mosaico": "PlanetScope mosaic", "Planet PlanetScope mosaico": "Planet PlanetScope mosaic",
    "Sentinel-1 (par HyP3)": "Sentinel-1 (HyP3 pair)",
}


def csv_bilingue(df, ruta, index=False):
    """Guarda <ruta>.csv (ES) y <ruta>_en.csv (EN). `ruta` puede venir con o sin .csv."""
    base = ruta[:-4] if ruta.endswith(".csv") else ruta
    df.to_csv(f"{base}.csv", index=index)
    en = df.rename(columns=lambda c: COLS_EN.get(c, c))
    if getattr(en.index, "names", None):
        en.index = en.index.set_names([COLS_EN.get(n, n) for n in en.index.names])
    en = en.rename(columns=lambda c: COLS_EN.get(c, c) if isinstance(c, str) else c)
    import pandas as pd
    for c in en.columns:
        if not pd.api.types.is_numeric_dtype(en[c]) and not pd.api.types.is_datetime64_any_dtype(en[c]):
            en[c] = en[c].replace(VALORES_EN)
    if index:
        en.index = en.index.map(lambda v: tuple(VALORES_EN.get(x, x) for x in v) if isinstance(v, tuple)
                                else VALORES_EN.get(v, v))
    en.columns = [VALORES_EN.get(c, c) if isinstance(c, str) else c for c in en.columns]
    en.to_csv(f"{base}_en.csv", index=index)


def guardar_bilingue(dibujar, base, formatos=("pdf", "eps", "tiff", "png"), dpi=300, mostrar=True):
    """dibujar(idioma) -> figura. Guarda <base>_es.<fmt> y <base>_en.<fmt> en PDF, EPS, TIFF y PNG (siempre los cuatro,
    aunque se pidan menos); muestra solo la ES. Always saves ES and EN in all four formats."""
    import matplotlib.pyplot as plt
    rutas = []
    for idioma in IDIOMAS:
        fig = dibujar(idioma)
        for fmt in dict.fromkeys(tuple(formatos) + ("pdf", "eps", "tiff", "png")):
            r = f"{base}_{idioma}.{fmt}"
            kw = dict(dpi=600, pil_kwargs={"compression": "tiff_lzw"}) if fmt == "tiff" else dict(dpi=dpi)
            try:
                fig.savefig(r, format=fmt, bbox_inches="tight", **kw)
                rutas.append(r)
            except Exception as e:
                print(f"   ⚠️ {os.path.basename(r)} no se pudo guardar / could not be saved: {str(e)[:80]}")
        if mostrar and idioma == "es":
            plt.show()
        plt.close(fig)
    print("   guardado / saved:", ", ".join(os.path.basename(r) for r in rutas))
    return rutas


# --------------------------------------------------------------------------
# Registro de ejecución / Run logging
# --------------------------------------------------------------------------
class _Tee(io.TextIOBase):
    def __init__(self, *flujos):
        self.flujos = flujos

    def write(self, s):
        for f in self.flujos:
            if not getattr(f, "closed", False):
                f.write(s)
        return len(s)

    def flush(self):
        for f in self.flujos:
            if not getattr(f, "closed", False):
                f.flush()


def correr(script, carpeta_logs, src, notebook="", version=""):
    """Ejecuta src/<script> con %run -i y guarda TODO lo impreso (y errores) en un .log en Drive.
    Runs src/<script> with %run -i and saves ALL printed output (and errors) to a .log in Drive."""
    from IPython import get_ipython
    # git pull automático antes de cada script: así una corrección subida a GitHub se usa sin volver a correr la celda 0.
    # Automatic git pull before each script, so fixes pushed to GitHub are used without re-running cell 0.
    import subprocess
    repo = os.path.dirname(os.path.abspath(src))
    if os.path.isdir(os.path.join(repo, ".git")):
        try:
            antes = subprocess.run(["git", "-C", repo, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
            subprocess.run(["git", "-C", repo, "pull", "-q", "--ff-only"], capture_output=True, text=True, timeout=60)
            ahora = subprocess.run(["git", "-C", repo, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
            if ahora and ahora != antes:
                nuevos = subprocess.run(["git", "-C", repo, "log", "--oneline", "--no-merges", f"{antes}..{ahora}"],
                                        capture_output=True, text=True).stdout.strip()
                print(f"🔄 Código actualizado desde GitHub / code updated: {antes} → {ahora}\n{nuevos}\n")
                version = ahora
        except Exception as e:
            print(f"(sin git pull / no git pull: {str(e)[:60]}; se usa el código actual / using current code)")
    os.makedirs(carpeta_logs, exist_ok=True)
    marca = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(carpeta_logs, f"{marca}_{notebook}_{script.replace('.py', '')}.log")
    with open(ruta, "w", encoding="utf-8") as log:
        log.write(f"# script: {script}\n# notebook: {notebook}\n# version: {version}\n# inicio/start: {marca}\n\n")
        out, err = sys.stdout, sys.stderr
        try:
            with contextlib.redirect_stdout(_Tee(out, log)), contextlib.redirect_stderr(_Tee(err, log)):
                ruta_script = os.path.join(src, script)
                # módulos auxiliares del proyecto (estilo_figuras, mascaras, registro_datos…): se descartan de la memoria para que
                # siempre se use la versión recién bajada con git pull (si no, Python reutiliza la vieja y falla el import).
                # Project helper modules are dropped from memory so the freshly pulled version is always used.
                for _m in [m for m, mod in list(sys.modules.items())
                           if m not in ("comun", "maestro") and not m.startswith("_") and getattr(mod, "__file__", None)
                           and os.path.dirname(os.path.abspath(mod.__file__)) == os.path.abspath(src)]:
                    del sys.modules[_m]
                sys.modules.setdefault("__main__", get_ipython().user_module)   # repara sesiones afectadas por el error anterior
                ns = get_ipython().user_ns          # equivalente a %run -i / same as %run -i
                ns["__file__"] = ruta_script
                exec(compile(open(ruta_script, encoding="utf-8").read(), ruta_script, "exec"), ns)
        except BaseException:
            log.write("\n# ERROR\n" + traceback.format_exc())
            raise
        finally:
            log.write(f"\n# fin/end: {datetime.datetime.now():%Y%m%d_%H%M%S}\n")
    print(f"\n📝 Registro / log: {ruta}")
    return ruta
