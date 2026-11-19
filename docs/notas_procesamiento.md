# Bitácora de procesamiento / Processing log

🇪🇸 Registrar aquí cada decisión que afecte a los resultados, con fecha. Alimenta las secciones *Methods* y *Data and Resources* del artículo.  
🇬🇧 Record here, with date, every decision that affects the results. Feeds the *Methods* and *Data and Resources* sections of the manuscript.

| Fecha / Date | Decisión / Decision | Valor / Value | Justificación / Rationale |
|---|---|---|---|
| 2026-11-19 | Convención de signo LOS | + = acercamiento al satélite | Común a C, L y X; validar con GNSS CCS1 |
| 2026-11-19 | Umbral de coherencia | 0.30 | Enmascara mar, bosque denso y decorrelación cerca de la ruptura |
| 2026-11-19 | Grilla común | UTM 19N (EPSG:32619), 80 m | Resolución nativa de GUNW NISAR; S1 HyP3 a 40 m se remuestrea |
| 2026-11-19 | Descomposición | Este + Vertical, N ≈ 0 | GNSS CCS1: dN ≈ −1 cm (Arenas & Suárez, 2026) |
| 2026-11-19 | Sentinel-1 HyP3 | looks 10x2 (~40 m), look vectors | Necesario para E/U y para escala urbana |
| 2026-11-19 | NISAR GUNW cosísmicos | 061A, 162A, 126D (+054D) | Filtro: fecha_ref < sismo < fecha_sec y cobertura de La Guaira |
| 2026-11-19 | Umbra × Planet por sitios de daño / per damage site | 6 sitios, recorte 1 km, 0,5 m | Evita el colapso de memoria de Colab; centra el análisis donde hubo colapsos (Catia La Mar, Playa Grande, La Guaira, Caraballeda, Tanaguarena, Naiguatá) |
| 2026-11-19 | Índices Umbra / Umbra indices | Lee 5×5, CV local 9×9, multi-aspecto | Imagen única post-evento: textura y dependencia de la dirección de mirada distinguen edificios en pie de escombros |
| 2026-11-19 | Salidas bilingües / bilingual outputs | `_es` / `_en` | Figuras y tablas en español e inglés desde el origen / Figures and tables in Spanish and English from the source |
| 2026-11-19 | Registros / logs | `05_documentacion/logs` | Trazabilidad de cada ejecución y su versión de código / Traceability of each run and its code version |

## Pendientes / To do
- [ ] Coordenadas exactas de CCS1 (ficha NGL / IGVSB)
- [ ] ALOS-2 ScanSAR L1.1: descargar (ASF/JAXA) y procesar con GMTSAR o ISCE2
- [ ] Planet: confirmar con la revista la compatibilidad CC BY-NC vs. acceso abierto CC-BY
