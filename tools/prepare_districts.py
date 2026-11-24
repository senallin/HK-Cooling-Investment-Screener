#!/usr/bin/env python3
"""Reproducible district extraction from the FULL HK-BFETD GeoJSON + CSV.

What it does
  * Reads the two original Hong Kong-wide files READ-ONLY (never modified, fingerprinted before and after).
  * Assigns each building to every configured area by testing its footprint centroid (EPSG:2326 metres)
    against the area polygon. Areas come from official boundary files, user polygons or bounding boxes.
    It does NOT use building names, the Kai Tak workbook or any earlier partial match.
  * Writes one package per area: buildings.geojson (feature text copied byte-for-byte), buildings.csv
    (all original columns, values unchanged), manifest.json, validation_report.md.
  * Rebuilds data/districts/index.json so the app discovers new districts without code changes.

Standard library only. pyproj is needed ONLY if a boundary file is in longitude/latitude (WGS84).

Commands:  check | boundaries FILE | run | verify      (see docs/DATA_PREP.md)
"""
import argparse, codecs, csv, datetime, hashlib, json, math, os, platform, random, re, shutil, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from geometry import ring_centroid  # noqa: E402  (shared with the app so there is one implementation)

VERSION = "2.0.0"
ID_FIELD = "Building_ID_建筑ID"
GEOJSON_NAME = "HK_UBEM_Buildings_Public_v1_1.geojson"
CSV_NAME = "HK_UBEM_Buildings_Public_v1_1.csv"
LICENCE_NOTE = ("HK-BFETD v1.1: CC BY 4.0 according to the Zenodo record cited in the earlier preparation report. "
                "Not verified from the files themselves: confirm at the source and credit the dataset authors. "
                "Footprint licence for Lands Department derived geometry is unconfirmed.")


class PrepError(Exception):
    pass


# ----------------------------------------------------------------------------------------------- logging
_LOG = []
def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True); _LOG.append(line)


def sha256_file(path, chunk=1 << 23):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""): h.update(b)
    return h.hexdigest()


def utc_now(): return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------------------------- streaming GeoJSON
class GeoJSONStream:
    """Streams features from a (possibly 1 GB) GeoJSON FeatureCollection without loading it.
    Layout-independent: uses json.JSONDecoder.raw_decode on a rolling buffer, and yields the EXACT source text of
    each feature together with its parsed object. The header (everything before "features") is parsed into .header."""
    FEAT_RE = re.compile(r'"features"\s*:\s*\[')

    def __init__(self, path, chunk=1 << 22):
        self.path, self.chunk = Path(path), chunk
        self.size = self.path.stat().st_size
        self.bytes_read = 0; self.header = None; self.n = 0

    def _chunks(self):
        dec = codecs.getincrementaldecoder("utf-8-sig")()       # handles BOM; copes with multibyte chars split across chunks
        with open(self.path, "rb") as fh:
            while True:
                b = fh.read(self.chunk)
                if not b:
                    tail = dec.decode(b"", final=True)
                    if tail: yield tail
                    return
                self.bytes_read += len(b)
                s = dec.decode(b)
                if s: yield s

    def features(self):
        it, dec, buf = self._chunks(), json.JSONDecoder(), ""
        def more():
            nonlocal buf
            try: buf += next(it); return True
            except StopIteration: return False
        while True:
            m = self.FEAT_RE.search(buf)
            if m: break
            if not more(): raise PrepError(f"{self.path.name}: no \"features\" array found")
        head = buf[:m.start()].rstrip().rstrip(",")
        try: self.header = json.loads(head + "}")
        except json.JSONDecodeError as e: raise PrepError(f"{self.path.name}: cannot parse the header before \"features\": {e}")
        buf, pos = buf[m.end():], 0
        while True:
            while True:
                while pos < len(buf) and buf[pos] in " \t\r\n,": pos += 1
                if pos < len(buf): break
                if not more(): raise PrepError(f"{self.path.name}: file ended inside the features array")
            if buf[pos] == "]": break
            while True:
                try: obj, end = dec.raw_decode(buf, pos); break
                except json.JSONDecodeError as e:
                    if not more(): raise PrepError(f"{self.path.name}: malformed JSON at feature {self.n + 1}: {e}")
            self.n += 1
            yield buf[pos:end], obj
            pos = end
            if pos > (1 << 20): buf, pos = buf[pos:], 0
        while more(): pass
        if buf[pos + 1:].strip() != "}":
            raise PrepError(f"{self.path.name}: unexpected content after the features array (not supported, nothing is guessed)")


# ----------------------------------------------------------------------------------------------- geometry
class RingIndex:
    """Even-odd point-in-ring with a horizontal-band edge index (same rule as geometry.inside, much faster)."""
    def __init__(self, ring):
        self.ring = ring
        xs, ys = [p[0] for p in ring], [p[1] for p in ring]
        self.minx, self.maxx, self.miny, self.maxy = min(xs), max(xs), min(ys), max(ys)
        n = len(ring) - 1
        self.nb = max(1, min(256, int(n ** 0.5)))
        self.h = (self.maxy - self.miny) / self.nb or 1.0
        self.bands = [[] for _ in range(self.nb)]
        for i in range(n):
            (x1, y1), (x2, y2) = ring[i], ring[i + 1]
            if y1 == y2: continue
            lo, hi = (y1, y2) if y1 < y2 else (y2, y1)
            for b in range(self._band(lo), self._band(hi) + 1): self.bands[b].append((x1, y1, x2, y2))

    def _band(self, y): return min(self.nb - 1, max(0, int((y - self.miny) // self.h)))

    def contains(self, x, y):
        if x < self.minx or x > self.maxx or y < self.miny or y > self.maxy: return False
        c = False
        for x1, y1, x2, y2 in self.bands[self._band(y)]:
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
        return c


class Area:
    """One or more polygons (outer ring + holes) in EPSG:2326."""
    def __init__(self, polygons):
        if not polygons: raise PrepError("area has no polygons")
        self.polys = [(RingIndex(o), [RingIndex(h) for h in holes]) for o, holes in polygons]
        self.bbox = (min(p[0].minx for p in self.polys), min(p[0].miny for p in self.polys),
                     max(p[0].maxx for p in self.polys), max(p[0].maxy for p in self.polys))

    def contains(self, x, y):
        b = self.bbox
        if x < b[0] or x > b[2] or y < b[1] or y > b[3]: return False
        for outer, holes in self.polys:
            if outer.contains(x, y) and not any(h.contains(x, y) for h in holes): return True
        return False


def _close(ring):
    r = [tuple(map(float, p[:2])) for p in ring]
    if len(r) < 3: raise PrepError("a boundary ring has fewer than 3 points")
    if r[0] != r[-1]: r.append(r[0])
    if len(r) < 4: raise PrepError("a boundary ring is degenerate")
    return r


def _signed_area(r): return sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1)) / 2


def is_esri_json(obj):
    return isinstance(obj, dict) and isinstance(obj.get("features"), list) and bool(obj["features"]) and \
        all(isinstance(f, dict) and "attributes" in f and "rings" in (f.get("geometry") or {}) for f in obj["features"])


def esri_polygons(rings):
    """Esri JSON polygon rings -> [(outer, [holes])]. Esri rule: clockwise ring = outer, anticlockwise = hole.
    Each hole goes to the outer ring that contains its first vertex; a hole inside no outer is an error, not a guess."""
    rs = [_close(r) for r in rings]
    outers = [(r, []) for r in rs if _signed_area(r) < 0]
    if not outers: raise PrepError("Esri polygon has no clockwise (outer) ring")
    for r in rs:
        if _signed_area(r) > 0:
            host = [o for o in outers if RingIndex(o[0]).contains(*r[0])]
            if not host: raise PrepError("Esri polygon hole lies outside every outer ring")
            host[0][1].append(r)
    return outers


def esri_crs(obj):
    sr = obj.get("spatialReference") or {}
    w = sr.get("latestWkid") or sr.get("wkid")
    return {2326: "EPSG:2326", 102140: "EPSG:2326", 4326: "EPSG:4326"}.get(w)


def geometry_polygons(g):
    """GeoJSON geometry/Feature/FeatureCollection (or Esri JSON FeatureSet) -> [(outer, [holes])] (raw coordinates, no transform)."""
    if is_esri_json(g): return [p for f in g["features"] for p in esri_polygons(f["geometry"]["rings"])]
    t = g.get("type")
    if t == "FeatureCollection": return [p for f in g["features"] for p in geometry_polygons(f)]
    if t == "Feature": return geometry_polygons(g["geometry"]) if g.get("geometry") else []
    if t == "GeometryCollection": return [p for x in g["geometries"] for p in geometry_polygons(x)]
    if t == "Polygon": return [(_close(g["coordinates"][0]), [_close(h) for h in g["coordinates"][1:]])]
    if t == "MultiPolygon": return [(_close(c[0]), [_close(h) for h in c[1:]]) for c in g["coordinates"]]
    raise PrepError(f"unsupported boundary geometry type {t!r} (need Polygon or MultiPolygon)")


def _extent(polys):
    pts = [p for o, hs in polys for r in [o] + hs for p in r]
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


def detect_crs(obj, polys, declared=None):
    """Returns 2326 or 4326. Declared CRS (config or GeoJSON crs member) must agree with the coordinate magnitudes."""
    name = declared or (esri_crs(obj) if is_esri_json(obj) else ((obj.get("crs") or {}).get("properties") or {}).get("name")) if isinstance(obj, dict) else declared
    name = str(name or "")
    decl = 2326 if "2326" in name else 4326 if ("4326" in name or "CRS84" in name.upper()) else None
    x0, y0, x1, y1 = _extent(polys)
    looks = 4326 if max(abs(x0), abs(x1)) <= 180 and max(abs(y0), abs(y1)) <= 90 else \
            2326 if 700000 <= x0 and x1 <= 900000 and 780000 <= y0 and y1 <= 880000 else None
    if decl and looks and decl != looks:
        raise PrepError(f"boundary declares EPSG:{decl} but its coordinates look like EPSG:{looks}")
    out = decl or looks
    if out is None: raise PrepError('cannot tell the boundary CRS; set "crs": "EPSG:2326" or "EPSG:4326" in the config')
    return out


def to_hk80(polys, crs):
    if crs == 2326: return polys
    try: from pyproj import Transformer
    except ImportError: raise PrepError("this boundary is in longitude/latitude: run  python -m pip install pyproj  and retry")
    tr = Transformer.from_crs(4326, 2326, always_xy=True)
    def ring(r):
        xs, ys = tr.transform([p[0] for p in r], [p[1] for p in r]); return list(zip(xs, ys))
    return [(ring(o), [ring(h) for h in hs]) for o, hs in polys]


def norm_name(s): return re.sub(r"[^a-z0-9]+", "", str(s).lower().replace("&", "and"))


def load_json(path):
    try: return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e: raise PrepError(f"cannot read {path}: {e}")


def resolve_area(spec, root=ROOT):
    """Turn one config entry into (Area, info). Types: boundary | polygon_file | bbox."""
    d, t = spec["definition"], spec["definition"].get("type")
    info = {"type": t, "files": []}
    if t == "bbox":
        x0, y0, x1, y1 = d["bbox"]; crs = 2326 if "2326" in d.get("crs", "EPSG:2326") else 4326
        polys = [([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], [])]
        hk = to_hk80(polys, crs)
        info.update(bbox=d["bbox"], crs_in=f"EPSG:{crs}", area_m2=round(abs(_signed_area(hk[0][0])), 1),
                    polygons_hk80=[[[list(p) for p in hk[0][0]]]])
        return Area(hk), info
    if t not in ("boundary", "polygon_file"): raise PrepError(f"{spec['id']}: unknown definition type {t!r}")
    path = (root / d["file"]).resolve()
    if not path.exists(): raise PrepError(f"{spec['id']}: boundary file not found: {d['file']}")
    obj = load_json(path)
    info["files"].append({"name": path.name, "sha256": sha256_file(path)})
    if t == "boundary":
        feats = obj["features"] if isinstance(obj, dict) and obj.get("type") == "FeatureCollection" else None
        if feats is None: raise PrepError(f"{d['file']} is not a GeoJSON FeatureCollection; run the 'boundaries' command to inspect it")
        m = d.get("match", {}); want = {norm_name(v) for v in m.get("values", [])}
        if not want: raise PrepError(f"{spec['id']}: boundary definition needs match.values")
        fields = [m["field"]] if m.get("field") else sorted({k for f in feats for k, v in (f.get("properties") or {}).items() if isinstance(v, str)})
        hits = {fld: [i for i, f in enumerate(feats) if norm_name((f.get("properties") or {}).get(fld, "")) in want] for fld in fields}
        hits = {k: v for k, v in hits.items() if v}
        if not hits:
            sample = sorted({str(v) for f in feats[:60] for v in (f.get("properties") or {}).values() if isinstance(v, str)})[:25]
            raise PrepError(f"{spec['id']}: no boundary feature matches {m.get('values')}. Example values in the file: {sample}")
        if len({tuple(v) for v in hits.values()}) > 1:
            raise PrepError(f"{spec['id']}: several fields match with different results ({list(hits)}); set match.field")
        fld, idx = next(iter(hits.items()))
        found = {norm_name(feats[i]["properties"][fld]) for i in idx}
        if not want <= found: raise PrepError(f"{spec['id']}: only found {sorted(found)} of {m.get('values')}")
        sel = {"type": "FeatureCollection", "features": [feats[i] for i in idx]}
        info.update(match_field=fld, matched_features=len(idx))
    else:
        sel = obj
        if is_esri_json(obj):
            info["format"] = "Esri JSON FeatureSet"
            info["source_attributes"] = [f["attributes"] for f in obj["features"]]
    raw = geometry_polygons(sel)
    crs = detect_crs(obj, raw, d.get("crs")); info["crs_in"] = f"EPSG:{crs}"
    if crs == 4326: info["transformed_with"] = "pyproj (EPSG:4326 -> EPSG:2326)"
    hk = to_hk80(raw, crs)
    info["area_m2"] = round(sum(abs(_signed_area(o)) - sum(abs(_signed_area(h)) for h in hs) for o, hs in hk), 1)
    info["polygons_hk80"] = [[[list(map(lambda v: round(v, 2), p)) for p in o]] + [[list(map(lambda v: round(v, 2), p)) for p in h] for h in hs] for o, hs in hk]
    return Area(hk), info


# ----------------------------------------------------------------------------------------------- helpers
def feature_checks(obj, n):
    g = obj.get("geometry") or {}
    if obj.get("type") != "Feature" or g.get("type") != "Polygon":
        raise PrepError(f"source feature #{n} has geometry {g.get('type')!r}; only Polygon is supported. "
                        "Nothing is dropped silently, so the run stops here.")
    return g["coordinates"][0]


def centroid(ring):
    return ring_centroid([tuple(p[:2]) for p in ring])


def same(a, b):
    """CSV text vs GeoJSON JSON value."""
    if a in (None, "") and b in (None, ""): return True
    if a is None or b is None: return False
    try: return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=0.0)
    except (TypeError, ValueError): return str(a) == str(b)


class Progress:
    def __init__(self, label, size): self.label, self.size, self.next = label, size, 10
    def tick(self, done):
        pct = int(100 * done / self.size) if self.size else 100
        while pct >= self.next and self.next <= 100: log(f"   {self.label}: {self.next}%"); self.next += 10


def load_config(path):
    cfg = load_json(path); ids = [d["id"] for d in cfg["districts"]]
    if len(set(ids)) != len(ids): raise PrepError("duplicate district ids in the config")
    for d in cfg["districts"]:
        if not re.fullmatch(r"[a-z0-9_]+", d["id"]): raise PrepError(f"district id {d['id']!r} must be lowercase letters, digits, underscore")
    return cfg


# ----------------------------------------------------------------------------------------------- commands
def cmd_check(a):
    raw = Path(a.raw); ok = True
    gj, cv = raw / (a.geojson or GEOJSON_NAME), raw / (a.csv or CSV_NAME)
    for p in (gj, cv):
        if p.exists(): log(f"found   {p.name}  ({p.stat().st_size / 1e6:,.1f} MB)")
        else: log(f"MISSING {p}"); ok = False
    if not ok: raise PrepError("place the two original files in the raw folder (see docs/DATA_PREP.md)")
    s = GeoJSONStream(gj); gen = s.features(); first = next(gen)[1]; gen.close()
    crs = json.dumps((s.header or {}).get("crs", {}))
    log(f"GeoJSON header: {crs}")
    if "2326" not in crs: raise PrepError("GeoJSON does not declare EPSG:2326; refusing to guess the coordinate system")
    keys = list(first["properties"]); log(f"GeoJSON properties: {len(keys)} fields; first feature geometry = {first['geometry']['type']}")
    with open(cv, encoding="utf-8-sig", newline="") as fh: head = next(csv.reader(fh))
    if ID_FIELD not in head or ID_FIELD not in keys: raise PrepError(f"identifier column {ID_FIELD!r} not found in both files")
    log(f"CSV header: {len(head)} columns; same names as GeoJSON properties: {set(head) == set(keys)}")
    log("check OK")


def cmd_boundaries(a):
    p = Path(a.file); obj = load_json(p)
    log(f"{p.name}: top-level {'type=' + str(obj.get('type')) if isinstance(obj, dict) else type(obj).__name__}")
    if not (isinstance(obj, dict) and obj.get("type") == "FeatureCollection"):
        log("Not a GeoJSON FeatureCollection. First 600 characters:"); log(p.read_text(encoding="utf-8-sig")[:600])
        raise PrepError("convert to GeoJSON (free: mapshaper.org or QGIS) or send me the first 1,000 characters so a reader can be added")
    feats = obj["features"]; polys = geometry_polygons(obj)
    log(f"{len(feats)} features; crs member: {obj.get('crs')}; detected CRS: EPSG:{detect_crs(obj, polys)}")
    fields = {}
    for f in feats:
        for k, v in (f.get("properties") or {}).items(): fields.setdefault(k, []).append(v)
    for k, vals in fields.items(): log(f"   field {k!r}: e.g. {[str(v)[:40] for v in vals[:4]]}")
    log("Use one of these text fields' values in config/districts.json  (definition.match.values).")


def cmd_run(a):
    out, raw = Path(a.out), Path(a.raw)
    gj, cv = raw / (a.geojson or GEOJSON_NAME), raw / (a.csv or CSV_NAME)
    for p in (gj, cv):
        if not p.exists(): raise PrepError(f"missing original file: {p}  (see docs/DATA_PREP.md)")
    cfg = load_config(a.config)
    specs = [d for d in cfg["districts"] if not a.only or d["id"] in a.only.split(",")]
    if not specs: raise PrepError("no districts selected")
    out.mkdir(parents=True, exist_ok=True)
    for s in specs:
        if (out / s["id"]).exists() and not a.overwrite:
            raise PrepError(f"{out / s['id']} already exists. Nothing was changed. Use --overwrite to archive it and rebuild.")
    log(f"prepare_districts v{VERSION}; districts: {[s['id'] for s in specs]}")
    areas = {}
    for s in specs:
        areas[s["id"]], info = resolve_area(s); s["_info"] = info
        b = areas[s["id"]].bbox
        log(f"   area {s['id']:<18} {s.get('status', 'official'):<11} bbox E{b[0]:,.0f}-{b[2]:,.0f} N{b[1]:,.0f}-{b[3]:,.0f}")
        if s.get("status") == "provisional": log(f"   WARNING: {s['id']} is a PROVISIONAL area; replace its polygon with an official boundary")

    log("fingerprinting the original files (SHA-256) ..."); src = {}
    for key, p in (("geojson", gj), ("csv", cv)): src[key] = {"name": p.name, "bytes": p.stat().st_size, "sha256": sha256_file(p), "mtime_ns": p.stat().st_mtime_ns}
    stamp = time.strftime("%Y%m%d_%H%M%S"); stage = out / f"_staging_{stamp}"; stage.mkdir()
    S = {}
    for s in specs:
        d = stage / s["id"]; d.mkdir()
        fh = open(d / "buildings.geojson", "w", encoding="utf-8", newline="")
        S[s["id"]] = dict(dir=d, fh=fh, first=True, ids=set(), digest={}, inside=0)

    # ---- pass 1: GeoJSON (single streaming pass) -------------------------------------------------------------
    log("pass 1: streaming the GeoJSON and assigning buildings to areas ...")
    st = GeoJSONStream(gj); prog = Progress("GeoJSON", st.size); all_ids, dup_geo, n = set(), 0, 0
    header_written = False; crs_obj = None
    for rawtext, obj in st.features():
        if not header_written:
            crs_obj = (st.header or {}).get("crs")
            if "2326" not in json.dumps(crs_obj or {}): raise PrepError("source GeoJSON does not declare EPSG:2326; refusing to guess")
            for aid, z in S.items():
                z["fh"].write('{"type":"FeatureCollection","name":' + json.dumps(f"{st.header.get('name', 'buildings')}__{aid}", ensure_ascii=False)
                              + ',"crs":' + json.dumps(crs_obj) + ',"features":[\n')
            header_written = True
        n += 1; ring = feature_checks(obj, n)
        bid = str(obj["properties"].get(ID_FIELD, ""))
        if not bid: raise PrepError(f"source feature #{n} has no {ID_FIELD}")
        if bid in all_ids: dup_geo += 1
        all_ids.add(bid)
        cx, cy = centroid(ring)
        for aid, ar in areas.items():
            if ar.contains(cx, cy):
                z = S[aid]
                z["fh"].write(("" if z["first"] else ",\n") + rawtext); z["first"] = False
                z["ids"].add(bid); z["digest"][bid] = hashlib.sha1(rawtext.encode("utf-8")).hexdigest(); z["inside"] += 1
        if n % 5000 == 0: prog.tick(st.bytes_read)
    prog.tick(st.size)
    for z in S.values(): z["fh"].write("\n]}\n"); z["fh"].close()
    log(f"   {n:,} features scanned; duplicates of Building_ID in GeoJSON: {dup_geo}")
    for aid, z in S.items(): log(f"   {aid}: {z['inside']:,} buildings")

    # ---- pass 2: CSV ------------------------------------------------------------------------------------------
    log("pass 2: reading the CSV and collecting the matching rows ...")
    wanted = {}
    for aid, z in S.items():
        for i in z["ids"]: wanted.setdefault(i, []).append(aid)
    csv_ids, csv_rows, counts = set(), 0, {}
    with open(cv, encoding="utf-8-sig", newline="") as fh:
        rd = csv.reader(fh); header = next(rd); ix = header.index(ID_FIELD)
        writers = {}
        for aid, z in S.items():
            f = open(z["dir"] / "buildings.csv", "w", encoding="utf-8", newline=""); z["csvfh"] = f
            w = csv.writer(f, lineterminator="\r\n"); w.writerow(header); writers[aid] = w
        prog = Progress("CSV", os.path.getsize(cv))
        for row in rd:
            csv_rows += 1; bid = row[ix]; csv_ids.add(bid)
            if bid in wanted:
                counts[bid] = counts.get(bid, 0) + 1
                for aid in wanted[bid]: writers[aid].writerow(row)
            if csv_rows % 20000 == 0: prog.tick(int(prog.size * min(1, csv_rows / max(n, 1))))
        for z in S.values(): z["csvfh"].close()
    log(f"   {csv_rows:,} CSV rows")
    source_checks = [
        ("source: GeoJSON feature count equals CSV row count", n == csv_rows, f"geojson={n:,} csv={csv_rows:,}"),
        ("source: Building_ID unique in GeoJSON", dup_geo == 0, f"{dup_geo} duplicates"),
        ("source: Building_ID sets identical in both files", all_ids == csv_ids, f"only-GeoJSON={len(all_ids - csv_ids):,} only-CSV={len(csv_ids - all_ids):,}"),
        ("source: CSV row count equals unique CSV ids", csv_rows == len(csv_ids), f"rows={csv_rows:,} unique={len(csv_ids):,}")]

    # ---- validation: re-read what was written (independent of the extraction loop) ---------------------------------
    log("validating the written packages ...")
    results = {}
    for s in specs:
        aid, z = s["id"], S[s["id"]]; chk = []
        def add(name, ok, detail=""): chk.append({"check": name, "passed": bool(ok), "detail": str(detail)})
        gids, bad_digest, bad_geom, outside, mism, extent = [], 0, 0, 0, {}, [math.inf, math.inf, -math.inf, -math.inf]
        props_by_id, mix_counts, area_sum = {}, {}, 0.0
        sg = GeoJSONStream(z["dir"] / "buildings.geojson")
        for rt, ob in sg.features():
            ring = feature_checks(ob, sg.n); bid = str(ob["properties"][ID_FIELD]); gids.append(bid); props_by_id[bid] = ob["properties"]
            if hashlib.sha1(rt.encode("utf-8")).hexdigest() != z["digest"].get(bid): bad_digest += 1
            if ring[0] != ring[-1] or len(ring) < 4 or any(not all(math.isfinite(c) for c in p[:2]) for p in ring): bad_geom += 1
            cx, cy = centroid(ring)
            if not areas[aid].contains(cx, cy): outside += 1
            for p in ring: extent = [min(extent[0], p[0]), min(extent[1], p[1]), max(extent[2], p[0]), max(extent[3], p[1])]
        add("every GeoJSON feature is byte-identical to its source text", bad_digest == 0 and len(gids) == z["inside"], f"{len(gids):,} features, {bad_digest} differ")
        add("GeoJSON Building_IDs unique", len(set(gids)) == len(gids), f"{len(gids) - len(set(gids))} duplicates")
        add("rings closed, finite, at least 4 points", bad_geom == 0, f"{bad_geom} bad")
        add("every centroid is inside the area polygon (re-tested from the written file)", outside == 0, f"{outside} outside")
        with open(z["dir"] / "buildings.csv", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        rid = [r[ID_FIELD] for r in rows]
        add("CSV has the same columns, in the same order, as the original", list(rows[0].keys() if rows else header) == header, f"{len(header)} columns")
        add("CSV rows = GeoJSON features, same Building_ID set, no duplicates", set(rid) == set(gids) and len(rid) == len(set(rid)), f"csv={len(rid):,} geojson={len(gids):,}")
        add("every source CSV row for these ids was captured exactly once", all(counts.get(i, 0) == 1 for i in gids), f"{sum(1 for i in gids if counts.get(i, 0) != 1)} ids with 0 or >1 rows")
        for r in rows:
            p = props_by_id.get(r[ID_FIELD], {})
            for k in header:
                if not same(r[k], p.get(k)): mism[k] = mism.get(k, 0) + 1
        keys_ok = all(set(p) == set(header) for p in props_by_id.values())
        add("all attributes agree between CSV and GeoJSON for every building (same field names, equal values)", not mism and keys_ok,
            "no differences" if not mism and keys_ok else (mism or "field names differ"))
        for r in rows: mix_counts[r["UBEM_Main_Class_主类别"]] = mix_counts.get(r["UBEM_Main_Class_主类别"], 0) + 1
        z.update(chk=chk, rows=rows, extent=extent, main_class=mix_counts)

    log("re-fingerprinting the original files (must be unchanged) ...")
    for key, p in (("geojson", gj), ("csv", cv)):
        now = sha256_file(p)
        ok = now == src[key]["sha256"] and p.stat().st_size == src[key]["bytes"] and p.stat().st_mtime_ns == src[key]["mtime_ns"]
        source_checks.append((f"ORIGINAL {p.name} UNCHANGED (SHA-256, size, mtime before = after)", ok, "")); 
    for k in src: src[k].pop("mtime_ns")

    # ---- manifests, reports, finalise ------------------------------------------------------------------------------
    failed = 0; (out / "_archive").mkdir(exist_ok=True)
    for s in specs:
        aid, z = s["id"], S[s["id"]]; rows = z["rows"]
        chk = z["chk"] + [{"check": c, "passed": bool(o), "detail": d} for c, o, d in source_checks]
        passed = all(c["passed"] for c in chk)
        fl = [float(r["Floors_Count_地上层数"]) for r in rows if r["Floors_Count_地上层数"] != ""]
        summary = dict(buildings=len(rows), extent_hk80=[round(v, 2) for v in z["extent"]] if rows else None,
                       main_class=dict(sorted(z["main_class"].items(), key=lambda kv: -kv[1])),
                       registered_gfa_present=sum(1 for r in rows if r["LandsD_Registered_GFA_地政署注册面积"].strip() != ""),
                       floors_missing=len(rows) - len(fl), footprint_area_total_m2=round(sum(float(r["Footprint_Area_sqm_占地面积"] or 0) for r in rows), 1),
                       with_building_name=sum(1 for r in rows if r["LandsD_Building_Name_EN_地政署英文名"].strip() or r["LandsD_Building_Name_TC_地政署中文名"].strip()))
        polys = s["_info"].pop("polygons_hk80", [])
        (z["dir"] / "boundary.geojson").write_text(json.dumps({"type": "FeatureCollection", "crs": crs_obj, "features": [
            {"type": "Feature", "properties": {"id": aid, "name": s["name"], "status": s.get("status", "official")},
             "geometry": {"type": "MultiPolygon", "coordinates": polys}}]}, ensure_ascii=False), encoding="utf-8")
        files = {n: {"sha256": sha256_file(z["dir"] / n), "bytes": (z["dir"] / n).stat().st_size} for n in ("buildings.geojson", "buildings.csv", "boundary.geojson")}
        man = {"schema_version": 1,
               "district": {"id": aid, "name": s["name"], "kind": s.get("kind", "district"), "status": s.get("status", "official"),
                            "parent": cfg.get("parent", "Hong Kong"), "description": s.get("description", "")},
               "area_definition": {**{k: v for k, v in s["_info"].items()},
                                   "assignment_rule": "footprint area-centroid (EPSG:2326 metres) inside the area polygon; no names or workbooks used"},
               "crs": "EPSG:2326", "sources": {**src, "licence_note": LICENCE_NOTE, "features_total": n, "csv_rows_total": csv_rows},
               "counts": {"buildings": len(rows)}, "summary": summary, "files": files,
               "validation": {"passed": passed, "checks": chk},
               "generated": {"utc": utc_now(), "script": "tools/prepare_districts.py", "version": VERSION, "python": platform.python_version()}}
        (z["dir"] / "manifest.json").write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
        md = [f"# Validation report: {s['name']} ({aid})", f"Generated {man['generated']['utc']} by prepare_districts v{VERSION}.",
              f"Status: **{'PASSED' if passed else 'FAILED'}**; buildings: **{len(rows):,}**; CRS EPSG:2326; area status: {man['district']['status']}.", "",
              "| check | result | detail |", "|---|---|---|"] + [f"| {c['check']} | {'PASS' if c['passed'] else 'FAIL'} | {c['detail']} |" for c in chk]
        md += ["", "Assignment is by footprint centroid, so a building that straddles the boundary belongs to the area holding its centroid."]
        (z["dir"] / "validation_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        dest = out / aid
        if passed:
            if dest.exists(): shutil.move(str(dest), str(out / "_archive" / f"{aid}_{stamp}"))
            shutil.move(str(z["dir"]), str(dest)); log(f"   {aid}: PASSED -> {dest}")
        else:
            failed += 1; rej = out / "_rejected" / f"{aid}_{stamp}"; rej.parent.mkdir(exist_ok=True); shutil.move(str(z["dir"]), str(rej))
            log(f"   {aid}: FAILED validation -> {rej} (not published; see validation_report.md)")
    shutil.rmtree(stage, ignore_errors=True)
    if not any((out / "_archive").iterdir()): (out / "_archive").rmdir()
    rebuild_index(out); (out / "run_log.txt").write_text("\n".join(_LOG) + "\n", encoding="utf-8")
    if failed: raise PrepError(f"{failed} district(s) failed validation")
    log("DONE")


def rebuild_index(out):
    out = Path(out); entries = []
    for m in sorted(out.glob("*/manifest.json")):
        j = json.loads(m.read_text(encoding="utf-8"))
        if j["validation"]["passed"]:
            entries.append({"id": j["district"]["id"], "name": j["district"]["name"], "kind": j["district"]["kind"], "status": j["district"]["status"],
                            "parent": j["district"]["parent"], "buildings": j["counts"]["buildings"], "extent_hk80": j["summary"]["extent_hk80"],
                            "generated": j["generated"]["utc"]})
    (out / "index.json").write_text(json.dumps({"schema_version": 1, "districts": entries}, indent=1, ensure_ascii=False), encoding="utf-8")


def cmd_verify(a):
    from districts import verify_package
    out = Path(a.out); bad = 0
    for m in sorted(out.glob("*/manifest.json")):
        ok, probs = verify_package(m.parent); bad += (not ok)
        log(f"{m.parent.name}: {'OK' if ok else 'PROBLEMS ' + '; '.join(probs)}")
    if bad: raise PrepError(f"{bad} package(s) do not match their manifests")


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    def common(p):
        p.add_argument("--raw", default=str(ROOT / "raw"), help="folder holding the two original files")
        p.add_argument("--geojson"); p.add_argument("--csv")
    c = sub.add_parser("check"); common(c)
    b = sub.add_parser("boundaries"); b.add_argument("file")
    r = sub.add_parser("run"); common(r)
    r.add_argument("--config", default=str(ROOT / "config" / "districts.json")); r.add_argument("--out", default=str(ROOT / "data" / "districts"))
    r.add_argument("--only", help="comma-separated district ids"); r.add_argument("--overwrite", action="store_true")
    v = sub.add_parser("verify"); v.add_argument("--out", default=str(ROOT / "data" / "districts"))
    a = ap.parse_args(argv)
    try: {"check": cmd_check, "boundaries": cmd_boundaries, "run": cmd_run, "verify": cmd_verify}[a.cmd](a)
    except PrepError as e:
        log(f"STOPPED: {e}"); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
