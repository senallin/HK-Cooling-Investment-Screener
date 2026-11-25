"""Compare districts tab.
A. Typical cluster: the same kind of cluster (size, spacing, floors, building types) found in every district; the typical one
   (median shared-plant saving per MW) is shown side by side with the district's building mix.
B. Pattern: up to 50 non-overlapping matching clusters per district; distribution of the lifecycle saving.
Engine: compare.py (pure, tested). Uses the same model inputs as every other tab."""
import json
from dataclasses import replace
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compare as K
from model import Assumptions
from ui import state, inputs
from ui.style import note, html, layout, explain, OPTION_NAMES, OPTION_COLORS, TEAL, MUTED

A0 = inputs.A0                                   # the app defaults (sources.APP_DEFAULTS)
CLASS_OPTS = ["Commercial", "Mixed-use", "Residential", "Industrial"]


@st.cache_data(show_spinner="Finding matching clusters and running the lifecycle model …")
def _run(did, stamp, n, max_d, floors, classes, k, ov_json, tkey, kw_json):
    DD = state.district_data(did, stamp); _, areas, _ = state.dcs_data()
    kw = json.loads(kw_json); base = replace(A0, **kw)
    ov = json.loads(ov_json); tbl = {a: tuple(b) for a, b in json.loads(tkey).items()}
    return K.run_district(DD["recs"], base, n, max_d, tuple(floors), tuple(classes), k, ov, {"cop_existing": kw["cop_existing"]}, tbl, areas)


def _open(did, dname, ids, label):
    """Callback: create a cluster with these buildings in that district and switch the map to it."""
    ss = st.session_state
    state.new_cluster(did, dname, ids, name=label)
    ss["district"] = did; ss.focus = ids[0] if ids else None; ss.fit = ("cluster", ss.ver + 1)
    ss.notice = f"Opened “{label}”: the typical matching cluster in {dname}. Open the Map and selection tab to see it."
    state.bump()


def _m(x): return "—" if x is None else f"{x / 1e6:,.1f}"


def render(districts):
    ss = st.session_state
    st.markdown("### Compare districts")
    st.caption("Describe the kind of cluster you have in mind. The app looks for clusters like it in every district, with the same rules "
               "and the same model inputs, so differences come from the districts themselves: how dense they are, what mix of buildings they hold "
               "and which power company supplies them.")
    note("<b>Kai Tak is the reference case:</b> district cooling already exists there and connection is mandatory for non-domestic buildings, "
         "so it is left out of this comparison by default (you can add it). The districts compared are an old business district (Central and Western), "
         "a former industrial area becoming a business district (Kwun Tong) and a planned 1970s–80s new town (Sha Tin). More districts can be added "
         "without code changes.")
    with st.form("cmp_form"):
        c1, c2, c3, c4 = st.columns([1, 1.3, 1.5, 1.6])
        n = c1.number_input("Buildings per cluster", 2, 30, 6, 1, help="Every matched cluster has exactly this many buildings.")
        max_d = c2.slider("Max distance between buildings (m)", 100, 800, 300, 50,
                          help="Centre to centre, between any two members. 300 m matches the app's distance check.")
        floors = c3.slider("Floors", 1, 100, (1, 100), help="Only buildings in this storey range. Low-rise ≈ up to 10, high-rise ≈ 25 or more.")
        classes = c4.multiselect("Building types", CLASS_OPTS, ["Commercial", "Mixed-use"], help="Source building class (HK-BFETD).")
        c5, c6 = st.columns([2, 1])
        dsel = c5.multiselect("Districts", [d["id"] for d in districts], [d["id"] for d in districts if d.get("kind") != "study_area"],
                              format_func=lambda i: next(d["name"] for d in districts if d["id"] == i))
        k = c6.slider("Clusters per district (max)", 10, 50, 50, 5, help="Sample size for the pattern chart.")
        go_ = st.form_submit_button("Compare districts", type="primary")
    if go_: ss.cmp = dict(n=int(n), max_d=float(max_d), floors=tuple(floors), classes=tuple(classes), dids=list(dsel), k=int(k))
    p = ss.get("cmp")
    if not p:
        html('<div class="card"><div class="eyebrow">How it works</div><div class="sub">Set the cluster you are looking for and press '
             '<b>Compare districts</b>. You get (A) the typical matching cluster in each district, side by side, and (B) the spread of '
             'results over up to 50 matching clusters per district, to see the general pattern rather than one case.</div></div>')
        explain("districts", "ⓘ NPV saving, density, distribution"); return
    if not p["classes"] or not p["dids"]: st.warning("Choose at least one building type and one district."); return

    ov_json = json.dumps(ss.overrides, sort_keys=True)
    by = {d["id"]: d for d in districts}; out = {}; broken = []
    for did in p["dids"]:
        try: out[did] = _run(did, by[did].get("generated", ""), p["n"], p["max_d"], p["floors"], p["classes"], p["k"], ov_json, state.table_key(),
                             json.dumps(inputs.values(did), sort_keys=True))
        except Exception as e:                                   # a missing or altered package must not take the whole tab down
            broken.append(f"{by[did]['name']} ({type(e).__name__})")
    if broken: note("Skipped, because their data package could not be loaded: " + ", ".join(broken) + ". See the Data and assumptions tab.", "warn")
    p = dict(p, dids=[d for d in p["dids"] if d in out])
    if not p["dids"]: return
    explain("districts", "ⓘ NPV saving, density, distribution")

    # ---------------------------------------------------------------- A. typical cluster per district
    st.markdown("#### A. The typical matching cluster in each district")
    typ = {did: K.typical(out[did]["results"]) for did in p["dids"]}
    pc = lambda x: "—" if x is None else f"{x:.0%}"
    num = lambda x, f="{:,.1f}": "—" if x is None else f.format(x)
    M = [("Matching clusters found", lambda o, t: str(len(o["results"]))),
         ("District floor area: commercial", lambda o, t: pc(o["context"]["commercial_share"])),
         ("District floor area: mixed-use", lambda o, t: pc(o["context"]["mixed_share"])),
         ("District floor area: residential", lambda o, t: pc(o["context"]["residential_share"])),
         ("Typical cluster: mean floors", lambda o, t: num(t and t["mean_storeys"])),
         ("Typical cluster: commercial share", lambda o, t: pc(t and t["commercial_share"])),
         ("Typical cluster: cooling density (kW/ha)", lambda o, t: num(t and t["density_kw_ha"], "{:,.0f}")),
         ("Typical cluster: peak cooling (MW)", lambda o, t: num(t and t["peak_mw"], "{:,.2f}")),
         ("Typical cluster: inside a DCS area", lambda o, t: f"{t['in_dcs']} of {t['n']}" if t else "—"),
         ("Shared plant: NPV saving (HK$M)", lambda o, t: num(t and t["npv_cmcs"] / 1e6)),
         ("District cooling: NPV saving (HK$M)", lambda o, t: num(t and t["npv_dcs"] / 1e6)),
         ("Cheapest option", lambda o, t: OPTION_NAMES[t["best"]] if t else "no match")]
    import sources as SRC
    sup = lambda did: (lambda s_: f"{s_['name']} (HK${s_['tariff']:.2f}/kWh, {s_['emission_factor']:.2f} kg/kWh)")(SRC.supplier_for(did))
    tab = pd.DataFrame({by[did]["name"]: [sup(did)] + [fn(out[did], typ[did]) for _, fn in M] for did in p["dids"]},
                       index=["Power company (default)"] + [m for m, _ in M])
    st.dataframe(tab, width="stretch", height=36 * (len(tab) + 1) + 4)
    found = {d: t for d, t in typ.items() if t}
    if found:
        best = max(found, key=lambda d: found[d]["npv_cmcs_per_mw"])
        none = [by[d]["name"] for d in p["dids"] if not typ[d]]
        tb = found[best]; dens = f'{tb["density_kw_ha"] or 0:,.0f} kW/ha'
        if tb["npv_cmcs"] > 0: msg = f'a shared plant pays off best in <b>{by[best]["name"]}</b>: HK${tb["npv_cmcs"] / 1e6:,.1f}M saved over the period ({dens}).'
        else: msg = (f'a shared plant does not pay off in any district with these inputs; it comes closest in <b>{by[best]["name"]}</b> '
                     f'(still HK${-tb["npv_cmcs"] / 1e6:,.1f}M more than keeping individual plants; {dens}).')
        html(f'<div class="verdict small">For a typical cluster like this, {msg}' + (f' No matching cluster in {", ".join(none)}.' if none else "") + "</div>")
        st.caption("Typical = the cluster whose shared-plant saving per MW of peak is closest to that district's median, so one unusual group does not "
                   "carry the comparison. District floor-area shares use registered GFA where it exists, otherwise footprint × storeys.")
        cols = st.columns(len(found))
        for col, (did, t) in zip(cols, found.items()):
            col.button(f"Open {by[did]['name']}'s typical cluster on the map", key=f"open_{did}", on_click=_open,
                       args=(did, by[did]["name"], t["ids"], f"{by[did]['name']} typical"), width="stretch")
    else:
        st.info("No district has a cluster that matches. Try more distance, fewer buildings, a wider floor range or more building types.")

    # ---------------------------------------------------------------- B. pattern across all matching clusters
    st.markdown("#### B. The pattern across all matching clusters")
    c1, c2 = st.columns(2)
    opt = c1.radio("Option", ["CMCS", "DCS"], format_func=OPTION_NAMES.get, horizontal=True, key="cmp_opt")
    per = c2.radio("Show saving", ["per MW of peak cooling", "total for the cluster"], horizontal=True, key="cmp_per",
                   help="Per MW makes clusters of different sizes comparable.")
    metric = f"npv_{opt.lower()}" + ("_per_mw" if per.startswith("per") else ""); unit = "HK$M per MW" if per.startswith("per") else "HK$M"
    f = go.Figure()
    for did in p["dids"]:
        res = out[did]["results"]
        if not res: continue
        f.add_box(y=[x[metric] / 1e6 for x in res], name=f"{by[did]['name']} ({len(res)})", boxpoints="all", jitter=.45, pointpos=0,
                  marker=dict(color=OPTION_COLORS[opt], size=6, opacity=.65), line=dict(color=OPTION_COLORS[opt]), fillcolor="rgba(0,0,0,0)",
                  customdata=[[x["n"], x["mean_storeys"], x["density_kw_ha"] or 0, x["in_dcs"]] for x in res],
                  hovertemplate="%{y:,.1f} " + unit + "<br>%{customdata[0]} buildings · %{customdata[1]:.1f} floors avg<br>"
                                "%{customdata[2]:,.0f} kW/ha · %{customdata[3]} inside DCS area<extra></extra>")
    f.add_hline(y=0, line_color="#2C3E50", line_dash="dot", annotation_text="break-even", annotation_position="top left")
    f.update_layout(title=f"{OPTION_NAMES[opt]}: NPV saving vs keeping individual plants ({unit})", yaxis_title=unit)
    st.plotly_chart(layout(f, 420), width="stretch")
    srows = []
    for did in p["dids"]:
        s = K.summarise(out[did]["results"], metric)
        if not s["n"]: srows.append({"District": by[did]["name"], "Clusters": 0}); continue
        srows.append({"District": by[did]["name"], "Clusters": s["n"], "Pool of matching buildings": out[did]["pool"],
                      "Shared plant pays in": s["share_cmcs_pays"], "District cooling pays in": s["share_dcs_pays"],
                      f"Median ({unit})": s["median"] / 1e6, f"Middle half ({unit})": f"{s['q1'] / 1e6:,.1f} to {s['q3'] / 1e6:,.1f}",
                      f"Range ({unit})": f"{s['lo'] / 1e6:,.1f} to {s['hi'] / 1e6:,.1f}"})
    st.dataframe(pd.DataFrame(srows).set_index("District").style.format({"Shared plant pays in": "{:.0%}", "District cooling pays in": "{:.0%}",
                                                                          f"Median ({unit})": "{:,.1f}"}, na_rep="—"), width="stretch")
    note("Each dot is one matched cluster. Clusters never share a building, and their seeds are spread across the district in a fixed "
         "pseudo-random order, so the sample is repeatable and not biased toward the biggest buildings. <b>Pays in</b> = share of clusters whose NPV saving "
         "is above zero. Loads and most costs are illustrative placeholders, so read the <b>differences between districts</b> (driven by real density and "
         "building mix), not the absolute amounts. Outside a DCS service area the district cooling result is hypothetical.")
