"""Cluster logic, independent of Streamlit so it can be unit-tested.
A cluster = a named set of building ids inside one district. Selection never edits building records."""
import json, math
from dataclasses import replace
from pathlib import Path
from buildings import effective, resolve, EDITABLE
from geometry import (ring_area, ring_centroid, inside, bbox, check_cluster_fast, mst_length, convex_hull,
                      nearest_neighbour_gaps)

ROOT = Path(__file__).resolve().parent

# ILLUSTRATIVE planning densities by HK-BFETD use label (W/m2 peak cooling, equivalent full-load hours, cooled share of GFA).
# Not Hong Kong statistics: replace with metered or design data. Mixed buildings use the share-weighted average.
USE_DEFAULTS = {
    "Office": (110, 2800, 0.85), "Retail": (150, 3200, 0.85), "Restaurant": (160, 3500, 0.85), "Food & Beverage": (160, 3500, 0.85),
    "Accommodation": (120, 4000, 0.85), "Human Health": (120, 5000, 0.85), "Education": (90, 1800, 0.80),
    "Commercial": (120, 3000, 0.85), "Other Commercial": (120, 3000, 0.85),
    "Private Housing": (60, 1500, 0.70), "Public Housing": (60, 1500, 0.70), "Other Housing": (60, 1500, 0.70),
    "Other Industrial": (80, 2500, 0.60), "Non-manufacturing": (80, 2500, 0.60),
}
FALLBACK = (80, 2000, 0.70)
USE_COLOURS = {"Commercial": "#0E6E73", "Mixed-use": "#C98A1B", "Residential": "#9AA9B0", "Industrial": "#7A5C99", "Non-assessed": "#D0D6D9"}


def main_class(rec): return rec.building_type.split("_", 1)[0] if rec.building_type else "Unknown"


def use_defaults(rec, table=None):
    """Share-weighted defaults from the building's use mix. Returns a dict for buildings.resolve().
    table: {use label: (W/m2, hours, cooled share)}; defaults to USE_DEFAULTS (editable in the app)."""
    T = table or USE_DEFAULTS
    mix = rec.use_mix or ((rec.primary_use or "", 1.0),)
    w = sum(s for _, s in mix) or 1.0
    vals = [tuple(T.get(l.split("_", 1)[0], FALLBACK)) for l, _ in mix]
    load = sum(v[0] * s for v, (_, s) in zip(vals, mix)) / w
    hours = sum(v[1] * s for v, (_, s) in zip(vals, mix)) / w
    frac = sum(v[2] * s for v, (_, s) in zip(vals, mix)) / w
    return {"load_w_m2": round(load, 1), "hours": round(hours), "cooled_fraction": round(frac, 3)}


def merged_defaults(rec, global_defaults=None, table=None):
    d = use_defaults(rec, table)
    d.update({k: v for k, v in (global_defaults or {}).items() if v is not None})
    return d


def building_inputs(rec, overrides=None, global_defaults=None, table=None):
    """Effective values with status for every editable field + cooled area, peak kW and annual cooling."""
    f = effective(rec, overrides, merged_defaults(rec, global_defaults, table))
    area, load, hours = f["cooled_area_m2"].value, f["load_w_m2"].value, f["hours"].value
    pk = area * load / 1000 if area is not None and load is not None else None
    return f, pk, (pk * hours if pk is not None and hours is not None else None)


def to_model(records, overrides=None, global_defaults=None, table=None):
    """Tuples for model/lifecycle + list of excluded (id, name, missing fields)."""
    out, excl = [], []
    for r in records:
        f, pk, q = building_inputs(r, overrides, global_defaults, table)
        miss = [k for k in ("cooled_area_m2", "load_w_m2", "hours") if f[k].value is None]
        if miss: excl.append((r.building_id, r.name, miss)); continue
        out.append((r.name, f["cooled_area_m2"].value, f["load_w_m2"].value, f["hours"].value, f["cop_existing"].value))
    return tuple(out), excl


# ---------------------------------------------------------------------------------------------------- spatial
class SpatialIndex:
    """Grid index of footprints (EPSG:2326) for click and polygon selection."""
    def __init__(self, records, cell=200.0):
        self.cell, self.grid, self.recs = cell, {}, {r.building_id: r for r in records}
        for r in records:
            x0, y0, x1, y1 = bbox(r.footprint_hk80)
            for i in range(int(x0 // cell), int(x1 // cell) + 1):
                for j in range(int(y0 // cell), int(y1 // cell) + 1):
                    self.grid.setdefault((i, j), []).append(r.building_id)

    def at(self, x, y):
        """Building whose footprint contains the point; nearest within 5 m otherwise (helps with thin slivers)."""
        cands = self.grid.get((int(x // self.cell), int(y // self.cell)), [])
        for bid in cands:
            if inside((x, y), self.recs[bid].footprint_hk80): return bid
        from geometry import ring_distance
        best = min(((ring_distance([(x, y), (x, y)], self.recs[b].footprint_hk80), b) for b in cands), default=(math.inf, None))
        return best[1] if best[0] <= 5 else None

    def in_polygons(self, polys):
        """Ids whose footprint centroid lies inside any polygon [(outer, [holes])] (EPSG:2326)."""
        out = set()
        for outer, holes in polys:
            x0, y0, x1, y1 = bbox(outer)
            for i in range(int(x0 // self.cell), int(x1 // self.cell) + 1):
                for j in range(int(y0 // self.cell), int(y1 // self.cell) + 1):
                    for bid in self.grid.get((i, j), []):
                        c = self.recs[bid].centroid_hk80
                        if bid not in out and inside(c, outer) and not any(inside(c, h) for h in holes): out.add(bid)
        return out

    def within(self, x, y, radius):
        out = set(); c = self.cell
        for i in range(int((x - radius) // c), int((x + radius) // c) + 1):
            for j in range(int((y - radius) // c), int((y + radius) // c) + 1):
                for bid in self.grid.get((i, j), []):
                    cx, cy = self.recs[bid].centroid_hk80
                    if math.hypot(cx - x, cy - y) <= radius: out.add(bid)
        return out


def starter_cluster(records, overrides=None, max_m=300.0, n=12, classes=("Commercial", "Mixed-use")):
    """Suggest a cluster: the largest-demand non-residential building, plus the next-largest such buildings whose
    centroids lie within max_m of it. Deterministic. Clearly a SUGGESTION for the user to edit."""
    pool = [r for r in records if main_class(r) in classes and r.selectable]
    if not pool: return []
    dem = {r.building_id: (building_inputs(r, overrides)[2] or 0) for r in pool}
    anchor = max(pool, key=lambda r: (dem[r.building_id], r.building_id))
    ax, ay = anchor.centroid_hk80
    near = [r for r in pool if math.hypot(r.centroid_hk80[0] - ax, r.centroid_hk80[1] - ay) <= max_m]
    near.sort(key=lambda r: (-dem[r.building_id], r.building_id))
    return [r.building_id for r in near[:n]]


def dominant_share(ids, dem):
    """Share of the group's cooling demand that comes from its single largest building (0 when the group has no demand)."""
    tot = sum(dem.get(i, 0) for i in ids)
    return max(dem.get(i, 0) for i in ids) / tot if ids and tot > 0 else 0.0


def suggest_clusters(records, index, radius=150.0, min_n=8, overrides=None, global_defaults=None, table=None,
                     classes=("Commercial", "Mixed-use"), k=5, max_share=0.5):
    """Candidate clusters: take the largest-demand building not yet used, group every selectable building of the chosen
    classes whose centroid is within `radius` of it (so members are at most 2 x radius apart), keep groups of >= min_n.
    Groups where one building carries more than `max_share` of the demand are skipped: their result would describe that one
    building (often a large low-rise complex whose estimated GFA is least reliable), not a shared-cooling cluster.
    Deterministic. Computed starting points, not existing systems or recommendations."""
    pool = {r.building_id: r for r in records if r.selectable and (not classes or main_class(r) in classes)}
    dem = {i: (building_inputs(r, overrides, global_defaults, table)[2] or 0) for i, r in pool.items()}
    used, out = set(), []
    for seed in sorted(pool, key=lambda i: (-dem[i], i)):
        if seed in used: continue
        x, y = pool[seed].centroid_hk80
        grp = sorted((i for i in index.within(x, y, radius) if i in pool and i not in used), key=lambda i: (-dem[i], i))
        if len(grp) >= min_n and (max_share is None or dominant_share(grp, dem) <= max_share):
            out.append({"ids": grp, "seed": seed, "demand_kwh": sum(dem[i] for i in grp)}); used.update(grp)
            if len(out) >= k: break
    return out


def clusters_to_json(clusters):
    """clusters: {name: {"district": id, "ids": [...]}} -> JSON text (schema_version 1)."""
    return json.dumps({"schema_version": 1, "clusters": [{"name": n, "district": c["district"], "building_ids": list(c["ids"])}
                                                          for n, c in clusters.items()]}, ensure_ascii=False, indent=1)


def clusters_from_json(text, known):
    """known: {district id: set of building ids}. Returns ({name: cluster}, problems). Unknown ids are dropped and reported."""
    data, out, probs = json.loads(text), {}, []
    for c in data.get("clusters", []):
        d = c.get("district")
        if d not in known: probs.append(f"{c.get('name')}: district {d!r} is not prepared here"); continue
        ids = [i for i in c.get("building_ids", []) if i in known[d]]
        if len(ids) < len(c.get("building_ids", [])): probs.append(f"{c.get('name')}: {len(c['building_ids']) - len(ids)} unknown building id(s) dropped")
        out[c.get("name") or f"Imported {len(out) + 1}"] = {"district": d, "ids": ids}
    return out, probs


# ---------------------------------------------------------------------------------------------------- summaries
def aggregates(records, overrides=None, global_defaults=None, table=None):
    rows = [(r, *building_inputs(r, overrides, global_defaults, table)) for r in records]
    gfa = sum(f["gfa_m2"].value or 0 for _, f, _, _ in rows)
    mix = {}
    for r, *_ in rows: mix[main_class(r)] = mix.get(main_class(r), 0) + 1
    status = {}
    for _, f, _, _ in rows:
        for k in ("gfa_m2", "load_w_m2", "hours", "cop_existing"):
            status.setdefault(k, {}); s = f[k].status; status[k][s] = status[k].get(s, 0) + 1
    by_cls = {}
    for r, f, pk, _ in rows: by_cls[main_class(r)] = by_cls.get(main_class(r), 0) + (f["cooled_area_m2"].value or 0)
    est = sum(f["gfa_m2"].value or 0 for _, f, _, _ in rows if f["gfa_m2"].status != "source")
    hts = [r.height_m.value for r, *_ in rows if r.height_m.value]; fls = [r.storeys.value for r, *_ in rows if r.storeys.value]
    return dict(cooled_by_class=dict(sorted(by_cls.items(), key=lambda kv: -kv[1])), gfa_estimated_share=(est / gfa if gfa else None),
                max_height_m=max(hts) if hts else None, mean_storeys=sum(fls) / len(fls) if fls else None,
                n_included=sum(1 for _, f, pk, q in rows if pk is not None and q is not None),
                n=len(rows), gfa_m2=gfa, cooled_m2=sum(f["cooled_area_m2"].value or 0 for _, f, _, _ in rows),
                peak_kw=sum(p or 0 for *_, p, _ in rows), cooling_kwh=sum(q or 0 for *_, q in rows), mix=mix, status=status,
                footprint_m2=sum(r.footprint_area_m2.value or 0 for r, *_ in rows))


def geometry_summary(records, max_m=300.0, route_factor=1.3):
    rings = {r.building_id: r.footprint_hk80 for r in records}
    if not rings: return dict(n=0)
    prox = check_cluster_fast(rings, max_m)
    pts = [r.centroid_hk80 for r in records]
    mst = mst_length(pts) if len(pts) <= 1500 else None
    hull = convex_hull([p for r in records for p in r.footprint_hk80])
    cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    gaps = nearest_neighbour_gaps(rings) if 1 < len(rings) <= 600 else {}
    return dict(n=len(rings), proximity=prox, mst_m=mst, network_m=(mst * route_factor if mst is not None else None),
                hull_hk80=hull, hull_area_m2=ring_area(hull) if len(hull) > 3 else 0.0, centre_hk80=(cx, cy),
                isolated=sorted(((b, g) for b, g in gaps.items() if g is not None and g > max_m), key=lambda t: -t[1]))


# ---------------------------------------------------------------------------------------------------- DCS registry
def load_dcs(path=None):
    return json.loads(Path(path or ROOT / "config" / "dcs_systems.json").read_text(encoding="utf-8"))


def dcs_coverage(records, areas):
    """areas: {dcs_id: [(outer, holes)] EPSG:2326}. Returns {dcs_id: n buildings whose centroid is inside}."""
    out = {}
    for k, polys in areas.items():
        out[k] = sum(1 for r in records if any(inside(r.centroid_hk80, o) and not any(inside(r.centroid_hk80, h) for h in hs) for o, hs in polys))
    return out


# ---------------------------------------------------------------------------------------------------- export
def cluster_geojson(records, name, to_wgs84=None):
    """FeatureCollection of the cluster's footprints, WGS84 if a transformer is given (for Scribble Maps / geojson.io)."""
    feats = []
    for r in records:
        ring = [list(to_wgs84(*p)) if to_wgs84 else list(p) for p in r.footprint_hk80]
        feats.append({"type": "Feature", "properties": {"building_id": r.building_id, "name": r.name, "cluster": name,
                                                         "use": main_class(r)}, "geometry": {"type": "Polygon", "coordinates": [ring]}})
    fc = {"type": "FeatureCollection", "name": name, "features": feats}
    if not to_wgs84: fc["crs"] = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::2326"}}
    return fc
