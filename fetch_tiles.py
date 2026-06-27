#!/usr/bin/env python3
"""
Pre-fetch satellite basemap tiles covering the Lake Winnipeg sampling area and
bake them into basemap.json so the Station Map works fully offline (no live tile
server needed). Tiles: Esri World Imagery. Run once; basemap.json is committed.

Coordinate convention used downstream (matches Plotly map tab):
  x = (lon+180)/360                     (0..1, linear in longitude)
  y = web-mercator latitude            (0..1, INCREASING SOUTHWARD)
The map plots with the y-axis reversed so north is up.
"""
import csv, io, math, base64, json, urllib.request, sys

CHEM = "LWFC_2025_RosetteChemistry_Compiled_for_ODV.csv"
CTD  = "LWFC_2025_Day1_2_3_RBR_CTD_profile_data.csv"
ZOOM = 11
PAD  = 0.06          # fractional padding around data bbox
URL  = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}")
ATTR = "Imagery: Esri, Maxar, Earthstar Geographics, and the GIS User Community"


def lon2x(lon): return (lon + 180.0) / 360.0
def lat2y(lat):
    s = math.sin(math.radians(lat))
    return 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)
def x2lon(x): return x * 360.0 - 180.0
def y2lat(y):
    n = math.pi - 2 * math.pi * y
    return math.degrees(math.atan(math.sinh(n)))


def collect_coords():
    lats, lons = [], []
    t = open(CHEM, "rb").read().decode("cp1252")
    for r in list(csv.reader(io.StringIO(t)))[1:]:
        try:
            lats.append(float(r[2])); lons.append(float(r[3]))
        except (ValueError, IndexError):
            pass
    t = open(CTD, "rb").read().decode("cp1252")
    for r in list(csv.reader(io.StringIO(t)))[1:]:
        try:
            la, lo = float(r[8]), float(r[9])
            if lo < 0 and 49 < la < 52:
                lats.append(la); lons.append(lo)
        except (ValueError, IndexError):
            pass
    return lats, lons


def main():
    lats, lons = collect_coords()
    la0, la1 = min(lats), max(lats)
    lo0, lo1 = min(lons), max(lons)
    dla, dlo = (la1 - la0) * PAD, (lo1 - lo0) * PAD
    la0, la1 = la0 - dla, la1 + dla
    lo0, lo1 = lo0 - dlo, lo1 + dlo

    n = 2 ** ZOOM
    tx0 = int(lon2x(lo0) * n); tx1 = int(lon2x(lo1) * n)
    ty0 = int(lat2y(la1) * n); ty1 = int(lat2y(la0) * n)   # la1=north=small y
    txs = range(tx0, tx1 + 1)
    tys = range(ty0, ty1 + 1)
    total = len(txs) * len(tys)
    print(f"bbox lat[{la0:.3f},{la1:.3f}] lon[{lo0:.3f},{lo1:.3f}]  "
          f"zoom {ZOOM}: {len(txs)}x{len(tys)} = {total} tiles")

    tiles = []
    for ty in tys:
        for tx in txs:
            url = URL.format(z=ZOOM, x=tx, y=ty)
            req = urllib.request.Request(url, headers={"User-Agent": "LWFC-edu/1.0"})
            try:
                img = urllib.request.urlopen(req, timeout=30).read()
            except Exception as e:
                print(f"  ! tile {tx},{ty} failed: {e}", file=sys.stderr); continue
            b64 = base64.b64encode(img).decode("ascii")
            tiles.append({
                "x0": tx / n, "x1": (tx + 1) / n,     # left, right (lon dir)
                "y0": ty / n, "y1": (ty + 1) / n,     # top(north), bottom(south)
                "uri": "data:image/jpeg;base64," + b64,
            })
            print(f"  + {tx},{ty} ({len(img)//1024} KB)")

    # nice graticule tick suggestions
    def ticks(lo, hi, step):
        out, v = [], math.ceil(lo / step) * step
        while v <= hi + 1e-9:
            out.append(round(v, 4)); v += step
        return out
    lon_ticks = ticks(lo0, lo1, 0.1)
    lat_ticks = ticks(la0, la1, 0.1)

    basemap = {
        "tiles": tiles,
        "attribution": ATTR,
        "xrange": [lon2x(lo0), lon2x(lo1)],
        "yrange": [lat2y(la0), lat2y(la1)],   # [south(big), north(small)]
        "lonTicks": [{"v": lon2x(l), "t": f"{abs(l):.2f}°W"} for l in lon_ticks],
        "latTicks": [{"v": lat2y(l), "t": f"{l:.2f}°N"} for l in lat_ticks],
    }
    with open("basemap.json", "w") as f:
        json.dump(basemap, f)
    kb = len(json.dumps(basemap)) // 1024
    print(f"Wrote basemap.json: {len(tiles)} tiles, ~{kb} KB (base64)")


if __name__ == "__main__":
    main()
