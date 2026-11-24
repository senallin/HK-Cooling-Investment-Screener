"""Cluster selection, geometry speed-ups, Esri JSON boundaries and the real prepared packages."""
import json, math, random, unittest
from pathlib import Path
import clusters as C
import geometry as G
from buildings import BuildingRecord, Val
import tools.prepare_districts as P

ROOT = Path(__file__).resolve().parent


def sq(x, y, s=20): return ((x, y), (x + s, y), (x + s, y + s), (x, y + s), (x, y))


def rec(i, x, y, cls="Commercial_商业类别", mix=(("Office_办公室", 1.0),), tier="exact_id"):
    ring = sq(x, y)
    return BuildingRecord(building_id=f"B{i}", name=f"B{i}", footprint_hk80=ring, centroid_hk80=G.ring_centroid(list(ring)),
                          building_type=cls, use_mix=mix, match_tier=tier, footprint_area_m2=Val(400.0, "source", "t"),
                          storeys=Val(10.0, "source", "t"))


class Geometry(unittest.TestCase):
    def test_fast_check_equals_exact(self):
        rnd = random.Random(7)
        for trial in range(5):
            rings = {}
            for i in range(40):
                x, y, s = rnd.uniform(0, 900), rnd.uniform(0, 900), rnd.uniform(5, 60)
                rings[i] = sq(x, y, s)
            a, b = G.check_cluster(rings, 300), G.check_cluster_fast(rings, 300)
            self.assertAlmostEqual(a["max_distance_m"], b["max_distance_m"], places=6)
            self.assertEqual(len(a["pairs_over_limit"]), b["n_pairs_over_limit"])          # exact count
            exact = {(p, q): d for p, q, d in a["pairs_over_limit"]}
            for p, q, d in b["pairs_over_limit"]: self.assertAlmostEqual(exact[(p, q)], d, places=6)  # reported pairs exact
            self.assertAlmostEqual(max(exact.values()), b["pairs_over_limit"][0][2], places=6)  # the widest pair is always listed first
            self.assertEqual(a["within_limit"], b["within_limit"])

    def test_mst_and_hull(self):
        self.assertAlmostEqual(G.mst_length([(0, 0), (100, 0), (100, 50)]), 150)
        h = G.convex_hull([(0, 0), (10, 0), (10, 10), (0, 10), (5, 5)])
        self.assertEqual(len(h), 5); self.assertAlmostEqual(G.ring_area(h), 100)

    def test_nearest_gap(self):
        g = G.nearest_neighbour_gaps({"a": sq(0, 0), "b": sq(50, 0), "c": sq(1000, 0)})
        self.assertAlmostEqual(g["a"], 30); self.assertAlmostEqual(g["c"], 930)


class Selection(unittest.TestCase):
    def setUp(self):
        self.recs = [rec(i, (i % 10) * 50, (i // 10) * 50) for i in range(100)]
        self.recs[5] = rec(5, 250, 0, tier="ambiguous")
        self.ix = C.SpatialIndex(self.recs)

    def test_click_hits_footprint(self):
        self.assertEqual(self.ix.at(110, 60), "B12")
        self.assertIsNone(self.ix.at(135, 60))                     # gap between buildings (>5 m from any footprint)

    def test_polygon_selection_with_hole(self):
        outer = [(0, 0), (200, 0), (200, 120), (0, 120), (0, 0)]
        hole = [(90, 40), (130, 40), (130, 80), (90, 80), (90, 40)]
        got = self.ix.in_polygons([(outer, [hole])])
        self.assertEqual(got, {f"B{r * 10 + c}" for r in range(3) for c in range(4)} - {"B12"})

    def test_starter_cluster_is_deterministic_and_selectable(self):
        a = C.starter_cluster(self.recs, max_m=120); b = C.starter_cluster(self.recs, max_m=120)
        self.assertEqual(a, b); self.assertNotIn("B5", a); self.assertTrue(a)

    def test_use_defaults_weighted(self):
        r = rec(1, 0, 0, mix=(("Office_办公室", 0.5), ("Private Housing_私人房屋", 0.5)))
        d = C.use_defaults(r); self.assertAlmostEqual(d["load_w_m2"], 85); self.assertAlmostEqual(d["hours"], 2150)
        f, pk, q = C.building_inputs(r)
        self.assertEqual(f["gfa_m2"].status, "derived"); self.assertEqual(f["load_w_m2"].status, "assumption")
        self.assertAlmostEqual(pk, 4000 * 0.775 * 85 / 1000)

    def test_override_wins_and_never_mutates(self):
        r = self.recs[1]; ov = {r.building_id: {"load_w_m2": 200.0}}
        f, _, _ = C.building_inputs(r, ov); self.assertEqual((f["load_w_m2"].value, f["load_w_m2"].status), (200.0, "override"))
        self.assertEqual(r.load_w_m2.status, "missing")

    def test_geometry_summary_network(self):
        g = C.geometry_summary(self.recs[:3], 300, 1.3)
        self.assertAlmostEqual(g["mst_m"], 100); self.assertAlmostEqual(g["network_m"], 130)


class Esri(unittest.TestCase):
    def test_orientation_rule_and_real_kai_tak_area(self):
        cw = [[0, 0], [0, 100], [100, 100], [100, 0], [0, 0]]                 # clockwise = outer
        ccw = [[40, 40], [60, 40], [60, 60], [40, 60], [40, 40]]              # anticlockwise = hole
        polys = P.esri_polygons([cw, ccw])
        self.assertEqual(len(polys), 1); self.assertEqual(len(polys[0][1]), 1)
        with self.assertRaises(P.PrepError): P.esri_polygons([ccw])
        p = ROOT / "config" / "areas" / "kai_tak_ozp_S_K22_9_plan_scheme_area.json"
        obj = json.loads(p.read_text(encoding="utf-8"))
        a, info = P.resolve_area({"id": "kt", "definition": {"type": "polygon_file", "file": str(p)}})
        self.assertAlmostEqual(info["area_m2"], obj["features"][0]["attributes"]["Shape_Area"], delta=1)
        self.assertEqual(info["crs_in"], "EPSG:2326")


@unittest.skipUnless((ROOT / "data" / "districts" / "kai_tak" / "manifest.json").exists(), "real packages not built")
class RealPackages(unittest.TestCase):
    def test_packages_verify_and_kai_tak_uses_official_boundary(self):
        import districts as D
        for d in D.list_districts():
            self.assertTrue(D.verify_package(D.ROOT_DIR / d["id"])[0], d["id"])
        m = D.load_manifest("kai_tak")
        self.assertEqual(m["counts"]["buildings"], 899); self.assertEqual(m["district"]["status"], "official")
        self.assertIn("Esri", m["area_definition"]["format"])

    def test_dcs_registry_values(self):
        reg = C.load_dcs(); kt = next(s for s in reg["systems"] if s["id"] == "kai_tak")
        self.assertEqual(kt["rates"]["2026/27"], {"capacity_hkd_per_kwr_month": 140.88, "consumption_hkd_per_kwhr": 0.2387})
        from model import Assumptions
        self.assertEqual((Assumptions().dcs_capacity_rate, Assumptions().dcs_consumption_rate), (140.88, 0.2387))


if __name__ == "__main__": unittest.main()
