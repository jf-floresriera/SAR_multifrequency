# Plan de figuras, tablas y estadísticas: qué estaba propuesto y en qué estado está / Planned figures, tables and statistics: status

> 🇪🇸 Reconstruido el 26-nov-2026 desde `PROYECTO.md` (§ figuras) y `ESTILO_FIGURAS.md` §5 (estadísticas) para que nada propuesto al inicio se pierda. ✅ hecho y probado · 🟡 parcial / por rehacer · ⬜ pendiente. «Probado» = con datos sintéticos o descargados aquí; ninguna salida real de Colab revisada salvo `descomp`.
> 🇬🇧 Rebuilt on 26 Nov 2026 from `PROYECTO.md` (figures) and `ESTILO_FIGURAS.md` §5 (statistics) so nothing proposed at the start is lost.

## 1. Figuras del artículo (≤ 10) / Main-text figures
| Fig. | Contenido / Content | Script | Estado |
|---|---|---|---|
| 1 | Mapa de ubicación: contexto Sudamérica, regional, costa; fallas, epicentros, sitios, referencias | `mapa_ubicacion.py` | ✅ (3 paneles ES/EN) — falta mostrar cobertura de sensores |
| 3 | LOS Sentinel-1 asc/desc | `insar_metricas.py` | 🟡 mapas comparables listos (mm, misma escala); falta versión final con paneles elegidos |
| 4 | LOS NISAR asc/desc (+ ALOS-2 de UCSD) | `insar_metricas.py`, `ucsd_los_a_geotiff.py` | 🟡 igual; ALOS-2 sin corrección ionosférica |
| 5 | Este/Vertical C vs L y L − C | `descomposicion_C_L.py` | 🟡 rehecha en mm, con contexto; **resultado real dudoso (17 %/0 %/18 % de píxeles; E ±1 m)**: repetir tras referencia + ionosfera |
| 6 | Coherencia por cobertura del suelo (WorldCover) | — | ⬜ |
| 7 | Ventana postsísmica 126D − S1 | — | ⬜ |
| 8 | Daño Umbra × Planet/Vantor por sitio | `umbra_planet_sitios.py`, `vantor_buscar.py` | 🟡 rehacer con `estilo_figuras.py` y «antes» de Vantor (~0,4 m) |
| 9 | Daño vs gradiente y distancia a la falla | — | ⬜ |
| 10 | Infraestructura: aeropuerto, puerto, viaducto | — | ⬜ |

## 2. Suplemento (sin límite; muchos paneles) / Supplement
S1 línea de tiempo de adquisiciones · S2 huellas por sensor · S3 los 6 sitios de daño · S4 paletas y prueba de gris · **S5 QC de cada interferograma** (`qc_interferogramas.py`: LOS mm, fase en rad, franjas, coherencia, histogramas) · S6 comparación nuestro NISAR vs UCSD. Estado: S5 y S6 ✅ (probados), S1–S4 🟡/⬜.

## 3. Tablas / Tables
| Tabla | Contenido | Estado |
|---|---|---|
| 1 | Inventario de datos | 🟡 CSV existe (`inventario_multisensor.py`); darle formato bilingüe de revista |
| 2 | Parámetros de procesamiento | 🟡 `notas_procesamiento.md`; convertir en tabla (λ, looks, DEM, filtro, referencia, ionosfera, troposfera) por producto: se genera parte con `metricas_insar_{es,en}.csv` |
| 3 | Detección de daño por sensor (P/R/F1/MCC) | ⬜ |
| S-Tabla | Métricas por interferograma (`insar_metricas`), diagnóstico QC (`qc`), auditoría de correcciones (`auditoria`) | ✅ |

## 4. Estadísticas propuestas (ESTILO_FIGURAS §5) / Proposed statistics
| Estadística | Estado |
|---|---|
| Referenciar a campo lejano / GNSS | ✅ campo lejano (`REFERENCIAR`); ⬜ GNSS (faltan coordenadas de CCS1) |
| Quitar rampa (plano enmascarado) | ⬜ |
| Corrección atmosférica (fase–elevación, ERA5/GACOS) | ⬜ (R² = 0,25 en S-1) |
| Ionosfera en L (división espectral) | ✅ NISAR (si el GUNW trae la capa); ALOS-2/UCSD ⬜ no corregido |
| Incertidumbre por semivariograma, propagación a E/U | ⬜ (hoy: σ en campo lejano por MAD) |
| Sensibilidad a N ≈ 0 (±10 cm) | ⬜ |
| Sesgo, RMSE, regresión frente a otro producto | ✅ nuestro NISAR vs UCSD; ⬜ vs GNSS |
| Bland–Altman, KS de L − C, coherencia por cobertura | ⬜ |
| Perfiles apilados (mediana ± MAD) | 🟡 perfil común (`insar_metricas`); falta ± MAD |
| Gradiente de deformación (1/m) | ⬜ (había uno en `VargaS_Earthquake`) |
| Regresión logística daño ~ distancia + gradiente, ROC/AUC con CV espacial, Moran, Kruskal–Wallis/Cliff, P/R/F1/MCC | ⬜ |

## 5. Estilo (decisiones de hoy) / Style decisions
- **LOS a nivel de milímetro** (como UCSD), mapas y tablas en mm; fase también en radianes.
- **Paleta propia:** UCSD usa marrón–blanco–azul (≈ vik) para LOS y arcoíris para fase; nosotros usamos Crameri **bam** (10–90 %) y **bamO** (cíclica). Se cambia con `PALETA_DIV` / `PALETA_CICLICA`.
- Misma ventana y misma escala de color para comparar productos; «SIN corr. iono.» visible en el título si falta la corrección.
