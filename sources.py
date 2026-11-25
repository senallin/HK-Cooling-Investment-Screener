"""Where every model input comes from, and the app's default values.

PUBLISHED  values stated by an authority (utility, EMSD, building code, ASHRAE). A manager should change them only with better data.
JUDGEMENT  values that depend on the project, the owner or a view of the future. Benchmarks bound them.
Conservatism rule (25 Nov 2026): costs of the SHARED options (pipes, connections, shared-plant maintenance) are set at 1.5x the evidence-based
base value; costs of the INDIVIDUAL option are kept at base, because overstating them would favour sharing. The aim is fewer, stronger
shared-cooling candidates rather than false positives.
HELP gives the short text and link behind each input's ⓘ icon in the Inputs tab. Pure Python; read by ui/inputs.py, ui/data_tab.py, docs/SOURCES.md."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UTIL = json.loads((ROOT / "config" / "utilities.json").read_text(encoding="utf-8"))


def supplier_for(district_id):
    return UTIL["suppliers"][UTIL["district_supplier"].get(district_id, UTIL["default_supplier"])]


def supplier_code(district_id): return UTIL["district_supplier"].get(district_id, UTIL["default_supplier"])


# ------------------------------------------------------------------------------------------------ app defaults
# Applied on top of model.Assumptions() by the app (model.py keeps its original defaults for its regression tests).
APP_DEFAULTS = dict(
    upgrade_capex_kw=4000.0,        # base, not uplifted (individual option)
    network_cost_m=75000.0,         # 1.5 x HK$50,000 per route-metre
    connection_cost=4.5e6,          # minimum per building = 1.5 x HK$3M
    connection_cost_kw=3000.0,      # 1.5 x HK$2,000 per kW of building peak
    maint_existing_kw=120.0,        # base, not uplifted (individual option)
    maint_upgrade_kw=80.0,          # base, not uplifted (individual option)
    maint_central_plant_kw=225.0,   # 1.5 x HK$150
    dcs_plant_cop=4.9,              # EMSD: DCS uses 35% less electricity than air-cooled (3.2 / 0.65)
)

U = dict(  # source links
    clp="https://www.clp.com.hk/content/dam/clp-group/channels/media/document/2025/20251118_en.pdf",
    hke="https://www.hkelectric.com/documents/en/MediaResources/PressReleases/Documents/20251118_pre_TR%202026_final_website.pdf",
    clp_ef="https://sustainability.clpgroup.com/en/2025/esg-data-hub",
    clp_jul="https://www.clpgroup.com/content/dam/clp-group/channels/media/document/2026/20260626_en.pdf.coredownload.pdf",
    emsd_tariff="https://www.emsd.gov.hk/en/energy_efficiency/DCS_in_HK/charges/index.html",
    emsd_dcs="https://emsd.gov.hk/en/energy_efficiency/district_cooling_system/introduction/index.html",
    bec21="https://www.emsd.gov.hk/beeo/en/pee/BEC_2021.pdf",
    bec24="https://emsd.gov.hk/beeo/en/pee/BEC2021vsBEC2024.pdf",
    ashrae="https://handbook.ashrae.org/Handbooks/A15/IP/A15_CH37/a15_ch37_ip.aspx",
    eia="https://www.eia.gov/analysis/studies/buildings/equipcosts/pdf/appendix-a.pdf",
    fpl="https://www.fpl.com/content/dam/fplgp/us/en/business/save/programs/pdf/water-cooled-chillers-primer.pdf",
    polyu="https://ira.lib.polyu.edu.hk/bitstream/10397/28317/1/a0861-n02_13-Chiller_maint_cost_6Aug07.pdf",
    audit="https://www.aud.gov.hk/pdf_e/e77ch02.pdf",
    legco_50cg="https://www.legco.gov.hk/yr18-19/english/fc/pwsc/papers/p19-01e.pdf",
    legco_45cg="https://www.legco.gov.hk/yr15-16/english/fc/pwsc/papers/p15-62e.pdf",
    legco_2014="https://www.legco.gov.hk/yr13-14/english/panels/ea/papers/ea0717cb1-1785-1-e.pdf",
)

# field -> (short note shown behind the ⓘ icon, link or None). Kept to one or two lines; longer only where the chosen value departs from the benchmark.
HELP = {
    "tariff": ("2026 average net tariff: CLP HK$1.406/kWh, HK Electric HK$1.633/kWh.", U["clp"]),
    "emission_factor": ("CO₂e per kWh sold, 2025: CLP 0.34, HK Electric 0.59.", U["clp_ef"]),
    "equipment_life": ("ASHRAE median service life: reciprocating chillers 20 yrs, centrifugal 23.", U["ashrae"]),
    "plant_life": ("ASHRAE survival analysis: centrifugal chillers >25 yrs.", U["ashrae"]),
    "dcs_tariff": ("EMSD published DCS charges (Cap. 624); capacity rate follows the Composite CPI.", U["emsd_tariff"]),
    "discount_rate": ("Method: owner's real required return; 3–8% is typical. Higher favours low up-front cost.", None),
    "analysis_years": ("Method: about one central-plant life (ASHRAE >25 yrs).", U["ashrae"]),
    "elec_escalation": ("Method: real change beyond inflation. CLP moved −2.6% (Jan 2026) then +2.9% (Jul 2026).", U["clp_jul"]),
    "dcs_capacity_escalation": ("Method: rate follows the Composite CPI, so ≈0% in real terms.", U["emsd_tariff"]),
    "demand_scale": ("Method: stress test on the per-use placeholder loads; try 70–130%.", None),
    "cop_existing": ("BEC 2021 minimum for NEW air-cooled chillers is 2.9–3.1; aged plant is lower.", U["bec21"]),
    "existing_remaining_life": ("Method: years until today's chillers must be replaced; needs a site survey (0–15).", None),
    "cop_upgrade": ("Between BEC 2024 minimums: air-cooled screw 3.2, water-cooled screw 5.1–5.3 (assumes a mix).", U["bec24"]),
    "upgrade_capex_kw": ("Base, not uplifted. US plant-level HK$3,300–4,000/kW (FPL); chiller-only HK$1,240–2,770/kW (EIA 2023); "
                         "plus a Hong Kong retrofit premium. Overstating it would favour sharing.", U["eia"]),
    "maint_existing_kw": ("Base, not uplifted. HK chiller contracts ≈HK$37/kW/yr in 2005 (PolyU), ≈60–65 today; EIA 2023: HK$44–111.", U["polyu"]),
    "maint_upgrade_kw": ("Base, not uplifted. Newer plant: lower end of HK$44–111/kW/yr (EIA 2023).", U["eia"]),
    "cop_central": ("Code minimum for large water-cooled CHILLERS is 5.9 (BEC 2021); the whole plant, with towers and pumps, is lower.", U["bec21"]),
    "diversity": ("Method: buildings' peaks do not coincide; 0.7–0.9 for mixed commercial clusters.", None),
    "central_capex_kw": ("Plant only (pipes and connections are priced separately). Below the Kai Tak public-sector cross-checks: "
                         "≈HK$13,750/kW all-in for 45CG and ≈HK$9,040/kW for 50CG plant E&M, which include seawater systems and standby.",
                         U["legco_50cg"]),
    "network_cost_m": ("1.5 × base HK$50,000 per route-metre. Kai Tak DCS pipe outturns: HK$32,000–173,000/m.", U["audit"]),
    "cmcs_route_factor": ("Method: real routes are longer than straight lines; 1.2–1.6.", None),
    "connection_cost": ("Minimum per building = 1.5 × base HK$3M; the per-kW rate applies when it is higher.", U["legco_50cg"]),
    "connection_cost_kw": ("1.5 × base HK$2,000/kW. Kai Tak 50CG connection facilities ≈HK$2,235/kW.", U["legco_50cg"]),
    "pump_share": ("Method: network pumping energy; 5–10% of plant electricity.", None),
    "network_loss": ("Method: cooling lost in distribution; 2–5%.", None),
    "maint_central_plant_kw": ("1.5 × base HK$150. Kai Tak DCS operator payment ≈HK$207/kW/yr on design capacity (Audit Commission 2021).", U["audit"]),
    "maint_network_pct": ("Method: 0.5–2% of network cost per year.", None),
    "network_life": ("Method: buried pipe life, 40–60 yrs.", None),
    "dcs_contract_factor": ("Method: contract below peak lowers the bill but overrun is charged at 1.1 × the rate.", U["legco_2014"]),
    "dcs_connection_cost": ("Owner pays the substation room and secondary works; government funds the heat exchangers at Kai Tak.", U["audit"]),
    "dcs_building_capex_kw": ("Method: secondary-side changes per kW; no public unit rate found.", None),
    "dcs_maint_kw": ("Method: building-side DCS equipment only; no public benchmark found.", None),
    "dcs_aux_kwh_per_kwh": ("Method: building pumping, 0.01–0.03 kWh per kWh of cooling.", None),
    "dcs_plant_cop": ("EMSD: DCS uses 35% less electricity than air-cooled systems → 3.2 / 0.65 ≈ 4.9. Emissions only.", U["emsd_dcs"]),
    "dcs_building_life": ("ASHRAE service lives for heat exchangers and pumps: 20–30 yrs.", U["ashrae"]),
    "max_m": ("Method: screening distance for a shared network; edge to edge.", None),
}


def help_md(field, extra=None):
    """Markdown for a widget's ⓘ tooltip."""
    if field not in HELP: return extra
    text, url = HELP[field]
    return text + (f" [Source]({url})" if url else "") + (f"\n\n{extra}" if extra else "")


PUBLISHED_FIELDS = ("tariff", "emission_factor", "equipment_life", "plant_life", "dcs_capacity_rate", "dcs_consumption_rate")
PUBLISHED = {f: HELP.get(f, HELP["dcs_tariff"]) for f in PUBLISHED_FIELDS}
JUDGEMENT = {f: v for f, v in HELP.items() if f not in PUBLISHED_FIELDS and f != "dcs_tariff"}

# Building attributes and how each is obtained (for the docs and the Data tab)
BUILDING_FEATURES = [
    ("Footprint polygon and area", "Source", "HK-BFETD v1.1 (from Lands Department building outlines)"),
    ("Number of storeys, height", "Source", "HK-BFETD v1.1 (origin of the field not documented in the files)"),
    ("Main class and use mix (shares)", "Source", "HK-BFETD v1.1 (UBEM classification; what the shares measure is not documented)"),
    ("Registered GFA", "Source (rare)", "Lands Department registered GFA via HK-BFETD: 11 of 29,387 prepared buildings"),
    ("BDBIAR year", "Source", "Buildings Department approval year via HK-BFETD; NOT plant age"),
    ("GFA when not registered", "Estimate", "footprint × storeys (overstates large low-rise complexes)"),
    ("Cooled share, peak load (W/m²), full-load hours", "Assumption", "per-use placeholders, share-weighted for mixed buildings; editable"),
    ("Peak cooling (kW), annual cooling (kWh)", "Estimate", "cooled area × W/m²; × full-load hours"),
    ("Existing chiller COP", "Assumption", "one value for all buildings unless set per building"),
    ("Inside a DCS service area", "Estimate", "building centre inside the Kai Tak OZP boundary (approximation of the service area)"),
]
