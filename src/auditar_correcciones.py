# -*- coding: utf-8 -*-
"""
AUDITORÍA: ¿qué correcciones interferométricas traen realmente nuestros productos? / AUDIT: which InSAR corrections do our products really have?
==============================================================================================================================
No se asume nada: se LEE cada producto y se lista qué capas de corrección existen (y cuáles no).
  · NISAR GUNW (.h5): busca capas de ionosfera, troposfera (húmeda/hidrostática), mareas terrestres, offsets, componentes conexas, etc.
  · Sentinel-1 HyP3 (carpetas/ZIP): lista los archivos entregados (fase envuelta/desenvuelta, coherencia, DEM, vectores de mirada,
    máscara de agua…) y las líneas relevantes del .txt de metadatos (procesamiento, DEM, filtro, desenvolvimiento).
Salida / Output: <RAIZ>/05_documentacion/auditoria_correcciones.csv y un resumen impreso.
Úselo ANTES de interpretar los mapas: sirve de prueba para decidir qué corrección falta. / Use it BEFORE interpreting the maps.
"""
import glob
import os
import re
import zipfile

import pandas as pd

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
NISAR_DIRS = globals().get("NISAR_DIRS", [f"{RAIZ}/01_datos_crudos/nisar_gunw", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/inventario_2026/datos_nisar_vargas"])
S1_DIR = globals().get("S1_DIR", f"{RAIZ}/01_datos_crudos/sentinel1_hyp3")
CLAVES = {  # palabra clave → corrección que representa / keyword → correction it represents
    "ionosphere": "ionosfera", "iono": "ionosfera", "wettropo": "troposfera húmeda", "wettropospheric": "troposfera húmeda",
    "hydrostatic": "troposfera hidrostática", "troposphere": "troposfera", "tropo": "troposfera",
    "solidearth": "marea terrestre", "tide": "marea", "connectedcomponents": "componentes conexas (control del desenvolvimiento)",
    "unwrappedphase": "fase desenvuelta", "coherence": "coherencia", "offset": "offsets (rango/acimut)",
    "losunitvector": "vectores de mirada", "heightaboveellipsoid": "altura/DEM", "layover": "máscara layover/sombra",
    "mask": "máscara", "uncertainty": "incertidumbre"}
filas = []

# ---------------------------------------------------------------- NISAR GUNW
try:
    import h5py
except ImportError:
    h5py = None
for d in NISAR_DIRS:
    for f in sorted(glob.glob(f"{d}/*GUNW*.h5")):
        if h5py is None:
            print("[!] instale h5py / install h5py"); break
        base = os.path.basename(f)
        enc = {}
        with h5py.File(f, "r") as h:
            def _v(nombre, obj):
                if isinstance(obj, h5py.Dataset):
                    n = nombre.lower()
                    for k, v in CLAVES.items():
                        if k in n.replace("_", ""):
                            enc.setdefault(v, []).append(nombre.split("/", 3)[-1] if nombre.count("/") > 3 else nombre)
            h.visititems(_v)
            # banderas «...Applied»: ¿el GUNW ya aplicó troposfera / mareas? (valor real leído del archivo) / flags: real values read from the file
            banderas = {}

            def _b(nombre, obj):
                if isinstance(obj, h5py.Dataset) and "applied" in nombre.lower():
                    try:
                        val = obj[()]
                        val = val.decode() if isinstance(val, bytes) else val
                        banderas[nombre.split("/")[-1]] = str(val)
                    except Exception:
                        pass
            h.visititems(_b)
        for nom_b, val_b in sorted(banderas.items()):
            filas.append(dict(producto=base[:60], sensor="NISAR GUNW", capa_o_correccion="BANDERA " + nom_b, presente=val_b, n=1, ejemplo=""))
        for v, rutas in sorted(enc.items()):
            filas.append(dict(producto=base[:60], sensor="NISAR GUNW", capa_o_correccion=v, presente="sí", n=len(rutas), ejemplo=rutas[0][:90]))
        for v in ("ionosfera", "troposfera húmeda", "troposfera hidrostática", "marea terrestre"):
            if v not in enc:
                filas.append(dict(producto=base[:60], sensor="NISAR GUNW", capa_o_correccion=v, presente="NO ENCONTRADA", n=0, ejemplo=""))

# ---------------------------------------------------------------- Sentinel-1 HyP3
carpetas = [c for c in sorted(glob.glob(f"{S1_DIR}/S1*_INT*")) if os.path.isdir(c)]
for z in sorted(glob.glob(f"{S1_DIR}/S1*_INT*.zip")):
    if z[:-4] not in carpetas:
        carpetas.append(z)
for c in carpetas:
    base = os.path.basename(c).replace(".zip", "")
    if os.path.isdir(c):
        nombres = [os.path.relpath(p, c) for p in glob.glob(f"{c}/*")]
        txt = glob.glob(f"{c}/*.txt")
        meta = open(txt[0], errors="ignore").read() if txt else ""
    else:
        with zipfile.ZipFile(c) as zf:
            nombres = zf.namelist()
            t = [n for n in nombres if n.endswith(".txt")]
            meta = zf.read(t[0]).decode(errors="ignore") if t else ""
    suf = sorted({re.sub(r"^.*?_(unw_phase|wrapped_phase|corr|dem|lv_theta|lv_phi|water_mask|conncomp|amp|vert_disp|los_disp|iono)\.tif$", r"\1", n)
                  for n in nombres if n.endswith(".tif")})
    filas.append(dict(producto=base[:60], sensor="Sentinel-1 HyP3", capa_o_correccion="capas entregadas", presente="sí", n=len(nombres),
                      ejemplo=", ".join(s for s in suf if len(s) < 20)))
    for k, etiqueta in (("DEM", "DEM usado (quita la fase topográfica)"), ("Looks", "multilook"), ("filter", "filtro"), ("Unwrapping", "desenvolvimiento"),
                        ("Orbit", "órbitas"), ("Reference", "referencia")):
        m = [ln.strip() for ln in meta.splitlines() if k.lower() in ln.lower()]
        if m:
            filas.append(dict(producto=base[:60], sensor="Sentinel-1 HyP3", capa_o_correccion=etiqueta, presente="sí (metadato)", n=len(m), ejemplo=m[0][:90]))
    for v in ("ionosfera", "troposfera", "marea terrestre"):
        filas.append(dict(producto=base[:60], sensor="Sentinel-1 HyP3", capa_o_correccion=v, presente="NO entregada por HyP3 (INSAR_GAMMA)", n=0, ejemplo=""))

A = pd.DataFrame(filas)
os.makedirs(f"{RAIZ}/05_documentacion", exist_ok=True)
A.to_csv(f"{RAIZ}/05_documentacion/auditoria_correcciones.csv", index=False)
if A.empty:
    print("No se encontraron productos / no products found. Revise NISAR_DIRS y S1_DIR.")
else:
    pd.set_option("display.width", 220, "display.max_colwidth", 70)
    print(A.drop_duplicates(["sensor", "capa_o_correccion", "presente"])[["sensor", "capa_o_correccion", "presente", "ejemplo"]].to_string(index=False))
    b_ = A[A.capa_o_correccion.str.startswith("BANDERA")]
    if len(b_):
        print("\n=== BANDERAS «Applied» (valor leído del GUNW) ===")
        print(b_.drop_duplicates(["capa_o_correccion", "presente"])[["capa_o_correccion", "presente"]].to_string(index=False))
    print("\nLectura / reading: 'NO ENCONTRADA' = esa corrección NO viene en el archivo y habría que aplicarla aparte (ver docs/CORRECCIONES_INSAR.md).")
