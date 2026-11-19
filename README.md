# GUAIRA-SAR · SAR_multifrequency

**From fault to façade: multi-frequency SAR (C-, L- and X-band) and high-resolution optical observations of the 24 June 2026 Venezuela earthquake doublet along the La Guaira coast**

[![Open 01 in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jf-floresriera/SAR_multifrequency/blob/main/notebooks/01_Inventario_Multisensor.ipynb)
[![Open 02 in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jf-floresriera/SAR_multifrequency/blob/main/notebooks/02_Procesamiento_InSAR_multifrecuencia.ipynb)
![License: MIT](https://img.shields.io/badge/code-MIT-blue)
![Status](https://img.shields.io/badge/status-in%20progress-orange)
![Target](https://img.shields.io/badge/target-SRL%20Focus%20Section%202026-8A2BE2)

Reproducible, open-data workflow supporting a manuscript in preparation for the *Seismological Research Letters* Focus Section on the **2026 Venezuela, Colombia and Panama Earthquakes**.

> 🇪🇸 **Resumen:** flujo de trabajo abierto y reproducible que compara, para el doblete sísmico Mw 7.2 + 7.5 del 24 de junio de 2026 en Venezuela, la deformación cosísmica medida con InSAR en **banda C (Sentinel-1)** y **banda L (NISAR, ALOS-2)**, y el daño a escala de edificio observado con **radar banda X submétrico (Umbra)** e **imágenes ópticas de alta resolución (Planet)**. Ver [sección en español](#-versión-en-español).

---

## 1 · The event

On 24 June 2026 a strike-slip earthquake doublet (Mw 7.2 at 22:04:33 UTC, followed 30–40 s later by Mw 7.5) ruptured the San Sebastián – Boconó fault system along the northern coast of Venezuela. La Guaira state, between Catia La Mar and Caraballeda, concentrated the most severe damage.

## 2 · Workflow

<p align="center"><img src="docs/img/flujo_trabajo.gif" width="560" alt="Animated workflow: open data, inventory, InSAR C and L processing, X-band and optical damage analysis, East/Up decomposition with GNSS validation, integration and publication"></p>

| Step | What is done | Notebook / script |
|---|---|---|
| **1 · Inventory** | Discover every open dataset; classify NISAR GUNW as pre-, co- or post-seismic; Umbra STAC metadata; Umbra × Planet overlaps; Sentinel-1 coseismic pairs; access dates and licences | `notebooks/01_…` · `src/umbra_inventario.py`, `src/nisar_filtrar.py`, `src/inventario_multisensor.py`, `src/cruce_umbra_planet.py` |
| **2a · InSAR C and L** | Unwrapped phase → LOS (m) with **one sign convention for all sensors** (+ = toward the satellite); coherence ≥ 0.3 mask; NISAR ionospheric correction; resampling to a common UTM 19N 80 m grid | `notebooks/02_…` · `src/nisar_gunw_a_geotiff.py`, `src/proc_s1_y_descomposicion.py` |
| **2b · Damage X + optical** | Umbra GEC amplitude (dB) against Planet SkySat/PlanetScope post-event and the Q1-2026 pre-event mosaic, co-registered on the same 0.5 m grid | `src/cruce_umbra_planet.py` |
| **3 · East / Up** | Ascending + descending least-squares decomposition (N ≈ 0, supported by GNSS dN ≈ −1 cm at CCS1), **separately for C-band and L-band**, then L − C difference maps | `notebooks/02_…` (cells 6–8) |
| **4 · Integration** | Damage vs. deformation gradients and distance to the fault trace; infrastructure profiles (airport, port, highway viaduct) | *in progress* |
| **5 · Publication** | Code release on GitHub → Zenodo DOI; derived products on Zenodo; *Data and Resources* section with URLs and access dates | — |

## 3 · Data

<p align="center"><img src="docs/img/linea_tiempo_sensores.gif" width="760" alt="Animated timeline of acquisitions from 11 June to 6 July 2026 for Umbra, Sentinel-1, NISAR and Planet, with the earthquake marked on 24 June"></p>

| Band (λ) | Sensor | What we use | Dates (2026) | Licence / access |
|---|---|---|---|---|
| **C** (5.55 cm) | Sentinel-1A/1D | HyP3 INSAR_GAMMA, tracks **033A** and **025D**, 40 m, look vectors | 18 Jun → 25 Jun | Copernicus, free (ASF DAAC) |
| **L** (23.8 cm) | NISAR | GUNW, tracks **061A**, **162A** (asc.) and **126D** (desc.), + 054D | 13 Jun → 4 Jul (12-day pairs) | NASA, free (ASF DAAC) |
| **L** (23.8 cm) | ALOS-2 PALSAR-2 | ScanSAR L1.1 (*pending download*) | JAXA emergency obs. from 30 Jun | JAXA free release (3 Jul 2026), ASF mirror |
| **X** (3.1 cm) | Umbra | 26 spotlight collects (GEC, SICD, SIDD) | 26 Jun → 2 Jul (post-event only; several at night) | CC BY 4.0 |
| Optical | Planet SkySat / PlanetScope | 17 post-event scenes; Q1-2026 PlanetScope mosaic (pre-event) | 26–28 Jun · Jan–Mar | CC BY-NC 4.0 (not redistributed) |
| Optical | Sentinel-2 L2A | True colour, before/after | Jun–Jul | Copernicus, free |
| GNSS | CCS1 and others | Coseismic offsets for validation | — | Cited sources |

<p align="center"><img src="docs/img/mapa_umbra_por_dia.gif" width="760" alt="Animated map of the 26 Umbra X-band collects appearing day by day between 26 June and 2 July 2026 over Yumare, Ocumare, La Guaira, Caracas and Guarenas–Guatire"></p>

**Umbra coverage by area:** La Guaira coast (Catia La Mar → La Guaira, left + right look), eastern Caracas, Guarenas–Guatire (11 collects), Ocumare / Henri Pittier (left + right look) and Yumare (near the Mw 7.2 epicentre). No repeat-pass geometry exists, so X-band is used for amplitude-based damage mapping, not InSAR.

## 4 · How to run

### Google Colab (recommended)
1. Click a **Open in Colab** badge above.
2. Run the cells **in order**. Cell 1 installs dependencies; cell 2 mounts Google Drive (all outputs go to `InSAR_LaGuaira_Resultados/GUAIRA-SAR/`).
3. A NASA Earthdata account is needed to download NISAR/Sentinel-1 and to use HyP3.
4. If the Colab session restarts, start again from cell 1.

### Local
```bash
git clone https://github.com/jf-floresriera/SAR_multifrequency.git
cd SAR_multifrequency
conda env create -f environment.yml
conda activate guaira-sar
jupyter lab notebooks/
```
Edit the `RAIZ` / `CARPETA` paths at the top of each notebook if not using Google Drive.

### Regenerate the animations in this README
```bash
python docs/make_animations.py    # writes docs/img/*.gif
```

## 5 · Repository layout

```
SAR_multifrequency/
├── notebooks/
│   ├── 01_Inventario_Multisensor.ipynb          # inventory, filtering, HyP3, downloads
│   └── 02_Procesamiento_InSAR_multifrecuencia.ipynb  # common InSAR processing, E/U, GNSS check
├── src/                      # same code as the notebook cells, as scripts
├── docs/
│   ├── img/                  # README animations (GIF)
│   ├── make_animations.py    # reproducible generator of the GIFs
│   └── notas_procesamiento.md   # processing log: every decision, value and reason
├── figures/                  # final manuscript figures (SRL format)
├── environment.yml
├── CITATION.cff
└── LICENSE
```

Heavy data (`.h5`, `.tif`, `.zip`, `.nitf`) are **never** committed (see `.gitignore`); they live in Google Drive during processing and derived products will be archived on Zenodo.

## 6 · Conventions

| Item | Convention |
|---|---|
| LOS sign | **+ = motion toward the satellite** (range decrease) for every sensor |
| Units | metres |
| Common grid | UTM zone 19N (EPSG:32619), 80 m |
| Coherence mask | γ ≥ 0.3 |
| Time | UTC (local time = UTC − 4 h) |
| Event time | 2026-06-24 22:04:33 UTC (Mw 7.2) |
| Look geometry | NISAR looks **left**, Sentinel-1 looks **right**: westward motion appears with opposite LOS sign in ascending tracks |

## 7 · Status

- [x] Multi-sensor inventory (Sentinel-1, NISAR, Umbra, Planet)
- [x] NISAR coseismic GUNW identified and downloaded (061A, 162A, 126D)
- [x] Sentinel-1 coseismic pairs identified (033A, 025D) and submitted to HyP3
- [ ] Sentinel-1 40 m products with look vectors
- [ ] ALOS-2 ScanSAR interferometry
- [ ] East/Up decomposition C vs L and GNSS validation
- [ ] Umbra × Planet damage figures
- [ ] Manuscript, Zenodo deposit, submission (deadline 21 Dec 2026)

## 8 · Data attribution

- Contains modified Copernicus Sentinel data (2026), processed by ESA and ASF HyP3.
- NISAR data courtesy of NASA/JPL-Caltech and ISRO, distributed by ASF DAAC.
- ALOS-2 PALSAR-2 data © JAXA.
- Contains Umbra open data, licensed under CC BY 4.0.
- Imagery © Planet Labs PBC, released through the Planet Crisis Response Program under CC BY-NC 4.0.

## 9 · Citation and licence

Code: MIT (see [`LICENSE`](LICENSE)). Please cite using [`CITATION.cff`](CITATION.cff); a Zenodo DOI will be added on the first release. Data keep the licence of each provider.

---

## 🇪🇸 Versión en español

**Qué es:** el flujo completo, abierto y reproducible del artículo *"De la falla a la fachada"* para la sección especial de SRL sobre los sismos de 2026.

**Pregunta científica:** ¿cómo cambia lo que vemos de un mismo sismo según la frecuencia y la resolución del sensor? Comparamos la deformación cosísmica en **banda C (Sentinel-1)** y **banda L (NISAR y ALOS-2)**, ambas con órbita ascendente y descendente para obtener los componentes **Este y Vertical**, y el daño a escala de edificio con **Umbra (banda X, < 1 m, de día y de noche)** frente a **Planet (0,5–3 m)**.

**Cómo correrlo:** abra los notebooks en Colab con los botones de arriba y ejecute las celdas en orden. Si Colab se reinicia, empiece desde la celda 1. Todos los resultados se guardan en Google Drive.

**Reglas del proyecto:** un solo signo de LOS para todos los sensores (+ = hacia el satélite), grilla común UTM 19N a 80 m, coherencia ≥ 0,3, todo en metros y en UTC. Cada decisión queda anotada en [`docs/notas_procesamiento.md`](docs/notas_procesamiento.md).
