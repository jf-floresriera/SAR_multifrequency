# -*- coding: utf-8 -*-
"""
Máscara de TIERRA para todas las figuras y métricas: se excluyen el MAR CARIBE y los LAGOS/EMBALSES (Lago de Valencia, Camatagua…).
Land mask for every figure and metric: the Caribbean Sea and lakes/reservoirs (Lake Valencia, Camatagua…) are excluded.
El agua no es coherente: en un interferograma solo aporta ruido. / Water is incoherent: it only adds noise to an interferogram.
Capas: tierra = límites estatales de Venezuela (geoBoundaries, capa `venezuela_estados`) o países (Natural Earth);
agua interior = Natural Earth 1:10m lakes (dominio público), guardada en el gpkg como `lagos_ne10` la primera vez.
Uso / usage:  from mascaras import mascara_tierra;  m = mascara_tierra(RAIZ, transform, (ny, nx), crs="EPSG:4326")
"""
import geopandas as gpd
import numpy as np
from rasterio.features import rasterize
from shapely.geometry import box

_CACHE = {}
_LAGOS_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_lakes.geojson"
_BBOX = box(-70.5, 9.0, -64.5, 11.8)


def _gpkg(raiz):
    return f"{raiz}/01_datos_crudos/mapas_base/mapas_base.gpkg"


def capa_tierra(raiz):
    for capa in ("venezuela_estados", "paises_sudamerica_ne50"):
        try:
            return gpd.read_file(_gpkg(raiz), layer=capa)
        except Exception:
            continue
    return None


def capa_lagos(raiz):
    try:
        return gpd.read_file(_gpkg(raiz), layer="lagos_ne10")
    except Exception:
        pass
    try:
        g = gpd.read_file(_LAGOS_URL)
        g = g[g.intersects(_BBOX)][["name", "featurecla", "geometry"]].to_crs(4326)
        try:
            g.to_file(_gpkg(raiz), layer="lagos_ne10", driver="GPKG")     # se guarda para no bajarla otra vez / cached
        except Exception:
            pass
        return g
    except Exception as e:
        print("[!] sin capa de lagos (Natural Earth) / no lakes layer:", e)
        return None


def mascara_tierra(raiz, transform, shape, crs="EPSG:4326"):
    """True = tierra firme (sin mar ni lagos). None si no hay capa de tierra. / True = dry land; None if no land layer."""
    clave = (raiz, tuple(transform)[:6], tuple(shape), str(crs))
    if clave in _CACHE:
        return _CACHE[clave]
    t = capa_tierra(raiz)
    if t is None:
        _CACHE[clave] = None
        return None
    t = t.to_crs(crs)
    m = rasterize([(g, 1) for g in t.geometry if g is not None], out_shape=shape, transform=transform, all_touched=False).astype(bool)
    lagos = capa_lagos(raiz)
    if lagos is not None and len(lagos):
        lg = lagos.to_crs(crs)
        agua = rasterize([(g, 1) for g in lg.geometry if g is not None], out_shape=shape, transform=transform, all_touched=True).astype(bool)
        m &= ~agua
    _CACHE[clave] = m
    return m


def solo_tierra(arr, raiz, transform, crs="EPSG:4326"):
    """Devuelve una copia con NaN sobre mar y lagos / copy with NaN over sea and lakes."""
    m = mascara_tierra(raiz, transform, arr.shape, crs)
    return arr if m is None else np.where(m, arr, np.nan)
