"""Map and selection tab. Split view: map, distance check and building table on the left; live result card and building
card on the right. Map, table and results always show the same selection (the active cluster)."""
import json
import folium
import pandas as pd
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium

import clusters as C
import overlays as O
import verdict as V
from buildings import EDITABLE, resolve
from ui import state, inputs
from ui.style import (html, note, badge, status_label, mhk, yrs, num, TEAL, ORANGE, MUTED, PURPLE, SLATE, TYPE_COLORS, FALLBACK_TYPE,
                      BLUES, NO_DATA, OPTION_NAMES)

MAX_FEATURES = 5000
FIELD_UI = {"gfa_m2": ("Gross floor area (m²)", 0.0, 1e8), "cooled_fraction": ("Cooled share of floor area", 0.0, 1.0),
            "load_w_m2": ("Peak cooling load (W/m²)", 1.0, 500.0), "hours": ("Full-load hours per year", 1.0, 8760.0),
            "cop_existing": ("Existing system efficiency (COP)", 1.0, 10.0)}


def type_color(r): return TYPE_COLORS.get(C.main_class(r), FALLBACK_TYPE)


@st.cache_data(show_spinner=False)
def district_peaks(did, ov_json, tkey, cop, stamp=""):
    ov, tab = json.loads(ov_json), {k: tuple(v) for k, v in json.loads(tkey).items()}
    return {r.building_id: C.building_inputs(r, ov, {"cop_existing": cop}, tab)[1] for r in state.district_data(did, stamp)["recs"]}


def intensity_bins(values, k=5):
    v = sorted(x for x in values if x)
    return [v[min(len(v) - 1, int(len(v) * q / k))] for q in range(1, k)] if v else []


def intensity_color(x, bins): return NO_DATA if not x else BLUES[sum(1 for b in bins if x >= b)]


def _feat(r, peak, col, sel=False, warn=False):
    f = resolve(r, "gfa_m2", st.session_state.overrides)
    gtxt = "n/a" if f.value is None else f"{f.value:,.0f} m² ({status_label(f.status).lower()})"
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in r.footprint]]},
            "properties": {"name": r.name, "type": C.main_class(r), "use": r.primary_use or "–", "use2": r.secondary_use or "–",
                           "storeys": f"{r.storeys.value:.0f}" if r.storeys.value else "n/a", "gfa": gtxt,
                           "peak": "no cooling inputs" if not peak else f"{peak:,.0f} kW (estimate)", "color": col, "sel": sel, "warn": warn,
                           "hint": "click to remove" if sel else "click to add"}}


def _tip(): return folium.GeoJsonTooltip(["name", "type", "use", "use2", "storeys", "gfa", "peak", "hint"],
                                         ["Building", "Type", "Primary use", "Secondary use", "Storeys", "GFA", "Peak cooling", ""], sticky=True)


def _style(f):
    p = f["properties"]
    if p["warn"]: return dict(fillColor=p["color"], color=ORANGE, weight=3.5, opacity=1, fillOpacity=.95, dashArray="5 4")
    if p["sel"]: return dict(fillColor=p["color"], color=TEAL, weight=3.5, opacity=1, fillOpacity=.95)
    return dict(fillColor=p["color"], color=SLATE, weight=.5, opacity=.5, fillOpacity=.55)


def _multipoly(polys): return {"type": "MultiPolygon", "coordinates": [[[list(p) for p in ring] for ring in poly] for poly in polys]}


def toolbar(cl):
    ss = st.session_state
    a, b, c = st.columns([5, 4, 3])
    a.radio("Drawing tool (▢ ⬠ on the map)", ["add", "remove", "replace"], key="draw_mode", horizontal=True,
            format_func={"add": "Adds", "remove": "Removes", "replace": "Replaces selection"}.get,
            help="Pick before you draw. The rectangle and polygon tools are in the map's top-left corner. Clicking a building always toggles it.")
    b.radio("Colour buildings by", ["type", "intensity"], key="color_by", horizontal=True, format_func={"type": "Type", "intensity": "Peak cooling (est.)"}.get)
    with c:
        st.write("")
        if st.button("Clear selection", key="clear_sel", disabled=not cl["ids"], width="stretch"):
            cl["ids"] = []; ss.focus = None; ss.seen_draw = set(); state.bump(); st.rerun()
    with st.expander("Map layers and zoom"):
        x, y, z = st.columns([4, 3, 3])
        x.multiselect("Show building types", list(TYPE_COLORS), ["Commercial", "Mixed-use"], key="m_types",
                      help="Selected buildings are always shown. Fewer types = faster map in big districts.")
        y.checkbox("Existing DCS service area", True, key="m_dcs"); y.checkbox("Kai Tak zoning (OZP)", False, key="m_zone")
        if z.button("Zoom to district", width="stretch"): ss.fit = ("district", ss.ver); state.bump(); st.rerun()
        if z.button("Zoom to cluster", width="stretch", disabled=not cl["ids"]): ss.fit = ("cluster", ss.ver); state.bump(); st.rerun()


def map_panel(meta, DD, cl, G):
    ss = st.session_state; by_id = DD["by_id"]; members = [by_id[i] for i in cl["ids"]]; mset = set(cl["ids"])
    toolbar(cl)
    shown = ss.get("m_types", ["Commercial", "Mixed-use"])
    peaks = district_peaks(meta["id"], json.dumps(ss.overrides, sort_keys=True), state.table_key(), inputs.values()["cop_existing"], meta.get("generated", ""))
    if ss.get("color_by") == "intensity":
        bins = intensity_bins(peaks.values()); colf = lambda r: intensity_color(peaks.get(r.building_id), bins)
        edges = ([f"< {bins[0]:,.0f}"] + [f"{a:,.0f}–{b:,.0f}" for a, b in zip(bins, bins[1:])] + [f"≥ {bins[-1]:,.0f}"]) if bins else []
        items = [(f"{e} kW", c) for e, c in zip(edges, BLUES)] + [("No cooling inputs", NO_DATA)]
    else:
        colf = type_color; items = [(k, c) for k, c in TYPE_COLORS.items() if k in shown or any(C.main_class(r) == k for r in members)]
    vis = [r for r in DD["recs"] if r.building_id not in mset and C.main_class(r) in shown]
    capped = len(vis) > MAX_FEATURES
    if capped: vis = sorted(vis, key=lambda r: -(r.footprint_area_m2.value or 0))[:MAX_FEATURES]

    ext = meta["extent_hk80"]; sw, ne = O.point_to_wgs84(ext[0], ext[1]), O.point_to_wgs84(ext[2], ext[3])
    bounds = [[sw[1], sw[0]], [ne[1], ne[0]]]
    if ss.fit and ss.fit[0] == "cluster" and members:
        pts = [p for r in members for p in r.footprint]
        bounds = [[min(p[1] for p in pts) - .0005, min(p[0] for p in pts) - .0005], [max(p[1] for p in pts) + .0005, max(p[0] for p in pts) + .0005]]
    m = folium.Map(location=[(bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2], zoom_start=15, tiles=None,
                   control_scale=True, prefer_canvas=True)
    folium.TileLayer("OpenStreetMap", name="Street map", opacity=0.5).add_to(m)
    m.fit_bounds(bounds)
    if DD["boundary_wgs"]:
        folium.GeoJson({"type": "Feature", "properties": {}, "geometry": _multipoly(DD["boundary_wgs"])}, interactive=False,
                       style_function=lambda f: dict(fill=False, color=MUTED, weight=1.5, dashArray="2 6")).add_to(m)
    if ss.get("m_dcs", True):
        _, _, dwgs = state.dcs_data()
        for k, polys in dwgs.items():
            folium.GeoJson({"type": "Feature", "properties": {}, "geometry": _multipoly(polys)}, interactive=False,
                           style_function=lambda f: dict(color=PURPLE, weight=2, fillColor=PURPLE, fillOpacity=.05)).add_to(m)
    if ss.get("m_zone"):
        zf = [{"type": "Feature", "properties": {"zone": lab, "desc": desc, "col": O.zone_colour(lab)}, "geometry": _multipoly(polys)}
              for lab, desc, polys in state.zone_data()]
        if zf:
            folium.GeoJson({"type": "FeatureCollection", "features": zf}, interactive=False,
                           style_function=lambda f: dict(color="#888", weight=.5, fillColor=f["properties"]["col"], fillOpacity=.3)).add_to(m)
    if vis:   # an empty layer with a tooltip makes folium 1.0 raise, so only add layers that have features
        folium.GeoJson({"type": "FeatureCollection", "features": [_feat(r, peaks.get(r.building_id), colf(r)) for r in vis]},
                       style_function=_style, highlight_function=lambda f: dict(weight=2, color=SLATE), tooltip=_tip()).add_to(m)
    Draw(export=False, position="topleft", draw_options=dict(polyline=False, circle=False, marker=False, circlemarker=False,
         polygon={"allowIntersection": False, "shapeOptions": {"color": TEAL}}, rectangle={"shapeOptions": {"color": TEAL}}),
         edit_options=dict(edit=False, remove=True)).add_to(m)
    fg = folium.FeatureGroup(name="Selected")
    if members:
        iso = {b for b, _ in G.get("isolated", [])}
        folium.GeoJson({"type": "FeatureCollection", "features": [_feat(r, peaks.get(r.building_id), colf(r), True, r.building_id in iso) for r in members]},
                       style_function=_style, tooltip=_tip()).add_to(fg)
        if len(G.get("hull_wgs") or []) > 3:
            folium.Polygon([[p[1], p[0]] for p in G["hull_wgs"]], color=TEAL, weight=2, dash_array="8 5", fill=True, fill_color=TEAL,
                           fill_opacity=.05, tooltip="Cluster boundary (convex hull)").add_to(fg)
        for a_, b_, d_ in (G.get("proximity") or {}).get("pairs_over_limit", [])[:30]:
            ra, rb = by_id[a_], by_id[b_]
            folium.PolyLine([[ra.lat, ra.lon], [rb.lat, rb.lon]], color=ORANGE, weight=2, dash_array="5 5",
                            tooltip=f"{ra.name} ↔ {rb.name}: {d_:,.0f} m").add_to(fg)
    out = st_folium(m, key=f"map_{meta['id']}_{ss.fit}", height=560, use_container_width=True, feature_group_to_add=fg,
                    returned_objects=["last_object_clicked", "last_clicked", "all_drawings"]) or {}
    if capped: note(f"Showing the {MAX_FEATURES:,} largest footprints of the chosen types. Show fewer types (Map layers) to see the rest. "
                    "Selected buildings are always shown.")
    leg = "".join(f'<span class="sw" style="background:{c}"></span>{t}' for t, c in items)
    html(f'<div class="legend">{leg}<span class="sw sel"></span>Selected<span class="sw far"></span>Over {inputs.max_m():,.0f} m from the rest'
         f'<span class="sw dcs"></span>DCS service area (approx.)<span class="sw bnd"></span>District boundary</div>')
    st.caption("Click a building to select or deselect it. Hover for details. Map and table always show the same selection.")
    return out


def handle_events(DD, cl, out):
    ss = st.session_state; mode = ss.get("draw_mode", "add")
    click = out.get("last_object_clicked") or out.get("last_clicked")
    if click and (click["lat"], click["lng"]) != ss.seen_click:
        ss.seen_click = (click["lat"], click["lng"])
        hit = DD["idx"].at(*O.point_to_hk80(click["lng"], click["lat"]))
        if hit:
            ss.focus = hit; bl = state.apply(cl, DD["by_id"], [hit], "toggle")
            if bl: ss.notice = f"{bl[0]} cannot be selected: its footprint area check failed (see its building card)."
            state.bump(); st.rerun()
    shown = set(ss.get("m_types", ["Commercial", "Mixed-use"]))
    for f in out.get("all_drawings") or []:
        key = json.dumps(f.get("geometry"), sort_keys=True)
        if key in ss.seen_draw or (f.get("geometry") or {}).get("type") != "Polygon": continue
        ss.seen_draw.add(key)
        polys = O.polygons_from_obj({"type": "FeatureCollection", "features": [f]}, "EPSG:4326")
        ids = sorted(i for i in DD["idx"].in_polygons(polys) if C.main_class(DD["by_id"][i]) in shown or (mode == "remove" and i in cl["ids"]))
        bl = state.apply(cl, DD["by_id"], ids, mode)
        ss.notice = (f"Drawn area: {len(ids)} building(s) {dict(add='added', remove='removed', replace='selected')[mode]}"
                     + (f"; {len(bl)} could not be selected (data check)" if bl else "") + ".")
        state.bump(); st.rerun()


def live_panel(meta, DD, cl, R, A):
    ss = st.session_state
    if not cl["ids"]:
        html('<div class="card"><div class="eyebrow">Start here</div><h4>Build a cluster</h4><div class="sub">Click buildings on the map, '
             'draw an area with the ▢ or ⬠ tool, tick them in the table below, or let the tool suggest a group of large, close buildings.</div>'
             '<div class="sub" style="margin-top:.45rem"><b>ⓘ buttons</b> next to results explain each finance term (present value, payback, '
             'capex …) in two sentences. To see how districts differ, open the <b>Compare districts</b> tab.</div></div>')
        if st.button("Suggest a starting cluster", key="suggest_start", type="primary"):
            items = C.suggest_clusters(DD["recs"], DD["idx"], 150, 6, ss.overrides, inputs.global_defaults(), state.table())
            ids = items[0]["ids"] if items else C.starter_cluster(DD["recs"], ss.overrides)
            cl["ids"] = list(ids); ss.focus = ids[0] if ids else None; ss.fit = ("cluster", ss.ver)
            ss.notice = ("Suggested: a group of large commercial and mixed-use buildings within 300 m of each other, where no single building "
                         "carries more than half the cooling demand. Edit it freely.")
            state.bump(); st.rerun()
        return
    ag = C.aggregates([DD["by_id"][i] for i in cl["ids"]], ss.overrides, inputs.global_defaults(), state.table())
    stats = (f'<div class="kv"><div><div class="k">Buildings</div><div class="v">{ag["n_included"]}/{ag["n"]}</div></div>'
             f'<div><div class="k">Peak (est.)</div><div class="v">{ag["peak_kw"] / 1000:,.1f} MW</div></div>'
             f'<div><div class="k">Pipe length</div><div class="v">{A.network_m:,.0f} m</div></div></div>')
    head = f'<div class="eyebrow">Cluster at a glance · {ss.active[meta["id"]]}</div>'
    if R is None:
        html(f'<div class="card">{head}{stats}<div class="sub">No result yet: the selected buildings have no cooling inputs, or a model input is invalid.</div></div>'); return
    S = R["scenarios"]; best = V.best_by_row(R)
    rows = "".join(f'<tr><td>{OPTION_NAMES[k]}</td><td class="v{" win" if best.get("pv_cost") == k else ""}">{mhk(S[k]["pv_cost"])}</td>'
                   f'<td class="v{" win" if best.get("payback") == k else ""}">{"—" if k == "Individual" else yrs(S[k]["discounted_payback"])}</td></tr>'
                   for k in ("Individual", "CMCS", "DCS"))
    html(f'<div class="card">{head}{stats}<div class="verdict small" style="margin-top:.6rem">{V.headline(R)}</div>'
         f'<div class="opt" style="border:0;padding:.3rem 0 0"><table><tr><td class="sub">Option</td><td class="sub" style="text-align:right">'
         f'Lifecycle cost (PV)</td><td class="sub" style="text-align:right">Payback</td></tr>{rows}</table></div>'
         f'<div class="sub" style="margin-top:.5rem">Full comparison, charts and inputs: <b>Compare options</b> tab.</div></div>')


def _reset_all(bid): st.session_state.overrides.pop(bid, None)


def info_panel(meta, DD, cl):
    ss = st.session_state; by_id = DD["by_id"]
    opts = [i for i in dict.fromkeys([ss.focus, *cl["ids"]]) if i in by_id]
    if not opts: return
    bid = st.selectbox("Building details", opts, index=opts.index(ss.focus) if ss.focus in opts else 0,
                       format_func=lambda i: f"{by_id[i].name}  ({i})" + ("" if i in cl["ids"] else " · not in cluster"), key=f"focus_{ss.ver}")
    ss.focus = bid; r = by_id[bid]
    use = " · ".join(x for x in (f"Primary use: {r.primary_use}" if r.primary_use else "", f"Secondary: {r.secondary_use}" if r.secondary_use else "") if x)
    kv = "".join(f'<div><div class="k">{lab} {badge(v.status)}</div><div class="v">{num(v.value, u)}</div></div>'
                 for lab, v, u in (("Footprint", r.footprint_area_m2, " m²"), ("Storeys", r.storeys, ""), ("Height", r.height_m, " m")))
    html(f'<div class="card"><div class="eyebrow">{C.main_class(r)}</div><h4>{r.name}</h4><div class="sub">{use}</div><div class="kv">{kv}</div>'
         f'<div class="sub">{r.building_id} · {meta["name"]}</div></div>')
    if r.match_tier != "exact_id": note("Data check: the footprint area in the attributes differs from the polygon area (courtyard or data issue), "
                                        "so this building cannot be added to a cluster.", "warn")
    if len(r.use_mix) > 1: st.caption("Use shares in the source: " + ", ".join(f"{l.split('_')[0]} {s:.0%}" for l, s in r.use_mix)
                                      + " (what the shares measure is not documented; defaults are weighted by them)")
    st.markdown("**Cooling inputs**")
    st.caption("Not in any source dataset: defaults are illustrative placeholders by use. Edit a value to set your own; source data never change.")
    eff, _, _ = C.building_inputs(r, ss.overrides, inputs.global_defaults(), state.table())
    rows = pd.DataFrame([{"Input": FIELD_UI[f][0], "Value": eff[f].value, "Basis": status_label(eff[f].status), "From": eff[f].ref or ""} for f in EDITABLE])
    okey = json.dumps(ss.overrides.get(bid, {}), sort_keys=True)
    ed = st.data_editor(rows, key=f"inp_{bid}_{abs(hash(okey))}", hide_index=True, disabled=["Input", "Basis", "From"], width="stretch",
                        column_config={"Value": st.column_config.NumberColumn("Value", format="%.2f", help="Type a new value.")})
    changed = False
    for f, (_, row) in zip(EDITABLE, ed.iterrows()):
        v = row["Value"]; lo, hi = FIELD_UI[f][1], FIELD_UI[f][2]
        if v is None or v != v: continue
        v = min(max(float(v), lo), hi)
        if eff[f].value is None or abs(v - float(eff[f].value)) > 1e-9: ss.overrides.setdefault(bid, {})[f] = v; changed = True
    if changed: state.bump(); st.rerun()
    st.button("Reset this building to defaults", key=f"rs_{bid}", on_click=_reset_all, args=(bid,), disabled=not ss.overrides.get(bid))
    with st.expander("All source attributes"):
        st.dataframe(pd.DataFrame([{"Attribute": k, "Value": "" if v is None else str(v)} for k, v in [*r.attrs, *r.source_ids]]), hide_index=True, width="stretch")
        if r.age_year.value: st.caption(f"BDBIAR year {r.age_year.value:.0f} is the building's approval year, NOT the age of its cooling plant.")


MAIN_COLS = ["Select", "Name", "Type", "Storeys", "GFA (m²)", "GFA basis", "Peak (kW, est.)"]
MORE_COLS = ["ID", "Primary use", "Secondary use", "Footprint (m²)", "Height (m)", "Load (W/m²)", "Load basis", "Hours/yr", "Approval year", "OZP zone", "Data check"]


@st.cache_data(show_spinner=False)
def district_rows(did, ov_json, tkey, cop, stamp=""):
    ov, tab = json.loads(ov_json), {k: tuple(v) for k, v in json.loads(tkey).items()}
    out = []
    for r in state.district_data(did, stamp)["recs"]:
        f, pk, _ = C.building_inputs(r, ov, {"cop_existing": cop}, tab)
        out.append({"ID": r.building_id, "Name": r.name, "Type": C.main_class(r), "Primary use": r.primary_use, "Secondary use": r.secondary_use,
                    "Footprint (m²)": r.footprint_area_m2.value, "Storeys": r.storeys.value, "Height (m)": r.height_m.value,
                    "GFA (m²)": f["gfa_m2"].value, "GFA basis": status_label(f["gfa_m2"].status), "Load (W/m²)": f["load_w_m2"].value,
                    "Load basis": status_label(f["load_w_m2"].status), "Hours/yr": f["hours"].value, "Peak (kW, est.)": pk,
                    "Approval year": r.age_year.value, "OZP zone": dict(r.attrs).get("OZP_Zone_Code_法定图则代码", ""), "Data check": r.match_tier})
    return pd.DataFrame(out)


def table_panel(meta, DD, cl):
    ss = st.session_state
    st.markdown("#### Buildings")
    c1, c2, c3, c4 = st.columns([3, 3, 3, 2])
    scope = c1.radio("Show", ["Selected", "Whole district"], index=0 if cl["ids"] else 1, horizontal=True, key="tbl_scope")
    q = c2.text_input("Search name or ID", key="tbl_q")
    tf = c3.multiselect("Type", list(TYPE_COLORS), key="tbl_types"); minfl = c4.number_input("Min storeys", 0, 200, 0, key="tbl_fl")
    T = district_rows(meta["id"], json.dumps(ss.overrides, sort_keys=True), state.table_key(), inputs.values()["cop_existing"], meta.get("generated", "")).copy()
    T.insert(0, "Select", T["ID"].isin(set(cl["ids"])))
    mask = T["Select"] if scope == "Selected" else pd.Series(True, index=T.index)
    if q: mask &= T["Name"].str.contains(q, case=False, regex=False) | T["ID"].str.contains(q, case=False, regex=False)
    if tf: mask &= T["Type"].isin(tf)
    if minfl: mask &= T["Storeys"].fillna(0) >= minfl
    V_ = T[mask]; total = len(V_); V_ = V_.head(1500)
    if V_.empty: st.info("No buildings match." if scope == "Whole district" else "No buildings selected yet."); return
    more = st.multiselect("More columns", MORE_COLS, key="tbl_more", placeholder="Add columns (ID, use, height, load, hours …)")
    ed = st.data_editor(V_, key=f"tbl_{meta['id']}_{ss.ver}", hide_index=True, width="stretch", height=380,
                        disabled=[c for c in V_.columns if c != "Select"], column_order=MAIN_COLS + list(more),
                        column_config={"Select": st.column_config.CheckboxColumn("Select", help="Tick to add to the cluster; untick to remove. Click a column title to sort."),
                                       "GFA (m²)": st.column_config.NumberColumn(format="%.0f"), "Peak (kW, est.)": st.column_config.NumberColumn(format="%.0f"),
                                       "Storeys": st.column_config.NumberColumn(format="%.0f"), "Footprint (m²)": st.column_config.NumberColumn(format="%.0f"),
                                       "Approval year": st.column_config.NumberColumn(format="%d")})
    ch = ed["Select"].values != V_["Select"].values
    if ch.any():
        add = list(ed["ID"][ch & ed["Select"].values]); rem = list(ed["ID"][ch & ~ed["Select"].values])
        bl = state.apply(cl, DD["by_id"], add, "add") if add else []
        if rem: state.apply(cl, DD["by_id"], rem, "remove")
        if bl: ss.notice = f"{len(bl)} building(s) could not be selected (data check)."
        state.bump(); st.rerun()
    st.caption(f"{total:,} buildings match" + (" (first 1,500 shown)" if total > 1500 else "") + f" · {len(cl['ids'])} selected. "
               "Basis: Source = HK-BFETD, Estimate = calculated, Assumption = placeholder, Your value = your edit.")
    if cl["ids"]:
        members = [DD["by_id"][i] for i in cl["ids"]]; act = ss.active[meta["id"]]
        a, b = st.columns(2)
        a.download_button("Export selected buildings (CSV)", T[T["Select"]].drop(columns=["Select"]).to_csv(index=False).encode("utf-8-sig"),
                          f"{act}.csv", "text/csv", key="dl_sel", width="stretch")
        b.download_button("Export footprints (GeoJSON, WGS84)", json.dumps(C.cluster_geojson(members, act, O.point_to_wgs84), ensure_ascii=False),
                          f"{act}.geojson", "application/geo+json", key="dl_geo", width="stretch", help="Opens in Scribble Maps, geojson.io or QGIS.")
    with st.expander("Import a drawn polygon (Scribble Maps, geojson.io, QGIS)"):
        up = st.file_uploader("GeoJSON or Esri JSON polygon, EPSG:4326 or EPSG:2326. Buildings whose centre is inside are added.", type=["geojson", "json"], key=f"up_{ss.ver}")
        if up is not None:
            try:
                polys, msg = O.parse_upload(up.getvalue()); ids = DD["idx"].in_polygons(polys)
                st.write(f"{msg}; {len(ids)} building(s) of {meta['name']} inside.")
                if ids and st.button(f"Add {len(ids)} building(s)", key="up_add"):
                    state.apply(cl, DD["by_id"], sorted(ids), "add"); state.bump(); st.rerun()
            except Exception as e:
                st.error(f"Could not read the file: {e}")


def render(meta, DD, cl, G, R, A):
    ss = st.session_state
    left, right = st.columns([3, 2], gap="medium")
    with left:
        out = map_panel(meta, DD, cl, G)
        p = G.get("proximity") if cl["ids"] else None
        if p and p.get("within_limit") is False:
            iso = len(G.get("isolated", []))
            note(f"<b>Distance check:</b> {p['n_pairs_over_limit']} pair(s) of the {len(cl['ids'])} selected buildings are more than {inputs.max_m():,.0f} m apart "
                 f"(widest {p['max_distance_m']:,.0f} m)" + (f"; {iso} building(s) have no other selected building within {inputs.max_m():,.0f} m (orange outline)" if iso else "")
                 + ". A screening flag, not an engineering limit: the selection is kept.", "warn")
        elif p and len(cl["ids"]) > 1: note(f"Distance check: every selected building is within {inputs.max_m():,.0f} m of the others (widest {p['max_distance_m']:,.0f} m).")
        if ss.notice: st.caption(ss.notice); ss.notice = None
    with right:
        live_panel(meta, DD, cl, R, A); info_panel(meta, DD, cl)
    handle_events(DD, cl, out)
    table_panel(meta, DD, cl)
