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

def check_cluster(rings, max_m=300.0):
    """rings: {id: outer ring}. Returns the largest pairwise edge-to-edge distance and every pair above max_m."""
    ids, over, worst = list(rings), [], 0.0
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            d = ring_distance(rings[a], rings[b]); worst = max(worst, d)
            if d > max_m: over.append((a, b, d))
    return dict(n=len(ids), max_distance_m=worst, limit_m=max_m, within_limit=not over, pairs_over_limit=sorted(over, key=lambda t: -t[2]))
