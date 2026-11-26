# -*- coding: utf-8 -*-
"""
Control anti-duplicados: nunca reenviar a HyP3 ni volver a descargar lo que ya existe.
Anti-duplicate control: never resubmit to HyP3 or re-download what already exists.

Un trabajo HyP3 se identifica por su PAR DE ESCENAS + tipo de producto (no por el nombre, que cambia).
A HyP3 job is identified by its SCENE PAIR + job type (not by name, which changes).
"""
import os
import re
from datetime import datetime, timezone

# Estados que NO deben reenviarse / states that must NOT be resubmitted
ESTADOS_VIGENTES = ("SUCCEEDED", "RUNNING", "PENDING")
TAG_LOOKS = {"10x2": "INT40", "20x4": "INT80"}  # resolución en el nombre del ZIP / resolution tag in ZIP name


def clave_par(granules):
    """Clave canónica de un par de escenas / canonical key of a scene pair."""
    return frozenset(g.replace("-SLC", "").strip() for g in granules)


def trabajos_por_par(hyp3, job_type="INSAR_GAMMA"):
    """{clave_par: [trabajos]} de todos los trabajos de la cuenta, sin importar el nombre.
    {pair key: [jobs]} for every job on the account, regardless of name."""
    out = {}
    for j in hyp3.find_jobs():
        if j.job_type != job_type or not j.job_parameters:
            continue
        g = j.job_parameters.get("granules") or []
        if len(g) == 2:
            out.setdefault(clave_par(g), []).append(j)
    return out


def _vigente(j, ahora=None):
    """True si el trabajo sirve (no falló) y sus productos no han expirado.
    True if the job is usable (not failed) and its products have not expired."""
    ahora = ahora or datetime.now(timezone.utc)
    if j.status_code not in ESTADOS_VIGENTES:
        return False
    exp = getattr(j, "expiration_time", None)
    return not (exp is not None and exp < ahora)


def decidir_envio(existentes, ref, sec, destino_zip=None, looks="10x2"):
    """Devuelve ('reusar'|'descargado'|'enviar', trabajo_o_None, motivo).
    Returns ('reuse'|'downloaded'|'submit', job_or_None, reason)."""
    # 1) ¿ya está el ZIP en Drive? (HyP3 nombra S1AD_<ref>_<sec>_...)
    if destino_zip and os.path.isdir(destino_zip):
        t_ref = _marca(ref)
        t_sec = _marca(sec)
        for f in os.listdir(destino_zip):
            if f.endswith(".zip") and t_ref and t_sec and f"{t_ref}_{t_sec}" in f and f"_{TAG_LOOKS.get(looks, 'INT')}_" in f:
                return "descargado", None, f"ya en Drive / already on Drive: {f}"
    # 2) ¿ya existe un trabajo vigente para el mismo par (cualquier nombre)?
    for j in existentes.get(clave_par([ref, sec]), []):
        if _vigente(j) and (j.job_parameters or {}).get("looks", looks) == looks:
            return "reusar", j, f"trabajo {j.status_code} '{j.name}' ({str(j.request_time)[:10]}) / existing job"
    # 3) ¿solo hay trabajos expirados o fallidos?
    return "enviar", None, "sin trabajo vigente / no usable job"


def _marca(escena):
    """'S1A_IW_SLC__1SDV_20260618T101640_...' -> '20260618T101640'"""
    m = re.search(r"_(\d{8}T\d{6})_", escena)
    return m.group(1) if m else None


def manifiesto(carpeta, salida_csv):
    """CSV con todos los archivos de una carpeta (nombre, tamaño, fecha): inventario sin hashes lentos.
    CSV of every file in a folder (name, size, mtime): inventory without slow hashes."""
    import pandas as pd
    filas = []
    for raiz, _, archivos in os.walk(carpeta):
        for f in archivos:
            p = os.path.join(raiz, f)
            s = os.stat(p)
            filas.append(dict(ruta=os.path.relpath(p, carpeta), mb=round(s.st_size / 1e6, 1),
                              modificado=datetime.fromtimestamp(s.st_mtime).strftime("%Y-%m-%d %H:%M")))
    df = pd.DataFrame(filas).sort_values("ruta")
    df.to_csv(salida_csv, index=False)
    return df
