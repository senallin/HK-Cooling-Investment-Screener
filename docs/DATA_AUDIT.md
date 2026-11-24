# Kai Tak data audit (from the files uploaded after running prepare_kaitak_data.py)
- Extracts: 176 buildings in CSV and GeoJSON; identical IDs, 0 duplicates; all 29 shared fields equal. Polygon area matches Footprint_Area_sqm (0.9955 to 1.0004). Checked, not assumed.
- CRS: HK-BFETD GeoJSON and the Lands Department GeoPackage are both EPSG:2326 (Hong Kong 1980 Grid, metres). Distances are therefore measured directly in metres. Display on a web map needs a conversion to WGS84 (not yet done; no conversion library available in the build sandbox).
- Workbook has 195 buildings, extracts 176: 19 unexplained until reports/ (quality_report.md, unmatched_and_ambiguous.csv, matching_table.csv) are provided.
- Selection by building NAME is geographically unreliable: 155 buildings sit in the Kai Tak cluster; 21 are far from it (e.g. "Kai Tak Garden", "Kai Tak Commercial Building"), apparently name coincidences. The same method will also miss Kai Tak buildings without "Kai Tak" in the name. Flagged in the data as far_from_cluster (heuristic: more than 3 km from the median centre).
- Only 17 commercial and 4 mixed-use buildings are in the cluster (132 residential, 2 non-assessed).
- Registered GFA is empty for all 176; GFA is therefore a derived estimate (footprint x floors) and labelled so. Floors_Count and Height_m are used as provided; their origin is not documented in the files.
- HK-BFETD has no Lands Department BuildingID/GeoRefNo, so it cannot be joined to the GeoPackage by ID; only by geometry or name. The GeoPackage is not used yet.
- BDBIAR year is an approval year for 47/176 buildings, not a plant age.
- Licences: HK-BFETD is CC BY 4.0 (credit the authors). The Lands Department footprint licence is unconfirmed: keep the repository private until checked.
