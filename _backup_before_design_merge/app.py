"""HK Cooling Investment Screener: Hong Kong > District > Cluster > Buildings.
Compares Individual building plants, a shared CMCS plant and a government DCS connection for a user-defined cluster
of real HK-BFETD buildings. Run:  streamlit run app.py"""
import json, math
from dataclasses import replace, fields as dc_fields
from pathlib import Path

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium

import clusters as C
import districts as D
import lifecycle as L
import overlays as O
from buildings import EDITABLE, resolve
from model import Assumptions, validate

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="HK Cooling Investment Screener", page_icon="❄", layout="wide")
INK, TEAL, AMBER, SLATE, BLUE, RED = "#14232B", "#0E6E73", "#C98A1B", "#7C8C94", "#2F6DB5", "#B3412E"
SCOL = {"Individual": SLATE, "CMCS": AMBER, "DCS": TEAL}
SNAME = {"Individual": "Individual building plants", "CMCS": "Shared CMCS plant", "DCS": "Government DCS connection"}
MAX_FEATURES = 5000
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:wght@500;600&family=Public+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"] {font-family:'Public Sans',sans-serif;}
h1,h2,h3 {font-family:'Newsreader',serif !important; color:#14232B; letter-spacing:-.01em;}
.verdict {font-family:'Newsreader',serif; font-size:1.9rem; line-height:1.25; max-width:52ch; margin:.2rem 0 .6rem;}
.note {border-left:3px solid #C98A1B; padding:.5rem .9rem; background:#fff; font-size:.92rem; margin:.4rem 0;}
.warn {border-left:3px solid #B3412E; padding:.5rem .9rem; background:#fff; font-size:.92rem; margin:.4rem 0;}
.badge {display:inline-block; padding:0 .45rem; border-radius:3px; font-size:.75rem; font-weight:600; color:#fff;}
.b-source{background:#0E6E73}.b-derived{background:#2F6DB5}.b-assumption{background:#C98A1B}.b-override{background:#7A3E9D}.b-missing{background:#B3412E}
.legend span.sw {display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:6px;vertical-align:-1px}
[data-testid="stMetric"] {background:#fff; padding:.7rem .9rem; border-radius:6px;}
@media (max-width:640px){.verdict{font-size:1.4rem}}
</style>""", unsafe_allow_html=True)


def badge(status): return f'<span class="badge b-{status}">{status}</span>'
def mhk(x): return "n/a" if x is None else f"HK${x / 1e6:,.1f}M"
def yrs(x): return "not within period" if x is None else f"{x:.1f} yrs"


# =============================================================================================== cached data
@st.cache_resource(show_spinner="Loading and verifying district package ...")
def district_data(did):
    recs, rep = D.load_district(did)                       # verifies SHA-256 against the manifest
    wgs = O.rings_to_wgs84([r.footprint_hk80 for r in recs])
    cen = O.rings_to_wgs84([[r.centroid_hk80] for r in recs])
    recs = [replace(r, footprint=tuple(w), lon=c[0][0], lat=c[0][1]) for r, w, c in zip(recs, wgs, cen)]
    bnd = O.district_boundary(D.ROOT_DIR / did)
    return dict(recs=recs, by_id={r.building_id: r for r in recs}, rep=rep, idx=C.SpatialIndex(recs), boundary=bnd,
                boundary_wgs=[[O.to_wgs84_ring(o)] + [O.to_wgs84_ring(h) for h in hs] for o, hs in bnd])


@st.cache_resource
def dcs_data():
    reg = C.load_dcs(); areas = {}
    for s in reg["systems"]:
        if s.get("service_area"): areas[s["id"]] = O.polygons_from_file(ROOT / s["service_area"]["file"])
    wgs = {k: [[O.to_wgs84_ring(o)] + [O.to_wgs84_ring(h) for h in hs] for o, hs in v] for k, v in areas.items()}
    return reg, areas, wgs


@st.cache_resource
def zone_data():
    return [(lab, desc, [[O.to_wgs84_ring(o)] + [O.to_wgs84_ring(h) for h in hs] for o, hs in polys]) for lab, desc, polys in O.ozp_zones()]


@st.cache_data(show_spinner=False)
def geo_summary(did, ids, max_m, route_factor):
    by = district_data(did)["by_id"]
    g = C.geometry_summary([by[i] for i in ids], max_m, route_factor)
    if g.get("n"): g["hull_wgs"] = O.to_wgs84_ring(g["hull_hk80"])
    return g


@st.cache_data(show_spinner=False)
def coverage(did, ids):
    _, areas, _ = dcs_data(); by = district_data(did)["by_id"]
    return C.dcs_coverage([by[i] for i in ids], areas), None


districts = D.list_districts()
if not districts:
    st.error("No prepared district packages found in data/districts. Run tools/prepare_districts.py (see docs/DATA_PREP.md)."); st.stop()
DNAME = {d["id"]: d for d in districts}

# =============================================================================================== session state
ss = st.session_state
ss.setdefault("clusters", {})          # name -> {"district": id, "ids": [building ids]}
ss.setdefault("active", {})            # district id -> active cluster name
ss.setdefault("overrides", {})         # building id -> {field: value}
ss.setdefault("seen_click", None); ss.setdefault("seen_draw", None); ss.setdefault("ver", 0); ss.setdefault("focus", None)
ss.setdefault("fit", None)

A0 = Assumptions()
AKEYS = [f.name for f in dc_fields(Assumptions) if f.name not in ("buildings", "horizon_years")]


def cluster_names(did): return [n for n, c in ss.clusters.items() if c["district"] == did]


def new_cluster(did, name=None, ids=()):
    base = name or f"{DNAME[did]['name']} cluster"; n, k = base, 2
    while n in ss.clusters: n, k = f"{base} {k}", k + 1
    ss.clusters[n] = {"district": did, "ids": list(ids)}; ss.active[did] = n; return n


def bump(): ss.ver += 1


# =============================================================================================== sidebar
with st.sidebar:
    st.markdown("### Where")
    did = st.selectbox("District", [d["id"] for d in districts], key="district",
                       index=[d["id"] for d in districts].index("kai_tak") if "kai_tak" in DNAME else 0,
                       format_func=lambda i: f"{DNAME[i]['name']} ({DNAME[i]['buildings']:,} buildings)")
    DD = district_data(did)
    if not cluster_names(did): new_cluster(did)
    names = cluster_names(did)
    if ss.active.get(did) not in names: ss.active[did] = names[0]
    act = st.selectbox("Cluster", names, index=names.index(ss.active[did]), key=f"cl_sel_{did}_{ss.ver}")
    ss.active[did] = act
    CL = ss.clusters[act]
    c1, c2 = st.columns(2)
    if c1.button("New cluster", width="stretch"): new_cluster(did); bump(); st.rerun()
    if c2.button("Delete", width="stretch", disabled=len(ss.clusters) < 1):
        del ss.clusters[act]; ss.active.pop(did, None); bump(); st.rerun()
    with st.expander("Rename / suggest / clear"):
        nn = st.text_input("Rename cluster", act, key=f"rn_{act}_{ss.ver}")
        if nn.strip() and nn != act and st.button("Apply name"):
            if nn in ss.clusters: st.warning("That name is taken.")
            else: ss.clusters[nn] = ss.clusters.pop(act); ss.active[did] = nn; bump(); st.rerun()
        if st.button("Suggest a starter cluster", help="Largest-demand commercial or mixed-use building plus the largest such buildings within 300 m of it. A suggestion only; edit it freely."):
            CL["ids"] = C.starter_cluster(DD["recs"], ss.overrides); bump(); st.rerun()
        if st.button("Clear this cluster"): CL["ids"] = []; bump(); st.rerun()

    st.markdown("### Assumptions")
    st.caption("Badges: **source** = EMSD / dataset value; everything else is an illustrative placeholder to replace.")
    if st.button("Reset assumptions and building edits"):
        for k in list(ss.keys()):
            if k.startswith("a_"): del ss[k]
        ss.overrides = {}; bump(); st.rerun()

    def num(label, key, lo, hi, step, fmt="%.2f", help=None, scale=1.0):
        v = getattr(A0, key) * scale
        x = st.number_input(label, float(lo), float(hi), float(v), float(step), format=fmt, key="a_" + key, help=help)
        return x / scale

    def inum(label, key, lo, hi, help=None):
        return int(st.number_input(label, lo, hi, int(getattr(A0, key)), 1, key="a_" + key, help=help))

    V = {}
    with st.expander("Energy, carbon and finance", True):
        V["tariff"] = num("Electricity tariff (HK$/kWh)", "tariff", 0.1, 10, 0.05, help="Illustrative. Use your CLP / HK Electric commercial tariff.")
        V["emission_factor"] = num("Grid emission factor (kgCO₂e/kWh)", "emission_factor", 0, 2, 0.01, help="Illustrative. Use the utility's published factor.")
        V["discount_rate"] = num("Real discount rate (%)", "discount_rate", -4, 40, 0.5, "%.1f", scale=100)
        V["analysis_years"] = inum("Analysis period (years)", "analysis_years", 1, 60)
        V["elec_escalation"] = num("Real electricity price change (%/yr)", "elec_escalation", -10, 10, 0.5, "%.1f", scale=100)
        V["demand_scale"] = num("Scale all cooling demand (%)", "demand_scale", 30, 200, 5, "%.0f", scale=100)
    with st.expander("Individual building plants (reference)"):
        V["cop_existing"] = num("Existing system COP (default for all buildings)", "cop_existing", 1, 10, 0.1, "%.1f",
                                help="Seasonal coefficient of performance. Per-building values can be edited in Buildings.")
        V["existing_remaining_life"] = inum("Remaining life of existing chillers (years)", "existing_remaining_life", 0, 60)
        V["cop_upgrade"] = num("Replacement chiller COP", "cop_upgrade", 1, 10, 0.1, "%.1f")
        V["upgrade_capex_kw"] = num("Replacement cost (HK$/kW)", "upgrade_capex_kw", 0, 50000, 100, "%.0f")
        V["equipment_life"] = inum("Chiller life (years)", "equipment_life", 1, 60)
        V["maint_existing_kw"] = num("Maintenance, existing (HK$/kW/yr)", "maint_existing_kw", 0, 5000, 10, "%.0f")
        V["maint_upgrade_kw"] = num("Maintenance, replaced (HK$/kW/yr)", "maint_upgrade_kw", 0, 5000, 10, "%.0f")
    with st.expander("CMCS shared plant"):
        V["cop_central"] = num("Central plant COP", "cop_central", 1, 10, 0.1, "%.1f")
        V["diversity"] = num("Peak diversity (plant size / sum of peaks)", "diversity", 0.4, 1.0, 0.01)
        V["central_capex_kw"] = num("Plant cost (HK$/kW)", "central_capex_kw", 0, 50000, 100, "%.0f")
        V["plant_life"] = inum("Plant life (years)", "plant_life", 1, 60)
        V["pump_share"] = num("Pumping energy (% of plant)", "pump_share", 0, 30, 1, "%.0f", scale=100)
        V["network_loss"] = num("Distribution loss (%)", "network_loss", 0, 30, 1, "%.0f", scale=100)
        V["network_cost_m"] = num("Pipe cost (HK$/m)", "network_cost_m", 0, 200000, 500, "%.0f")
        V["cmcs_route_factor"] = num("Pipe route / spanning-tree length", "cmcs_route_factor", 1, 3, 0.05,
                                     help="The network length is DERIVED from the buildings' positions (minimum spanning tree) times this factor.")
        net_override = st.checkbox("Override network length", key="a_net_ovr")
        net_m = st.number_input("Network length (m)", 0.0, 50000.0, float(A0.network_m), 50.0, key="a_net_m", disabled=not net_override)
        V["connection_cost"] = num("Connection per building (HK$)", "connection_cost", 0, 50e6, 50000, "%.0f")
        V["maint_central_plant_kw"] = num("Plant maintenance (HK$/kW/yr)", "maint_central_plant_kw", 0, 5000, 10, "%.0f")
        V["maint_network_pct"] = num("Network maintenance (% of capex/yr)", "maint_network_pct", 0, 10, 0.1, "%.1f", scale=100)
        V["network_life"] = inum("Network life (years)", "network_life", 1, 100)
    reg, dcs_areas, dcs_wgs = dcs_data()
    with st.expander("DCS connection"):
        sysopt = {s["id"]: s for s in reg["systems"]}
        dsys = st.selectbox("Tariff of", list(sysopt), format_func=lambda k: sysopt[k]["name"], key="a_dcs_sys")
        yr = st.selectbox("Tariff year", list(sysopt[dsys]["rates"]), index=len(sysopt[dsys]["rates"]) - 1, key="a_dcs_year")
        rate = sysopt[dsys]["rates"][yr]
        st.markdown(f"{badge('source')} EMSD {yr}: HK${rate['capacity_hkd_per_kwr_month']}/kW·month, HK${rate['consumption_hkd_per_kwhr']}/kWh",
                    unsafe_allow_html=True)
        V["dcs_capacity_rate"] = st.number_input("Capacity charge (HK$/kW refrigeration/month)", 0.0, 1000.0,
                                                 float(rate["capacity_hkd_per_kwr_month"]), 1.0, key=f"a_dcs_cap_{dsys}_{yr}")
        V["dcs_consumption_rate"] = st.number_input("Consumption charge (HK$/kWh refrigeration)", 0.0, 5.0,
                                                    float(rate["consumption_hkd_per_kwhr"]), 0.005, format="%.4f", key=f"a_dcs_use_{dsys}_{yr}")
        V["dcs_capacity_escalation"] = num("Real capacity-charge change (%/yr)", "dcs_capacity_escalation", -10, 10, 0.5, "%.1f", scale=100)
        V["dcs_contract_factor"] = num("Contract capacity / building peak", "dcs_contract_factor", 0.5, 1.5, 0.05)
        V["dcs_connection_cost"] = num("Building-side works per building (HK$)", "dcs_connection_cost", 0, 50e6, 50000, "%.0f")
        V["dcs_building_capex_kw"] = num("Secondary-side modification (HK$/kW)", "dcs_building_capex_kw", 0, 20000, 50, "%.0f")
        V["dcs_building_life"] = inum("Building-side equipment life (years)", "dcs_building_life", 1, 60)
        V["dcs_maint_kw"] = num("Building-side maintenance (HK$/kW/yr)", "dcs_maint_kw", 0, 2000, 5, "%.0f")
        V["dcs_aux_kwh_per_kwh"] = num("Building pumping (kWh per kWh cooling)", "dcs_aux_kwh_per_kwh", 0, 0.2, 0.005, "%.3f")
        V["dcs_plant_cop"] = num("DCS plant COP (for attributed emissions only)", "dcs_plant_cop", 1, 10, 0.1, "%.1f")
    with st.expander("Cluster rule"):
        max_m = st.number_input("Proximity warning distance (m)", 50.0, 2000.0, 300.0, 25.0, key="a_maxm",
                                help="Buildings further apart than this (edge to edge) trigger a warning, never a block.")

GLOBAL_DEFAULTS = {"cop_existing": V["cop_existing"]}

# =============================================================================================== cluster inputs
recs_all, by_id = DD["recs"], DD["by_id"]
CL["ids"] = [i for i in CL["ids"] if i in by_id]
members = [by_id[i] for i in CL["ids"]]
member_set = set(CL["ids"])


def assumptions_for(did_, ids, V=V):
    recs = [district_data(did_)["by_id"][i] for i in ids]
    b, excl = C.to_model(recs, ss.overrides, GLOBAL_DEFAULTS)
    g = geo_summary(did_, tuple(ids), max_m, V["cmcs_route_factor"]) if ids else {"n": 0}
    nm = net_m if net_override else (g.get("network_m") or 0.0)
    return replace(A0, buildings=b, network_m=nm, **V), excl, g


A, EXCL, G = assumptions_for(did, CL["ids"])

# =============================================================================================== header + tabs
st.title("HK Cooling Investment Screener")
st.caption(f"Hong Kong › {DNAME[did]['name']} › {act} › {len(members)} building(s).  Screening tool, not a feasibility study.")
VIEWS = ["Start here", "Map & cluster", "Buildings", "Results", "Sensitivity", "Compare clusters", "Method & data"]
view = st.radio("View", VIEWS, horizontal=True, key="view", label_visibility="collapsed")
st.divider()

if view == "Start here":
    st.markdown("### What this tool does")
    st.write("Pick a district, draw or click a cluster of real buildings on the map, then compare three ways to cool them "
             "over their life: each building keeps its own chillers (**Individual**), the buildings share a privately built "
             "central plant and pipe network (**CMCS**), or they connect to a government **District Cooling System** and pay "
             "the published EMSD tariff.")
    st.markdown("""1. **Sidebar:** choose the district and a cluster (or *Suggest a starter cluster*).
2. **Map & cluster:** click buildings to add or remove them, or draw a polygon / rectangle to add everything inside.
3. **Buildings:** filter, search, sort, tick buildings in or out, edit any building's inputs, export CSV or GeoJSON.
4. **Results:** lifecycle cost, NPV, payback and emissions of the three options. **Sensitivity:** what changes the answer.
5. **Compare clusters:** every cluster you have built, side by side.""")
    st.markdown('<div class="note">Building footprints, heights, floors and uses come from HK-BFETD v1.1. Gross floor area is '
                '<b>estimated</b> (footprint × floors) because registered GFA is almost never present. Cooling loads, hours, COPs '
                'and costs are <b>illustrative placeholders</b>. Only the DCS tariff is a published figure (EMSD).</div>', unsafe_allow_html=True)
    st.markdown("**Status labels used everywhere:** " + " ".join(badge(s) for s in ("source", "derived", "assumption", "override", "missing")),
                unsafe_allow_html=True)

# =============================================================================================== map
if view == "Map & cluster":
    left, right = st.columns([3, 1.15])
    with right:
        st.markdown("**Map layers**")
        show_uses = st.multiselect("Show building classes", list(C.USE_COLOURS), ["Commercial", "Mixed-use"], key="m_uses")
        show_dcs = st.checkbox("Existing DCS service area (Kai Tak)", True, key="m_dcs")
        show_zone = st.checkbox("Kai Tak OZP zones", False, key="m_zone")
        mode = st.radio("Click / draw action", ["Add or remove (toggle)", "Add only", "Remove only"], key="m_mode", horizontal=False)
        z1, z2 = st.columns(2)
        if z1.button("Zoom to district", width="stretch"): ss.fit = ("district", did); bump(); st.rerun()
        if z2.button("Zoom to cluster", width="stretch", disabled=not members): ss.fit = ("cluster", act); bump(); st.rerun()

    vis = [r for r in recs_all if C.main_class(r) in show_uses or r.building_id in member_set]
    capped = len(vis) > MAX_FEATURES
    if capped: vis = sorted(vis, key=lambda r: -(r.footprint_area_m2.value or 0))[:MAX_FEATURES]

    ext = DNAME[did]["extent_hk80"]
    sw, ne = O.point_to_wgs84(ext[0], ext[1]), O.point_to_wgs84(ext[2], ext[3])
    bounds = [[sw[1], sw[0]], [ne[1], ne[0]]]
    if ss.fit and ss.fit[0] == "cluster" and members:
        pts = [p for r in members for p in r.footprint]
        bounds = [[min(p[1] for p in pts) - .0005, min(p[0] for p in pts) - .0005],
                  [max(p[1] for p in pts) + .0005, max(p[0] for p in pts) + .0005]]
    m = folium.Map(location=[(bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2], zoom_start=15,
                   tiles=None, control_scale=True, prefer_canvas=True)
    folium.TileLayer("OpenStreetMap", name="Street map", opacity=0.55).add_to(m)
    m.fit_bounds(bounds)
    folium.GeoJson({"type": "Feature", "properties": {"name": DNAME[did]["name"]},
                    "geometry": {"type": "MultiPolygon", "coordinates": [[[list(p) for p in ring] for ring in poly] for poly in DD["boundary_wgs"]]}},
                   name="District boundary", style_function=lambda f: {"color": INK, "weight": 2, "dashArray": "6 4", "fill": False},
                   interactive=False).add_to(m)
    if show_dcs:
        for k, polys in dcs_wgs.items():
            folium.GeoJson({"type": "Feature", "properties": {"name": sysopt[k]["name"]},
                            "geometry": {"type": "MultiPolygon", "coordinates": [[[list(p) for p in ring] for ring in poly] for poly in polys]}},
                           name="DCS service area", style_function=lambda f: {"color": BLUE, "weight": 2, "fillColor": BLUE, "fillOpacity": 0.06},
                           tooltip=f"{sysopt[k]['name']}: service area approximated by the OZP boundary", interactive=False).add_to(m)
    if show_zone:
        zf = [{"type": "Feature", "properties": {"zone": lab, "desc": desc, "col": O.zone_colour(lab)},
               "geometry": {"type": "MultiPolygon", "coordinates": [[[list(p) for p in ring] for ring in poly] for poly in polys]}}
              for lab, desc, polys in zone_data()]
        folium.GeoJson({"type": "FeatureCollection", "features": zf}, name="OZP zones",
                       style_function=lambda f: {"color": "#888", "weight": .5, "fillColor": f["properties"]["col"], "fillOpacity": .35},
                       tooltip=folium.GeoJsonTooltip(["zone", "desc"], ["Zone", ""]), interactive=False).add_to(m)

    def feat(r, sel=False):
        f, pk, q = C.building_inputs(r, ss.overrides, GLOBAL_DEFAULTS)
        return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in r.footprint]]},
                "properties": {"id": r.building_id, "name": r.name, "cls": C.main_class(r), "use": r.primary_use or "-",
                               "use2": r.secondary_use or "-", "floors": int(r.storeys.value) if r.storeys.value else "-",
                               "gfa": f"{f['gfa_m2'].value:,.0f} m² ({f['gfa_m2'].status})" if f["gfa_m2"].value else "missing",
                               "peak": f"{pk:,.0f} kW (est.)" if pk else "-", "col": C.USE_COLOURS.get(C.main_class(r), "#BBB"),
                               "state": "IN CLUSTER" if sel else "click to add"}}
    tip = folium.GeoJsonTooltip(["name", "cls", "use", "use2", "floors", "gfa", "peak", "state"],
                                ["Building", "Class", "Primary use", "Secondary use", "Floors", "GFA", "Peak cooling", ""], sticky=True)
    folium.GeoJson({"type": "FeatureCollection", "features": [feat(r) for r in vis]}, name="Buildings",
                   style_function=lambda f: {"color": "#4A5A62", "weight": .4, "fillColor": f["properties"]["col"], "fillOpacity": .7},
                   highlight_function=lambda f: {"weight": 2, "color": INK}, tooltip=tip).add_to(m)
    Draw(export=False, position="topleft", draw_options={"polyline": False, "circle": False, "marker": False, "circlemarker": False,
         "polygon": {"allowIntersection": False, "shapeOptions": {"color": RED}}, "rectangle": {"shapeOptions": {"color": RED}}},
         edit_options={"edit": False, "remove": True}).add_to(m)
    fg = folium.FeatureGroup(name="Cluster")
    if members:
        folium.GeoJson({"type": "FeatureCollection", "features": [feat(r, True) for r in members]},
                       style_function=lambda f: {"color": RED, "weight": 2.5, "fillColor": f["properties"]["col"], "fillOpacity": .95},
                       tooltip=folium.GeoJsonTooltip(["name", "cls", "use", "use2", "floors", "gfa", "peak", "state"],
                                                     ["Building", "Class", "Primary use", "Secondary use", "Floors", "GFA", "Peak cooling", ""], sticky=True)).add_to(fg)
        if G.get("hull_wgs") and len(G["hull_wgs"]) > 3:
            folium.PolyLine([[p[1], p[0]] for p in G["hull_wgs"]], color=RED, weight=1.5, dash_array="5 5", tooltip="Cluster boundary (convex hull)").add_to(fg)
        for a_, b_, d_ in G["proximity"]["pairs_over_limit"][:30]:
            ra, rb = by_id[a_], by_id[b_]
            folium.PolyLine([[ra.lat, ra.lon], [rb.lat, rb.lon]], color=RED, weight=1, opacity=.6,
                            tooltip=f"{ra.name} ↔ {rb.name}: {d_:,.0f} m (over {max_m:,.0f} m)").add_to(fg)
    with left:
        if capped: st.caption(f"Showing the {MAX_FEATURES:,} largest footprints of the selected classes; narrow the classes to see the rest.")
        out = st_folium(m, key=f"map_{did}_{ss.fit}", height=640, use_container_width=True, feature_group_to_add=fg,
                        returned_objects=["last_object_clicked", "last_clicked", "all_drawings"])

    def apply(ids, how):
        s = set(CL["ids"]); blocked = []
        for i in ids:
            r = by_id[i]
            if how == "remove" or (how == "toggle" and i in s): s.discard(i)
            elif r.selectable: s.add(i)
            else: blocked.append(r.name)
        CL["ids"] = [i for i in CL["ids"] if i in s] + sorted(s - set(CL["ids"]))
        return blocked

    how = {"Add or remove (toggle)": "toggle", "Add only": "add", "Remove only": "remove"}[mode]
    out = out or {}
    click = out.get("last_object_clicked") or out.get("last_clicked")
    if click and (click["lat"], click["lng"]) != ss.seen_click:
        ss.seen_click = (click["lat"], click["lng"])
        x, y = O.point_to_hk80(click["lng"], click["lat"])
        hit = DD["idx"].at(x, y)
        if hit:
            ss.focus = hit; bl = apply([hit], how)
            if bl: st.toast(f"{bl[0]}: not selectable (footprint area check failed). See Buildings › details.")
            bump(); st.rerun()
    draws = out.get("all_drawings") or []
    sig = json.dumps(draws, sort_keys=True)
    if draws and sig != ss.seen_draw:
        ss.seen_draw = sig
        polys = O.polygons_from_obj({"type": "FeatureCollection", "features": [draws[-1]]}, "EPSG:4326")
        ids = {i for i in DD["idx"].in_polygons(polys) if C.main_class(by_id[i]) in show_uses or (how == "remove" and i in member_set)}
        bl = apply(sorted(ids), "remove" if how == "remove" else "add")
        st.toast(f"Drawn shape: {len(ids)} building(s) {'removed' if how == 'remove' else 'added'}" + (f"; {len(bl)} not selectable" if bl else ""))
        bump(); st.rerun()
    elif not draws: ss.seen_draw = None

    with right:
        st.markdown('<div class="legend">' + "".join(f'<div><span class="sw" style="background:{c}"></span>{k}</div>' for k, c in C.USE_COLOURS.items())
                    + f'<div><span class="sw" style="background:#fff;border:2px solid {RED}"></span>In cluster</div>'
                    + f'<div><span class="sw" style="background:{BLUE}22;border:2px solid {BLUE}"></span>DCS service area (approx.)</div>'
                    + f'<div><span class="sw" style="border:2px dashed {INK}"></span>District boundary</div></div>', unsafe_allow_html=True)
        st.markdown(f"**{act}**")
        if members:
            ag = C.aggregates(members, ss.overrides, GLOBAL_DEFAULTS)
            st.metric("Buildings", ag["n"], ", ".join(f"{v} {k.lower()}" for k, v in ag["mix"].items()), delta_color="off")
            st.metric("Estimated GFA", f"{ag['gfa_m2'] / 1e3:,.0f}k m²", f"cooled {ag['cooled_m2'] / 1e3:,.0f}k m²", delta_color="off")
            st.metric("Peak cooling (sum)", f"{ag['peak_kw'] / 1e3:,.1f} MW", f"{ag['cooling_kwh'] / 1e6:,.1f} GWh/yr", delta_color="off")
            p = G["proximity"]
            if p.get("skipped"): st.info("Cluster too large for the proximity check.")
            elif p["within_limit"]: st.success(f"All buildings within {max_m:,.0f} m of each other (widest gap {p['max_distance_m']:,.0f} m).")
            else: st.markdown(f'<div class="warn">⚠ {p["n_pairs_over_limit"]} pair(s) more than {max_m:,.0f} m apart; widest {p["max_distance_m"]:,.0f} m. '
                              f'A shared plant is less likely to suit them (warning, not a block).</div>', unsafe_allow_html=True)
        else:
            st.info("Click buildings or draw a shape on the map to start this cluster.")
        if ss.focus and ss.focus in by_id:
            r = by_id[ss.focus]; f, pk, q = C.building_inputs(r, ss.overrides, GLOBAL_DEFAULTS)
            st.markdown(f"**Last clicked:** {r.name}  \n{C.main_class(r)} · {r.primary_use}{' / ' + r.secondary_use if r.secondary_use else ''}")
            st.markdown(f"GFA {f['gfa_m2'].value:,.0f} m² {badge(f['gfa_m2'].status)}  \nLoad {f['load_w_m2'].value:.0f} W/m² {badge(f['load_w_m2'].status)}"
                        if f["gfa_m2"].value else "GFA missing", unsafe_allow_html=True)
            st.caption("Full details and editing: Buildings tab.")

# =============================================================================================== buildings
if view == "Buildings":
    st.markdown("#### Find and select buildings")
    f1, f2, f3, f4 = st.columns([2, 2, 1, 1])
    q = f1.text_input("Search name or ID", key="b_q")
    cls = f2.multiselect("Classes", list(C.USE_COLOURS), list(C.USE_COLOURS), key="b_cls")
    minfl = f3.number_input("Min. floors", 0, 200, 0, key="b_fl")
    only = f4.selectbox("Show", ["All", "In cluster", "Not in cluster"], key="b_only")

    @st.cache_data(show_spinner=False)
    def base_table(did_, ov_json, cop):
        rows = []
        for r in district_data(did_)["recs"]:
            f, pk, qq = C.building_inputs(r, json.loads(ov_json), {"cop_existing": cop})
            rows.append({"id": r.building_id, "Building": r.name, "Class": C.main_class(r), "Primary use": r.primary_use,
                         "Secondary use": r.secondary_use, "Floors": r.storeys.value, "Height (m)": r.height_m.value,
                         "Footprint (m²)": r.footprint_area_m2.value, "GFA (m²)": f["gfa_m2"].value, "GFA status": f["gfa_m2"].status,
                         "Peak (kW)": pk, "Cooling (MWh/yr)": qq / 1000 if qq else None, "Approval year": r.age_year.value,
                         "OZP zone": dict(r.attrs).get("OZP_Zone_Code_法定图则代码", ""), "Data check": r.match_tier})
        return pd.DataFrame(rows)

    T = base_table(did, json.dumps(ss.overrides, sort_keys=True), V["cop_existing"]).copy()
    T.insert(0, "In cluster", T["id"].isin(member_set))
    mask = T["Class"].isin(cls) & (T["Floors"].fillna(0) >= minfl)
    if q: mask &= T["Building"].str.contains(q, case=False, regex=False) | T["id"].str.contains(q, case=False, regex=False)
    if only == "In cluster": mask &= T["In cluster"]
    elif only == "Not in cluster": mask &= ~T["In cluster"]
    TV = T[mask].set_index("id")
    st.caption(f"{len(TV):,} of {len(T):,} buildings match. Click a column header to sort. Tick or untick **In cluster** to add or remove.")
    shown = TV.head(3000)
    if len(TV) > 3000: st.caption("Showing the first 3,000 matches; refine the filters to see the rest.")
    ed = st.data_editor(shown, key=f"tbl_{did}_{act}_{ss.ver}", height=420, width="stretch",
                        disabled=[c for c in shown.columns if c != "In cluster"],
                        column_config={"In cluster": st.column_config.CheckboxColumn(width="small"),
                                       "GFA (m²)": st.column_config.NumberColumn(format="%,.0f"), "Peak (kW)": st.column_config.NumberColumn(format="%,.0f"),
                                       "Footprint (m²)": st.column_config.NumberColumn(format="%,.0f"),
                                       "Cooling (MWh/yr)": st.column_config.NumberColumn(format="%,.0f"),
                                       "Approval year": st.column_config.NumberColumn(format="%d")})
    chg = ed["In cluster"] != shown["In cluster"]
    if chg.any():
        add = [i for i in ed.index[chg] if ed.at[i, "In cluster"]]; rem = [i for i in ed.index[chg] if not ed.at[i, "In cluster"]]
        bl = apply(add, "add") if add else []
        if rem: apply(rem, "remove")
        if bl: st.toast(f"{len(bl)} building(s) not selectable (footprint area check failed).")
        bump(); st.rerun()
    e1, e2, e3 = st.columns(3)
    e1.download_button("Download filtered table (CSV)", TV.to_csv().encode("utf-8-sig"), f"{did}_buildings_filtered.csv", "text/csv", width="stretch")

    st.markdown(f"#### Cluster inputs: {act}")
    if not members:
        st.info("The cluster is empty.")
    else:
        st.caption("Edit any value to override it for this building only (source records are never changed). Status shows where each value comes from.")
        rows = []
        for r in members:
            f, pk, qq = C.building_inputs(r, ss.overrides, GLOBAL_DEFAULTS)
            rows.append({"id": r.building_id, "Building": r.name, **{k: f[k].value for k in EDITABLE},
                         **{f"{k} status": f[k].status for k in EDITABLE}, "Peak (kW)": pk})
        CI = pd.DataFrame(rows).set_index("id")
        lab = {"gfa_m2": "GFA (m²)", "cooled_fraction": "Cooled share", "load_w_m2": "Peak load (W/m²)", "hours": "Full-load hours/yr", "cop_existing": "Existing COP"}
        ced = st.data_editor(CI, key=f"ci_{act}_{ss.ver}", width="stretch", disabled=["Building", "Peak (kW)"] + [f"{k} status" for k in EDITABLE],
                             column_config={**{k: st.column_config.NumberColumn(v, min_value=0.0) for k, v in lab.items()},
                                            "Peak (kW)": st.column_config.NumberColumn(format="%,.0f")})
        changed = False
        for k in EDITABLE:
            diff = ced[k].astype(float).fillna(-1) != CI[k].astype(float).fillna(-1)
            for i in ced.index[diff]:
                v = ced.at[i, k]
                if v is None or (isinstance(v, float) and math.isnan(v)): ss.overrides.get(i, {}).pop(k, None)
                else: ss.overrides.setdefault(i, {})[k] = float(v)
                changed = True
        if changed: bump(); st.rerun()
        if EXCL: st.markdown('<div class="warn">Excluded from the calculation (missing inputs): ' + ", ".join(f"{n} ({', '.join(ms)})" for _, n, ms in EXCL) + "</div>", unsafe_allow_html=True)
        k1, k2, k3 = st.columns(3)
        if k1.button("Reset edits for this cluster", width="stretch"):
            for i in CL["ids"]: ss.overrides.pop(i, None)
            bump(); st.rerun()
        exp = []
        for r in members:
            f, pk, qq = C.building_inputs(r, ss.overrides, GLOBAL_DEFAULTS)
            exp.append({"cluster": act, "district": did, "building_id": r.building_id, "name": r.name, "class": C.main_class(r),
                        "primary_use": r.primary_use, "secondary_use": r.secondary_use,
                        **{k: f[k].value for k in list(EDITABLE) + ["cooled_area_m2"]}, **{f"{k}_status": f[k].status for k in EDITABLE},
                        "peak_kw": pk, "cooling_kwh": qq, **dict(r.attrs)})
        k2.download_button("Download cluster (CSV)", pd.DataFrame(exp).to_csv(index=False).encode("utf-8-sig"), f"{act}.csv", "text/csv", width="stretch")
        k3.download_button("Download cluster (GeoJSON, WGS84)", json.dumps(C.cluster_geojson(members, act, O.point_to_wgs84), ensure_ascii=False),
                           f"{act}.geojson", "application/geo+json", width="stretch", help="Opens in Scribble Maps, geojson.io or QGIS.")

        st.markdown("#### Building details")
        pick = st.selectbox("Building", CL["ids"], index=CL["ids"].index(ss.focus) if ss.focus in CL["ids"] else 0,
                            format_func=lambda i: by_id[i].name, key=f"pick_{act}_{ss.ver}")
        r = by_id[pick]; f, pk, qq = C.building_inputs(r, ss.overrides, GLOBAL_DEFAULTS)
        d1, d2 = st.columns(2)
        with d1:
            st.markdown(f"**{r.name}** · `{r.building_id}`  \n{C.main_class(r)}; uses: " +
                        (", ".join(f"{l.split('_')[0]} {s:.0%}" for l, s in r.use_mix) or "not parsed"))
            src_rows = [("Height (m)", r.height_m), ("Floors", r.storeys), ("Footprint area (m²)", r.footprint_area_m2), ("Approval year (BDBIAR)", r.age_year)]
            st.markdown("<br>".join(f"{n}: <b>{v.value if v.value is not None else '–'}</b> {badge(v.status)} <small>{v.ref}</small>" for n, v in src_rows),
                        unsafe_allow_html=True)
            st.markdown("<br>".join(f"{k}: <b>{f[k].value if f[k].value is not None else '–'}</b> {badge(f[k].status)} <small>{f[k].ref}</small>"
                                    for k in list(EDITABLE) + ["cooled_area_m2"]), unsafe_allow_html=True)
            if r.match_tier != "exact_id": st.markdown(f'<div class="warn">Data check: {r.match_tier} (footprint area differs from polygon area).</div>', unsafe_allow_html=True)
        with d2:
            st.caption("All source attributes (unchanged)")
            st.dataframe(pd.DataFrame([{"field": k, "value": v} for k, v in r.attrs] + [{"field": a, "value": b} for a, b in r.source_ids]),
                         hide_index=True, width="stretch")

    st.markdown("#### Import a polygon (Scribble Maps, geojson.io, QGIS)")
    up = st.file_uploader("GeoJSON or Esri JSON polygon, EPSG:4326 or EPSG:2326. Buildings whose centroid is inside are added to the cluster.",
                          type=["geojson", "json"], key=f"up_{ss.ver}")
    if up is not None:
        try:
            polys, msg = O.parse_upload(up.getvalue()); ids = DD["idx"].in_polygons(polys)
            st.write(f"{msg}; {len(ids)} building(s) of {DNAME[did]['name']} inside.")
            if ids and st.button(f"Add {len(ids)} building(s) to {act}"):
                apply(sorted(ids), "add"); bump(); st.rerun()
        except Exception as e:
            st.error(f"Could not read the file: {e}")

# =============================================================================================== results
def evaluate_safe(a):
    errs = validate(a)
    return (None, errs) if errs else (L.evaluate(a), [])


def pv_parts(s, r):
    return {k: sum(v / (1 + r) ** t for t, v in enumerate(s[k])) for k in ("capex", "energy", "maint", "charges")}


def layout(fig, h=340, legend=False):
    fig.update_layout(height=h, margin=dict(l=0, r=0, t=36, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Public Sans", color=INK), showlegend=legend, legend=dict(orientation="h", y=-.18))
    fig.update_xaxes(gridcolor="#DCE3E4"); fig.update_yaxes(gridcolor="#DCE3E4"); return fig


R, ERR = (None, ["Add buildings to the cluster."]) if not A.buildings else evaluate_safe(A)
cov, cov_ids = coverage(did, tuple(CL["ids"])) if members else ({}, {})

if view == "Results":
    if R is None:
        for e in ERR:
            if "Add buildings" in e: st.info(e)
            else: st.error(e)
    else:
        S = R["scenarios"]; best = R["best"]
        warn = []
        p = G["proximity"]
        if p.get("within_limit") is False: warn.append(f"{p['n_pairs_over_limit']} building pair(s) are more than {max_m:,.0f} m apart (widest {p['max_distance_m']:,.0f} m): CMCS piping may be impractical.")
        if G.get("isolated"): warn.append(f"{len(G['isolated'])} building(s) have no other cluster building within {max_m:,.0f} m.")
        n_dcs = sum(cov.values())
        if n_dcs < len(members):
            warn.append(f"Only {n_dcs} of {len(members)} buildings lie inside an existing DCS service area. For the others the DCS result is "
                        "hypothetical (it uses the selected EMSD tariff as if a network were available).")
        if EXCL: warn.append(f"{len(EXCL)} building(s) excluded for missing inputs (Buildings tab).")
        if len(A.buildings) > 1:
            big = max(A.buildings, key=lambda b: b[1] * b[2]); share = big[1] * big[2] / 1000 * A.demand_scale / R["peak_kw"]
            if share > 0.5:
                warn.append(f"{big[0]} is {share:.0%} of the cluster's peak load. Check its GFA: footprint × floors overstates large "
                            "low-rise complexes. Override it in Buildings › Cluster inputs if you know a better value.")
        for w in warn: st.markdown(f'<div class="warn">⚠ {w}</div>', unsafe_allow_html=True)
        alt = [n for n in ("CMCS", "DCS") if S[n]["npv_saving"] > 0]
        if best == "Individual":
            verdict = f"Keeping individual plants is cheapest over {R['years']} years; the best alternative costs {mhk(-max(S['CMCS']['npv_saving'], S['DCS']['npv_saving']))} more in present value."
        else:
            dp = S[best]["discounted_payback"]
            verdict = (f"{SNAME[best]} is cheapest: it saves {mhk(S[best]['npv_saving'])} in present value against individual plants"
                       + (f" and pays back in {dp:.1f} years (discounted)" if dp is not None else "") + f", cutting {S[best]['co2_cut_t']:,.0f} tCO₂e a year.")
        st.markdown(f'<div class="verdict">{verdict}</div>', unsafe_allow_html=True)
        k = st.columns(4)
        k[0].metric("Cluster peak cooling", f"{R['peak_kw'] / 1e3:,.1f} MW", f"{R['cooling_kwh'] / 1e6:,.1f} GWh cooling/yr", delta_color="off")
        k[1].metric("CMCS NPV vs Individual", mhk(S["CMCS"]["npv_saving"]), f"payback {yrs(S['CMCS']['discounted_payback'])}", delta_color="off")
        k[2].metric("DCS NPV vs Individual", mhk(S["DCS"]["npv_saving"]), f"payback {yrs(S['DCS']['discounted_payback'])}", delta_color="off")
        k[3].metric("CMCS network length", f"{A.network_m:,.0f} m", "override" if net_override else "derived from building positions", delta_color="off")
        tbl = pd.DataFrame([{"Scenario": SNAME[n], "Investment year 0 (HK$M)": S[n]["capex0"] / 1e6, "Annual cost year 1 (HK$M)": S[n]["opex1"] / 1e6,
                             "of which DCS charges (HK$M)": S[n]["charges"][1] / 1e6 if R["years"] else 0,
                             "Building electricity (GWh/yr)": S[n]["elec_yr"] / 1e6, "Emissions incl. attributed (tCO₂e/yr)": S[n]["co2_t"],
                             "Lifecycle cost, PV (HK$M)": S[n]["pv_cost"] / 1e6, "NPV saving vs Individual (HK$M)": S[n]["npv_saving"] / 1e6,
                             "Simple payback (yrs)": S[n]["simple_payback"], "Discounted payback (yrs)": S[n]["discounted_payback"],
                             "Levelised cost (HK$/kWh cooling)": S[n]["levelised_hk_per_kwh"]} for n in L.SCENARIOS]).set_index("Scenario")
        st.dataframe(tbl.style.format("{:,.2f}", na_rep="–"), width="stretch")
        c1_, c2_ = st.columns(2)
        f = go.Figure(); r_ = A.discount_rate
        parts = {n: pv_parts(S[n], r_) for n in L.SCENARIOS}
        for comp, col, lab_ in (("capex", INK, "Investment & replacement"), ("energy", AMBER, "Electricity"), ("maint", SLATE, "Maintenance"), ("charges", TEAL, "DCS charges")):
            f.add_bar(x=list(L.SCENARIOS), y=[parts[n][comp] / 1e6 for n in L.SCENARIOS], name=lab_, marker_color=col)
        f.update_layout(barmode="relative", title=f"Lifecycle cost, present value over {R['years']} yrs (HK$M)", title_font_size=14)
        c1_.plotly_chart(layout(f, 360, True), width="stretch")
        f = go.Figure()
        for n in ("CMCS", "DCS"):
            f.add_scatter(x=list(range(R["years"] + 1)), y=[v / 1e6 for v in S[n]["cum_saving_disc"]], name=SNAME[n], line=dict(color=SCOL[n], width=3))
        f.add_hline(y=0, line_color=INK, line_width=1)
        f.update_layout(title="Cumulative discounted saving vs Individual (HK$M)", title_font_size=14, xaxis_title="Year")
        c2_.plotly_chart(layout(f, 360, True), width="stretch")
        c3_, c4_ = st.columns(2)
        f = go.Figure(go.Bar(x=list(L.SCENARIOS), y=[S[n]["co2_t"] for n in L.SCENARIOS], marker_color=[SCOL[n] for n in L.SCENARIOS]))
        f.update_layout(title="Emissions, tCO₂e/yr (DCS includes attributed plant electricity)", title_font_size=14)
        c3_.plotly_chart(layout(f, 320), width="stretch")
        with c4_:
            d = S["DCS"]
            st.markdown("**DCS bill, year 1**")
            st.write(f"Contract capacity {d['capacity_kw'] / 1e3:,.2f} MW refrigeration ({d['capacity_kw'] / 3.517:,.0f} RT). "
                     f"Capacity charge {mhk(d['capacity_charge'])}, consumption charge {mhk(d['consumption_charge'])}.")
            st.markdown("**DCS coverage**")
            for k_, n_ in cov.items(): st.write(f"{sysopt[k_]['name']}: {n_} of {len(members)} buildings inside the approximate service area.")
            st.caption(sysopt["kai_tak"]["service_area"]["basis"])
        with st.expander("Year-by-year cash flows"):
            cf = pd.DataFrame({f"{n} {k_}": S[n][k_] for n in L.SCENARIOS for k_ in ("capex", "energy", "maint", "charges", "cost")})
            cf.index.name = "year"
            st.dataframe((cf / 1e6).style.format("{:,.2f}"), width="stretch")
            st.download_button("Download cash flows (CSV, HK$)", cf.to_csv().encode("utf-8-sig"), f"{act}_cashflows.csv", "text/csv")

# =============================================================================================== sensitivity
if view == "Sensitivity":
    if R is None:
        st.info("Build a cluster first.")
    else:
        s1, s2, s3 = st.columns(3)
        sc = s1.selectbox("Scenario", ["DCS", "CMCS"], format_func=SNAME.get, key="s_sc")
        met = s2.selectbox("Result", ["npv_saving", "discounted_payback", "pv_cost", "co2_cut_t"], format_func=L.METRICS.get, key="s_m")
        pct = s3.slider("Swing each input by ±%", 5, 50, 20, 5, key="s_pct") / 100
        fields = [f_ for f_, (_, ap) in L.PARAMS.items() if ap in ("all", sc)]
        base, rows = L.tornado(A, sc, met, pct, fields)
        div_ = 1e6 if met in ("npv_saving", "pv_cost") else 1
        unit = " (HK$M)" if div_ == 1e6 else ""
        st.markdown(f"**One-at-a-time ({L.METRICS[met]}{unit})** · base: " + ("not reached" if base is None else f"{base / div_:,.2f}"))
        f = go.Figure()
        ys = [r_["label"] for r_ in rows]
        f.add_bar(y=ys, x=[(r_["low"] - base) / div_ if r_["low"] is not None and base is not None else 0 for r_ in rows], orientation="h", name=f"Input −{pct:.0%}", marker_color=SLATE)
        f.add_bar(y=ys, x=[(r_["high"] - base) / div_ if r_["high"] is not None and base is not None else 0 for r_ in rows], orientation="h", name=f"Input +{pct:.0%}", marker_color=TEAL)
        f.update_layout(barmode="overlay", xaxis_title=f"Change in {L.METRICS[met]}{unit}", yaxis=dict(autorange="reversed"))
        st.plotly_chart(layout(f, 460, True), width="stretch")
        if met == "discounted_payback": st.caption("Bars at zero can also mean payback is not reached in the period at that input value.")
        st.markdown("**Two-way table**")
        t1, t2 = st.columns(2)
        opts = fields
        fx = t1.selectbox("Across", opts, index=opts.index("tariff"), format_func=lambda k: L.PARAMS[k][0], key="s_fx")
        fy = t2.selectbox("Down", opts, index=opts.index("dcs_capacity_rate" if sc == "DCS" else "central_capex_kw"), format_func=lambda k: L.PARAMS[k][0], key="s_fy")
        if fx == fy: st.warning("Choose two different inputs.")
        else:
            xs, ys2, z = L.two_way(A, fx, fy, sc, met)
            zz = [[None if v is None else v / div_ for v in row] for row in z]
            f = go.Figure(go.Heatmap(x=[f"{v:,.3g}" for v in xs], y=[f"{v:,.3g}" for v in ys2], z=zz, colorscale=[[0, "#B3412E"], [.5, "#F4F1EA"], [1, "#0E6E73"]],
                                     zmid=0 if met == "npv_saving" else None, text=[[("–" if v is None else f"{v:,.1f}") for v in row] for row in zz],
                                     texttemplate="%{text}", colorbar=dict(title=unit.strip() or "")))
            f.update_layout(xaxis_title=L.PARAMS[fx][0], yaxis_title=L.PARAMS[fy][0], title=f"{L.METRICS[met]}{unit}, {SNAME[sc]}", title_font_size=14)
            st.plotly_chart(layout(f, 440), width="stretch")
        st.markdown("**Break-even points** (NPV saving vs Individual = 0, other inputs fixed)")
        be = []
        for f_ in fields:
            k_ = L.breakeven(A, f_, sc)
            if k_ is not None: be.append({"Input": L.PARAMS[f_][0], "Current value": getattr(A, f_), "Break-even value": getattr(L._set(A, f_, k_), f_), "Change needed": f"{k_ - 1:+.0%}"})
        if be: st.dataframe(pd.DataFrame(be), hide_index=True, width="stretch")
        else: st.caption("No input reaches break-even within 0–5× its current value.")

# =============================================================================================== compare
if view == "Compare clusters":
    rows = []
    for n_, c_ in ss.clusters.items():
        if not c_["ids"] or c_["district"] not in DNAME: continue
        a_, ex_, g_ = assumptions_for(c_["district"], c_["ids"])
        r__, e__ = evaluate_safe(a_) if a_.buildings else (None, ["empty"])
        if r__ is None: continue
        s_ = r__["scenarios"]; cv_, _ = coverage(c_["district"], tuple(c_["ids"]))
        rows.append({"Cluster": n_, "District": DNAME[c_["district"]]["name"], "Buildings": len(c_["ids"]), "Peak (MW)": r__["peak_kw"] / 1e3,
                     "Best option": r__["best"], "PV Individual (HK$M)": s_["Individual"]["pv_cost"] / 1e6, "PV CMCS (HK$M)": s_["CMCS"]["pv_cost"] / 1e6,
                     "PV DCS (HK$M)": s_["DCS"]["pv_cost"] / 1e6, "NPV CMCS (HK$M)": s_["CMCS"]["npv_saving"] / 1e6, "NPV DCS (HK$M)": s_["DCS"]["npv_saving"] / 1e6,
                     "Payback CMCS (yrs)": s_["CMCS"]["discounted_payback"], "Payback DCS (yrs)": s_["DCS"]["discounted_payback"],
                     "CO₂e cut, best (t/yr)": s_[r__["best"]]["co2_cut_t"], "Widest gap (m)": g_["proximity"]["max_distance_m"],
                     "In DCS area": f"{sum(cv_.values())}/{len(c_['ids'])}", "Network (m)": a_.network_m})
    if not rows:
        st.info("Build at least one cluster. Make more with *New cluster* in the sidebar, in any district, to compare them here.")
    else:
        CMP = pd.DataFrame(rows).set_index("Cluster")
        st.dataframe(CMP.style.format({c: "{:,.1f}" for c in CMP.columns if CMP[c].dtype.kind == "f"}, na_rep="–"), width="stretch")
        f = go.Figure()
        for n, col in (("Individual", SLATE), ("CMCS", AMBER), ("DCS", TEAL)):
            f.add_bar(x=CMP.index, y=CMP[f"PV {n} (HK$M)"] / CMP["Peak (MW)"], name=SNAME[n], marker_color=col)
        f.update_layout(barmode="group", title="Lifecycle cost per MW of peak cooling (HK$M/MW, PV)", title_font_size=14)
        st.plotly_chart(layout(f, 380, True), width="stretch")
        st.download_button("Download comparison (CSV)", CMP.to_csv().encode("utf-8-sig"), "cluster_comparison.csv", "text/csv")
        st.caption("All clusters use the same sidebar assumptions; network length is derived per cluster unless overridden.")

# =============================================================================================== method
if view == "Method & data":
    man = DD["rep"]["manifest"]
    st.markdown("### Method")
    st.markdown(f"""**Demand.** Cooled area = GFA × cooled share; peak kW = cooled area × W/m² ÷ 1,000; annual cooling = peak × full-load hours. GFA is the registered value
if present, otherwise **derived** as footprint × floors. Loads, hours and cooled share default by HK-BFETD use (share-weighted for mixed buildings) and are **illustrative**.

**Individual (reference).** Existing chillers run at the existing COP until their remaining life ends, then are replaced (replacement cost per kW, replacement COP) every chiller life.
**CMCS.** A privately developed shared plant sized at peak × diversity, with pipe network (length = minimum spanning tree between building centroids × route factor, or your override)
and a connection per building. Electricity = cooling ÷ (1 − loss) ÷ plant COP × (1 + pumping share). Plant and network are replaced at the end of their lives.
**DCS.** Building-side works per building plus per kW. Annual bill = contract capacity (peak × contract factor) × capacity rate × 12 + cooling kWh × consumption rate (EMSD tariff).
The building pays only for its own pumping electricity; DCS plant electricity (cooling ÷ DCS plant COP) is **attributed** to the cluster for emissions only.

**Finance.** Real HK$, year 0 investment, years 1–N operation, end-of-year discounting at the real discount rate. Residual value = straight-line remaining life of the latest assets,
credited in year N in every scenario. NPV saving = PV(Individual costs) − PV(scenario costs). Discounted payback = first year the cumulative discounted saving turns positive.
Simple payback = extra year-0 investment ÷ year-1 saving. Levelised cost = PV cost ÷ PV of cooling delivered.

**Proximity.** Edge-to-edge distances between footprints in Hong Kong 1980 Grid metres (EPSG:2326). Over the limit = warning, never a block.

**Sensitivity.** One input at a time by ±x %, a two-way grid, and break-even multipliers found by bisection.""")
    st.markdown("### Data for this district")
    st.markdown(f"""* Package `{did}`: **{man['counts']['buildings']:,} buildings**, validation **{'PASSED' if man['validation']['passed'] else 'FAILED'}**, files re-verified by SHA-256 at load.
* Area: {man['district']['description']} Status: {man['district']['status']}. Assignment rule: {man['area_definition']['assignment_rule']}.
* Source: {man['sources']['geojson']['name']} and {man['sources']['csv']['name']} (SHA-256 `{man['sources']['geojson']['sha256'][:16]}…`). {man['sources']['licence_note']}
* Registered GFA present for {man['summary']['registered_gfa_present']} buildings; data-check tiers: {DD['rep']['tiers']}.
* DCS tariffs: [{reg['source']['title']}]({reg['source']['url']}) (accessed {reg['source']['accessed']}). {reg['source']['notes']}
* District boundaries: Home Affairs Department 18-district boundary (data.gov.hk). Kai Tak: Planning Department OZP S/K22/9 GIS data.""")
    st.markdown("### DCS systems")
    st.dataframe(pd.DataFrame([{"System": s["name"], "Status": s["status"], **{f"{y} capacity (HK$/kW/mo)": v["capacity_hkd_per_kwr_month"] for y, v in s["rates"].items()},
                                **{f"{y} consumption (HK$/kWh)": v["consumption_hkd_per_kwhr"] for y, v in s["rates"].items()}} for s in reg["systems"]]),
                 hide_index=True, width="stretch")
    st.markdown("### Limits")
    st.markdown("""Screening only: no hourly load profiles, no part-load curves, no tax, financing or land cost, no capacity-overrun charges, and no check that the
DCS network actually reaches a building. Floors and heights come from HK-BFETD; their origin is not documented in the files. BDBIAR year is an approval year, not plant age.""")
