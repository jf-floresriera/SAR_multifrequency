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
| LOS, E/U, L − C | divergente `vik` (alternativas `roma`, `berlin`, `managua`, `vanimo`, `broc`) | centro en 0 |
| Coherencia, retrodispersión, elevación | secuencial `batlow` (`lajolla`, `oslo`, `turku`) | monótona en gris |
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
