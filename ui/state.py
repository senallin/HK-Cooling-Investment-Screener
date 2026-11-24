"""Session state and cached loading. The active cluster's id list is the single source of truth for map, table and results.
Clusters are named and kept per district so they can be compared across districts."""
import json
from dataclasses import replace
from pathlib import Path
import streamlit as st

import clusters as C
import districts as D
import overlays as O

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------------------------------- cached data
@st.cache_resource(show_spinner="Loading the district, checking its fingerprints and converting footprints for the map ...")
def district_data(did, stamp=""):
    """stamp = package build time, so rebuilding a package invalidates the cache."""
    recs, rep = D.load_district(did)
    wgs = O.rings_to_wgs84([r.footprint_hk80 for r in recs])
    cen = O.rings_to_wgs84([[r.centroid_hk80] for r in recs])
    recs = [replace(r, footprint=tuple(w), lon=c[0][0], lat=c[0][1]) for r, w, c in zip(recs, wgs, cen)]
    bnd = O.district_boundary(D.ROOT_DIR / did)
    return dict(id=did, recs=recs, by_id={r.building_id: r for r in recs}, rep=rep, manifest=rep["manifest"], idx=C.SpatialIndex(recs),
                boundary=bnd, boundary_wgs=[[O.to_wgs84_ring(o)] + [O.to_wgs84_ring(h) for h in hs] for o, hs in bnd])


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
def geo_summary(did, ids, max_m, route_factor, stamp=""):
    by = district_data(did, stamp)["by_id"]
    g = C.geometry_summary([by[i] for i in ids], max_m, route_factor)
    if g.get("n"): g["hull_wgs"] = O.to_wgs84_ring(g["hull_hk80"])
    return g


@st.cache_data(show_spinner=False)
def coverage(did, ids, stamp=""):
    _, areas, _ = dcs_data(); by = district_data(did, stamp)["by_id"]
    return C.dcs_coverage([by[i] for i in ids], areas)


# ---------------------------------------------------------------------------------------------------- session
def init():
    ss = st.session_state
    for k, v in dict(clusters={}, active={}, overrides={}, focus=None, ver=0, seen_click=None, seen_draw=set(), fit=None, notice=None,
                     candidates=None).items():
        if k not in ss: ss[k] = v
    if "use_table" not in ss: ss.use_table = {k: list(v) for k, v in C.USE_DEFAULTS.items()}


def table():
    return {k: tuple(v) for k, v in st.session_state.use_table.items()}


def table_key(): return json.dumps(st.session_state.use_table, sort_keys=True)


def bump(): st.session_state.ver += 1


def names(did): return [n for n, c in st.session_state.clusters.items() if c["district"] == did]


def new_cluster(did, dname, ids=(), name=None):
    ss = st.session_state; base = name or f"{dname} cluster"; k = 1
    n = name if name and name not in ss.clusters else f"{base} {k}"
    while n in ss.clusters: k += 1; n = f"{base} {k}"
    ss.clusters[n] = {"district": did, "ids": list(ids)}; ss.active[did] = n
    return n


def active(did, dname):
    ss = st.session_state
    if not names(did): new_cluster(did, dname)
    if ss.active.get(did) not in names(did): ss.active[did] = names(did)[0]
    return ss.active[did]


def apply(cl, by_id, ids, how):
    """how: add | remove | toggle | replace. Returns names of buildings that cannot be selected (data check failed)."""
    s = set(cl["ids"]) if how != "replace" else set(); blocked = []
    for i in ids:
        r = by_id[i]
        if how == "remove" or (how == "toggle" and i in s): s.discard(i)
        elif r.selectable: s.add(i)
        else: blocked.append(r.name)
    cl["ids"] = [i for i in cl["ids"] if i in s] + sorted(s - set(cl["ids"]))
    return blocked
