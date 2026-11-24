"""Cluster assessment: characteristics, composition, proximity, editable inputs for every building, and comparison of all clusters."""
import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import clusters as C
import lifecycle as L
from buildings import EDITABLE
from model import validate
from ui import state, inputs
from ui.style import note, layout, status_label, mhk, yrs, TEAL, OPTION_NAMES, OPTION_COLORS

LAB = {"gfa_m2": "GFA (m²)", "cooled_fraction": "Cooled share", "load_w_m2": "Peak load (W/m²)", "hours": "Full-load hours/yr", "cop_existing": "Existing COP"}


def single(meta, DD, cl, G, A, EXCL):
    ss = st.session_state
    if not cl["ids"]:
        st.info("No buildings selected yet. Pick or build a cluster in the sidebar, or select buildings on the Map and selection tab."); return
    members = [DD["by_id"][i] for i in cl["ids"]]
    a = C.aggregates(members, ss.overrides, inputs.global_defaults(), state.table())
    ha = (G.get("hull_area_m2") or 0) / 1e4
    k = st.columns(6)
    k[0].metric("Buildings", f"{a['n_included']} of {a['n']}", f"{a['n'] - a['n_included']} excluded" if a["n"] != a["n_included"] else None, delta_color="off")
    k[1].metric("GFA", f"{a['gfa_m2'] / 1e3:,.0f}k m²", f"{a['gfa_estimated_share']:.0%} estimated" if a["gfa_estimated_share"] is not None else None, delta_color="off")
    k[2].metric("Peak cooling (est.)", f"{a['peak_kw'] / 1000:,.1f} MW")
    k[3].metric("Annual demand (est.)", f"{a['cooling_kwh'] / 1e6:,.1f} GWh")
    k[4].metric("Cooling density (est.)", f"{a['peak_kw'] / ha:,.0f} kW/ha" if ha > 0.01 else "n/a", help="Peak cooling per hectare of the convex hull of the selected footprints.")
    k[5].metric("Pipe length", f"{A.network_m:,.0f} m", "from selection" if inputs.use_mst() else "typed", delta_color="off",
                help="Minimum spanning tree between building centres × route factor. A screening proxy that ignores streets and plant location.")
    note("Source data: footprint, storeys, height, type and use shares. <b>Estimates</b>: GFA (footprint × storeys unless registered or overridden), "
         "cooled area, peak load and hours (illustrative use defaults or your values). Nothing here is a measured cooling demand.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Composition by cooled area**")
        mix = a["cooled_by_class"]
        if mix:
            f = go.Figure(go.Bar(y=list(mix), x=[v / 1e3 for v in mix.values()], orientation="h", marker_color=TEAL))
            f.update_layout(xaxis_title="Cooled area (thousand m²)", yaxis=dict(autorange="reversed"))
            st.plotly_chart(layout(f, 240), width="stretch")
        extra = []
        if a["max_height_m"]: extra.append(f"tallest {a['max_height_m']:.0f} m")
        if a["mean_storeys"]: extra.append(f"mean {a['mean_storeys']:.1f} storeys")
        st.caption(" · ".join(extra))
        if len(A.buildings) > 1 and a["peak_kw"]:
            big = max(A.buildings, key=lambda b: b[1] * b[2]); share = big[1] * big[2] / 1000 * A.demand_scale / a["peak_kw"]
            if share > .5: note(f"{big[0]} is {share:.0%} of the cluster's peak. Check its GFA: footprint × storeys overstates large low-rise complexes. "
                                "Set a better value in the table below.", "warn")
    with c2:
        st.markdown(f"**Proximity screening ({inputs.max_m():,.0f} m)**")
        p = G.get("proximity")
        if len(members) < 2: st.caption("Select at least two buildings.")
        elif p.get("skipped"): st.caption("Cluster too large for the pairwise check.")
        elif p["within_limit"]: st.success(f"No pair of the {p['n']} buildings is more than {inputs.max_m():,.0f} m apart (edge to edge; widest {p['max_distance_m']:,.0f} m).")
        else:
            st.warning(f"{p['n_pairs_over_limit']} pair(s) exceed {inputs.max_m():,.0f} m; {len(G.get('isolated', []))} building(s) have no other selected "
                       f"building within {inputs.max_m():,.0f} m. Selection is not blocked.")
            nm = lambda i: DD["by_id"][i].name
            st.dataframe(pd.DataFrame([{"Building A": nm(x), "Building B": nm(y), "Distance (m)": round(d)} for x, y, d in p["pairs_over_limit"][:15]]),
                         hide_index=True, width="stretch")
        st.caption("Initial spatial screening indicator, not a definitive engineering limit.")
        cov = state.coverage(meta["id"], tuple(cl["ids"]), meta.get("generated", ""))
        n_dcs = sum(cov.values())
        st.markdown("**Public district cooling coverage**")
        st.caption(f"{n_dcs} of {len(members)} building(s) lie inside an existing DCS service area (approximated by the Kai Tak OZP boundary)."
                   + ("" if n_dcs == len(members) else " For the others the district cooling result is hypothetical."))
    st.markdown("**Buildings and cooling inputs** (edit any value: it becomes *Your value* for that building only)")
    rows = []
    for r in members:
        f, pk, _ = C.building_inputs(r, ss.overrides, inputs.global_defaults(), state.table())
        rows.append({"id": r.building_id, "Name": r.name, "Type": C.main_class(r), **{LAB[k]: f[k].value for k in EDITABLE},
                     **{f"{LAB[k]} basis": status_label(f[k].status) for k in ("gfa_m2", "load_w_m2", "hours")}, "Peak (kW, est.)": pk})
    CI = pd.DataFrame(rows).set_index("id")
    ed = st.data_editor(CI, key=f"ci_{ss.active[meta['id']]}_{ss.ver}", width="stretch",
                        disabled=["Name", "Type", "Peak (kW, est.)"] + [c for c in CI.columns if c.endswith("basis")],
                        column_config={**{LAB[k]: st.column_config.NumberColumn(LAB[k], min_value=0.0) for k in EDITABLE},
                                       "Peak (kW, est.)": st.column_config.NumberColumn(format="%.0f")})
    changed = False
    for k in EDITABLE:
        diff = ed[LAB[k]].astype(float).fillna(-1) != CI[LAB[k]].astype(float).fillna(-1)
        for i in ed.index[diff]:
            v = ed.at[i, LAB[k]]
            if v is None or (isinstance(v, float) and math.isnan(v)): ss.overrides.get(i, {}).pop(k, None)
            else: ss.overrides.setdefault(i, {})[k] = float(v)
            changed = True
    if changed: state.bump(); st.rerun()
    if EXCL: note(f"{len(EXCL)} building(s) have missing inputs and are left out of every total rather than given a guessed value: "
                  + ", ".join(n for _, n, _ in EXCL[:10]), "warn")
    if st.button("Reset all edits in this cluster", key="rs_cluster", disabled=not any(i in ss.overrides for i in cl["ids"])):
        for i in cl["ids"]: ss.overrides.pop(i, None)
        state.bump(); st.rerun()


def compare(districts):
    ss = st.session_state; dname = {d["id"]: d for d in districts}
    st.markdown("### Compare clusters")
    rows = []
    for n, c in ss.clusters.items():
        if not c["ids"] or c["district"] not in dname: continue
        stamp = dname[c["district"]].get("generated", "")
        a_, ex_, g_ = inputs.assumptions_for(c["district"], c["ids"], stamp)
        if not a_.buildings or validate(a_): continue
        r_ = L.evaluate(a_); s_ = r_["scenarios"]; cv = state.coverage(c["district"], tuple(c["ids"]), stamp)
        ha = (g_.get("hull_area_m2") or 0) / 1e4
        rows.append({"Cluster": n, "District": dname[c["district"]]["name"], "Buildings": len(c["ids"]), "Peak (MW, est.)": r_["peak_kw"] / 1e3,
                     "Density (kW/ha)": r_["peak_kw"] / ha if ha > .01 else None, "Pipe (m)": a_.network_m,
                     "Widest gap (m)": (g_.get("proximity") or {}).get("max_distance_m"), "In DCS area": f"{sum(cv.values())}/{len(c['ids'])}",
                     "Cheapest": OPTION_NAMES[r_["best"]], **{f"PV {OPTION_NAMES[k]} (HK$M)": s_[k]["pv_cost"] / 1e6 for k in L.SCENARIOS},
                     "NPV shared plant (HK$M)": s_["CMCS"]["npv_saving"] / 1e6, "NPV district cooling (HK$M)": s_["DCS"]["npv_saving"] / 1e6,
                     "Payback shared plant (yrs)": s_["CMCS"]["discounted_payback"], "Payback district cooling (yrs)": s_["DCS"]["discounted_payback"]})
    if not rows:
        st.caption("Build two or more clusters (New cluster or Find candidate clusters in the sidebar, in any district) to compare them side by side."); return
    d = pd.DataFrame(rows).set_index("Cluster")
    st.dataframe(d.style.format({c: "{:,.1f}" for c in d.columns if d[c].dtype.kind == "f"}, na_rep="–"), width="stretch")
    f = go.Figure()
    for k in L.SCENARIOS:
        f.add_bar(x=d.index, y=d[f"PV {OPTION_NAMES[k]} (HK$M)"] / d["Peak (MW, est.)"], name=OPTION_NAMES[k], marker_color=OPTION_COLORS[k])
    f.update_layout(barmode="group", title="Lifecycle cost per MW of peak cooling (HK$M per MW, present value)")
    st.plotly_chart(layout(f, 360, True), width="stretch")
    st.download_button("Download comparison (CSV)", d.to_csv().encode("utf-8-sig"), "cluster_comparison.csv", "text/csv", key="dl_cmp")
    st.caption("Same inputs for every cluster; pipe length derived per cluster. Loads are placeholders, so read differences between clusters, not absolute values.")


def render(meta, DD, cl, G, A, EXCL, districts):
    single(meta, DD, cl, G, A, EXCL); compare(districts)
    if cl["ids"]: st.caption("Next: the Compare options tab shows which option is cheapest for this cluster.")
