# -*- coding: utf-8 -*-
"""
TABLAS DEL ARTÍCULO (ES/EN) a partir de los resultados del flujo / Paper tables (ES/EN) from the workflow outputs
================================================================================================================
Junta los CSV que producen los pasos (insar_metricas, qc, mosaico, descomp, auditoria, ucsd_los) en tablas listas para el manuscrito:
  Tabla 1  · Datos por banda y producto (sensor, banda, λ, dirección, track/frame, fechas, línea base, días tras el sismo, fuente)
  Tabla 2  · Procesamiento y correcciones por producto (ionosfera, referencia, troposfera/marea según el GUNW, umbral de coherencia)
  Tabla S1 · Calidad por producto: cobertura total y SOBRE TIERRA (el mar se excluye: es incoherente), coherencia en tierra y mar,
             franjas, señal/ruido, ruido en campo lejano, barrido del umbral de coherencia
  Tabla S2 · Mosaicos: procedencia de cada pieza y calidad de las costuras
  Tabla S3 · Comparaciones: C vs L (Este/Vertical en píxeles comunes sobre tierra) y NISAR propio vs UCSD
Cada tabla se guarda en CSV y Markdown, en español y en inglés: <RAIZ>/05_documentacion/tablas/. Si falta un insumo, la tabla se omite y se avisa.
"""
import os

import numpy as np
import pandas as pd

RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
OUT = f"{RAIZ}/05_documentacion/tablas"
os.makedirs(OUT, exist_ok=True)
PROC = f"{RAIZ}/02_procesados"   # (no llamar P: es la función del cuaderno)
SISMO = pd.Timestamp("2026-06-24")
LAMBDA_CM = {"C": 5.55, "L": 23.8}


def leer(ruta):
    try:
        return pd.read_csv(ruta)
    except Exception:
        print(f"   [!] falta / missing: {os.path.relpath(ruta, RAIZ)}")
        return None


def guardar(df, nombre, en_cols):
    """CSV + Markdown en ES y EN / CSV + Markdown in ES and EN."""
    if df is None or df.empty:
        print(f"   (omitida / skipped) {nombre}"); return
    en = df.rename(columns=en_cols)
    for sufijo, d in (("es", df), ("en", en)):
        d.to_csv(f"{OUT}/{nombre}_{sufijo}.csv", index=False)
        try:
            md = d.to_markdown(index=False)
        except Exception:                       # sin 'tabulate'
            md = "| " + " | ".join(map(str, d.columns)) + " |\n|" + "---|" * len(d.columns) + "\n" + \
                 "\n".join("| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in d.itertuples(index=False))
        open(f"{OUT}/{nombre}_{sufijo}.md", "w", encoding="utf-8").write(md + "\n")
    print(f"✓ {nombre}: {len(df)} filas / rows")


met = leer(f"{PROC}/metricas_insar/metricas_insar_es.csv")
qc = leer(f"{PROC}/metricas_insar/qc_interferogramas_es.csv")
prov = leer(f"{PROC}/mosaicos/mosaico_procedencia_es.csv")
cost = leer(f"{PROC}/mosaicos/mosaico_costuras_es.csv")
cl = leer(f"{PROC}/descomposicion/comparacion_C_vs_L_es.csv")
pu = leer(f"{PROC}/metricas_insar/comparacion_propio_vs_ucsd_es.csv")
aud = leer(f"{RAIZ}/05_documentacion/auditoria_correcciones.csv")

# ---------------------------------------------------------------- Tabla 1 · datos
if met is not None:
    t1 = met.copy()
    t1["dirección"] = np.where(t1["track"].astype(str).str.endswith("A"), "ASC",
                               np.where(t1["track"].astype(str).str.endswith("D"), "DESC",
                                        np.where(t1["mirada_E_media"] < 0, "ASC (S-1)", "DESC (S-1)")))
    t1["λ (cm)"] = t1["banda"].map(LAMBDA_CM)
    t1["días tras el sismo"] = (pd.to_datetime(t1["fecha_sec"]) - SISMO).dt.days.clip(lower=0)
    t1["fuente de datos"] = np.where(t1["fuente"] == "ucsd", "UCSD/Scripps (externo, sin revisión por pares)", "propio")
    t1 = t1[["sensor", "banda", "λ (cm)", "dirección", "track", "fecha_ref", "fecha_sec", "linea_base_dias", "días tras el sismo",
             "relacion_sismo", "fuente de datos", "producto"]]
    guardar(t1, "Tabla1_datos", {"sensor": "sensor", "banda": "band", "dirección": "direction", "fecha_ref": "ref_date", "fecha_sec": "sec_date",
                                 "linea_base_dias": "baseline_days", "días tras el sismo": "days_after_quake", "relacion_sismo": "relation",
                                 "fuente de datos": "data_source", "producto": "product"})

# ---------------------------------------------------------------- Tabla 2 · procesamiento y correcciones
if met is not None:
    t2 = met[["sensor", "track", "producto", "ionosfera", "offset_referencia_mm", "coh_ge_umbral_pct"]].copy()
    t2["referencia"] = "mediana del campo lejano (> 20 km de fallas)"
    if aud is not None and (aud["capa_o_correccion"].str.startswith("BANDERA")).any():
        b = aud[aud.capa_o_correccion.str.startswith("BANDERA")].drop_duplicates(["capa_o_correccion", "presente"])
        resumen_b = "; ".join(f"{r.capa_o_correccion.replace('BANDERA ', '')}={r.presente}" for r in b.itertuples())
        t2["troposfera/marea (banderas GUNW)"] = np.where(t2["sensor"].eq("NISAR"), resumen_b, "no aplicada")
    else:
        t2["troposfera/marea (banderas GUNW)"] = np.where(t2["sensor"].eq("NISAR"), "por leer (ejecute `auditoria`)", "no aplicada")
    guardar(t2, "Tabla2_procesamiento", {"sensor": "sensor", "producto": "product", "ionosfera": "ionosphere", "offset_referencia_mm": "reference_offset_mm",
                                         "coh_ge_umbral_pct": "coh_above_threshold_pct", "referencia": "reference",
                                         "troposfera/marea (banderas GUNW)": "troposphere/tide (GUNW flags)"})

# ---------------------------------------------------------------- Tabla S1 · calidad, con el análisis tierra/mar
if qc is not None:
    cols = [c for c in ("producto", "sensor", "ionosfera_restada", "cobertura_pct", "huella_en_tierra_pct", "coh_sobre_umbral_en_tierra_pct",
                        "coh_sobre_umbral_en_mar_pct", "franjas_p2_p98", "relacion_senal_ruido", "ruido_campo_lejano_mm",
                        "cobertura_coh0.1_pct", "cobertura_coh0.2_pct", "cobertura_coh0.3_pct", "cobertura_coh0.4_pct", "diagnostico") if c in qc]
    guardar(qc[cols], "TablaS1_calidad", {"producto": "product", "ionosfera_restada": "ionosphere_removed", "cobertura_pct": "coverage_pct",
                                          "huella_en_tierra_pct": "footprint_on_land_pct", "coh_sobre_umbral_en_tierra_pct": "land_coh_above_thr_pct",
                                          "coh_sobre_umbral_en_mar_pct": "sea_coh_above_thr_pct", "franjas_p2_p98": "fringes_p2_p98",
                                          "relacion_senal_ruido": "snr", "ruido_campo_lejano_mm": "far_field_noise_mm", "diagnostico": "diagnosis"})

# ---------------------------------------------------------------- Tabla S2 · mosaicos
if prov is not None:
    t = prov.copy()
    if cost is not None:
        t = t.merge(cost[["producto", "solape_pix", "rms_solape_mm", "mad_solape_mm"]], on="producto", how="left")
    guardar(t, "TablaS2_mosaicos", {"mosaico": "mosaic", "producto": "product", "fecha_ref": "ref_date", "fecha_sec": "sec_date",
                                    "linea_base_dias": "baseline_days", "dias_post_sismo_en_la_ventana": "days_after_quake",
                                    "pct_pixeles_del_mosaico": "pct_of_mosaic", "desfase_aplicado_mm": "applied_offset_mm",
                                    "solape_pix": "overlap_px", "rms_solape_mm": "overlap_rms_mm", "mad_solape_mm": "overlap_mad_mm"})

# ---------------------------------------------------------------- Tabla S3 · comparaciones
partes = []
if cl is not None:
    partes.append(cl.assign(comparacion="L − C (Este/Vertical, tierra, píxeles comunes)"))
if pu is not None:
    partes.append(pu.assign(comparacion="NISAR propio vs UCSD (LOS)"))
if partes:
    guardar(pd.concat(partes, ignore_index=True), "TablaS3_comparaciones", {"comparacion": "comparison", "componente": "component",
                                                                           "sesgo_L_menos_C_mm": "bias_L_minus_C_mm", "pendiente": "slope"})
print(f"\nTablas / tables: {OUT}")
