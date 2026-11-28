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
| 2026-11-19 | Figuras formato SRL / SRL-style figures | sin título, (a)(b) fuera, 7.2 in, ≥ 6 pt, pies bilingües aparte | Guía de envío SRL / SRL submission guidelines |
| 2026-11-19 | Acercamiento automático / automatic zoom | máximo aclaramiento post-sismo (polvo/escombros), excluye mar | Zoom informativo en vez del centro / informative zoom instead of centre |
| 2026-11-19 | HyP3 duplicados / duplicates | 025D enviado 4 veces; se usa uno, resto a `_duplicados` | Evitar productos repetidos / avoid duplicate products |
| 2026-11-19 | Zonas de contraste / contrast zones | dañada = máx. edificios destruidos/dañados en 100 m; sana = 200–900 m, sin dañados a < 150 m | Comparar respuesta radar/óptica dañado vs sano / compare radar-optical response |
| 2026-11-19 | Acercamiento / zoom | 400 m (antes 300 m), escala 100 m | Mejor legibilidad / better legibility |
| 2026-11-19 | Daño HOTOSM: archivos usados / files used | `<zona>_damage_polygons.geojson` (fusión fAIr/Microsoft) + `venezuela_validated_damage.geojson`; zonas Catia La Mar, La Guaira, Caraballeda, Naiguatá, Carayaca; recorte a la costa de La Guaira | Evita duplicados y colapso de memoria; etiquetas xView2 (no-/minor-/major-damage, destroyed) / avoids duplicates and memory crash |
| 2026-11-26 | Anti-duplicados HyP3 / HyP3 anti-duplicates | clave = par de escenas + tipo (`src/registro_datos.py`) | Antes se comparaba el nombre; 033A (`Sismo_LaGuaira_S1_Path33`, 5-nov, INT80) habría sido reenviado y 025D se envió 4 veces. Ahora: 1º ZIP en Drive, 2º trabajo vigente con el mismo par, 3º recién enviar. `FORZAR_ENVIO=True` para repetir a propósito |
| 2026-11-26 | 033A a 80 m / 033A at 80 m | se usa INT80 ya descargado (no reenviar a 40 m) | La grilla común es 80 m; 40 m solo aporta si se analiza escala urbana con C |

| 2026-11-27 | Composición óptica / optical composition | antes Vantor 21-mar · después Vantor 29-jun · Umbra 48° izq. + 27° der. | Elegida por el autor; sitios S1–S4 (costa de Catia La Mar–Playa Grande) |
| 2026-11-27 | Desfase Umbra GEC ↔ óptico | 120–220 m, distinto por escena; la de 48° (squint 29°) además está deformada | Un desfase por ventana de ≤ 500–700 m; manual en S1: U1 +125/−80 m, U2 −60/+100 m |
| 2026-11-27 | Par pre-sísmico S-1 033A | FAILED en HyP3 | Probable poco solape entre los cortes S1D 13-jun y S1A 18-jun; diagnosticar antes de reenviar |
| 2026-11-28 | Alineación automática | busca ±60 m alrededor de un desfase de partida (manual o heredado del sitio más cercano con la misma escena), no alrededor de 0 | Con partida 0 nunca podía hallar 120–220 m; S2–S4 se habían dibujado sin desfase |
| 2026-11-28 | Óptico completo en Drive | `descargar_opticos.py`: todos los activos GeoTIFF de Vantor y Planet en la zona | Antes solo se leían ventanas por internet; CC BY-NC → solo Drive |

## Pendientes / To do
- [ ] Coordenadas exactas de CCS1 (ficha NGL / IGVSB)
- [ ] ALOS-2 ScanSAR L1.1: descargar (ASF/JAXA) y procesar con GMTSAR o ISCE2
- [ ] Planet: confirmar con la revista la compatibilidad CC BY-NC vs. acceso abierto CC-BY


| 2026-11-26 | **Ionosfera (banda L)** | `nisar_gunw_a_geotiff.py` resta la `ionospherePhaseScreen` del GUNW (división espectral, frecuencias A y B) y guarda `*_los_iono_m.tif`; `descomposicion_C_L.py` e `insar_metricas.py` la usan por defecto (`USAR_IONO=True`). Si falta, el título del mapa y la tabla dicen «SIN corr. iono.». ALOS-2 de UCSD NO está corregido (lo declaran los autores). Banda C: ionosfera despreciable, troposfera sin corregir (R² fase–elevación ≈ 0,25). | **Ionosphere (L-band):** NISAR GUNW ionosphere screen is subtracted and `*_los_iono_m.tif` saved; downstream scripts use it by default. If missing, the map title and table state "NO iono. corr.". UCSD ALOS-2 is NOT corrected (authors say so). C-band: ionosphere negligible, troposphere uncorrected. |

| 2026-11-28 | Redescarga del 025D | `hyp3_estado` y `descargas` comparan por par de escenas + resolución y miran también `_duplicados` | El duplicado movido se volvía a bajar (1 GB) en cada corrida |
