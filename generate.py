#!/usr/bin/env python3
"""
Build a self-contained HTML data explorer for the 2025 Lake Winnipeg Field Course
(LWFC) rosette chemistry data collected aboard the MV NAMAO.

Reads the CP1252-encoded ODV CSV, cleans it, and writes a single index.html with
the data and the Plotly library embedded inline so it works fully offline and can
be shared via Google Drive as one file.
"""
import csv
import json
import io
import math
import os

SRC = "LWFC_2025_RosetteChemistry_Compiled_for_ODV.csv"
PLOTLY = "plotly.min.js"
OUT = "index.html"
# Set False for public builds (e.g. GitHub Pages): hides the "Talk to the Lake"
# chat tab and embeds NO API key. Flip to True (and provide keyfile) to re-enable.
CHAT_ENABLED = False

# (csv column index, key, short label, long label w/ units, group)
# Units use proper unicode. The source file lost the delta (?) on isotopes.
COLUMNS = [
    (0,  "date",   "Date",     "Date",                        "meta"),
    (1,  "station","Station",  "Station",                     "meta"),
    (2,  "lat",    "Latitude", "Latitude (°N)",          "position"),
    (3,  "lon",    "Longitude","Longitude (°E)",         "position"),
    (4,  "depth",  "Depth",    "Depth (m)",                   "position"),
    (5,  "chla",   "Chl a",    "Chlorophyll a (µg/L)",   "biology"),
    (6,  "po4",    "PO₄", "Phosphate PO₄ (µmol/L)", "nutrients"),
    (7,  "si",     "Si",       "Silicate Si (µmol/L)",   "nutrients"),
    (8,  "no2",    "NO₂", "Nitrite NO₂ (µmol/L)",   "nutrients"),
    (9,  "no3",    "NO₃", "Nitrate NO₃ (µmol/L)",   "nutrients"),
    (10, "d15n",   "δ¹⁵N", "δ¹⁵N (‰)", "isotopes"),
    (11, "n_ug",   "N",        "Particulate N (µg)",     "isotopes"),
    (12, "d13c",   "δ¹³C", "δ¹³C (‰)", "isotopes"),
    (13, "c_ug",   "C",        "Particulate C (µg)",     "isotopes"),
    (14, "cdom",   "CDOM a440","CDOM a(440) (m⁻¹)",  "optics"),
    (15, "ta",     "TA",       "Total Alkalinity (µmol/kg)", "carbonate"),
    (16, "dic",    "DIC",      "Dissolved Inorg. C (µmol/kg)", "carbonate"),
    (17, "ph1",    "pH [1]",   "pH [1]",                      "carbonate"),
    (18, "ph2",    "pH [2]",   "pH [2]",                      "carbonate"),
    (19, "cl",     "Cl⁻", "Chloride Cl⁻ (µmol/L)",  "ions"),
    (20, "so4",    "SO₄²⁻", "Sulfate SO₄²⁻ (µmol/L)", "ions"),
    (21, "ca",     "Ca²⁺", "Calcium Ca²⁺ (µmol/L)", "ions"),
    (22, "mg",     "Mg²⁺", "Magnesium Mg²⁺ (µmol/L)", "ions"),
    (23, "na",     "Na⁺", "Sodium Na⁺ (µmol/L)",    "ions"),
    (24, "k",      "K⁺",  "Potassium K⁺ (µmol/L)",  "ions"),
    (25, "ca_na",  "Ca/Na",    "Ca/Na ratio",                 "ratios"),
    (26, "mg_na",  "Mg/Na",    "Mg/Na ratio",                 "ratios"),
]

MISSING = {"", "n.d.", "nd", "na", "n/a", "nan", "-"}

# ---- CTD (RBR) high-resolution profile data --------------------------------
CTD_SRC = "LWFC_2025_Day1_2_3_RBR_CTD_profile_data.csv"

# (csv col index, key, short label, long label w/ units, round-digits)
CTD_COLUMNS = [
    (11, "temp",   "Temp",     "Temperature (°C)",            3),
    (21, "sal",    "Salinity", "Salinity (PSU)",                   3),
    (16, "do_conc","DO",       "Dissolved O₂ (µmol/L)",  1),
    (24, "do_sat", "DO sat",   "O₂ saturation (%)",       1),
    (14, "chla",   "Chl a",    "Chlorophyll a (µg/L)",   2),
    (13, "cdom",   "CDOM",     "CDOM (ppb)",                  1),
    (18, "turb",   "Turb",     "Turbidity (NTU)",             1),
    (17, "par",    "PAR",      "PAR (µmol/m²/s)",     0),
    (25, "dens",   "σ",   "Density anomaly (kg/m³)", 2),
    (10, "cond",   "Cond",     "Conductivity (mS/cm)",        3),
    (22, "sos",    "Sound",    "Speed of sound (m/s)",        1),
]


def clean_station(raw):
    s = (raw or "").strip()
    if s.startswith("Station #1"):
        return "S1 Red River"
    if s == "Station #2":
        return "S2"
    if s == "STN 59":
        return "S59"
    if s == "STN59_3":
        return "S59 (Day 3)"
    if s == "STN_7":
        return "S7"
    if s.startswith("Transect: Stop"):
        return "Transect"
    if s == "Station" or s == "":
        return None
    return s


def parse_ctd():
    import glob as _glob
    files = sorted(_glob.glob("LWFC_*_RBR_CTD_profile_data.csv"))  # all years, same column layout
    stations = []
    st_index = {}
    cols = {k: [] for (_i, k, *_r) in CTD_COLUMNS}
    cols["st"] = []
    cols["depth"] = []
    cols["date"] = []
    cols["lat"] = []
    cols["lon"] = []
    for path in files:
        raw = open(path, "rb").read().decode("cp1252")
        rows = list(csv.reader(io.StringIO(raw)))[1:]
        for r in rows:
            if not any(c.strip() for c in r):
                continue
            st = clean_station(r[0])
            if st is None:
                continue
            depth = clean_num(r[20])
            if depth is None or depth <= 0.05:        # drop above-water samples
                continue
            lat, lon = clean_num(r[8]), clean_num(r[9])
            if lat is None or lon is None:
                continue
            if st not in st_index:
                st_index[st] = len(stations)
                stations.append(st)
            cols["st"].append(st_index[st])
            cols["depth"].append(round(depth, 2))
            cols["lat"].append(round(lat, 5))
            cols["lon"].append(round(lon, 5))
            try:
                cols["date"].append(f"{int(r[2]):04d}-{int(r[3]):02d}-{int(r[4]):02d}")
            except (ValueError, IndexError):
                cols["date"].append("")
            for idx, key, _s, _l, dig in CTD_COLUMNS:
                v = clean_num(r[idx] if idx < len(r) else "")
                if key == "par" and v is not None and v < 0:   # unphysical sensor noise
                    v = None
                cols[key].append(round(v, dig) if v is not None else None)
    ctd_vars = [{"key": k, "short": s, "label": lbl}
                for (_i, k, s, lbl, _d) in CTD_COLUMNS]
    return cols, ctd_vars, stations


def clean_num(s):
    s = (s or "").strip()
    if s.lower() in MISSING:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ---- pre-load real YSI sonde data (CSV) + GPS track (GPX), merged by time ----
import glob
def live_csvs():
    return sorted(glob.glob("LWFC_2026_YSI_sonde*.csv"))
def live_gpx():
    return sorted(glob.glob("LWFC_2026_track*.gpx") + glob.glob("LWFC_2026_track*.kml"))
LIVE_KEYS = ["temp", "spcond", "sal", "odo_sat", "odo", "ph", "orp", "turb", "chl", "fdom"]
LIVE_ROUND = {"t": 0, "lat": 6, "lon": 6, "depth": 3, "temp": 3, "spcond": 1,
              "sal": 3, "odo_sat": 1, "odo": 2, "ph": 2, "orp": 1, "turb": 1,
              "chl": 2, "fdom": 2}


def _num(r, i):
    if i is None or i < 0 or i >= len(r):
        return None
    try:
        return float(r[i])
    except ValueError:
        return None


def _gpx_track(path):
    import re
    import datetime as dt
    txt = open(path, "rb").read().decode("utf-8", "ignore")
    pts = []

    def epoch(s):
        return int(dt.datetime.strptime(s.strip(), "%Y-%m-%dT%H:%M:%SZ")
                   .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)

    if "<gx:coord>" in txt:                                   # KML gx:Track (when + gx:coord pairs)
        whens = re.findall(r"<when>(.*?)</when>", txt)
        coords = re.findall(r"<gx:coord>(.*?)</gx:coord>", txt)
        for w, c in zip(whens, coords):
            try:
                lon, lat = c.split()[0], c.split()[1]
                pts.append((epoch(w), float(lat), float(lon)))
            except (ValueError, IndexError):
                continue
    else:                                                     # GPX trkpt / rtept
        for m in re.finditer(r"<(?:trkpt|rtept)[^>]*lat=\"([^\"]+)\"[^>]*lon=\"([^\"]+)\"[^>]*>(.*?)</(?:trkpt|rtept)>",
                             txt, re.S):
            tm = re.search(r"<time>(.*?)</time>", m.group(3))
            if not tm:
                continue
            try:
                pts.append((epoch(tm.group(1)), float(m.group(1)), float(m.group(2))))
            except ValueError:
                continue
    pts.sort()
    return pts


def _merge_gps(L, g, tol=120000):
    import bisect
    ts = [p[0] for p in g]
    for i, t in enumerate(L["t"]):
        j = bisect.bisect_left(ts, t)
        lat = lon = None
        if j <= 0:
            if ts[0] - t <= tol:
                lat, lon = g[0][1], g[0][2]
        elif j >= len(g):
            if t - ts[-1] <= tol:
                lat, lon = g[-1][1], g[-1][2]
        else:
            a, b = g[j - 1], g[j]
            if (t - a[0]) <= tol or (b[0] - t) <= tol:
                f = (t - a[0]) / ((b[0] - a[0]) or 1)
                lat = a[1] + (b[1] - a[1]) * f
                lon = a[2] + (b[2] - a[2]) * f
        L["lat"][i], L["lon"][i] = lat, lon


def parse_stations():
    path = "sonde_stations.csv"
    if not os.path.exists(path):
        return []
    out = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        try:
            lat, lon = float(r["Latitude"]), float(r["Longitude"])
        except (ValueError, KeyError):
            continue
        try:
            dur = float(r["Duration_min"])
        except (ValueError, KeyError, TypeError):
            dur = 0.0
        out.append({"name": (r.get("Station") or "").strip(), "type": (r.get("Type") or "").strip(),
                    "lat": lat, "lon": lon, "date": (r.get("Date") or "").strip(),
                    "start": (r.get("Start") or "").strip(), "end": (r.get("End") or "").strip(), "dur": dur})
    return out


def parse_live():
    import datetime as dt
    files = live_csvs()
    if not files:
        return {}
    L = {k: [] for k in ["t", "lat", "lon", "depth"] + LIVE_KEYS}
    for path in files:                                  # concatenate all daily exports
        rows = list(csv.reader(io.StringIO(open(path, "rb").read().decode("iso-8859-1"))))
        if not rows:
            continue
        hdr = [h.strip().lower() for h in rows[0]]

        def has(*subs):
            for i, h in enumerate(hdr):
                if all(s in h for s in subs):
                    return i
            return -1

        cmap = {"temp": has("temp"), "spcond": has("sp cond"), "sal": has("sal"),
                "odo_sat": has("do (", "% sat"), "odo": has("do (", "mg/l"),
                "ph": has("ph ( ph"), "orp": has("orp"), "turb": has("turb"),
                "fdom": has("fdom", "qsu") if has("fdom", "qsu") >= 0 else has("fdom"),
                "chl": has("chl"), "depth": has("depth")}
        di, ti = has("date"), has("time")
        for r in rows[1:]:
            if not r or not r[0].strip():
                continue
            try:
                d = dt.datetime.strptime(r[di].strip() + " " + r[ti].strip(), "%m/%d/%Y %I:%M:%S %p")
                t = int(d.timestamp() * 1000)
            except (ValueError, IndexError):
                continue
            L["t"].append(t)
            L["depth"].append(_num(r, cmap["depth"]))
            for k in LIVE_KEYS:
                L[k].append(_num(r, cmap[k]))
            L["lat"].append(None)
            L["lon"].append(None)
    # time-sort the combined multi-day log
    order = sorted(range(len(L["t"])), key=lambda i: L["t"][i])
    for k in list(L):
        L[k] = [L[k][i] for i in order]
    gpx_files = live_gpx()
    if gpx_files:
        g = []
        for gp in gpx_files:
            g.extend(_gpx_track(gp))
        g.sort()
        if g:
            _merge_gps(L, g)
    for k, arr in L.items():
        dgt = LIVE_ROUND.get(k, 3)
        L[k] = [(int(v) if dgt == 0 else round(v, dgt)) if v is not None else None for v in arr]
    return L


def main():
    with open(SRC, "rb") as f:
        raw = f.read().decode("cp1252")
    rows = list(csv.reader(io.StringIO(raw)))
    header, body = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]

    records = []
    for r in body:
        rec = {}
        for idx, key, *_rest in COLUMNS:
            val = r[idx] if idx < len(r) else ""
            if key in ("date", "station"):
                rec[key] = val.strip()
            else:
                rec[key] = clean_num(val)
        records.append(rec)

    variables = [
        {"key": k, "short": s, "label": lbl, "group": g}
        for (_i, k, s, lbl, g) in COLUMNS
    ]

    data_json = json.dumps(records, ensure_ascii=False)
    vars_json = json.dumps(variables, ensure_ascii=False)

    ctd_cols, ctd_vars, ctd_stations = parse_ctd()
    ctd_json = json.dumps(ctd_cols, ensure_ascii=False)
    ctdvars_json = json.dumps(ctd_vars, ensure_ascii=False)
    ctdst_json = json.dumps(ctd_stations, ensure_ascii=False)

    with open("basemap.json", "r", encoding="utf-8") as f:
        basemap_json = f.read()

    # optional bundled class key (time/credit-limited) from `keyfile`.
    # Accepts a bare key or an ENV-style line like OPENROUTER_API_KEY=sk-or-...
    # Never embedded when the chat is disabled.
    bundled_key = ""
    if CHAT_ENABLED and os.path.exists("keyfile"):
        raw_key = open("keyfile", "r", encoding="utf-8").read().strip()
        if raw_key:
            bundled_key = raw_key.split("=", 1)[1].strip() if "=" in raw_key else raw_key
            bundled_key = bundled_key.strip().strip('"').strip("'")

    with open(PLOTLY, "r", encoding="utf-8") as f:
        plotly_js = f.read()

    with open("app_template.html", "r", encoding="utf-8") as f:
        html = f.read()

    html = html.replace("/*__PLOTLY__*/", plotly_js)
    html = html.replace("/*__DATA__*/", data_json)
    html = html.replace("/*__VARS__*/", vars_json)
    html = html.replace("/*__CTD__*/", ctd_json)
    html = html.replace("/*__CTDVARS__*/", ctdvars_json)
    html = html.replace("/*__CTDSTATIONS__*/", ctdst_json)
    html = html.replace("/*__BASEMAP__*/", basemap_json)
    html = html.replace("/*__ORKEY__*/", json.dumps(bundled_key))
    html = html.replace("/*__CHAT__*/", "true" if CHAT_ENABLED else "false")

    prelive = parse_live()
    html = html.replace("/*__PRELIVE__*/", json.dumps(prelive))
    stations = parse_stations()
    html = html.replace("/*__STATIONS__*/", json.dumps(stations, ensure_ascii=False))
    npl = len(prelive.get("t", []))
    ngps = sum(1 for v in prelive.get("lat", []) if v is not None)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote {OUT}: {len(records)} bottle records, {len(variables)} vars; "
          f"{len(ctd_cols['depth'])} CTD points, {len(ctd_stations)} CTD stations; "
          f"{npl} pre-loaded live rows ({ngps} geolocated); {len(stations)} sonde stops")


if __name__ == "__main__":
    main()
