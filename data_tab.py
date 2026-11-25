"""Data and assumptions: provenance, validation, DCS tariffs, editable use defaults, cluster import, method and limits."""
import pandas as pd
import streamlit as st
import clusters as C
from ui import state
from ui.style import note

METHOD = """**Demand.** Cooled area = GFA × cooled share; peak kW = cooled area × W/m² ÷ 1,000; annual cooling = peak × full-load hours. GFA is the registered value
if present, otherwise an **estimate** (footprint × storeys). Loads, hours and cooled share default by use (share-weighted for mixed buildings) and are **assumptions**.

**Keep individual plants (reference).** Today's chillers run at the existing COP until their remaining life ends, then are replaced (cost per kW, replacement COP) every chiller life.
**Shared plant (private).** A privately developed central plant sized at peak × diversity, a pipe network (spanning tree between building centres × route factor, or a typed length)
and a connection per building. Electricity = cooling ÷ (1 − loss) ÷ plant COP × (1 + pumping share). Plant and network are replaced at the end of their lives.
**Public district cooling.** Building-side works per building and per kW. Bill = contract capacity (peak × contract factor) × capacity rate × 12 + cooling kWh × consumption rate
(EMSD tariff). Buildings pay only for their own pumping electricity; the DCS plant's electricity (cooling ÷ DCS plant COP) is **attributed** to the cluster for emissions only.

**Finance.** Real HK$, investment in year 0, operation in years 1–N, end-of-year discounting. Residual value = straight-line remaining life of the latest assets, credited in year N
in every option. Saving = PV(keep individual plants) − PV(option). Discounted payback = first year the cumulative discounted saving turns positive. Levelised cost = PV cost ÷ PV cooling.

**Distance check.** Edge-to-edge distances between footprints in Hong Kong 1980 Grid metres (EPSG:2326). Over the limit = a flag, never a block."""


def render(meta, DD, districts):
    ss = st.session_state; m = DD["manifest"]
    st.markdown("### Data provenance")
    a, b, c, d = st.columns(4)
    a.metric("District", m["district"]["name"]); b.metric("Buildings", f"{m['counts']['buildings']:,}"); c.metric("Area status", m["district"]["status"]); d.metric("CRS", m["crs"])
    st.write(m["district"].get("description", ""))
    st.markdown(f"Source: **{m['sources']['geojson']['name']}** (SHA-256 `{m['sources']['geojson']['sha256'][:16]}…`), {m['sources']['features_total']:,} buildings "
                f"Hong Kong-wide. Package built {m['generated']['utc']} by `{m['generated']['script']}` v{m['generated']['version']}; its files are re-checked "
                "against their fingerprints every time it loads.")
    st.caption(m["sources"]["licence_note"]); st.caption("Assignment rule: " + m["area_definition"]["assignment_rule"])
    with st.expander("Validation report"):
        st.dataframe(pd.DataFrame(m["validation"]["checks"]).assign(passed=lambda x: x.passed.map({True: "PASS", False: "FAIL"})), hide_index=True, width="stretch")
    note("<b>Source</b> = value from HK-BFETD or EMSD. <b>Estimate</b> = calculated from source values (GFA = footprint × storeys). <b>Assumption</b> = placeholder default. "
         "<b>Your value</b> = a value you typed. Source data are never changed.")

    st.markdown("### Public district cooling: systems and tariffs")
    reg, _, _ = state.dcs_data()
    st.dataframe(pd.DataFrame([{"System": s["name"], "Status": s["status"],
                                **{f"{y} capacity (HK$/kW/month)": v["capacity_hkd_per_kwr_month"] for y, v in s["rates"].items()},
                                **{f"{y} consumption (HK$/kWh)": v["consumption_hkd_per_kwhr"] for y, v in s["rates"].items()}} for s in reg["systems"]]),
                 hide_index=True, width="stretch")
    st.caption(f"[{reg['source']['title']}]({reg['source']['url']}), accessed {reg['source']['accessed']}. {reg['source']['notes']}")
    st.caption(next(s for s in reg["systems"] if s["id"] == "kai_tak")["service_area"]["basis"])
    for s_ in reg["systems"]:
        rule = s_.get("connection_rule")
        if rule: note(f"<b>{s_['name']}: connection rule.</b> {rule['text']} Source: <a href='{rule['url']}'>{rule['source']}</a>.")

    st.markdown("### Cooling intensity by use (illustrative placeholders)")
    st.caption("Not sourced, not Hong Kong statistics. Mixed buildings use the share-weighted average of their listed uses. Edits apply to every building "
               "without its own value.")
    rows = pd.DataFrame([{"Use": k, "Peak load (W/m²)": v[0], "Full-load hours/yr": v[1], "Cooled share": v[2]} for k, v in ss.use_table.items()])
    ed = st.data_editor(rows, hide_index=True, disabled=["Use"], key=f"use_ed_{ss.ver}", width="stretch")
    new = {r["Use"]: [float(r["Peak load (W/m²)"]), float(r["Full-load hours/yr"]), float(r["Cooled share"])] for _, r in ed.iterrows()}
    if new != ss.use_table: ss.use_table = new; state.bump(); st.rerun()
    st.caption(f"Uses not listed fall back to {C.FALLBACK[0]} W/m², {C.FALLBACK[1]:,} h/yr, cooled share {C.FALLBACK[2]}.")
    if st.button("Reset use defaults", key="rs_use"): ss.use_table = {k: list(v) for k, v in C.USE_DEFAULTS.items()}; state.bump(); st.rerun()

    st.markdown("### Clusters: import")
    st.caption("Export is in the sidebar. Imported clusters are matched to prepared districts; unknown buildings are dropped and reported.")
    up = st.file_uploader("Import clusters (JSON)", type="json", key="cl_up")
    if up is not None and ss.get("_imported") != up.name + str(up.size):
        known = {d["id"]: set(state.district_data(d["id"], d.get("generated", ""))["by_id"]) for d in districts}
        cl, probs = C.clusters_from_json(up.getvalue().decode("utf-8"), known); ss["_imported"] = up.name + str(up.size)
        for n, c in cl.items(): state.new_cluster(c["district"], n, c["ids"], name=n)
        st.success(f"Imported {len(cl)} cluster(s).")
        for p in probs: st.warning(p)

    st.markdown("### Where every input comes from")
    import sources as SRC
    st.caption("Published = stated by a utility, EMSD, the Building Energy Code or ASHRAE. Judgement = depends on the project or a view of the future; "
               "change them on the Inputs tab.")
    st.dataframe(pd.DataFrame([{"Input": k, "Kind": "Published", "Basis": v[0], "Source": v[1]} for k, v in SRC.PUBLISHED.items()]
                              + [{"Input": k, "Kind": "Judgement", "Basis": v[0], "Source": v[1]} for k, v in SRC.JUDGEMENT.items()]),
                 hide_index=True, width="stretch", column_config={"Source": st.column_config.LinkColumn("Source")})
    st.markdown("### Building features and how each is obtained")
    st.dataframe(pd.DataFrame(SRC.BUILDING_FEATURES, columns=["Feature", "Status", "Origin"]), hide_index=True, width="stretch")
    st.markdown("### Glossary: finance and engineering terms")
    import glossary as G
    st.caption("The same explanations open from the ⓘ buttons next to results.")
    st.dataframe(pd.DataFrame([{"Term": t, "What it is": w, "Why it matters here": y} for t, w, y in G.TERMS.values()]),
                 hide_index=True, width="stretch")
    st.markdown("### Method and limits")
    st.markdown(METHOD)
    st.markdown("""**Not in the supplied data, so never shown as facts:** registered GFA (11 of the 29,387 prepared buildings), cooling loads, operating hours,
plant age, type or efficiency, DCS pipe routes, building-level use areas. Floors and heights come from HK-BFETD; their origin is not documented in the files.
The BDBIAR year is an approval year, not plant age.
**Initial screening only:** no hourly load profiles, part-load curves, tax, financing or land cost, or capacity-overrun charges; straight-line distances ignore streets,
utilities and terrain. Not an engineering feasibility study.""")
