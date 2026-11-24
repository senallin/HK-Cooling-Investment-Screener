"""Building records: immutable source layer, derived estimates, user overrides kept separately."""
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Val:
    value: Optional[float] = None
    status: str = "missing"   # override | source | derived | assumption | missing
    ref: str = ""             # dataset field, method note, or assumption label

def _en(label): return label.split("_", 1)[0]

def src(v, ref): return Val(v, "source", ref) if v is not None else Val()

@dataclass(frozen=True)
class BuildingRecord:
    building_id: str
    name: str
    lon: float = float("nan")   # WGS84, filled only once a verified conversion exists
    lat: float = float("nan")
    footprint: tuple = ()          # outer ring [(lon, lat)], WGS84, for display
    footprint_hk80: tuple = ()     # same ring in EPSG:2326 metres, for distances
    building_type: str = ""
    function: str = ""
    match_tier: str = "unmatched"  # exact_id | spatial_high | ambiguous | unmatched | synthetic
    source_ids: tuple = ()         # ((dataset, id), ...)
    height_m: Val = Val()
    storeys: Val = Val()
    footprint_area_m2: Val = Val()
    gfa_m2: Val = Val()            # gross floor area from source, if any
    cooled_fraction: Val = Val()
    load_w_m2: Val = Val()
    hours: Val = Val()
    cop_existing: Val = Val()
    synthetic: bool = False        # True = test geometry, never real data
    centroid_hk80: tuple = ()      # (E, N) metres, EPSG:2326
    age_year: Val = Val()          # BDBIAR year linked by HK-BFETD; approval year, NOT plant age
    attrs: tuple = ()              # extra untouched source attributes as ((name, value), ...)
    district: str = ""             # district package id (data/districts/<id>)
    use_mix: tuple = ()            # ((source label, share), ...) parsed from UBEM_Mixed_Proportions; basis of share NOT documented

    @property
    def primary_use(self): return _en(max(self.use_mix, key=lambda t: t[1])[0]) if self.use_mix else ""
    @property
    def secondary_use(self):
        m = sorted(self.use_mix, key=lambda t: -t[1])
        return _en(m[1][0]) if len(m) > 1 else ""

    @property
    def selectable(self): return self.match_tier in ("exact_id", "spatial_high", "synthetic")

# Editable fields. Anything not in the source falls back to a labelled, editable assumption.
EDITABLE = ("gfa_m2", "cooled_fraction", "load_w_m2", "hours", "cop_existing")
DEFAULT_ASSUMPTIONS = {"cooled_fraction": 1.0, "load_w_m2": 110.0, "hours": 2800.0, "cop_existing": 3.2}

def resolve(rec, field, overrides=None, defaults=None):
    """override > source > derived > assumption > missing. Never mutates the record."""
    ov = (overrides or {}).get(rec.building_id, {}).get(field)
    if ov is not None and ov == ov:
        return Val(float(ov), "override", "user edit")
    v = getattr(rec, field)
    if v.value is not None: return v
    if field == "gfa_m2" and rec.footprint_area_m2.value and rec.storeys.value:
        return Val(rec.footprint_area_m2.value * rec.storeys.value, "derived", "footprint area x storeys (estimate)")
    d = {**DEFAULT_ASSUMPTIONS, **(defaults or {})}.get(field)
    return Val(d, "assumption", "illustrative default") if d is not None else Val()

def effective(rec, overrides=None, defaults=None):
    f = {k: resolve(rec, k, overrides, defaults) for k in EDITABLE}
    g, c = f["gfa_m2"], f["cooled_fraction"]
    f["cooled_area_m2"] = (Val(g.value * c.value, "derived", "GFA x cooled fraction")
                           if g.value is not None and c.value is not None else Val())
    return f

def to_model_buildings(records, overrides=None, defaults=None):
    """Convert records to the tuples model.run() consumes. Incomplete records are excluded and reported, never filled in."""
    out, excluded = [], []
    for r in records:
        f = effective(r, overrides, defaults)
        missing = [k for k in ("cooled_area_m2", "load_w_m2", "hours") if f[k].value is None]
        if missing: excluded.append((r.building_id, r.name, missing)); continue
        out.append((r.name, f["cooled_area_m2"].value, f["load_w_m2"].value, f["hours"].value, f["cop_existing"].value))
    return tuple(out), excluded
