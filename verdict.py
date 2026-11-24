"""Plain-language verdict for lifecycle.evaluate() results. Pure Python (no Streamlit), unit-tested.
One name per option everywhere (verdict, cards, tables, charts, legends)."""

NAMES = {"Individual": "Keep individual plants", "CMCS": "Shared plant (private)", "DCS": "Public district cooling"}
LOWER = {"Individual": "keeping individual plants", "CMCS": "a shared plant", "DCS": "public district cooling"}
SHORT = {"Individual": "Individual", "CMCS": "Shared plant", "DCS": "District cooling"}
ALTS = ("CMCS", "DCS")


def _m(x): return f"HK${abs(x) / 1e6:,.1f}M"


def ranking(res):
    S = res["scenarios"]
    paying = sorted([n for n in ALTS if S[n]["npv_saving"] > 0], key=lambda n: -S[n]["npv_saving"])
    pb = [n for n in paying if S[n]["discounted_payback"] is not None]
    return dict(S=S, paying=paying, best=res["best"], fastest=min(pb, key=lambda n: S[n]["discounted_payback"]) if pb else None)


def best_by_row(res):
    """Which option wins each card row. Cost rows compare all three; saving rows only the alternatives that pay."""
    S = res["scenarios"]; r = ranking(res); allo = ("Individual",) + ALTS
    out = {"pv_cost": min(allo, key=lambda n: S[n]["pv_cost"]), "opex1": min(allo, key=lambda n: S[n]["opex1"]),
           "co2": min(allo, key=lambda n: S[n]["co2_t"])}
    if r["paying"]: out["npv"] = r["paying"][0]
    if r["fastest"]: out["payback"] = r["fastest"]
    return out


def headline(res):
    r = ranking(res); S = r["S"]; p = r["paying"]; yrs = res["years"]
    if not p:
        a, b = S["CMCS"]["npv_saving"], S["DCS"]["npv_saving"]
        return (f"With these inputs, keeping individual plants is cheapest over {yrs} years: a shared plant costs {_m(a)} more "
                f"and public district cooling {_m(b)} more (present value).")
    f = p[0]; sf = S[f]
    pay = f" and pays back in {sf['discounted_payback']:.1f} years" if sf["discounted_payback"] is not None else ""
    if len(p) == 1:
        o = next(n for n in ALTS if n != f)
        return (f"Only {LOWER[f]} beats keeping individual plants: it saves {_m(sf['npv_saving'])} over {yrs} years (present value){pay}. "
                f"{NAMES[o]} costs {_m(S[o]['npv_saving'])} more.")
    o = p[1]; so = S[o]
    if r["fastest"] in (f, None):
        opay = f", {so['discounted_payback']:.1f} years" if so["discounted_payback"] is not None else ""
        return (f"{NAMES[f]} wins on both counts: it saves {_m(sf['npv_saving'])} over {yrs} years{pay} "
                f"({NAMES[o].lower()}: {_m(so['npv_saving'])}{opay}).")
    return (f"{NAMES[f]} saves the most ({_m(sf['npv_saving'])} over {yrs} years, present value). {NAMES[o]} pays back faster "
            f"({so['discounted_payback']:.1f} years) but saves less ({_m(so['npv_saving'])}).")


def short(res):
    r = ranking(res)
    if not r["paying"]: return "Cheapest: keep individual plants"
    f = r["paying"][0]; s = r["S"][f]
    return f"Best: {NAMES[f]}, saves {_m(s['npv_saving'])}" + (f", {s['discounted_payback']:.1f} yrs" if s["discounted_payback"] is not None else "")
