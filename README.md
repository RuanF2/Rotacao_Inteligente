# Rotação Inteligente 2.0 — Global Agricultural Intelligence

**Climate-informed crop rotation decision support powered by NASA Earth observation data.**

A project for the **NASA Space Apps Challenge 2026**, addressing *Field Shift: Adapting Farms with NASA Data*.

> **Decision-support tool, not a prescription.** Recommendations are model-based scenarios and do not replace farmers' judgment, field measurements, or advice from local agronomists.

## The challenge

Farmers must decide what to plant and when amid increasingly variable rainfall, extreme heat, soil degradation, and limited water availability. Crop-rotation decisions often lack location-specific historical climate analysis, while the potential benefits of legumes and cover crops are difficult to weigh against crop-failure risk.

## Our solution

For user-selected coordinates around the world, Rotação Inteligente 2.0:

1. **Analyzes environmental conditions** using approximately 35 complete years of daily NASA POWER data (precipitation, temperature, and modeled soil moisture). It derives reference evapotranspiration (ET₀), aridity, dry spells, extreme-heat indicators, rainfall erosivity, climate trends, and historical relationships with El Niño/La Niña.
2. **Assesses vulnerability** through a documented, experimental index composed of eight indicators and defined rating bands.
3. **Optimizes crop rotations** using the multi-objective **NSGA-II** algorithm (`pymoo`) and a catalog of 13 crops, with agronomic constraints covering planting windows, temperature suitability, overlap, monoculture, and yearly commercial-crop requirements.
4. **Compares four strategies:** **A — Current rotation**, **B — Soil conservation**, **C — Water resilience**, and **D — User-priority balance**, assessing their performance across approximately 34 overlapping pairs of historical years rather than relying on long-term averages alone.
5. **Simulates climate sensitivity** under hypothetical changes in temperature and precipitation.
6. **Explains recommendations**, including their rationale, supporting evidence, sources and reference periods, modeled relative water-stress losses, risks, uncertainty and missing information. The reported evidence-quality indicator is **not** a probability that a crop will succeed.
7. **Produces reports** in Markdown and a print-friendly format that can be saved as PDF from the browser.

A distinguishing feature is the **24-month crop-rotation timeline**, which displays planting sequences, botanical families, and modeled soil-cover duration in relation to local water availability.

When no valid two-year rotation is found, the interface provides a **diagnostic explanation of the constraints checked**, rather than inventing an agronomically unsupported recommendation. An optimizer's failure to find a solution is not automatically proof that no solution exists.

## Current implementation status: what works and what does not

| Capability | Current status |
|---|---|
| NASA POWER climate ingestion, local caching, historical environmental analysis | **Implemented in FastAPI 2.0** (NASA1 POWER client reused) |
| ENSO/ONI context | **Implemented in FastAPI 2.0** using the shared legacy module and auxiliary NOAA data |
| 13-crop evaluation, 24-month rotation optimization, Pareto solutions and A–D strategies | **Implemented in FastAPI 2.0**, with a new `rotacao.py` and catalog |
| Soil/environmental vulnerability, mapped satellite overlays, hypothetical climate sensitivity, reports | **Implemented in the 2.0 web application** |
| Legacy `planejador`, `janelas`, `alerta`, `semaforo` | **Streamlit/NASA1 only; not exposed by the FastAPI 2.0 endpoints** |
| Automatic “PLANTE AGORA” planting message and SMS/WhatsApp/email/push notifications | **Not implemented in the 2.0 web application**. Legacy planting alerts are *simulated* and require agronomically calibrated thresholds; no delivery integration exists. |
| Seed quantity in kg for a specified field area | **Not implemented as a validated 2.0 calculation**; the 13-crop catalog has no sowing-rate dataset. The six-crop legacy CSV contains missing rates, including maize and sorghum. |
| Actual harvest in kg/ha, tonnes or bags, or financial returns | **Not forecast**: regional yield fields are unpopulated and the local productivity dataset has no observations. Historical **relative potential water-stress loss** is modeled using Ky; this is not a calibrated yield forecast. |
| Evidence “confidence” indicator | **Implemented as a 0–100 evidence-quality/completeness score**, **not** a statistical chance of success or validation of real-world outcomes. |

**Historical-period interpretation:** The legacy POWER request can extend from **1991 through 2026** to support complete agricultural-year windows; annual historical comparisons in the current materials often use **1991–2025** (35 complete calendar years). Approximately 34 overlapping two-year windows yield 68 crop-year observations, but those are **not independent years or trials**. Available coverage and final complete years depend on NASA POWER availability and processing rules.

**No automated grower notifications:** The web dashboard displays analytical warnings about climate risks and model limitations. These are not calibrated “plant now” commands, messages sent to growers, or external notifications.

## Application features

| Screen | Functionality |
|---|---|
| **Dashboard** | Vulnerability assessment, environmental conditions, statistically qualified alerts, strategies, and map |
| **Property** | Map-based or coordinate-based location selection, OpenStreetMap reverse geocoding, soil properties, slope, irrigation, current rotation, allowed crops, priorities, and local SQLite save/load; prompts to review location-dependent inputs after moving |
| **Environmental analysis** | NASA POWER time series, soil moisture, ENSO, comparison of 1991–2005 with 2011–2025, vulnerability indicators, and NASA GIBS map overlays (NDVI, IMERG, SMAP) |
| **Smart rotation** | Strategies A–D, comparative tables and radar charts, explanations, and Pareto-front exploration; actionable diagnostics if optimization fails |
| **Climate simulator** | Temperature and precipitation adjustments, irrigation, baseline-period selection, historical versus recent versus hypothetical scenarios, and sensitivity curves |
| **Report** | Exportable presentation of evidence, analyses, results, risks, and limitations |

## Technology stack

- **Backend:** Python, FastAPI, pandas, NumPy, SciPy, `pymoo` (NSGA-II), SQLite.
- **Scientific core:** the preserved NASA1/Streamlit application under `rotacao_inteligente/`. The FastAPI 2.0 service reuses **only** `core.nasa_power`, `core.enso` and selected constants in legacy `config.py`; its rotation optimizer, crop catalog, vulnerability index, explanations and API use separate 2.0 implementations. The original `planejador`, `janelas`, `alerta`, `semaforo` and other NASA1 workflows remain available **only in Streamlit**.
- **Frontend:** React 19, Vite, Tailwind CSS 4, Recharts, React Leaflet.
- **External data/services:** NASA POWER, NASA GIBS, OpenTopoData (SRTM-derived elevation/slope), and OpenStreetMap Nominatim.

GeoPandas, Rasterio, Xarray, and scikit-learn are **not** current dependencies. Landsat, ECOSTRESS, and NEX-GDDP-CMIP6 are **not** implemented data pipelines.

## Repository structure

```text
RotacaoInteligente2/
├── backend/
│   ├── app/
│   │   ├── legacy.py                # Partial NASA1 adapter: POWER, ENSO, config
│   │   ├── clima.py                 # Climate series, ET₀, ENSO, scenarios
│   │   ├── vulnerabilidade.py       # Experimental vulnerability index
│   │   ├── rotacao.py               # Rotation evaluation and NSGA-II
│   │   ├── explicabilidade.py       # Recommendation explanations
│   │   ├── servico.py               # Analysis orchestration
│   │   ├── topografia.py            # Elevation and slope via OpenTopoData
│   │   └── main.py                  # FastAPI endpoints
│   └── tests/
├── frontend/
│   └── src/                       # React interface and tests
├── rotacao_inteligente/
│   ├── core/                      # Original NASA1 modules (mostly Streamlit-only)
│   ├── data/                      # Reference datasets; runtime caches excluded
│   └── app.py                     # Preserved Streamlit interface
├── scripts/
├── METHODOLOGY.md
├── DATA_SOURCES.md
├── README.pt-BR.md
├── README.md
├── LICENSE
└── .gitignore
```

**Analysis flow:** the React frontend submits property settings to `POST /api/analise`. The FastAPI backend obtains the corresponding NASA POWER time series (from a local cache if available, otherwise from the public API), derives climate indicators and vulnerability, evaluates crop/month/year combinations, runs NSGA-II, selects strategies B/C/D, and returns comparisons and explanations as JSON.

API documentation is available at **http://localhost:8000/docs** when the backend is running.

## Local setup

### Requirements

- **Python 3.10+**
- **Node.js 20.19+ or 22.12+** (Vite 7 requirement)
- Internet access for the first NASA POWER request for a location and for external map services

### 1. Install the backend

From the repository root:

**Windows (PowerShell):**

```powershell
# From the repository root
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

**Linux/macOS:**

```bash
# From the repository root
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

### 2. Install the frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm ci
```

### 3. Start the application

**Terminal 1 — API:**

```bash
cd backend
# Activate your Python environment if it is not already active.
python -m uvicorn app.main:app --port 8000
```

**Terminal 2 — Web interface:**

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser. The application includes a demonstration property in the semi-arid region of Piauí, Brazil. The initial analysis may take longer when the climate cache has not yet been populated.

To build the frontend:

```bash
cd frontend
npm run build
npm run preview
```

The original Streamlit application is also preserved:

```bash
cd rotacao_inteligente
python -m pip install -r requirements.txt
streamlit run app.py
```

## Configuration

| Environment variable | Purpose |
|---|---|
| `ROTACAO_DB_PATH` | Local SQLite database path (default under `backend/`) |
| `ROTACAO_CORS_ORIGINS` | Allowed frontend origins |
| `ROTACAO_OFFLINE` | Set to `1` to disable SRTM and reverse-geocoding requests |
| `ROTACAO_GEOCODER_UA` | Nominatim User-Agent; configure a project-identifying value with contact information in your local environment |
| `ROTACAO_GEOCODER_URL` | Optional alternative Nominatim server |
| `ROTACAO_NSGA_POP`, `ROTACAO_NSGA_GEN`, `ROTACAO_NSGA_SEED` | Optimizer population, generations, and random seed (defaults: `120`, `120`, `42`) |
| `VITE_API_URL` | Optional frontend API URL; empty by default for local development via the Vite proxy |

No API keys are required for the publicly accessible services currently used. Follow each provider's usage and attribution policies, including Nominatim's request-rate and identification requirements. **Never commit local `.env` files or credentials.**

## Tests and verification

Run these commands from the relevant directories after installing dependencies:

```bash
# Backend
cd backend
python -m pytest -q

# Frontend
cd frontend
npm test
npm run build

# Preserved NASA1 scientific core
cd rotacao_inteligente
python -m pytest -q
```

From the repository root, with Python dependencies installed:

```bash
python scripts/smoke_global_3pontos.py
python scripts/verificacao_independente_srn.py
python scripts/validar_integracoes.py
```

The last command requires internet connectivity and tests real NASA POWER, OpenTopoData, Nominatim, and NASA GIBS access. Validation results depend on network availability and service status. Separate backend and frontend test suites were also run successfully during final project checks; see the audit and diagnostic documents for their respective environments and results.

## Data access, caching, and offline behavior

- Historical NASA POWER requests are cached **locally at runtime**. For a new location, the first request may download decades of daily observations and take several minutes.
- **Pre-downloaded climate caches are intentionally excluded from this public repository.** As a result, a fresh clone generally needs internet access before its first environmental analysis, including for the default demonstration property.
- Once data have been cached locally, previously analyzed locations can reuse those observations.
- Without internet access, an uncached location cannot be analyzed. SRTM-based slope may be unavailable and can be entered manually.
- NASA GIBS imagery and background map tiles require browser internet access.

## Scientific limitations and responsible use

- **Spatial resolution:** NASA POWER represents a gridded climate estimate (approximately 50 km for relevant meteorological parameters), **not measurements taken within a specific field**.
- **Simplified water balance:** the current model does not carry soil-water storage from month to month, and reference evapotranspiration uses Hargreaves rather than a complete wind-aware Penman–Monteith implementation.
- **Experimental metrics:** the vulnerability index and *Environmental Soil Debt* indicator are decision-support constructs, **not observed measurements of soil fertility, soil carbon, or degradation**.
- **Crop parameters:** confidence levels are disclosed; estimated or analogous parameters need local calibration and agronomic validation.
- **Yields and seed rates:** the 13-crop 2.0 catalog does not supply field-validated sowing rates or measured regional yields, so the app does **not** calculate validated seed kilograms or forecast harvest quantities. Relative modeled water-stress losses do not establish absolute production.
- **Alerts:** the 2.0 interface does not provide calibrated planting commands or WhatsApp, SMS, email or push delivery.
- **Economic outcomes:** local crop prices, production costs, and reliably calibrated yields are insufficient for a robust profitability forecast.
- **Historical comparisons:** overlapping two-year historical windows are not independent experimental observations. Reported water-deficit and crop-loss indicators are **model outputs**, not measured field outcomes or validated predictions of actual harvest losses.
- **Data layers:** SMAP, IMERG, and NDVI are presented as visual map layers; they are not independently assimilated into the crop-rotation optimizer.
- **Climate scenarios:** user-defined temperature and precipitation adjustments are **hypothetical sensitivity tests, not official climate projections**.
- **Optimizer diagnostics:** an NSGA-II run that fails to identify a valid sequence does not, by itself, mathematically establish global infeasibility.

The system should be treated as a **transparent, exploratory decision-support prototype** and its outputs reviewed with local practitioners before real agricultural decisions.

## Supporting documentation

- [Scientific methodology](METHODOLOGY.md)
- [Data sources and attribution](DATA_SOURCES.md)
- [Portuguese README](README.pt-BR.md)
- [MIT License](LICENSE)

## Project context

Developed as a prototype for the **NASA Space Apps Challenge 2026**. References to NASA datasets and imagery indicate the origin of source information, not NASA endorsement or field validation of this system.
