# Traspaso de trabajo / Work handoff · 2026-11-26

> 🇪🇸 Estado real del proyecto **verificado el 26-nov-2026** contra el Drive del autor y los cuadernos de Colab. Complementa `PROYECTO.md` (que describe el plan) con lo que **de verdad existe**, lo que falta y lo que NO hay que repetir.
> 🇬🇧 Real project state **verified on 2026-11-26** against the author's Drive and Colab notebooks. Complements `PROYECTO.md` (the plan) with what **actually exists**, what is missing and what must NOT be repeated.

## 1. Regla de oro: no repetir procesamiento / Golden rule: do not redo work
- Un trabajo HyP3 se identifica por **par de escenas + resolución**, no por nombre (`src/registro_datos.py`, usado por `s1_pares_hyp3.py`). Esto evita reenvíos: antes 025D se envió 4 veces y 033A (nombre distinto) habría vuelto a enviarse.
- Orden de decisión: (1) ¿ya está el ZIP en Drive? → no; (2) ¿hay un trabajo vigente del mismo par y resolución? → reusar; (3) solo entonces enviar. `FORZAR_ENVIO = True` repite a propósito.
- Los productos HyP3 **caducan a los ~14 días**. Descargar siempre a Drive (`hyp3_estado.py`).

## 2. Qué existe hoy / What exists today (Drive: `InSAR_LaGuaira_Resultados/`)

| Dato / Data | Estado | Ubicación (relativa a `GUAIRA-SAR/01_datos_crudos/` salvo indicación) |
|---|---|---|
| Sentinel-1 **025D**, 40 m (INT40), 18→25 jun | ✅ descargado, **3 copias idénticas** (usar 1; ~2,2 GB sobran) | `sentinel1_hyp3/` |
| Sentinel-1 **033A** (job `Sismo_LaGuaira_S1_Path33`), **80 m** (INT80), 18→25 jun | ✅ descargado, 2 copias | `sentinel1_hyp3/` |
| Sentinel-1 033A a **40 m** | ❌ no existe. **Decisión recomendada: enviar UN trabajo** (consistencia con 025D y análisis urbano) | — |
| NISAR GUNW **061A, 162A, 126D** cosísmicos (2,3 GB c/u) | ✅ descargados | carpeta `datos_nisar_vargas/` en la raíz de Drive (`inventario_2026/`); `descargas.py` los copia a `nisar_gunw/` |
| NISAR 054D | no necesario: cubre 0 % de La Guaira | — |
| Inventario NISAR / Umbra / Planet (CSV) | ✅ | `inventario_2026/{nisar_filtrado,umbra_inventario,umbra_planet_sitios}/` |
| Figuras Umbra × Planet v2 (6 sitios, ES/EN) | ✅ pero **no publicables** (ver §4) | `inventario_2026/umbra_planet_sitios/` |
| Umbra GEC | ⏳ sin descargar | — |
| ALOS-2 | ❌ **nunca se obtuvo ni procesó** (ver §5) | — |
| GNSS CCS1 (coordenadas exactas) | ❌ pendiente | — |
| `GUAIRA-SAR/04_figuras/` | vacía (solo `borradores/`) | — |

Cuadernos de Colab del autor (en Drive; las **salidas guardadas contienen figuras**): `SAR_Multifrequency` (lanzador, 9 celdas), `VargaS_Earthquake` (exploración original del 5-nov, 47 celdas, S1 + NISAR + Esri), `Inventario_Multisensor_Venezuela_2026` (inventario del 19-nov). Las figuras se pueden extraer de las salidas `image/png` del `.ipynb`.

## 3. Hallazgos científicos y de calidad a tener en cuenta / Findings to keep in mind
- En `VargaS_Earthquake` el desplazamiento NISAR (126D, ±20 rad) **no muestra patrón claro** de deformación: revisar ionosfera/referencia antes de publicar. El interferograma S1 mezcla "radianes" y "cm" en la misma barra de color.
- La dispersión DEM-vs-desplazamiento de S1 da R² = 0,25: **hay fase correlacionada con la topografía (atmósfera)**; corregir (regresión fase-elevación o ERA5/GACOS).
- El daño de referencia (HOTOSM fAIr/Microsoft) es **automático**: tiene ruido de etiqueta; contrastar con el subconjunto validado.
- Umbra cubre solo 3 de los 6 sitios (Catia La Mar, Playa Grande, La Guaira).

## 4. Figuras: lo existente NO sirve tal cual / Existing figures are NOT publishable as is
Todas tienen título interno, rótulos A/B/1/2 en vez de (a)(b), paleta jet, mosaicos Esri (licencia restrictiva), texto pequeño y solo español. **Rehacer** con `src/estilo_figuras.py` (ver `ESTILO_FIGURAS.md`). Clasificación:
- Rehacer con datos que ya existen: línea de tiempo (Fig. 2), mapa de cobertura sin Esri (Fig. 1), Umbra × Planet por sitio (Fig. 8).
- Rehacer desde los productos: interferogramas S1/NISAR, perfil a través de la falla, histograma.
- Conservar la idea: dispersión DEM-desplazamiento (diagnóstico atmosférico).
- Descartar: mosaico de 4 sitios con paneles negros, franja "Zonas críticas", figura del viaducto.
- **Planet es CC BY-NC y Esri es restrictivo: no subir esas imágenes al repositorio.**

## 5. ALOS-2: por qué está pendiente y cuándo hacerlo / ALOS-2 status
- Solo existe `alos2_buscar.py` (una búsqueda en ASF); no hay evidencia de que haya devuelto escenas. `VargaS_Earthquake` buscó **ALOS-1 (terminó en 2011) → 0 escenas**: no es ALOS-2.
- JAXA liberó el ScanSAR del sismo el 3-jul-2026; el espejo de ASF llega con retraso. Si ASF no lo tiene: portal de JAXA, o **citar** los LOS ALOS-2 de Scripps/UCSD.
- Procesarlo exige GMTSAR o ISCE2 (ScanSAR en ráfagas, pesado). **Cuándo:** después de (1) 033A a 40 m, (2) E/U en C y L con S1 + NISAR, (3) validación GNSS. **Fecha de corte propuesta: 5-dic-2026**; si no está procesado, ALOS-2 pasa al suplemento / trabajo futuro y el artículo se sostiene con S1 + NISAR (+ UCSD citado).
- Otras bandas/sensores que se podrían sumar (**disponibilidad para este evento NO verificada**): SAOCOM (L, CONAE), TerraSAR-X/TanDEM-X y COSMO-SkyMed (X), ICEYE y Capella (X, programas de datos abiertos), RADARSAT-2/RCM (C), ALOS-4 (L).

## 6. Siguiente trabajo, en orden / Next work, in order
1. Rehacer Fig. 2, Fig. 1 y Fig. 8 con `estilo_figuras.py` (datos ya en Drive).
2. Cuaderno maestro único (`notebooks/00_Maestro.ipynb`): `git pull` → inventario de Drive → solo lo que falta → procesa → figuras ES/EN. Celdas ya ejecutadas marcadas "hecho 19-nov" y con salto automático si existe la salida.
3. Enviar 033A a 40 m (1 trabajo) y descargar. 4. GNSS CCS1. 5. E/U C y L, L − C. 6. Estadísticas (ver `ESTILO_FIGURAS.md` §5). 7. Fig. 6, 7, 9, 10 y Tabla 3. 8. Manuscrito completo (hoy ~400 palabras). 9. Zenodo y envío ≤ 18-dic.

## 7. Seguridad y licencias / Security and licences
- **Nunca** escribir credenciales de Earthdata en celdas: usar *Secretos* de Colab o `.netrc`. Las salidas guardadas de un cuaderno antiguo contienen el nombre de usuario; limpiar salidas antes de compartir cuadernos.
- No subir datos pesados ni imágenes con licencia restrictiva (`.gitignore` ya excluye `*.tif`, `*.h5`, `*.zip`).
- Entorno: usar un `venv`/conda propio; no modificar el entorno global.
