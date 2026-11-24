import unittest
from dataclasses import replace
from model import Assumptions
import lifecycle as L
import verdict as V


def fake(cm, dc, years=25):
    """cm / dc = (npv_saving, discounted_payback). Individual pv_cost 100."""
    def s(npv, pb, co2=100): return dict(npv_saving=npv, discounted_payback=pb, pv_cost=100 - npv, opex1=10, co2_t=co2)
    S = {"Individual": s(0, None, 200), "CMCS": s(*cm), "DCS": s(*dc)}
    return {"scenarios": S, "years": years, "best": min(S, key=lambda n: S[n]["pv_cost"])}


class Verdict(unittest.TestCase):
    def test_none_pays(self):
        t = V.headline(fake((-5e6, None), (-9e6, None)))
        self.assertTrue(t.startswith("With these inputs, keeping individual plants is cheapest over 25 years"))
        self.assertIn("HK$5.0M more", t); self.assertIn("HK$9.0M more", t)
        self.assertEqual(V.short(fake((-1, None), (-1, None))), "Cheapest: keep individual plants")

    def test_only_one_pays(self):
        t = V.headline(fake((-5e6, None), (20e6, 6.0)))
        self.assertTrue(t.startswith("Only public district cooling beats keeping individual plants"))
        self.assertIn("6.0 years", t); self.assertIn("Shared plant (private) costs HK$5.0M more", t)

    def test_dominant(self):
        t = V.headline(fake((30e6, 4.0), (10e6, 9.0)))
        self.assertTrue(t.startswith("Shared plant (private) wins on both counts"))

    def test_tradeoff(self):
        t = V.headline(fake((30e6, 9.0), (10e6, 4.0)))
        self.assertIn("saves the most", t); self.assertIn("Public district cooling pays back faster (4.0 years)", t)

    def test_best_by_row(self):
        b = V.best_by_row(fake((30e6, 9.0), (10e6, 4.0)))
        self.assertEqual((b["npv"], b["payback"], b["pv_cost"]), ("CMCS", "DCS", "CMCS"))

    def test_real_model(self):
        for a in (Assumptions(), replace(Assumptions(), tariff=0.05), replace(Assumptions(), tariff=6.0)):
            r = L.evaluate(a); self.assertTrue(V.headline(r)); self.assertTrue(V.short(r))


if __name__ == "__main__": unittest.main()
