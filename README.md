# Lake Winnipeg 2025 — MV NAMAO Data Explorer

An interactive, **self-contained** explorer for the 2025 Limnology & Oceanography
Field Course rosette water-chemistry and CTD data, built as a companion to Ocean
Data View (ODV).

## For students

Just **open `index.html` in any web browser** (Chrome, Safari, Firefox, Edge).
No internet, no install — the data and all plotting code are baked into the one file.

**Navigating any chart:** drag to pan, scroll-wheel or double-click to zoom (double-click
resets to the full view). Every plot's dataset can be switched between **Bottle chemistry**,
**CTD sensors**, and **Live sonde** where they apply.

**Year filter:** the **Year** checkboxes in the top-right of the header filter every analysis tab by year
(e.g. 2025 bottle/CTD vs 2026 live sonde). The *Live* console tab itself always shows the full log.

Two datasets are bundled:

- **Bottle chemistry** — discrete rosette/Niskin samples (nutrients, isotopes, carbonate, ions…)
- **RBR CTD casts** — high-resolution sensor profiles (T, salinity, O₂, Chl a, CDOM, turbidity, PAR)
- **Live YSI sonde** — a real June-25 EXO sonde run (892 KB KorDSS export, time-matched to a GPS track) is **pre-loaded**; you can also stream live or load your own files on the **Live** tab

### Tabs

- **Station Map** — sampling locations over an offline satellite basemap (Web-Mercator), colour-coded by any bottle variable. The geolocated **live sonde track** can be overlaid and coloured by any YSI parameter (its own colourbar), so you can see e.g. the conductivity gradient laid over the station grid. A **Sonde stops** overlay (from `sonde_stations.csv`) marks every >5-min stop — **FULL stations** as labelled gold diamonds sized by duration, quick **CTD stops** as small dots.
- **Live** — stream and log real-time data from the YSI Bluetooth/GPS sonde: live readouts, a rolling chart, and a track on the map (coloured by the selected variable). A real sonde run is **pre-loaded** on open; **Load KorDSS CSV** imports a logged export and **Load GPS (GPX)** geolocates it by time-match (with a GPS-offset nudge). A built-in **Demo** mode simulates a cast offline. **CSV (sonde+GPS, ODV)** exports the merged, geolocated data in Ocean Data View spreadsheet format. Everything appears as the **Live sonde** dataset in the other tabs (the Section inset map is also coloured by the chosen parameter).
- **Bottle Profiles** — a bottle variable vs. depth, overlaying several stations.
- **CTD Casts** — high-resolution CTD sensor profiles vs. depth.
- **Property–Property** — any variable vs. any other, coloured by a third (the ODV X/Y scatter).
- **Section** — a vertical section along the cruise track. The track is an inverted V (southwest → northern apex → southeast): bottle `S1 → S2 → W12 → S59 → W10 → W9 → CS1 → S7`; the denser CTD track adds the transect stops along the same path. An inset map shows the station order.
- **Data Table** — sort, search, and download the cleaned bottle/CTD data as CSV.
- **Talk to the Lake** — a built-in AI chat assistant. This is included **only as a demonstration of what AI can do** with a dataset like this — it is **not a tool for your graded work**. There is nothing to set up; just type a question. It is the only feature that needs an internet connection, and replies can take up to a minute.

Try reproducing each of these views in ODV yourself — that's the exercise.

## Sharing via Google Drive

Upload **`index.html`** to Drive. To use it, collaborators should **Download** the file
and open it locally (Drive's in-browser preview won't run the interactive scripts).

## Notes on the data

- Sources: `LWFC_2025_RosetteChemistry_Compiled_for_ODV.csv` (16 bottle samples, 8 stations)
  and `LWFC_2025_Day1_2_3_RBR_CTD_profile_data.csv` (~4,400 CTD readings, June 2025).
- `N.D.` and blank cells are treated as **missing** (excluded from plots/stats), not zero.
- The original chemistry CSV lost its delta symbols; isotopes are labelled **δ¹⁵N** / **δ¹³C** (‰).
- CTD: station names were normalised (e.g. `STN 59` → `S59`); above-water rows (depth ≤ 0)
  and unphysical negative PAR values are dropped. Each cast includes down- and up-traces.
- Section colours are interpolated (inverse-distance weighting) — the smooth field
  *between* the sample points is an estimate, not a measurement.
- The satellite basemap (Esri World Imagery) was **pre-fetched once** into `basemap.json`
  and embedded, so the map works with no internet.

## For instructors — rebuilding & the AI demo

To rebuild `index.html` after editing the data or layout:

```bash
python3 generate.py
```

This reads both CSVs (CP1252) plus `app_template.html`, and embeds `plotly.min.js`
and `basemap.json` inline.

To re-fetch the map tiles (needs internet, run rarely):

```bash
python3 fetch_tiles.py    # writes basemap.json
```

**The "Live" tab** streams from a YSI sonde over Web Bluetooth. Web Bluetooth only works in
Chrome/Edge served over `https://` or `localhost` (not a `file://` page from Drive), and the
sonde's BLE profile is proprietary — set the service/characteristic UUIDs and packet decoder in
`YSI_BLE` / `parseYsiPacket()` in `app_template.html`. Until that's configured, the **Demo** mode
streams realistic simulated data so the tab (and its integration into the other panels) is fully usable.

**The "Talk to the Lake" demo** uses a free hosted model via OpenRouter. A temporary,
credit-limited class key placed in a file named `keyfile` (a bare key, or
`OPENROUTER_API_KEY=sk-or-...`) is embedded at build time so students don't configure
anything. Because the key is embedded, anyone who opens the file can read it — so only ever
bundle a disposable, limited key, and rotate it by replacing `keyfile` and re-running
`generate.py`. The model can be changed in one line (`OR_MODEL` in `app_template.html`).

**Pre-loaded Live data:** `generate.py` embeds **every** `LWFC_2026_YSI_sonde*.csv` (KorDSS exports),
concatenated and time-sorted into one running multi-day log, then time-matched to **every**
`LWFC_2026_track*.gpx` **and** `LWFC_2026_track*.kml` (GPX track logs and Google-style KML `gx:Track`
exports are both supported, and all are combined) at build time. **To add a new day or track, just drop
another `LWFC_2026_YSI_sonde_<date>.csv` / `LWFC_2026_track_<date>.{gpx,kml}` in the folder and re-run
`python3 generate.py`** — no code changes. (The in-app **Load GPS (GPX/KML)** button is also additive —
load several partial tracks and they merge.) The track line breaks across gaps >30 min so
overnight returns aren't drawn as straight lines. The GPX is *partial* (recording ends ≈12:08 PM each day),
so afternoon rows past that point aren't geolocated; drop in a fuller GPX and rebuild (or use the in-app
**Load GPS** button) to fill them in. Sonde and GPS clocks are aligned on epoch; if a future export is off,
use the in-app **GPS offset (min)** control.

Files involved: `generate.py`, `fetch_tiles.py`, `app_template.html`, `plotly.min.js`,
`basemap.json`, `LWFC_2026_YSI_sonde_*.csv` (one per day), `LWFC_2026_track_*.gpx`/`.kml` (one or more),
`sonde_stations.csv` (stop centroids overlaid on the map; re-run `generate.py` after editing), and (optionally) `keyfile`.
