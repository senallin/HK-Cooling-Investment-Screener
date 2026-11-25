"""Look and feel ("Trust & Clarity" design system, see docs/DESIGN.md): one palette, one set of names, status badges.
primary teal #006D77 · slate #2C3E50 · text #333333 on #F5F5F5 · green = best value · orange = warnings · red = hard errors only.
Inter for interface text, IBM Plex Mono (tabular) for numbers."""
import streamlit as st
from verdict import NAMES as OPTION_NAMES, SHORT as OPTION_SHORT  # noqa: F401  (one vocabulary, re-exported)

TEAL, SLATE, TEXT, BG, CARD, LINE = "#006D77", "#2C3E50", "#333333", "#F5F5F5", "#FFFFFF", "#DDE3E6"
GREEN, ORANGE, RED, MUTED, PURPLE = "#4CAF50", "#FF9800", "#C62828", "#6B7A85", "#7B5EA7"
OPTION_COLORS = {"Individual": "#9AA5AB", "CMCS": TEAL, "DCS": PURPLE}

# Muted building-type palette so the teal selection outline and orange warning outline stay the strongest marks.
TYPE_COLORS = {"Commercial": "#D4B483", "Mixed-use": "#A68DC4", "Residential": "#7FA7C9", "Industrial": "#8A979E", "Non-assessed": "#C9CFD2"}
FALLBACK_TYPE = "#B4BDC2"
BLUES = ["#DCEAF4", "#A9CBE3", "#6FA6CF", "#3A7DB3", "#1B4F7A"]; NO_DATA = "#D5DADD"

STATUS_LABEL = {"source": "Source", "derived": "Estimate", "assumption": "Assumption", "override": "Your value", "missing": "Missing"}
STATUS_COLOR = {"source": "#1F6F4A", "derived": "#8A6100", "assumption": "#9A5B00", "override": TEAL, "missing": RED}


def status_label(s): return STATUS_LABEL.get(s, s or "")


CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
html, body, .stApp, [class*="css"], .stMarkdown, button, input, textarea, select {font-family:'Inter',system-ui,sans-serif;}
.stApp {background:%(BG)s; color:%(TEXT)s;}
h1,h2,h3,h4 {font-family:'Inter',sans-serif !important; color:%(SLATE)s; font-weight:650; letter-spacing:-.015em;}
h1 {font-size:1.65rem !important; margin-bottom:0 !important;}
.block-container {padding-top:1.6rem;}
.num, [data-testid="stMetricValue"] {font-family:'IBM Plex Mono',ui-monospace,monospace !important; font-variant-numeric:tabular-nums;}
[data-testid="stMetric"] {background:%(CARD)s; padding:.65rem .85rem; border-radius:8px; border:1px solid %(LINE)s;}
[data-testid="stMetricValue"] {font-size:1.35rem; color:%(SLATE)s;}
section[data-testid="stSidebar"] {background:%(CARD)s; border-right:1px solid %(LINE)s;}
.stTabs [data-baseweb="tab"] {font-weight:600;}

.card {background:%(CARD)s; border:1px solid %(LINE)s; border-radius:10px; padding:.9rem 1rem; margin:.2rem 0 .7rem;}
.card h4 {margin:0 0 .35rem; font-size:1.02rem;}
.card .sub, .sub {color:%(MUTED)s; font-size:.82rem;}
.eyebrow {text-transform:uppercase; letter-spacing:.06em; font-size:.68rem; font-weight:700; color:%(MUTED)s;}

.verdict {font-size:1.35rem; font-weight:600; line-height:1.35; color:%(SLATE)s; max-width:62ch; margin:.1rem 0 .5rem;}
.verdict.small {font-size:1.0rem;}
.note {border-left:3px solid %(TEAL)s; padding:.45rem .85rem; background:%(CARD)s; font-size:.9rem; margin:.4rem 0; border-radius:0 6px 6px 0;}
.warn {border-left:3px solid %(ORANGE)s; padding:.45rem .85rem; background:#FFF6E8; font-size:.9rem; margin:.4rem 0; border-radius:0 6px 6px 0;}
.badge {display:inline-block; font-size:.68rem; font-weight:600; color:#fff; padding:1px 7px; border-radius:9px; vertical-align:middle;}
.chip {display:inline-block; font-size:.78rem; padding:2px 9px; margin:2px 4px 2px 0; border-radius:12px; background:#E6F1F2; color:%(TEAL)s; border:1px solid #BFDADD;}
.chip.warn {background:#FFF3E0; color:#8A4B00; border-color:#FFD08A;}
.chip.src {background:#E8F3EC; color:#1F6F4A; border-color:#BCD9C6;}

.legend {font-size:.8rem; color:%(TEXT)s; margin-top:.2rem; line-height:1.9;}
.legend span.sw {display:inline-block; width:12px; height:12px; border-radius:2px; margin:0 5px 0 12px; vertical-align:middle; border:1px solid #2C3E5033;}
.legend span.sw.sel {background:#fff; border:3px solid %(TEAL)s;}
.legend span.sw.far {background:#fff; border:2px dashed %(ORANGE)s;}
.legend span.sw.dcs {background:#7B5EA722; border:2px solid %(PURPLE)s;}
.legend span.sw.bnd {background:#fff; border:1.5px dotted %(MUTED)s;}

.steps {display:flex; gap:.6rem; margin:.6rem 0 .9rem; flex-wrap:wrap;}
.step {flex:1 1 200px; display:flex; gap:.6rem; align-items:center; background:%(CARD)s; border:1px solid %(LINE)s; border-radius:10px; padding:.55rem .8rem;}
.step .n {flex:0 0 26px; height:26px; border-radius:50%%; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:.85rem; background:#E9EDEF; color:%(MUTED)s;}
.step.done .n {background:%(TEAL)s; color:#fff;}
.step.now {border-color:%(TEAL)s; box-shadow:0 0 0 1px %(TEAL)s inset;}
.step b {display:block; font-size:.85rem; color:%(SLATE)s;}
.step small {display:block; font-size:.8rem; color:%(MUTED)s; line-height:1.3;}

.opts {display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:.7rem; margin:.4rem 0 .8rem;}
.opt {background:%(CARD)s; border:1px solid %(LINE)s; border-top:4px solid var(--c); border-radius:10px; padding:.75rem .9rem;}
.opt.best {box-shadow:0 0 0 2px %(GREEN)s;}
.opt .name {font-weight:650; color:%(SLATE)s; font-size:.95rem; margin-bottom:.15rem;}
.opt .what {color:%(MUTED)s; font-size:.76rem; margin-bottom:.45rem; min-height:2.1em;}
.opt .tag {float:right; font-size:.68rem; font-weight:700; color:#fff; background:%(GREEN)s; border-radius:9px; padding:1px 7px;}
.opt table {width:100%%; border-collapse:collapse; font-size:.82rem;}
.opt td {padding:.18rem 0; border-top:1px solid #EEF1F3;}
.opt td.v {text-align:right; font-family:'IBM Plex Mono',monospace; font-variant-numeric:tabular-nums; color:%(SLATE)s;}
.opt td.v.win {color:#2E7D32; font-weight:600;}
.opt td.v.win::before {content:"● "; color:%(GREEN)s; font-size:.6rem; vertical-align:middle;}

.kv {display:grid; grid-template-columns:repeat(3,1fr); gap:.5rem; margin:.4rem 0 .2rem;}
.kv div {background:#F7F9FA; border-radius:8px; padding:.45rem .6rem;}
.kv .k {font-size:.72rem; color:%(MUTED)s;}
.kv .v {font-family:'IBM Plex Mono',monospace; font-size:1.0rem; color:%(SLATE)s;}
@media (max-width:640px){.verdict{font-size:1.1rem} .kv{grid-template-columns:repeat(2,1fr)}}
</style>""" % dict(BG=BG, TEXT=TEXT, SLATE=SLATE, CARD=CARD, LINE=LINE, TEAL=TEAL, ORANGE=ORANGE, GREEN=GREEN, MUTED=MUTED, PURPLE=PURPLE)


def inject_css(): st.markdown(CSS, unsafe_allow_html=True)
def html(s): st.markdown(s, unsafe_allow_html=True)
def note(text, kind="note"): html(f'<div class="{kind}">{text}</div>')


def badge(status):
    return f'<span class="badge" style="background:{STATUS_COLOR.get(status, MUTED)}">{STATUS_LABEL.get(status, status)}</span>'


def layout(fig, h=340, legend=False):
    fig.update_layout(height=h, margin=dict(l=0, r=0, t=36, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Inter, sans-serif", color=TEXT, size=12), title_font=dict(color=SLATE, size=14), showlegend=legend,
                      legend=dict(orientation="h", y=-.2), hoverlabel=dict(font_family="IBM Plex Mono, monospace"))
    fig.update_xaxes(gridcolor="#E3E8EB", zerolinecolor="#C5CDD2", tickfont=dict(family="IBM Plex Mono, monospace"))
    fig.update_yaxes(gridcolor="#E3E8EB", zerolinecolor="#C5CDD2")
    return fig


def mhk(x): return "n/a" if x is None else f"{'−' if x < 0 else ''}HK${abs(x) / 1e6:,.1f}M"
def yrs(x): return "not within period" if x is None else f"{x:.1f} yrs"
def num(v, unit=""): return "n/a" if v is None else (f"{v:,.0f}{unit}" if abs(v) >= 100 else f"{v:,.1f}{unit}")


def explain(group_or_keys, label="ⓘ What do these terms mean?"):
    """Small button that opens a panel with plain-language explanations (glossary.py). Accepts a group name or a list of keys."""
    import glossary as G
    keys = G.GROUPS.get(group_or_keys, group_or_keys) if isinstance(group_or_keys, str) else group_or_keys
    with st.popover(label):
        st.markdown(G.markdown(keys))
        st.caption("Full glossary: Data and assumptions tab.")
