# -*- coding: utf-8 -*-
"""
EXPLORADOR INTERACTIVO de zonas para el daño (banda X + óptico) — el autor elige mirando / Interactive explorer, the author picks
==============================================================================================================================
Condiciones de una zona candidata (en este orden) / candidate-zone conditions:
  1) hay UMBRA (banda X)  ·  2) hay PLANET SkySat DESPUÉS del sismo  ·  3) hay imagen ANTES (Vantor «pre»; si no, mosaico Planet Q1-2026)
  4) se ordenan por número de edificios DAÑADOS/DESTRUIDOS (HOTOSM + Copernicus EMS) → las más afectadas primero.
Mover la ventana: arrastre el marcador en el mapa del panel (ipyleaflet) o use las flechas ↑↓←→ (paso en m). Cada toma = una configuración.
Uso en Colab (después de la celda #1) / usage:
    from explorador_optico import Explorador
    ex = Explorador(RAIZ, TRABAJO)
    ex.mapa()      # mapa con zoom: daño, huellas Umbra/Planet/Vantor y zonas candidatas numeradas
    ex.panel()     # elegir zona, ventana (m) y escenas; «Ver» dibuja ANTES | DESPUÉS | UMBRA; «Usar» guarda la elección
Cada «Usar» guarda una CONFIGURACIÓN (Z1-1, Z1-2…): la misma zona puede guardarse con otra ventana u otras escenas. «Borrar última» deshace; «Ver guardadas» lista.
Cada «Usar» guarda además los RECORTES con TODAS sus bandas (GeoTIFF, misma malla UTM 19N) en 02_procesados/recortes_zonas/<config>/
LOTE (sin panel): ex.lote([dict(lat=…, lon=…, lado=550), …]) elige escenas, alinea, guarda cada sitio y arma la lámina ES/EN.
para hacer composiciones e índices: ex.cargar('Z1-3') los devuelve como arreglos; ex.guardar_recortes() rehace los que falten.
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
# Umbra GEC: error de geolocalización de pocos m en terreno plano; el relieve (h·cot θ) aquí ≤ ~60 m → no se buscan desfases mayores.
# Si la coincidencia es débil (< CONF_MIN σ) se deja el desfase en 0: mejor sin mover que movido a un falso máximo.
RADIO_ALINEACION_M = 60.0
CONF_MIN = 6.0


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


def _nmi(a, b, bins=32):
    """Información mutua normalizada (Studholme et al., 1999) entre dos imágenes de distinto sensor / normalized mutual information."""
    v = np.isfinite(a) & np.isfinite(b)
    if v.sum() < 500:
        return np.nan
    h, _, _ = np.histogram2d(a[v], b[v], bins=bins)
    pxy = h / h.sum(); px_ = pxy.sum(1); py_ = pxy.sum(0)
    hx = -np.sum(px_[px_ > 0] * np.log(px_[px_ > 0])); hy = -np.sum(py_[py_ > 0] * np.log(py_[py_ > 0]))
    hxy = -np.sum(pxy[pxy > 0] * np.log(pxy[pxy > 0]))
    return (hx + hy) / hxy


def _registrar_nmi(opt, sar, mp, paso=3):
    """Busca el desplazamiento (dy, dx en píxeles) de `sar` (tamaño n+2mp) que maximiza la NMI con `opt` (n×n),
    usando intensidad y magnitud de bordes; búsqueda gruesa y luego fina. Devuelve (dy, dx, confianza).
    Grid search maximizing NMI of intensities + edge magnitudes (coarse-to-fine)."""
    from scipy.ndimage import gaussian_filter, sobel, median_filter
    n = opt.shape[0]
    o1 = gaussian_filter(opt, 1.0)
    o2 = np.hypot(sobel(o1, 0), sobel(o1, 1))
    s1 = median_filter(sar, 3)                                  # reduce el moteado / speckle
    s2 = np.hypot(sobel(gaussian_filter(s1, 1.0), 0), sobel(gaussian_filter(s1, 1.0), 1))

    def puntaje(dy, dx):
        y0, x0 = mp + dy, mp + dx
        return _nmi(o1, s1[y0:y0 + n, x0:x0 + n]) + _nmi(o2, s2[y0:y0 + n, x0:x0 + n])
    gr = {(dy, dx): puntaje(dy, dx) for dy in range(-mp, mp + 1, paso) for dx in range(-mp, mp + 1, paso)}
    (by, bx) = max(gr, key=lambda k: -np.inf if not np.isfinite(gr[k]) else gr[k])
    fi = {(dy, dx): puntaje(dy, dx) for dy in range(max(-mp, by - paso), min(mp, by + paso) + 1)
          for dx in range(max(-mp, bx - paso), min(mp, bx + paso) + 1)}
    (by, bx) = max(fi, key=lambda k: -np.inf if not np.isfinite(fi[k]) else fi[k])
    vals = np.array([v for v in gr.values() if np.isfinite(v)])
    conf = (fi[(by, bx)] - np.median(vals)) / (np.std(vals) + 1e-9)   # cuántas desviaciones sobre lo típico
    return by, bx, conf


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
        self.recortes = f"{raiz}/02_procesados/recortes_zonas"
        self.f_alin = f"{raiz}/05_documentacion/alineacion_manual.json"     # desfases manuales por sitio / manual offsets             # recortes multibanda por configuración / multiband chips
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
        cols_ = [c for c in ("task_id", "inicio_utc", "satelite", "incidencia_deg", "direccion_mirada", "azimut_deg", "squint_deg") if c in inv]
        um = um[["task_id", "geometry"]].merge(inv[cols_], on="task_id")
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

    def _dem(self, lon, lat, lado, n):
        """Alturas (m) sobre la misma malla que _recorte, del DEM GLO-30 que entrega HyP3 / heights on the chip grid."""
        import glob, rasterio
        from rasterio.vrt import WarpedVRT
        from rasterio.transform import from_origin
        from rasterio.enums import Resampling
        from pyproj import Transformer
        x, y = Transformer.from_crs(4326, 32619, always_xy=True).transform(lon, lat)
        tr = from_origin(x - lado / 2, y + lado / 2, lado / n, lado / n)
        out = np.full((n, n), np.nan, "float32")
        for f in sorted(glob.glob(f"{self.raiz}/01_datos_crudos/sentinel1_hyp3/*/*_dem.tif")):
            with rasterio.open(f) as s, WarpedVRT(s, crs="EPSG:32619", transform=tr, width=n, height=n, resampling=Resampling.bilinear) as v:
                a = v.read(1).astype("float32")
                a[a <= -100] = np.nan
                out = np.where(np.isfinite(out), out, np.where(a == 0, np.nan, a))
        return np.nan_to_num(out, nan=0.0)

    def _umbra_orto(self, url, lon, lat, lado, n=500, invertir=False):
        """Umbra GEC está sobre el ELIPSOIDE: un punto a altura h aparece corrido h·cot(θ) HACIA el satélite.
        Se corrige muestreando, para cada punto del terreno, la posición corrida (corrección de relieve aproximada, sin edificios).
        Umbra GEC is ellipsoid-projected: a point at height h appears shifted h·cot(θ) toward the sensor; approximate terrain correction."""
        from scipy.ndimage import map_coordinates
        r = self.umbra[self.umbra.url == url]
        if not len(r):
            return self._recorte(url, lon, lat, lado, bandas=(1,), n=n)[0], "sin metadatos"
        r = r.iloc[0]
        th = np.radians(float(r.incidencia_deg))
        az = float(r.azimut_deg) if "azimut_deg" in r and pd.notna(r.azimut_deg) else None
        if az is None:
            return self._recorte(url, lon, lat, lado, bandas=(1,), n=n)[0], "sin azimut: sin corrección"
        margen = 500.0
        nb = int(round(n * (lado + 2 * margen) / lado))
        grande = self._recorte(url, lon, lat, lado + 2 * margen, bandas=(1,), n=nb)[0]
        h = self._dem(lon, lat, lado, n)
        px = lado / n
        d = h / np.tan(th)                                        # corrimiento horizontal (m) / horizontal shift
        ux, uy = np.sin(np.radians(az)), np.cos(np.radians(az))   # azimut de mirada (satélite → suelo) / look azimuth
        sg = 1.0 if invertir else -1.0                            # el punto aparece corrido hacia el satélite (−mirada)
        yy, xx = np.mgrid[0:n, 0:n]
        X = (xx + 0.5) * px - lado / 2; Y = lado / 2 - (yy + 0.5) * px
        Xs, Ys = X + sg * d * ux, Y + sg * d * uy
        col = (Xs + lado / 2 + margen) / px - 0.5; fil = (lado / 2 + margen - Ys) / px - 0.5
        img = map_coordinates(grande, [fil, col], order=1, mode="constant", cval=0.0)
        return img.astype("float32"), f"relieve corregido (θ={np.degrees(th):.0f}°, az={az:.0f}°, h máx {h.max():.0f} m)"

    @staticmethod
    def _si(v, defecto=False):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return defecto
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "si", "sí", "yes")
        return bool(v)

    def guardar_recortes(self, fila=None, configs=None, px=None, rehacer=False):
        """Guarda los recortes de una configuración (o de todas las del CSV) con TODAS sus bandas, en la MISMA malla UTM 19N:
        antes.tif, despues.tif (todas las bandas ópticas), umbra1_<mirada>.tif, umbra2_<mirada>.tif (amplitud, con corrección de
        relieve y desfase guardados), dem.tif, edificios_danio.gpkg y meta.json. Así se pueden hacer composiciones e índices después.
        Saves every band of each chip on one common UTM 19N grid, so composites and indices can be computed later."""
        import rasterio
        from rasterio.transform import from_origin
        from pyproj import Transformer
        from shapely.geometry import box as _bx
        if fila is None:
            if not os.path.exists(self.salida):
                print("No hay configuraciones guardadas / nothing saved"); return
            t = pd.read_csv(self.salida)
            if configs:
                t = t[t.config.isin([configs] if isinstance(configs, str) else configs)]
            for _, f in t.iterrows():
                d = f"{self.recortes}/{f['config']}"
                if os.path.exists(f"{d}/meta.json") and not rehacer:
                    print(f"{f['config']}: ya hecho / already done"); continue
                print(f"{f['config']}: {self.guardar_recortes(f.to_dict(), px=px)}")
            return
        f = fila
        lado, lat, lon = float(f["ventana_m"]), float(f["lat"]), float(f["lon"])
        p_ = px or max(0.5, lado / 4000)                                     # 0,5 m (ventanas ≤ 2 km); más grueso si es mayor
        n = int(round(lado / p_))
        x, y = Transformer.from_crs(4326, 32619, always_xy=True).transform(lon, lat)
        tr = from_origin(x - lado / 2, y + lado / 2, lado / n, lado / n)
        d = f"{self.recortes}/{f['config']}"
        os.makedirs(d, exist_ok=True)
        hechos, errores = {}, {}

        def escribir(nombre, a, desc, nodata=0.0):
            with rasterio.open(f"{d}/{nombre}.tif", "w", driver="GTiff", height=n, width=n, count=a.shape[0], dtype="float32",
                               crs="EPSG:32619", transform=tr, compress="deflate", tiled=True, nodata=nodata) as o:
                o.write(a.astype("float32"))
                for i, t_ in enumerate(desc, 1):
                    o.set_band_description(i, t_)
            hechos[nombre] = f"{a.shape[0]} bandas"

        for clave in ("antes", "despues"):
            url = f.get(f"url_{clave}")
            if isinstance(url, str) and url:
                try:
                    a = self._recorte(url, lon, lat, lado, bandas=tuple(range(1, 17)), n=n)
                    escribir(clave, a, [f"{clave}_b{i}" for i in range(1, a.shape[0] + 1)])
                except Exception as e:
                    errores[clave] = str(e)[:120]
        for k in range(1, 6):
            pre_ = "umbra" if k == 1 else f"umbra{k}"
            url = f.get(f"url_{pre_}")
            if not (isinstance(url, str) and url):
                continue
            dE_ = float(f.get(f"{pre_}_dE_m")) if pd.notna(f.get(f"{pre_}_dE_m")) else 0.0
            dN_ = float(f.get(f"{pre_}_dN_m")) if pd.notna(f.get(f"{pre_}_dN_m")) else 0.0
            mir = f.get(f"{pre_}_mirada") if isinstance(f.get(f"{pre_}_mirada"), str) and f.get(f"{pre_}_mirada") else \
                ("left" if "left" in str(f.get(pre_)) else "right")
            corr_ = self._si(f.get(f"{pre_}_relieve_corregido", f.get("umbra_relieve_corregido")), True)
            inv__ = self._si(f.get(f"{pre_}_invertido", f.get("umbra_invertido")), False)
            lo_ = lon + dE_ / (111320 * np.cos(np.radians(lat))); la_ = lat + dN_ / 111320
            try:
                a = self._umbra_orto(url, lo_, la_, lado, n=n, invertir=inv__)[0] if corr_ else \
                    self._recorte(url, lo_, la_, lado, bandas=(1,), n=n)[0]
                escribir(f"umbra{k}_{mir}", a[None], [f"umbra{k}_{mir}_amplitud"])
            except Exception as e:
                errores[f"umbra{k}"] = str(e)[:120]
        try:
            escribir("dem", self._dem(lon, lat, lado, n)[None], ["altura_m"], nodata=None)
        except Exception as e:
            errores["dem"] = str(e)[:120]
        dlo = lado / 2 / (111320 * np.cos(np.radians(lat))); dla = lado / 2 / 111320
        dv = self.danio[self.danio.intersects(_bx(lon - dlo, lat - dla, lon + dlo, lat + dla))]
        if len(dv):
            dv.to_crs(32619).to_file(f"{d}/edificios_danio.gpkg", layer="edificios_danio", driver="GPKG")
            hechos["edificios_danio"] = f"{len(dv)} edificios"
        meta = {k_: (None if (isinstance(v, float) and np.isnan(v)) else v) for k_, v in f.items()}
        meta.update(pixel_m=lado / n, n_pix=n, crs="EPSG:32619", archivos=hechos, errores=errores,
                    nota_malla="todos los .tif comparten malla: se apilan directamente / all .tif share one grid")
        with open(f"{d}/meta.json", "w", encoding="utf-8") as o:
            json.dump(meta, o, ensure_ascii=False, indent=1, default=str)
        return f"{len(hechos)} archivos en {d}" + (f" · ⚠️ errores: {errores}" if errores else "")

    def cargar(self, config):
        """Devuelve {nombre: arreglo (bandas, filas, cols)} de una configuración, más 'meta' / returns the chips of one configuration."""
        import glob, rasterio
        d = f"{self.recortes}/{config}"
        out = {"meta": json.load(open(f"{d}/meta.json", encoding="utf-8"))}
        for f in sorted(glob.glob(f"{d}/*.tif")):
            with rasterio.open(f) as r:
                out[os.path.basename(f)[:-4]] = r.read()
        return out

    # ------------------------------------------------------------ LOTE: varios sitios sin panel / batch of sites
    @staticmethod
    def _traducir(t, idioma):
        t = str(t or "")
        if idioma == "en":
            t = t.replace("nubes", "clouds").replace("relieve corregido", "terrain-corrected").replace("h máx", "max h")
            t = t.replace("sin corrección de relieve", "no terrain correction").replace("Planet mosaico", "Planet mosaic")
            for sen in ("Planet SkySat", "Vantor", "Planet mosaic"):
                if t.startswith(sen):
                    return f"Optical ({sen})" + t[len(sen):]
            return t
        return t.replace("· left", "· mirada izquierda").replace("· right", "· mirada derecha")

    def _escenas(self, lon, lat, preferir=None):
        """Escenas por defecto en un punto: ANTES = Vantor pre con menos nubes (si no, mosaico Planet); DESPUÉS = Planet SkySat
        (si no, Vantor post con menos nubes); UMBRA = TODAS las que cubren el punto, primero mirada izquierda y mayor incidencia.
        Default scenes at a point; all Umbra scenes covering it."""
        from shapely.geometry import Point
        p = Point(lon, lat)
        vp = self.vantor[(self.vantor.fase == "pre") & self.vantor.contains(p)].sort_values(["nubes", "fecha"], ascending=[True, False])
        pre_op = [(f"Vantor {x.fecha} (nubes {x.nubes}%)", x.url) for x in vp.itertuples()] + [("Planet mosaico Q1-2026 (4,8 m)", MOSAICO_PRE)]
        vq = self.vantor[(self.vantor.fase == "post") & self.vantor.contains(p)].sort_values("nubes")
        pl = self.planet[self.planet.contains(p)] if len(self.planet) else self.planet
        post_op = [(f"Vantor {x.fecha} (nubes {x.nubes}%)", x.url) for x in vq.itertuples()] + \
                  [(f"Planet SkySat {str(x.datetime)[:16]}", x.url) for x in pl.itertuples()]
        pref = dict(antes="Vantor 2026-03-21", despues="Vantor 2026-06-29")   # composición elegida por el autor / author's choice
        pref.update(preferir or {})
        def _elegir(op, clave):
            m = [o for o in op if pref.get(clave) and pref[clave] in o[0]]
            return m[0] if m else (op[0] if op else ("", None))
        pre, post = _elegir(pre_op, "antes"), _elegir(post_op, "despues")
        um = self.umbra[self.umbra.contains(p)].copy()
        um["_der"] = um.direccion_mirada.astype(str).str.contains("right")
        um = um.sort_values(["_der", "incidencia_deg"], ascending=[True, False])
        umbras = [(f"Umbra {str(x.inicio_utc)[:16]} · {x.satelite} · inc {x.incidencia_deg:.0f}° · {x.direccion_mirada}", x.url)
                  for x in um.itertuples()]
        return dict(antes=pre, despues=post, umbras=umbras)

    def _alinear_umbra(self, url_post, url_u, lon, lat, lado=800, variantes=("dem", "sin", "dem_inv"), inicial=None, radio=None):
        """Alineación AUTOMÁTICA de una Umbra con el óptico DESPUÉS. Prueba varias correcciones de relieve
        (dem = corrección con DEM; sin = ninguna; dem_inv = sentido invertido) y, para cada una, el desplazamiento que maximiza la
        información mutua (NMI) en ±RADIO_ALINEACION_M ALREDEDOR de `inicial` (dict dE, dN en m; por defecto 0, 0).
        El desfase real de las Umbra GEC aquí es de 100–250 m (medido a mano en S1), fuera de ±60 m: sin `inicial` la búsqueda
        no puede encontrarlo. Devuelve dict(dE, dN, conf, variante) con el desfase TOTAL (inicial + refinamiento).
        Automatic alignment: NMI shift search of ±radius around `inicial` (the real offset here is 100–250 m, so a start is needed)."""
        from scipy.ndimage import gaussian_filter, sobel, median_filter
        e0 = float((inicial or {}).get("dE", 0) or 0); n0 = float((inicial or {}).get("dN", 0) or 0)
        lon_u = lon + e0 / (111320 * np.cos(np.radians(lat))); lat_u = lat + n0 / 111320   # misma convención que _leer_umbra
        n = 250; px = lado / n
        mp = int(round(min(radio or RADIO_ALINEACION_M, 0.4 * lado) / px)); nb = n + 2 * mp
        o = self._recorte(url_post, lon, lat, lado, n=n)[:3].mean(0); o = np.where(o > 0, o, np.nan)
        if not np.isfinite(o).any():
            return dict(dE=int(e0), dN=int(n0), conf=np.nan, variante="sin" if inicial else "dem", puntaje=np.nan)
        o = np.where(np.isfinite(o), o, np.nanmedian(o))
        if inicial:                       # el desfase manual se midió SIN corrección de relieve → refinar en esa misma variante
            variantes = ("sin",)
        mejor = None
        for v in variantes:
            u = self._recorte(url_u, lon_u, lat_u, nb * px, bandas=(1,), n=nb)[0] if v == "sin" else \
                self._umbra_orto(url_u, lon_u, lat_u, nb * px, n=nb, invertir=(v == "dem_inv"))[0]
            val = np.isfinite(u) & (u > 0)
            if val[mp:mp + n, mp:mp + n].mean() < 0.3:
                continue
            u = np.where(val, 10 * np.log10(np.where(val, u, 1.0)), np.nan); u = np.where(np.isfinite(u), u, np.nanmedian(u))
            dy, dx, conf = _registrar_nmi(o, u, mp)
            # puntaje absoluto en la posición elegida, comparable entre variantes
            o1 = gaussian_filter(o, 1.0); s1 = median_filter(u, 3)
            sub = s1[mp + dy:mp + dy + n, mp + dx:mp + dx + n]
            pun = _nmi(o1, sub) + _nmi(np.hypot(sobel(o1, 0), sobel(o1, 1)),
                                       np.hypot(sobel(gaussian_filter(sub, 1.0), 0), sobel(gaussian_filter(sub, 1.0), 1)))
            ok_ = conf >= CONF_MIN
            r = dict(dE=int(round((e0 + (dx * px if ok_ else 0)) / 5) * 5), dN=int(round((n0 + (-dy * px if ok_ else 0)) / 5) * 5),
                     conf=conf, variante=v, puntaje=pun)
            if mejor is None or pun > mejor["puntaje"]:
                mejor = r
        return mejor or dict(dE=int(e0), dN=int(n0), conf=np.nan, variante="sin" if inicial else "dem", puntaje=np.nan)

    def _alin_heredada(self, url_u, lon, lat, max_km=5.0):
        """Desfase guardado para la MISMA escena Umbra en el sitio más cercano (≤ max_km). El desfase de una GEC depende sobre todo
        de la escena (geolocalización, squint) y cambia poco a lo largo de la costa → buen punto de partida para sitios sin desfase.
        Offset saved for the same Umbra scene at the nearest site (≤ max_km): a good start for sites without their own."""
        if not os.path.exists(self.f_alin):
            return None
        todo = json.load(open(self.f_alin, encoding="utf-8"))
        cand = []
        for sitio, d in todo.items():
            v = (d or {}).get(url_u)
            if v and "lat" in v and "lon" in v:
                km = np.hypot((v["lon"] - lon) * 111.32 * np.cos(np.radians(lat)), (v["lat"] - lat) * 111.32)
                if km <= max_km:
                    cand.append((km, sitio, v))
        if not cand:
            return None
        km, sitio, v = min(cand, key=lambda t: t[0])
        return dict(dE=v["dE"], dN=v["dN"], variante=v.get("variante", "sin"), heredado_de=sitio, km=round(float(km), 2))

    def alinear_auto_sitios(self, sitios, guardar=True, radio=60.0, max_km=5.0, sobrescribir=False, umbra_inc=((48, "left"), (27, "right"))):
        """Para cada sitio y cada Umbra (48° izq., 27° der.): parte del desfase guardado del sitio o, si no tiene, del sitio más
        cercano con la misma escena; lo REFINA por NMI en ±radio m y lo guarda en alineacion_manual.json (variante «sin»,
        origen «auto»). Después revise cada sitio con ex.alinear_manual(...): las barras arrancan en el valor guardado.
        Per site and Umbra: start from saved/nearest offset, refine by NMI within ±radio, save; then check with alinear_manual."""
        import re as _re
        todo = json.load(open(self.f_alin, encoding="utf-8")) if os.path.exists(self.f_alin) else {}
        filas = []
        for s_ in sitios:
            nombre, lat, lon = s_["nombre"], float(s_["lat"]), float(s_["lon"])
            esc = self._escenas(lon, lat)
            propio = todo.get(nombre, {}) or {}
            for inc_, mir_ in umbra_inc:
                c = [u for u in esc["umbras"] if mir_ in u[0] and abs(float(_re.search(r"inc (\d+)", u[0]).group(1)) - inc_) <= 1.5]
                if not c:
                    filas.append(dict(sitio=nombre, umbra=f"{inc_}° {mir_}", estado="sin escena")); continue
                lab, url = c[0]
                if url in propio and propio[url].get("origen") != "auto" and not sobrescribir:
                    v = propio[url]
                    filas.append(dict(sitio=nombre, umbra=f"{inc_}° {mir_}", dE=v["dE"], dN=v["dN"], estado="manual (se respeta)")); continue
                ini = propio.get(url) or self._alin_heredada(url, lon, lat, max_km) or {}
                try:
                    al = self._alinear_umbra(esc["despues"][1], url, lon, lat, inicial=ini or None, radio=radio)
                except Exception as e:
                    filas.append(dict(sitio=nombre, umbra=f"{inc_}° {mir_}", estado=f"falló: {str(e)[:60]}")); continue
                ok = np.isfinite(al["conf"]) and al["conf"] >= CONF_MIN
                filas.append(dict(sitio=nombre, umbra=f"{inc_}° {mir_}", inicio=f"{ini.get('dE', 0)}/{ini.get('dN', 0)}"
                                  + (f" (de {ini['heredado_de']})" if ini.get("heredado_de") else ""),
                                  dE=al["dE"], dN=al["dN"], confianza=round(float(al["conf"]), 1) if np.isfinite(al["conf"]) else np.nan,
                                  estado="refinado" if ok else "débil: se deja el inicio"))
                if guardar and (ok or ini):
                    todo.setdefault(nombre, {})[url] = dict(dE=al["dE"], dN=al["dN"], variante="sin", origen="auto",
                                                            confianza=None if not np.isfinite(al["conf"]) else float(al["conf"]),
                                                            fecha=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), lat=lat, lon=lon)
        if guardar:
            json.dump(todo, open(self.f_alin, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"Guardado / saved: {self.f_alin}")
        t = pd.DataFrame(filas)
        print(t.to_string(index=False))
        return t

    def _leer_umbra(self, url, lon, lat, lado, al, n=500):
        lo_ = lon + al["dE"] / (111320 * np.cos(np.radians(lat))); la_ = lat + al["dN"] / 111320
        if al["variante"] == "sin":
            return self._recorte(url, lo_, la_, lado, bandas=(1,), n=n)[0], "sin corrección de relieve"
        return self._umbra_orto(url, lo_, la_, lado, n=n, invertir=(al["variante"] == "dem_inv"))

    def lote(self, puntos, prefijo="S", lados=(500, 700, 1000), umbra_inc=((48, "left"), (27, "right")), min_umbra=None, alinear=True, contornos=False, verificar=False, preferir=None,
             recortes=False, ancho=18, px_m=0.35, dpi=300):
        """Para cada punto {lat, lon, nombre opcional}: SOLO si lo cubren al menos `min_umbra` escenas Umbra, alinea cada Umbra
        automáticamente (una vez, en 800 m alrededor del centro) y dibuja el sitio con CADA tamaño de ventana de `lados`
        (antes | después | todas las Umbra). Cada tamaño se guarda como composición; al final, una lámina ES/EN por tamaño.
        Recortes multibanda: recortes=True, o después con ex.guardar_recortes(configs=[...]) para las que elija.
        Batch: only sites covered by ≥ min_umbra Umbra scenes; one composition per window size; one plate per size."""
        import matplotlib.pyplot as plt
        from IPython.display import display
        from pyproj import Transformer
        from shapely.geometry import box as _bx
        to_utm = Transformer.from_crs(4326, 32619, always_xy=True)
        filas, por_lado = [], {int(l): [] for l in lados}
        cache_al = {}                                                   # (grupo, url) → alineación / alignment cache
        por_grupo = {}
        for i, pt in enumerate(puntos, start=1):
            lat, lon = float(pt["lat"]), float(pt["lon"])
            nombre = pt.get("nombre", f"{prefijo}{i}")
            esc = self._escenas(lon, lat, preferir)
            if umbra_inc:                                         # SOLO las escenas pedidas (p. ej. 48° izq. y 27° der.)
                import re as _re
                elegidas = []
                for inc_, mir_ in umbra_inc:
                    cand = [u for u in esc["umbras"] if mir_ in u[0] and abs(float(_re.search(r"inc (\d+)", u[0]).group(1)) - inc_) <= 1.5]
                    if cand:
                        elegidas.append(cand[0])
                if len(elegidas) < len(umbra_inc):
                    print(f"✗ {nombre} ({lat:.5f}, {lon:.5f}): no tiene todas las Umbra pedidas {list(umbra_inc)} → se omite / skipped")
                    continue
                esc["umbras"] = elegidas
            if len(esc["umbras"]) < (min_umbra or 1):
                print(f"✗ {nombre} ({lat:.5f}, {lon:.5f}): solo {len(esc['umbras'])} escena(s) Umbra (< {min_umbra or 1}) → se omite / skipped")
                continue
            print(f"✓ {nombre} ({lat:.5f}, {lon:.5f}): antes «{esc['antes'][0]}» · después «{esc['despues'][0]}» · {len(esc['umbras'])} Umbra")
            alin = []
            for k, (lab_u, url_u) in enumerate(esc["umbras"], start=1):
                al = dict(dE=0, dN=0, conf=np.nan, variante="dem", puntaje=np.nan)
                clave_al = (pt.get("grupo", nombre), url_u)
                if not pt.get("alineacion"):                             # desfase manual guardado para el sitio / saved manual offset
                    pt = dict(pt, alineacion=self._alin_guardada(pt.get("grupo", nombre)) or {})
                if pt.get("alineacion") and url_u in pt["alineacion"]:    # desfase fijado a mano / user-fixed offset
                    al = dict(dict(conf=np.nan, puntaje=np.nan, variante="dem"), **pt["alineacion"][url_u])
                elif clave_al in cache_al:
                    al = cache_al[clave_al]
                elif alinear and esc["despues"][1]:
                    c_lon, c_lat = pt.get("centro_grupo", (lon, lat))
                    her = self._alin_heredada(url_u, c_lon, c_lat)          # mismo Umbra en el sitio más cercano / nearest site
                    try:
                        al = self._alinear_umbra(esc["despues"][1], url_u, c_lon, c_lat, inicial=her)
                        if her:
                            al["heredado_de"] = her["heredado_de"]
                    except Exception as e:
                        print(f"   alineación Umbra {k} falló: {str(e)[:80]}")
                        if her:
                            al = dict(dE=her["dE"], dN=her["dN"], conf=np.nan, variante="sin", puntaje=np.nan, heredado_de=her["heredado_de"])
                cache_al[clave_al] = al
                alin.append(al)
                print(f"   Umbra {k} ({lab_u.split('·')[-2].strip()}, {lab_u.split('·')[-1].strip()}): ΔE {al['dE']} m, ΔN {al['dN']} m, "
                      + (("desfase AUTO guardado (revisar con alinear_manual)" if al.get("origen") == "auto" else
                          "desfase MANUAL guardado / saved manual offset") if "fecha" in al else
                         (f"partiendo de {al['heredado_de']} · " if al.get("heredado_de") else "")
                         + f"corrección «{al['variante']}», confianza {al['conf']:.1f}σ"
                         + ("" if al["conf"] >= CONF_MIN else (" (débil: se deja el heredado)" if al.get("heredado_de") else " (débil: desfase dejado en 0)"))))
            for lado in lados:
                lado = float(lado)
                n_px = int(min(3000, round(lado / px_m)))              # alta resolución: ~0,35 m/píxel / high resolution
                cx, cy = to_utm.transform(lon, lat)
                dv_ = self.danio.to_crs(32619)
                dv_ = dv_[dv_.intersects(_bx(cx - lado / 2, cy - lado / 2, cx + lado / 2, cy + lado / 2))]
                capas = []
                for tes, ten, (lab, url) in (("Antes", "Before", esc["antes"]), ("Después", "After", esc["despues"])):
                    c = dict(tit_es=tes, tit_en=ten, sar=False, img=None, nota="", error="", lab=lab)
                    try:
                        c["img"] = self._rgb(self._recorte(url, lon, lat, lado, bandas=(1, 2, 3), n=n_px)) if url else None
                    except Exception as e:
                        c["error"] = str(e)[:60]
                    capas.append(c)
                for k, ((lab, url), al) in enumerate(zip(esc["umbras"], alin), start=1):
                    c = dict(tit_es=f"Banda X (Umbra {k})", tit_en=f"X-band (Umbra {k})", sar=True, img=None, nota="", error="", lab=lab)
                    try:
                        a0, c["nota"] = self._leer_umbra(url, lon, lat, lado, al, n=n_px)
                        c["img"] = self._sar(a0[None]); c["nota"] += f" · ΔE {al['dE']} m, ΔN {al['dN']} m"
                    except Exception as e:
                        c["error"] = str(e)[:60]
                    capas.append(c)
                if verificar and capas[1]["img"] is not None:     # SAR (magenta) sobre óptico (verde): si coinciden se ve gris/blanco
                    for k, c_u in enumerate([c for c in capas if c["sar"] and c["img"] is not None][:2], start=1):
                        og = np.nan_to_num(capas[1]["img"][..., :3].mean(-1)); sg = np.nan_to_num(c_u["img"])
                        capas.append(dict(tit_es=f"Verificación Umbra {k} (SAR magenta / óptico verde)",
                                          tit_en=f"Check Umbra {k} (SAR magenta / optical green)", sar=False, nota="", error="",
                                          img=np.dstack([sg, og, sg]), lab=c_u["lab"]))
                por_clase = dv_["clase"].astype(str).value_counts().to_dict() if "clase" in dv_ else {}
                fila = dict(zona=nombre, lat=round(lat, 6), lon=round(lon, 6), ventana_m=lado, edificios_danados=int(len(dv_)),
                            destruidos=int(sum(v for k_, v in por_clase.items() if "destru" in k_.lower())),
                            danados=int(sum(v for k_, v in por_clase.items() if "dañ" in k_.lower() or "dan" in k_.lower())),
                            antes=esc["antes"][0], url_antes=esc["antes"][1], despues=esc["despues"][0], url_despues=esc["despues"][1],
                            nota=pt.get("nota", f"lote {int(lado)} m"), fecha_eleccion=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))
                for k, ((lab, url), al) in enumerate(zip(esc["umbras"], alin), start=1):
                    pre_ = "umbra" if k == 1 else f"umbra{k}"
                    fila.update({pre_: lab, f"url_{pre_}": url, f"{pre_}_mirada": "left" if "left" in lab else "right",
                                 f"{pre_}_dE_m": al["dE"], f"{pre_}_dN_m": al["dN"], f"{pre_}_confianza": al["conf"],
                                 f"{pre_}_relieve_corregido": al["variante"] != "sin", f"{pre_}_invertido": al["variante"] == "dem_inv"})
                prev = pd.read_csv(self.salida) if os.path.exists(self.salida) else pd.DataFrame()
                usados = prev.config.dropna().astype(str).str.extract(rf"^{nombre}-(\d+)$")[0].dropna().astype(int) \
                    if len(prev) and "config" in prev else pd.Series([], dtype=int)
                fila["config"] = f"{nombre}-{(usados.max() + 1) if len(usados) else 1}"
                d = f"{self.recortes}/{fila['config']}"; os.makedirs(d, exist_ok=True)
                dvc = dv_ if contornos else dv_.iloc[:0]
                for idi in ("es", "en"):
                    f_ = self._figura(capas, idi, cx, cy, lado, dvc, fila, ancho)
                    f_.savefig(f"{self.capturas}/ELEGIDA_{fila['config']}_{int(lado)}m_{idi}.png", dpi=dpi)
                    from estilo_figuras import guardar_formatos
                    guardar_formatos(f_, f"{d}/vista_{fila['config']}_{idi}", dpi_png=dpi)   # pdf, eps, tiff, png
                    if idi == "es":
                        display(f_)
                    plt.close(f_)
                fila["captura"] = f"ELEGIDA_{fila['config']}_{int(lado)}m_es.png | _en.png"
                pd.concat([prev, pd.DataFrame([fila])], ignore_index=True).to_csv(self.salida, index=False)
                with open(f"{d}/meta.json" if recortes else f"{d}/eleccion.json", "w", encoding="utf-8") as o_:
                    json.dump({k_: (None if isinstance(v, float) and np.isnan(v) else v) for k_, v in fila.items()}, o_,
                              ensure_ascii=False, indent=1, default=str)
                if recortes:
                    try:
                        print("   📦", self.guardar_recortes(fila))
                    except Exception as e:
                        print(f"   ⚠️ recortes no guardados: {str(e)[:100]}")
                print(f"   → {fila['config']}: ventana {int(lado)} m, {fila['edificios_danados']} edificios dañados")
                filas.append(fila); por_lado[int(lado)].append((fila, capas, cx, cy, dvc))
                por_grupo.setdefault((pt.get("grupo"), int(lado)), []).append((fila, capas, cx, cy, dvc))
        if any(g is not None for g, _ in por_grupo):                   # teselas: una lámina por sitio / one plate per site
            for (g, lado), sitios in por_grupo.items():
                self.lamina(sitios, nombre=f"lamina_{g}_{lado}m")
        else:
            for lado, sitios in por_lado.items():
                if sitios:
                    self.lamina(sitios, nombre=f"lamina_destruccion_{lado}m")
        if not filas:
            print("Ningún sitio tiene las escenas Umbra pedidas / no site has the required Umbra scenes"); return pd.DataFrame()
        t = pd.DataFrame(filas)
        return t[[c for c in ("config", "zona", "lat", "lon", "ventana_m", "edificios_danados", "destruidos") if c in t]]

    def _alin_guardada(self, sitio):
        if os.path.exists(self.f_alin):
            return json.load(open(self.f_alin, encoding="utf-8")).get(sitio)
        return None

    def alinear_manual(self, sitio, lat, lon, lado=500, inicial=None, margen=350, px=1.0, umbra_inc=((48, "left"), (27, "right"))):
        """ALINEACIÓN MANUAL con puntos de referencia: barras ΔE/ΔN para cada Umbra (1 y 2), con los BORDES del óptico en
        verde y una cuadrícula cada 50 m encima de la Umbra. «Guardar» escribe el desfase del sitio en
        05_documentacion/alineacion_manual.json; ex.teselas() y ex.lote() lo usan automáticamente para ese sitio.
        Manual alignment: sliders per Umbra scene, optical edges overlaid; saved per site and reused by teselas/lote."""
        import ipywidgets as w
        import matplotlib.pyplot as plt
        from IPython.display import display, clear_output
        from scipy.ndimage import gaussian_filter, sobel
        esc = self._escenas(lon, lat)
        import re as _re
        ums = []
        for inc_, mir_ in umbra_inc:
            c = [u for u in esc["umbras"] if mir_ in u[0] and abs(float(_re.search(r"inc (\d+)", u[0]).group(1)) - inc_) <= 1.5]
            if c:
                ums.append(c[0])
        if not ums:
            print(f"Este sitio no tiene las Umbra pedidas {list(umbra_inc)} / no requested Umbra scenes"); return
        n = int(round(lado / px)); mpx = int(round(margen / px)); nb = n + 2 * mpx
        print("Leyendo imágenes (una sola vez)… / reading images once…")
        opt = self._recorte(esc["despues"][1], lon, lat, lado, n=n)[:3]
        rgb = self._rgb(opt)
        g = gaussian_filter(opt.mean(0), 1.2); bor = np.hypot(sobel(g, 0), sobel(g, 1))
        bor = bor > np.percentile(bor, 88)                                 # bordes fuertes del óptico / strong optical edges
        guardada = self._alin_guardada(sitio) or {}
        U, sl = [], []
        for k, (lab, url) in enumerate(ums, start=1):
            a = self._recorte(url, lon, lat, nb * px, bandas=(1,), n=nb)[0]
            U.append(self._sar(a[None]))
            v0 = guardada.get(url, {}) or self._alin_heredada(url, lon, lat) or (inicial or {}).get(k, {}) or {}
            if v0.get("heredado_de"):
                print(f"   Umbra {k}: arranca con el desfase de {v0['heredado_de']} ({v0['km']} km): ΔE {v0['dE']} ΔN {v0['dN']} m")
            sl.append((w.IntSlider(value=int(v0.get("dE", 0)), min=-margen, max=margen, step=5, description=f"U{k} ΔE (m)",
                                   continuous_update=False, layout=w.Layout(width="420px")),
                       w.IntSlider(value=int(v0.get("dN", 0)), min=-margen, max=margen, step=5, description=f"U{k} ΔN (m)",
                                   continuous_update=False, layout=w.Layout(width="420px"))))
        out = w.Output(); msg = w.HTML()
        malla = np.zeros((n, n), bool); paso = int(round(50 / px))
        malla[::paso, :] = True; malla[:, ::paso] = True

        def dibujar(*_):
            with out:
                clear_output(wait=True)
                fig, axs = plt.subplots(1, 1 + len(U), figsize=(5.2 * (1 + len(U)), 5.4))
                axs[0].imshow(rgb); axs[0].imshow(np.ma.masked_where(~malla, malla), cmap="autumn", alpha=0.5)
                axs[0].set_title(f"Óptico DESPUÉS · {esc['despues'][0]}\n(cuadrícula 50 m)", fontsize=9)
                for k, (u, (sE, sN)) in enumerate(zip(U, sl)):
                    dx = int(round(sE.value / px)); dy = int(round(-sN.value / px))
                    sub = u[mpx + dy:mpx + dy + n, mpx + dx:mpx + dx + n]
                    axs[k + 1].imshow(sub, cmap="gray")
                    axs[k + 1].imshow(np.ma.masked_where(~bor, bor), cmap="brg_r", alpha=0.9, interpolation="nearest")
                    axs[k + 1].imshow(np.ma.masked_where(~malla, malla), cmap="autumn", alpha=0.5)
                    axs[k + 1].set_title(f"{ums[k][0].replace('Umbra-10 · ', '')}\nΔE {sE.value} m · ΔN {sN.value} m "
                                         f"(verde = bordes del óptico)", fontsize=9)
                for ax in axs:
                    ax.set_xticks([]); ax.set_yticks([])
                fig.tight_layout(); plt.show()

        for sE, sN in sl:
            sE.observe(dibujar, names="value"); sN.observe(dibujar, names="value")
        bg = w.Button(description="Guardar desfase / save", button_style="success")

        def guardar(_):
            todo = json.load(open(self.f_alin, encoding="utf-8")) if os.path.exists(self.f_alin) else {}
            todo.setdefault(sitio, {}).update({url: dict(dE=sE.value, dN=sN.value, variante="sin", fecha=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                                                         lat=lat, lon=lon) for (lab, url), (sE, sN) in zip(ums, sl)})   # conserva otras escenas del sitio
            json.dump(todo, open(self.f_alin, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            msg.value = f"✅ Desfase de <b>{sitio}</b> guardado: " + " · ".join(f"U{k + 1} ΔE {a.value} ΔN {b.value} m" for k, (a, b) in enumerate(sl))
        bg.on_click(guardar)
        display(w.VBox([w.HTML(f"<b>{sitio}</b>: mueva cada Umbra hasta que calles, espigones y bordes de edificios bajos caigan "
                               "sobre las líneas VERDES (bordes del óptico). Las torres no coincidirán (se inclinan hacia el satélite)."),
                        *[w.HBox(list(x)) for x in sl], bg, msg, out]))
        dibujar()

    def teselas(self, sitios, ventana=500, **kw):
        """Cubre el área de cada sitio con ventanas de `ventana` m (cuadrícula centrada en la coordenada dada).
        sitio = dict(nombre, lat, lon, area=lado total en m (p. ej. 1000 → 2×2 ventanas de 500 m)).
        Todas las ventanas de un sitio usan el MISMO desfase de Umbra (se mide una vez, en el centro del sitio).
        Tiles each site's area with `ventana`-m windows; one Umbra offset per site."""
        from pyproj import Transformer
        a = Transformer.from_crs(4326, 32619, always_xy=True); b = Transformer.from_crs(32619, 4326, always_xy=True)
        puntos = []
        for s_ in sitios:
            area = float(s_.get("area", ventana))
            m = max(1, int(np.ceil(area / ventana - 1e-6)))
            x0, y0 = a.transform(s_["lon"], s_["lat"])
            for i in range(m):                                         # filas de norte a sur / rows north→south
                for j in range(m):                                     # columnas de oeste a este / columns west→east
                    x = x0 + (j - (m - 1) / 2) * ventana; y = y0 - (i - (m - 1) / 2) * ventana
                    lo, la = b.transform(x, y)
                    alin_ = self._alin_guardada(s_["nombre"])
                    if alin_:
                        s_ = dict(s_, alineacion=alin_)
                    puntos.append(dict(s_, nombre=f"{s_['nombre']}{'ABCDEFGH'[i]}{j + 1}" if m > 1 else s_["nombre"], lat=la, lon=lo,
                                       grupo=s_["nombre"], centro_grupo=(s_["lon"], s_["lat"])))
        print(f"{len(puntos)} ventanas de {ventana} m en {len(sitios)} sitios / windows")
        kw.setdefault("lados", (ventana,))
        return self.lote(puntos, **kw)

    def _figura(self, capas, idioma, cx, cy, lado, dv_, fila, ancho=16):
        """Una fila de paneles (antes | después | X 1 | X 2 | verificaciones) en un idioma, con coordenadas geográficas,
        norte, escala y leyenda / one row of panels with geographic coordinates, north arrow, scale bar and legend."""
        import textwrap
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D
        k = len(capas)
        izq, abajo_in, tit_in, sup_in = 0.55, 0.45, 0.85, 0.35          # márgenes en pulgadas / margins (in)
        lado_in = (ancho - izq - 0.1) / k - 0.06
        alto = lado_in + abajo_in + tit_in + sup_in
        fig = plt.figure(figsize=(ancho, alto))
        ancho_c = max(28, int(lado_in * 11))
        for i, c in enumerate(capas):
            ax = fig.add_axes([(izq + i * (lado_in + 0.06)) / ancho, abajo_in / alto, lado_in / ancho, lado_in / alto])
            self._dibujar_panel(ax, c, idioma, cx, cy, lado, dv_, barra=(i == 0), lat_eje=(i == 0), lon_eje=True, norte=(i == 0))
            tit = (c["tit_es"] if idioma == "es" else c["tit_en"]).replace(" (SAR magenta / óptico verde)", "").replace(" (SAR magenta / optical green)", "")
            if "erific" in tit or "Check" in tit:
                sub = "SAR magenta · óptico verde" if idioma == "es" else "SAR magenta · optical green"
            else:
                lab = self._traducir(c["lab"], idioma).replace("Umbra-10 · ", "")
                sub = lab + (" · " + self._traducir(c["nota"], idioma).split(" (")[0] if c["nota"] else "")
            ax.set_title(textwrap.fill(f"({chr(97 + i)}) {tit}", ancho_c) + "\n" + textwrap.fill(sub, ancho_c), fontsize=7.5, loc="left", pad=3)
        es = idioma == "es"
        sup = (f"{fila['zona']} · centro {fila['lat']:.5f}° N, {abs(fila['lon']):.5f}° W · ventana {lado:.0f} m × {lado:.0f} m"
               if es else f"{fila['zona']} · centre {fila['lat']:.5f}° N, {abs(fila['lon']):.5f}° W · window {lado:.0f} m × {lado:.0f} m")
        fig.text(izq / ancho, 1 - 0.08 / alto, sup, ha="left", va="top", fontsize=10)
        ley = []
        if any(c["sar"] for c in capas):
            ley.append(Patch(fc="0.5", ec="0.3", label="Banda X (Umbra): brillo = retrodispersión" if es else "X-band (Umbra): brightness = backscatter"))
        if any(("erific" in c["tit_es"]) for c in capas):
            ley += [Patch(fc="#FF00FF", label="SAR (verificación)" if es else "SAR (check)"),
                    Patch(fc="#00FF00", label="Óptico (verificación)" if es else "Optical (check)"),
                    Patch(fc="#DDDDDD", ec="0.4", label="Coinciden (gris/blanco)" if es else "Match (grey/white)")]
        if len(dv_):
            ley.append(Line2D([], [], color="#FFD400", lw=1.2, label="Edificio con daño (referencia)" if es else "Damaged building (reference)"))
        if ley:
            fig.legend(handles=ley, loc="upper right", bbox_to_anchor=(1 - 0.05 / ancho, 1 - 0.02 / alto), ncol=len(ley),
                       fontsize=7.5, frameon=False, handlelength=1.2, columnspacing=1.2)
        return fig

    @staticmethod
    def _marcas_geo(cx, cy, lado):
        """Marcas redondas de longitud y latitud (en posiciones UTM) para una ventana / round lon-lat ticks in UTM positions."""
        from pyproj import Transformer
        a = Transformer.from_crs(32619, 4326, always_xy=True); b = Transformer.from_crs(4326, 32619, always_xy=True)
        lo0, la0 = a.transform(cx - lado / 2, cy - lado / 2); lo1, la1 = a.transform(cx + lado / 2, cy + lado / 2)
        lon_c, lat_c = a.transform(cx, cy)
        paso = next(p_ for p_ in (0.001, 0.002, 0.0025, 0.005, 0.01, 0.02, 0.025, 0.05, 0.1) if (lo1 - lo0) / p_ <= 3.5)
        dec = 3 if paso < 0.01 else 2
        lons = np.arange(np.ceil(lo0 / paso) * paso, lo1, paso); lats = np.arange(np.ceil(la0 / paso) * paso, la1, paso)
        xs = [b.transform(v, lat_c)[0] for v in lons]; ys = [b.transform(lon_c, v)[1] for v in lats]
        dentro = lambda v, c0: abs(v - c0) <= 0.40 * lado             # sin marcas pegadas al borde / no ticks at the edges
        X = [(x_, f"{abs(v):.{dec}f}°W") for x_, v in zip(xs, lons) if dentro(x_, cx)]
        Y = [(y_, f"{v:.{dec}f}°N") for y_, v in zip(ys, lats) if dentro(y_, cy)]
        return ([x_ for x_, _ in X], [l_ for _, l_ in X]), ([y_ for y_, _ in Y], [l_ for _, l_ in Y])

    def _dibujar_panel(self, ax, c, idioma, cx, cy, lado, dv_, barra=False, lat_eje=False, lon_eje=False, norte=False):
        from matplotlib.patches import Rectangle
        ext = [cx - lado / 2, cx + lado / 2, cy - lado / 2, cy + lado / 2]
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_linewidth(0.4)
        if c["img"] is not None:
            ax.imshow(c["img"], cmap="gray" if c["sar"] else None, extent=ext, interpolation="nearest")
            if len(dv_):
                ed = dv_[[not (g.geom_type == "Polygon" and len(g.exterior.coords) == 7) for g in dv_.geometry]]   # sin hexágonos
                if len(ed):
                    ed.boundary.plot(ax=ax, color="#FFD400", linewidth=0.5)
            ax.set_xlabel(""); ax.set_ylabel("")
        else:
            ax.set_facecolor("#f2f2f2")
            ax.text(0.5, 0.5, "sin escena" if idioma == "es" else "no scene", ha="center", va="center", transform=ax.transAxes,
                    fontsize=8, color="#666666")
        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        if lat_eje or lon_eje:
            (xs, xl), (ys, yl) = self._marcas_geo(cx, cy, lado)
            if lon_eje:
                ax.set_xticks(xs); ax.set_xticklabels(xl, fontsize=6.5)
            if lat_eje:
                ax.set_yticks(ys); ax.set_yticklabels(yl, fontsize=6.5, rotation=90, va="center")
            ax.tick_params(length=2.5, width=0.5, pad=1.5)
        if norte:                                                      # flecha de norte / north arrow
            ax.annotate("", xy=(0.92, 0.95), xytext=(0.92, 0.80), xycoords="axes fraction",
                        arrowprops=dict(arrowstyle="-|>,head_width=0.35,head_length=0.6", color="white", lw=1.6))
            ax.text(0.92, 0.75, "N", transform=ax.transAxes, ha="center", va="top", fontsize=9, color="white", weight="bold",
                    bbox=dict(fc="black", alpha=0.45, lw=0, pad=1))
        if barra:
            b = 100 if lado <= 700 else (200 if lado <= 1500 else (1000 if lado >= 4000 else 500))
            x0, y0 = ext[0] + 0.05 * lado, ext[2] + 0.05 * lado
            ax.add_patch(Rectangle((x0, y0), b, 0.012 * lado, color="white", ec="black", lw=0.5))
            ax.text(x0 + b / 2, y0 + 0.025 * lado, f"{b / 1000:g} km" if b >= 1000 else f"{b} m", ha="center", fontsize=7, color="white",
                    bbox=dict(fc="black", alpha=0.4, lw=0, pad=0.8))

    def lamina(self, sitios, nombre="lamina_destruccion", ancho=7.2):
        """Lámina de todos los sitios: filas = sitios, columnas = antes | después | X izq. | X der.; ES y EN; png, pdf y eps.
        Combined plate (rows = sites), SRL width 7.2 in."""
        import matplotlib.pyplot as plt
        nf, nc = len(sitios), max(len(x[1]) for x in sitios)
        lado_p = (ancho - 0.35) / nc
        alto = nf * (lado_p + 0.05) + 0.2
        os.makedirs(f"{self.raiz}/04_figuras/suplemento", exist_ok=True)
        for idi in ("es", "en"):
            fig = plt.figure(figsize=(ancho, alto))
            cab = [c["tit_es" if idi == "es" else "tit_en"].split(" (SAR")[0] for c in max((x[1] for x in sitios), key=len)]
            for r, (fila, capas, cx, cy, dv_) in enumerate(sitios):
                y0 = 1 - (0.2 + (r + 1) * (lado_p + 0.05) - 0.05) / alto
                for j, c in enumerate(capas[:nc]):
                    ax = fig.add_axes([(0.35 + j * lado_p) / ancho, y0, lado_p / ancho * 0.985, lado_p / alto])
                    self._dibujar_panel(ax, c, idi, cx, cy, float(fila["ventana_m"]), dv_, barra=(j == 0), norte=(j == 0))
                    fecha = (c["lab"].split("·")[0].replace("Umbra ", "").replace("Planet SkySat ", "").replace("Vantor ", "")
                             .split("(")[0].strip()[:10]) if c["lab"] else ""
                    if c["sar"] and c["lab"]:
                        izq = "left" in c["lab"]
                        fecha += (" · izq." if izq else " · der.") if idi == "es" else (" · left" if izq else " · right")
                    ax.text(0.02, 0.98, f"({chr(97 + r * nc + j) if r * nc + j < 26 else chr(97 + (r * nc + j) // 26 - 1) + chr(97 + (r * nc + j) % 26)}) {fecha}", transform=ax.transAxes, va="top", fontsize=6,
                            bbox=dict(fc="white", alpha=0.8, lw=0, pad=0.8))
                    if r == 0 and j < len(cab):
                        ax.set_title(cab[j], fontsize=7.5, pad=2)
                fig.text(0.30 / ancho, y0 + lado_p / alto / 2,
                         f"{fila['zona']} · {fila['ventana_m']:.0f} m\n{fila['lat']:.4f}°N {abs(fila['lon']):.4f}°W",
                         rotation=90, ha="right", va="center", fontsize=6.5)
            from estilo_figuras import guardar_formatos
            guardar_formatos(fig, f"{self.raiz}/04_figuras/suplemento/{nombre}_{idi}")     # pdf, eps, tiff, png
            if idi == "es":
                from IPython.display import display
                display(fig)
            plt.close(fig)
        print(f"Lámina guardada / plate saved: {self.raiz}/04_figuras/suplemento/{nombre}_es|en.png|pdf|eps")

    def campo_desfases(self, url_umbra, lon, lat, lado=1500, celda=250, url_optico=None, variante="sin", radio=100,
                       nombre=None, guardar=True):
        """CARACTERIZA cuánto y hacia dónde está corrida una Umbra respecto al óptico DESPUÉS, por celdas (tie points por NMI).
        Devuelve una tabla (x, y, ΔE, ΔN, |Δ|, confianza, altura DEM) y dibuja un mapa de flechas ES/EN.
        Si el desfase es casi igual en todas las celdas → basta un desplazamiento constante; si crece con la altura → relieve
        (layover h·cot θ); si es desordenado/con baja confianza → no hay rasgos comunes (vegetación, mar).
        Characterizes the Umbra-vs-optical offset per cell (NMI tie points): constant, height-dependent or unreliable."""
        import matplotlib.pyplot as plt
        from pyproj import Transformer
        url_optico = url_optico or self._escenas(lon, lat)["despues"][1]
        pxm = 2.5
        n_c = int(round(celda / pxm)); mp = int(round(radio / pxm))
        x0, y0 = Transformer.from_crs(4326, 32619, always_xy=True).transform(lon, lat)
        inv = Transformer.from_crs(32619, 4326, always_xy=True)
        filas = []
        m = int(lado // celda)
        for i in range(m):
            for j in range(m):
                cx = x0 - lado / 2 + (j + 0.5) * celda; cy = y0 + lado / 2 - (i + 0.5) * celda
                lo_, la_ = inv.transform(cx, cy)
                try:
                    o = self._recorte(url_optico, lo_, la_, celda, n=n_c)[:3].mean(0)
                    if (o > 0).mean() < 0.5:
                        continue
                    o = np.where(o > 0, o, np.median(o[o > 0]))
                    nb = n_c + 2 * mp
                    u = self._recorte(url_umbra, lo_, la_, nb * pxm, bandas=(1,), n=nb)[0] if variante == "sin" else \
                        self._umbra_orto(url_umbra, lo_, la_, nb * pxm, n=nb, invertir=(variante == "dem_inv"))[0]
                    val = u > 0
                    if val.mean() < 0.5:
                        continue
                    u = np.where(val, 10 * np.log10(np.where(val, u, 1)), np.nan); u = np.where(np.isfinite(u), u, np.nanmedian(u))
                    dy, dx, conf = _registrar_nmi(o, u, mp, paso=2)
                    h = float(np.nanmean(self._dem(lo_, la_, celda, 10)))
                    filas.append(dict(fila=i, col=j, x=cx, y=cy, lon=lo_, lat=la_, dE_m=dx * pxm, dN_m=-dy * pxm,
                                      mag_m=float(np.hypot(dx, dy) * pxm), conf=conf, h_m=h))
                except Exception as e:
                    print(f"celda {i},{j}: {str(e)[:60]}")
        t = pd.DataFrame(filas)
        if not len(t):
            print("Sin celdas válidas / no valid cells"); return t
        ok = t[t.conf >= CONF_MIN]
        print(f"{len(t)} celdas, {len(ok)} confiables (≥{CONF_MIN:.0f}σ). Mediana confiables: ΔE {ok.dE_m.median():+.0f} m, "
              f"ΔN {ok.dN_m.median():+.0f} m; dispersión (MAD) {np.median(np.abs(ok.dE_m - ok.dE_m.median())):.0f} / "
              f"{np.median(np.abs(ok.dN_m - ok.dN_m.median())):.0f} m" if len(ok) else "ninguna celda confiable")
        if len(ok) >= 4:
            r = np.corrcoef(ok.h_m, ok.mag_m)[0, 1]
            print(f"Correlación |Δ| vs altura / |offset| vs height: r = {r:.2f} " + ("→ el relieve explica el corrimiento" if r > 0.5 else ""))
        if guardar:
            nombre = nombre or f"campo_desfases_{lat:.4f}_{lon:.4f}"
            d = f"{self.capturas}/desfases"; os.makedirs(d, exist_ok=True)
            t.to_csv(f"{d}/{nombre}.csv", index=False)
            fondo = self._rgb(self._recorte(url_optico, lon, lat, lado, n=600))
            for idi in ("es", "en"):
                fig, ax = plt.subplots(figsize=(7, 7.4))
                ext = [x0 - lado / 2, x0 + lado / 2, y0 - lado / 2, y0 + lado / 2]
                ax.imshow(fondo, extent=ext, alpha=0.75)
                esc = 3.0                                              # flechas exageradas ×3 para verlas / arrows exaggerated ×3
                for _, r_ in t.iterrows():
                    col = "#D55E00" if r_.conf >= CONF_MIN else "#999999"
                    ax.annotate("", xy=(r_.x + esc * r_.dE_m, r_.y + esc * r_.dN_m), xytext=(r_.x, r_.y),
                                arrowprops=dict(arrowstyle="-|>", color=col, lw=1.4))
                    ax.text(r_.x, r_.y - celda * 0.3, f"{r_.mag_m:.0f} m", ha="center", fontsize=6.5,
                            color="black", bbox=dict(fc="white", alpha=0.7, lw=0, pad=0.5))
                ax.set_xlim(ext[:2]); ax.set_ylim(ext[2:])
                (xs, xl), (ys, yl) = self._marcas_geo(x0, y0, lado)
                ax.set_xticks(xs); ax.set_xticklabels(xl, fontsize=7); ax.set_yticks(ys); ax.set_yticklabels(yl, fontsize=7, rotation=90, va="center")
                es = idi == "es"
                ax.set_title(("Desfase de Umbra respecto al óptico (flechas ×3)\nnaranja = confiable · gris = baja confianza" if es else
                              "Umbra offset relative to optical (arrows ×3)\norange = reliable · grey = low confidence"), fontsize=9, loc="left")
                ax.annotate("", xy=(0.93, 0.97), xytext=(0.93, 0.86), xycoords="axes fraction", arrowprops=dict(arrowstyle="-|>", color="k", lw=1.5))
                ax.text(0.93, 0.83, "N", transform=ax.transAxes, ha="center", va="top", fontsize=9, weight="bold")
                fig.tight_layout(); fig.savefig(f"{d}/{nombre}_{idi}.png", dpi=200)
                if es:
                    from IPython.display import display
                    display(fig)
                plt.close(fig)
            print(f"Guardado / saved: {d}/{nombre}_es|en.png y .csv")
        return t

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
        dl = w.IntSlider(value=600, min=100, max=6000, step=50, description="Ventana (m)", continuous_update=False,
                         layout=w.Layout(width="420px"))
        dtam = w.IntSlider(value=16, min=10, max=30, step=2, description="Tamaño fig.", continuous_update=False)
        dalto = w.IntSlider(value=520, min=300, max=900, step=50, description="Alto mapa", continuous_update=False)
        dpre, dpost, dum, dum2 = [w.Dropdown(description=t, layout=w.Layout(width="620px"), style={"description_width": "initial"})
                                 for t in ("ANTES", "DESPUÉS", "UMBRA 1 (X)", "UMBRA 2 (otra mirada, opcional)")]
        bver, busar = w.Button(description="Ver / show", button_style="info"), w.Button(description="Usar esta / use", button_style="success")
        bborrar, blista = w.Button(description="Borrar última / undo", button_style="warning"), w.Button(description="Ver guardadas / list")
        tnota = w.Text(description="Nota", placeholder="p. ej. ventana amplia / zoom edificio")
        dcont = w.Checkbox(value=True, description="Contornos de edificios dañados / damaged outlines", indent=False)
        grec = w.Checkbox(value=True, description="Guardar recortes con todas las bandas (GeoTIFF) / save multiband chips", indent=False)
        out, msg = w.Output(), w.HTML()
        centro = {"lat": None, "lon": None}                         # centro actual de la ventana (se mueve con el ratón)
        paso = w.IntText(value=50, description="paso (m)", layout=w.Layout(width="160px"))
        bn, bs, be, bo = [w.Button(description=t, layout=w.Layout(width="42px")) for t in ("↑", "↓", "→", "←")]
        lblc = w.HTML()
        mapa_w = None
        try:
            from google.colab import output as _co
            _co.enable_custom_widget_manager()                      # necesario para ipyleaflet en Colab / needed for ipyleaflet in Colab
        except Exception:
            pass
        try:
            import ipyleaflet as L
            r0 = self.zonas.iloc[0]
            mapa_w = L.Map(center=(r0.lat, r0.lon), zoom=15, scroll_wheel_zoom=True, layout=w.Layout(height="520px", width="100%"))
            mapa_w.add_control(L.FullScreenControl())               # botón de pantalla completa / full-screen button
            mapa_w.add_layer(L.TileLayer(url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                                         name="satélite (solo para explorar)", attribution="Esri"))
            marcador = L.Marker(location=(r0.lat, r0.lon), draggable=True, title="Arrastre para mover la ventana / drag to move the window")
            rect = L.Rectangle(bounds=((r0.lat, r0.lon), (r0.lat, r0.lon)), color="#D55E00", weight=2, fill_opacity=0.05)
            # huellas de TODAS las escenas disponibles (capas activables) / footprints of ALL available scenes (toggleable)
            def _capa(g, nombre, col, etiqueta, opac=0.04):
                if g is None or not len(g):
                    return
                gg = g[["geometry"]].copy(); gg["info"] = etiqueta(g)
                mapa_w.add_layer(L.GeoJSON(data=json.loads(gg.to_json()), name=nombre,
                                           style={"color": col, "weight": 1.5, "fillOpacity": opac},
                                           hover_style={"weight": 3, "fillOpacity": 0.25}))
            _capa(self.umbra, "Umbra (X)", "#0072B2",
                  lambda g: [f"Umbra {str(t)[:16]} {s_}" for t, s_ in zip(g.inicio_utc, g.satelite)])
            if len(self.planet):
                _capa(self.planet, "Planet SkySat (después)", "#CC79A7", lambda g: [str(t)[:16] for t in g.get("datetime", g.index)])
            _capa(self.vantor[self.vantor.fase == "pre"], "Vantor ANTES", "#009E73", lambda g: list(g.fecha))
            _capa(self.vantor[self.vantor.fase == "post"], "Vantor DESPUÉS", "#555555", lambda g: list(g.fecha), opac=0.0)
            try:                                                    # daño de referencia como puntos / reference damage as points
                cen = self.danio.to_crs(32619).geometry.centroid.to_crs(4326)
                mapa_w.add_layer(L.MarkerCluster(name="Edificios dañados", markers=[L.CircleMarker(location=(p_.y, p_.x), radius=3,
                                 color="#B2182B", fill_color="#B2182B", fill_opacity=0.8, weight=0) for p_ in cen[:4000]]))
            except Exception:
                pass
            mapa_w.add_control(L.LayersControl(position="topright"))
            mapa_w.add_layer(rect); mapa_w.add_layer(marcador)
        except Exception as e:
            msg.value = f"(mapa arrastrable no disponible: {str(e)[:60]} → instale con <code>!pip install -q ipyleaflet</code>; use las flechas)"
            marcador = rect = None

        def _rect():
            dlon = dl.value / 2 / (111320 * np.cos(np.radians(centro["lat"]))); dlat = dl.value / 2 / 111320
            if rect is not None:
                rect.bounds = ((centro["lat"] - dlat, centro["lon"] - dlon), (centro["lat"] + dlat, centro["lon"] + dlon))
            lblc.value = f"centro / centre: <b>{centro['lat']:.5f}, {centro['lon']:.5f}</b> · ventana {dl.value} m"

        def mover_a(lat, lon, recentrar=False):
            centro["lat"], centro["lon"] = lat, lon
            if marcador is not None and tuple(marcador.location) != (lat, lon):
                marcador.location = (lat, lon)
            if recentrar and mapa_w is not None:
                mapa_w.center = (lat, lon)
            _rect()

        if marcador is not None:
            marcador.observe(lambda ch: mover_a(ch["new"][0], ch["new"][1]), names="location")

        def empujar(dn, de):
            dlat = dn * paso.value / 111320; dlon = de * paso.value / (111320 * np.cos(np.radians(centro["lat"])))
            mover_a(centro["lat"] + dlat, centro["lon"] + dlon)
        bn.on_click(lambda _: empujar(1, 0)); bs.on_click(lambda _: empujar(-1, 0))
        be.on_click(lambda _: empujar(0, 1)); bo.on_click(lambda _: empujar(0, -1))
        dl.observe(lambda _: _rect(), names="value")
        if mapa_w is not None:
            dalto.observe(lambda ch: setattr(mapa_w.layout, "height", f"{ch['new']}px"), names="value")

        def opciones(*_):
            r = self.zonas[self.zonas.zona == dz.value].iloc[0]; p = Point(r.lon, r.lat)
            mover_a(r.lat, r.lon, recentrar=True)
            pre = [(f"Vantor {x.fecha} (nubes {x.nubes}%)", x.url) for x in self.vantor[(self.vantor.fase == "pre") & self.vantor.contains(p)].sort_values("fecha", ascending=False).itertuples()]
            pre.append(("Planet mosaico Q1-2026 (4,8 m)", MOSAICO_PRE))
            post = [(f"Planet SkySat {str(x.datetime)[:16]}", x.url) for x in self.planet[self.planet.contains(p)].itertuples()]
            post += [(f"Vantor {x.fecha} (nubes {x.nubes}%)", x.url) for x in self.vantor[(self.vantor.fase == "post") & self.vantor.contains(p)].itertuples()]
            um = [(f"Umbra {str(x.inicio_utc)[:16]} · {x.satelite} · inc {x.incidencia_deg:.0f}° · {x.direccion_mirada}", x.url)
                  for x in self.umbra[self.umbra.contains(p)].itertuples()]
            dpre.options, dpost.options, dum.options = pre, post, um
            dum2.options = [("(ninguna / none)", None)] + um
            # sugerir para UMBRA 2 una escena con la mirada CONTRARIA a la de UMBRA 1 / suggest the opposite look
            if um:
                lado1 = "left" if "left" in dum.label else "right"
                otra = [u for u in um if ("right" if lado1 == "left" else "left") in u[0]]
                dum2.value = otra[0][1] if otra else None
            msg.value = f"<b>{r.zona}</b>: {r.n_danio} edificios dañados · {r.lat:.5f}, {r.lon:.5f} · {len(pre)} antes · {len(post)} después · {len(um)} Umbra"

        # --- Desfase de Umbra respecto al óptico: los GEC de Umbra están proyectados sobre el ELIPSOIDE (sin corrección de terreno),
        # así que cada punto se desplaza ~ h·cot(incidencia) hacia el satélite (h = altura; a 48° y 50 m ≈ 45 m). Se corrige con un
        # desplazamiento constante en la ventana: manual (barras) o automático (correlación de bordes con el óptico DESPUÉS).
        # Umbra GEC is ellipsoid-projected (no terrain correction): points shift ~h·cot(incidence) toward the sensor.
        dE2 = w.IntSlider(value=0, min=-300, max=300, step=5, description="UMBRA 2 · Este ΔE (m)", continuous_update=False,
                          style={"description_width": "initial"}, layout=w.Layout(width="360px"))
        dN2 = w.IntSlider(value=0, min=-300, max=300, step=5, description="UMBRA 2 · Norte ΔN (m)", continuous_update=False,
                          style={"description_width": "initial"}, layout=w.Layout(width="360px"))
        dE = w.IntSlider(value=0, min=-300, max=300, step=5, description="Este ΔE (m)", continuous_update=False,
                         style={"description_width": "initial"}, layout=w.Layout(width="360px"))
        dN = w.IntSlider(value=0, min=-300, max=300, step=5, description="Norte ΔN (m)", continuous_update=False,
                         style={"description_width": "initial"}, layout=w.Layout(width="360px"))
        bauto = w.Button(description="Alinear auto / auto-align", button_style="primary", layout=w.Layout(width="200px"))
        bcero = w.Button(description="Desfase 0", layout=w.Layout(width="100px"))
        bcero.on_click(lambda _: [setattr(x, "value", 0) for x in (dE, dN, dE2, dN2)])
        corr = w.Checkbox(value=True, description="Corregir relieve (DEM) / terrain-correct", indent=False)
        inv_ = w.Checkbox(value=False, description="invertir sentido / flip", indent=False)

        def _umbra(url, lo_, la_, lado, n=500):
            if corr.value:
                a, nota = self._umbra_orto(url, lo_, la_, lado, n=n, invertir=inv_.value)
                return a, nota
            return self._recorte(url, lo_, la_, lado, bandas=(1,), n=n)[0], "sin corrección de relieve"

        def _desplazado(k=1):
            if k == 2:
                return (centro["lon"] + dE2.value / (111320 * np.cos(np.radians(centro["lat"]))), centro["lat"] + dN2.value / 111320)
            # ΔE/ΔN = cuánto aparece DESPLAZADA la imagen Umbra (+ = hacia el este/norte); se lee Umbra en centro + Δ para alinearla
            la = centro["lat"] + dN.value / 111320
            lo = centro["lon"] + dE.value / (111320 * np.cos(np.radians(centro["lat"])))
            return lo, la

        def _alinear(url_u):
            """Desfase (ΔE, ΔN en m) de una escena Umbra respecto al óptico DESPUÉS, maximizando la información mutua (NMI)
            de intensidades y bordes en ±margen. Offset of one Umbra scene vs the post-event optical, by NMI grid search."""
            lado = dl.value
            n = 250
            px = lado / n
            mp = int(round(min(RADIO_ALINEACION_M, 0.4 * lado) / px))   # búsqueda limitada a lo físicamente posible               # búsqueda hasta ±150 m / search radius
            o = self._recorte(dpost.value, centro["lon"], centro["lat"], lado, n=n)[:3].mean(0)
            o = np.where(o > 0, o, np.nan)
            nb = n + 2 * mp
            u, _ = _umbra(url_u, centro["lon"], centro["lat"], nb * px, n=nb)
            val = np.isfinite(u) & (u > 0)
            if val[mp:mp + n, mp:mp + n].mean() < 0.3:
                return None, f"Umbra casi sin datos en esta ventana ({val.mean() * 100:.0f} % válido)"
            u = np.where(val, 10 * np.log10(np.where(val, u, 1.0)), np.nan)
            o = np.where(np.isfinite(o), o, np.nanmedian(o)); u = np.where(np.isfinite(u), u, np.nanmedian(u))
            dy, dx, conf = _registrar_nmi(o, u, mp)
            dE_, dN_ = int(round(dx * px / 5) * 5), int(round(-dy * px / 5) * 5)
            aviso = ""
            if not conf >= CONF_MIN:
                dE_, dN_, aviso = 0, 0, f" → coincidencia débil (máx. en {int(round(dx * px))}, {int(round(-dy * px))} m): se deja en 0"
            return (int(np.clip(dE_, -300, 300)), int(np.clip(dN_, -300, 300))), f"confianza {conf:.1f}σ{aviso}"

        def auto(_=None):
            if not (dpost.value and dum.value):
                msg.value = "Elija una escena DESPUÉS y una UMBRA 1"; return
            msg.value = "Alineando… / aligning…"
            textos = []
            for k, (url_u, sE, sN) in enumerate(((dum.value, dE, dN), (dum2.value, dE2, dN2)), start=1):
                if not url_u:
                    continue
                d_, err_ = _alinear(url_u)
                if d_ is None:
                    textos.append(f"UMBRA {k}: ⚠️ {err_}"); continue
                sE.value, sN.value = d_
                textos.append(f"UMBRA {k}: ΔE = {d_[0]} m, ΔN = {d_[1]} m · {err_}")
            msg.value = " · ".join(textos) + " — revise con «Ver»; ajuste a mano si hace falta."
            ver()
        bauto.on_click(auto)

        def _traducir(t, idioma):
            """Etiquetas de escena en español o inglés / scene labels in Spanish or English."""
            if idioma == "en":
                t = t.replace("nubes", "clouds").replace("relieve corregido", "terrain-corrected").replace("h máx", "max h")
                t = t.replace("sin corrección de relieve", "no terrain correction").replace("Planet mosaico", "Planet mosaic")
                for sen in ("Planet SkySat", "Vantor", "Planet mosaic"):
                    if t.startswith(sen):
                        t = f"Optical ({sen})" + t[len(sen):]
                        break
            else:
                t = t.replace("· left", "· mirada izquierda").replace("· right", "· mirada derecha")
            return t

        def _dibujar(capas, idioma, cx, cy, dv_, n_v):
            """Figura compacta (sin espacios entre paneles) en un idioma / compact figure in one language."""
            from matplotlib.patches import Rectangle
            L_ = dl.value
            k = len(capas)
            ancho = dtam.value
            fig = plt.figure(figsize=(ancho, ancho / k + 1.0))
            alto_tit = 0.95 / (ancho / k + 1.0)                          # ~0,95 pulgadas para títulos / title band
            for i, c in enumerate(capas):
                ax = fig.add_axes([i / k + 0.002, 0.005, 1 / k - 0.004, 1 - alto_tit - 0.01])
                ax.set_xticks([]); ax.set_yticks([])
                for sp in ax.spines.values():
                    sp.set_linewidth(0.4)
                ext = [cx - L_ / 2, cx + L_ / 2, cy - L_ / 2, cy + L_ / 2]
                if c["img"] is not None:
                    ax.imshow(c["img"], cmap="gray" if c["sar"] else None, extent=ext, interpolation="nearest")
                    if dcont.value and len(dv_):
                        dv_.boundary.plot(ax=ax, color="#FF2A00", linewidth=0.6)
                else:
                    ax.text(0.5, 0.5, ("sin escena" if idioma == "es" else "no scene") + (f"\n{c['error']}" if c["error"] else ""),
                            ha="center", va="center", transform=ax.transAxes, fontsize=8)
                ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
                letra = "abcd"[i]
                tit = c["tit_es"] if idioma == "es" else c["tit_en"]
                sub = _traducir(c["lab"], idioma) + (f"\n{_traducir(c['nota'], idioma)}" if c["nota"] else "")
                ax.set_title(f"({letra}) {tit}\n{sub}", fontsize=8, loc="left", pad=3)
                if i == 0:                                              # barra de escala / scale bar
                    b = 100 if L_ <= 1500 else 500
                    x0, y0 = ext[0] + 0.05 * L_, ext[2] + 0.05 * L_
                    ax.add_patch(Rectangle((x0, y0), b, 0.012 * L_, color="white", ec="black", lw=0.5))
                    ax.text(x0 + b / 2, y0 + 0.025 * L_, f"{b} m", ha="center", fontsize=7, color="white",
                            bbox=dict(fc="black", alpha=0.4, lw=0, pad=0.8))
            if idioma == "es":
                sup = f"{dz.value} · {centro['lat']:.5f}, {centro['lon']:.5f} · ventana {L_} m · {n_v} edificios dañados en la ventana"
            else:
                sup = f"{dz.value} · {centro['lat']:.5f}, {centro['lon']:.5f} · window {L_} m · {n_v} damaged buildings in the window"
            if dcont.value:
                sup += " (contornos rojos)" if idioma == "es" else " (red outlines)"
            fig.text(0.003, 0.995, sup, ha="left", va="top", fontsize=10)
            return fig

        def ver(_=None):
            from pyproj import Transformer as _T
            from shapely.geometry import box as _bx0
            with out:
                clear_output(wait=True)
                paneles = [("Antes", "Before", dpre.value, 0), ("Después", "After", dpost.value, 0),
                           ("Banda X (Umbra 1)", "X-band (Umbra 1)", dum.value, 1)]
                if dum2.value:
                    paneles.append(("Banda X (Umbra 2)", "X-band (Umbra 2)", dum2.value, 2))
                cx, cy = _T.from_crs(4326, 32619, always_xy=True).transform(centro["lon"], centro["lat"])
                dv_ = self.danio.to_crs(32619)
                dv_ = dv_[dv_.intersects(_bx0(cx - dl.value / 2, cy - dl.value / 2, cx + dl.value / 2, cy + dl.value / 2))]
                capas = []
                for tes, ten, url, k_u in paneles:                       # se leen UNA vez y se dibujan en los dos idiomas
                    sar = k_u > 0
                    c = dict(tit_es=tes, tit_en=ten, sar=sar, img=None, nota="", error="",
                             lab={d.value: d.label for d in (dpre, dpost, dum, dum2) if d.value}.get(url, ""))
                    if url:
                        try:
                            lo_, la_ = _desplazado(k_u) if sar else (centro["lon"], centro["lat"])
                            if sar:
                                a0, c["nota"] = _umbra(url, lo_, la_, dl.value)
                                c["img"] = self._sar(a0[None])
                                dEk, dNk = (dE, dN) if k_u == 1 else (dE2, dN2)
                                c["nota"] += f" · ΔE {dEk.value} m, ΔN {dNk.value} m"
                            else:
                                c["img"] = self._rgb(self._recorte(url, lo_, la_, dl.value, bandas=(1, 2, 3)))
                        except Exception as e:
                            c["error"] = str(e)[:60]
                    capas.append(c)
                self._figs = {idi: _dibujar(capas, idi, cx, cy, dv_, len(dv_)) for idi in ("es", "en")}
                self._fig = self._figs["es"]
                sello = f"{dz.value}_{dl.value}m_{pd.Timestamp.now():%Y%m%d_%H%M%S}"
                for idi, f_ in self._figs.items():
                    f_.savefig(f"{self.capturas}/vista_{sello}_{idi}.png", dpi=110)
                plt.close(self._figs["en"])                                # la versión en inglés se guarda, no se muestra
                display(self._figs["es"])
                plt.close(self._figs["es"])
                print("Guardada en español e inglés / saved in Spanish and English: " + f"vista_{sello}_es.png · _en.png")

        def usar(_):
            # cada guardado es una CONFIGURACIÓN nueva: la misma zona puede guardarse varias veces (otra ventana u otras escenas)
            # every save is a new CONFIGURATION: the same zone can be saved several times
            r = self.zonas[self.zonas.zona == dz.value].iloc[0]
            prev = pd.read_csv(self.salida) if os.path.exists(self.salida) else pd.DataFrame()
            from shapely.geometry import box as _bx
            dlo = dl.value / 2 / (111320 * np.cos(np.radians(centro["lat"]))); dla = dl.value / 2 / 111320
            vent = _bx(centro["lon"] - dlo, centro["lat"] - dla, centro["lon"] + dlo, centro["lat"] + dla)
            dv = self.danio[self.danio.intersects(vent)]
            por_clase = dv["clase"].astype(str).value_counts().to_dict() if "clase" in dv else {}
            fila = dict(zona=dz.value, lat=round(centro["lat"], 6), lon=round(centro["lon"], 6), ventana_m=dl.value,
                        edificios_danados=int(len(dv)), destruidos=int(sum(v for k, v in por_clase.items() if "destru" in k.lower())),
                        danados=int(sum(v for k, v in por_clase.items() if "dañ" in k.lower() or "dan" in k.lower())),
                        umbra_dE_m=dE.value, umbra_dN_m=dN.value, umbra_relieve_corregido=corr.value, umbra_invertido=inv_.value,
                        antes=dpre.label, url_antes=dpre.value, despues=dpost.label, url_despues=dpost.value,
                        umbra=dum.label, url_umbra=dum.value, umbra_mirada=("left" if "left" in dum.label else "right") if dum.value else "",
                        umbra2=(dum2.label if dum2.value else ""), url_umbra2=(dum2.value or ""),
                        umbra2_mirada=(("left" if "left" in dum2.label else "right") if dum2.value else ""),
                        umbra2_dE_m=(dE2.value if dum2.value else np.nan), umbra2_dN_m=(dN2.value if dum2.value else np.nan), nota=tnota.value, fecha_eleccion=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))
            repetida = ""
            if len(prev):
                igual = (prev.zona == fila["zona"]) & (prev.ventana_m == fila["ventana_m"]) & (prev.lat.round(5) == round(fila["lat"], 5)) & (prev.lon.round(5) == round(fila["lon"], 5)) & (prev.url_antes == fila["url_antes"]) &                         (prev.url_despues == fila["url_despues"]) & (prev.url_umbra == fila["url_umbra"]) & (prev.get("url_umbra2", pd.Series("", index=prev.index)).fillna("") == fila["url_umbra2"])
                if igual.any() and "config" in prev:                  # se guarda igual (otra composición), solo se avisa
                    repetida = str(prev.loc[igual, "config"].iloc[-1])
            # número siguiente SIN choques aunque se haya borrado alguna / next number, no clashes after deletions
            usados = prev.config.dropna().astype(str).str.extract(rf"^{dz.value}-(\d+)$")[0].dropna().astype(int) if len(prev) and "config" in prev else pd.Series([], dtype=int)
            fila["config"] = f"{dz.value}-{(usados.max() + 1) if len(usados) else 1}"   # Z1-1, Z1-2, … / configuration id
            # celda candidata donde está REALMENTE el centro (si se arrastró la ventana fuera de la zona elegida)
            dd = (self.zonas.lat - centro["lat"]) ** 2 + ((self.zonas.lon - centro["lon"]) * np.cos(np.radians(centro["lat"]))) ** 2
            fila["zona_del_centro"] = str(self.zonas.zona.iloc[int(np.argmin(dd.values))])
            fila["repetida_de"] = repetida
            figs = getattr(self, "_figs", None) or ({"es": self._fig} if self._fig is not None else {})
            for idi, f_ in figs.items():
                f_.savefig(f"{self.capturas}/ELEGIDA_{fila['config']}_{dl.value}m_{idi}.png", dpi=150)
            if figs:
                fila["captura"] = f"ELEGIDA_{fila['config']}_{dl.value}m_es.png | _en.png"
            todo = pd.concat([prev, pd.DataFrame([fila])], ignore_index=True)
            todo.to_csv(self.salida, index=False)
            n_z = int((todo.zona == dz.value).sum())
            txt = (f"✅ Guardada <b>{fila['config']}</b> (ventana {dl.value} m) · {fila['edificios_danados']} edificios dañados en la ventana "
                   f"({fila['destruidos']} destruidos) · {n_z} composiciones de {dz.value} · total {len(todo)}"
                   + (f" · (misma ventana y escenas que {repetida})" if repetida else ""))
            msg.value = txt
            if figs:
                os.makedirs(f"{self.recortes}/{fila['config']}", exist_ok=True)
                for idi, f_ in figs.items():
                    f_.savefig(f"{self.recortes}/{fila['config']}/vista_{fila['config']}_{idi}.png", dpi=150)
            if grec.value:
                msg.value = txt + " · guardando recortes multibanda… / saving chips…"
                try:
                    msg.value = txt + " · 📦 " + self.guardar_recortes(fila)
                except Exception as e:
                    msg.value = txt + f" · ⚠️ recortes no guardados: {str(e)[:100]} (reintente con ex.guardar_recortes())"

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
                    t["recortes"] = [("✓" if os.path.exists(f"{self.recortes}/{c}/meta.json") else "—") for c in t.get("config", t.zona)]
                    cols = [c for c in ("config", "zona", "lat", "lon", "ventana_m", "edificios_danados", "destruidos", "umbra_mirada",
                                        "umbra_dE_m", "umbra_dN_m", "umbra2_mirada", "umbra2_dE_m", "umbra2_dN_m", "recortes", "nota") if c in t]
                    display(t[cols])
                    print(f"Tabla completa / full table: {self.salida}\nRecortes por composición / chips: {self.recortes}/<config>/ (meta.json + .tif)")
                else:
                    print("Aún no hay configuraciones guardadas / nothing saved yet")

        dz.observe(opciones, names="value"); bver.on_click(ver); busar.on_click(usar); bborrar.on_click(borrar); blista.on_click(listar)
        opciones()
        caja = [w.HBox([dz, dl]), w.HBox([dtam, dalto]), w.HBox([bo, bn, bs, be, paso, lblc]), dpre, dpost, dum, dum2, w.VBox([w.HTML('<b>⚙️ Alinear Umbra (X) con el óptico</b> — Umbra GEC no está corregido por relieve: muévalo hasta que calles y edificios coincidan'), w.HBox([dE, dN]), w.HBox([dE2, dN2]), w.HBox([bauto, bcero, corr, inv_])], layout=w.Layout(border='1px solid #0072B2', padding='4px', margin='4px 0')), tnota, w.HBox([dcont, grec]), w.HBox([bver, busar, bborrar, blista]), msg, out]
        if mapa_w is not None:
            caja.insert(1, mapa_w)
        display(w.VBox(caja))
