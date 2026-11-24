"""Deterministic cooling-investment model. Pure Python: no Streamlit, no randomness.
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
    connection_cost: float = 1500000   # HK$ per building (energy transfer station)
    maint_existing_m2: float = 18      # HK$/m2/yr
    maint_upgrade_m2: float = 13       # HK$/m2/yr
    maint_central_pct: float = 0.03    # share of central capex per year
    horizon_years: int = 20

def validate(a):
    e = []
    if not a.buildings: e.append("Add at least one building.")
    for i, b in enumerate(a.buildings, 1):
        if not (b[1] > 0 and b[2] > 0 and 0 < b[3] <= 8760):
            e.append(f"Building {i}: area and load must be above 0, hours between 1 and 8,760.")
    for f in ("cop_existing", "cop_upgrade", "cop_central", "tariff"):
        if getattr(a, f) <= 0: e.append(f"{f} must be above 0.")
    if not 0 <= a.network_loss < 0.5: e.append("Network loss must be between 0% and 50%.")
    if not 0 < a.diversity <= 1: e.append("Diversity must be above 0 and at most 1.")
    if a.demand_scale <= 0: e.append("Demand scale must be above 0.")
    return e

def run(a):
    errs = validate(a)
    if errs: raise ValueError("; ".join(errs))
    area = sum(b[1] for b in a.buildings)
    peak = sum(b[1] * b[2] for b in a.buildings) / 1000 * a.demand_scale
    demand = sum(b[1] * b[2] * b[3] for b in a.buildings) / 1000 * a.demand_scale
    def scen(name, elec, capex, maint):
        energy = elec * a.tariff
        return dict(name=name, demand=demand, elec=elec, energy_cost=energy, maint=maint,
                    opex=energy + maint, capex=capex, co2_t=elec * a.emission_factor / 1000)
    s1 = scen("Retain", demand / a.cop_existing, 0, a.maint_existing_m2 * area)
    s2 = scen("Upgrade", demand / a.cop_upgrade, peak * a.upgrade_capex_kw, a.maint_upgrade_m2 * area)
    plant = demand / (1 - a.network_loss) / a.cop_central * (1 + a.pump_share)
    cap3 = (peak * a.diversity * a.central_capex_kw + a.network_m * a.network_cost_m
            + len(a.buildings) * a.connection_cost)
    s3 = scen("Central", plant, cap3, cap3 * a.maint_central_pct)
    for s in (s1, s2, s3):
        s["saving"] = s1["opex"] - s["opex"]
        s["co2_cut_t"] = s1["co2_t"] - s["co2_t"]
        s["payback"] = s["capex"] / s["saving"] if s["capex"] > 0 and s["saving"] > 0 else None
    return dict(area=area, peak_kw=peak, scenarios=[s1, s2, s3])

SENSITIVITY = [("tariff", "Electricity tariff"), ("cop_central", "Central plant COP"),
               ("cop_existing", "Existing COP"), ("demand_scale", "Cooling demand"),
               ("central_capex_kw", "Central plant cost"), ("network_cost_m", "Pipe cost per metre"),
               ("network_m", "Network length"), ("diversity", "Peak diversity"),
               ("maint_central_pct", "Central maintenance")]

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
