import dataclasses
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from model import Assumptions, SAMPLE_BUILDINGS, run, sensitivity, cumulative, validate

st.set_page_config(page_title="Cooling Investment Screener", page_icon="❄", layout="wide")
INK, TEAL, AMBER, SLATE = "#14232B", "#0E6E73", "#C98A1B", "#7C8C94"
COL = {"Retain": SLATE, "Upgrade": AMBER, "Central": TEAL}
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:wght@500;600&family=Public+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"] {font-family:'Public Sans',sans-serif;}
h1,h2,h3 {font-family:'Newsreader',serif !important; color:#14232B; letter-spacing:-.01em;}
.verdict {font-family:'Newsreader',serif; font-size:2.1rem; line-height:1.25; max-width:46ch; margin:.2rem 0 .6rem;}
.note {border-left:3px solid #C98A1B; padding:.5rem .9rem; background:#fff; font-size:.92rem;}
[data-testid="stMetric"] {background:#fff; padding:.8rem 1rem; border-radius:6px;}
@media (max-width:640px){.verdict{font-size:1.5rem}}
</style>""", unsafe_allow_html=True)

D = Assumptions()
def num(label, key, lo, hi, step, fmt="%.2f", help=None):
    return st.number_input(label, lo, hi, float(getattr(D, key)), step, format=fmt, key=key, help=help)

with st.sidebar:
    st.header("Assumptions")
    st.caption("Every figure is an illustrative placeholder. Replace with project data.")
    if st.button("Reset to sample project"):
        for k in list(st.session_state): del st.session_state[k]
        st.rerun()
    with st.expander("Energy and tariff", True):
        tariff = num("Electricity tariff (HK$/kWh)", "tariff", 0.1, 10.0, 0.05)
        ef = num("Grid emission factor (kgCO₂e/kWh)", "emission_factor", 0.0, 2.0, 0.01)
        c0 = num("Existing system COP", "cop_existing", 1.0, 10.0, 0.1, "%.1f", "Seasonal coefficient of performance: cooling delivered per unit of electricity.")
        c1 = num("Upgraded system COP", "cop_upgrade", 1.0, 10.0, 0.1, "%.1f")
        c2 = num("Central plant COP", "cop_central", 1.0, 10.0, 0.1, "%.1f")
        pump = st.slider("Network pumping energy (% of plant)", 0, 30, int(D.pump_share * 100), key="pump")
        loss = st.slider("Distribution cooling loss (%)", 0, 30, int(D.network_loss * 100), key="loss")
    with st.expander("Capital cost"):
        ucap = num("Upgrade cost (HK$/kW)", "upgrade_capex_kw", 0.0, 50000.0, 100.0, "%.0f")
        ccap = num("Central plant cost (HK$/kW)", "central_capex_kw", 0.0, 50000.0, 100.0, "%.0f")
        div = st.slider("Peak diversity (central plant size vs sum of peaks)", 0.4, 1.0, D.diversity, 0.01, key="div")
        nlen = num("Network length (m)", "network_m", 0.0, 20000.0, 50.0, "%.0f")
        ncost = num("Network cost (HK$/m)", "network_cost_m", 0.0, 200000.0, 500.0, "%.0f")
        conn = num("Connection cost per building (HK$)", "connection_cost", 0.0, 50e6, 50000.0, "%.0f")
    with st.expander("Maintenance (HK$ per kW of capacity per year)"):
        m0 = num("Existing independent plants", "maint_existing_kw", 0.0, 5000.0, 10.0, "%.0f")
        m1 = num("Upgraded independent plants", "maint_upgrade_kw", 0.0, 5000.0, 10.0, "%.0f")
        m2 = num("Central plant", "maint_central_plant_kw", 0.0, 5000.0, 10.0, "%.0f")
        m3 = st.slider("Network and connections (% of their capex per year)", 0.0, 10.0, D.maint_network_pct * 100, 0.1, key="m3")
    horizon = st.slider("Chart horizon (years)", 5, 30, D.horizon_years, key="hz")

st.title("Cooling Investment Screener")
st.caption("Preliminary comparison of independent and shared central cooling for a group of commercial buildings.")
tab_guide, tab_b, tab_r, tab_s, tab_m = st.tabs(["Start here", "Buildings", "Results", "Sensitivity", "Method"])

with tab_guide:
    st.markdown("### What this tool does")
    st.write("A cluster of commercial buildings can keep cooling itself, upgrade each building's chillers, "
             "or connect to one shared plant through a district pipe network. This tool estimates what each "
             "choice costs, how much electricity it uses and how much carbon it emits.")
    st.markdown("**How to use it:** check the sample buildings in *Buildings*, adjust assumptions in the sidebar, "
                "then read *Results* and test what matters in *Sensitivity*.")
    st.markdown('<div class="note">All defaults are <b>illustrative</b>, not Hong Kong statistics. This is a '
                'screening tool, not a feasibility study or engineering design.</div>', unsafe_allow_html=True)

with tab_b:
    st.write("Edit, add or delete rows. Load is peak cooling per m²; hours are equivalent full-load hours per year.")
    df = st.data_editor(pd.DataFrame(SAMPLE_BUILDINGS), num_rows="dynamic", use_container_width=True, key="bld",
        column_config={"name": "Building", "area_m2": st.column_config.NumberColumn("Floor area (m²)", min_value=1, format="%d"),
                       "load_w_m2": st.column_config.NumberColumn("Peak load (W/m²)", min_value=1, format="%d"),
                       "hours": st.column_config.NumberColumn("Full-load hours/yr", min_value=1, max_value=8760, format="%d")})
    demand_scale = st.slider("Scale all cooling demand (%)", 50, 150, 100, key="ds") / 100

df = df.dropna(subset=["area_m2", "load_w_m2", "hours"])
df["name"] = df["name"].fillna("Unnamed").replace("", "Unnamed")
A = Assumptions(buildings=tuple(tuple(r) for r in df[["name", "area_m2", "load_w_m2", "hours"]].itertuples(index=False)),
    demand_scale=demand_scale, tariff=tariff, emission_factor=ef, cop_existing=c0, cop_upgrade=c1, cop_central=c2,
    pump_share=pump / 100, network_loss=loss / 100, upgrade_capex_kw=ucap, central_capex_kw=ccap, diversity=div,
    network_m=nlen, network_cost_m=ncost, connection_cost=conn, maint_existing_kw=m0, maint_upgrade_kw=m1,
    maint_central_plant_kw=m2, maint_network_pct=m3 / 100, horizon_years=horizon)
errs = validate(A)

def mhk(x): return f"HK${x/1e6:,.1f}M"
def layout(fig, h=340):
    fig.update_layout(height=h, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Public Sans", color=INK), showlegend=False)
    fig.update_xaxes(gridcolor="#DCE3E4"); fig.update_yaxes(gridcolor="#DCE3E4")
    return fig

if errs:
    for e in errs: tab_r.error(e)
    tab_s.info("Fix the input errors to see sensitivity."); st.stop()
R = run(A); S = {s["name"]: s for s in R["scenarios"]}

with tab_r:
    c, u = S["Central"], S["Upgrade"]
    if c["payback"]: verdict = f"Central cooling pays back in {c['payback']:.1f} years and cuts {c['co2_cut_t']:,.0f} tCO₂e a year."
    else: verdict = "With these assumptions, central cooling does not save money against today's systems."
    st.markdown(f'<div class="verdict">{verdict}</div>', unsafe_allow_html=True)
    best = min((s for s in (u, c) if s["payback"]), key=lambda s: s["payback"], default=None)
    if best: st.caption(f"Fastest payback: {best['name'].lower()} option at {best['payback']:.1f} years. "
                        f"Upgrade: {u['payback']:.1f} yrs." if u["payback"] else "")
    k = st.columns(4)
    k[0].metric("Cooling demand", f"{R['scenarios'][0]['demand']/1e6:,.1f} GWh/yr", f"Peak {R['peak_kw']/1000:,.1f} MW", delta_color="off")
    k[1].metric("Central investment", mhk(c["capex"]))
    k[2].metric("Central annual saving", mhk(c["saving"]))
    k[3].metric("Central electricity", f"{c['elec']/1e6:,.2f} GWh/yr")
    table = pd.DataFrame([{"Scenario": n, "Electricity (GWh/yr)": s["elec"]/1e6, "Annual opex (HK$M)": s["opex"]/1e6,
        "Investment (HK$M)": s["capex"]/1e6, "Annual saving (HK$M)": s["saving"]/1e6,
        "Simple payback (yrs)": s["payback"] if s["payback"] else None, "Emissions (tCO₂e/yr)": s["co2_t"],
        "Reduction (tCO₂e/yr)": s["co2_cut_t"]} for n, s in S.items()]).set_index("Scenario")
    st.dataframe(table.style.format("{:,.1f}", na_rep="no payback"), use_container_width=True)
    c1_, c2_, c3_ = st.columns(3)
    names = list(S)
    for col, key, title in ((c1_, "opex", "Annual operating cost (HK$M)"), (c2_, "co2_t", "Emissions (tCO₂e/yr)")):
        f = go.Figure(go.Bar(x=names, y=[S[n][key] / (1e6 if key == "opex" else 1) for n in names], marker_color=[COL[n] for n in names]))
        col.plotly_chart(layout(f.update_layout(title=title, title_font_size=14)), use_container_width=True)
    cum = cumulative(A, R); f = go.Figure()
    for n in names: f.add_scatter(x=list(range(len(cum[n]))), y=[v/1e6 for v in cum[n]], name=n, line=dict(color=COL[n], width=3))
    f.update_layout(title="Cumulative cash vs today (HK$M)", title_font_size=14, showlegend=True, legend=dict(orientation="h", y=-.2))
    c3_.plotly_chart(layout(f).update_layout(showlegend=True), use_container_width=True)

with tab_s:
    st.write("Each input is moved 20% down and up while everything else stays fixed. Bars show the change in the central scheme's annual saving.")
    base, rows = sensitivity(A)
    f = go.Figure()
    f.add_bar(y=[r["label"] for r in rows], x=[r["low"]/1e6 for r in rows], orientation="h", name="Input −20%", marker_color=SLATE)
    f.add_bar(y=[r["label"] for r in rows], x=[r["high"]/1e6 for r in rows], orientation="h", name="Input +20%", marker_color=TEAL)
    f.update_layout(barmode="relative", xaxis_title="Change in annual saving (HK$M)", yaxis=dict(autorange="reversed"),
                    legend=dict(orientation="h", y=1.1))
    st.plotly_chart(layout(f, 420).update_layout(showlegend=True), use_container_width=True)
    st.caption(f"Base annual saving: {mhk(base)}.")

with tab_m:
    st.markdown("""**Demand.** Area × peak load × full-load hours ÷ 1,000 gives cooling in kWh.  
**Electricity.** Retain and Upgrade: demand ÷ COP. Central: demand ÷ (1 − network loss) ÷ COP × (1 + pumping share).  
**Investment.** Upgrade: peak kW × cost per kW. Central (privately developed shared plant): peak kW × diversity × cost per kW + network length × cost per metre + connection cost per building.  
**Operating cost.** Electricity × tariff + maintenance (HK$ per kW of installed capacity for all three scenarios, plus a share of network capex for Central). **Saving.** Retain opex minus scenario opex.  
**Simple payback.** Investment ÷ annual saving, shown only when the saving is positive. It ignores discounting, inflation, tariff changes and equipment replacement.  
**Emissions.** Electricity × grid emission factor.  
Retain is the baseline, so its saving is zero by definition.""")
