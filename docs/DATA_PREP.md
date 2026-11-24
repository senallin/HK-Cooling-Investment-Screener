# Preparing district datasets (run once on your computer)

## 1. Where the files go
Use the project folder that contains `app.py` (example: `C:\Users\nadya\Documents\hk-cooling-screener`).

    hk-cooling-screener\
      raw\
        HK_UBEM_Buildings_Public_v1_1.geojson     <- original 782 MB file, copy here
        HK_UBEM_Buildings_Public_v1_1.csv         <- original 130 MB file, copy here
        boundaries\
          district_boundary.json                  <- official 18-district boundary (section 2)

You can leave the big files where they are and add `--raw "C:\Users\nadya\Downloads\ccai project"` to the
commands below instead. The script only reads them and checks afterwards (SHA-256) that they are unchanged.

## 2. District boundary file (small)
Source: Home Affairs Department "District boundary" dataset on data.gov.hk (JSON or GML, longitude/latitude).
Save it as `raw\boundaries\district_boundary.json`. Licence terms have not been verified: check the dataset page.
If the file is not GeoJSON the `boundaries` command (step 4) says so; convert at mapshaper.org (free) or send me the first 1,000 characters.

## 3. Install (once)
    python -m pip install pyproj
Python 3.9 or newer. pyproj is needed only because the boundary is in longitude/latitude.

## 4. Commands (Command Prompt or PowerShell, from the project folder)
    python tools\prepare_districts.py check
    python tools\prepare_districts.py boundaries raw\boundaries\district_boundary.json
    python tools\prepare_districts.py run
`check` confirms files, CRS and columns. `boundaries` lists the district names so you can confirm the spellings in
`config\districts.json`. `run` takes a few minutes and prints progress. Results: `data\districts\<id>\`
(`buildings.geojson`, `buildings.csv`, `manifest.json`, `validation_report.md`) plus `data\districts\index.json`.
A district that fails validation is NOT published; it is moved to `data\districts\_rejected\`.
Re-running refuses to overwrite; add `--overwrite` to archive the old package into `_archive\` and rebuild.
`python tools\prepare_districts.py verify` re-checks packages against their manifests at any time.

## 5. Adding a district later (no code changes)
Add an entry to `config\districts.json` and run `python tools\prepare_districts.py run --only new_id`. Three area types:
* `boundary`: official boundary file plus `match.values` (district names)
* `polygon_file`: any GeoJSON polygon you draw (EPSG:4326 or 2326), e.g. exported from Scribble Maps or geojson.io
* `bbox`: `[minE, minN, maxE, maxN]` in EPSG:2326

## 5a. What was actually run (21 Nov 2026)
    python tools\prepare_districts.py run --raw "C:\Users\nadya\Downloads\ccai project"
* District boundary: `hksar_18_district_boundary.json` (18 features, WGS84, name field `District`, values such as
  "Kwun Tong District"), copied to `raw\boundaries\district_boundary.json`.
* Kai Tak: Planning Department OZP **S/K22/9** `PLAN_SCHEME_AREA.json` (Esri JSON, EPSG:2326, 2 outer rings + 1 hole;
  area 3,232,027 m², equal to the file's Shape_Area). The script now reads Esri JSON (clockwise ring = outer, anticlockwise = hole).
  Kai Tak is therefore **official**, no longer the provisional rectangle.
* Result: all four packages PASSED; originals unchanged (SHA-256). Kai Tak 899, Central and Western 7,076, Kwun Tong 4,783,
  Sha Tin 16,629 buildings (341,153 scanned). Each package now also contains `boundary.geojson` (EPSG:2326) for the map.

## 6. What is guaranteed
GeoJSON feature text is copied byte-for-byte; CSV keeps all 30 columns and values; each building is assigned by its
footprint centroid (a building straddling a boundary goes to the area holding its centroid); no names, workbooks or
earlier matches are used. Kai Tak is not an administrative district; its area is the official OZP S/K22/9 planning scheme boundary.
