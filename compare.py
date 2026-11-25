"""Compare districts: find clusters with the same characteristics in several districts and compare their lifecycle results.
Pure Python (no Streamlit), deterministic, unit-tested.

Matching rule (the same in every district):
  * pool  = selectable buildings of the chosen classes whose storeys lie in the chosen range;
  * seeds = every pool building, visited in a fixed pseudo-random order (seeded), so the sample is spread across the district
            instead of starting from the biggest buildings;
  * a cluster = the seed and its nearest unused pool neighbours whose centres lie within max_d / 2 of the seed, so no two
            members are more than max_d apart (centre to centre); exactly n buildings;
  * clusters do not overlap (each building is used once) and one building may carry at most max_share of the demand;
  * at most k clusters per district.
Feature A shows the TYPICAL cluster of each district: the one whose shared-plant saving per MW is closest to the district median.
Feature B shows the distribution over all matched clusters.
"""
import math, random, statistics
from dataclasses import replace

import clusters as C
import lifecycle as L
from geometry import mst_length, convex_hull, ring_area
from model import validate

CLASSES = ("Commercial", "Mixed-use", "Residential", "Industrial")


def _storeys(r): return r.storeys.value


def pool_of(records, classes=("Commercial", "Mixed-use"), floors=(1, 200)):
    lo, hi = floors
    return [r for r in records if r.selectable and (not classes or C.main_class(r) in classes)
            and _storeys(r) is not None and lo <= _storeys(r) <= hi]


def match_clusters(records, n=6, max_d=300.0, floors=(1, 200), classes=("Commercial", "Mixed-use"), k=50,
                   overrides=None, global_defaults=None, table=None, seed=7, max_share=0.5):
    """Up to k non-overlapping clusters of exactly n buildings matching the rule above. Returns lists of building ids."""
    pool = pool_of(records, classes, floors)
    if len(pool) < n or n < 1: return []
    idx = C.SpatialIndex(pool, cell=max(50.0, max_d / 2)); by = {r.building_id: r for r in pool}
    dem = {}
    def d(i):
        if i not in dem: dem[i] = C.building_inputs(by[i], overrides, global_defaults, table)[2] or 0.0
        return dem[i]
    order = sorted(by); random.Random(seed).shuffle(order)
    used, out = set(), []
    for s in order:
        if s in used: continue
        x, y = by[s].centroid_hk80
        near = [i for i in idx.within(x, y, max_d / 2) if i not in used]
        if len(near) < n: continue
        near.sort(key=lambda i: (math.hypot(by[i].centroid_hk80[0] - x, by[i].centroid_hk80[1] - y), i))
        grp = near[:n]
        if s not in grp: grp = [s] + grp[:n - 1]
        if n > 1 and max_share is not None and C.dominant_share(grp, {i: d(i) for i in grp}) > max_share: continue
        out.append(grp); used.update(grp)
        if len(out) >= k: break
    return out


def evaluate_cluster(members, base, overrides=None, global_defaults=None, table=None, dcs_areas=None):
    """Lifecycle results and characteristics for one cluster (list of records) under assumptions `base`. None if not computable."""
    b, excl = C.to_model(members, overrides, global_defaults, table)
    if not b: return None
    pts = [r.centroid_hk80 for r in members]
    A = replace(base, buildings=b, network_m=(mst_length(pts) * base.cmcs_route_factor if len(pts) > 1 else 0.0))
    if validate(A): return None
    R = L.evaluate(A); S = R["scenarios"]
    hull = convex_hull([p for r in members for p in r.footprint_hk80])
    ha = (ring_area(hull) if len(hull) > 3 else 0.0) / 1e4
    gfa = {}
    for r in members:
        f = C.building_inputs(r, overrides, global_defaults, table)[0]
        gfa[C.main_class(r)] = gfa.get(C.main_class(r), 0.0) + (f["gfa_m2"].value or 0.0)
    gt = sum(gfa.values()) or 1.0
    cov = C.dcs_coverage(members, dcs_areas or {}); in_dcs = max(cov.values(), default=0)
    mw = R["peak_kw"] / 1e3
    return dict(ids=[r.building_id for r in members], n=len(members), excluded=len(excl), peak_mw=mw,
                density_kw_ha=(R["peak_kw"] / ha if ha > 0.01 else None), pipe_m=A.network_m,
                commercial_share=gfa.get("Commercial", 0.0) / gt, mixed_share=gfa.get("Mixed-use", 0.0) / gt,
                mean_storeys=statistics.mean(r.storeys.value for r in members if r.storeys.value is not None),
                in_dcs=in_dcs, best=R["best"],
                npv_cmcs=S["CMCS"]["npv_saving"], npv_dcs=S["DCS"]["npv_saving"],
                npv_cmcs_per_mw=(S["CMCS"]["npv_saving"] / mw if mw else None), npv_dcs_per_mw=(S["DCS"]["npv_saving"] / mw if mw else None),
                pv_individual=S["Individual"]["pv_cost"])


def district_context(records, overrides=None, global_defaults=None, table=None):
    """District-wide mix: share of (estimated) floor area by building class, and building count."""
    gfa = {}
    for r in records:
        g = C.building_inputs(r, overrides, global_defaults, table)[0]["gfa_m2"].value or 0.0
        gfa[C.main_class(r)] = gfa.get(C.main_class(r), 0.0) + g
    tot = sum(gfa.values()) or 1.0
    return dict(n=len(records), gfa_m2=tot, share={k: v / tot for k, v in gfa.items()},
                commercial_share=gfa.get("Commercial", 0.0) / tot, mixed_share=gfa.get("Mixed-use", 0.0) / tot,
                residential_share=gfa.get("Residential", 0.0) / tot)


def summarise(results, metric="npv_cmcs_per_mw"):
    """Distribution summary of one metric over a district's clusters."""
    v = sorted(x[metric] for x in results if x.get(metric) is not None)
    if not v: return dict(n=0)
    q = statistics.quantiles(v, n=4) if len(v) >= 2 else [v[0]] * 3
    return dict(n=len(v), median=statistics.median(v), q1=q[0], q3=q[2], lo=v[0], hi=v[-1],
                share_cmcs_pays=sum(1 for x in results if x["npv_cmcs"] > 0) / len(results),
                share_dcs_pays=sum(1 for x in results if x["npv_dcs"] > 0) / len(results))


def typical(results, metric="npv_cmcs_per_mw"):
    """The cluster whose metric is closest to the median (ties: lower index). None when empty."""
    v = [x for x in results if x.get(metric) is not None]
    if not v: return None
    med = statistics.median(x[metric] for x in v)
    return min(v, key=lambda x: abs(x[metric] - med))


def run_district(records, base, n=6, max_d=300.0, floors=(1, 200), classes=("Commercial", "Mixed-use"), k=50,
                 overrides=None, global_defaults=None, table=None, dcs_areas=None, seed=7):
    by = {r.building_id: r for r in records}
    groups = match_clusters(records, n, max_d, floors, classes, k, overrides, global_defaults, table, seed)
    res = [x for x in (evaluate_cluster([by[i] for i in g], base, overrides, global_defaults, table, dcs_areas) for g in groups) if x]
    return dict(results=res, context=district_context(records, overrides, global_defaults, table),
                pool=len(pool_of(records, classes, floors)))
