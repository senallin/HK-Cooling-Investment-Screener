# Cooling Investment Screener (Streamlit)
Compares three options for a group of commercial buildings: retain independent cooling, upgrade it, or build a shared central cooling plant. All numbers are **illustrative defaults**, not Hong Kong statistics. Replace them with project data. Works without API keys.

## Run locally
    pip install -r requirements.txt
    streamlit run app.py
Run the calculation tests: `python -m unittest -v`

## Deploy on Streamlit Community Cloud (needs your account)
1. Create a free GitHub account and a new public repository; upload every file in this folder.
2. Sign in at share.streamlit.io with GitHub.
3. Choose "Create app", select the repository, branch `main`, main file `app.py`, then Deploy.

## Files
`app.py` interface · `model.py` calculations · `test_model.py` tests · `docs/AI_LOG.md` AI-use record

## District data
See `docs/DATA_PREP.md` (district preparation from the full HK-BFETD files) and `docs/BRIEF_COVERAGE.md` (status against the brief).

## Kai Tak data (legacy workbook extract, superseded by data/districts)
`data/kaitak/` holds unchanged extracts from HK-BFETD v1.1 (CC BY 4.0, credit the dataset authors) and a manifest of SHA-256 fingerprints. Footprints derive from Lands Department data whose licence has not yet been confirmed: use a private repository until it is. See `docs/DATA_AUDIT.md`. The map interface is not built yet; the current app still uses the illustrative sample buildings.
Run all tests: `python -m unittest -v`
