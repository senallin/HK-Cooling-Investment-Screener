# Validation report: Sha Tin (sha_tin)
Generated 2026-11-21T10:13:41Z by prepare_districts v2.0.0.
Status: **PASSED**; buildings: **16,629**; CRS EPSG:2326; area status: official.

| check | result | detail |
|---|---|---|
| every GeoJSON feature is byte-identical to its source text | PASS | 16,629 features, 0 differ |
| GeoJSON Building_IDs unique | PASS | 0 duplicates |
| rings closed, finite, at least 4 points | PASS | 0 bad |
| every centroid is inside the area polygon (re-tested from the written file) | PASS | 0 outside |
| CSV has the same columns, in the same order, as the original | PASS | 30 columns |
| CSV rows = GeoJSON features, same Building_ID set, no duplicates | PASS | csv=16,629 geojson=16,629 |
| every source CSV row for these ids was captured exactly once | PASS | 0 ids with 0 or >1 rows |
| all attributes agree between CSV and GeoJSON for every building (same field names, equal values) | PASS | no differences |
| source: GeoJSON feature count equals CSV row count | PASS | geojson=341,153 csv=341,153 |
| source: Building_ID unique in GeoJSON | PASS | 0 duplicates |
| source: Building_ID sets identical in both files | PASS | only-GeoJSON=0 only-CSV=0 |
| source: CSV row count equals unique CSV ids | PASS | rows=341,153 unique=341,153 |
| ORIGINAL HK_UBEM_Buildings_Public_v1_1.geojson UNCHANGED (SHA-256, size, mtime before = after) | PASS |  |
| ORIGINAL HK_UBEM_Buildings_Public_v1_1.csv UNCHANGED (SHA-256, size, mtime before = after) | PASS |  |

Assignment is by footprint centroid, so a building that straddles the boundary belongs to the area holding its centroid.
