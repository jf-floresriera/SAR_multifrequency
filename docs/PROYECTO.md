# GUAIRA-SAR · Documento maestro del proyecto / Project master document

> 🇪🇸 **Léase primero.** Este documento resume TODO el proyecto: objetivo, datos, método, decisiones, estado, reglas de la revista y plan del manuscrito. Está pensado para que cualquier persona (o asistente de IA) que abra el repositorio pueda continuar el trabajo sin el historial de conversaciones.
> 🇬🇧 **Read first.** This document summarises the WHOLE project: goal, data, method, decisions, status, journal rules and manuscript plan, so that anyone (or any AI assistant) opening the repository can continue the work without the conversation history.

Última actualización / Last update: 2026-11-19

---

## 1. Objetivo / Goal

| 🇪🇸 | 🇬🇧 |
|---|---|
| Artículo para la **sección especial de *Seismological Research Letters* (SRL) sobre los sismos de 2026 en Venezuela, Colombia y Panamá**. **Fecha límite de envío: 21 de diciembre de 2026.** Categoría en Editorial Manager: "2026 Venezuela, Colombia and Panama Earthquakes". | Paper for the **SRL Focus Section on the 2026 Venezuela, Colombia and Panama Earthquakes**. **Submission deadline: 21 December 2026.** Editorial Manager category: "2026 Venezuela, Colombia and Panama Earthquakes". |
| **Título de trabajo:** *De la falla a la fachada: observaciones SAR multifrecuencia (bandas C, L y X) y ópticas de alta resolución del doblete sísmico del 24 de junio de 2026 en Venezuela, a lo largo de la costa de La Guaira.* | **Working title:** *From fault to façade: multi-frequency SAR (C-, L- and X-band) and high-resolution optical observations of the 24 June 2026 Venezuela earthquake doublet along the La Guaira coast.* |
| **Pregunta:** ¿cómo cambia lo que observamos de un mismo sismo según la frecuencia y la resolución del sensor? | **Question:** how do sensor frequency and resolution shape what we observe of the same earthquake? |

### Aportes / Contributions
1. 🇪🇸 Deformación cosísmica en **banda C (Sentinel-1) y banda L (NISAR, ALOS-2)**, ambas con órbita ascendente + descendente → **Este/Vertical en cada banda** y mapas de diferencia L − C. 🇬🇧 Coseismic deformation in C- and L-band, both with ascending + descending geometry → East/Up per band and L − C difference maps.
2. 🇪🇸 Ventana **postsísmica temprana**: Sentinel-1 (hasta 25 jun) vs NISAR 126D (hasta 4 jul). 🇬🇧 Early **postseismic** window.
3. 🇪🇸 **Daño a escala de edificio**: Umbra banda X submétrica (también de noche) vs Planet SkySat/PlanetScope, en 6 sitios de La Guaira. 🇬🇧 **Building-scale damage**: sub-metre X-band Umbra (also at night) vs Planet.
4. 🇪🇸 Relación daño ↔ gradiente de deformación y distancia a la falla San Sebastián; flujo **abierto y reproducible**. 🇬🇧 Damage vs deformation gradient and distance to the San Sebastián fault; **open, reproducible** workflow.

### Trabajos previos (no duplicar, sí citar) / Prior work (cite, do not duplicate)
- Scripps/UCSD (Garcia-Gonzalez et al.): LOS NISAR + ALOS-2 + Sentinel-1, web report (no revisado por pares / not peer-reviewed), topex.ucsd.edu/VNZ_7.5; póster SCEC 2026 (3D con banda L).
- *The Seismic Record* 6(4) 2026: ruptura multifalla supershear Boconó–San Sebastián (Mw 7.6); intensidad en Caraballeda por video CCTV (Bustos et al., doi 10.1785/0320260045).
- Suárez Acosta & Arenas Bermúdez (LUZ, 2026): GNSS + DInSAR Sentinel-1 preliminar; CCS1 dE = −0.464 m, dN = −0.011 m, dU = +0.021 m.
- USGS: correlación óptica Sentinel-2 / Vantor; ESA, NASA/JPL (NISAR UR), JAXA (ALOS-2), Copernicus EMS EMSR884.
- **Ninguno** integra C + L + X + óptico con cuantificación a escala urbana → ese es nuestro hueco / **None** integrates C + L + X + optical at urban scale → our gap.

---

## 2. Datos / Data

| Banda / Band | Sensor | Productos / Products | Fechas 2026 | Licencia / Licence | Estado / Status |
|---|---|---|---|---|---|
| C (5.55 cm) | Sentinel-1A/1D | HyP3 INSAR_GAMMA 40 m + look vectors: **025D** (18→25 jun), **033A** (18→25 jun) | | Copernicus | 025D ✅ · 033A ⏳ enviado 19-nov |
| L (23.8 cm) | NISAR | GUNW cosísmicos: **061A** (18→30 jun), **162A** (13→25 jun), **126D** (22 jun→4 jul), 054D | | NASA | 3 descargados, faltan 3 |
| L (23.8 cm) | ALOS-2 | ScanSAR L1.1 (JAXA liberó 3-jul-2026; espejo ASF) | desde 30 jun | JAXA | ⏳ buscar |
| X (3.1 cm) | Umbra | 26 spotlight GEC/SICD/SIDD (post-evento, sin geometría repetida → solo amplitud) | 26 jun → 2 jul | CC BY 4.0 | inventariado |
| Óptico | Planet SkySat/PlanetScope | 17 post + mosaico Q1-2026 (pre) | 26–28 jun | **CC BY-NC 4.0** (no redistribuir) | URLs resueltas |
| GNSS | CCS1 y otras | validación | | citado | coordenadas CCS1 pendientes |
| Mapas base | geoBoundaries, GEM GAF-DB, OSM, USGS | estados, municipios, fallas, vías, epicentros | | CC BY 4.0 · CC BY-SA 4.0 · ODbL | `mapas_base.py` |

**Sitios de daño / damage sites** (aprox.): Catia La Mar (10.6055, −67.0324), Playa Grande/Urimare (10.6100, −67.0103), La Guaira (10.6000, −66.9331), Caraballeda (10.6122, −66.8519), Tanaguarena (10.6150, −66.8200), Naiguatá (10.6200, −66.7400). Umbra cubre solo Catia La Mar, Playa Grande y La Guaira.

**Epicentros / epicentres:** USGS us6000t7zc (Mw 7.2) y us6000t7zp (Mw 7.5; ~10.622° N, 67.194° W).

---

## 3. Método / Method (flujo / workflow)

| Paso | 🇪🇸 | 🇬🇧 | Código |
|---|---|---|---|
| 1 | Inventario, filtro cosísmico, huellas, licencias | Inventory, coseismic filter, footprints, licences | `01_Inventario` |
| 2 | HyP3 (40 m, look vectors) y descargas | HyP3 and downloads | `02_Descargas_HyP3` |
| 3 | Fase → LOS (m), **un solo signo** (+ = hacia el satélite); coherencia ≥ 0,3; ionosfera NISAR; grilla común UTM 19N 80 m; **Este/Vertical** asc+desc (N ≈ 0, justificado por GNSS dN ≈ −1 cm); validación GNSS; L − C | Phase → LOS, single sign; coherence; ionosphere; common grid; East/Up; GNSS; L − C | `03_InSAR_C_L` |
| 4 | Daño por sitio: Planet antes/después, Umbra amplitud (Lee 5×5), textura (CV 9×9), **NDLI** = (I_izq − I_der)/(I_izq + I_der) normalizado por mediana, acercamiento 300 m automático (máximo aclaramiento post-sismo) o manual | Damage per site: Planet before/after, Umbra amplitude, texture, NDLI, automatic/manual 300 m zoom | `04_Danio_X_Optico` |
| 5 | Integración: daño vs gradiente y distancia a la falla; perfiles aeropuerto/puerto/viaducto | Integration | *pendiente* |

Convenciones / conventions: metros, UTC (local = UTC − 4 h), EPSG:32619, NISAR mira a la izquierda y Sentinel-1 a la derecha.
Decisiones con fecha y justificación / dated decisions: [`docs/notas_procesamiento.md`](notas_procesamiento.md).

### Arquitectura reproducible / Reproducible architecture
- Toda la lógica en `src/*.py`; los notebooks solo llaman `correr("script.py")`. All logic in `src/`; notebooks call `correr()`.
- La celda 0 hace `git pull`, monta Drive y registra el commit en `05_documentacion/versiones_codigo.csv`.
- Cada ejecución guarda su salida y errores en `05_documentacion/logs/`.
- **Cada figura** en `_es` y `_en` (PNG + PDF); **cada tabla** en `.csv` (ES) y `_en.csv`; **pies de figura** bilingües `_pie_es.txt` / `_pie_en.txt`.
- Datos crudos en Google Drive (`InSAR_LaGuaira_Resultados/GUAIRA-SAR/01_datos_crudos`), nunca en GitHub.

---

## 4. Reglas SRL que afectan al trabajo / SRL rules that affect the work

| Regla / Rule | Implicación / Implication |
|---|---|
| Artículo regular: **≤ 6000 palabras, ≤ 10 figuras, ≤ 3 tablas**; resumen ≤ 300 palabras, un párrafo | Plan de figuras abajo; material extra al suplemento electrónico |
| Word o LaTeX; carta, márgenes 1", doble espacio, 12 pt, **numeración de páginas y de líneas continua**; inglés estadounidense; títulos de sección **sin numerar** | `manuscrito/` |
| **Data and Resources** obligatorio, antes de Acknowledgments; **todas las URL van ahí** con mes y año de último acceso; las bases de datos en línea no van en References | `05_documentacion/registro_descargas*.csv`, `fuentes_mapas_base*.csv` dan URL y fecha |
| Figuras: **sin título dentro**; etiquetas (a)(b)… en minúscula, **fuera y arriba-izquierda**; Helvetica/Times; 10–12 pt a 100 %, nunca < 6 pt tras reducción; evitar texto claro sobre fondo oscuro; unidades consistentes; **alt-text** tras cada pie | Implementado en `umbra_planet_sitios.py` (v3) y a aplicar a todas |
| Figuras finales TIFF/JPEG/PDF, ≤ 10 MB c/u, una por archivo | `04_figuras/` |
| Tablas en Word, título arriba, notas al pie con *, †, ‡, §, ‖, # | `manuscrito/tablas/` |
| Color: opción 2 (solo cargos de publicación) → color en línea, **gris en papel**: las figuras deben entenderse en escala de grises | Elegir mapas de color legibles en gris |
| Acceso abierto = CC-BY; **Planet es CC BY-NC** → posible conflicto en figuras con Planet | Consultar a SRL/Planet o elegir opción con cargos de página |
| Declaración de conflictos de interés; autor de correspondencia con dirección completa; una afiliación principal por autor | Página de título |

Lista oficial / official checklist: [`manuscrito/CHECKLIST_SRL.md`](../manuscrito/CHECKLIST_SRL.md).

---

## 5. Plan de figuras y tablas / Figure and table plan (máx. 10 + 3)

| # | 🇪🇸 | 🇬🇧 | Fuente / source script |
|---|---|---|---|
| Fig. 1 | Mapa de ubicación: fallas, epicentros, sitios, cobertura de sensores | Location map | `mapas_base.py` |
| Fig. 2 | Línea de tiempo de adquisiciones | Acquisition timeline | `inventario_multisensor.py` |
| Fig. 3 | LOS Sentinel-1 asc/desc | Sentinel-1 LOS | `descomposicion_C_L.py` |
| Fig. 4 | LOS NISAR asc/desc (+ ALOS-2) | NISAR LOS | idem |
| Fig. 5 | Este/Vertical C vs L y diferencia | East/Up C vs L | idem |
| Fig. 6 | Coherencia por cobertura del suelo (WorldCover) | Coherence by land cover | *pendiente* |
| Fig. 7 | Ventana postsísmica 126D − S1 | Postseismic window | *pendiente* |
| Fig. 8 | Daño Umbra × Planet (sitios) | Damage per site | `umbra_planet_sitios.py` |
| Fig. 9 | Daño vs gradiente y distancia a la falla | Damage vs gradient | *pendiente* |
| Fig. 10 | Infraestructura: aeropuerto, puerto, viaducto | Infrastructure | *pendiente* |
| Tabla 1 | Inventario de datos | Data inventory | `inventario_multisensor.py` |
| Tabla 2 | Parámetros de procesamiento | Processing parameters | `notas_procesamiento.md` |
| Tabla 3 | Detección de daño por sensor | Damage detection per sensor | *pendiente* |

---

## 6. Estado y siguientes pasos / Status and next steps (2026-11-19)

- [x] Inventario de los 4 sensores · [x] NISAR cosísmicos identificados · [x] 025D 40 m descargado · [x] Umbra × Planet v1–v2 · [x] Repositorio, logs, salidas ES/EN
- [ ] 033A 40 m (enviado a HyP3 el 19-nov) → descargar con `hyp3_estado.py`
- [ ] Descargar NISAR restantes y GEC Umbra (`descargas.py`)
- [ ] `mapas_base.py` → Fig. 1
- [ ] Notebook 03: LOS → Este/Vertical C vs L, validación GNSS (coordenadas CCS1)
- [ ] ALOS-2 ScanSAR
- [ ] Figuras 6, 7, 9, 10 y Tabla 3
- [ ] Manuscrito en inglés (y versión en español), Data and Resources, Zenodo, envío ≤ 18-dic-2026

## 7. Para asistentes de IA / For AI assistants
- Lea este archivo, `README.md`, `docs/notas_procesamiento.md` y `manuscrito/`. Read these first.
- No cambie la convención de signo, la grilla común ni los nombres de archivo sin anotarlo en `notas_procesamiento.md`.
- Todo texto visible al usuario y toda figura/tabla deben salir en **español e inglés** (use `src/comun.py`: `T()`, `csv_bilingue()`, `guardar_bilingue()`).
- Nuevas funciones → nuevo script en `src/` + una celda `correr("...")` en el notebook correspondiente.
- El usuario trabaja en Google Colab; los datos están en Google Drive, no en el repositorio.
