# AI-use log (for assignment appendix)
**Tool:** Claude (Anthropic). **Date:** 20 Nov 2026.

## Prompt
Brief to act as senior full-stack developer and product designer and build, test and package a Streamlit "HK Building Cooling Investment Screener" comparing retain, upgrade and central cooling, with editable assumptions, sample data and deployment files.

## Key decisions
- Separated pure-Python calculations (`model.py`) from the interface so the maths is deterministic and testable without Streamlit.
- All default values are marked illustrative; no Hong Kong statistics are asserted. The user must source real tariff, emission factor and cost data and cite it.
- Simple payback only (as briefed); documented limits: no discounting, inflation or replacement costs.
- Central plant sized with a diversity factor; network loss and pumping energy modelled explicitly.
- Sensitivity: one-at-a-time ±20% on the central scheme's annual saving.
- Design: cool grey and teal palette, Newsreader and Public Sans, the headline verdict as the focal element.

## Verification
- 8 unit tests (hand calculation, invalid inputs, no-saving payback, determinism, sensitivity) pass.
- Sandbox had no internet, so Streamlit could not be installed: the interface was compile-checked only and has NOT been run or visually inspected. Do this before submission.

## Upgrade, stages 0-1 (branch gis-upgrade)
- Approved plan: GIS upgrade in small stages; baseline tagged v1-baseline. Decisions: distance limit is a warning not a block; edge-to-edge distance; per-building existing COP with regression tests; no fabricated Kai Tak data (synthetic geometry only, labelled); maintenance made comparable.
- Maintenance now HK$/kW installed capacity/yr for all scenarios, plus a % of network capex for Central. Defaults are illustrative; this changes Central payback in the sample from 14.8 to 12.3 years.
- Building records separate source / derived / assumption / override. Overrides never modify source records.

## Data preparation script (Phase 2)
- User's datasets are local; Claude never receives originals. Claude wrote data_prep/prepare_kaitak_data.py (standard library only) for the user to run locally, with SHA-256 before/after, read-only access, output outside the input folder, and no network code.
- Workflow chosen with the user: the Excel list (HK UBEM Kai Tak.xlsx) is the building reference; the match key is discovered from the data and verified by agreement on shared fields, not assumed.
- Tested on SYNTHETIC data only (data_prep/test_prepare_kaitak.py, 5 tests) and on an 853 MB synthetic GeoJSON (29 s, 215 MB peak memory, flat as file size grew).
- Bugs found by testing and fixed: (1) a many-records-per-value column ('Storeys') was accepted as a key when no true key existed; now rejected. (2) GeoPackage link was chosen by shape agreement and could pick the row-number column; now row-number keys are excluded and identifier evidence ranks first.
- Not yet tested: real data, Windows execution of the .bat launcher.

## Stage 2a: data integration (uploaded extracts)
- User uploaded the schema pack and the two extracts (not the reports folder). Analysis found 176 matched buildings (workbook has 195), perfect CSV/GeoJSON agreement, CRS EPSG:2326, and name-based selection pulling in buildings far from Kai Tak (21 flagged).
- Added kaitak_data.py (join + provenance), geometry.py (edge-to-edge distance in metres; 300 m check returns a warning, never a block), manifest of extract fingerprints, 7 new tests on the real extracts (26 tests total pass).
- Not done: map UI (no Streamlit/Folium/pyproj in the build sandbox, so it cannot be run here), WGS84 conversion, selection-state sync tests.

## Milestone 1: district preparation
- `tools/prepare_districts.py` assigns buildings to areas by footprint centroid from the full HK-BFETD files, with validation
  and fingerprints; `districts.py` loads packages. Kai Tak was a provisional rectangle pending an official boundary.

## Milestones 2–5 (21 Nov 2026, Claude Code on the user's computer)
- Run locally on the user's machine this time (Python 3.15.2), so the real data and a real browser could be used.
- Data: added an Esri JSON reader (orientation rule checked against the file's own Shape_Area) and used the Planning Department
  OZP S/K22/9 boundary for Kai Tak, the HAD 18-district boundary for the others. Fixed the config: the boundary file names
  districts "Kwun Tong District", not "Kwun Tong". All four packages passed; Kai Tak now 899 buildings (176 by name earlier).
- Research: EMSD DCS charges page read for the tariff (Kai Tak 2026/27: HK$140.88 per kW refrigeration per month,
  HK$0.2387 per kWh refrigeration). A search result claiming a "35% DCS saving" was not attributable to EMSD and was not used.
- Model: new `lifecycle.py` (Individual / CMCS / DCS, replacements, residual value, discounting, payback, tornado, two-way,
  break-even). The original `model.run` is unchanged and its regression tests still pass.
- Interface: map (folium) with click and draw selection, cluster management, table, overrides, results, sensitivity,
  comparison, method. Problems found by running it and fixed: CartoDB tiles now need an API key (switched to OpenStreetMap);
  Leaflet inside hidden `st.tabs` initialises at zoom 0 (replaced tabs with a view switcher, which also renders only one view);
  Streamlit "magic" broke on conditional-expression statements; zoom-to-cluster ignored large footprints; drawn shapes added
  hidden classes.
- Verification: 62 unit and headless tests pass; map click, rectangle draw, highlight, zoom and the Results view checked in a browser.
- Design merge (same day): a parallel chat had redesigned an older copy (`Documents\hk-cooling-screener`) that still used the 176-building
  extract and the simple-payback model, and whose Map tab crashed (folium 1.0 rejects an empty layer with a tooltip). Its design system and
  interaction patterns (palette, Inter/Plex Mono, step bar, sidebar for district and cluster only, split map view with live card and building
  card, inputs and chips on the Compare tab, option cards, Cluster assessment tab, candidate search) were re-implemented in `ui/` on this
  version's data and lifecycle model; its files were not copied. Previous interface kept in `_backup_before_design_merge/`. 68 tests pass;
  map, suggestion, live card and option cards checked in the browser.
- Judgement calls the user should review: per-use default loads and hours, DCS contract capacity = building peak, DCS plant
  COP for attributed emissions, the OZP boundary as a stand-in for the DCS service area.

## Final day (25 Nov 2026, Claude in a cowork chat, editing the project folder through the desktop app)
- Usability review against the Option 6 brief and rubric; top-5 list: publish, fix the misleading demo, sourced figures, a district comparison,
  plain-language help. Hosting: Streamlit Community Cloud from a private GitHub repository with a public app (two separate settings).
- Glossary: `glossary.py` (26 terms) and ⓘ buttons (`st.popover`) next to every financial result; full table on the Data tab.
- Demo fix: the suggested cluster was 94% one building (Kai Tak Cruise Terminal, GFA estimated as footprint × storeys). Suggestions now skip
  groups where one building carries more than half the demand (`clusters.dominant_share`).
- Kai Tak connection rule added with its LegCo sources: private non-domestic developments must connect to the Kai Tak DCS (land-sale conditions).
- New Compare districts tab (`compare.py`, `ui/districts_tab.py`): same cluster rule in every district (n buildings, max distance, floor range,
  types); non-overlapping clusters from seeds in a fixed pseudo-random order; typical cluster = closest to the median saving per MW; box plot and
  "share of clusters where it pays". Kai Tak excluded by default as the reference case.
- Bugs found by running it: a district with a missing manifest crashed the tab (now skipped with a warning); one file write landed stale and
  had to be repeated (sizes are now checked after every write); a 13-column table was transposed to fit.
- Sha Tin restored: its 38 MB GeoJSON is stored gzipped (5.3 MB) and verified after decompression.
- Research (web, 25 Nov 2026): CLP and HK Electric 2026 average net tariffs; CLP Power HK 2025 and HK Electric 2025 carbon intensity;
  Building Energy Code minimum chiller COPs; ASHRAE service lives; EMSD's own statement of 35% / 20% DCS electricity savings (this corrects the
  earlier note above: the claim IS on EMSD's site; it is used only as a benchmark for the DCS plant COP, not as a result).
- Power company by district (`config/utilities.json`): Central and Western is HK Electric, the others CLP. Inputs are now split on a new
  Inputs tab into Published values and Judgement and risk (`sources.py`, `docs/SOURCES.md`).
- Judgement values still to be chosen by the user are listed in `docs/SOURCES.md`.
- Cost research (Claude research task, 25 Nov 2026): benchmarks for chiller replacement, pipe network, connection and maintenance
  (EIA 2023, US DOE, FPL, PolyU 2005 Hong Kong contracts, Audit Commission Report No. 77 Ch. 2, LegCo PWSC papers on Kai Tak 45CG/50CG).
  The user chose a conservative rule: shared-option costs at 1.5x base, individual-option costs at base. New defaults in `sources.APP_DEFAULTS`;
  connection cost is now capacity-scaled (HK$/kW with a per-building minimum, `connection_cost_kw` in `lifecycle.py`; the original model is
  unchanged). Each input on the Inputs tab has an ⓘ icon with a short note and its source link.
- Effect: with these costs, no matched 6-building cluster pays with a shared plant in any district (it was 4–20% before); even at base
  (1.0x) only 2% in Central and Western. The connection cost per kW is the largest single driver.
