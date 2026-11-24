"""New model vs the frozen v1 model (tests/legacy_model.py = git tag v1-baseline)."""
import unittest
from dataclasses import replace
from model import Assumptions, run
from tests import legacy_model as old

class T(unittest.TestCase):
    def setUp(self):
        self.o = old.run(old.Assumptions()); self.peak = 10020.0
    def test_same_cop_matches_v1_energy_capex_emissions(self):
        n = run(Assumptions())
        for so, sn in zip(self.o["scenarios"], n["scenarios"]):
            for k in ("demand", "elec", "energy_cost", "capex", "co2_t"): self.assertAlmostEqual(so[k], sn[k], places=6, msg=k)
    def test_explicit_per_building_cop_equal_to_global_is_identical(self):
        b = tuple((x[0], x[1], x[2], x[3], 3.2) for x in Assumptions().buildings)
        self.assertEqual(run(Assumptions())["scenarios"], run(Assumptions(buildings=b))["scenarios"])
    def test_full_v1_opex_reproduced_when_maintenance_calibrated(self):
        # Same HK$ maintenance totals as v1, expressed on the new per-kW basis.
        s = self.o["scenarios"]; a = Assumptions(maint_existing_kw=s[0]["maint"] / self.peak, maint_upgrade_kw=s[1]["maint"] / self.peak,
            maint_central_plant_kw=s[2]["maint"] / (self.peak * 0.8), maint_network_pct=0.0)
        for so, sn in zip(s, run(a)["scenarios"]):
            self.assertAlmostEqual(so["opex"], sn["opex"], places=4); self.assertAlmostEqual(so["saving"], sn["saving"], places=4)
    def test_mixed_cop_changes_only_retain(self):
        b = list(Assumptions().buildings); b[0] = (*b[0][:4], 2.0)
        n = run(Assumptions(buildings=tuple(b)))["scenarios"]; base = run(Assumptions())["scenarios"]
        self.assertGreater(n[0]["elec"], base[0]["elec"]); self.assertAlmostEqual(n[1]["elec"], base[1]["elec"])
    def test_maintenance_independent_of_floor_area_split(self):
        a1 = run(Assumptions(buildings=(("A", 1000, 100, 2000), ("B", 1000, 100, 2000))))["scenarios"][0]["maint"]
        a2 = run(Assumptions(buildings=(("A", 2000, 100, 2000),)))["scenarios"][0]["maint"]; self.assertAlmostEqual(a1, a2)
if __name__ == "__main__": unittest.main()
