"""Sidebar (district and cluster tools only), candidate-cluster search, data banner and the step bar."""
import streamlit as st
import clusters as C
from ui import state, inputs
from ui.style import html, note


def pick_district(districts):
    ss = st.session_state; ids = [d["id"] for d in districts]; by = {d["id"]: d for d in districts}
    if "district" in ss and ss["district"] not in ids: del ss["district"]
    lab = lambda i: f"{by[i]['name']} · {by[i]['buildings']:,} buildings"
    did = st.selectbox("District", ids, index=ids.index("kai_tak") if "kai_tak" in ids else 0, format_func=lab, key="district",
                       help="Kai Tak is the Outline Zoning Plan S/K22/9 area (served by the government DCS). The others are administrative districts.")
    return by[did]


def cluster_tools(meta):
    ss = st.session_state; did, dname = meta["id"], meta["name"]
    act = state.active(did, dname); nm = state.names(did)
    pick = st.selectbox("Cluster", nm, index=nm.index(act), key=f"cl_{did}_{ss.ver}")
    if pick != act: ss.active[did] = pick; ss.focus = None; state.bump(); st.rerun()
    cl = ss.clusters[act]
    st.caption(f"{len(cl['ids'])} building(s) selected")
    if st.button("New cluster", key="new_cl", width="stretch", type="primary"):
        state.new_cluster(did, dname); ss.focus = None; state.bump(); st.rerun()
    if st.button("Delete this cluster", key="del_cl", width="stretch", help=f"Delete “{act}”."):
        del ss.clusters[act]; ss.active.pop(did, None); ss.notice = f"Deleted “{act}”."; state.bump(); st.rerun()
    with st.expander("Rename or clear"):
        new = st.text_input("Name", act, key=f"rn_{act}_{ss.ver}")
        c1, c2 = st.columns(2)
        if c1.button("Rename", key="rn_go", disabled=not new.strip() or new == act):
            if new in ss.clusters: st.warning("That name is taken.")
            else: ss.clusters[new] = ss.clusters.pop(act); ss.active[did] = new; state.bump(); st.rerun()
        if c2.button("Clear buildings", key="clr_go", disabled=not cl["ids"]):
            cl["ids"] = []; ss.focus = None; ss.seen_draw = set(); state.bump(); st.rerun()
    if ss.notice: st.success(ss.notice); ss.notice = None
    return act, cl


def candidates_panel(meta, DD):
    ss = st.session_state
    with st.expander("Find candidate clusters"):
        st.caption("Groups the largest-demand buildings with every neighbour whose centre is within the radius (so members are at most "
                   "twice the radius apart: 150 m matches the 300 m screening check). Computed starting points, not existing systems.")
        r = st.slider("Radius (m)", 50, 300, 150, 10, key="sg_r"); n = st.slider("Minimum buildings", 3, 30, 6, key="sg_n")
        res = st.checkbox("Include residential buildings", False, key="sg_res")
        if st.button("Find candidates", key="sg_go", type="primary"):
            classes = None if res else ("Commercial", "Mixed-use")
            items = C.suggest_clusters(DD["recs"], DD["idx"], r, n, ss.overrides, inputs.global_defaults(), state.table(), classes)
            if not items: ss.notice = "No group of that size within that radius. Try a larger radius or fewer buildings."
            for k, it in enumerate(items):
                state.new_cluster(meta["id"], meta["name"], it["ids"], name=f"{meta['name']} candidate {k + 1}")
            if items:
                ss.active[meta["id"]] = f"{meta['name']} candidate 1" if f"{meta['name']} candidate 1" in ss.clusters else ss.active[meta["id"]]
                ss.notice = f"{len(items)} candidate cluster(s) added, largest first. Pick one in the Cluster box."; ss.fit = ("cluster", ss.ver)
            state.bump(); st.rerun()


def export_panel():
    ss = st.session_state
    if any(c["ids"] for c in ss.clusters.values()):
        st.caption("Clusters last until you close or reload this tab. Export them to keep them; import on the Data and assumptions tab.")
        st.download_button("Export all clusters (JSON)", C.clusters_to_json(ss.clusters), "clusters.json", "application/json", key="dl_cl", width="stretch")


def banners(DD):
    m = DD["manifest"]
    if m["district"]["status"] == "provisional":
        note("⚠ This district's area is provisional. Details on the Data and assumptions tab.", "warn")


def step_bar(meta, act, n_sel, R, short):
    s1 = f"{meta['name']} · {meta['buildings']:,} buildings"
    s2 = f"{act} · {n_sel} building{'s' if n_sel != 1 else ''}" if n_sel else "Click, draw or find candidates"
    s3 = short if R else ("Select at least one building" if not n_sel else "Waiting for valid inputs")
    d2, d3 = n_sel >= 1, R is not None
    step = lambda k, t, sub, done, now: (f'<div class="step{" done" if done else ""}{" now" if now else ""}"><span class="n">{"✓" if done else k}</span>'
                                         f'<div><b>{t}</b><small>{sub}</small></div></div>')
    html('<div class="steps">' + step(1, "District", s1, True, False) + step(2, "Cluster", s2, d2, not d2)
         + step(3, "Result", s3 + (" · see Compare options" if d3 else ""), d3, d2 and not d3) + "</div>")
