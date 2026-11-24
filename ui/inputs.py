"""Model inputs. Widgets live on the Compare options tab; values are read from session state at the top of every run,
so the step bar, the live card next to the map and every tab use the same numbers."""
from dataclasses import replace
import streamlit as st
from model import Assumptions
from ui import state
from ui.style import html

A0 = Assumptions()
# field, label, widget, lo, hi, step, format, display scale, group, help
SPECS = [
    ("demand_scale", "Scale all cooling demand (%)", "slider", 30, 200, 5, "%d", 100, "demand",
     "Multiplies every building's cooling demand: test what happens if loads are higher or lower than the placeholders."),
    ("cop_existing", "Existing system efficiency (COP)", "slider", 1.0, 8.0, 0.1, "%.1f", 1, "demand",
     "Used for every building without its own COP. A COP set on the building card takes priority."),
    ("tariff", "Electricity tariff (HK$/kWh)", "slider", 0.1, 5.0, 0.05, "%.2f", 1, "finance", None),
    ("emission_factor", "Grid emission factor (kgCO₂e/kWh)", "number", 0.0, 2.0, 0.01, "%.2f", 1, "finance", None),
    ("discount_rate", "Real discount rate (%)", "slider", 0.0, 15.0, 0.5, "%.1f", 100, "finance", None),
    ("analysis_years", "Analysis period (years)", "slider", 5, 50, 1, "%d", 1, "finance", None),
    ("elec_escalation", "Real electricity price change (%/yr)", "slider", -5.0, 5.0, 0.5, "%.1f", 100, "finance", None),
    ("existing_remaining_life", "Remaining life of today's chillers (years)", "slider", 0, 30, 1, "%d", 1, "indiv", None),
    ("cop_upgrade", "Replacement chiller COP", "slider", 1.0, 8.0, 0.1, "%.1f", 1, "indiv", None),
    ("upgrade_capex_kw", "Replacement cost (HK$/kW)", "number", 0.0, 50000.0, 100.0, "%.0f", 1, "indiv", None),
    ("equipment_life", "Chiller life (years)", "number", 1, 60, 1, "%d", 1, "indiv", None),
    ("maint_existing_kw", "Maintenance, today's plants (HK$/kW/yr)", "number", 0.0, 5000.0, 10.0, "%.0f", 1, "indiv", None),
    ("maint_upgrade_kw", "Maintenance, replaced plants (HK$/kW/yr)", "number", 0.0, 5000.0, 10.0, "%.0f", 1, "indiv", None),
    ("cop_central", "Shared plant efficiency (COP)", "slider", 1.0, 8.0, 0.1, "%.1f", 1, "cmcs", None),
    ("diversity", "Peak diversity (plant size ÷ sum of peaks)", "slider", 0.4, 1.0, 0.01, "%.2f", 1, "cmcs", None),
    ("central_capex_kw", "Shared plant cost (HK$/kW)", "number", 0.0, 50000.0, 100.0, "%.0f", 1, "cmcs", None),
    ("network_cost_m", "Pipe cost (HK$/m)", "number", 0.0, 200000.0, 500.0, "%.0f", 1, "cmcs", None),
    ("cmcs_route_factor", "Pipe route ÷ straight-line length", "slider", 1.0, 3.0, 0.05, "%.2f", 1, "cmcs",
     "The pipe length is the minimum spanning tree between the selected buildings times this factor."),
    ("connection_cost", "Connection per building (HK$)", "number", 0.0, 50e6, 50000.0, "%.0f", 1, "cmcs", None),
    ("pump_share", "Pumping energy (% of plant)", "slider", 0, 30, 1, "%d", 100, "cmcs", None),
    ("network_loss", "Distribution loss (%)", "slider", 0, 30, 1, "%d", 100, "cmcs", None),
    ("maint_central_plant_kw", "Plant maintenance (HK$/kW/yr)", "number", 0.0, 5000.0, 10.0, "%.0f", 1, "cmcs", None),
    ("maint_network_pct", "Network maintenance (% of its cost/yr)", "slider", 0.0, 10.0, 0.1, "%.1f", 100, "cmcs", None),
    ("plant_life", "Plant life (years)", "number", 1, 60, 1, "%d", 1, "cmcs", None),
    ("network_life", "Network life (years)", "number", 1, 100, 1, "%d", 1, "cmcs", None),
    ("dcs_contract_factor", "Contract capacity ÷ building peak", "slider", 0.5, 1.5, 0.05, "%.2f", 1, "dcs",
     "The capacity charge is paid on contract capacity. Contracting below the sum of peaks lowers the bill but risks overrun charges."),
    ("dcs_capacity_escalation", "Real capacity-charge change (%/yr)", "slider", -5.0, 5.0, 0.5, "%.1f", 100, "dcs", None),
    ("dcs_connection_cost", "Building-side works per building (HK$)", "number", 0.0, 50e6, 50000.0, "%.0f", 1, "dcs", None),
    ("dcs_building_capex_kw", "Secondary-side changes (HK$/kW)", "number", 0.0, 20000.0, 50.0, "%.0f", 1, "dcs", None),
    ("dcs_maint_kw", "Building-side maintenance (HK$/kW/yr)", "number", 0.0, 2000.0, 5.0, "%.0f", 1, "dcs", None),
    ("dcs_aux_kwh_per_kwh", "Building pumping (kWh per kWh of cooling)", "number", 0.0, 0.2, 0.005, "%.3f", 1, "dcs", None),
    ("dcs_plant_cop", "DCS plant COP (emissions only)", "slider", 1.0, 8.0, 0.1, "%.1f", 1, "dcs", None),
    ("dcs_building_life", "Building-side equipment life (years)", "number", 1, 60, 1, "%d", 1, "dcs", None),
]
GROUPS = [("demand", "Cooling demand"), ("finance", "Energy, carbon and finance"), ("indiv", "Keep individual plants"),
          ("cmcs", "Shared plant (private)"), ("dcs", "Public district cooling")]
INTS = {"analysis_years", "existing_remaining_life", "equipment_life", "plant_life", "network_life", "dcs_building_life"}


def _default(sp):
    v = getattr(A0, sp[0]) * sp[7]
    return int(round(v)) if sp[6] == "%d" else float(v)


def _key(f): return "in_" + f
def _val(sp): return st.session_state.get(_key(sp[0]), _default(sp))


def dcs_choice():
    reg, _, _ = state.dcs_data(); sysopt = {s["id"]: s for s in reg["systems"]}
    sid = st.session_state.get("in_dcs_sys", "kai_tak"); sid = sid if sid in sysopt else "kai_tak"
    yrs = list(sysopt[sid]["rates"]); yr = st.session_state.get("in_dcs_year", yrs[-1]); yr = yr if yr in yrs else yrs[-1]
    rate = sysopt[sid]["rates"][yr]
    cap = st.session_state.get(f"in_dcs_cap_{sid}_{yr}", float(rate["capacity_hkd_per_kwr_month"]))
    use = st.session_state.get(f"in_dcs_use_{sid}_{yr}", float(rate["consumption_hkd_per_kwhr"]))
    return sysopt, sid, yr, rate, cap, use


def values():
    kw = {}
    for sp in SPECS:
        v = _val(sp) / sp[7] if sp[7] != 1 else _val(sp)
        kw[sp[0]] = int(round(v)) if sp[0] in INTS else float(v)
    _, _, _, _, cap, use = dcs_choice()
    kw.update(dcs_capacity_rate=float(cap), dcs_consumption_rate=float(use))
    return kw


def max_m(): return float(st.session_state.get("in_max_m", 300.0))
def use_mst(): return st.session_state.get("in_use_mst", True)
def global_defaults(): return {"cop_existing": values()["cop_existing"]}


def assumptions_for(did, ids, stamp=""):
    """(Assumptions, excluded, geometry summary) for any cluster, with the current inputs."""
    kw = values()
    recs = [state.district_data(did, stamp)["by_id"][i] for i in ids]
    b, excl = __import__("clusters").to_model(recs, st.session_state.overrides, {"cop_existing": kw["cop_existing"]}, state.table())
    g = state.geo_summary(did, tuple(ids), max_m(), kw["cmcs_route_factor"], stamp) if ids else {"n": 0}
    nm = (g.get("network_m") or 0.0) if use_mst() and len(ids) > 1 else float(st.session_state.get("in_network_m", A0.network_m))
    return replace(A0, buildings=b, network_m=nm, **kw), excl, g


def chips(A):
    """Every input that differs from its default (orange), plus the sourced tariff and the pipe-length basis."""
    out = []
    for sp in SPECS:
        if abs(float(_val(sp)) - float(_default(sp))) > 1e-9:
            out.append((f"{sp[1].split(' (')[0]}: {sp[6] % _val(sp)}{' %' if sp[7] == 100 else ''}", "warn"))
    sysopt, sid, yr, rate, cap, use = dcs_choice()
    src = abs(cap - rate["capacity_hkd_per_kwr_month"]) < 1e-9 and abs(use - rate["consumption_hkd_per_kwhr"]) < 1e-9
    out.append((f"DCS tariff: {sysopt[sid]['name'].replace(' District Cooling System', '')} {yr}, HK${cap:g}/kW·month + HK${use:g}/kWh"
                + (" (EMSD)" if src else " (edited)"), "src" if src else "warn"))
    out.append((f"Pipe length {A.network_m:,.0f} m " + ("(from selection)" if use_mst() else "(typed)"), ""))
    return "".join(f'<span class="chip {k}">{t}</span>' for t, k in out)


def panel(have_cluster):
    n_changed = sum(1 for sp in SPECS if abs(float(_val(sp)) - float(_default(sp))) > 1e-9)
    with st.expander(f"Model inputs · {n_changed} changed from default" if n_changed else "Model inputs (illustrative defaults, except the DCS tariff)"):
        st.caption("Every default is an illustrative placeholder, not a Hong Kong statistic, except the DCS tariff (EMSD). "
                   "Results update as you move a slider. Sliders = values to explore; number boxes = costs to type in.")
        tabs = st.tabs([t for _, t in GROUPS] + ["Screening"])
        for (g, _), tab in zip(GROUPS, tabs):
            with tab:
                cols = st.columns(3)
                for k, sp in enumerate([s for s in SPECS if s[8] == g]):
                    f, label, kind, lo, hi, step, fmt, _, _, hlp = sp
                    with cols[k % 3]:
                        if kind == "slider": st.slider(label, lo, hi, _default(sp), step, format=fmt, key=_key(f), help=hlp)
                        else: st.number_input(label, lo, hi, _default(sp), step, format=fmt, key=_key(f), help=hlp)
                if g == "cmcs":
                    st.checkbox("Use pipe length from the selection (spanning tree × route factor)", value=True, key="in_use_mst",
                                disabled=not have_cluster)
                    if not use_mst(): st.number_input("Network length (m)", 0.0, 50000.0, float(A0.network_m), 50.0, format="%.0f", key="in_network_m")
                if g == "dcs":
                    sysopt, sid, yr, rate, cap, use = dcs_choice()
                    c1, c2 = st.columns(2)
                    c1.selectbox("Tariff of", list(sysopt), format_func=lambda k: sysopt[k]["name"], key="in_dcs_sys")
                    c2.selectbox("Tariff year", list(sysopt[sid]["rates"]), index=list(sysopt[sid]["rates"]).index(yr), key="in_dcs_year")
                    c1.number_input("Capacity charge (HK$/kW refrigeration/month)", 0.0, 1000.0, float(rate["capacity_hkd_per_kwr_month"]), 1.0,
                                    key=f"in_dcs_cap_{sid}_{yr}")
                    c2.number_input("Consumption charge (HK$/kWh refrigeration)", 0.0, 5.0, float(rate["consumption_hkd_per_kwhr"]), 0.005,
                                    format="%.4f", key=f"in_dcs_use_{sid}_{yr}")
                    st.caption(f"Source: EMSD District Cooling Services Charges, {yr}. Rates follow the Cap. 624 adjustment formula.")
        with tabs[-1]:
            st.number_input("Distance check: flag buildings further apart than (m)", 50.0, 2000.0, 300.0, 25.0, key="in_max_m",
                            help="Edge-to-edge distance. A screening flag, never a block.")
        if st.button("Reset all inputs to defaults", key="reset_inputs"):
            for k in [k for k in list(st.session_state.keys()) if str(k).startswith("in_")]: del st.session_state[k]
            st.rerun()
