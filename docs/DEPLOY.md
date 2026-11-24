# Deployment

## Local (already working on this computer)
    cd "C:\Users\nadya\Downloads\ccai project\hk-cooling-screener"
    python -m pip install -r requirements.txt
    python -m streamlit run app.py
The browser opens at http://localhost:8501. Tested here with Python 3.15.2, Streamlit 1.67, folium 1.0, streamlit-folium 0.27, pyproj 3.8.
Map tiles come from OpenStreetMap, so the browser needs internet access; everything else is local.

## Streamlit Community Cloud
1. **Private** GitHub repository (footprint licence unconfirmed). Include everything in this folder except `raw/`
   (already in `.gitignore`). `data/districts/sha_tin/buildings.geojson` is 38 MB: GitHub's web uploader stops at 25 MB,
   so push with GitHub Desktop or `git` (limit 100 MB per file), or drop Sha Tin from `config/districts.json` and rebuild.
2. share.streamlit.io › Create app › repository, branch `main`, main file `app.py`; under Advanced settings choose Python 3.12 or 3.13.
3. Memory: each district is loaded once per server and cached. Sha Tin (16,629 buildings) takes about 4 s the first time.

## Rebuilding data
See `DATA_PREP.md`. The app refuses a package whose files no longer match its manifest (SHA-256).

## Known environment note
On Python 3.15, Streamlit's *test* harness (AppTest) must import pandas in the main thread first; `test_app_smoke.py` does this.
`streamlit run` itself is unaffected.
