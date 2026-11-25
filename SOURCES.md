# Sources and judgement calls for every model input

Generated from `sources.py`: the same notes appear behind each input's ⓘ icon on the Inputs tab. Accessed 25 Nov 2026.

**Conservatism rule.** Costs of the shared options (pipe network, connections, shared-plant maintenance) are set at 1.5× the evidence-based base value; costs of keeping individual plants are kept at base, because overstating them would favour sharing. The aim is fewer, stronger shared-cooling candidates rather than false positives.

## Published values (change only with better data)

| Input | Basis | Source |
|---|---|---|
| `tariff` | 2026 average net tariff: CLP HK$1.406/kWh, HK Electric HK$1.633/kWh. | https://www.clp.com.hk/content/dam/clp-group/channels/media/document/2025/20251118_en.pdf |
| `emission_factor` | CO₂e per kWh sold, 2025: CLP 0.34, HK Electric 0.59. | https://sustainability.clpgroup.com/en/2025/esg-data-hub |
| `equipment_life` | ASHRAE median service life: reciprocating chillers 20 yrs, centrifugal 23. | https://handbook.ashrae.org/Handbooks/A15/IP/A15_CH37/a15_ch37_ip.aspx |
| `plant_life` | ASHRAE survival analysis: centrifugal chillers >25 yrs. | https://handbook.ashrae.org/Handbooks/A15/IP/A15_CH37/a15_ch37_ip.aspx |
| `dcs_capacity_rate` | EMSD published DCS charges (Cap. 624); capacity rate follows the Composite CPI. | https://www.emsd.gov.hk/en/energy_efficiency/DCS_in_HK/charges/index.html |
| `dcs_consumption_rate` | EMSD published DCS charges (Cap. 624); capacity rate follows the Composite CPI. | https://www.emsd.gov.hk/en/energy_efficiency/DCS_in_HK/charges/index.html |

Power company by district (`config/utilities.json`): Central and Western = HK Electric; Kai Tak, Kwun Tong, Sha Tin = CLP.

## Judgement and risk (benchmarks bound them)

| Input | Default | Basis | Source |
|---|---|---|---|
| `discount_rate` | 0.04 | Method: owner's real required return; 3–8% is typical. Higher favours low up-front cost. | method (no single source) |
| `analysis_years` | 25 | Method: about one central-plant life (ASHRAE >25 yrs). | https://handbook.ashrae.org/Handbooks/A15/IP/A15_CH37/a15_ch37_ip.aspx |
| `elec_escalation` | 0.0 | Method: real change beyond inflation. CLP moved −2.6% (Jan 2026) then +2.9% (Jul 2026). | https://www.clpgroup.com/content/dam/clp-group/channels/media/document/2026/20260626_en.pdf.coredownload.pdf |
| `dcs_capacity_escalation` | 0.0 | Method: rate follows the Composite CPI, so ≈0% in real terms. | https://www.emsd.gov.hk/en/energy_efficiency/DCS_in_HK/charges/index.html |
| `demand_scale` | 1.0 | Method: stress test on the per-use placeholder loads; try 70–130%. | method (no single source) |
| `cop_existing` | 3.2 | BEC 2021 minimum for NEW air-cooled chillers is 2.9–3.1; aged plant is lower. | https://www.emsd.gov.hk/beeo/en/pee/BEC_2021.pdf |
| `existing_remaining_life` | 5 | Method: years until today's chillers must be replaced; needs a site survey (0–15). | method (no single source) |
| `cop_upgrade` | 4.2 | Between BEC 2024 minimums: air-cooled screw 3.2, water-cooled screw 5.1–5.3 (assumes a mix). | https://emsd.gov.hk/beeo/en/pee/BEC2021vsBEC2024.pdf |
| `upgrade_capex_kw` | 4000.0 | Base, not uplifted. US plant-level HK$3,300–4,000/kW (FPL); chiller-only HK$1,240–2,770/kW (EIA 2023); plus a Hong Kong retrofit premium. Overstating it would favour sharing. | https://www.eia.gov/analysis/studies/buildings/equipcosts/pdf/appendix-a.pdf |
| `maint_existing_kw` | 120.0 | Base, not uplifted. HK chiller contracts ≈HK$37/kW/yr in 2005 (PolyU), ≈60–65 today; EIA 2023: HK$44–111. | https://ira.lib.polyu.edu.hk/bitstream/10397/28317/1/a0861-n02_13-Chiller_maint_cost_6Aug07.pdf |
| `maint_upgrade_kw` | 80.0 | Base, not uplifted. Newer plant: lower end of HK$44–111/kW/yr (EIA 2023). | https://www.eia.gov/analysis/studies/buildings/equipcosts/pdf/appendix-a.pdf |
| `cop_central` | 5.2 | Code minimum for large water-cooled CHILLERS is 5.9 (BEC 2021); the whole plant, with towers and pumps, is lower. | https://www.emsd.gov.hk/beeo/en/pee/BEC_2021.pdf |
| `diversity` | 0.8 | Method: buildings' peaks do not coincide; 0.7–0.9 for mixed commercial clusters. | method (no single source) |
| `central_capex_kw` | 4200 | Plant only (pipes and connections are priced separately). Below the Kai Tak public-sector cross-checks: ≈HK$13,750/kW all-in for 45CG and ≈HK$9,040/kW for 50CG plant E&M, which include seawater systems and standby. | https://www.legco.gov.hk/yr18-19/english/fc/pwsc/papers/p19-01e.pdf |
| `network_cost_m` | 75000.0 | 1.5 × base HK$50,000 per route-metre. Kai Tak DCS pipe outturns: HK$32,000–173,000/m. | https://www.aud.gov.hk/pdf_e/e77ch02.pdf |
| `cmcs_route_factor` | 1.3 | Method: real routes are longer than straight lines; 1.2–1.6. | method (no single source) |
| `connection_cost` | 4500000.0 | Minimum per building = 1.5 × base HK$3M; the per-kW rate applies when it is higher. | https://www.legco.gov.hk/yr18-19/english/fc/pwsc/papers/p19-01e.pdf |
| `connection_cost_kw` | 3000.0 | 1.5 × base HK$2,000/kW. Kai Tak 50CG connection facilities ≈HK$2,235/kW. | https://www.legco.gov.hk/yr18-19/english/fc/pwsc/papers/p19-01e.pdf |
| `pump_share` | 0.08 | Method: network pumping energy; 5–10% of plant electricity. | method (no single source) |
| `network_loss` | 0.04 | Method: cooling lost in distribution; 2–5%. | method (no single source) |
| `maint_central_plant_kw` | 225.0 | 1.5 × base HK$150. Kai Tak DCS operator payment ≈HK$207/kW/yr on design capacity (Audit Commission 2021). | https://www.aud.gov.hk/pdf_e/e77ch02.pdf |
| `maint_network_pct` | 0.01 | Method: 0.5–2% of network cost per year. | method (no single source) |
| `network_life` | 50 | Method: buried pipe life, 40–60 yrs. | method (no single source) |
| `dcs_contract_factor` | 1.0 | Method: contract below peak lowers the bill but overrun is charged at 1.1 × the rate. | https://www.legco.gov.hk/yr13-14/english/panels/ea/papers/ea0717cb1-1785-1-e.pdf |
| `dcs_connection_cost` | 1000000 | Owner pays the substation room and secondary works; government funds the heat exchangers at Kai Tak. | https://www.aud.gov.hk/pdf_e/e77ch02.pdf |
| `dcs_building_capex_kw` | 400 | Method: secondary-side changes per kW; no public unit rate found. | method (no single source) |
| `dcs_maint_kw` | 30 | Method: building-side DCS equipment only; no public benchmark found. | method (no single source) |
| `dcs_aux_kwh_per_kwh` | 0.02 | Method: building pumping, 0.01–0.03 kWh per kWh of cooling. | method (no single source) |
| `dcs_plant_cop` | 4.9 | EMSD: DCS uses 35% less electricity than air-cooled systems → 3.2 / 0.65 ≈ 4.9. Emissions only. | https://emsd.gov.hk/en/energy_efficiency/district_cooling_system/introduction/index.html |
| `dcs_building_life` | 30 | ASHRAE service lives for heat exchangers and pumps: 20–30 yrs. | https://handbook.ashrae.org/Handbooks/A15/IP/A15_CH37/a15_ch37_ip.aspx |
| `max_m` |  | Method: screening distance for a shared network; edge to edge. | method (no single source) |

Per-use cooling loads (W/m²), full-load hours and cooled share (`clusters.USE_DEFAULTS`) are judgement too: illustrative planning densities.

## Cost benchmarks behind the four researched inputs (25 Nov 2026)

| Input | Base | App default | Evidence |
|---|---|---|---|
| Replacement chiller, installed | HK$4,000/kW | HK$4,000/kW (not uplifted) | EIA 2023 chiller-only US$560–1,250/ton (HK$1,240–2,770/kW); FPL plant-level US$1,500–1,800/ton (HK$3,300–4,000/kW); US DOE schools package ≈HK$8,000/kW (small units) |
| Pipe network | HK$50,000/route-m | HK$75,000/m (1.5×) | Kai Tak DCS: Contract A HK$138.1M for ≈800 m (≈HK$172,600/m, Audit Commission 2021); 50CG HK$744.5M for ≈23 km (≈HK$32,400/m, LegCo PWSC(2019-20)1); US US$500–1,250/ft trench |
| Connection | HK$2,000/kW, min HK$3M | HK$3,000/kW, min HK$4.5M (1.5×) | Kai Tak 50CG connection facilities HK$397.8M for ≈178 MW (≈HK$2,235/kW); IEA DHC Connection Handbook; Energy Transition Model ≈€152/kW + €7,563 |
| Maintenance, today's plant | HK$120/kW/yr | 120 (not uplifted) | Lai, Yik & Chan (PolyU), 40 HK contracts 2005: mean HK$129/TR/yr ≈HK$37/kW/yr; EIA 2023 HK$44–111/kW/yr |
| Maintenance, replaced plant | HK$80/kW/yr | 80 (not uplifted) | as above, lower end for new plant |
| Maintenance, shared plant | HK$150/kW/yr | HK$225/kW/yr (1.5×) | Kai Tak DCS operator payment HK$58.7M in 2020-21 ≈HK$207/kW/yr on 284 MW design capacity (Audit Commission 2021) |

Exchange rates: 1 USD = 7.8 HKD; 1 EUR = 8.5; 1 GBP = 10; 1 AED = 2.12. 1 RT = 3.517 kW. US figures are 2022 dollars (≈+10–15% to 2026, estimate).
No published Hong Kong chiller replacement with both cost and capacity was found; the chiller figure rests on US data plus a retrofit premium.

## Building features

| Feature | Status | Origin |
|---|---|---|
| Footprint polygon and area | Source | HK-BFETD v1.1 (from Lands Department building outlines) |
| Number of storeys, height | Source | HK-BFETD v1.1 (origin of the field not documented in the files) |
| Main class and use mix (shares) | Source | HK-BFETD v1.1 (UBEM classification; what the shares measure is not documented) |
| Registered GFA | Source (rare) | Lands Department registered GFA via HK-BFETD: 11 of 29,387 prepared buildings |
| BDBIAR year | Source | Buildings Department approval year via HK-BFETD; NOT plant age |
| GFA when not registered | Estimate | footprint × storeys (overstates large low-rise complexes) |
| Cooled share, peak load (W/m²), full-load hours | Assumption | per-use placeholders, share-weighted for mixed buildings; editable |
| Peak cooling (kW), annual cooling (kWh) | Estimate | cooled area × W/m²; × full-load hours |
| Existing chiller COP | Assumption | one value for all buildings unless set per building |
| Inside a DCS service area | Estimate | building centre inside the Kai Tak OZP boundary (approximation of the service area) |
