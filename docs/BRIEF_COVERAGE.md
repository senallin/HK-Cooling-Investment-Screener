# Brief coverage tracker (final, 21 Nov 2026)
Status: DONE = implemented and tested here (unit tests and/or headless app test, plus a browser check where noted);
LIMITED = done with a stated limitation; NOT IN DATA = cannot be sourced from the supplied data.

| Brief item | Status | Where / notes |
|---|---|---|
| Hong Kong > District > Cluster > Buildings | DONE | sidebar district + cluster selectors; breadcrumb in header |
| Real buildings replace fictional sample | DONE | 4 district packages built from the full HK-BFETD files (899 / 7,076 / 4,783 / 16,629 buildings) |
| Additional districts without code change | DONE | `config/districts.json` + `prepare_districts.py run --only <id>` (tested) |
| Preserve source attributes and geometry; never overwrite originals | DONE | byte-identical features, SHA-256 before/after, re-verified at every app load |
| Source / derived / assumption / override separation | DONE | colour badges in table, details panel and cluster editor |
| Primary / secondary use and mix | DONE | parsed for every building; drives per-use default loads (share-weighted) |
| Registered GFA vs estimate | DONE | registered if present (11 of 29,387 buildings), else derived footprint × floors, labelled |
| District selector, zoom (district / cluster) | DONE | browser-checked |
| Cluster selector, create, rename, delete, starter suggestion | DONE | sidebar |
| Map footprints, hover info, legend, highlight, cluster boundary | DONE | folium; red outline = in cluster; dashed convex hull; browser-checked |
| Click / draw / table selection, synchronised | DONE | one cluster state; map click and rectangle draw browser-checked; table ticks tested headlessly |
| Existing DCS overlay | LIMITED | Kai Tak service area shown as the OZP boundary (labelled approximation); pipe network not in the data. Tung Chung East and Kwu Tung North listed with status and tariff (outside configured districts) |
| 300 m proximity warning, distances | DONE | edge-to-edge, warning not block; pairs drawn on the map; limit editable; fast pruned algorithm tested against exact |
| Building table: filter, sort, search, add/remove, CSV export | DONE | plus cluster CSV and GeoJSON export |
| Information panel, editable assumptions, reset | DONE | per-building override editor, sidebar assumptions, reset buttons |
| Three scenarios, same cluster | DONE | Individual / CMCS / DCS in `lifecycle.py` |
| Public DCS tariffs and status | DONE | EMSD 2025/26 and 2026/27 rates for Kai Tak, Tung Chung East, Kwu Tung North (`config/dcs_systems.json`) |
| NPV, discounting, lifetime, payback | DONE | real discount rate, asset lives with replacement and residual value, simple and discounted payback, levelised cost |
| Sensitivity: OAT tornado, two-way, NPV/payback | DONE | plus break-even values |
| Multi-cluster comparison | DONE | across districts; table, chart, CSV |
| Scribble Maps | LIMITED | GeoJSON import (adds buildings inside a drawn polygon) and GeoJSON export; no live API link (no public API verified) |
| Tests, deployment doc | DONE | 62 tests; `docs/DEPLOY.md` |
| Kai Tak OZP zones | DONE (extra) | optional map layer from S/K22/9 ZONE data |
| Sourced cooling loads, plant age, existing COP | NOT IN DATA | illustrative, labelled assumptions; editable per building |
