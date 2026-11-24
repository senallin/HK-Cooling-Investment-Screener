import unittest
from dataclasses import replace
from model import Assumptions, run, validate, sensitivity, cumulative

class T(unittest.TestCase):
    def test_hand_calc(self):
        a = Assumptions(buildings=(("X", 1000, 100, 2000),), tariff=1.0, emission_factor=0.5,
                        cop_existing=4, maint_existing_kw=0)
        s = run(a)["scenarios"][0]
        self.assertAlmostEqual(s["demand"], 200000)   # 1000*100*2000/1000 kWh
        self.assertAlmostEqual(s["elec"], 50000)
        self.assertAlmostEqual(s["opex"], 50000)
        self.assertAlmostEqual(s["co2_t"], 25)
    def test_baseline_has_no_saving(self):
        s = run(Assumptions())["scenarios"][0]
        self.assertEqual(s["saving"], 0); self.assertIsNone(s["payback"])
    def test_payback_formula(self):
        s = run(Assumptions())["scenarios"][2]
        if s["payback"]: self.assertAlmostEqual(s["payback"], s["capex"] / s["saving"])
    def test_better_cop_lowers_electricity(self):
        r = run(Assumptions())["scenarios"]
        self.assertLess(r[2]["elec"], r[0]["elec"]); self.assertLess(r[1]["elec"], r[0]["elec"])
    def test_invalid_inputs(self):
        for bad in (replace(Assumptions(), cop_central=0), replace(Assumptions(), buildings=()),
                    replace(Assumptions(), network_loss=0.9), replace(Assumptions(), buildings=(("x", -5, 100, 2000),))):
            self.assertTrue(validate(bad)); self.assertRaises(ValueError, run, bad)
    def test_no_saving_gives_none_payback(self):
        s = run(replace(Assumptions(), cop_central=1.0))["scenarios"][2]
        self.assertIsNone(s["payback"])
    def test_deterministic(self):
        self.assertEqual(run(Assumptions()), run(Assumptions()))
    def test_sensitivity_and_cumulative(self):
        a = Assumptions(); base, rows = sensitivity(a)
        self.assertEqual(len(rows), 9)
        tariff = next(r for r in rows if r["label"] == "Electricity tariff")
        self.assertGreater(tariff["high"], 0)
        c = cumulative(a, run(a), 5); self.assertEqual(len(c["Central"]), 6)
if __name__ == "__main__": unittest.main()
