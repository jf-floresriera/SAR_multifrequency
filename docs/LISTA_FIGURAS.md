# Lista de figuras y tablas del artículo / List of figures and tables · versión 27-nov-2026

> 🇪🇸 Una sola lista con lo que va en el **texto principal** (SRL: ≤ 10 figuras) y en el **suplemento** (sin límite). Cada entrada dice el paso del cuaderno que la produce, el archivo en Drive (`04_figuras/borradores/`) y el estado. Principio: en el texto principal **una figura por idea**, con paneles comparables (misma ventana, misma escala, solo tierra); los cientos de paneles individuales van al suplemento y se citan desde el texto («Fig. S5a–l»).
> 🇬🇧 One list for the **main text** (≤ 10 figures) and the **supplement** (no limit), with the step, the Drive file and status. One figure per idea in the main text; hundreds of individual panels go to the supplement and are cited from the text.

**Reglas comunes a todos los mapas / common map rules:** solo tierra (se excluyen Mar Caribe, Lago de Valencia y embalses — `src/mascaras.py`); ventana fija de la zona de estudio; LOS en mm, + = hacia el satélite; paleta bam (LOS) y bamO (fase); (a)(b) fuera del panel; ES y EN; PDF + TIFF + PNG (EPS solo en figuras vectoriales).
**Regla de selección de panel (cobertura parcial) / panel rule:** por banda y dirección se usa el **mosaico** si sus costuras son aceptables (MAD ≤ 40 mm, `UMBRAL_COSTURA_MM`); si no, el **producto individual con mayor cobertura sobre tierra**; la decisión queda en `seleccion_paneles_{es,en}.csv` y se declara en el pie. Los demás productos → suplemento.

Estado: ✅ código hecho y probado · 🟡 código hecho, falta corrida real/revisión · ⬜ por hacer.

## A. Texto principal (≤ 10 figuras)
| # | Figura | Paneles | Paso / archivo | Estado |
|---|---|---|---|---|
| **Fig. 1** | Ubicación | (a) contexto Sudamérica; (b) regional con fallas y epicentros; (c) costa de La Guaira con sitios y referencias | `mapas_base` → `mapa_ubicacion_*` | ✅ |
| **Fig. 2** | Inventario de datos por banda | línea de tiempo: Umbra X, Sentinel-1 C, NISAR L, **ALOS-2 L** (ASF + UCSD), óptico (Planet, Vantor); escenas y pares usados, sismo marcado | `inventario` → `fig_inventario_*` | 🟡 nuevo (27-nov) |
| **Fig. 3** | Interferogramas (franjas) por banda — «la historia visual» | filas = Sentinel-1 C · NISAR L · NISAR L (UCSD) · ALOS-2 L (UCSD); columnas = ASC · DESC; fase re-envuelta (1 ciclo = λ/2) | `comparacion` → `comparacion_franjas_*` | 🟡 nuevo (27-nov) |
| **Fig. 4** | Desplazamiento LOS por banda | igual que Fig. 3 pero en mm (misma escala para todas) | `comparacion` → `comparacion_modelos_*` | 🟡 |
| **Fig. 5** | Este y Vertical por banda y L − C | (a) E C, (b) U C, (c) E L, (d) U L, (e) E L−C, (f) U L−C; solo píxeles con ASC + DESC, solo tierra | `descomp` → `descomposicion_C_vs_L_*` | 🟡 (corregido 27-nov: antes ±1–2 m) |
| **Fig. 6** | Perfiles a través de la falla | (a) LOS por banda, mediana ± MAD; (b) Este/Vertical C vs L con GNSS CCS1 | `insar_metricas` → `insar_perfil_comparable_*` | 🟡 falta ± MAD y GNSS |
| **Fig. 7** | Calidad por banda: coherencia | (a) coherencia sobre tierra por banda (histogramas); (b) % de tierra coherente por banda y umbral; (c) coherencia por cobertura del suelo (WorldCover) | `qc` + nuevo | ⬜ (a–b con datos de `qc`; c pendiente) |
| **Fig. 8** | Daño por pérdida de coherencia C vs L | ΔCOH = coh_pre − coh_co en C y en L, con daño de referencia | nuevo `danio_coherencia` | ⬜ **necesita pares pre-sísmicos** |
| **Fig. 9** | Daño a escala de edificio: X y óptico | por sitio: Vantor antes, Planet/Vantor después, Umbra X (amplitud, textura, NDLI), contornos de daño | `vantor` + `danio_sitios` | 🟡 rehacer con estilo |
| **Fig. 10** | Integración | daño vs distancia a la falla y gradiente de deformación (por banda), curva ROC | nuevo | ⬜ |

## B. Tablas del texto principal
| # | Tabla | Paso / archivo | Estado |
|---|---|---|---|
| Tabla 1 | Datos por banda y producto (sensor, banda, λ, dirección, track/frame, fechas, línea base, días tras el sismo, fuente) | `tablas` → `Tabla1_datos_*` | 🟡 |
| Tabla 2 | Procesamiento y correcciones por producto (ionosfera, referencia, troposfera/marea, umbral de coherencia) | `tablas` → `Tabla2_procesamiento_*` | 🟡 |
| Tabla 3 | Comparación C vs L: sesgo, RMSE, MAD, R², pendiente en Este y Vertical (píxeles comunes sobre tierra); y propio vs UCSD | `tablas` → `TablaS3_comparaciones_*` (pasa al texto) | 🟡 |
| Tabla 4 | Detección de daño por banda (precisión, exhaustividad, F1, MCC, AUC) | nuevo | ⬜ |

## C. Suplemento (sin límite de paneles; se cita desde el texto)
| # | Contenido | Paso / archivo | Estado |
|---|---|---|---|
| Fig. S1 | Huellas de todos los productos (S-1, NISAR por frame, ALOS-2, Umbra, Planet, Vantor) sobre la zona de estudio | nuevo (de `inv_*`) | ⬜ |
| Fig. S2 | Auditoría de correcciones (qué capas trae cada GUNW/HyP3) | `auditoria` → CSV | 🟡 tabla |
| Fig. S3a–… | **QC de cada interferograma** (LOS mm, fase rad, franjas, coherencia, histogramas), solo tierra | `qc` → `qc/qc_<producto>_*` | ✅ |
| Fig. S4a–… | **QC de cada mosaico** | `qc` → `qc/qc_*_MOSAICO_*` | ✅ |
| Fig. S5 | Mosaicos con el producto que aporta cada píxel (leyenda con fechas) | `mosaico` → `mosaico_nisar_*` | ✅ |
| Fig. S6a–l | Paneles individuales de todos los productos (región y costa) con la misma escala | `insar_metricas` → `insar_comparable_*` | ✅ |
| Fig. S7 | Productos no elegidos para el texto principal (regla de selección) | `comparacion` + `seleccion_paneles_*` | 🟡 |
| Fig. S8 | Nuestro NISAR vs UCSD (mapas de diferencia y dispersión) | nuevo (de `insar_metricas`) | ⬜ |
| Fig. S9 | Los 6 sitios de daño (todos), Umbra + óptico | `danio_sitios` | 🟡 |
| Fig. S10 | Paletas y prueba en gris | `comparar_paletas` | ✅ |
| Tabla S1 | Calidad por producto, **tierra vs mar**, barrido del umbral de coherencia | `tablas` → `TablaS1_calidad_*` | 🟡 |
| Tabla S2 | Mosaicos: procedencia de cada pieza y costuras | `tablas` → `TablaS2_mosaicos_*` | 🟡 |
| Tabla S3 | Selección de paneles y motivo | `comparacion` → `seleccion_paneles_*` | 🟡 |
| Tabla S4 | Auditoría de correcciones (banderas del GUNW) | `auditoria` | 🟡 |

## D. Qué falta para cerrar la lista (en orden)
1. Correr en Colab la versión nueva del cuaderno y revisar Figs. 2–6 con datos reales.
2. **Pares pre-sísmicos** (Sentinel-1 033A 13→18 jun por HyP3; NISAR 126D 10→22 jun) → Fig. 8 y Tabla 4. *Requiere tu confirmación para el trabajo HyP3.*
3. Coordenadas de CCS1 → GNSS en Fig. 6.
4. Fig. 7 (WorldCover), Fig. 9 (estilo + Vantor), Fig. 10 (integración).
5. Banda X y óptico: métricas por clase de daño (Kruskal–Wallis, delta de Cliff) y detección (Tabla 4).
