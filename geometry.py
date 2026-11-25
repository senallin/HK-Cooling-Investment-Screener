"""Planar geometry in metres (Hong Kong 1980 Grid, EPSG:2326). Pure Python. Distance = shortest edge-to-edge gap."""
import math

def ring_area(r):
    return abs(sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1))) / 2

def ring_centroid(r):
    a = cx = cy = 0.0
    for i in range(len(r) - 1):
        f = r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]
        a += f; cx += (r[i][0] + r[i + 1][0]) * f; cy += (r[i][1] + r[i + 1][1]) * f
    if abs(a) < 1e-9:
        return (sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r))
    return (cx / (3 * a), cy / (3 * a))

def bbox(r):
    xs, ys = [p[0] for p in r], [p[1] for p in r]
    return min(xs), min(ys), max(xs), max(ys)

def _pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = 0 if dx == dy == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)

def _cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

def _seg_intersect(p1, p2, p3, p4):
    d1, d2, d3, d4 = _cross(p3, p4, p1), _cross(p3, p4, p2), _cross(p1, p2, p3), _cross(p1, p2, p4)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0) and d1 * d2 < 0 and d3 * d4 < 0

def inside(p, r):
    c = False
    for i in range(len(r) - 1):
        (x1, y1), (x2, y2) = r[i], r[i + 1]
        if (y1 > p[1]) != (y2 > p[1]) and p[0] < (x2 - x1) * (p[1] - y1) / (y2 - y1) + x1: c = not c
    return c

def ring_distance(a, b):
    """Shortest distance between two polygon outlines' areas (0 if they touch, cross or one contains the other)."""
    ba, bb = bbox(a), bbox(b)
    if ba[0] <= bb[2] and bb[0] <= ba[2] and ba[1] <= bb[3] and bb[1] <= ba[3]:
        if inside(a[0], b) or inside(b[0], a): return 0.0
        for i in range(len(a) - 1):
            for j in range(len(b) - 1):
                if _seg_intersect(a[i], a[i + 1], b[j], b[j + 1]): return 0.0
    best = math.inf
    for i in range(len(a) - 1):
        for j in range(len(b) - 1):
            for p, s0, s1 in ((a[i], b[j], b[j + 1]), (b[j], a[i], a[i + 1])):
                best = min(best, _pt_seg(p, s0, s1))
    return best

def _radius(r, c): return max(math.hypot(p[0] - c[0], p[1] - c[1]) for p in r)

def check_cluster_fast(rings, max_m=300.0, max_n=1500):
    """Same result as check_cluster, but prunes pairs with bounds so large clusters stay fast.
    For a pair with centroid gap d and vertex radii ra, rb: max(0, d-ra-rb) <= edge distance <= d+ra+rb.
    Only pairs whose bounds straddle the limit, or that could be the widest pair, are measured exactly."""
    ids = list(rings)
    if len(ids) > max_n: return dict(n=len(ids), max_distance_m=None, limit_m=max_m, within_limit=None, pairs_over_limit=[], skipped=True)
    cen = {i: ring_centroid(list(rings[i])) for i in ids}; rad = {i: _radius(rings[i], cen[i]) for i in ids}
    over, cand, best_lo = [], [], 0.0
    exact = {}
    def ex(a, b):
        k = (a, b)
        if k not in exact: exact[k] = ring_distance(rings[a], rings[b])
        return exact[k]
    for i, a in enumerate(ids):
        ca, ra = cen[a], rad[a]
        for b in ids[i + 1:]:
            d = math.hypot(ca[0] - cen[b][0], ca[1] - cen[b][1]); lo, hi = max(0.0, d - ra - rad[b]), d + ra + rad[b]
            if lo > max_m: over.append((a, b, None))
            elif hi > max_m:
                v = ex(a, b)
                if v > max_m: over.append((a, b, v))
            cand.append((hi, lo, a, b)); best_lo = max(best_lo, lo)
    worst, worst_pair = 0.0, None
    for hi, lo, a, b in sorted(cand, reverse=True):
        if hi < max(worst, best_lo): break
        v = ex(a, b)
        if v > worst: worst, worst_pair = v, (a, b)
    n_over = len(over)
    if n_over > 200:   # list 200 pairs chosen by centroid gap (approximately the widest) plus the widest pair; all measured exactly
        key = {(a, b): math.hypot(cen[a][0] - cen[b][0], cen[a][1] - cen[b][1]) for a, b, _ in over}
        keep = sorted(over, key=lambda t: -key[(t[0], t[1])])[:200]
        if worst_pair and worst > max_m and all((a, b) != worst_pair for a, b, _ in keep): keep[-1] = (*worst_pair, worst)
        over = keep
    over = sorted(((a, b, v if v is not None else ex(a, b)) for a, b, v in over), key=lambda t: -t[2])
    return dict(n=len(ids), max_distance_m=worst, limit_m=max_m, within_limit=not over, pairs_over_limit=over,
                n_pairs_over_limit=n_over, skipped=False)

def nearest_neighbour_gaps(rings):
    """Edge-to-edge distance from each building to its nearest other building in the set (isolation check)."""
    ids = list(rings); cen = {i: ring_centroid(list(rings[i])) for i in ids}; rad = {i: _radius(rings[i], cen[i]) for i in ids}
    out = {}
    for a in ids:
        order = sorted((math.hypot(cen[a][0] - cen[b][0], cen[a][1] - cen[b][1]), b) for b in ids if b != a)
        best = math.inf
        for d, b in order:
            if d - rad[a] - rad[b] > best: break
            best = min(best, ring_distance(rings[a], rings[b]))
        out[a] = best if order else None
    return out

def mst_length(points):
    """Length (m) of the minimum spanning tree through the points (Prim, O(n^2)). A lower bound for a pipe route."""
    n = len(points)
    if n < 2: return 0.0
    best = [math.inf] * n; used = [False] * n; best[0] = 0.0; total = 0.0
    for _ in range(n):
        u = min((i for i in range(n) if not used[i]), key=best.__getitem__); used[u] = True; total += best[u]
        ux, uy = points[u]
        for v in range(n):
            if not used[v]:
                d = math.hypot(points[v][0] - ux, points[v][1] - uy)
                if d < best[v]: best[v] = d
    return total

def convex_hull(points):
    """Monotone chain. Returns a closed ring (anticlockwise)."""
    pts = sorted(set(map(tuple, points)))
    if len(pts) < 3: return pts + pts[:1]
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and _cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and _cross(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    h = lo[:-1] + up[:-1]
    return h + h[:1]

def check_cluster(rings, max_m=300.0):
    """rings: {id: outer ring}. Returns the largest pairwise edge-to-edge distance and every pair above max_m."""
    ids, over, worst = list(rings), [], 0.0
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            d = ring_distance(rings[a], rings[b]); worst = max(worst, d)
            if d > max_m: over.append((a, b, d))
    return dict(n=len(ids), max_distance_m=worst, limit_m=max_m, within_limit=not over, pairs_over_limit=sorted(over, key=lambda t: -t[2]))
