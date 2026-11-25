"""Lifecycle comparison of three cooling scenarios for ONE cluster. Pure Python, deterministic.

Scenarios
  Individual : every building keeps its own chillers (reference case). Existing plant runs at its current COP until
               `existing_remaining_life`, is then replaced at `upgrade_capex_kw` with the upgraded COP, and again every
               `equipment_life` years.
  CMCS       : Centralised Multi-building Cooling System, a PRIVATELY developed shared plant plus pipe network
               (the 'Central' case of model.run, with replacements and residual value).
  DCS        : connection to a government District Cooling System, paying the public tariff
               (capacity charge on contract capacity + consumption charge on cooling energy).

Conventions: year 0 = investment, years 1..N = operation, real (inflation-free) HK$, end-of-year discounting.
Residual value: straight-line remaining life of the latest asset vintage, credited in year N (same rule in every scenario).
kW refrigeration (DCS tariff unit) = kW of cooling (thermal), the unit used throughout.
"""
import math
from dataclasses import replace
from model import validate

SCENARIOS = ("Individual", "CMCS", "DCS")


def _peaks(a):
    """Per-building (peak kW, annual cooling kWh, existing COP)."""
    out = []
    for b in a.buildings:
        pk = b[1] * b[2] / 1000 * a.demand_scale
        cop = b[4] if len(b) > 4 and b[4] else a.cop_existing
        out.append((pk, pk * b[3], cop))
    return out


def _asset_flows(cost, first_year, life, years):
    """Purchases of an asset bought at first_year and every `life` years after, plus residual credit at year N."""
    flows = [0.0] * (years + 1)
    if cost == 0: return flows
    t, last = first_year, None
    while t <= years:
        flows[t] += cost; last = t; t += life
    if last is not None:
        remaining = last + life - years
        if remaining > 0: flows[years] -= cost * remaining / life
    return flows


def _pv(flows, r): return sum(v / (1 + r) ** t for t, v in enumerate(flows))


def _payback(diff, r=None):
    """Year (interpolated) when cumulative (optionally discounted) saving first becomes >= 0 after starting negative."""
    cum, prev = 0.0, 0.0
    for t, v in enumerate(diff):
        v = v if r is None else v / (1 + r) ** t
        prev, cum = cum, cum + v
        if t > 0 and cum >= 0 and prev < 0:
            return t - 1 + (-prev / v if v else 0)
    if diff and diff[0] >= 0 and all(x >= 0 for x in diff): return 0.0
    return None


def evaluate(a):
    errs = validate(a)
    if errs: raise ValueError("; ".join(errs))
    N, r = a.analysis_years, a.discount_rate
    bl = _peaks(a)
    P = sum(p for p, _, _ in bl); Q = sum(q for _, q, _ in bl); nb = len(bl)
    tariff = [a.tariff * (1 + a.elec_escalation) ** max(t - 1, 0) for t in range(N + 1)]
    out = {}

    # ---- Individual (reference) -----------------------------------------------------------------------------
    L0 = min(a.existing_remaining_life, N + 1)
    elec_old, elec_new = sum(q / c for _, q, c in bl), Q / a.cop_upgrade
    cap = _asset_flows(P * a.upgrade_capex_kw, L0, a.equipment_life, N) if L0 <= N else [0.0] * (N + 1)
    elec = [0.0] + [elec_old if t <= L0 else elec_new for t in range(1, N + 1)]
    maint = [0.0] + [P * (a.maint_existing_kw if t <= L0 else a.maint_upgrade_kw) for t in range(1, N + 1)]
    out["Individual"] = dict(capex=cap, elec=elec, energy=[e * tariff[t] for t, e in enumerate(elec)], maint=maint,
                             charges=[0.0] * (N + 1), attributed_elec=elec,
                             capex0=cap[0], capacity_kw=P, note="existing plant replaced at end of life")

    # ---- CMCS ---------------------------------------------------------------------------------------------
    plant_kw = P * a.diversity
    # connection per building = max(minimum per building, HK$/kW x that building's peak); flat when connection_cost_kw = 0
    conn = sum(max(a.connection_cost, getattr(a, "connection_cost_kw", 0.0) * pk) for pk, _, _ in bl)
    net = a.network_m * a.network_cost_m + conn
    cap = [x + y for x, y in zip(_asset_flows(plant_kw * a.central_capex_kw, 0, a.plant_life, N), _asset_flows(net, 0, a.network_life, N))]
    e = Q / (1 - a.network_loss) / a.cop_central * (1 + a.pump_share)
    elec = [0.0] + [e] * N
    maint = [0.0] + [plant_kw * a.maint_central_plant_kw + net * a.maint_network_pct] * N
    out["CMCS"] = dict(capex=cap, elec=elec, energy=[x * tariff[t] for t, x in enumerate(elec)], maint=maint,
                       charges=[0.0] * (N + 1), attributed_elec=elec, capex0=cap[0], capacity_kw=plant_kw,
                       network_capex=net, plant_capex=plant_kw * a.central_capex_kw)

    # ---- DCS ------------------------------------------------------------------------------------------------
    contract = P * a.dcs_contract_factor
    capex_b = nb * a.dcs_connection_cost + P * a.dcs_building_capex_kw
    cap = _asset_flows(capex_b, 0, a.dcs_building_life, N)
    aux = Q * a.dcs_aux_kwh_per_kwh
    cap_charge = [0.0] + [contract * a.dcs_capacity_rate * 12 * (1 + a.dcs_capacity_escalation) ** (t - 1) for t in range(1, N + 1)]
    # Consumption rate follows the electricity tariff under Cap. 624, so it escalates with it.
    use_charge = [0.0] + [Q * a.dcs_consumption_rate * (1 + a.elec_escalation) ** (t - 1) for t in range(1, N + 1)]
    plant_e = Q / a.dcs_plant_cop
    out["DCS"] = dict(capex=cap, elec=[0.0] + [aux] * N, energy=[0.0] + [aux * tariff[t] for t in range(1, N + 1)],
                      maint=[0.0] + [P * a.dcs_maint_kw] * N, charges=[c + u for c, u in zip(cap_charge, use_charge)],
                      capacity_charge=cap_charge[1] if N else 0.0, consumption_charge=use_charge[1] if N else 0.0,
                      attributed_elec=[0.0] + [aux + plant_e] * N, capex0=cap[0], capacity_kw=contract)

    ref = None
    for name in SCENARIOS:
        s = out[name]
        s["cost"] = [s["capex"][t] + s["energy"][t] + s["maint"][t] + s["charges"][t] for t in range(N + 1)]
        s["opex1"] = (s["energy"][1] + s["maint"][1] + s["charges"][1]) if N else 0.0
        s["pv_cost"] = _pv(s["cost"], r)
        s["elec_yr"] = s["elec"][1] if N else 0.0
        s["co2_t"] = (s["attributed_elec"][1] if N else 0.0) * a.emission_factor / 1000
        s["levelised_hk_per_kwh"] = s["pv_cost"] / _pv([0.0] + [Q] * N, r) if Q and N else None
        if name == "Individual": ref = s
    for name in SCENARIOS:
        s = out[name]
        diff = [rc - c for rc, c in zip(ref["cost"], s["cost"])]
        s["npv_saving"] = ref["pv_cost"] - s["pv_cost"]
        s["annual_saving1"] = ref["opex1"] - s["opex1"]
        s["co2_cut_t"] = ref["co2_t"] - s["co2_t"]
        extra = s["capex0"] - ref["capex0"]
        s["simple_payback"] = extra / s["annual_saving1"] if name != "Individual" and extra > 0 and s["annual_saving1"] > 0 else None
        s["discounted_payback"] = _payback(diff, r) if name != "Individual" else None
        s["cum_saving"] = [sum(diff[:t + 1]) for t in range(N + 1)]
        s["cum_saving_disc"] = [sum(v / (1 + r) ** k for k, v in enumerate(diff[:t + 1])) for t in range(N + 1)]
    best = min(SCENARIOS, key=lambda n: out[n]["pv_cost"])
    return dict(scenarios=out, peak_kw=P, cooling_kwh=Q, n_buildings=nb, best=best, years=N)


# ---- sensitivity --------------------------------------------------------------------------------------------
PARAMS = {  # field: (label, applies to)
    "tariff": ("Electricity tariff", "all"), "dcs_capacity_rate": ("DCS capacity charge", "DCS"),
    "dcs_consumption_rate": ("DCS consumption charge", "DCS"), "discount_rate": ("Discount rate", "all"),
    "demand_scale": ("Cooling demand", "all"), "cop_existing": ("Existing COP", "all"),
    "cop_upgrade": ("Replacement COP (Individual)", "Individual"), "cop_central": ("CMCS plant COP", "CMCS"),
    "central_capex_kw": ("CMCS plant cost", "CMCS"), "network_cost_m": ("Pipe cost per metre", "CMCS"),
    "network_m": ("Network length", "CMCS"), "diversity": ("Peak diversity", "CMCS"),
    "upgrade_capex_kw": ("Chiller replacement cost", "Individual"),
    "connection_cost_kw": ("Connection cost per kW", "CMCS"), "dcs_connection_cost": ("DCS connection cost", "DCS"),
    "existing_remaining_life": ("Remaining life of existing plant", "all"), "analysis_years": ("Analysis period", "all"),
}
METRICS = {"npv_saving": "NPV saving vs Individual (HK$)", "discounted_payback": "Discounted payback (years)",
           "pv_cost": "Lifecycle cost, present value (HK$)", "co2_cut_t": "CO₂e cut vs Individual (t/yr)"}
INT_FIELDS = {"existing_remaining_life", "analysis_years", "equipment_life", "plant_life", "network_life", "dcs_building_life"}


def _set(a, field, factor):
    v = getattr(a, field) * factor
    if field == "diversity": v = min(v, 1.0)
    if field in INT_FIELDS: v = max(0 if field == "existing_remaining_life" else 1, int(round(v)))
    return replace(a, **{field: v})


def metric(a, scenario, m):
    try: return evaluate(a)["scenarios"][scenario][m]
    except ValueError: return None


def tornado(a, scenario="DCS", m="npv_saving", pct=0.2, fields=None):
    """One-at-a-time: each input at (1-pct) and (1+pct), all else fixed. Sorted by swing."""
    base = metric(a, scenario, m); rows = []
    for f in fields or PARAMS:
        lo, hi = metric(_set(a, f, 1 - pct), scenario, m), metric(_set(a, f, 1 + pct), scenario, m)
        sw = (abs(lo - base) if lo is not None and base is not None else 0) + (abs(hi - base) if hi is not None and base is not None else 0)
        rows.append(dict(field=f, label=PARAMS[f][0], low=lo, high=hi, base=base, swing=sw,
                         low_value=getattr(_set(a, f, 1 - pct), f), high_value=getattr(_set(a, f, 1 + pct), f)))
    return base, sorted(rows, key=lambda r: -r["swing"])


def two_way(a, fx, fy, scenario="DCS", m="npv_saving", steps=(0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3)):
    """Grid of the metric over two inputs scaled by `steps`. Returns (x values, y values, z[y][x])."""
    xs = [getattr(_set(a, fx, s), fx) for s in steps]; ys = [getattr(_set(a, fy, s), fy) for s in steps]
    z = [[metric(_set(_set(a, fx, sx), fy, sy), scenario, m) for sx in steps] for sy in steps]
    return xs, ys, z


def breakeven(a, field, scenario="DCS", lo=0.0, hi=5.0, tol=1e-8):
    """Multiplier on `field` at which the scenario's NPV saving vs Individual is zero (bisection), or None."""
    f = lambda k: metric(_set(a, field, k), scenario, "npv_saving")
    flo, fhi = f(lo), f(hi)
    if flo is None or fhi is None or (flo > 0) == (fhi > 0): return None
    for _ in range(60):
        mid = (lo + hi) / 2; fm = f(mid)
        if fm is None: return None
        if (fm > 0) == (flo > 0): lo, flo = mid, fm
        else: hi = mid
        if hi - lo < tol: break
    return (lo + hi) / 2
