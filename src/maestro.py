# -*- coding: utf-8 -*-
"""
Motor del cuaderno maestro: una sola lista de pasos, cada uno se ejecuta UNA vez y luego se salta.
Master-notebook engine: one list of steps; each runs ONCE and is then skipped.

· El historial vive en Drive: <RAIZ>/05_documentacion/pasos_ejecutados.csv  (id, fecha, versión, estado, origen).
· Los pasos que ya se hicieron antes de existir este cuaderno están en HECHO_PREVIO (con la evidencia).
· `paso("id")` no repite lo hecho; `paso("id", forzar=True)` lo repite a propósito.
· Los pasos que gastan créditos de HyP3 piden confirmación explícita (`confirmar=True`).
"""
import os
import datetime
import pandas as pd

# id, fase, script, descripción ES, descripción EN
PASOS = [
    ("inv_umbra",   "A Inventario", "umbra_inventario.py",          "Umbra X: 26 adquisiciones, STAC, huellas",           "Umbra X: 26 collects, STAC, footprints"),
    ("inv_nisar",   "A Inventario", "nisar_filtrar.py",             "NISAR L: GUNW cosísmicos",                           "NISAR L: coseismic GUNW"),
    ("inv_s1",      "A Inventario", "s1_pares_hyp3.py",             "Sentinel-1 C: pares cosísmicos (solo búsqueda)",     "Sentinel-1 C: coseismic pairs (search only)"),
    ("inv_alos2",   "A Inventario", "alos2_buscar.py",              "ALOS-2 L: búsqueda en ASF",                          "ALOS-2 L: ASF search"),
    ("inv_tabla",   "A Inventario", "inventario_multisensor.py",    "Tabla maestra y línea de tiempo (suplemento)",       "Master table and timeline (supplement)"),
    ("mapas_base",  "A Inventario", "mapas_base.py",                "Mapas base y figura de ubicación (Fig. 1)",          "Base maps and location figure (Fig. 1)"),
    ("hyp3_estado", "B Descargas",  "hyp3_estado.py",               "Estado de HyP3 y descarga de lo terminado",          "HyP3 status and download of finished jobs"),
    ("hyp3_envio",  "B Descargas",  "s1_pares_hyp3.py",             "Enviar a HyP3 (SOLO lo que no existe; gasta créditos)", "Submit to HyP3 (ONLY what does not exist; uses credits)"),
    ("descargas",   "B Descargas",  "descargas.py",                 "NISAR, Umbra GEC y Sentinel-1 a Drive",              "NISAR, Umbra GEC and Sentinel-1 to Drive"),
    ("auxiliares",  "C InSAR",      "auxiliares.py",                "Réplicas USGS y WorldCover",                         "USGS aftershocks and WorldCover"),
    ("nisar_tif",   "C InSAR",      "nisar_gunw_a_geotiff.py",      "NISAR GUNW → GeoTIFF (LOS, coherencia)",             "NISAR GUNW → GeoTIFF (LOS, coherence)"),
    ("s1_tif",      "C InSAR",      "s1_hyp3_a_geotiff.py",         "Sentinel-1 HyP3 → GeoTIFF (LOS, coherencia)",        "Sentinel-1 HyP3 → GeoTIFF (LOS, coherence)"),
    ("descomp",     "C InSAR",      "descomposicion_C_L.py",        "Este/Vertical C y L, L − C, validación GNSS",        "East/Up C and L, L − C, GNSS validation"),
    ("ucsd_los",    "C InSAR",      "ucsd_los_a_geotiff.py",        "ALOS-2 y NISAR procesados por UCSD → GeoTIFF (7 tracks)",  "UCSD-processed ALOS-2 and NISAR → GeoTIFF (7 tracks)"),
    ("auditoria",   "C InSAR",      "auditar_correcciones.py",      "Auditoría: qué correcciones traen los productos",    "Audit: which corrections the products carry"),
    ("insar_metricas", "C InSAR",   "insar_metricas.py",            "Métricas y mapas/perfil COMPARABLES (misma escala y ventana)", "COMPARABLE metrics, maps and profile (same scale and window)"),
    ("danio_ref",   "D Daño",       "danio_referencia.py",          "Daño de referencia HOTOSM + Copernicus EMS",         "Reference damage HOTOSM + Copernicus EMS"),
    ("vantor",      "D Daño",       "vantor_buscar.py",             "Óptico ~0,4 m ANTES/DESPUÉS (Vantor abierto) por sitio",  "~0.4 m optical PRE/POST (Vantor open data) per site"),
    ("danio_sitios", "D Daño",      "umbra_planet_sitios.py",       "Umbra × Planet por sitio (Fig. 8 y suplemento)",     "Umbra × Planet per site (Fig. 8 and supplement)"),
    ("exportar",    "E Salida",     "exportar_figuras_github.py",   "Preparar figuras para GitHub (sin Planet/Esri)",     "Prepare figures for GitHub (no Planet/Esri)"),
]
IDS = [p[0] for p in PASOS]
SIEMPRE = {"hyp3_estado", "descargas", "exportar"}     # idempotentes por diseño: se pueden correr siempre / idempotent: safe to always run

# Hecho ANTES de este cuaderno (19-nov-2026), con la evidencia encontrada en Drive. Es evidencia de que el paso
# se ejecutó, no una verificación del contenido de sus salidas. / Done BEFORE this notebook, with Drive evidence.
HECHO_PREVIO = {
    "inv_umbra":    "2026-11-19 · carpeta/folder inventario_2026/umbra_inventario",
    "inv_nisar":    "2026-11-19 · inventario_2026/nisar_filtrado/nisar_productos.csv",
    "inv_s1":       "2026-11-19 · trabajos/jobs HyP3 025D, Path33",
    "inv_tabla":    "2026-11-19 · cuaderno/notebook Inventario_Multisensor (timeline)",
    "danio_ref":    "2026-11-19 · 01_datos_crudos/danio_referencia",
    "danio_sitios": "2026-11-19 · resumen_sitios_v2.csv (3 sitios/sites); figuras NO publicables, rehacer / figures NOT publishable, redo",
}


def _ruta(raiz):
    return os.path.join(raiz, "05_documentacion", "pasos_ejecutados.csv")


def leer(raiz):
    r = _ruta(raiz)
    cols = ["id", "fecha", "version", "estado", "origen"]
    if os.path.exists(r):
        return pd.read_csv(r)
    return pd.DataFrame(columns=cols)


def estado(raiz):
    """Tabla de todos los pasos: ✅ hecho · ♻️ siempre re-ejecutable · ⏳ pendiente."""
    h = leer(raiz)
    ok = set(h[h.estado == "ok"].id) if len(h) else set()
    filas = []
    for pid, fase, script, es, en in PASOS:
        if pid in ok:
            u = h[(h.id == pid) & (h.estado == "ok")].iloc[-1]
            s, det = "✅", f"{u.fecha} · {u.origen}"
        elif pid in HECHO_PREVIO:
            s, det = "✅", f"previo / earlier · {HECHO_PREVIO[pid]}"
        elif pid in SIEMPRE:
            s, det = "♻️", "se puede correr siempre / safe to always run"
        else:
            s, det = "⏳", "pendiente / pending"
        filas.append({"paso / step": pid, "fase / phase": fase, "estado / status": s,
                      "descripción (ES)": es, "description (EN)": en, "detalle / detail": det})
    return pd.DataFrame(filas)


FORZAR_SIN_HASH = {"descomp", "mapas_base", "insar_metricas", "nisar_tif"}   # se repiten una vez si su registro no tiene huella del código / re-run once


def _md5(script):
    import hashlib
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), script)
    return hashlib.md5(open(f, "rb").read()).hexdigest()[:8] if os.path.exists(f) else ""


def _desactualizado(h, pid, script):
    """True si el código del script cambió desde la última ejecución registrada / script changed since the last logged run."""
    f = h[(h.id == pid) & (h.estado == "ok")]
    if not len(f):
        return False                                   # solo en HECHO_PREVIO: se respeta / only in HECHO_PREVIO: respected
    o = str(f.iloc[-1].origen)
    if "md5:" in o:
        return o.split("md5:")[-1].strip() != _md5(script)
    return pid in FORZAR_SIN_HASH


def paso(pid, correr, raiz, version="", forzar=False, confirmar=False, variables=None):
    """Ejecuta un paso salvo que ya esté hecho. `correr` es la función del cuaderno; `variables` se inyectan antes."""
    assert pid in IDS, f"paso desconocido / unknown step: {pid} (válidos / valid: {IDS})"
    script = next(p[2] for p in PASOS if p[0] == pid)
    h = leer(raiz)
    hecho = (pid in set(h[h.estado == "ok"].id)) if len(h) else False
    hecho = hecho or pid in HECHO_PREVIO
    if hecho and not forzar and pid not in SIEMPRE and _desactualizado(h, pid, script):
        print(f"🔄 {pid}: el código cambió desde la última vez: se repite solo / code changed since the last run: re-running")
        hecho = False
    if hecho and not forzar and pid not in SIEMPRE:
        print(f"⏭️  {pid}: ya hecho / already done. Use forzar=True para repetir / to repeat.")
        return None
    if pid == "hyp3_envio" and not confirmar:
        print("🛑 hyp3_envio gasta créditos de HyP3. Revise primero con inv_s1 y repita con confirmar=True.")
        print("🛑 hyp3_envio uses HyP3 credits. Check with inv_s1 first, then repeat with confirmar=True.")
        print("   Solo se enviará lo que NO exista (par de escenas + resolución). / Only what does not exist (scene pair + resolution) is submitted.")
        return None
    if variables:
        from IPython import get_ipython
        get_ipython().user_ns.update(variables)
    estado_final, origen = "ok", ""
    try:
        correr(script)
    except BaseException as e:               # registra el fallo y vuelve a lanzarlo / log the failure and re-raise
        estado_final, origen = "error", f"{type(e).__name__}: {str(e)[:120]}"
        raise
    finally:
        os.makedirs(os.path.dirname(_ruta(raiz)), exist_ok=True)
        fila = pd.DataFrame([dict(id=pid, fecha=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), version=version,
                                  estado=estado_final, origen=origen or f"{script} md5:{_md5(script)}")])
        fila.to_csv(_ruta(raiz), mode="a", header=not os.path.exists(_ruta(raiz)), index=False)
    return True
