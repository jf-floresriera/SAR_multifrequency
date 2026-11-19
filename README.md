# GUAIRA-SAR · SAR_multifrequency

**🇬🇧 From fault to façade: multi-frequency SAR (C-, L- and X-band) and high-resolution optical observations of the 24 June 2026 Venezuela earthquake doublet along the La Guaira coast**

**🇪🇸 De la falla a la fachada: observaciones SAR multifrecuencia (bandas C, L y X) y ópticas de alta resolución del doblete sísmico del 24 de junio de 2026 en Venezuela, a lo largo de la costa de La Guaira**

| Notebook | 🇪🇸 | 🇬🇧 | Colab |
|---|---|---|---|
| **01 · Inventario** | Encontrar y clasificar los datos | Find and classify the data | [![Open](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jf-floresriera/SAR_multifrequency/blob/main/notebooks/01_Inventario.ipynb) |
| **02 · Descargas + HyP3** | Enviar Sentinel-1 a HyP3 y descargar todo | Submit Sentinel-1 to HyP3 and download | [![Open](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jf-floresriera/SAR_multifrequency/blob/main/notebooks/02_Descargas_HyP3.ipynb) |
| **03 · InSAR C y L** | Deformación: LOS, Este/Vertical, GNSS | Deformation: LOS, East/Up, GNSS | [![Open](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jf-floresriera/SAR_multifrequency/blob/main/notebooks/03_InSAR_C_L.ipynb) |
| **04 · Daño X + óptico** | Umbra × Planet en sitios de daño | Umbra × Planet at damage sites | [![Open](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jf-floresriera/SAR_multifrequency/blob/main/notebooks/04_Danio_X_Optico.ipynb) |
![License: MIT](https://img.shields.io/badge/code-MIT-blue)
![Status](https://img.shields.io/badge/status-in%20progress%20%2F%20en%20curso-orange)
![Target](https://img.shields.io/badge/SRL-Focus%20Section%202026-8A2BE2)

| 🇬🇧 English | 🇪🇸 Español |
|---|---|
| Reproducible, open-data workflow for a manuscript in preparation for the *Seismological Research Letters* Focus Section on the **2026 Venezuela, Colombia and Panama Earthquakes**. | Flujo de trabajo reproducible y con datos abiertos para un artículo en preparación para la sección especial de *Seismological Research Letters* sobre los **sismos de 2026 en Venezuela, Colombia y Panamá**. |

---

## 1 · The event / El evento

| 🇬🇧 | 🇪🇸 |
|---|---|
| On 24 June 2026 a strike-slip earthquake doublet (Mw 7.2 at 22:04:33 UTC, followed 30–40 s later by Mw 7.5) ruptured the San Sebastián – Boconó fault system along the northern coast of Venezuela. La Guaira state, between Catia La Mar and Caraballeda, concentrated the most severe damage. | El 24 de junio de 2026 un doblete sísmico de rumbo (Mw 7,2 a las 22:04:33 UTC y, 30–40 s después, Mw 7,5) rompió el sistema de fallas San Sebastián – Boconó en la costa norte de Venezuela. El estado La Guaira, entre Catia La Mar y Caraballeda, concentró los daños más graves. |

## 2 · Scientific question / Pregunta científica

| 🇬🇧 | 🇪🇸 |
|---|---|
| **How do SAR frequency and resolution shape what we observe of the same earthquake?** We compare coseismic deformation in **C-band (Sentinel-1)** and **L-band (NISAR, ALOS-2)**, both with ascending and descending geometry to retrieve **East and Up**, and building-scale damage from **sub-metre X-band SAR (Umbra, day and night)** versus **0.5–3 m optical imagery (Planet)**. | **¿Cómo cambia lo que observamos de un mismo sismo según la frecuencia y la resolución del radar?** Comparamos la deformación cosísmica en **banda C (Sentinel-1)** y **banda L (NISAR, ALOS-2)**, ambas con órbita ascendente y descendente para obtener **Este y Vertical**, y el daño a escala de edificio con **radar banda X submétrico (Umbra, de día y de noche)** frente a **imágenes ópticas de 0,5–3 m (Planet)**. |

## 3 · Workflow / Flujo de trabajo

| 🇪🇸 Español | 🇬🇧 English |
|---|---|
| <img src="docs/img/flujo_trabajo_es.gif" width="400" alt="Flujo de trabajo animado"> | <img src="docs/img/flujo_trabajo_en.gif" width="400" alt="Animated workflow"> |

| Step / Paso | 🇬🇧 What is done | 🇪🇸 Qué se hace | Code / Código |
|---|---|---|---|
| **1** | Discover every open dataset; classify NISAR GUNW as pre-, co- or post-seismic; Umbra STAC metadata; Umbra × Planet overlaps; Sentinel-1 coseismic pairs; licences and access dates | Buscar todos los datos abiertos; clasificar los GUNW de NISAR en pre, co y postsísmicos; metadatos STAC de Umbra; cruces Umbra × Planet; pares cosísmicos de Sentinel-1; licencias y fechas de acceso | `01_Inventario` · `02_Descargas_HyP3` |
| **2a** | Phase → LOS (m) with **one sign convention for all sensors**; coherence ≥ 0.3; NISAR ionosphere; common UTM 19N 80 m grid | Fase → LOS (m) con **un solo signo para todos los sensores**; coherencia ≥ 0,3; ionosfera NISAR; grilla común UTM 19N de 80 m | `03_InSAR_C_L` |
| **2b** | Per damage site: Umbra amplitude (Lee), texture (local CV) and normalised difference look index (NDLI) vs. Planet before/after, with a 300 m zoom | Por sitio de daño: amplitud Umbra (Lee), textura (CV local) e índice de diferencia de miradas (NDLI) frente a Planet antes/después, con acercamiento de 300 m | `04_Danio_X_Optico` |
| **3** | Asc + desc least-squares **East/Up**, separately for **C** and **L**; L − C difference maps; GNSS check at CCS1 | **Este/Vertical** por mínimos cuadrados con asc + desc, por separado en **C** y **L**; mapas de diferencia L − C; validación GNSS en CCS1 | `03_InSAR_C_L` |
| **4** | Damage vs. deformation gradient and distance to the fault; airport, port and viaduct profiles | Daño frente a gradiente de deformación y distancia a la falla; perfiles en aeropuerto, puerto y viaducto | *in progress / en curso* |
| **5** | GitHub release → Zenodo DOI; derived products on Zenodo; *Data and Resources* section | Versión en GitHub → DOI de Zenodo; productos derivados en Zenodo; sección *Data and Resources* | — |

## 4 · Data / Datos

| 🇪🇸 Español | 🇬🇧 English |
|---|---|
| <img src="docs/img/linea_tiempo_sensores_es.gif" width="420" alt="Línea de tiempo animada de adquisiciones"> | <img src="docs/img/linea_tiempo_sensores_en.gif" width="420" alt="Animated acquisition timeline"> |

| Band / Banda (λ) | Sensor | 🇬🇧 What we use · 🇪🇸 Qué usamos | Dates / Fechas (2026) | Licence / Licencia |
|---|---|---|---|---|
| **C** (5.55 cm) | Sentinel-1A/1D | HyP3 INSAR_GAMMA · tracks **033A** + **025D** · 40 m · look vectors / vectores de mirada | 18 → 25 Jun | Copernicus (free / libre) |
| **L** (23.8 cm) | NISAR | GUNW · **061A**, **162A** (asc) + **126D** (desc) + 054D | 13 Jun → 4 Jul (12 d) | NASA (free / libre) |
| **L** (23.8 cm) | ALOS-2 PALSAR-2 | ScanSAR L1.1 · *pending / pendiente* | JAXA obs. from / desde 30 Jun | JAXA free release (3 Jul 2026) |
| **X** (3.1 cm) | Umbra | 26 spotlight (GEC, SICD, SIDD) · post-event only, several at night / solo post-evento, varias nocturnas | 26 Jun → 2 Jul | CC BY 4.0 |
| Optical / Óptico | Planet SkySat · PlanetScope | 17 post-event / después + Q1-2026 mosaic / mosaico previo | 26–28 Jun · Jan–Mar | CC BY-NC 4.0 (not redistributed / no se redistribuye) |
| Optical / Óptico | Sentinel-2 L2A | True colour / color verdadero | Jun–Jul | Copernicus |
| GNSS | CCS1 (+ others / otras) | Coseismic offsets for validation / desplazamientos para validar | — | Cited / citado |
| Base maps / Mapas base | geoBoundaries · GEM GAF-DB · OpenStreetMap · USGS | States, municipalities, active faults, main roads, epicentres / estados, municipios, fallas activas, vías, epicentros | — | CC BY 4.0 · CC BY-SA 4.0 · ODbL · public domain |

| 🇪🇸 Español | 🇬🇧 English |
|---|---|
| <img src="docs/img/mapa_umbra_por_dia_es.gif" width="420" alt="Mapa animado de las 26 escenas Umbra"> | <img src="docs/img/mapa_umbra_por_dia_en.gif" width="420" alt="Animated map of the 26 Umbra collects"> |

| 🇬🇧 | 🇪🇸 |
|---|---|
| **Umbra coverage:** La Guaira coast (left + right look), eastern Caracas, Guarenas–Guatire (11 collects), Ocumare / Henri Pittier (left + right look) and Yumare (near the Mw 7.2 epicentre). There is no repeat-pass geometry, so X-band is used for amplitude-based damage mapping, not InSAR. | **Cobertura Umbra:** costa de La Guaira (mirada izquierda + derecha), Caracas este, Guarenas–Guatire (11 escenas), Ocumare / Henri Pittier (izquierda + derecha) y Yumare (cerca del epicentro del Mw 7,2). No hay geometría repetida, así que la banda X se usa para mapear daño con la amplitud, no para InSAR. |

## 5 · Preliminary results / Resultados preliminares

> 🇬🇧 First-pass figures from the exploratory notebook (Sentinel-1 track 033A at 80 m, NISAR GUNW). They will be replaced by the harmonised C/L products of step 3.
> 🇪🇸 Figuras de la primera aproximación (Sentinel-1 track 033A a 80 m, NISAR GUNW). Se reemplazarán por los productos armonizados C/L del paso 3.

| 🇪🇸 Español | 🇬🇧 English |
|---|---|
| <img src="docs/img/cobertura_nisar_umbra_es.jpg" width="420" alt="Cobertura NISAR y Umbra"> | <img src="docs/img/cobertura_nisar_umbra_en.jpg" width="420" alt="NISAR and Umbra coverage"> |
| Huellas GUNW de NISAR (co, pre y postsísmicas) y escenas Umbra. | NISAR GUNW footprints (co-, pre-, post-seismic) and Umbra collects. |
| <img src="docs/img/sitio_playa_grande_es.jpg" width="420" alt="Playa Grande: Planet y Umbra"> | <img src="docs/img/sitio_playa_grande_en.jpg" width="420" alt="Playa Grande: Planet and Umbra"> |
| Playa Grande (Urimare): Planet antes/después, amplitud y textura Umbra, NDLI y acercamiento de 300 m. | Playa Grande (Urimare): Planet before/after, Umbra amplitude and texture, NDLI and 300 m zoom. |
| <img src="docs/img/sitio_catia_la_mar_es.jpg" width="420" alt="Catia La Mar"> | <img src="docs/img/sitio_catia_la_mar_en.jpg" width="420" alt="Catia La Mar"> |
| Catia La Mar (mosaico de escenas Umbra para cubrir el sitio completo). | Catia La Mar (Umbra scene mosaic to cover the full site). |

| Sentinel-1 033A (80 m) · 🇪🇸 primera aproximación / 🇬🇧 first pass | |
|---|---|
| <img src="docs/img/prelim_s1_coherencia_fase_los.jpg" width="420" alt="Sentinel-1 coherence, wrapped phase, LOS"> | <img src="docs/img/prelim_s1_zooms_guaira.jpg" width="420" alt="Sentinel-1 LOS zooms"> |
| 🇪🇸 Coherencia, interferograma envuelto y LOS. 🇬🇧 Coherence, wrapped interferogram and LOS. | 🇪🇸 Acercamientos del LOS. 🇬🇧 LOS zooms. |
| <img src="docs/img/prelim_s1_correlacion_dem.jpg" width="420" alt="LOS vs DEM"> | <img src="docs/img/prelim_s1_viaducto.jpg" width="420" alt="Viaduct profile"> |
| 🇪🇸 LOS vs. elevación (control troposférico). 🇬🇧 LOS vs. elevation (tropospheric check). | 🇪🇸 Perfil exploratorio del Viaducto N° 1 (80 m; se rehará a 40 m y con Umbra). 🇬🇧 Exploratory Viaduct No. 1 profile (80 m; to be redone at 40 m and with Umbra). |

## 6 · How to run / Cómo ejecutar

| 🇬🇧 Google Colab (recommended) | 🇪🇸 Google Colab (recomendado) |
|---|---|
| 1. Open notebooks **01 → 02 → 03 → 04** with the badges above.<br>2. Cell **0** installs libraries, pulls the latest code from this repository, mounts Drive and logs the code version (`05_documentacion/versiones_codigo.csv`).<br>3. Every other cell is one line: `%run -i {SRC}/script.py`. All logic lives in `src/`.<br>4. If Colab restarts, run cell 0 again; results already in Drive are kept. | 1. Abra los notebooks **01 → 02 → 03 → 04** con los botones de arriba.<br>2. La celda **0** instala librerías, baja la última versión del código de este repositorio, monta Drive y registra la versión usada (`05_documentacion/versiones_codigo.csv`).<br>3. Las demás celdas son de una línea: `%run -i {SRC}/script.py`. Toda la lógica vive en `src/`.<br>4. Si Colab se reinicia, corra la celda 0 otra vez; lo guardado en Drive no se pierde. |

| 🇬🇧 Development cycle | 🇪🇸 Ciclo de desarrollo |
|---|---|
| Error in Colab → fix the script in `src/` on GitHub → re-run cell 0 (pulls the fix) → re-run the cell. Every result is tied to a commit. | Error en Colab → se corrige el script en `src/` en GitHub → se vuelve a correr la celda 0 (baja la corrección) → se vuelve a correr la celda. Cada resultado queda ligado a un commit. |

```bash
# Local
git clone https://github.com/jf-floresriera/SAR_multifrequency.git
cd SAR_multifrequency
conda env create -f environment.yml
conda activate guaira-sar
jupyter lab notebooks/

# Regenerate README animations / Regenerar las animaciones del README
python docs/make_animations.py
```

## 7 · Repository layout / Estructura del repositorio

```
SAR_multifrequency/
├── notebooks/                 # short cells: setup + %run / celdas cortas: preparación + %run
│   ├── 01_Inventario.ipynb
│   ├── 02_Descargas_HyP3.ipynb
│   ├── 03_InSAR_C_L.ipynb
│   └── 04_Danio_X_Optico.ipynb
├── src/                       # all the logic / toda la lógica
│   ├── umbra_inventario.py · nisar_filtrar.py · s1_pares_hyp3.py · inventario_multisensor.py · mapas_base.py   (01)
│   ├── descargas.py · hyp3_estado.py                                                           (02)
│   ├── alos2_buscar.py · auxiliares.py · nisar_gunw_a_geotiff.py · s1_hyp3_a_geotiff.py · descomposicion_C_L.py   (03)
│   ├── umbra_planet_sitios.py · exportar_figuras_github.py                                    (04)
│   └── comun.py   # ES/EN outputs + logs / salidas ES/EN + registros
├── docs/
│   ├── img/                   # README figures and animations / figuras y animaciones
│   ├── make_animations.py     # reproducible GIF generator / generador reproducible de GIF
│   └── notas_procesamiento.md # processing log / bitácora de procesamiento
├── figures/                   # final SRL figures / figuras finales para SRL
├── environment.yml · CITATION.cff · LICENSE
```

| 🇬🇧 | 🇪🇸 |
|---|---|
| Heavy data (`.h5`, `.tif`, `.zip`, `.nitf`) are **never** committed; they live in Google Drive during processing, and derived products will be archived on Zenodo. | Los datos pesados (`.h5`, `.tif`, `.zip`, `.nitf`) **nunca** se suben al repositorio; viven en Google Drive durante el procesamiento y los productos derivados se archivarán en Zenodo. |

## 8 · Outputs and logs / Salidas y registros

| 🇬🇧 | 🇪🇸 |
|---|---|
| **Every figure** is saved twice: `<name>_es.png` (Spanish) and `<name>_en.png` (English); timeline and decomposition also as vector PDF. **Every table**: `<name>.csv` (Spanish, used by the pipeline) and `<name>_en.csv` (English headers and values). **Every notebook cell** writes its printed output and any error to `05_documentacion/logs/<date>_<notebook>_<script>.log`, and each session logs the code version (commit) to `05_documentacion/versiones_codigo.csv`. | **Cada figura** se guarda dos veces: `<nombre>_es.png` (español) y `<nombre>_en.png` (inglés); la línea de tiempo y la descomposición también en PDF vectorial. **Cada tabla**: `<nombre>.csv` (español, la usa el flujo) y `<nombre>_en.csv` (encabezados y valores en inglés). **Cada celda** guarda lo que imprime y cualquier error en `05_documentacion/logs/<fecha>_<notebook>_<script>.log`, y cada sesión registra la versión del código (commit) en `05_documentacion/versiones_codigo.csv`. |

## 9 · Conventions / Convenciones

| Item / Elemento | 🇬🇧 | 🇪🇸 |
|---|---|---|
| LOS sign / Signo LOS | **+ = toward the satellite**, all sensors | **+ = hacia el satélite**, todos los sensores |
| Units / Unidades | metres | metros |
| Grid / Grilla | UTM 19N (EPSG:32619), 80 m | UTM 19N (EPSG:32619), 80 m |
| Coherence / Coherencia | γ ≥ 0.3 | γ ≥ 0,3 |
| Time / Hora | UTC (local = UTC − 4 h) | UTC (local = UTC − 4 h) |
| Look side / Lado de mirada | NISAR looks **left**, Sentinel-1 **right** | NISAR mira a la **izquierda**, Sentinel-1 a la **derecha** |

## 10 · Status / Estado

| | 🇬🇧 | 🇪🇸 |
|---|---|---|
| ✅ | Multi-sensor inventory | Inventario multisensor |
| ✅ | NISAR coseismic GUNW downloaded (061A, 162A, 126D) | GUNW cosísmicos NISAR descargados (061A, 162A, 126D) |
| ✅ | Sentinel-1 coseismic pairs submitted to HyP3 | Pares cosísmicos Sentinel-1 enviados a HyP3 |
| ⏳ | Sentinel-1 40 m with look vectors | Sentinel-1 a 40 m con vectores de mirada |
| ⏳ | ALOS-2 ScanSAR interferometry | Interferometría ALOS-2 ScanSAR |
| ⏳ | East/Up C vs L and GNSS validation | Este/Vertical C vs L y validación GNSS |
| ✅ | Umbra × Planet first figures (Catia La Mar, Playa Grande, La Guaira) | Primeras figuras Umbra × Planet (Catia La Mar, Playa Grande, La Guaira) |
| ⏳ | Umbra × Planet v2 (full coverage, NDLI, zoom) | Umbra × Planet v2 (cobertura completa, NDLI, acercamiento) |
| ⏳ | Manuscript, Zenodo, submission (deadline 21 Dec 2026) | Manuscrito, Zenodo, envío (fecha límite 21 dic 2026) |

## 11 · Attribution / Atribución

- Contains modified Copernicus Sentinel data (2026), processed by ESA and ASF HyP3. / Contiene datos Copernicus Sentinel modificados (2026), procesados por ESA y ASF HyP3.
- NISAR data courtesy of NASA/JPL-Caltech and ISRO, distributed by ASF DAAC. / Datos NISAR cortesía de NASA/JPL-Caltech e ISRO, distribuidos por ASF DAAC.
- ALOS-2 PALSAR-2 data © JAXA. / Datos ALOS-2 PALSAR-2 © JAXA.
- Contains Umbra open data, licensed under CC BY 4.0. / Contiene datos abiertos de Umbra, licencia CC BY 4.0.
- Imagery © Planet Labs PBC, Planet Crisis Response Program, CC BY-NC 4.0. / Imágenes © Planet Labs PBC, programa Crisis Response, CC BY-NC 4.0.

## 12 · Citation and licence / Cita y licencia

| 🇬🇧 | 🇪🇸 |
|---|---|
| Code: MIT ([`LICENSE`](LICENSE)). Cite with [`CITATION.cff`](CITATION.cff); a Zenodo DOI will be added on the first release. Data keep each provider's licence. | Código: MIT ([`LICENSE`](LICENSE)). Citar con [`CITATION.cff`](CITATION.cff); se añadirá un DOI de Zenodo en la primera versión. Los datos conservan la licencia de cada proveedor. |
