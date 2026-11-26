# Correcciones interferométricas: qué traen los datos y qué falta / InSAR corrections: what the data carry and what is missing

> 🇪🇸 Escrito el 26-nov-2026. **Honestidad:** lo marcado «(verificar)» no está comprobado contra los archivos reales; para eso existe `src/auditar_correcciones.py` (paso `auditoria` del maestro), que LEE cada producto y lista qué capas de corrección trae. Ejecutarlo antes de interpretar mapas.
> 🇬🇧 Written 26 Nov 2026. **Honesty:** items marked "(verify)" are not checked against the real files; `src/auditar_correcciones.py` (master step `auditoria`) READS every product and lists which correction layers it carries. Run it before interpreting maps.

## 1. Nivel de procesamiento de cada fuente / Processing level of each source
| Fuente / Source | Nivel / Level | Ya incluye / Already includes | NO incluye (hay que hacerlo) / NOT included |
|---|---|---|---|
| **Sentinel-1 HyP3 INSAR_GAMMA** (INT40/INT80) | Interferograma desenvuelto y geocodificado (≈ L2) | órbitas, corregistro, **fase topográfica removida con DEM GLO-30**, multilook, filtro, desenvolvimiento (SNAPHU), geocodificación, máscara de agua, coherencia, vectores de mirada | **ionosfera** (poco relevante en banda C), **troposfera** (estratificada y turbulenta), mareas terrestres (pequeñas), **referencia** (desfase arbitrario), errores de desenvolvimiento |
| **NISAR GUNW (L2)** | Interferograma desenvuelto y geocodificado | órbitas, topografía, filtro, desenvolvimiento, coherencia, componentes conexas, **capa de pantalla ionosférica (frecuencias A y B)** como capa SEPARADA; capas de troposfera y mareas como metadatos (verificar) | **la ionosfera NO viene restada** de `unwrappedPhase` (se resta aparte), **referencia** arbitraria, troposfera/mareas no aplicadas (verificar) |
| **UCSD/Scripps LOS «500 m»** (ALOS-2 y NISAR) | Desplazamiento LOS ya en mm (≈ L3), malla ~30 m, enmascarado | GMTSAR; filtro 400 m (ALOS-2) / 160 m (NISAR) / 200 m (S-1); NISAR con ionosfera corregida | **ALOS-2 SIN corrección ionosférica** (lo dicen los autores); signo, referencia, troposfera y licencia: **no declarados** |
| **ALOS-2 L1.1 SLC (JAXA)** | Complejo single-look: nada hecho | — | **todo**: coregistro ScanSAR, topografía, filtro, desenvolvimiento, ionosfera, troposfera, referencia (GMTSAR/ISCE2) |

## 2. Qué se corrige y cómo (receta) / What to correct and how
1. **Referencia (OBLIGATORIA).** La fase desenvuelta tiene un desfase constante arbitrario. Se resta la mediana de un campo lejano (>20–25 km de las fallas) o se ancla a GNSS (CCS1). *Implementado:* `REFERENCIAR=True` en `descomposicion_C_L.py` e `insar_metricas.py`; la tabla guarda `offset_referencia_cm` (con UCSD NISAR T162A aparece un desfase de ≈ −16 cm en datos reales de prueba: sin esto los mapas no son comparables).
2. **Ionosfera (banda L, OBLIGATORIA).** Restar la pantalla ionosférica de división espectral (`ionospherePhaseScreen` del GUNW). *Implementado* en `nisar_gunw_a_geotiff.py` (`*_los_iono_m.tif`, también si viene en otra malla) y usado por defecto (`USAR_IONO=True`). *Mejora pendiente:* suavizar la pantalla (p. ej. Gauss ~10–20 km) antes de restarla. **ALOS-2 (UCSD): no corregido →** usar solo cualitativo o con la advertencia «sin corr. iono.».
3. **Troposfera.** (a) Estratificada: regresión fase–elevación en campo lejano con el DEM (R² = 0,25 en S-1) y restar; (b) ERA5/GACOS (PyAPS/MintPy) — *no implementado*; (c) la turbulenta no se corrige con un par: declarar como incertidumbre (semivariograma en campo lejano).
4. **Rampas orbitales.** Ajuste de plano en campo lejano y restar (ojo: la deformación cosísmica ocupa decenas de km; usar máscara).
5. **Errores de desenvolvimiento.** Revisar componentes conexas, comparar con fase envuelta; enmascarar saltos de 2π (en NISAR 126D hay ±20 rad → sospechoso).
6. **Mareas terrestres/carga oceánica:** ≲ 1 cm en 100 km; si el GUNW trae la capa, aplicarla (verificar).
7. **Validación:** GNSS CCS1 (dE ≈ −0,464 m, dN ≈ −0,011 m, dU ≈ +0,021 m; Arenas & Suárez 2026) y convención de signo (+ = hacia el satélite).

Pendiente de implementar (por prioridad): troposfera estratificada · suavizado de ionosfera · rampa · incertidumbre por semivariograma · ERA5/GACOS.

---
# 🇬🇧 English version

## 1. Processing level of each source
**Sentinel-1 HyP3** = unwrapped geocoded interferogram (orbits, DEM topographic phase removed, multilook, filter, SNAPHU, water mask, coherence, look vectors); **not** corrected: ionosphere (minor in C-band), troposphere, solid-earth tides, reference (arbitrary offset), unwrapping errors. **NISAR GUNW** = unwrapped geocoded interferogram + a SEPARATE ionosphere phase screen (split spectrum, freq. A/B); the ionosphere is **not subtracted** from `unwrappedPhase`; reference arbitrary; troposphere/tide layers as metadata (verify). **UCSD LOS files** = displacement in mm (≈ L3), ~30 m grid, masked, GMTSAR; NISAR ionosphere-corrected; **ALOS-2 NOT ionosphere-corrected** (authors say so); sign, reference, troposphere and licence not stated. **ALOS-2 L1.1 SLC (JAXA)** = nothing done: everything must be processed (GMTSAR/ISCE2).

## 2. What to correct and how
1. **Reference (MANDATORY):** subtract the far-field median (>20–25 km from faults) or anchor to GNSS. *Implemented* (`REFERENCIAR=True`; the table stores `offset_referencia_cm`; real UCSD NISAR T162A shows ≈ −16 cm offset). 2. **Ionosphere (L-band, MANDATORY):** subtract the split-spectrum screen; *implemented* (`USAR_IONO=True`); pending: smooth the screen first. UCSD ALOS-2 is uncorrected: qualitative use only, flagged "NO iono. corr.". 3. **Troposphere:** stratified phase–elevation regression (S-1 R² = 0.25), ERA5/GACOS (not implemented); turbulent part → report as uncertainty. 4. **Orbital ramps:** masked plane fit in the far field. 5. **Unwrapping errors:** check connected components (NISAR 126D shows ±20 rad: suspicious). 6. **Tides/ocean loading:** ≲ 1 cm over 100 km; apply if the GUNW carries the layer (verify). 7. **Validation:** GNSS CCS1 and sign convention (+ = toward satellite).
