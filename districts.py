"""Application-side access to prepared district packages: data/districts/<id>/{manifest.json,buildings.geojson,buildings.csv}.
Adding a district = running tools/prepare_districts.py with a new config entry. No application code changes."""
import csv, gzip, hashlib, io, json, re
from pathlib import Path
from buildings import BuildingRecord, Val, src
from geometry import ring_area, ring_centroid

ROOT_DIR = Path(__file__).resolve().parent / "data" / "districts"
ID = "Building_ID_建筑ID"
HB = "HK-BFETD v1.1 "
_MIX = re.compile(r"([^:]+?):(\d+(?:\.\d+)?)(?:-|$)")


class DataIntegrityError(Exception):
    pass


def _f(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def parse_mix(s):
    """'Private Housing_私人房屋:0.77-Commercial_商业类别:0.23' -> ((label, 0.77), (label, 0.23)).
    Returns () when the text cannot be parsed completely or the shares do not sum to ~1. Never guesses."""
    m = _MIX.findall(s or "")
    if not m or "-".join(f"{l}:{v}" for l, v in m) != s: return ()
    out = tuple((l, float(v)) for l, v in m)
    return out if abs(sum(v for _, v in out) - 1) <= 0.02 else ()


def read_bytes(pkg, name):
    """Bytes of a package file. A large file may be stored gzip-compressed as <name>.gz (GitHub's web uploader stops at 25 MB);
    it is decompressed here, and the fingerprint check below runs on the decompressed bytes, so the integrity guarantee is the same."""
    p = Path(pkg) / name
    if p.exists(): return p.read_bytes()
    gz = Path(pkg) / (name + ".gz")
    if gz.exists(): return gzip.decompress(gz.read_bytes())
    raise FileNotFoundError(str(p))


def verify_package(pkg):
    """Re-hash the package files against its manifest. Returns (ok, problems)."""
    pkg = Path(pkg); probs = []
    try: man = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e: return False, [f"manifest unreadable: {e}"]
    for name, meta in man["files"].items():
        try: b = read_bytes(pkg, name)
        except FileNotFoundError: probs.append(f"{name} missing"); continue
        if len(b) != meta["bytes"] or hashlib.sha256(b).hexdigest() != meta["sha256"]:
            probs.append(f"{name} differs from the manifest fingerprint")
    if not man["validation"]["passed"]: probs.append("package did not pass validation when it was built")
    return not probs, probs


def list_districts(root=None):
    root = Path(root or ROOT_DIR); idx = root / "index.json"
    if idx.exists(): return sorted(json.loads(idx.read_text(encoding="utf-8"))["districts"], key=lambda d: d["name"])
    out = []
    for m in sorted(root.glob("*/manifest.json")):
        j = json.loads(m.read_text(encoding="utf-8"))
        if j["validation"]["passed"]:
            out.append({"id": j["district"]["id"], "name": j["district"]["name"], "kind": j["district"]["kind"], "status": j["district"]["status"],
                        "parent": j["district"]["parent"], "buildings": j["counts"]["buildings"], "extent_hk80": j["summary"]["extent_hk80"]})
    return sorted(out, key=lambda d: d["name"])


def load_manifest(district_id, root=None):
    return json.loads((Path(root or ROOT_DIR) / district_id / "manifest.json").read_text(encoding="utf-8"))


def load_district(district_id, root=None, verify=True):
    """Returns (records, report). Every attribute keeps its source status; nothing is filled in here."""
    pkg = Path(root or ROOT_DIR) / district_id
    if verify:
        ok, probs = verify_package(pkg)
        if not ok: raise DataIntegrityError(f"{district_id}: " + "; ".join(probs))
    with io.StringIO(read_bytes(pkg, "buildings.csv").decode("utf-8"), newline="") as fh: rows = {r[ID]: r for r in csv.DictReader(fh)}
    feats = json.loads(read_bytes(pkg, "buildings.geojson").decode("utf-8"))["features"]
    recs, issues = [], []
    for f in feats:
        gid = str(f["properties"][ID]); row = rows.get(gid)
        ring = tuple(tuple(p[:2]) for p in f["geometry"]["coordinates"][0])
        if row is None: tier = "unmatched"; issues.append((gid, "no CSV row"))
        else:
            fa = _f(row.get("Footprint_Area_sqm_占地面积"))
            tier = "exact_id" if fa and abs(ring_area(ring) / fa - 1) <= 0.01 else "ambiguous"
            if tier != "exact_id": issues.append((gid, "footprint area differs from polygon area (courtyard or data issue)"))
        r = row or {k: ("" if v is None else str(v)) for k, v in f["properties"].items()}
        name = (r.get("LandsD_Building_Name_EN_地政署英文名") or r.get("LandsD_Building_Name_TC_地政署中文名") or "").strip() or f"Building {gid}"
        gfa = _f(r.get("LandsD_Registered_GFA_地政署注册面积"))
        recs.append(BuildingRecord(
            building_id=f"HKBFETD-{gid}", name=name.title() if name.isupper() else name, district=district_id,
            footprint_hk80=ring, centroid_hk80=ring_centroid(list(ring)),
            building_type=r.get("UBEM_Main_Class_主类别", ""), function=r.get("UBEM_Sub_Class_子类别", ""),
            use_mix=parse_mix(r.get("UBEM_Mixed_Proportions_混合比例", "")),
            match_tier=tier, source_ids=(("HK-BFETD Building_ID", gid),),
            height_m=src(_f(r.get("Height_m_建筑高度")), HB + "Height_m (origin not documented in files)"),
            storeys=src(_f(r.get("Floors_Count_地上层数")), HB + "Floors_Count (origin not documented in files)"),
            footprint_area_m2=src(_f(r.get("Footprint_Area_sqm_占地面积")), HB + "Footprint_Area_sqm"),
            gfa_m2=src(gfa, HB + "LandsD_Registered_GFA") if gfa else Val(),
            age_year=src(_f(r.get("BDBIAR_Building_Age_Year_屋宇署楼龄年份")), HB + "BDBIAR year (approval year, not plant age)"),
            attrs=tuple((k, r.get(k, "")) for k in ("Classification_Source_分类来源", "UBEM_Mixed_Proportions_混合比例",
                        "ML_Prediction_Confidence_机器学习置信度", "OZP_Zone_Code_法定图则代码", "BDBIAR_Classification_屋宇署分类"))))
    man = load_manifest(district_id, root)
    return recs, dict(n=len(recs), tiers={t: sum(1 for r in recs if r.match_tier == t) for t in {r.match_tier for r in recs}},
                      issues=issues, unparsed_mix=sum(1 for r in recs if not r.use_mix), manifest=man)
