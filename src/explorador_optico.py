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
        self.recortes = f"{raiz}/02_procesados/recortes_zonas"             # recortes multibanda por configuración / multiband chips
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
        for k, (cu, cE, cN, cm, ci) in enumerate((("url_umbra", "umbra_dE_m", "umbra_dN_m", "umbra_mirada", "umbra"),
                                                  ("url_umbra2", "umbra2_dE_m", "umbra2_dN_m", "umbra2_mirada", "umbra2")), start=1):
            url = f.get(cu)
            if not (isinstance(url, str) and url):
                continue
            dE_ = float(f.get(cE)) if pd.notna(f.get(cE)) else 0.0
            dN_ = float(f.get(cN)) if pd.notna(f.get(cN)) else 0.0
            mir = f.get(cm) if isinstance(f.get(cm), str) and f.get(cm) else ("left" if "left" in str(f.get(ci)) else "right")
            lo_ = lon + dE_ / (111320 * np.cos(np.radians(lat))); la_ = lat + dN_ / 111320
            try:
                if self._si(f.get("umbra_relieve_corregido"), True):
                    a, _ = self._umbra_orto(url, lo_, la_, lado, n=n, invertir=self._si(f.get("umbra_invertido"), False))
                else:
                    a = self._recorte(url, lo_, la_, lado, bandas=(1,), n=n)[0]
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
            mp = int(round(min(150.0, 0.4 * lado) / px))               # búsqueda hasta ±150 m / search radius
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
            aviso = "" if conf >= 3 else " (confianza baja: revise a mano)"
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
