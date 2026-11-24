"""Loads the Kai Tak extract (unchanged HK-BFETD CSV + GeoJSON in data/kaitak) as BuildingRecords."""
import csv, json, hashlib, statistics
from pathlib import Path
from buildings import BuildingRecord, Val, src
from geometry import ring_area, ring_centroid
import math

DATA = Path(__file__).resolve().parent / "data" / "kaitak"
ID = "Building_ID_建筑ID"
HB = "HK-BFETD v1.1 "
FAR_FROM_CLUSTER_M = 3000.0

def _f(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def load_kaitak(data_dir=DATA):
    data_dir = Path(data_dir)
    rows = {r[ID]: r for r in csv.DictReader(open(data_dir / "hk_bfetd_kaitak.csv", encoding="utf-8-sig", newline=""))}
    feats = json.loads((data_dir / "hk_bfetd_kaitak.geojson").read_text(encoding="utf-8"))["features"]
    gids = [str(f["properties"][ID]) for f in feats]
    dup = {g for g in gids if gids.count(g) > 1}
    cents = [ring_centroid(f["geometry"]["coordinates"][0]) for f in feats]
    mid = (statistics.median(c[0] for c in cents), statistics.median(c[1] for c in cents))
    recs, issues = [], []
    for f, gid, c in zip(feats, gids, cents):
        p, row = f["properties"], rows.get(gid)
        ring = tuple(tuple(pt[:2]) for pt in f["geometry"]["coordinates"][0])
        if row is None: tier = "unmatched"; issues.append((gid, "no CSV row"))
        elif gid in dup: tier = "ambiguous"; issues.append((gid, "duplicate ID"))
        else:
            fa = _f(p.get("Footprint_Area_sqm_占地面积"))
            tier = "exact_id" if fa and abs(ring_area(ring) / fa - 1) <= 0.01 else "ambiguous"
            if tier != "exact_id": issues.append((gid, "footprint area differs from polygon area"))
        r = row or {k: ("" if v is None else str(v)) for k, v in p.items()}
        name = r.get("LandsD_Building_Name_EN_地政署英文名") or r.get("LandsD_Building_Name_TC_地政署中文名") or f"Building {gid}"
        dist = math.hypot(c[0] - mid[0], c[1] - mid[1])
        gfa = _f(r.get("LandsD_Registered_GFA_地政署注册面积"))
        recs.append(BuildingRecord(
            building_id=f"HKBFETD-{gid}", name=name.strip().title() if name.isupper() else name.strip(),
            footprint_hk80=ring, centroid_hk80=c,
            building_type=r.get("UBEM_Main_Class_主类别", ""), function=r.get("UBEM_Sub_Class_子类别", ""),
            match_tier=tier, source_ids=(("HK-BFETD Building_ID", gid),),
            height_m=src(_f(r.get("Height_m_建筑高度")), HB + "Height_m (origin not documented in files)"),
            storeys=src(_f(r.get("Floors_Count_地上层数")), HB + "Floors_Count (origin not documented in files)"),
            footprint_area_m2=src(_f(r.get("Footprint_Area_sqm_占地面积")), HB + "Footprint_Area_sqm"),
            gfa_m2=src(gfa, HB + "LandsD_Registered_GFA") if gfa else Val(),
            age_year=src(_f(r.get("BDBIAR_Building_Age_Year_屋宇署楼龄年份")), HB + "BDBIAR year (approval year, not plant age)"),
            attrs=tuple((k, r.get(k, "")) for k in ("Classification_Source_分类来源", "UBEM_Mixed_Proportions_混合比例",
                        "ML_Prediction_Confidence_机器学习置信度", "OZP_Zone_Code_法定图则代码")) + (("far_from_cluster", dist > FAR_FROM_CLUSTER_M), ("dist_from_cluster_centre_m", round(dist))),
        ))
    return recs, dict(n=len(recs), tiers={t: sum(1 for r in recs if r.match_tier == t) for t in {r.match_tier for r in recs}},
                      issues=issues, csv_only=sorted(set(rows) - set(gids)))

def sha256(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
