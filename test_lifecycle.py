"""Lifecycle model: hand calculations, conventions and sensitivity tools."""
import unittest
from dataclasses import replace
from model import Assumptions
import lifecycle as L

ONE = (("A", 10000, 100, 2000, 4.0),)          # 1,000 kW peak, 2,000,000 kWh cooling


def base(**kw):
    a = Assumptions(buildings=ONE, discount_rate=0.0, analysis_years=10, existing_remaining_life=20, tariff=1.0, emission_factor=0.5,
                    maint_existing_kw=0, maint_upgrade_kw=0, maint_central_plant_kw=0, maint_network_pct=0, dcs_maint_kw=0,
                    network_m=0, connection_cost=0, dcs_connection_cost=0, dcs_building_capex_kw=0, dcs_aux_kwh_per_kwh=0)
    return replace(a, **kw)


class Hand(unittest.TestCase):
    def test_individual_no_replacement_in_period(self):
        s = L.evaluate(base())["scenarios"]["Individual"]
        self.assertEqual(s["capex0"], 0); self.assertAlmostEqual(s["elec_yr"], 500000)      # 2e6 / COP 4
        self.assertAlmostEqual(s["pv_cost"], 10 * 500000)                                    # r = 0, tariff 1
        self.assertAlmostEqual(s["co2_t"], 250)

    def test_dcs_bill_is_capacity_plus_consumption(self):
        s = L.evaluate(base(dcs_capacity_rate=100, dcs_consumption_rate=0.2))["scenarios"]["DCS"]
        self.assertAlmostEqual(s["capacity_charge"], 1000 * 100 * 12)
        self.assertAlmostEqual(s["consumption_charge"], 2e6 * 0.2)
        self.assertAlmostEqual(s["opex1"], 1.2e6 + 0.4e6)
        self.assertAlmostEqual(s["elec_yr"], 0)                                              # building pays no plant electricity
        self.assertAlmostEqual(s["co2_t"], 2e6 / 5.5 * 0.5 / 1000)                           # attributed only

    def test_cmcs_matches_model_central_energy(self):
        from model import run
        a = base(network_m=800, network_cost_m=25000, connection_cost=1.5e6)
        c = L.evaluate(a)["scenarios"]["CMCS"]; m = run(a)["scenarios"][2]
        self.assertAlmostEqual(c["elec_yr"], m["elec"]); self.assertAlmostEqual(c["capex0"], m["capex"])

    def test_replacement_and_residual_value(self):
        # replacement at year 2 costing 1,000 kW x 1,000 = 1e6, life 4, period 4 -> residual 2/4 of 1e6 credited in year 4
        s = L.evaluate(base(existing_remaining_life=2, upgrade_capex_kw=1000, equipment_life=4, analysis_years=4))["scenarios"]["Individual"]
        self.assertEqual(s["capex"], [0, 0, 1e6, 0, -0.5e6])
        self.assertEqual([round(e) for e in s["elec"]], [0, 500000, 500000, round(2e6 / 4.2), round(2e6 / 4.2)])

    def test_discounting_and_payback(self):
        # DCS: invest 1e6 now, then save a fixed amount each year -> discounted payback known in closed form
        a = base(dcs_connection_cost=1e6, dcs_capacity_rate=0, dcs_consumption_rate=0, discount_rate=0.0, dcs_building_life=50)
        d = L.evaluate(a)["scenarios"]["DCS"]
        self.assertAlmostEqual(d["annual_saving1"], 500000)
        self.assertAlmostEqual(d["simple_payback"], 2.0); self.assertAlmostEqual(d["discounted_payback"], 2.0, places=6)
        d10 = L.evaluate(replace(a, discount_rate=0.10))["scenarios"]["DCS"]
        self.assertGreater(d10["discounted_payback"], 2.0)
        # 500k/1.1 + 500k/1.21 = 867,769 < 1e6 ; + 500k/1.331 = 1,243,426 -> between years 2 and 3
        self.assertTrue(2 < d10["discounted_payback"] < 3)

    def test_npv_saving_equals_difference_of_pv(self):
        r = L.evaluate(Assumptions())
        for n in L.SCENARIOS:
            self.assertAlmostEqual(r["scenarios"][n]["npv_saving"], r["scenarios"]["Individual"]["pv_cost"] - r["scenarios"][n]["pv_cost"])
        self.assertEqual(r["scenarios"]["Individual"]["npv_saving"], 0)
        self.assertEqual(r["best"], min(L.SCENARIOS, key=lambda n: r["scenarios"][n]["pv_cost"]))

    def test_invalid_inputs_raise(self):
        with self.assertRaises(ValueError): L.evaluate(Assumptions(buildings=()))
        with self.assertRaises(ValueError): L.evaluate(Assumptions(analysis_years=0))


class Sensitivity(unittest.TestCase):
    def test_tornado_signs(self):
        a = Assumptions()
        base_, rows = L.tornado(a, "DCS", "npv_saving", 0.2)
        r = {x["field"]: x for x in rows}
        self.assertLess(r["dcs_capacity_rate"]["high"], base_)           # dearer DCS tariff -> lower saving
        self.assertGreater(r["tariff"]["high"], base_)                   # dearer electricity -> DCS looks better
        self.assertEqual(rows, sorted(rows, key=lambda x: -x["swing"]))

    def test_two_way_centre_is_base(self):
        a = Assumptions(); xs, ys, z = L.two_way(a, "tariff", "dcs_capacity_rate", "DCS", "npv_saving")
        self.assertAlmostEqual(z[3][3], L.metric(a, "DCS", "npv_saving"))
        self.assertEqual(len(z), 7); self.assertEqual(len(z[0]), 7)

    def test_breakeven_gives_zero_npv(self):
        a = Assumptions(); k = L.breakeven(a, "dcs_capacity_rate", "DCS")
        self.assertIsNotNone(k)
        self.assertAlmostEqual(L.metric(L._set(a, "dcs_capacity_rate", k), "DCS", "npv_saving"), 0, delta=5e3)

    def test_deterministic(self):
        self.assertEqual(L.evaluate(Assumptions()), L.evaluate(Assumptions()))


if __name__ == "__main__": unittest.main()
