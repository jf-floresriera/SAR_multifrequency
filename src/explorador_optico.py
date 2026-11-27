# -*- coding: utf-8 -*-
"""
EXPLORADOR INTERACTIVO de zonas para el daño (banda X + óptico) — el autor elige mirando / Interactive explorer, the author picks
==============================================================================================================================
Condiciones de una zona candidata (en este orden) / candidate-zone conditions:
  1) hay UMBRA (banda X)  ·  2) hay PLANET SkySat DESPUÉS del sismo  ·  3) hay imagen ANTES (Vantor «pre»; si no, mosaico Planet Q1-2026)
  4) se ordenan por número de edificios DAÑADOS/DESTRUIDOS (HOTOSM + Copernicus EMS) → las más afectadas primero.
Uso en Colab (después de la celda #1) / usage:
    from explorador_optico import Explorador
    ex = Explorador(RAIZ, TRABAJO)
    ex.mapa()      # mapa con zoom: daño, huellas Umbra/Planet/Vantor y zonas candidatas numeradas
    ex.panel()     # elegir zona, ventana (m) y escenas; «Ver» dibuja ANTES | DESPUÉS | UMBRA; «Usar» guarda la elección
La elección se guarda en 05_documentacion/seleccion_zonas_danio.csv (zona, centro, ventana, escena antes, después y Umbra). No calcula métricas.
"""
import io
import json
import os

import numpy as np
import pandas as pd
import requests

VANTOR = "https://vantor-opendata.s3.amazonaws.com/events/Venezuela-Earthquake-Jun-2026/"
PLANET = "https://data.source.coop/planet/disasterdata/venezuela-earthquake-2026-06-24"
UMBRA_HTTPS = "https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/"
MOSAICO_PRE = f"{PLANET}/pre-event/quarterly-mosaic/quarterly-mosaic-2026Q1.tif"


class Explorador:
    def __init__(self, raiz, trabajo, celda_m=500, n_max=15):
        import geopandas as gpd
        from shapely.geometry import box
        from shapely.ops import unary_union
        self.raiz, self.trab = raiz, trabajo
        self.salida = f"{raiz}/05_documentacion/seleccion_zonas_danio.csv"
        # --- daño de referencia (destruido / dañado)
        d = gpd.read_file(f"{raiz}/01_datos_crudos/danio_referencia/danio_referencia.gpkg", layer="edificios_danio")
        if "clase" in d:
            d = d[d["clase"].astype(str).str.contains("destru|dañ", case=False)]
        self.danio = d.to_crs(4326)
        # --- Umbra (X)
        ud = f"{trabajo}/umbra_inventario"
        um = gpd.read_file(f"{ud}/umbra_huellas.geojson").set_crs(4326, allow_override=True)
        inv = pd.read_csv(f"{ud}/umbra_inventario.csv")
        lst = pd.read_csv(f"{ud}/umbra_listado_completo.csv")
        gec = lst[lst.key.str.contains("GEC", case=False) & lst.key.str.lower().str.endswith((".tif", ".tiff"))]
        um = um[["task_id", "geometry"]].merge(inv[["task_id", "inicio_utc", "satelite", "incidencia_deg", "direccion_mirada"]], on="task_id")
        um["url"] = um.task_id.map(lambda t: UMBRA_HTTPS + gec[gec.key.str.contains(t)].key.iloc[0] if gec.key.str.contains(t).any() else None)
        self.umbra = um[um.url.notna()].reset_index(drop=True)
        # --- Planet SkySat después (URLs ya resueltas por danio_sitios)
        pd_ = f"{trabajo}/umbra_planet_sitios"
        pq = f"{pd_}/planet_post_items.parquet"
        pl = gpd.read_parquet(pq if os.path.exists(pq) else io.BytesIO(requests.get(f"{PLANET}/post-event/items.parquet", timeout=120).content))
        pl = pl.to_crs(4326)
        if os.path.exists(f"{pd_}/planet_urls.csv"):
            pl = pl.merge(pd.read_csv(f"{pd_}/planet_urls.csv"), on="id", how="left")
        self.planet = pl[pl.get("url", pd.Series(dtype=str)).notna()].reset_index(drop=True) if "url" in pl else pl.iloc[0:0]
        # --- Vantor (antes y después)
        cache = f"{trabajo}/vantor/vantor_items.json"
        if os.path.exists(cache):
            items = json.load(open(cache))
        else:
            col = requests.get(VANTOR + "collection.json", timeout=60).json()
            items = [requests.get(l["href"], timeout=60).json() for l in col["links"] if l["rel"] == "item"]
            os.makedirs(os.path.dirname(cache), exist_ok=True); json.dump(items, open(cache, "w"))
        self.vantor = gpd.GeoDataFrame([dict(id=j["id"], fecha=j["properties"]["datetime"][:10], fase=j["properties"].get("phase"),
                                             nubes=j["properties"].get("eo:cloud_cover"), url=j["assets"]["visual"]["href"])
                                        for j in items], geometry=[box(*j["bbox"]) for j in items], crs=4326)
        # --- zonas candidatas: celdas con Umbra ∩ Planet después, ordenadas por daño
        U, P = unary_union(self.umbra.geometry), unary_union(self.planet.geometry) if len(self.planet) else None
        dutm = self.danio.to_crs(32619)
        c = dutm.geometry.centroid
        ij = pd.DataFrame({"i": (c.x // celda_m).astype(int), "j": (c.y // celda_m).astype(int)}).value_counts().reset_index(name="n")
        filas = []
        for r in ij.sort_values("n", ascending=False).itertuples():
            x, y = (r.i + 0.5) * celda_m, (r.j + 0.5) * celda_m
            cel = gpd.GeoSeries([box(x - celda_m / 2, y - celda_m / 2, x + celda_m / 2, y + celda_m / 2)], crs=32619).to_crs(4326).iloc[0]
            if not U.contains(cel.centroid) or P is None or not P.contains(cel.centroid):
                continue
            pre_v = self.vantor[(self.vantor.fase == "pre") & self.vantor.contains(cel.centroid)]
            filas.append(dict(n_danio=int(r.n), lon=cel.centroid.x, lat=cel.centroid.y, umbra=int(self.umbra.contains(cel.centroid).sum()),
                              planet_post=int(self.planet.contains(cel.centroid).sum()), vantor_pre=len(pre_v), geometry=cel))
            if len(filas) >= n_max:
                break
        self.zonas = gpd.GeoDataFrame(filas, crs=4326)
        self.zonas.insert(0, "zona", [f"Z{k + 1}" for k in range(len(self.zonas))])
        print(f"{len(self.zonas)} zonas candidatas (Umbra + Planet después + antes), ordenadas por edificios dañados:")
        print(self.zonas.drop(columns="geometry").round(5).to_string(index=False))

    # ------------------------------------------------------------ mapa interactivo
    def mapa(self):
        import folium
        from folium.plugins import HeatMap
        c = self.zonas.geometry.unary_union.centroid if len(self.zonas) else self.danio.unary_union.centroid
        m = folium.Map(location=[c.y, c.x], zoom_start=12, tiles="CartoDB positron", control_scale=True)
        folium.TileLayer("OpenStreetMap", name="OSM").add_to(m)
        cen = self.danio.geometry.centroid
        HeatMap(list(zip(cen.y, cen.x)), radius=12, blur=15, name="Daño (densidad) / damage density").add_to(m)
        estilos = [("Umbra (X)", self.umbra, "#0072B2"), ("Planet SkySat después / post", self.planet, "#CC79A7"),
                   ("Vantor antes / pre", self.vantor[self.vantor.fase == "pre"], "#009E73"),
                   ("Vantor después / post", self.vantor[self.vantor.fase == "post"], "#555555")]
        for nom, g, col in estilos:
            if len(g):
                folium.GeoJson(g[["geometry"]], name=nom, style_function=lambda _, c=col: {"color": c, "weight": 1, "fillOpacity": 0.05}).add_to(m)
        fz = folium.FeatureGroup(name="Zonas candidatas / candidate zones").add_to(m)
        for r in self.zonas.itertuples():
            folium.GeoJson(r.geometry.__geo_interface__, style_function=lambda _: {"color": "#D55E00", "weight": 2, "fillOpacity": 0.1}).add_to(fz)
            folium.Marker([r.lat, r.lon], tooltip=f"{r.zona}: {r.n_danio} edificios dañados · Umbra {r.umbra} · Planet {r.planet_post} · Vantor antes {r.vantor_pre}",
                          icon=folium.DivIcon(html=f'<div style="font-weight:bold;color:#D55E00;background:white;padding:1px 3px;border-radius:3px">{r.zona}</div>')).add_to(fz)
        folium.LayerControl(collapsed=False).add_to(m)
        return m

    # ------------------------------------------------------------ panel de selección
    def _recorte(self, url, lon, lat, lado, bandas=(1, 2, 3), n=500):
        import rasterio
        from rasterio.vrt import WarpedVRT
        from rasterio.transform import from_origin
        from rasterio.enums import Resampling
        from pyproj import Transformer
        x, y = Transformer.from_crs(4326, 32619, always_xy=True).transform(lon, lat)
        tr = from_origin(x - lado / 2, y + lado / 2, lado / n, lado / n)
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff"):
            with rasterio.open(url) as s, WarpedVRT(s, crs="EPSG:32619", transform=tr, width=n, height=n, resampling=Resampling.bilinear) as v:
                b = [i for i in bandas if i <= v.count]
                a = v.read(b).astype("float32")
        return a

    def _rgb(self, a):
        a = np.moveaxis(a[:3], 0, -1)
        v = a[a > 0]
        if not v.size:
            return a
        lo, hi = np.percentile(v, (2, 98))
        return np.clip((a - lo) / max(hi - lo, 1e-6), 0, 1)

    def _sar(self, a):
        x = a[0]; x = np.where(x > 0, 10 * np.log10(x), np.nan)
        lo, hi = np.nanpercentile(x, (2, 98)) if np.isfinite(x).any() else (0, 1)
        return np.clip((x - lo) / max(hi - lo, 1e-6), 0, 1)

    def panel(self):
        import ipywidgets as w
        import matplotlib.pyplot as plt
        from IPython.display import display, clear_output
        from shapely.geometry import Point
        zonas = list(self.zonas.zona)
        dz = w.Dropdown(options=zonas, description="Zona")
        dl = w.IntSlider(value=600, min=200, max=2000, step=100, description="Ventana (m)", continuous_update=False)
        dpre, dpost, dum = w.Dropdown(description="ANTES"), w.Dropdown(description="DESPUÉS"), w.Dropdown(description="UMBRA (X)")
        bver, busar = w.Button(description="Ver / show", button_style="info"), w.Button(description="Usar esta / use", button_style="success")
        out, msg = w.Output(), w.HTML()

        def opciones(*_):
            r = self.zonas[self.zonas.zona == dz.value].iloc[0]; p = Point(r.lon, r.lat)
            pre = [(f"Vantor {x.fecha} (nubes {x.nubes}%)", x.url) for x in self.vantor[(self.vantor.fase == "pre") & self.vantor.contains(p)].sort_values("fecha", ascending=False).itertuples()]
            pre.append(("Planet mosaico Q1-2026 (4,8 m)", MOSAICO_PRE))
            post = [(f"Planet SkySat {str(x.datetime)[:16]}", x.url) for x in self.planet[self.planet.contains(p)].itertuples()]
            post += [(f"Vantor {x.fecha} (nubes {x.nubes}%)", x.url) for x in self.vantor[(self.vantor.fase == "post") & self.vantor.contains(p)].itertuples()]
            um = [(f"Umbra {str(x.inicio_utc)[:16]} · {x.satelite} · inc {x.incidencia_deg:.0f}° · {x.direccion_mirada}", x.url)
                  for x in self.umbra[self.umbra.contains(p)].itertuples()]
            dpre.options, dpost.options, dum.options = pre, post, um
            msg.value = f"<b>{r.zona}</b>: {r.n_danio} edificios dañados · {r.lat:.5f}, {r.lon:.5f} · {len(pre)} antes · {len(post)} después · {len(um)} Umbra"

        def ver(_=None):
            r = self.zonas[self.zonas.zona == dz.value].iloc[0]
            with out:
                clear_output(wait=True)
                fig, axs = plt.subplots(1, 3, figsize=(15, 5.2))
                for ax, (tit, url, sar) in zip(axs, (("ANTES / before", dpre.value, False), ("DESPUÉS / after", dpost.value, False),
                                                     ("UMBRA banda X / X-band", dum.value, True))):
                    ax.axis("off")
                    if not url:
                        ax.set_title(tit + "\n(sin escena)"); continue
                    try:
                        a = self._recorte(url, r.lon, r.lat, dl.value, bandas=(1,) if sar else (1, 2, 3))
                        ax.imshow(self._sar(a) if sar else self._rgb(a), cmap="gray" if sar else None)
                    except Exception as e:
                        ax.text(0.5, 0.5, f"no se pudo leer\n{str(e)[:60]}", ha="center", transform=ax.transAxes)
                    lab = {d.value: d.label for d in (dpre, dpost, dum)}.get(url, "")
                    ax.set_title(f"{tit}\n{lab}", fontsize=9)
                    pdz = self.danio[self.danio.intersects(self.zonas[self.zonas.zona == dz.value].geometry.iloc[0].buffer(dl.value / 111320))]
                fig.suptitle(f"{dz.value} · ventana {dl.value} m · {r.n_danio} edificios dañados", x=0.01, ha="left")
                plt.tight_layout(); plt.show()

        def usar(_):
            r = self.zonas[self.zonas.zona == dz.value].iloc[0]
            fila = pd.DataFrame([dict(zona=dz.value, lat=round(r.lat, 6), lon=round(r.lon, 6), ventana_m=dl.value, edificios_danados=r.n_danio,
                                      antes=dpre.label, url_antes=dpre.value, despues=dpost.label, url_despues=dpost.value,
                                      umbra=dum.label, url_umbra=dum.value, fecha_eleccion=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))])
            prev = pd.read_csv(self.salida) if os.path.exists(self.salida) else pd.DataFrame()
            if len(prev):
                prev = prev[prev.zona != dz.value]
            pd.concat([prev, fila], ignore_index=True).to_csv(self.salida, index=False)
            msg.value = f"✅ <b>{dz.value}</b> guardada en {self.salida} ({len(prev) + 1} zonas elegidas)"

        dz.observe(opciones, names="value"); bver.on_click(ver); busar.on_click(usar)
        opciones()
        display(w.VBox([w.HBox([dz, dl]), dpre, dpost, dum, w.HBox([bver, busar]), msg, out]))
