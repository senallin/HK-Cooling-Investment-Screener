"""Deterministic cooling-investment model. Terms: GFA = gross floor area; cooled area = GFA x cooled fraction;
peak load (kW) = cooled area x W/m2; annual demand (kWh) = peak load x full-load hours.
Central = a PRIVATELY developed shared plant, not a government DCS connection. Pure Python: no Streamlit, no randomness.
All default numbers are ILLUSTRATIVE placeholders, not Hong Kong statistics."""
from dataclasses import dataclass, field, replace

SAMPLE_BUILDINGS = [  # name, floor area m2, peak cooling W/m2, equivalent full-load hours/yr
    {"name": "Office Tower A", "area_m2": 30000, "load_w_m2": 110, "hours": 2600},
    {"name": "Office Tower B", "area_m2": 22000, "load_w_m2": 105, "hours": 2500},
    {"name": "Retail Podium", "area_m2": 15000, "load_w_m2": 150, "hours": 3200},
    {"name": "Hotel Block", "area_m2": 18000, "load_w_m2": 120, "hours": 3800},
]

@dataclass(frozen=True)
class Assumptions:
    buildings: tuple = field(default_factory=lambda: tuple(tuple(b.values()) for b in SAMPLE_BUILDINGS))
    demand_scale: float = 1.0          # multiplier on cooling demand (for sensitivity)
    tariff: float = 1.5                # HK$/kWh (illustrative)
    emission_factor: float = 0.5       # kgCO2e/kWh grid (illustrative)
    cop_existing: float = 3.2          # seasonal COP, ageing independent plant
    cop_upgrade: float = 4.2           # seasonal COP, upgraded independent plant
    cop_central: float = 5.2           # seasonal COP, central plant
    pump_share: float = 0.08           # network pumping energy as share of plant electricity
    network_loss: float = 0.04         # share of cooling lost in distribution
    upgrade_capex_kw: float = 2800     # HK$ per kW_th (illustrative)
    central_capex_kw: float = 4200     # HK$ per kW_th of central plant
    diversity: float = 0.80            # peak coincidence: central plant size / sum of building peaks
    network_m: float = 800             # pipe route length
    network_cost_m: float = 25000      # HK$ per metre installed
    connection_cost: float = 1500000   # HK$ per building (energy transfer station); with connection_cost_kw > 0 it is the per-building MINIMUM
    connection_cost_kw: float = 0.0    # HK$ per kW of building peak (lifecycle model only); 0 = flat per-building cost
    # Maintenance: one comparable basis for all scenarios (HK$ per kW of installed cooling capacity per year)
    maint_existing_kw: float = 160     # independent plants, capacity = sum of building peaks
    maint_upgrade_kw: float = 120      # upgraded independent plants
    maint_central_plant_kw: float = 100  # central plant, capacity = peak x diversity
    maint_network_pct: float = 0.01    # pipe network + connections, share of their capex per year
    horizon_years: int = 20
    # ---- lifecycle (lifecycle.py). ILLUSTRATIVE unless a source is named. ----
    discount_rate: float = 0.04        # real discount rate per year
    analysis_years: int = 25
    elec_escalation: float = 0.0       # real change in electricity tariff per year
    existing_remaining_life: int = 5   # years until today's independent chillers must be replaced
    equipment_life: int = 20           # life of independent (building) chillers
    plant_life: int = 25               # life of CMCS central plant equipment
    network_life: int = 50             # life of CMCS pipes and connections
    # ---- DCS (government district cooling) ----
    # Tariff: EMSD "District Cooling Services Charges", Kai Tak DCS rates for 2026/27 (Cap. 624 adjustment formula).
    dcs_capacity_rate: float = 140.88  # HK$ per kW refrigeration of contract capacity per month (SOURCE: EMSD 2026/27)
    dcs_consumption_rate: float = 0.2387  # HK$ per kWh refrigeration consumed (SOURCE: EMSD 2026/27)
    dcs_capacity_escalation: float = 0.0  # real change per year (rate follows Composite CPI, so ~0 in real terms)
    dcs_contract_factor: float = 1.0   # contract capacity / building peak load
    dcs_connection_cost: float = 1000000  # HK$ per building: building-side works, heat exchangers / ETS (illustrative)
    dcs_building_capex_kw: float = 400  # HK$ per kW: secondary-side modification (illustrative)
    dcs_building_life: int = 30
    dcs_maint_kw: float = 30           # HK$ per kW per year, building-side equipment (illustrative)
    dcs_aux_kwh_per_kwh: float = 0.02  # building secondary pumping electricity per kWh cooling (illustrative)
    dcs_plant_cop: float = 5.5         # DCS plant system COP incl. distribution, for ATTRIBUTED emissions only (illustrative)
    cmcs_route_factor: float = 1.3     # pipe route length / minimum spanning tree length (illustrative)

def validate(a):
    e = []
    if not a.buildings: e.append("Add at least one building.")
    for i, b in enumerate(a.buildings, 1):
        if not (b[1] > 0 and b[2] > 0 and 0 < b[3] <= 8760):
            e.append(f"Building {i}: area and load must be above 0, hours between 1 and 8,760.")
    for i, b in enumerate(a.buildings, 1):
        if len(b) > 4 and b[4] is not None and not b[4] > 0: e.append(f"Building {i}: COP must be above 0.")
    for f in ("cop_existing", "cop_upgrade", "cop_central", "tariff"):
        if getattr(a, f) <= 0: e.append(f"{f} must be above 0.")
    if not 0 <= a.network_loss < 0.5: e.append("Network loss must be between 0% and 50%.")
    if not 0 < a.diversity <= 1: e.append("Diversity must be above 0 and at most 1.")
    if a.demand_scale <= 0: e.append("Demand scale must be above 0.")
    if not -0.05 < a.discount_rate < 0.5: e.append("Discount rate must be between -5% and 50%.")
    if not 1 <= a.analysis_years <= 60: e.append("Analysis period must be 1 to 60 years.")
    for f in ("equipment_life", "plant_life", "network_life", "dcs_building_life"):
        if getattr(a, f) < 1: e.append(f"{f} must be at least 1 year.")
    if a.existing_remaining_life < 0: e.append("Remaining life of existing plant cannot be negative.")
    if a.dcs_plant_cop <= 0: e.append("DCS plant COP must be above 0.")
    if a.dcs_contract_factor <= 0: e.append("DCS contract factor must be above 0.")
    return e

def run(a):
    errs = validate(a)
    if errs: raise ValueError("; ".join(errs))
    area = sum(b[1] for b in a.buildings)  # cooled floor area, m2
    peak = sum(b[1] * b[2] for b in a.buildings) / 1000 * a.demand_scale
    demand = sum(b[1] * b[2] * b[3] for b in a.buildings) / 1000 * a.demand_scale
    def scen(name, elec, capex, maint):
        energy = elec * a.tariff
        return dict(name=name, demand=demand, elec=elec, energy_cost=energy, maint=maint,
                    opex=energy + maint, capex=capex, co2_t=elec * a.emission_factor / 1000)
    # Existing COP can differ per building (optional 5th tuple item); falls back to the global value.
    elec1 = sum(b[1] * b[2] * b[3] / 1000 / (b[4] if len(b) > 4 and b[4] else a.cop_existing)
                for b in a.buildings) * a.demand_scale
    s1 = scen("Retain", elec1, 0, a.maint_existing_kw * peak)
    s2 = scen("Upgrade", demand / a.cop_upgrade, peak * a.upgrade_capex_kw, a.maint_upgrade_kw * peak)
    plant = demand / (1 - a.network_loss) / a.cop_central * (1 + a.pump_share)
    plant_kw = peak * a.diversity
    net_capex = a.network_m * a.network_cost_m + len(a.buildings) * a.connection_cost
    cap3 = plant_kw * a.central_capex_kw + net_capex
    s3 = scen("Central", plant, cap3, plant_kw * a.maint_central_plant_kw + net_capex * a.maint_network_pct)
    for s in (s1, s2, s3):
        s["saving"] = s1["opex"] - s["opex"]
        s["co2_cut_t"] = s1["co2_t"] - s["co2_t"]
        s["payback"] = s["capex"] / s["saving"] if s["capex"] > 0 and s["saving"] > 0 else None
    return dict(area=area, peak_kw=peak, scenarios=[s1, s2, s3])

SENSITIVITY = [("tariff", "Electricity tariff"), ("cop_central", "Central plant COP"),
               ("cop_existing", "Existing COP"), ("demand_scale", "Cooling demand"),
               ("central_capex_kw", "Central plant cost"), ("network_cost_m", "Pipe cost per metre"),
               ("network_m", "Network length"), ("diversity", "Peak diversity"),
               ("maint_central_plant_kw", "Central plant maintenance")]

def sensitivity(a, pct=0.2):
    """Central-scenario annual saving at -pct and +pct of each input."""
    base = run(a)["scenarios"][2]["saving"]
    rows = []
    for f, label in SENSITIVITY:
        v = getattr(a, f); out = []
        for m in (1 - pct, 1 + pct):
            nv = min(v * m, 1.0) if f == "diversity" else v * m
            try: out.append(run(replace(a, **{f: nv}))["scenarios"][2]["saving"])
            except ValueError: out.append(base)
        rows.append(dict(label=label, low=out[0] - base, high=out[1] - base))
    return base, sorted(rows, key=lambda r: -(abs(r["low"]) + abs(r["high"])))

def cumulative(a, res, years=None):
    years = years or a.horizon_years
    return {s["name"]: [-s["capex"] + s["saving"] * y for y in range(years + 1)] for s in res["scenarios"]}
