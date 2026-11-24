"""Map overlays and coordinate conversion: district boundaries, DCS service areas, Kai Tak OZP zones, uploaded polygons.
Reads GeoJSON and Esri JSON with the same parser as tools/prepare_districts.py (one implementation)."""
import json
from functools import lru_cache
from pathlib import Path
from tools.prepare_districts import geometry_polygons, detect_crs, to_hk80, is_esri_json, PrepError

ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=2)
def _tr(src, dst):
    from pyproj import Transformer
    return Transformer.from_crs(src, dst, always_xy=True)


def to_wgs84_ring(ring):
    xs, ys = _tr(2326, 4326).transform([p[0] for p in ring], [p[1] for p in ring])
    return [(round(x, 7), round(y, 7)) for x, y in zip(xs, ys)]


def point_to_hk80(lon, lat): return _tr(4326, 2326).transform(lon, lat)
def point_to_wgs84(x, y): return _tr(2326, 4326).transform(x, y)


def rings_to_wgs84(rings):
    """Bulk conversion of many rings (one pyproj call). rings: list of rings in EPSG:2326."""
    flat = [p for r in rings for p in r]
    if not flat: return []
    xs, ys = _tr(2326, 4326).transform([p[0] for p in flat], [p[1] for p in flat])
    out, i = [], 0
    for r in rings:
        out.append([(round(xs[k], 7), round(ys[k], 7)) for k in range(i, i + len(r))]); i += len(r)
    return out


def polygons_from_obj(obj, declared=None):
    """Any GeoJSON / Esri JSON polygon object -> [(outer, holes)] in EPSG:2326."""
    raw = geometry_polygons(obj)
    return to_hk80(raw, detect_crs(obj, raw, declared))


def polygons_from_file(path):
    return polygons_from_obj(json.loads(Path(path).read_text(encoding="utf-8-sig")))


def parse_upload(data: bytes):
    """User-supplied polygon file (e.g. exported from Scribble Maps or geojson.io). Non-polygon features are ignored
    and counted. Returns (polygons EPSG:2326, message)."""
    obj = json.loads(data.decode("utf-8-sig"))
    skipped = 0
    if isinstance(obj, dict) and obj.get("type") == "FeatureCollection":
        keep = [f for f in obj["features"] if (f.get("geometry") or {}).get("type") in ("Polygon", "MultiPolygon")]
        skipped = len(obj["features"]) - len(keep); obj = {**obj, "features": keep}
        if not keep: raise PrepError("the file contains no Polygon or MultiPolygon features")
    polys = polygons_from_obj(obj)
    return polys, f"{len(polys)} polygon(s) read" + (f"; {skipped} non-polygon feature(s) ignored" if skipped else "")


def district_boundary(pkg_dir):
    p = Path(pkg_dir) / "boundary.geojson"
    return polygons_from_file(p) if p.exists() else []


def ozp_zones(path=ROOT / "config" / "areas" / "kai_tak_ozp_S_K22_9_zone.json"):
    """Kai Tak OZP zones as [(label, description, [(outer, holes)])] in EPSG:2326."""
    p = Path(path)
    if not p.exists(): return []
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not is_esri_json(obj): return []
    out = []
    for f in obj["features"]:
        a = f["attributes"]
        out.append((a.get("ZONE_LABEL", "").strip(), a.get("DESC_ENG", "").strip(),
                    geometry_polygons({"features": [f], "spatialReference": obj.get("spatialReference")})))
    return out


def zone_colour(label):
    l = label.upper()
    for k, c in (("OU", "#B9A7D6"), ("CDA", "#E6B8A2"), ("C", "#F2A7A0"), ("R", "#F7D98B"), ("G/IC", "#A9C8E8"),
                 ("O", "#A8D5A2"), ("GB", "#8FBF88"), ("I", "#C9B8E0")):
        if l.startswith(k): return c
    return "#DDDDDD"
