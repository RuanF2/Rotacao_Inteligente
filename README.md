# Rotação Inteligente 2.0 — Global Agricultural Intelligence

**Climate-informed crop-rotation decision support using NASA Earth observation data.**

Developed for the **NASA Space Apps Challenge 2026**, addressing *Field Shift: Adapting Farms with NASA Data*.

> **Decision support, not an agronomic prescription.** Outputs are model-based scenarios, not validated field recommendations. They should be reviewed alongside field observations and advice from qualified local professionals.

**Language:** English | [Português (Brasil)](README.pt-BR.md)

## The challenge

Agricultural planning is increasingly affected by variable rainfall, extreme heat, limited water availability, and soil degradation. Farmers need to understand how local climate history and crop characteristics interact before choosing a sequence of crops.

## The solution

Rotação Inteligente 2.0 is an interactive web application that supports crop-rotation planning for user-selected geographic coordinates. It combines historical environmental analysis, multi-objective optimization, climate sensitivity scenarios, and explainable comparisons.

The application can:

1. **Analyze local climate history:** retrieve daily NASA POWER data and calculate rainfall, temperature, modeled soil moisture, reference evapotranspiration (ET₀), aridity, dry spells, extreme heat, rainfall erosivity, and historical trends. NOAA ENSO/ONI information provides additional climate context.
2. **Assess environmental vulnerability:** calculate an experimental index based on eight documented indicators and rating ranges.
3. **Explore crop rotations:** evaluate a catalog of **13 crops** and optimize **24-month sequences** using the multi-objective **NSGA-II** algorithm (`pymoo`), subject to agronomic constraints.
4. **Compare four strategies:** **A — Current rotation**, **B — Soil conservation**, **C — Water resilience**, and **D — User-priority balance**.
5. **Evaluate historical variability:** compare modeled outcomes across approximately 34 overlapping two-year historical windows, subject to data availability.
6. **Test climate sensitivity:** simulate hypothetical changes in temperature, precipitation, and irrigation, without presenting them as climate forecasts.
7. **Explain model outputs:** display trade-offs, assumptions, reference periods, uncertainty, evidence completeness, and reasons why an optimization run may not find a suitable sequence.
8. **Generate reports:** produce Markdown reports and browser-printable views that can be saved as PDF.

A key feature is the **24-month rotation timeline**, which helps users visualize crop sequences, botanical families, and modeled soil-cover duration alongside local climate conditions.

## Application screens

| Screen | Main features |
|---|---|
| **Dashboard** | Environmental conditions, experimental vulnerability index, analytical risk notices, strategy overview, and map |
| **Property** | Select coordinates or a location on a map; review soil, slope, irrigation, current rotation, permitted crops, and priorities; save and load local property records using SQLite |
| **Environmental analysis** | NASA POWER climate series, ENSO context, historical-period comparisons, vulnerability indicators, and NASA GIBS visual overlays |
| **Smart rotation** | A–D strategies, 24-month crop sequences, comparative indicators, Pareto-front exploration, and explanations |
| **Climate simulator** | Hypothetical temperature, precipitation, and irrigation adjustments, baseline selection, and sensitivity comparisons |
| **Report** | Findings, evidence, modeled results, risks, data sources, and limitations in a printable format |

When the optimizer does not identify a feasible rotation, the application provides diagnostic information about the checked constraints. **Failure to find a solution does not mathematically prove that no valid solution exists.**

## Data sources and integration

| Source | Use in the application |
|---|---|
| **NASA POWER** | Historical daily meteorological and modeled soil-moisture data used in environmental and rotation calculations |
| **NOAA ENSO/ONI** | Historical El Niño / La Niña context |
| **NASA GIBS** | Visual map layers for NDVI, IMERG precipitation, and SMAP soil moisture; these layers are **not assimilated** into the optimizer |
| **OpenTopoData / SRTM** | Elevation and terrain-slope context, subject to geographic and service coverage |
| **OpenStreetMap / Nominatim** | Reverse geocoding and map context |

NASA POWER data can cover the period from **1991 to the latest available dates in 2026**, but historical full-calendar-year comparisons generally use **1991–2025** (35 completed calendar years), when data completeness requirements are met. Approximately 34 overlapping two-year windows represent **68 crop-year model observations, not 68 independent years or field trials**.

See [Data sources and attribution](DATA_SOURCES.md) and [Scientific methodology](METHODOLOGY.md).

## Technology stack

- **Backend:** Python, FastAPI, pandas, NumPy, SciPy, `pymoo` (NSGA-II), SQLite.
- **Scientific processing:** Python modules for NASA POWER data retrieval, ENSO analysis, climate indicators, vulnerability assessment, crop evaluation, optimization, and explainability.
- **Frontend:** React 19, Vite 7, Tailwind CSS 4, Recharts, React Leaflet.
- **Additional analytical interface:** Streamlit, available within the repository.

The current application does **not** integrate Landsat, ECOSTRESS, or NEX-GDDP-CMIP6 data pipelines. GeoPandas, Rasterio, Xarray, and scikit-learn are not required dependencies.

## Repository structure

```text
Rotacao_Inteligente/
├── backend/
│   ├── app/                 # FastAPI, climate analysis, optimization, reports
│   │   └── data/            # Crop catalog
│   └── tests/               # Backend tests
├── frontend/
│   └── src/                 # React interface, components, and tests
├── rotacao_inteligente/
│   ├── core/                # Scientific data-processing modules
│   ├── data/                # Reference data and local cache directories
│   ├── tests/               # Scientific-module tests
│   └── app.py               # Additional Streamlit interface
├── scripts/                 # Verification and integration-check scripts
├── METHODOLOGY.md
├── DATA_SOURCES.md
├── README.pt-BR.md
├── README.md
├── LICENSE
└── .gitignore
```

The React frontend sends property settings to the FastAPI backend, including `POST /api/analise`. The backend retrieves or reads cached climate records, computes environmental indicators, evaluates rotation candidates, runs NSGA-II, compares strategies, and returns structured results and explanations.

When the backend is running, its interactive API documentation is available at **http://localhost:8000/docs**.

## Run locally

### Requirements

- **Python 3.10+**
- **Node.js 20.19+ or 22.12+** (Vite 7)
- Internet access for initial climate data retrieval and live mapping services

### 1. Install backend dependencies

Run from the repository root.

**Windows / PowerShell:**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

### 2. Start the backend

From the repository root, in the activated Python environment:

```bash
cd backend
python -m uvicorn app.main:app --port 8000
```

### 3. Start the frontend

Open a second terminal in the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. A demonstration property is available in the semi-arid region of Piauí, Brazil. The first analysis may require downloading climate data and therefore take longer than subsequent cached analyses.

To verify a production build from the `frontend/` directory:

```bash
npm run build
npm run preview
```

### Optional Streamlit interface

From the repository root, using an activated Python environment:

```bash
python -m pip install -r rotacao_inteligente/requirements.txt
cd rotacao_inteligente
python -m streamlit run app.py
```

## Configuration

| Environment variable | Purpose |
|---|---|
| `ROTACAO_DB_PATH` | Path to the local SQLite database |
| `ROTACAO_CORS_ORIGINS` | Allowed frontend origins |
| `ROTACAO_OFFLINE` | When set to `1`, disables selected external topography and reverse-geocoding requests; **does not provide climate data for uncached locations** |
| `ROTACAO_GEOCODER_UA` | Nominatim User-Agent; configure an identifying value and contact information |
| `ROTACAO_GEOCODER_URL` | Optional alternative Nominatim endpoint |
| `ROTACAO_NSGA_POP`, `ROTACAO_NSGA_GEN`, `ROTACAO_NSGA_SEED` | Optimization population, generations, and random seed (defaults: `120`, `120`, `42`) |
| `VITE_API_URL` | Optional frontend API address; local development normally uses the Vite proxy |

The currently used public services do not require project API keys. Follow each provider's rate limits, attribution rules, and usage policies. **Do not commit `.env` files, credentials, local databases, or downloaded caches.**

## Tests and verification

The repository includes automated tests and scripts for technical and external-service validation. Test presence does **not** establish that a specific commit or environment has passed all checks.

Run the relevant commands after installing dependencies:

**Backend (from repository root):**

```powershell
cd backend
python -m pytest -q
cd ..
```

**Scientific modules (install `rotacao_inteligente/requirements.txt` first):**

```powershell
cd rotacao_inteligente
python -m pytest -q
cd ..
```

**Frontend:**

```powershell
cd frontend
npm ci
npm test
npm run build
cd ..
```

**Additional verification scripts (from the repository root):**

```powershell
python scripts/smoke_global_3pontos.py
python scripts/verificacao_independente_srn.py
python scripts/validar_integracoes.py
```

`validar_integracoes.py` uses real external services (NASA POWER, OpenTopoData, Nominatim, and NASA GIBS). Results depend on internet connectivity, rate limits, and external-service availability.

## Internet access, caching, and offline behavior

- Historical NASA POWER observations are downloaded **on demand** and cached locally during execution.
- **Pre-downloaded climate caches are not included in the public repository.** A fresh clone generally needs internet access before its first environmental analysis, including for the demonstration property.
- Previously analyzed locations may reuse locally cached observations.
- Uncached locations cannot be analyzed without access to the required climate data.
- Topography, reverse geocoding, NASA GIBS imagery, and background-map tiles may require access to their respective online services.
- The `ROTACAO_OFFLINE` setting does not turn the application into a fully offline, globally self-contained dataset.

## Scientific limitations and responsible use

- **Spatial resolution:** NASA POWER represents gridded climate estimates, not measurements taken at an individual farm plot.
- **Simplified water balance:** modeled calculations do not carry soil-water storage between months; reference evapotranspiration uses Hargreaves rather than a complete Penman–Monteith formulation.
- **Experimental indicators:** the vulnerability index and *Environmental Soil Debt* are decision-support constructs, not direct measurements of soil fertility, carbon content, or degradation.
- **Crop parameters:** some values are estimated or adapted from reference literature and require local agronomic calibration.
- **Yields and seed quantities:** the system does not provide validated sowing-rate calculations or forecasts of absolute harvest output (kg/ha, tonnes, or bags). Modeled relative potential water-stress losses are **not observed crop yields**.
- **Economic returns:** reliable profitability projections require local prices, costs, and calibrated productivity data that are not available in the current implementation.
- **Historical evaluation:** overlapping two-year comparison windows are not independent experiments. Model-derived outcomes are not field-trial validation.
- **Visual satellite layers:** SMAP, IMERG, and NDVI overlays are not numerical inputs to the rotation optimizer.
- **Climate scenarios:** user-specified temperature and precipitation adjustments are hypothetical sensitivity tests, not official climate projections or predictions.
- **Alerts:** dashboard warnings describe analytical risks; the application does **not** issue calibrated “plant now” instructions or send WhatsApp, SMS, email, or push notifications.
- **Evidence indicator:** the 0–100 score reflects evidence quality/completeness, **not** the probability that a crop rotation will succeed.

**Use this software as an exploratory decision-support prototype, with appropriate professional review before real-world agricultural decisions.**

## Documentation

- [Scientific methodology](METHODOLOGY.md)
- [Data sources and attribution](DATA_SOURCES.md)
- [README em português](README.pt-BR.md)
- [MIT License](LICENSE)

## Project context

This prototype was developed for the **NASA Space Apps Challenge 2026**. NASA data references indicate the origin of the datasets and imagery and do not imply NASA endorsement, certification, or field validation.
