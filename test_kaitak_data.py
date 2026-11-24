import json, unittest
from pathlib import Path
from dataclasses import replace
from buildings import effective, to_model_buildings, resolve
from geometry import ring_distance, ring_area, check_cluster
from kaitak_data import load_kaitak, DATA, sha256
from model import Assumptions, run

def sq(x, y, s=10): return [(x, y), (x + s, y), (x + s, y + s), (x, y + s), (x, y)]

class Geo(unittest.TestCase):
    def test_distances(self):
        self.assertAlmostEqual(ring_distance(sq(0, 0), sq(30, 0)), 20)          # side by side
        self.assertAlmostEqual(ring_distance(sq(0, 0), sq(13, 14)), 5)          # corner to corner (3,4,5)
        self.assertEqual(ring_distance(sq(0, 0), sq(10, 0)), 0)                 # touching
        self.assertEqual(ring_distance(sq(0, 0), sq(5, 5)), 0)                  # overlapping
        self.assertEqual(ring_distance(sq(0, 0, 100), sq(40, 40, 5)), 0)        # contained
    def test_cluster_warning_not_block(self):
        c = check_cluster({"a": sq(0, 0), "b": sq(100, 0), "c": sq(500, 0)}, 300)
        self.assertFalse(c["within_limit"]); self.assertEqual(c["pairs_over_limit"][0][:2], ("a", "c")); self.assertAlmostEqual(c["max_distance_m"], 490)
        self.assertTrue(check_cluster({"a": sq(0, 0), "b": sq(100, 0)}, 300)["within_limit"])

class Real(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.recs, cls.rep = load_kaitak()
    def test_extracts_unchanged(self):
        m = json.loads((DATA / "manifest.json").read_text())["files"]
        for n, h in m.items(): self.assertEqual(sha256(DATA / n), h)
    def test_all_176_joined_exactly(self):
        self.assertEqual(self.rep["n"], 176); self.assertEqual(self.rep["tiers"], {"exact_id": 176}); self.assertEqual(self.rep["issues"], [])
        self.assertEqual(len({r.building_id for r in self.recs}), 176); self.assertTrue(all(r.selectable for r in self.recs))
    def test_source_vs_derived_and_no_fabrication(self):
        r = self.recs[0]
        self.assertEqual(r.gfa_m2.status, "missing")                           # registered GFA absent for all 176
        g = resolve(r, "gfa_m2"); self.assertEqual(g.status, "derived")
        self.assertAlmostEqual(g.value, r.footprint_area_m2.value * r.storeys.value)
        f = effective(r); self.assertEqual(f["load_w_m2"].status, "assumption")  # cooling load is never sourced
        ov = {r.building_id: {"load_w_m2": 150}}; self.assertEqual(resolve(r, "load_w_m2", ov).status, "override"); self.assertEqual(r.load_w_m2.status, "missing")
    def test_feeds_financial_model(self):
        tup, excl = to_model_buildings(self.recs[:5]); self.assertEqual((len(tup), excl), (5, []))
        res = run(Assumptions(buildings=tup)); self.assertGreater(res["scenarios"][0]["demand"], 0)
    def test_far_flag_and_real_distances(self):
        far = [r for r in self.recs if dict(r.attrs)["far_from_cluster"]]; self.assertTrue(0 < len(far) < 40)
        core = [r for r in self.recs if not dict(r.attrs)["far_from_cluster"]]
        c = check_cluster({r.building_id: r.footprint_hk80 for r in core[:6]}, 300); self.assertEqual(c["n"], 6)
        c2 = check_cluster({r.building_id: r.footprint_hk80 for r in (core[0], far[0])}, 300); self.assertFalse(c2["within_limit"])
if __name__ == "__main__": unittest.main()
