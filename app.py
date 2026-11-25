"""HK Cooling Investment Screener: thin router. Logic lives in tested modules; the interface in ui/ (design: docs/DESIGN.md).

Layout: sidebar = district and cluster tools · header = step bar (district → cluster → result) · tabs = work areas.
Model inputs live on the Compare options tab; their values are read from session state first, so every view uses the same numbers.
Run:  python -m streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="HK Cooling Investment Screener", page_icon="❄", layout="wide")
import lifecycle as L  # noqa: E402
import verdict as V  # noqa: E402
from districts import list_districts  # noqa: E402
from model import validate  # noqa: E402
from ui import style, state, inputs, controls, explorer, assess, scenarios, data_tab, districts_tab  # noqa: E402

style.inject_css(); state.init()
ss = st.session_state
st.title("HK Cooling Investment Screener")
st.caption("Should a group of buildings keep its own cooling, share a private plant, or connect to public district cooling? "
           "A first screening, not an engineering feasibility study. Cooling loads and costs are illustrative estimates; the DCS tariff is EMSD's. "
           "New to the finance terms? Press the **ⓘ** button next to any result for a plain explanation.")

districts = list_districts()
if not districts:
    st.error("No district datasets found in data/districts/. Prepare them first: see docs/DATA_PREP.md (python tools/prepare_districts.py run)."); st.stop()
with st.sidebar:
    meta = controls.pick_district(districts)
    try:
        DD = state.district_data(meta["id"], meta.get("generated", ""))
    except Exception as e:                                       # tampered package, missing pyproj, ...: say so plainly
        st.error(f"Could not load the district: {e}"); st.stop()
    act, cl = controls.cluster_tools(meta)
    controls.candidates_panel(meta, DD)
    controls.export_panel()

cl["ids"] = [i for i in cl["ids"] if i in DD["by_id"]]
A, EXCL, G = inputs.assumptions_for(meta["id"], cl["ids"], meta.get("generated", ""))
R = L.evaluate(A) if A.buildings and not validate(A) else None

controls.banners(DD)
controls.step_bar(meta, act, len(cl["ids"]), R, V.short(R) if R else "")

t1, t2, t3, t4, t5, t6 = st.tabs(["Map and selection", "Cluster assessment", "Compare options", "Compare districts", "Sensitivity", "Data and assumptions"])
with t1: explorer.render(meta, DD, cl, G, R, A)
with t2: assess.render(meta, DD, cl, G, A, EXCL, districts)
with t3: scenarios.render_results(meta, cl, A, EXCL, G, R)
with t4: districts_tab.render(districts)
with t5: scenarios.render_sensitivity(A)
with t6: data_tab.render(meta, DD, districts)
