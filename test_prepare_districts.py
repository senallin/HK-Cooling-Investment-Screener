"""Tests for tools/prepare_districts.py and districts.py using small synthetic source files in the real schema."""
import csv, hashlib, io, json, os, random, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import prepare_districts as P
import districts as D
from geometry import inside

COLS = ['Building_ID_建筑ID', 'Footprint_Area_sqm_占地面积', 'Floors_Count_地上层数', 'Height_m_建筑高度', 'UBEM_Main_Class_主类别', 'UBEM_Sub_Class_子类别', 'UBEM_Mixed_Proportions_混合比例', 'Classification_Source_分类来源', 'Classification_Notes_分类备注', 'ML_Prediction_Confidence_机器学习置信度', 'ML_Prob_Residential_住宅概率', 'ML_Prob_Commercial_商业概率', 'ML_Prob_Industrial_工业概率', 'LandsD_Structure_Type_地政署建筑类型', 'LandsD_Category_地政署分类', 'LandsD_Status_地政署状态', 'LandsD_Registered_GFA_地政署注册面积', 'LandsD_Building_Name_EN_地政署英文名', 'LandsD_Building_Name_TC_地政署中文名', 'BDBIAR_Record_ID_屋宇署记录ID', 'BDBIAR_Classification_屋宇署分类', 'BDBIAR_Building_Age_Year_屋宇署楼龄年份', 'Dist_to_BDBIAR_m_距屋宇署点位距离', 'Crowdsourced_POIs_Matched_众包POI匹配详情', 'OSM_Record_ID_OSM记录ID', 'OSM_Building_Tag_OSM建筑标签', 'OSM_Amenity_Tag_OSM设施标签', 'OSM_Shop_Tag_OSM商铺标签', 'OZP_Zone_Code_法定图则代码', 'OZP_Zone_Desc_EN_法定图则英文描述']
CRS = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::2326"}}

def sq(x, y, s=20): return [[x, y], [x + s, y], [x + s, y + s], [x, y + s], [x, y]]

def props(i, x, y):
    cls = ["Residential_住宅类别", "Commercial_商业类别", "Mixed-use_混合用途"][i % 3]
    mix = {0: "Private Housing_私人房屋:1.00", 1: "Office_办公室:1.00", 2: "Private Housing_私人房屋:0.60-Retail_零售:0.40"}[i % 3]
    p = {c: None for c in COLS}
    p.update({ID: str(i), "Footprint_Area_sqm_占地面积": 400.0, "Floors_Count_地上层数": float(5 + i % 9), "Height_m_建筑高度": 3.3 * (5 + i % 9),
              "UBEM_Main_Class_主类别": cls, "UBEM_Sub_Class_子类别": mix.split(":")[0], "UBEM_Mixed_Proportions_混合比例": mix,
              "Classification_Source_分类来源": "Rule_Engine(OSM)", "ML_Prediction_Confidence_机器学习置信度": 0.7576391331388549,
              "LandsD_Building_Name_EN_地政署英文名": "TOWER %d" % i if i % 2 else "", "LandsD_Building_Name_TC_地政署中文名": "大廈%d" % i,
              "OZP_Zone_Code_法定图则代码": "OU", "LandsD_Category_地政署分类": 1})
    return {k: ("" if v is None and k != "LandsD_Registered_GFA_地政署注册面积" else v) for k, v in p.items()} | {"LandsD_Registered_GFA_地政署注册面积": None}

ID = "Building_ID_建筑ID"

def build_source(tmp, layout="gdal", n=10, bad=None):
    """n x n grid of 20 m squares on a 50 m pitch from (800000, 800000). Returns feature text list."""
    feats, rows = [], []
    for i in range(n * n):
        x, y = 800000 + (i % n) * 50, 800000 + (i // n) * 50
        p = props(i, x, y); g = {"type": "Polygon", "coordinates": [sq(x, y)]}
        if bad == "multipolygon" and i == 5: g = {"type": "MultiPolygon", "coordinates": [[sq(x, y)]]}
        feats.append(json.dumps({"type": "Feature", "properties": p, "geometry": g}, ensure_ascii=False, separators=(", ", ": ")))
        rows.append(p)
    if bad == "dup": feats.append(feats[3]); rows.append(rows[3])
    head = '{\n"type": "FeatureCollection",\n"name": "TestSource",\n"crs": %s,\n"features": [\n' % json.dumps(CRS)
    if layout == "gdal": text = head + ",\n".join(feats) + "\n]\n}\n"
    else: text = '{"type":"FeatureCollection","name":"TestSource","crs":%s,"features":[%s]}' % (json.dumps(CRS), ",".join(feats))
    gj = Path(tmp) / "raw" / P.GEOJSON_NAME; gj.parent.mkdir(parents=True, exist_ok=True); gj.write_text(text, encoding="utf-8", newline="")
    cv = Path(tmp) / "raw" / P.CSV_NAME
    with open(cv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh); w.writerow(COLS)
        for r in rows[: (len(rows) - 2 if bad == "csv_missing" else len(rows))]:
            w.writerow(["" if r[c] is None else r[c] for c in COLS])
    return feats

def write_cfg(tmp, districts):
    p = Path(tmp) / "districts.json"; p.write_text(json.dumps({"schema_version": 1, "parent": "Hong Kong", "districts": districts}), encoding="utf-8"); return p

def poly_file(tmp, name, coords, holes=()):
    p = Path(tmp) / name
    p.write_text(json.dumps({"type": "FeatureCollection", "crs": CRS, "features": [{"type": "Feature", "properties": {"ENAME": "Zone A", "CNAME": "甲區"},
        "geometry": {"type": "Polygon", "coordinates": [coords, *holes]}}]}), encoding="utf-8"); return p

def run(tmp, cfg, *extra):
    return P.main(["run", "--raw", str(Path(tmp) / "raw"), "--out", str(Path(tmp) / "out"), "--config", str(cfg), *extra])

class Index(unittest.TestCase):
    def test_band_index_equals_reference_point_in_polygon(self):
        rnd = random.Random(1); ring = [(0, 0)]
        for k in range(1, 60): a = k * 0.2; r = 50 + 30 * rnd.random(); ring.append((r * __import__("math").cos(a), r * __import__("math").sin(a)))
        ring.append(ring[0]); ix = P.RingIndex(ring)
        for _ in range(3000):
            x, y = rnd.uniform(-90, 90), rnd.uniform(-90, 90)
            self.assertEqual(ix.contains(x, y), inside((x, y), ring))
    def test_hole_and_multipolygon(self):
        a = P.Area([([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)], [[(40, 40), (60, 40), (60, 60), (40, 60), (40, 40)]]),
                    ([(200, 0), (300, 0), (300, 100), (200, 100), (200, 0)], [])])
        self.assertTrue(a.contains(10, 10)); self.assertFalse(a.contains(50, 50)); self.assertTrue(a.contains(250, 50)); self.assertFalse(a.contains(150, 50))

class Stream(unittest.TestCase):
    def test_both_layouts_and_tiny_chunks_with_multibyte_text(self):
        with tempfile.TemporaryDirectory() as t:
            ref = None
            for layout in ("gdal", "compact"):
                feats = build_source(t, layout, n=6)
                for chunk in (7, 64, 1 << 22):
                    s = P.GeoJSONStream(Path(t) / "raw" / P.GEOJSON_NAME, chunk=chunk)
                    got = [rt for rt, _ in s.features()]
                    self.assertEqual(got, feats); self.assertEqual(s.n, 36); self.assertEqual(s.header["crs"], CRS)

class Pipeline(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.tmp = self.t.name
    def tearDown(self): self.t.cleanup()
    def cfg(self):
        # Zone A = squares with centroid in x 800000-800230, y 800000-800130, minus a hole around building (2,1)
        zone = poly_file(self.tmp, "a.geojson", [[799990, 799990], [800230, 799990], [800230, 800130], [799990, 800130], [799990, 799990]],
                         holes=[[[800090, 800040], [800130, 800040], [800130, 800080], [800090, 800080], [800090, 800040]]])
        bx = {"type": "bbox", "bbox": [800400, 800400, 800500, 800500], "crs": "EPSG:2326"}
        return write_cfg(self.tmp, [{"id": "zone_a", "name": "Zone A", "definition": {"type": "polygon_file", "file": str(zone)}},
                                    {"id": "box_b", "name": "Box B", "kind": "study_area", "status": "provisional", "definition": bx}])
    def test_end_to_end_lossless_and_validated(self):
        feats = build_source(self.tmp, "gdal", n=10); cfg = self.cfg(); raw = Path(self.tmp) / "raw"
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.iterdir()}
        self.assertEqual(run(self.tmp, cfg), 0)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.iterdir()})   # originals untouched
        out = Path(self.tmp) / "out"
        man = json.loads((out / "zone_a" / "manifest.json").read_text(encoding="utf-8"))
        # centroids (x+10, y+10): columns 0..4 (800010..800210), rows 0..2, minus hole covering centroid (800110,800060) = column 2,row 1 -> id 12
        expect = {str(r * 10 + c) for r in range(3) for c in range(5)} - {"12"}
        got = {str(f["properties"][ID]) for f in json.loads((out / "zone_a" / "buildings.geojson").read_text(encoding="utf-8"))["features"]}
        self.assertEqual(got, expect); self.assertEqual(man["counts"]["buildings"], 14)
        self.assertTrue(man["validation"]["passed"]); self.assertEqual(man["crs"], "EPSG:2326")
        text = (out / "zone_a" / "buildings.geojson").read_text(encoding="utf-8")
        for f in feats:                                                             # byte-identical feature text
            if json.loads(f)["properties"][ID] in expect: self.assertIn(f, text)
        with open(out / "zone_a" / "buildings.csv", encoding="utf-8", newline="") as fh: rows = list(csv.DictReader(fh))
        self.assertEqual(list(rows[0].keys()), COLS); self.assertEqual(len(rows), 14)
        self.assertEqual(json.loads((out / "box_b" / "manifest.json").read_text(encoding="utf-8"))["district"]["status"], "provisional")
        idx = json.loads((out / "index.json").read_text(encoding="utf-8"))["districts"]
        self.assertEqual({d["id"] for d in idx}, {"zone_a", "box_b"}); self.assertEqual(D.list_districts(out)[0]["parent"], "Hong Kong")
        self.assertTrue(D.verify_package(out / "zone_a")[0])
        self.assertEqual(P.main(["verify", "--out", str(out)]), 0)
    def test_never_overwrites_without_flag_and_archives_with_it(self):
        build_source(self.tmp); cfg = self.cfg(); self.assertEqual(run(self.tmp, cfg), 0)
        self.assertEqual(run(self.tmp, cfg), 2)
        self.assertEqual(run(self.tmp, cfg, "--overwrite"), 0)
        self.assertEqual(len(list((Path(self.tmp) / "out" / "_archive").iterdir())), 2)
    def test_adding_a_district_is_config_only(self):
        build_source(self.tmp); cfg = self.cfg(); self.assertEqual(run(self.tmp, cfg), 0)
        c = json.loads(cfg.read_text()); c["districts"].append({"id": "box_c", "name": "Box C", "definition": {"type": "bbox", "bbox": [800250, 800250, 800350, 800350]}})
        cfg.write_text(json.dumps(c)); self.assertEqual(run(self.tmp, cfg, "--only", "box_c"), 0)
        recs, rep = D.load_district("box_c", Path(self.tmp) / "out"); self.assertEqual(rep["tiers"], {"exact_id": len(recs)}); self.assertTrue(recs)
    def test_stops_on_unsupported_geometry_duplicate_ids_and_missing_csv_rows(self):
        for bad, code in (("multipolygon", 2), ("dup", 2), ("csv_missing", 2)):
            with self.subTest(bad):
                build_source(self.tmp, bad=bad, n=10); cfg = self.cfg(); shutil = __import__("shutil"); shutil.rmtree(Path(self.tmp) / "out", ignore_errors=True)
                self.assertEqual(run(self.tmp, cfg), code)
                self.assertFalse((Path(self.tmp) / "out" / "zone_a").exists())          # nothing published
    def test_loader_keeps_source_status_and_parses_mix(self):
        build_source(self.tmp); self.assertEqual(run(self.tmp, self.cfg()), 0)
        recs, rep = D.load_district("zone_a", Path(self.tmp) / "out")
        self.assertEqual(len(recs), 14); self.assertEqual(rep["unparsed_mix"], 0); self.assertTrue(all(r.district == "zone_a" for r in recs))
        r = next(r for r in recs if r.building_id == "HKBFETD-2"); self.assertEqual((r.primary_use, r.secondary_use), ("Private Housing", "Retail"))
        self.assertEqual(r.gfa_m2.status, "missing")
        self.assertEqual(r.storeys.status, "source")
        from buildings import resolve; self.assertEqual(resolve(r, "gfa_m2").status, "derived")
    def test_tampered_package_is_refused(self):
        build_source(self.tmp); self.assertEqual(run(self.tmp, self.cfg()), 0)
        p = Path(self.tmp) / "out" / "zone_a" / "buildings.csv"; p.write_bytes(p.read_bytes() + b"x")
        with self.assertRaises(D.DataIntegrityError): D.load_district("zone_a", Path(self.tmp) / "out")

class Boundaries(unittest.TestCase):
    def test_name_match_autodetects_field_and_normalises(self):
        with tempfile.TemporaryDirectory() as t:
            feats = [{"type": "Feature", "properties": {"ENAME": n, "CNAME": c}, "geometry": {"type": "Polygon", "coordinates": [sq(800000 + i * 100, 800000, 50)]}}
                     for i, (n, c) in enumerate([("Central & Western", "中西區"), ("Kwun Tong", "觀塘")])]
            p = Path(t) / "b.json"; p.write_text(json.dumps({"type": "FeatureCollection", "crs": CRS, "features": feats}), encoding="utf-8")
            a, info = P.resolve_area({"id": "x", "definition": {"type": "boundary", "file": str(p), "match": {"values": ["Central and Western"]}}})
            self.assertEqual(info["match_field"], "ENAME"); self.assertTrue(a.contains(800025, 800025)); self.assertFalse(a.contains(800125, 800025))
            with self.assertRaises(P.PrepError): P.resolve_area({"id": "x", "definition": {"type": "boundary", "file": str(p), "match": {"values": ["Atlantis"]}}})
    def test_crs_mismatch_is_an_error_not_a_guess(self):
        polys = [([(114.1, 22.3), (114.2, 22.3), (114.2, 22.4), (114.1, 22.3)], [])]
        self.assertEqual(P.detect_crs({}, polys), 4326)
        with self.assertRaises(P.PrepError): P.detect_crs({}, polys, declared="EPSG:2326")
        self.assertEqual(P.detect_crs({}, [([(830000, 820000), (831000, 820000), (831000, 821000), (830000, 820000)], [])]), 2326)
    def test_wgs84_boundary_converts_to_hk80_landmark(self):
        try: import pyproj  # noqa
        except ImportError: self.skipTest("pyproj not installed here; run this test locally")
        a = P.to_hk80([([(114.2145, 22.3057), (114.22, 22.3057), (114.22, 22.31), (114.2145, 22.3057)], [])], 4326)
        x, y = a[0][0][0]; self.assertTrue(839000 < x < 842000 and 817500 < y < 820500, (x, y))

if __name__ == "__main__": unittest.main()
