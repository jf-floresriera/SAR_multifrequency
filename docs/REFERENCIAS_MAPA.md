# Puntos y capas de referencia para los mapas / Reference points and layers for maps

> 🇪🇸 Para que los mapas no queden vacíos: qué etiquetar y de dónde sacarlo. Las coordenadas marcadas **aprox.** deben verificarse con OSM/IGVSB antes de publicar; las demás vienen de este repositorio.
> 🇬🇧 So maps are not left empty: what to label and where to get it. Coordinates marked **approx.** must be verified before publication.

## 1. Evento
| Elemento | Valor | Fuente |
|---|---|---|
| Doblete 24-jun-2026 | USGS `us6000t7zc` (Mw 7,2) y `us6000t7zp` (Mw 7,5; ~10,622° N, 67,194° W) | USGS |
| Sismo (UTC) | 2026-06-24 22:04:33 (local = UTC − 4 h) | `s1_pares_hyp3.py` |
| Falla principal | San Sebastián (con Boconó en la ruptura multifalla) | Seismic Record 6(4) 2026 |

## 2. Sitios de daño (de `PROYECTO.md`)
Catia La Mar (10,6055; −67,0324) · Playa Grande/Urimare (10,6100; −67,0103) · La Guaira (10,6000; −66,9331) · Caraballeda (10,6122; −66,8519) · Tanaguarena (10,6150; −66,8200) · Naiguatá (10,6200; −66,7400). Umbra cubre solo los tres primeros.

## 3. Referencias geográficas sugeridas (verificar)
| Elemento | Coordenada aprox. | Uso |
|---|---|---|
| Caracas (centro) | 10,50° N; −66,91° W | contexto urbano, límite sur de la Cordillera de la Costa |
| Aeropuerto Simón Bolívar (Maiquetía, SVMI) | 10,60° N; −66,99° W | infraestructura crítica (Fig. 10) |
| Puerto de La Guaira | ≈ sitio La Guaira | infraestructura crítica (Fig. 10) |
| Viaducto N.º 1 Caracas–La Guaira | **tomar de OSM** (sin coordenada fiable aquí) | perfil de deformación (Fig. 10) |
| Macuto | ≈ 10,61° N; −66,89° W | etiqueta entre La Guaira y Caraballeda |
| Valencia · Puerto Cabello | ≈ 10,18° N, −68,00° W · ≈ 10,47° N, −68,01° W | extremo oeste del recuadro macro |

## 4. Áreas de interés de Planet (nombres reales del catálogo)
`caracas`, `catia-la-mar`, `la-guaira`, `independencia-ocumare`, `puerto-cabello`, `valencia`, `yumare` (carpeta `planet/disasterdata/venezuela-earthquake-2026-06-24/post-event/`).

## 5. Capas y script
| Capa | Fuente | Licencia | Script |
|---|---|---|---|
| Límites ADM0–ADM2 | geoBoundaries | CC BY 4.0 | `mapas_base.py` |
| Fallas activas | GEM Global Active Faults | CC BY-SA 4.0 | `mapas_base.py` |
| Vías, puertos, aeropuertos, costa | OpenStreetMap | ODbL | `mapas_base.py` |
| Epicentros | USGS | dominio público | `mapas_base.py` |
| Relieve (sombreado gris) | SRTM / Copernicus DEM | verificar | *pendiente* |
| Cobertura del suelo | ESA WorldCover | CC BY 4.0 | *pendiente* (Fig. 6) |
| GNSS | CCS1 y vecinas (NGL / IGVSB) | citado | *pendiente* |

Contexto adicional que citar/consultar: el trabajo de Scripps/UCSD (`topex.ucsd.edu/VNZ_7.5`) como **referencia de estilo y de comparación**, no como base del análisis. El artículo de la BBC Mundo (`cpv38w3zg2ko`) **no pudo leerse** desde el entorno del asistente; si se usa, extraer manualmente fecha, cifras y zonas, y tratarlo como contexto periodístico, no como validación.
