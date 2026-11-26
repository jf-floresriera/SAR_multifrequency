# Resumen del proceso y pendientes / Process summary and to-do · 2026-11-26

> 🇪🇸 Documento de traspaso corto para retomar mañana (Google Colab + Drive + GitHub). Detalle técnico: `HANDOFF.md`, `CORRECCIONES_INSAR.md`, `FIGURAS_TABLAS_ESTADO.md`.
> 🇬🇧 Short handoff to resume tomorrow (Google Colab + Drive + GitHub). Technical detail: `HANDOFF.md`, `CORRECCIONES_INSAR.md`, `FIGURAS_TABLAS_ESTADO.md`.

## 1. Cómo se trabaja / How to work
- **Abrir el cuaderno / open the notebook:** <https://colab.research.google.com/github/jf-floresriera/SAR_multifrequency/blob/main/notebooks/00_Maestro.ipynb> (carga siempre la última versión / always the latest version). Activar en 🔑 Secretos «Acceso desde el cuaderno» para `EARTHDATA_USER` y `EARTHDATA_PASS`.
- **Siempre primero la celda #1** (git pull + monta Drive + muestra los cambios nuevos de GitHub). Si la copia del cuaderno está vieja, avisa. 🇬🇧 Always run cell #1 first (git pull + mount Drive + lists new GitHub changes; warns if the notebook copy is stale).
- **Código en GitHub (`src/`), datos y resultados en Drive** (`My Drive/InSAR_LaGuaira_Resultados/GUAIRA-SAR/`). Los pasos ya hechos se saltan; un paso cuyo código cambió se repite solo. 🇬🇧 Code on GitHub, data/results on Drive; done steps are skipped, a step whose code changed re-runs by itself.
- Un cambio de **forma** (colores, textos) → solo el paso de la figura. Un cambio de **cálculo** → ese paso y los siguientes. 🇬🇧 Style change → only the figure step; computation change → that step and downstream ones.

## 2. Carpetas de Drive / Drive folders
| Carpeta / Folder | Contenido / Content |
|---|---|
| `01_datos_crudos/` | `nisar_gunw` (GUNW), `sentinel1_hyp3` (ZIP HyP3), `mapas_base` (capas GEM/OSM/USGS/límites), `ucsd_los` (7 × ~445 MB de UCSD; **no redistribuir / do not redistribute**) |
| `02_procesados/` | `nisar`, `sentinel1` (GeoTIFF: `_los_m`, `_los_iono_m`, `_coh`, `_concomp`, `_losE/N/U`), `ucsd`, `mosaicos`, `descomposicion`, `metricas_insar` (CSV ES/EN) |
| `04_figuras/borradores/` | figuras PDF/TIFF/PNG (ES y EN); `qc/` = una figura por interferograma |
| `05_documentacion/` | `pasos_ejecutados.csv` (registro), `logs/`, `auditoria_correcciones.csv`, `versiones_codigo.csv` |

## 3. Pasos del cuaderno y qué producen / Notebook steps
`mapas_base` (Fig. 1) · `nisar_tif`, `s1_tif` (conversión a GeoTIFF; NISAR con ionosfera restada y **un archivo por frame**) · `descomp` (Este/Vertical) · `auditoria` (qué correcciones trae cada archivo) · `qc` (control de calidad por interferograma **y por mosaico**; el mosaico lleva leyenda de colores por producto) · `ucsd_los` (LOS de UCSD) · `mosaico` (une frames/tracks vecinos de la misma familia y dirección) · `comparacion` (figura de todos los modelos) · `insar_metricas` (tablas y mapas/perfil comparables) · `vantor` (óptico ~0,4 m antes/después) · `danio_*`, `exportar`.

## 4. Resultados clave de hoy / Key results
- **Hipótesis del mar confirmada:** 42–53 % de cada huella es mar. Coherencia ≥ 0,3 sobre tierra: NISAR 162A 73 %, 054D 54 %, 061A 47 %, 126D 48 %; Sentinel-1 033A 20 %, 025D 38 %.
- **Señal presente en los datos propios:** NISAR 162A/061A/054D ≈ 4,5 franjas entre p2 y p98, señal/ruido 13–35; LOS p2/p98 de −318/+227 mm (162A), −482/+50 (061A), −86/+462 (054D).
- **Desfases arbitrarios confirmados:** de −516 a +362 mm entre productos → la referencia es obligatoria (hecha en el análisis).
- **Costuras de los mosaicos (RMS / MAD en el solape, mm):** ALOS-2 UCSD DESC 34/30 · NISAR UCSD ASC 43/25, DESC 34/32 · NISAR propio DESC 44/45 y 22/8 · **NISAR propio ASC 147/33 y 171/3** (RMS ≫ MAD → hay valores atípicos, probablemente saltos de 2π entre componentes conexas).
- **Propio vs UCSD (correlación, antes de corregir los frames):** 061A 0,94 · 054D 0,64 · 162A 0,48 · 126D 0,43.
- **GUNW de NISAR trae:** ionosfera (+ incertidumbre), fase de marea terrestre y banderas `…TroposphericCorrectionApplied` (valor por leer con `auditoria`).

## 5. Errores encontrados y corregidos hoy / Bugs found and fixed today
Frames de NISAR que se sobrescribían (solo se analizaba la mitad de cada track) · `mosaico` pisaba la función `P()` · `LIM_MM=None` compartido entre scripts · etiquetas «ALOS-2 (UCSD)» mal puestas a NISAR de UCSD · etiquetas de ejes automáticas de GeoPandas en inglés («Geodetic latitude») · letras de panel repetidas en el mosaico · EPS de mapas ráster de 30–80 MB (ahora PDF + TIFF + PNG; EPS solo para figuras vectoriales como Fig. 1).
🇬🇧 NISAR frames overwritten · `mosaico` clobbered `P()` · shared `LIM_MM=None` · UCSD NISAR mislabelled · English GeoPandas auto axis labels · repeated panel letters · 30–80 MB raster EPS (now PDF+TIFF+PNG; EPS only for vector figures).

## 6. Figuras en Drive y estado / Figures in Drive and status
| Archivo (`04_figuras/borradores/`) | Estado |
|---|---|
| `mapa_ubicacion_{es,en}` | ✅ Fig. 1 |
| `descomposicion_C_vs_L_{es,en}` | ⚠️ **corrida vieja (E ±1–2 m): repetir `descomp` tras `nisar_tif`** |
| `insar_comparable_{propios,ucsd}_{region,costa}_{es,en}`, `insar_perfil_comparable_{es,en}` | 🟡 de antes de unir frames y de corregir etiquetas: repetir `insar_metricas` |
| `mosaico_nisar_{es,en}` | 🟡 repetir (letras y ejes corregidos) |
| `comparacion_modelos_{es,en}` | ⬜ no se generó (error `LIM_MM`, ya corregido): correr `comparacion` |
| `qc/qc_<producto>_{es,en}` | ✅ → suplemento |

## 7. Para mañana, en orden / To do tomorrow, in order
1. Celda #1 (git pull) → `descomp` (con `forzar=True`) → `auditoria` → `ucsd_los` → **`mosaico` → `qc`** (el QC de los mosaicos necesita que el mosaico exista) → `comparacion` → `insar_metricas`. El cuaderno (versión 2026-11-26.7) ya trae ese orden y una celda «Reproducir TODO»: paneles individuales (`qc`, `insar_metricas`) **y** mosaicos (`mosaico`, `comparacion`). Revisar la **sección «BANDERAS»** de `auditoria` (¿el GUNW ya aplicó troposfera/mareas?).
2. **Costuras de NISAR ASC** (RMS 147–171 mm vs MAD 3–33): usar `_concomp.tif` para enmascarar/revisar saltos de 2π. Ver los mapas de `mosaico`.
3. **Coordenadas exactas de CCS1** (NGL/IGVSB) → validar con GNSS (dE ≈ −0,464 m): fija el signo y la referencia.
4. Decidir Sentinel-1 **T106A** (1 trabajo HyP3 nuevo; solo si se quiere comparar toda la ruptura) y ALOS-2 (UCSD citado como externo, sin corrección ionosférica; opcional pedir a JAXA/UCSD).
5. Implementar troposfera estratificada, suavizado de ionosfera y rampa; incertidumbre (semivariograma).
6. Rehacer Fig. 8 con Vantor (antes) y `estilo_figuras`; Figs. 6, 7, 9, 10; Tabla 3; manuscrito; Zenodo; envío ≤ 18-dic.
7. Licencias: Planet/Vantor CC BY-NC y UCSD (no declarada) vs acceso abierto CC BY de SRL; política sobre fronteras en disputa (zona en reclamación). UCSD **no es un artículo revisado por pares**: citarlo como datos web externos.
