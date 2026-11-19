# Bitácora de procesamiento (processing log)

Registrar aquí cada decisión que afecte a los resultados, con fecha. Esto alimenta la sección *Methods* y *Data and Resources* del artículo.

| Fecha | Decisión | Valor | Justificación |
|---|---|---|---|
| 2026-11-19 | Convención de signo LOS | + = acercamiento al satélite | Común a C, L y X; validar con GNSS CCS1 |
| 2026-11-19 | Umbral de coherencia | 0.30 | Enmascara mar, bosque denso y decorrelación cerca de la ruptura |
| 2026-11-19 | Grilla común | UTM 19N (EPSG:32619), 80 m | Resolución nativa de GUNW NISAR; S1 HyP3 a 40 m se remuestrea |
| 2026-11-19 | Descomposición | Este + Vertical, N ≈ 0 | GNSS CCS1: dN ≈ −1 cm (Arenas & Suárez, 2026) |
| 2026-11-19 | Sentinel-1 HyP3 | looks 10x2 (~40 m), look vectors | Necesario para E/U y para escala urbana |
| 2026-11-19 | NISAR GUNW cosísmicos | 061A, 162A, 126D (+054D) | Filtro: fecha_ref < sismo < fecha_sec y cobertura de La Guaira |

## Pendientes
- [ ] Coordenadas exactas de CCS1 (ficha NGL / IGVSB)
- [ ] ALOS-2 ScanSAR L1.1: descargar (ASF/JAXA) y procesar con GMTSAR o ISCE2
- [ ] Planet: confirmar con la revista la compatibilidad CC BY-NC vs. acceso abierto CC-BY
