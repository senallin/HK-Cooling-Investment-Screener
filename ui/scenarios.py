"""Compare options and Sensitivity tabs. Model: lifecycle.py (three options, NPV, discounted payback)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lifecycle as L
import verdict as V
from model import validate
from ui import inputs, state
from ui.style import html, note, layout, mhk, yrs, explain, OPTION_NAMES, OPTION_COLORS, TEAL, MUTED, SLATE

WHAT = {"Individual": "Each building keeps its chillers and replaces them at end of life (reference case).",
        "CMCS": "One privately built central plant and pipe network shared by the cluster.",
        "DCS": "Connect to a government district cooling system and pay the EMSD tariff."}


def cards_html(R):
    S = R["scenarios"]; best = V.best_by_row(R); top = R["best"]
    rows = [("Investment now", None, lambda s: mhk(s["capex0"]) if s["capex0"] else "none"),
            ("Running cost, year 1", "opex1", lambda s: mhk(s["opex1"]) + "/yr"),
            ("Lifecycle cost (PV)", "pv_cost", lambda s: mhk(s["pv_cost"])),
            ("Saving vs individual (PV)", "npv", lambda s: "reference" if s is S["Individual"] else mhk(s["npv_saving"])),
            ("Payback (discounted)", "payback", lambda s: "—" if s is S["Individual"] else yrs(s["discounted_payback"])),
            ("Emissions", "co2", lambda s: f"{s['co2_t']:,.0f} tCO₂e/yr")]
    cards = []
    for n in L.SCENARIOS:
        s = S[n]
        tr = "".join(f'<tr><td>{lab}</td><td class="v{" win" if k and best.get(k) == n else ""}">{fn(s)}</td></tr>' for lab, k, fn in rows)
        tag = '<span class="tag">Lowest lifecycle cost</span>' if n == top else ""
        cards.append(f'<div class="opt{" best" if n == top else ""}" style="--c:{OPTION_COLORS[n]}"><div class="name">{OPTION_NAMES[n]}{tag}</div>'
                     f'<div class="what">{WHAT[n]}</div><table>{tr}</table></div>')
    return f'<div class="opts">{"".join(cards)}</div>'


def _pv(series, r): return sum(v / (1 + r) ** t for t, v in enumerate(series))


def render_results(meta, cl, A, EXCL, G, R):
    n_ch = inputs.changed_count()
    st.caption(("Results use the default inputs. " if not n_ch else f"{n_ch} input(s) changed from default (orange chips). ")
               + "Change any input on the **Inputs** tab, where published values and judgement calls are kept apart.")
    html(f'<div style="margin:.2rem 0 .5rem">{inputs.chips(A)}</div>')
    if not A.buildings: st.info("Select buildings on the Map and selection tab first."); return
    errs = validate(A)
    if errs:
        for e in errs: st.error(e)
        return
    p = G.get("proximity") or {}
    if p.get("within_limit") is False: note(f"Distance check: {p['n_pairs_over_limit']} pair(s) are more than {inputs.max_m():,.0f} m apart: "
                                            "the shared plant's pipe network may be impractical.", "warn")
    cov = state.coverage(meta["id"], tuple(cl["ids"]), meta.get("generated", "")); n_dcs = sum(cov.values())
    if n_dcs < len(cl["ids"]): note(f"Only {n_dcs} of {len(cl['ids'])} buildings are inside an existing DCS service area. For the rest, the district "
                                    "cooling result assumes a network could reach them at the selected tariff.", "warn")
    if EXCL: note(f"{len(EXCL)} selected building(s) have missing inputs and are left out. See the Cluster assessment tab.", "warn")
    reg, _, _ = state.dcs_data()
    for s_ in reg["systems"]:
        rule = s_.get("connection_rule")
        if rule and cov.get(s_["id"]): note(f"<b>{s_['name']}:</b> {rule['text']} <span class='sub'>Source: {rule['source']}.</span>")
    html(f'<div class="verdict">{V.headline(R)}</div>')
    html(cards_html(R))
    explain("results", "ⓘ What do these numbers mean?")
    st.caption(f"Present values over {R['years']} years at a {A.discount_rate:.1%} real discount rate, including replacements and residual value. "
               "Green dot = best on that row. District cooling emissions include the DCS plant's electricity (attributed). A screening, not a forecast.")
    S = R["scenarios"]; names = [OPTION_NAMES[n] for n in L.SCENARIOS]; r = A.discount_rate
    c1, c2 = st.columns(2)
    with c1:
        f = go.Figure()
        for comp, col, lab in (("capex", SLATE, "Investment & replacement"), ("energy", "#8FB8BD", "Electricity"), ("maint", "#9AA5AB", "Maintenance"), ("charges", "#7B5EA7", "DCS charges")):
            f.add_bar(x=names, y=[_pv(S[n][comp], r) / 1e6 for n in L.SCENARIOS], name=lab, marker_color=col)
        f.update_layout(barmode="relative", title=f"Lifecycle cost, present value (HK$M, {R['years']} yrs)")
        st.plotly_chart(layout(f, 330, True), width="stretch")
        explain("charts", "ⓘ Present value, residual value, cash flow")
    with c2:
        f = go.Figure()
        for n in ("CMCS", "DCS"):
            f.add_scatter(x=list(range(R["years"] + 1)), y=[v / 1e6 for v in S[n]["cum_saving_disc"]], name=OPTION_NAMES[n], line=dict(color=OPTION_COLORS[n], width=3))
        f.add_hline(y=0, line_color="#C5CDD2")
        f.update_layout(title="Cumulative discounted saving vs keeping individual plants (HK$M)", xaxis_title="Year")
        st.plotly_chart(layout(f, 330, True), width="stretch")
    d = S["DCS"]
    st.caption(f"District cooling bill, year 1: contract capacity {d['capacity_kw'] / 1e3:,.2f} MW ({d['capacity_kw'] / 3.517:,.0f} RT) → capacity charge "
               f"{mhk(d['capacity_charge'])} + consumption charge {mhk(d['consumption_charge'])}.")
    explain("dcs_bill", "ⓘ How the district cooling bill works")
    with st.expander("Detailed table and year-by-year cash flows"):
        t = pd.DataFrame([{"Option": OPTION_NAMES[n], "Investment now (HK$M)": S[n]["capex0"] / 1e6, "Running cost yr 1 (HK$M)": S[n]["opex1"] / 1e6,
                           "Building electricity (GWh/yr)": S[n]["elec_yr"] / 1e6, "Emissions (tCO₂e/yr)": S[n]["co2_t"], "Lifecycle cost PV (HK$M)": S[n]["pv_cost"] / 1e6,
                           "Saving vs individual PV (HK$M)": S[n]["npv_saving"] / 1e6, "Simple payback (yrs)": S[n]["simple_payback"],
                           "Discounted payback (yrs)": S[n]["discounted_payback"], "Levelised cost (HK$/kWh cooling)": S[n]["levelised_hk_per_kwh"]}
                          for n in L.SCENARIOS]).set_index("Option")
        st.dataframe(t.style.format("{:,.2f}", na_rep="—"), width="stretch")
        cf = pd.DataFrame({f"{OPTION_NAMES[n]} · {k}": S[n][k] for n in L.SCENARIOS for k in ("capex", "energy", "maint", "charges", "cost")})
        cf.index.name = "year"
        st.dataframe((cf / 1e6).style.format("{:,.2f}"), width="stretch", height=260)
        st.download_button("Download cash flows (CSV, HK$)", cf.to_csv().encode("utf-8-sig"), f"{st.session_state.active[meta['id']]}_cashflows.csv", "text/csv", key="dl_cf")


def render_sensitivity(A):
    if not A.buildings: st.info("Select buildings first."); return
    if validate(A): st.info("Fix the input errors on the Compare options tab to see sensitivity."); return
    s1, s2, s3 = st.columns(3)
    sc = s1.selectbox("Option", ["DCS", "CMCS"], format_func=OPTION_NAMES.get, key="s_sc")
    met = s2.selectbox("Result", list(L.METRICS), format_func=L.METRICS.get, key="s_m")
    pct = s3.slider("Move each input by ±%", 5, 50, 20, 5, key="s_pct") / 100
    explain("sensitivity", "ⓘ How to read this tab")
    fields = [f for f, (_, ap) in L.PARAMS.items() if ap in ("all", sc)]
    base, rows = L.tornado(A, sc, met, pct, fields)
    div = 1e6 if met in ("npv_saving", "pv_cost") else 1; unit = " (HK$M)" if div == 1e6 else ""
    st.markdown(f"#### What moves the {OPTION_NAMES[sc].lower()}'s {L.METRICS[met].split(' (')[0].lower()}?")
    st.caption(f"Each input moved {pct:.0%} down and up, one at a time, everything else fixed. Longest bars matter most. Base: "
               + ("not reached" if base is None else f"{base / div:,.2f}{unit}") + ".")
    f = go.Figure(); ys = [x["label"] for x in rows]
    d = lambda v: (v - base) / div if v is not None and base is not None else 0
    f.add_bar(y=ys, x=[d(x["low"]) for x in rows], orientation="h", name=f"Input −{pct:.0%}", marker_color="#9AA5AB")
    f.add_bar(y=ys, x=[d(x["high"]) for x in rows], orientation="h", name=f"Input +{pct:.0%}", marker_color=TEAL)
    f.update_layout(barmode="overlay", xaxis_title=f"Change{unit}", yaxis=dict(autorange="reversed"))
    st.plotly_chart(layout(f, 460, True), width="stretch")
    st.markdown("#### Two inputs at once")
    t1, t2 = st.columns(2)
    fx = t1.selectbox("Across", fields, index=fields.index("tariff"), format_func=lambda k: L.PARAMS[k][0], key="s_fx")
    dy = "dcs_capacity_rate" if sc == "DCS" else "central_capex_kw"
    fy = t2.selectbox("Down", fields, index=fields.index(dy), format_func=lambda k: L.PARAMS[k][0], key="s_fy")
    if fx == fy: st.warning("Choose two different inputs.")
    else:
        xs, ys2, z = L.two_way(A, fx, fy, sc, met)
        zz = [[None if v is None else v / div for v in row] for row in z]
        f = go.Figure(go.Heatmap(x=[f"{v:,.3g}" for v in xs], y=[f"{v:,.3g}" for v in ys2], z=zz, zmid=0 if met == "npv_saving" else None,
                                 colorscale=[[0, "#C62828"], [.5, "#F5F5F5"], [1, TEAL]], text=[["–" if v is None else f"{v:,.1f}" for v in row] for row in zz],
                                 texttemplate="%{text}", colorbar=dict(title=unit.strip())))
        f.update_layout(xaxis_title=L.PARAMS[fx][0], yaxis_title=L.PARAMS[fy][0], title=f"{L.METRICS[met]}{unit}, {OPTION_NAMES[sc]}")
        st.plotly_chart(layout(f, 440), width="stretch")
    st.markdown("#### Break-even values")
    st.caption("The value of each input (others fixed) at which this option's saving against keeping individual plants is exactly zero.")
    be = []
    for f_ in fields:
        k = L.breakeven(A, f_, sc)
        if k is not None: be.append({"Input": L.PARAMS[f_][0], "Current value": getattr(A, f_), "Break-even value": getattr(L._set(A, f_, k), f_), "Change needed": f"{k - 1:+.0%}"})
    if be: st.dataframe(pd.DataFrame(be), hide_index=True, width="stretch")
    else: st.caption("No input reaches break-even within 0–5× its current value.")
