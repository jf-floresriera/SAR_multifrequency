# Guía de escritura y estilo para SRL / Writing and style guide for SRL

> 🇪🇸 Cómo escribir el artículo para que cumpla el estilo de *Seismological Research Letters* (SRL). Basado en las *SRL Submission Guidelines* y la *Submission Checklist* (nov-2026). Úsese junto con [`CHECKLIST_SRL.md`](CHECKLIST_SRL.md) y [`../docs/PROYECTO.md`](../docs/PROYECTO.md).
> 🇬🇧 How to write the paper in *SRL* style. Based on the SRL Submission Guidelines and Checklist (Nov 2026).

---

## 1. Qué tipo de artículo es SRL / What an SRL article is

| 🇪🇸 | 🇬🇧 |
|---|---|
| SRL publica **estudios concisos y enfocados**, a menudo **multidisciplinarios**, de interés para una comunidad geocientífica amplia; pueden centrarse en **un método, un conjunto de datos o un evento**. Nuestro artículo es un **artículo regular** de la sección especial: un evento (doblete de 2026) visto con varios sensores. | SRL publishes **concise, focused**, often **multidisciplinary** studies for a broad geoscience readership, centred on **a method, a dataset or an event**. Ours is a **regular article** in the Focus Section: one event seen through several sensors. |
| **Consecuencia:** cada párrafo debe servir a la pregunta central (¿qué ve cada banda, de la falla al edificio?). Lo que no la sirva va al suplemento electrónico. | **Consequence:** every paragraph must serve the central question; anything else goes to the electronic supplement. |

**Límites / limits:** resumen ≤ 300 palabras (un párrafo) · texto ≤ 6000 palabras · ≤ 10 figuras · ≤ 3 tablas.

---

## 2. Estructura y extensión orientativa / Structure and target length

| Sección (sin numerar) / Section (unnumbered) | Palabras / words | Contenido / content |
|---|---|---|
| Title page | — | Título, autores, una afiliación principal c/u, autor de correspondencia con dirección postal completa, Declaration of Competing Interests |
| Abstract | ≤ 300 | Contexto (1 frase) · vacío (1) · datos y método (2–3) · resultados con **números** (3–4) · implicación (1) |
| Introduction | ~700 | Evento, productos rápidos existentes, vacío, objetivos |
| Data | ~700 | Sensores, fechas, geometrías → Table 1, Figs. 1–2 |
| Methods | ~1200 | Armonización InSAR, Este/Vertical, GNSS, análisis de daño → Table 2 |
| Results | ~1700 | Figs. 3–10, Table 3 |
| Discussion | ~1200 | Qué resuelve cada banda, limitaciones, implicaciones para respuesta y amenaza |
| Conclusions | ~300 | 3–5 hallazgos concretos |
| Data and Resources | — | **Todas las URL** con mes y año de acceso; código; suplemento |
| Acknowledgments | — | Financiamiento, datos, revisores |
| References | — | Solo obras publicadas, orden alfabético |
| Figure captions + alt-text | — | Un pie por figura y alt-text en línea aparte |

---

## 3. Estilo de redacción / Writing style

### Reglas de la revista / Journal rules
- **Inglés estadounidense** (*analyze, color, meter, modeling, center*). American English spelling.
- **Definir toda sigla en su primera mención**, también en el resumen: *interferometric synthetic aperture radar (InSAR)*, *line of sight (LOS)*, *Global Navigation Satellite System (GNSS)*. Define every acronym at first use.
- **No usar comillas ni cursiva para enfatizar.** No quotation marks or italics for emphasis.
- **Unidades SI**; momento sísmico en N·m; esfuerzo en MPa; segundos = **s**. SI units.
- **Ecuaciones editables** (no imágenes), numeradas a la derecha entre paréntesis, puntuadas como oraciones; variables en cursiva, vectores en negrita; usar barra (/) en vez de fracciones apiladas; exponenciales como exp( ).
- **Citas en el texto:** autor (año): *Johnson and Smith (2017)*, *(Styron and Pagani, 2020)*; tres o más autores: *Garcia-Gonzalez et al. (2026)*.
- **Fuentes de datos en el texto** → remitir a Data and Resources: *"…were obtained from the Alaska Satellite Facility (see Data and Resources)."*
- Figuras y tablas **citadas en orden** de aparición (Figure 1 antes que Figure 2…).

### Buenas prácticas (recomendado) / Good practice (recommended)
- Frases cortas; un párrafo = una idea; la primera frase del párrafo dice la idea.
- **Cuantificar siempre:** *"L-band coherence exceeds 0.5 over 78% of forested pixels versus 21% in C-band"*, no *"L-band is much better"*.
- Tiempo verbal: **pasado** para lo que hicimos (*we processed*), **presente** para lo que muestran figuras y lo establecido (*Figure 5 shows*; *L-band penetrates vegetation*).
- Voz activa en primera persona del plural aceptable (*we decompose*).
- Distinguir **observación** (lo que medimos) de **interpretación** (lo que creemos que significa).
- Reconocer los trabajos previos (Scripps/UCSD, LUZ, USGS, ESA, JAXA, NASA/JPL, Seismic Record) y decir **qué añadimos**.
- No exagerar: evitar *first*, *unprecedented*, *novel* salvo que sea verificable.
- Incertidumbre con cada número clave (± 1σ, RMSE frente a GNSS).

---

## 4. Terminología fija / Fixed terminology (ES ↔ EN)

Usar siempre el mismo término en todo el texto, figuras y tablas.

| Español | English (manuscrito) | Nota |
|---|---|---|
| doblete sísmico | earthquake doublet | |
| sismo principal / premonitor | mainshock / foreshock | |
| magnitud momento | moment magnitude, **M**w 7.5 | M w con subíndice en el manuscrito final |
| línea de vista (LOS) | line of sight (LOS) | + = toward the satellite |
| órbita ascendente / descendente | ascending / descending track | tracks: 033A, 025D (S1); 061A, 162A, 126D (NISAR) |
| componente Este / Vertical | east / vertical (up) component | |
| interferograma desenrollado | unwrapped interferogram | |
| coherencia interferométrica | interferometric coherence | |
| banda C / L / X | C-band / L-band / X-band | guion en inglés |
| retrodispersión, amplitud | backscatter, amplitude | dB |
| textura (coeficiente de variación local) | texture (local coefficient of variation) | |
| índice de diferencia de miradas (NDLI) | normalized difference look index (NDLI) | definir en Methods |
| daño a escala de edificio | building-scale damage | |
| huella de edificio | building footprint | |
| falla de San Sebastián | San Sebastián fault | con tilde |
| zona de estudio | study area | |
| sitio de daño | damage site | |
| ventana postsísmica | postseismic window | |

---

## 5. Figuras / Figures

- **Sin título dentro** de la figura; todo texto descriptivo en el pie.
- Etiquetas **(a), (b)…** en minúscula, entre paréntesis, **fuera y arriba-izquierda** de cada panel, de izquierda a derecha y de arriba abajo.
- Tipografía estándar (Helvetica/Arial o Times); **10–12 pt a 100 %**, **≥ 6 pt** tras reducción; variación máxima de 2 pt entre elementos de igual importancia; **sin cursivas**.
- Evitar texto claro sobre fondo oscuro y símbolos abiertos pequeños.
- Mismas unidades, abreviaturas y estilo de ejes en todas las figuras.
- Si se elige color solo en línea: **legibles en escala de grises** (mapas de color perceptuales; no depender solo del rojo/verde).
- Pie de figura: qué se muestra, datos y fechas, símbolos, fuente/licencia. Después, en **línea aparte**, el **alt-text** (1–2 frases que describen la imagen para lectores con discapacidad visual).
- Archivos finales: TIFF, JPEG o PDF de alta resolución, ≤ 10 MB, una figura por archivo, nombrados *Figure 1*, *Figure 2*…

Ejemplo / example:
> **Figure 8.** Damage site at Playa Grande (Urimare), La Guaira. (a) Planet pre-event mosaic (January–March 2026, ~4.8 m); (b) SkySat image, 26 June 2026 11:05 local time (0.62 m); (c) Umbra X-band amplitude (dB, Lee-filtered), 30 June 2026, left-looking; (d) local coefficient of variation; (e) normalized difference look index. Bottom row (f)–(j): 400 m zoom on the yellow box. Contains Umbra open data (CC BY 4.0); imagery © Planet Labs PBC (CC BY-NC 4.0).
> *Alt-text: Ten image panels comparing optical and radar views of a coastal neighborhood before and after the earthquake, with a zoom on a group of collapsed buildings.*

---

## 6. Tablas / Tables

- En **Word** (o LaTeX), nunca como imagen; **título arriba**; una sola fila de encabezados; **unidades entre paréntesis** en el encabezado.
- Definir todas las abreviaturas en la nota al pie de la tabla; notas con símbolos en este orden: *, †, ‡, §, ‖, #.
- Notación científica en forma "× 10".
- Sin subencabezados dentro de la tabla.

---

## 7. Data and Resources (modelo para nuestro artículo / template)

> Sentinel-1 data are from the Copernicus program and were processed with the Alaska Satellite Facility (ASF) Hybrid Pluggable Processing Pipeline (HyP3; https://hyp3-docs.asf.alaska.edu, last accessed December 2026). NISAR geocoded unwrapped interferograms (GUNW) were obtained from the ASF Distributed Active Archive Center (https://search.asf.alaska.edu, last accessed December 2026). ALOS-2 PALSAR-2 ScanSAR data are © JAXA (https://www.eorc.jaxa.jp/ALOS/en/dataset/alos_open_and_free_e.htm, last accessed December 2026). Umbra spotlight data are from the Umbra Open Data Program (s3://umbra-open-data-catalog, CC BY 4.0, last accessed December 2026). Planet imagery was released through the Planet Crisis Response Program (https://source.coop/planet/disasterdata, CC BY-NC 4.0, last accessed December 2026). Building-damage reference data are from Copernicus Emergency Management Service activation EMSR884 (https://mapping.emergency.copernicus.eu/activations/EMSR884/, last accessed December 2026) and the Humanitarian OpenStreetMap Team (https://huggingface.co/datasets/hotosm/venezuela_eq_2026, last accessed December 2026). Administrative boundaries are from geoBoundaries (https://www.geoboundaries.org, last accessed December 2026), active faults from the GEM Global Active Faults Database (Styron and Pagani, 2020), and roads from OpenStreetMap (https://www.openstreetmap.org, last accessed December 2026). Earthquake parameters are from the U.S. Geological Survey (USGS) Comprehensive Catalog (https://earthquake.usgs.gov/earthquakes/eventpage/us6000t7zp, last accessed December 2026). All processing code is available at https://github.com/jf-floresriera/SAR_multifrequency (archived at Zenodo, doi: [to be added]). Supplemental Material for this article includes [describe].

*(Actualizar fechas con `05_documentacion/registro_descargas*.csv` y `fuentes_mapas_base*.csv`.)*

---

## 8. Referencias / References (estilo SRL / SRL style)

- Orden alfabético por primer autor; solo obras publicadas (las bases de datos en línea van en Data and Resources).
- Formato / format:
  - Revista: *Styron, R., and M. Pagani (2020). The GEM Global Active Faults Database, Earthq. Spectra 36, no. 1_suppl, 160–180, doi: 10.1177/8755293020944182.*
  - Libro: *Hanssen, R. F. (2001). Radar Interferometry: Data Interpretation and Error Analysis, Kluwer Academic Publishers, Dordrecht, The Netherlands, 308 pp.*
  - Capítulo: *Apellido, A. B., and C. D. Apellido (Año). Título del capítulo, in Título del libro, E. Editor (Editor), Editorial, Ciudad, páginas.*
- Redes sísmicas con su DOI de FDSN (http://www.fdsn.org/networks/citation/).
- Abreviar revistas según la norma (p. ej., *Seismol. Res. Lett.*, *Bull. Seismol. Soc. Am.*, *Geophys. Res. Lett.*, *J. Geophys. Res.*).

---

## 9. Lo que el editor y los revisores buscarán / What editors and reviewers will look for

1. ¿Está claro qué añade el artículo frente a los productos rápidos ya publicados?
2. ¿Los números están validados (GNSS) y con incertidumbre?
3. ¿Se explican las diferencias de líneas base temporales entre sensores (6–12 días; ventana postsísmica)?
4. ¿Se tratan las limitaciones (ionosfera en banda L, geometría Umbra sin DEM, imagen previa de Planet a 4.8 m)?
5. ¿Los datos y el código son accesibles (Data and Resources, GitHub + Zenodo)?
6. ¿Las licencias permiten publicar las figuras (Planet CC BY-NC frente a CC-BY de acceso abierto)?
