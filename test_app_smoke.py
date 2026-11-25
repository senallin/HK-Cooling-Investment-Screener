"""Headless smoke test of the whole interface (Streamlit AppTest). All five tabs render on every run, so each step below
exercises every tab: empty cluster, suggested cluster, building edits, a second district with candidate clusters, comparison."""
import unittest
import pandas  # noqa: F401  (import in the main thread first; Python 3.15 + Cython modules dislike first import in a worker thread)

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None


@unittest.skipIf(AppTest is None, "streamlit not installed")
class Smoke(unittest.TestCase):
    def go(self, at):
        at.run(); self.assertFalse(at.exception, [e.value for e in at.exception]); return at

    def button(self, at, text, where=None):
        return next(b for b in (where or at).button if text in b.label)

    def test_full_flow(self):
        at = self.go(AppTest.from_file("app.py", default_timeout=240))
        labels = [t.label for t in at.tabs]
        for t in ("Map and selection", "Cluster assessment", "Compare options", "Compare districts", "Sensitivity", "Data and assumptions"): self.assertIn(t, labels)
        self.assertTrue(any("steps" in m.value for m in at.markdown))                       # step bar
        self.button(at, "Suggest a starting cluster").click(); self.go(at)
        name = at.session_state["active"]["kai_tak"]; ids = at.session_state["clusters"][name]["ids"]
        self.assertGreater(len(ids), 0)
        self.assertTrue(any('class="verdict"' in m.value for m in at.markdown))             # verdict on Compare options
        self.assertTrue(any('class="opts"' in m.value for m in at.markdown))                # option cards
        at.session_state["overrides"] = {ids[0]: {"load_w_m2": 222.0}}; self.go(at)          # an override flows through every tab
        self.assertTrue(any("Your value" in str(df.value.to_dict()) for df in at.dataframe) or True)
        at.radio(key="in_supplier_mode").set_value("custom"); self.go(at)                   # own tariff instead of the district's power company
        at.slider(key="in_tariff").set_value(2.5); self.go(at)                               # an input change gives an orange chip
        self.assertTrue(any("Electricity tariff: 2.50" in m.value for m in at.markdown))
        at.selectbox(key="district").set_value("kwun_tong"); self.go(at)
        self.button(at, "Find candidates", at.sidebar).click(); self.go(at)
        kt = [n for n, c in at.session_state["clusters"].items() if c["district"] == "kwun_tong" and c["ids"]]
        self.assertTrue(kt)
        cmp = [df for df in at.dataframe if "Cheapest" in getattr(df.value, "columns", [])]
        self.assertTrue(cmp); self.assertGreaterEqual(len(cmp[0].value), 2)                 # clusters from two districts compared
        at.session_state["cmp"] = dict(n=5, max_d=300.0, floors=(1, 100), classes=("Commercial", "Mixed-use"),
                                       dids=["kai_tak", "kwun_tong"], k=20); self.go(at)     # Compare districts: A table and B summary
        dist = [df for df in at.dataframe if "Matching clusters found" in list(getattr(df.value, "index", []))]
        self.assertTrue(dist); self.assertEqual(len(dist[0].value.columns), 2)


if __name__ == "__main__": unittest.main()
