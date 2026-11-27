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
Cada «Usar» guarda una CONFIGURACIÓN (Z1-1, Z1-2…): la misma zona puede guardarse con otra ventana u otras escenas. «Borrar última» deshace; «Ver guardadas» lista.
Se guarda en 05_documentacion/seleccion_zonas_danio.csv. Capturas en 04_figuras/borradores/explorador/: mapa_zonas_candidatas.html, vista_*.png (cada «Ver») y ELEGIDA_<config>.png (cada «Usar»). No calcula métricas.
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


def _reparar_main():
    """Si una versión anterior del flujo borró `__main__` de sys.modules, se restaura (evita KeyError: '__main__' sin reiniciar)."""
    import sys
    if "__main__" not in sys.modules:
        try:
            from IPython import get_ipython
            sys.modules["__main__"] = get_ipython().user_module
        except Exception:
            import types
            sys.modules["__main__"] = types.ModuleType("__main__")


class Explorador:
    def __init__(self, raiz, trabajo, celda_m=500, n_max=15):
        _reparar_main()
        import geopandas as gpd
        from shapely.geometry import box
        from shapely.ops import unary_union
        self.raiz, self.trab = raiz, trabajo
        self.salida = f"{raiz}/05_documentacion/seleccion_zonas_danio.csv"
        self.capturas = f"{raiz}/04_figuras/borradores/explorador"           # capturas de lo que se miró / screenshots of what was viewed
        os.makedirs(self.capturas, exist_ok=True)
        self._fig = None
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

    # ------------------------------------------------------------ zonas manuales (coordenadas que da el autor)
    def agregar(self, puntos, lado_m=500):
        """puntos = {"nombre": (lat, lon), ...}. Agrega zonas aunque NO cumplan las tres condiciones e informa qué datos hay en cada una.
        Adds author-given zones even if they do not meet all conditions, and reports which data exist there."""
        import geopandas as gpd
        from shapely.geometry import Point, box
        filas = []
        for nom, (lat, lon) in puntos.items():
            p = Point(lon, lat)
            dlon, dlat = lado_m / 2 / (111320 * np.cos(np.radians(lat))), lado_m / 2 / 111320
            cel = box(lon - dlon, lat - dlat, lon + dlon, lat + dlat)
            filas.append(dict(zona=nom, n_danio=int(self.danio.intersects(cel).sum()), lon=lon, lat=lat,
                              umbra=int(self.umbra.contains(p).sum()), planet_post=int(self.planet.contains(p).sum()) if len(self.planet) else 0,
                              vantor_pre=int(((self.vantor.fase == "pre") & self.vantor.contains(p)).sum()), geometry=cel))
        nuevas = gpd.GeoDataFrame(filas, crs=4326)
        nuevas["condiciones"] = ["✅ X + Planet + antes" if (r.umbra and r.planet_post) else
                                 ("⚠️ sin Umbra (X)" if not r.umbra else "⚠️ sin Planet después") for r in nuevas.itertuples()]
        self.zonas = pd.concat([nuevas, self.zonas[~self.zonas.zona.isin(nuevas.zona)]], ignore_index=True)
        self.zonas = gpd.GeoDataFrame(self.zonas, geometry="geometry", crs=4326)
        print("Zonas agregadas (edificios dañados en una celda de", lado_m, "m):")
        print(nuevas.drop(columns="geometry").round(5).to_string(index=False))

    # ------------------------------------------------------------ mapa interactivo
    def mapa(self):
        _reparar_main()
        import folium
        from folium.plugins import HeatMap
        c = self.zonas.geometry.unary_union.centroid if len(self.zonas) else self.danio.unary_union.centroid
        m = folium.Map(location=[c.y, c.x], zoom_start=13, tiles="OpenStreetMap", control_scale=True)   # CartoDB ya exige clave / now needs a key
        folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Satélite (solo para explorar) / satellite (exploration only)").add_to(m)
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
        m.save(f"{self.capturas}/mapa_zonas_candidatas.html")      # se abre en el navegador / opens in a browser
        self.zonas.drop(columns="geometry").to_csv(f"{self.capturas}/zonas_candidatas.csv", index=False)
        print(f"Mapa guardado / map saved: {self.capturas}/mapa_zonas_candidatas.html")
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
        _reparar_main()
        import ipywidgets as w
        import matplotlib.pyplot as plt
        from IPython.display import display, clear_output
        from shapely.geometry import Point
        zonas = list(self.zonas.zona)
        dz = w.Dropdown(options=zonas, description="Zona")
        dl = w.IntSlider(value=600, min=200, max=2000, step=100, description="Ventana (m)", continuous_update=False)
        dpre, dpost, dum = w.Dropdown(description="ANTES"), w.Dropdown(description="DESPUÉS"), w.Dropdown(description="UMBRA (X)")
        bver, busar = w.Button(description="Ver / show", button_style="info"), w.Button(description="Usar esta / use", button_style="success")
        bborrar, blista = w.Button(description="Borrar última / undo", button_style="warning"), w.Button(description="Ver guardadas / list")
        tnota = w.Text(description="Nota", placeholder="p. ej. ventana amplia / zoom edificio")
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
                plt.tight_layout()
                self._fig = fig
                fig.savefig(f"{self.capturas}/vista_{dz.value}_{dl.value}m_{pd.Timestamp.now():%Y%m%d_%H%M%S}.png", dpi=110)
                plt.show()

        def usar(_):
            # cada guardado es una CONFIGURACIÓN nueva: la misma zona puede guardarse varias veces (otra ventana u otras escenas)
            # every save is a new CONFIGURATION: the same zone can be saved several times
            r = self.zonas[self.zonas.zona == dz.value].iloc[0]
            prev = pd.read_csv(self.salida) if os.path.exists(self.salida) else pd.DataFrame()
            fila = dict(zona=dz.value, lat=round(r.lat, 6), lon=round(r.lon, 6), ventana_m=dl.value, edificios_danados=r.n_danio,
                        antes=dpre.label, url_antes=dpre.value, despues=dpost.label, url_despues=dpost.value,
                        umbra=dum.label, url_umbra=dum.value, nota=tnota.value, fecha_eleccion=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))
            if len(prev):
                igual = (prev.zona == fila["zona"]) & (prev.ventana_m == fila["ventana_m"]) & (prev.url_antes == fila["url_antes"]) &                         (prev.url_despues == fila["url_despues"]) & (prev.url_umbra == fila["url_umbra"])
                if igual.any():
                    msg.value = f"⚠️ Esa configuración de <b>{dz.value}</b> ya estaba guardada (no se duplica)."; return
            n_zona = int((prev.zona == dz.value).sum()) + 1 if len(prev) else 1
            fila["config"] = f"{dz.value}-{n_zona}"                     # Z1-1, Z1-2, … / configuration id
            if self._fig is not None:
                self._fig.savefig(f"{self.capturas}/ELEGIDA_{fila['config']}_{dl.value}m.png", dpi=150)
                fila["captura"] = f"ELEGIDA_{fila['config']}_{dl.value}m.png"
            pd.concat([prev, pd.DataFrame([fila])], ignore_index=True).to_csv(self.salida, index=False)
            msg.value = f"✅ Guardada <b>{fila['config']}</b> (ventana {dl.value} m) en {self.salida} · total {len(prev) + 1} configuraciones"

        def borrar(_):
            if not os.path.exists(self.salida):
                msg.value = "No hay configuraciones guardadas."; return
            prev = pd.read_csv(self.salida)
            if len(prev):
                ult = prev.iloc[-1]["config"] if "config" in prev else prev.iloc[-1]["zona"]
                prev.iloc[:-1].to_csv(self.salida, index=False)
                msg.value = f"🗑️ Borrada la última: <b>{ult}</b> · quedan {len(prev) - 1}"

        def listar(_):
            with out:
                clear_output(wait=True)
                if os.path.exists(self.salida):
                    t = pd.read_csv(self.salida)
                    cols = [c for c in ("config", "zona", "ventana_m", "antes", "despues", "umbra", "nota") if c in t]
                    display(t[cols])
                else:
                    print("Aún no hay configuraciones guardadas / nothing saved yet")

        dz.observe(opciones, names="value"); bver.on_click(ver); busar.on_click(usar); bborrar.on_click(borrar); blista.on_click(listar)
        opciones()
        display(w.VBox([w.HBox([dz, dl]), dpre, dpost, dum, tnota, w.HBox([bver, busar, bborrar, blista]), msg, out]))
