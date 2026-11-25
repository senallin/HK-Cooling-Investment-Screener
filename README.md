# HK Cooling Investment Screener (Streamlit)
Hong Kong › District › Cluster › Buildings. Pick a district, select a cluster of **real buildings** (HK-BFETD v1.1) on a map,
and compare three ways to cool them over their life:

* **Individual**: each building keeps its own chillers (reference case, replaced at end of life);
* **CMCS**: a privately built shared central plant and pipe network;
* **DCS**: connection to a government District Cooling System at the published **EMSD tariff** (Kai Tak 2026/27).

Results: lifecycle cost (present value), NPV saving, simple and discounted payback, levelised cost, electricity and emissions,
one-at-a-time tornado, two-way tables, break-even values, and a side-by-side comparison of every cluster you build.
Building inputs carry a status everywhere: **source**, **derived**, **assumption**, **override**, **missing**. Sourced: building attributes,
the EMSD district cooling tariff, each district's electricity tariff and grid emission factor (CLP or HK Electric, 2026) and equipment lives
(ASHRAE). Judgement: loads, hours, COPs, costs and finance settings, kept apart on the Inputs tab (full list in `docs/SOURCES.md`).
Tabs: Map and selection, Cluster assessment, Compare options, Compare districts, Sensitivity, Inputs, Data and assumptions.
Districts: Central and Western, Kwun Tong and Sha Tin for comparison; Kai Tak as the reference area where district cooling already exists.
More of the 18 districts can be added with one config entry and one preparation run each.

## Run locally (Windows)
    python -m pip install -r requirements.txt
    python -m streamlit run app.py
Tests: `python -m unittest -v` (about 80 tests; `test_app_smoke.py` drives the whole interface headlessly).

## Files
| file | role |
|---|---|
| `app.py` | thin router: sidebar, step bar, five tabs |
| `ui/` | interface: `style` (design system), `state`, `inputs`, `controls` (sidebar, step bar), `explorer` (map and selection), `assess`, `scenarios` (compare options, sensitivity), `data_tab` |
| `compare.py` | Compare districts: matched clusters per district, typical cluster, distribution |
| `glossary.py` | plain-language explanations behind the ⓘ buttons |
| `sources.py` | published vs judgement classification of every input (see `docs/SOURCES.md`) |
| `config/utilities.json` | power company per district, 2026 tariffs and emission factors with sources |
| `verdict.py` | plain-language verdict and "best on each row" for the option cards |
| `lifecycle.py` | three-scenario lifecycle model, NPV, payback, tornado, two-way, break-even |
| `model.py` | assumptions (with sources) and the original annual model (kept for regression tests) |
| `clusters.py` | selection (click, polygon, table), per-use defaults, aggregates, proximity, DCS coverage, exports |
| `buildings.py` | building record: source / derived / assumption / override layers |
| `districts.py` | loads prepared district packages and re-verifies SHA-256 fingerprints |
| `geometry.py` | planar geometry in EPSG:2326 metres (edge-to-edge distance, spanning tree, hull) |
| `overlays.py` | coordinate conversion, boundaries, DCS area, Kai Tak OZP zones, polygon import |
| `tools/prepare_districts.py` | builds `data/districts/<id>` from the full HK-BFETD files (run once) |
| `config/districts.json` | district list (add districts here, no code change) |
| `config/dcs_systems.json` | DCS systems, status and EMSD tariffs with source |
| `config/areas/` | Kai Tak OZP S/K22/9 boundary and zones (Planning Department GIS data) |
| `docs/` | `DATA_PREP.md`, `DEPLOY.md`, `BRIEF_COVERAGE.md`, `DATA_AUDIT.md`, `AI_LOG.md` |

## Data and licences
HK-BFETD v1.1 is CC BY 4.0 (credit the dataset authors). Footprints derive from Lands Department data whose licence has not
been confirmed: keep the repository **private** until checked. District boundaries: Home Affairs Department (data.gov.hk).
Kai Tak OZP: Planning Department statutory planning GIS data (see `GeoJSON_S_K22_9/.../Terms and Conditions of Use`).
DCS tariffs: EMSD "District Cooling Services Charges" (accessed 21 Nov 2026).
