# -*- coding: utf-8 -*-
"""ALOS-2 ScanSAR en ASF sobre la zona de ruptura / ALOS-2 ScanSAR on ASF over the rupture zone."""
import os
RAIZ = globals().get("RAIZ", "/content/drive/My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR")
os.makedirs(f"{RAIZ}/05_documentacion", exist_ok=True)
import asf_search as asf, pandas as pd
from shapely.geometry import box, shape
ROI = box(-68.6, 10.0, -66.4, 11.0)
SISMO = pd.Timestamp("2026-06-24T22:04:33Z")
res = []
for kw in ({"dataset": "ALOS-2"}, {"platform": "ALOS-2"}):
    try:
        res = asf.search(intersectsWith=ROI.wkt, start="2025-01-01", end="2026-08-31", **kw)
        if len(res):
            print("Búsqueda OK con", kw); break
    except Exception as e:
        print(kw, "->", e)
filas = [dict(escena=r.properties.get("sceneName"), fecha=pd.Timestamp(r.properties["startTime"]),
              path=r.properties.get("pathNumber"), frame=r.properties.get("frameNumber"),
              dir=r.properties.get("flightDirection"), modo=r.properties.get("beamModeType"),
              GB=round(sum(v.get("bytes", 0) for v in r.properties["bytes"].values()) / 1e9, 1)
                 if isinstance(r.properties.get("bytes"), dict) else None,
              url=r.properties.get("url")) for r in res]
alos2 = pd.DataFrame(filas)
if alos2.empty:
    print("ASF todavía no tiene ALOS-2 de 2026 sobre la zona (el espejo de JAXA llega con retraso).")
    print("Alternativas: (1) JAXA liberó el ScanSAR del sismo el 3-jul-2026: descargar desde el portal de JAXA")
    print("cuando su sitio vuelva; (2) usar los LOS ALOS-2 ya procesados por Scripps/UCSD (topex.ucsd.edu/VNZ_7.5), citándolos.")
else:
    alos2["relacion"] = alos2.fecha.map(lambda f: "PRE" if f < SISMO else "POST")
    alos2 = alos2.sort_values(["path", "fecha"])
    print(alos2.drop(columns="url").to_string(index=False))
    alos2.to_csv(f"{RAIZ}/05_documentacion/alos2_escenas.csv", index=False)
