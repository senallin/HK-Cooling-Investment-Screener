"""Tests for compare.py on the real Kai Tak package (skipped if it is not prepared)."""
import math, unittest
from pathlib import Path
import clusters as C
import compare as K
import districts as D
from model import Assumptions

HAVE = (Path(__file__).resolve().parent / "data" / "districts" / "kai_tak" / "manifest.json").exists()


@unittest.skipUnless(HAVE, "needs data/districts/kai_tak")
class Compare(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recs, _ = D.load_district("kai_tak"); cls.by = {r.building_id: r for r in cls.recs}

    def test_clusters_match_the_rule(self):
        g = K.match_clusters(self.recs, n=5, max_d=300, floors=(3, 40), k=50)
        self.assertGreater(len(g), 0)
        seen = set()
        for grp in g:
            self.assertEqual(len(grp), 5)
            self.assertFalse(seen & set(grp)); seen |= set(grp)                       # no overlap
            rs = [self.by[i] for i in grp]
            self.assertTrue(all(r.selectable and 3 <= r.storeys.value <= 40 and C.main_class(r) in ("Commercial", "Mixed-use") for r in rs))
            for a in rs:                                                              # every pair within max_d, centre to centre
                for b in rs: self.assertLessEqual(math.dist(a.centroid_hk80, b.centroid_hk80), 300 + 1e-6)
            dem = {i: C.building_inputs(self.by[i])[2] or 0 for i in grp}
            self.assertLessEqual(C.dominant_share(grp, dem), 0.5 + 1e-9)

    def test_deterministic_and_capped(self):
        a = K.match_clusters(self.recs, n=4, max_d=250, k=3); b = K.match_clusters(self.recs, n=4, max_d=250, k=3)
        self.assertEqual(a, b); self.assertLessEqual(len(a), 3)

    def test_impossible_request_returns_nothing(self):
        self.assertEqual(K.match_clusters(self.recs, n=6, max_d=300, floors=(150, 200)), [])

    def test_run_summary_and_typical(self):
        out = K.run_district(self.recs, Assumptions(), n=5, max_d=300, k=20)
        r = out["results"]; self.assertTrue(r)
        s = K.summarise(r); self.assertEqual(s["n"], len(r)); self.assertLessEqual(s["q1"], s["median"]); self.assertLessEqual(s["median"], s["q3"])
        t = K.typical(r); vals = sorted(x["npv_cmcs_per_mw"] for x in r)
        self.assertIn(t, r); self.assertGreaterEqual(t["npv_cmcs_per_mw"], vals[0]); self.assertLessEqual(t["npv_cmcs_per_mw"], vals[-1])
        self.assertTrue(0 <= out["context"]["commercial_share"] <= 1)

    def test_suggestions_are_not_dominated_by_one_building(self):
        for it in C.suggest_clusters(self.recs, C.SpatialIndex(self.recs), 150, 6):
            dem = {i: C.building_inputs(self.by[i])[2] or 0 for i in it["ids"]}
            self.assertLessEqual(C.dominant_share(it["ids"], dem), 0.5 + 1e-9)


class Glossary(unittest.TestCase):
    def test_every_group_key_has_an_entry(self):
        import glossary as G
        for g, keys in G.GROUPS.items():
            for k in keys: self.assertIn(k, G.TERMS, (g, k))
        self.assertTrue(all(len(v) == 3 and all(v) for v in G.TERMS.values()))


class Packages(unittest.TestCase):
    def test_gzip_package_verifies_and_tampering_is_caught(self):
        import gzip, json, shutil, tempfile
        src = Path(__file__).resolve().parent / "data" / "districts" / "kai_tak"
        if not src.exists(): self.skipTest("needs kai_tak")
        with tempfile.TemporaryDirectory() as t:
            pkg = Path(t) / "kai_tak"; shutil.copytree(src, pkg)
            if (pkg / "buildings.geojson").exists():
                (pkg / "buildings.geojson.gz").write_bytes(gzip.compress((pkg / "buildings.geojson").read_bytes())); (pkg / "buildings.geojson").unlink()
            self.assertTrue(D.verify_package(pkg)[0])
            recs, _ = D.load_district("kai_tak", root=t); self.assertEqual(len(recs), 899)
            (pkg / "buildings.geojson.gz").write_bytes(gzip.compress(b'{"type":"FeatureCollection","features":[]}'))
            self.assertFalse(D.verify_package(pkg)[0])

    def test_district_power_company(self):
        import sources as S
        self.assertEqual(S.supplier_code("central_western"), "HKE"); self.assertEqual(S.supplier_code("kwun_tong"), "CLP")
        self.assertTrue(all(k in S.PUBLISHED or k in S.JUDGEMENT for k in ("tariff", "discount_rate", "cop_central")))


if __name__ == "__main__": unittest.main()
