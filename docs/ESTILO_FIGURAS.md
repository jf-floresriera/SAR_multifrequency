# Estilo de figuras y estadísticas / Figure style and statistics

> 🇪🇸 Implementado en `src/estilo_figuras.py`. Muestras: `docs/img/demo_estilo_{es,en}.png` (**datos sintéticos**) y `docs/img/paletas_comparacion.png`.
> 🇬🇧 Implemented in `src/estilo_figuras.py`. Samples are synthetic.

## 1. Reglas (SRL manda sobre las guías genéricas de revistas Q1)
- Sin título interno; rótulos **(a)(b)** en negrita, **fuera y arriba-izquierda**; sin cursivas; pie y *alt-text* aparte.
- Ancho final real (sin reducir después): 1 columna 88 mm, 2 columnas 180 mm. **Verificar con las guías vigentes de SRL.**
- Arial (sustituye a Helvetica), 7 pt a tamaño final (SRL: ≥ 6 pt tras reducción; las guías dicen 10–12 pt al 100 %: confirmar).
- Fondo blanco, mapa base gris tenue (relieve) — **nada de Esri**; ticks externos con EPSG en el pie; barra de escala métrica y norte discreto con halo blanco si el fondo es oscuro.
- Estiramiento 2–98 % declarado en el pie. Divergentes centradas en 0 (`limites_simetricos`).
- Exportación: `exportar()` → PDF, EPS, TIFF (LZW, 600 dpi), PNG. **Enviar el PDF** (SRL: TIFF/JPEG/PDF ≤ 10 MB); el EPS pesa ~17 MB y no admite transparencia.

## 2. Paletas (Crameri; nunca jet/rainbow)
| Variable | Paleta | Nota |
|---|---|---|
| LOS, E/U, L − C | divergente **`vik` recortada 15–85 %** (más clara; declararlo en el pie). Alternativas: `roma_r` 15–85 %, `bam`, `RdBu_r`, `BrBG`, `PuOr` | centro en 0 |
| Coherencia, retrodispersión, elevación | secuencial `batlow` (`lajolla`, `bamako`, `davos`, `cividis`) | monótona en gris |
| Fase envuelta | cíclica `romaO` | |
| Clases de daño | Okabe-Ito (`CLASES_DANIO`) | ≤ 7–9 clases |

⚠️ **Hallazgo:** *ninguna* paleta divergente conserva el signo en escala de grises (ambos signos quedan igual de oscuros o claros; ver `paletas_comparacion.png`). SRL imprime en gris con la opción de color 2 → en mapas divergentes **añadir contornos con signo** (`contornos_signo`: continuo +, discontinuo −, cero grueso) o usar una secuencial. `prueba_gris()` ahora evalúa el rango completo: secuenciales ✅, divergentes y cíclicas ❌.

## 3. Mapa de localización (Fig. 1)
Recuadro macro (norte de Sudamérica/Caribe) + zona de estudio; fallas (GEM), epicentros (USGS), sitios de daño, huellas de sensores en líneas finas. Límites: geoBoundaries (CC BY 4.0) con nota sobre límites; verificar la política de SRL sobre fronteras. Puntos de referencia: ver `REFERENCIAS_MAPA.md`.

## 4. Figuras híbridas
Cada mapa va acoplado a un perfil, histograma o dispersión con R², RMSE, n (ver `demo_estilo.py`). Small multiples: misma extensión y **una barra de color compartida**.

## 5. Estadísticas propuestas
**Calidad:** referenciar a zona estable/GNSS · quitar rampa (ajuste plano enmascarado) · corrección atmosférica (regresión fase–elevación o ERA5/GACOS) · ionosfera en L (división espectral NISAR) · incertidumbre por píxel (semivariograma en campo lejano, propagación a Este/Vertical) · sensibilidad a N ≈ 0 (±10 cm).
**Validación y C vs L:** sesgo, RMSE, regresión y Bland-Altman frente a GNSS · L − C con histogramas y Kolmogorov-Smirnov · coherencia por cobertura (WorldCover).
**Falla y daño:** perfiles apilados (mediana ± MAD) · gradiente de deformación (1/m) · regresión logística daño ~ distancia a la falla + gradiente · ROC/AUC con **validación cruzada por bloques espaciales** · Moran de residuos · métricas Umbra por clase (Kruskal-Wallis, delta de Cliff, bootstrap) · precisión/recall/F1/MCC (clases desbalanceadas) · reconocer el ruido de etiquetas del daño automático.


---

# 🇬🇧 English version / Versión en inglés

Implemented in `src/estilo_figuras.py`. Samples (synthetic data): `docs/img/demo_estilo_{es,en}.png`, `paletas_comparacion.png`, `paletas_claras.png`.

## 1. Rules (SRL overrides generic Q1 guidance)
No internal title; bold **(a)(b)** labels **outside, top-left**; no italics; caption and alt-text separate. Final true width (never rescaled): 1 column 88 mm, 2 columns 180 mm — **verify with current SRL guidelines**. Arial (Helvetica substitute), 7 pt at final size (SRL: ≥ 6 pt after reduction; the generic guide says 10–12 pt at 100 %: confirm). White background, light grey relief basemap — **no Esri**; external ticks with EPSG in the caption; metric scale bar and discreet north arrow with a white halo over dark backgrounds. 2–98 % stretch stated in the caption; diverging maps centred on 0 (`limites_simetricos`). Export with `exportar()`: PDF, EPS, TIFF (LZW, 600 dpi), PNG. **Submit the PDF** (SRL: TIFF/JPEG/PDF ≤ 10 MB); EPS is ~17 MB and has no transparency.

## 2. Palettes (Crameri; never jet/rainbow)
Diverging (LOS, E/U, L − C): **`vik` truncated 15–85 %** (lighter; state "colour map truncated 15–85 %" in the caption); alternatives `roma_r` 15–85 %, `bam`, ColorBrewer `RdBu_r` / `BrBG` / `PuOr`. Sequential (coherence, backscatter, elevation): `batlow`, `lajolla`, `bamako`, `davos`, `cividis`. Cyclic (wrapped phase): `romaO`. Damage classes: Okabe-Ito.

⚠️ **Finding:** *no* diverging palette keeps the sign in greyscale; SRL prints in grey (colour option 2) → add **signed contours** (`contornos_signo`: solid +, dashed −, thick zero) or use a sequential map. `prueba_gris()` evaluates the full range: sequential ✅, diverging and cyclic ❌.

**Evidence limits:** the cited basis is Crameri, Shephard & Heron (2020), *Nature Communications* 11, 5444, doi:10.1038/s41467-020-19160-7 (perceptual uniformity, colour-vision deficiency; ~8 % of men and ~0.5 % of women are affected). Our web search did **not** retrieve evidence ranking palettes by "colour psychology" or specifically for InSAR; the lighter-palette choice is a design decision, not a literature result.

## 3. Location map (Fig. 1)
Macro inset (northern South America/Caribbean) + study area; faults (GEM), epicentres (USGS), damage sites, thin sensor footprints. Boundaries: geoBoundaries (CC BY 4.0); check SRL's policy on borders. Reference points: `REFERENCIAS_MAPA.md`.

## 4. Hybrid figures
Every map is paired with a profile, histogram or scatter with R², RMSE, n (see `demo_estilo.py`). Small multiples: same extent and **one shared colour bar**.

## 5. Proposed statistics
**Quality:** reference to stable area/GNSS · remove ramp (masked plane fit) · atmospheric correction (phase–elevation regression or ERA5/GACOS) · L-band ionosphere (NISAR split spectrum) · per-pixel uncertainty (far-field semivariogram, propagated to East/Up) · sensitivity to N ≈ 0 (±10 cm).
**Validation and C vs L:** bias, RMSE, regression and Bland-Altman against GNSS · L − C with histograms and Kolmogorov-Smirnov · coherence by land cover (WorldCover).
**Fault and damage:** stacked profiles (median ± MAD) · deformation gradient (1/m) · logistic regression damage ~ fault distance + gradient · ROC/AUC with **spatial block cross-validation** · Moran's I of residuals · Umbra metrics per damage class (Kruskal-Wallis, Cliff's delta, bootstrap) · precision/recall/F1/MCC (imbalanced classes) · acknowledge label noise of automatic damage.

## 6. Supplement plan / Plan del suplemento
🇪🇸 Las figuras de inventario van al suplemento (no cuentan en el límite de 10): S1 línea de tiempo de adquisiciones; S2 huellas por sensor (Sentinel-1, NISAR, ALOS-2, Umbra, Planet); Tabla S1 inventario completo; S3 los 6 sitios de daño; S4 paletas y prueba de gris.
🇬🇧 Inventory figures go to the supplement (not counted in the 10-figure limit): S1 acquisition timeline; S2 footprints per sensor; Table S1 full inventory; S3 all 6 damage sites; S4 palettes and grey test.
Nota / Note: los GeoTIFF "visual" de Planet son RGB; **el análisis multiespectral requeriría los productos analíticos (4/8 bandas), aún no inventariados** / Planet "visual" GeoTIFFs are RGB; **multispectral analysis would need the analytic (4/8-band) products, not yet inventoried**.


> 🇪🇸 **Suplemento = muchos paneles.** El material suplementario no tiene límite de figuras: usar figuras de **varios paneles** (cuadrículas a–z) para inventario, los 6 sitios de daño, cada geometría LOS (Sentinel-1, NISAR, ALOS-2) y pruebas de sensibilidad; el texto principal queda para los resultados clave (≤ 10 figuras).
> 🇬🇧 **Supplement = many panels.** The electronic supplement has no figure limit: use **multi-panel** figures (grids a–z) for the inventory, all 6 damage sites, every LOS geometry (Sentinel-1, NISAR, ALOS-2) and sensitivity tests; keep the main text for the key results (≤ 10 figures).


> 🇪🇸 **Actualización 26-nov-2026:** paleta divergente por defecto = Crameri **bam** (10–90 %) y cíclica **bamO**, para NO parecerse a UCSD/Scripps (marrón–azul y arcoíris). LOS en **mm**. Ver `FIGURAS_TABLAS_ESTADO.md`.
> 🇬🇧 **Update 26 Nov 2026:** default diverging palette = Crameri **bam** (10–90 %), cyclic **bamO**, deliberately different from UCSD/Scripps (brown–blue and rainbow). LOS in **mm**. See `FIGURAS_TABLAS_ESTADO.md`.
