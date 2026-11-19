# -*- coding: utf-8 -*-
"""
Sentinel-1: pares cosísmicos y (opcional) envío a HyP3 / coseismic pairs and (optional) HyP3 submission.
Usar con %run -i para reutilizar `usuario` y `clave`. Fijar ENVIAR_HYP3 = True para enviar.
Use with %run -i to reuse `usuario` and `clave`. Set ENVIAR_HYP3 = True to submit.
"""
import asf_search as asf
import pandas as pd
from shapely.geometry import box, shape

ENVIAR_HYP3 = globals().get("ENVIAR_HYP3", False)
SISMO = pd.Timestamp("2026-06-24T22:04:33Z")
ROI = box(-67.3, 10.4, -66.7, 10.8)   # La Guaira

res = asf.geo_search(platform=[asf.PLATFORM.SENTINEL1], intersectsWith=ROI.wkt,
                     start="2026-06-01", end="2026-07-15", processingLevel=asf.PRODUCT_TYPE.SLC)
s1 = pd.DataFrame([dict(escena=r.properties["sceneName"], fecha=pd.Timestamp(r.properties["startTime"]),
                        track=int(r.properties["pathNumber"]), dir=r.properties["flightDirection"],
                        geom=shape(r.geometry)) for r in res])
s1["cubre_%"] = s1.geom.map(lambda g: round(g.intersection(ROI).area / ROI.area * 100, 1))

pares = []
for (t, d), g in s1.groupby(["track", "dir"]):
    pre, post = g[g.fecha < SISMO].sort_values("fecha"), g[g.fecha > SISMO].sort_values("fecha")
    if pre.empty or post.empty:
        continue
    a = pre.iloc[-1]
    post = post[post.geom.map(lambda x: x.intersection(a.geom).area / a.geom.area) > 0.5]
    if post.empty:
        continue
    b = post.iloc[0]
    pares.append(dict(track=f"{t:03d}{d[0]}", ref=a.escena, sec=b.escena, fecha_ref=a.fecha.date(),
                      fecha_sec=b.fecha.date(), dias=round((b.fecha - a.fecha).total_seconds() / 86400),
                      cubre_LaGuaira=min(a["cubre_%"], b["cubre_%"])))
pares = pd.DataFrame(pares).sort_values("cubre_LaGuaira", ascending=False)
pares.to_csv("s1_pares_cosismicos.csv", index=False)
print(pares.to_string(index=False))

if ENVIAR_HYP3:
    import hyp3_sdk
    hyp3 = hyp3_sdk.HyP3(username=usuario, password=clave)
    existentes = {j.name for j in hyp3.find_jobs()}
    lote = hyp3_sdk.Batch()
    for _, p in pares.iterrows():
        nombre = f"S1_{p.track}_cosismico"
        if nombre in existentes:
            print("ya enviado / already submitted:", nombre); continue
        lote += hyp3.submit_insar_job(p.ref, p.sec, name=nombre, looks="10x2", include_inc_map=True,
                                      include_dem=True, include_look_vectors=True)
    print(lote)
    for nombre in (f"S1_{t}_cosismico" for t in pares.track):
        print(nombre, "->", hyp3.find_jobs(name=nombre))
