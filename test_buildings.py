import unittest
from dataclasses import replace
from buildings import BuildingRecord, Val, src, resolve, effective, to_model_buildings
from model import Assumptions, run

def rec(**k):
    base = dict(building_id="SYN-1", name="Synthetic A", lon=114.2, lat=22.3, match_tier="synthetic", synthetic=True,
                gfa_m2=src(10000, "test"), storeys=src(10, "test"), footprint_area_m2=src(1000, "test"))
    return BuildingRecord(**{**base, **k})

class T(unittest.TestCase):
    def test_override_does_not_touch_source(self):
        r = rec(); before = r
        v = resolve(r, "gfa_m2", {"SYN-1": {"gfa_m2": 5000}})
        self.assertEqual((v.value, v.status), (5000, "override"))
        self.assertEqual(r, before); self.assertEqual(r.gfa_m2.value, 10000)
        self.assertEqual(resolve(r, "gfa_m2").status, "source")
    def test_derived_gfa_labelled_and_missing_stays_missing(self):
        v = resolve(rec(gfa_m2=Val()), "gfa_m2"); self.assertEqual((v.value, v.status), (10000, "derived"))
        v = resolve(rec(gfa_m2=Val(), storeys=Val()), "gfa_m2"); self.assertIsNone(v.value); self.assertEqual(v.status, "missing")
    def test_defaults_are_flagged_assumptions(self):
        self.assertEqual(resolve(rec(), "load_w_m2").status, "assumption")
    def test_cooled_area(self):
        f = effective(rec(cooled_fraction=src(0.8, "test"))); self.assertAlmostEqual(f["cooled_area_m2"].value, 8000)
    def test_adapter_excludes_incomplete_and_feeds_model(self):
        bad = rec(building_id="SYN-2", gfa_m2=Val(), storeys=Val())
        tup, excl = to_model_buildings([rec(), bad])
        self.assertEqual(len(tup), 1); self.assertEqual(excl[0][0], "SYN-2")
        r = run(Assumptions(buildings=tup)); self.assertGreater(r["scenarios"][0]["demand"], 0)
    def test_clearing_override_restores_source(self):
        self.assertEqual(resolve(rec(), "gfa_m2", {"SYN-1": {"gfa_m2": float("nan")}}).status, "source")
if __name__ == "__main__": unittest.main()
