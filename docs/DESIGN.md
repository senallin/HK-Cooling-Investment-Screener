# Design system
Adopted from the design pass in the parallel copy (`Documents\hk-cooling-screener`, 21 Nov 2026) and applied to this version's data and
lifecycle model. Tokens live in `ui/style.py` (CSS and Plotly) and `.streamlit/config.toml` (Streamlit widgets). Change them there, not in tabs.

## Colour ("Trust & Clarity")
| Role | Colour | Used for |
|---|---|---|
| Primary | Teal `#006D77` | buttons, sliders, selection outline, cluster boundary, shared plant |
| Ink | Slate `#2C3E50` | headings, key numbers |
| Text / background | `#333333` on `#F5F5F5`, cards `#FFFFFF` | body |
| Positive | Green `#4CAF50` | best value on option cards ("Lowest lifecycle cost" tag, green dots) |
| Warning | Orange `#FF9800` | distance check, changed-input chips, data warnings |
| Error | Red `#C62828` | hard errors only |

Options: Keep individual plants grey `#9AA5AB` · Shared plant (private) teal `#006D77` · Public district cooling purple `#7B5EA7`
(also the DCS service-area outline on the map). Sourced inputs (EMSD tariff) get a green chip.

Map: building types use a muted palette so the teal selection outline and orange warning outline stay the strongest marks.
"Colour buildings by: Peak cooling (est.)" switches to a five-step blue scale (quantiles of the district; grey = no cooling inputs).

## Type
Inter for interface text; IBM Plex Mono (tabular figures) for numbers: metric values, option cards, building card, chart axes.
Loaded from Google Fonts; system fonts are the fallback offline.

## Words
One name per option everywhere (verdict, cards, tables, charts, legends: `verdict.NAMES`) and one status vocabulary:
Source, Estimate, Assumption, Your value, Missing.

## Interaction
* Sidebar: district and cluster tools only (pick, new, delete, rename, clear, find candidates, export). Step bar shows District → Cluster → Result.
* Map tab is a split view: map, distance check and building table on the left; live "Cluster at a glance" card and the building card on the right.
* Model inputs are on the Compare options tab, grouped by option; sliders for values to explore, number boxes for costs. Changed inputs are always listed as chips.
* Selected buildings are drawn in a separate map layer (`feature_group_to_add`) so clicking does not reset the map view.

## Differences from the parallel copy
* Clusters are named and kept per district (instead of one free selection plus saved clusters), so clusters can be compared across districts.
* The fourth "Public district cooling" card is a real option with the EMSD tariff, NPV and discounted payback, not a greyed placeholder.
* Map tiles: OpenStreetMap (CartoDB tiles now need an API key). Empty map layers are never added (folium 1.0 raises on an empty layer with a tooltip,
  which crashed the Map tab of the parallel copy).
