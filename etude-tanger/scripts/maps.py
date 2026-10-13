# -*- coding: utf-8 -*-
"""Cartes analytiques de Tanger à partir de données réelles (OSM/Overture, ESA WorldCover, Copernicus DEM, Sentinel-2)."""
import sys, json, glob, os
import numpy as np, pandas as pd, geopandas as gpd, rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patheffects as pe
from matplotlib.colors import ListedColormap, LightSource, LinearSegmentedColormap
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch, Polygon as MPoly
from matplotlib.collections import LineCollection
from pyproj import Transformer
from shapely.geometry import Point, LineString, box
from shapely.ops import unary_union
from scipy import ndimage as ndi
from scipy.stats import gaussian_kde

for f in glob.glob(os.path.expanduser("~/.fonts/barlow*.ttf")):
    fm.fontManager.addfont(f)
CF = "Barlow Condensed"
plt.rcParams["font.family"] = CF

OUT = "maps"
os.makedirs(OUT, exist_ok=True)
TO = Transformer.from_crs(4326, 32630, always_xy=True)
def U(lon, lat):
    return TO.transform(lon, lat)

# palette
PAPER = "#E9E7E2"; LAND = "#EDEAE3"; SEA = "#A9C3CC"; SEA_D = "#8FB0BC"
BUILT = "#DFA283"; BUILT_N = "#CFC6B9"; TREE = "#A3B78F"; SHRUB = "#C8CFAE"; GRASS = "#DAD9C2"; CROP = "#E5DEC8"
BARE = "#E8E1D2"; WET = "#B4CABE"; INK = "#1E1E1E"; RED = "#C8462B"; ORANGE = "#D9824F"; BLUE = "#1F3A5F"
GOLD = "#D9A441"; MUTED = "#6E6A64"; GREEN = "#5E7F4F"

# ------------------------------------------------------------------ data
WC = rasterio.open("u_wc10.tif"); W = WC.read(1); WT = WC.transform
DEMR = rasterio.open("u_dem20.tif"); DEM = DEMR.read(1); DT = DEMR.transform
SEA_M = np.load("a_sea.npy")
def extent(tr, shape):
    return (tr.c, tr.c + tr.a * shape[1], tr.f + tr.e * shape[0], tr.f)
WEXT = extent(WT, W.shape); DEXT = extent(DT, DEM.shape)

SEG = gpd.read_parquet("u_seg_region.parquet")
BLD = gpd.read_parquet("u_bld_city.parquet")
LU = gpd.read_parquet("u_lu_region.parquet")
INF = gpd.read_parquet("u_infra_region.parquet")
ARR = gpd.read_parquet("a_arr.parquet")
PL = gpd.read_parquet("a_places.parquet")
DIV = gpd.read_parquet("u_div_region.parquet")
CITY = unary_union(ARR.geometry.values)
ROADS = SEG[SEG.subtype.eq("road")]
RAIL = SEG[SEG.subtype.eq("rail")]
STOPS = INF[INF["class"].eq("bus_stop")]

ls = LightSource(azdeg=315, altdeg=40)
HS = ls.hillshade(np.where(DEM < -5, 0, DEM), vert_exag=2.2, dx=20, dy=20)


def fig_ax(bounds, w_px, h_px, dpi=200, bg=PAPER):
    fig = plt.figure(figsize=(w_px / dpi, h_px / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(bg); fig.patch.set_facecolor(bg)
    x0, y0, x1, y1 = bounds
    # keep aspect: expand to frame ratio
    r = w_px / h_px; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; ww, hh = x1 - x0, y1 - y0
    if ww / hh > r:
        hh = ww / r
    else:
        ww = hh * r
    ax.set_xlim(cx - ww / 2, cx + ww / 2); ax.set_ylim(cy - hh / 2, cy + hh / 2)
    ax.set_axis_off()
    return fig, ax


def bnd_ll(lon0, lat0, lon1, lat1):
    a = U(lon0, lat0); b = U(lon1, lat1)
    return (a[0], a[1], b[0], b[1])


def landcover(ax, mode="full", alpha=1.0):
    if mode == "full":
        cols = {10: TREE, 20: SHRUB, 30: GRASS, 40: CROP, 50: BUILT, 60: BARE, 80: SEA, 90: WET, 95: WET, 100: GRASS}
    elif mode == "neutral":
        cols = {10: "#CDD5C1", 20: "#DCDDCB", 30: "#E3E1D3", 40: "#E7E2D5", 50: BUILT_N, 60: "#E8E3D8", 80: SEA, 90: "#D2DCD3", 95: "#D2DCD3", 100: "#E3E1D3"}
    elif mode == "dark":
        cols = {10: "#2F3B2E", 20: "#34392F", 30: "#383B33", 40: "#3A3A34", 50: "#7A4E3A", 60: "#3B3A36", 80: "#1C3440", 90: "#2E3B39", 95: "#2E3B39", 100: "#383B33"}
    lut = np.zeros((256, 4))
    base = LAND if mode != "dark" else "#363632"
    for i in range(256):
        lut[i] = matplotlib.colors.to_rgba(cols.get(i, base))
    img = lut[W]
    sea = SEA if mode != "dark" else "#1C3440"
    img[SEA_M] = matplotlib.colors.to_rgba(sea)
    img[(W == 80) & ~SEA_M] = matplotlib.colors.to_rgba(SEA_D if mode != "dark" else "#24485A")
    ax.imshow(img, extent=WEXT, zorder=1, interpolation="nearest", alpha=alpha)


def hillshade(ax, strength=0.35, dark=False):
    hs = HS.copy()
    if dark:
        rgba = np.zeros(hs.shape + (4,)); rgba[..., :3] = 0; rgba[..., 3] = (1 - hs) * strength
        ax.imshow(rgba, extent=DEXT, zorder=2)
        rgba2 = np.zeros(hs.shape + (4,)); rgba2[..., :3] = 1; rgba2[..., 3] = np.clip(hs - 0.6, 0, 1) * strength * 0.6
        ax.imshow(rgba2, extent=DEXT, zorder=2)
    else:
        rgba = np.zeros(hs.shape + (4,)); rgba[..., :3] = 0.25; rgba[..., 3] = np.clip(0.75 - hs, 0, 1) * strength
        ax.imshow(rgba, extent=DEXT, zorder=2)


ROAD_STYLE = {"motorway": (RED, 2.0, 10), "trunk": (RED, 1.6, 10), "primary": (ORANGE, 1.0, 9), "secondary": ("#B7A898", 0.7, 8),
              "tertiary": ("#C9BFB2", 0.45, 7), "residential": ("#D3CBC0", 0.22, 6), "unclassified": ("#D3CBC0", 0.22, 6),
              "living_street": ("#D3CBC0", 0.2, 6), "service": ("#D8D1C7", 0.15, 6)}


def roads(ax, minor=True, scale=1.0, color_override=None, classes=None, alpha=1):
    for cl, (c, lw, z) in sorted(ROAD_STYLE.items(), key=lambda kv: kv[1][2]):
        if classes and cl not in classes:
            continue
        if not minor and cl in ("residential", "unclassified", "living_street", "service", "tertiary"):
            continue
        g = ROADS[ROADS["class"].eq(cl)]
        if len(g):
            g.plot(ax=ax, color=color_override.get(cl, c) if color_override else c, linewidth=lw * scale, zorder=z, alpha=alpha)


def rail(ax, color=INK, lw=0.9, z=11):
    RAIL.plot(ax=ax, color="white", linewidth=lw * 1.8, zorder=z, alpha=0.8)
    RAIL.plot(ax=ax, color=color, linewidth=lw, zorder=z + 0.1, linestyle=(0, (4, 3)))


def boundaries(ax, color=INK, arr=True, lw=1.4):
    gpd.GeoSeries([CITY]).boundary.plot(ax=ax, color=color, linewidth=lw, zorder=20)
    if arr:
        ARR.boundary.plot(ax=ax, color=color, linewidth=lw * 0.45, linestyle=(0, (5, 3)), zorder=20)


def txt(ax, x, y, s, size=9, color=INK, w="semibold", ha="center", va="center", halo=PAPER, spacing=False, z=40, style="normal", rot=0):
    if spacing:
        s = " ".join(list(s.upper())).replace("   ", "  ")
    t = ax.text(x, y, s, fontsize=size, color=color, fontweight=w, ha=ha, va=va, zorder=z, fontstyle=style, rotation=rot, family=CF)
    if halo:
        t.set_path_effects([pe.withStroke(linewidth=2.6, foreground=halo, alpha=0.9)])
    return t


def lbl(ax, lon, lat, s, **k):
    x, y = U(lon, lat); return txt(ax, x, y, s, **k)


def scalebar(ax, km=2, pos=(0.04, 0.05), dark=False, nseg=2):
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    sx = x0 + (x1 - x0) * pos[0]; sy = y0 + (y1 - y0) * pos[1]
    seg = km * 1000 / nseg; h = (y1 - y0) * 0.006
    fg = "white" if dark else INK
    for i in range(nseg):
        ax.add_patch(Rectangle((sx + i * seg, sy), seg, h, facecolor=fg if i % 2 == 0 else (PAPER if not dark else "#2A2A2A"), edgecolor=fg, lw=0.6, zorder=50))
    for i, v in enumerate([0, km / 2 if nseg == 2 else None, km]):
        if v is None:
            continue
        xx = sx + (km * 1000) * (v / km)
        txt(ax, xx, sy + h * 3.2, (f"{v:g}" + (" km" if v == km else "")), size=7, color=fg, halo=None, w="medium")


def northarrow(ax, pos=(0.955, 0.9), dark=False):
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    x = x0 + (x1 - x0) * pos[0]; y = y0 + (y1 - y0) * pos[1]; h = (y1 - y0) * 0.05
    fg = "white" if dark else INK
    ax.add_patch(MPoly([(x, y + h), (x - h * 0.22, y), (x, y + h * 0.25), (x + h * 0.22, y)], closed=True, facecolor=fg, zorder=50))
    txt(ax, x, y - h * 0.35, "N", size=8, color=fg, halo=None, w="bold")


def source(ax, s, dark=False):
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    txt(ax, x1 - (x1 - x0) * 0.01, y0 + (y1 - y0) * 0.015, s, size=5.5, color=("#BBBBBB" if dark else MUTED), halo=None, ha="right", va="bottom", w="regular")


def marker(ax, lon, lat, n, color=RED, r=None, fs=8, ring=False, dark=False):
    x, y = U(lon, lat)
    x0, x1 = ax.get_xlim(); r = r or (x1 - x0) * 0.009
    if ring:
        ax.add_patch(Circle((x, y), r * 2.6, facecolor="none", edgecolor=color, lw=0.8, alpha=0.7, zorder=44))
        ax.add_patch(Circle((x, y), r * 1.8, facecolor=color, edgecolor="none", alpha=0.18, zorder=44))
    ax.add_patch(Circle((x, y), r, facecolor=color, edgecolor="white", lw=1.0, zorder=45))
    txt(ax, x, y, str(n), size=fs, color="white", halo=None, w="bold", z=46)
    return x, y


def save(fig, name):
    fig.savefig(f"{OUT}/{name}.png", dpi=fig.dpi, facecolor=fig.get_facecolor())
    plt.close(fig); print("saved", name)


CITY_B = bnd_ll(-5.965, 35.695, -5.715, 35.825)

# ================================================================== MAPS
def m_territoire():
    b = bnd_ll(-6.06, 35.55, -5.40, 35.93)
    fig, ax = fig_ax(b, 2400, 1700, bg="#2A2C2B")
    landcover(ax, "dark"); hillshade(ax, 0.55, dark=True)
    ROADS[ROADS["class"].isin(["secondary", "tertiary"])].plot(ax=ax, color="#5A5A55", lw=0.35, zorder=6)
    ROADS[ROADS["class"].eq("primary")].plot(ax=ax, color="#B8865E", lw=0.8, zorder=7)
    ROADS[ROADS["class"].isin(["motorway", "trunk"])].plot(ax=ax, color="#E07A3F", lw=1.9, zorder=8)
    RAIL.plot(ax=ax, color="#EDEDED", lw=0.9, zorder=9, linestyle=(0, (4, 3)))
    gpd.GeoSeries([CITY]).boundary.plot(ax=ax, color="white", lw=1.1, zorder=10)
    poles = [(1, -5.8054, 35.7880, "Port Tanger Ville\n& Tanja Marina Bay", RED), (2, -5.5015, 35.8836, "Port Tanger Med", BLUE), (3, -5.9129, 35.7260, "Aéroport\nIbn Battouta", "#7D8B96"),
             (4, -5.9053, 35.7155, "Zone franche\nde Tanger", BLUE), (5, -5.6868, 35.6916, "Usine Renault\nMelloussa", BLUE), (6, -5.6618, 35.6575, "Tanger\nAutomotive City", BLUE),
             (7, -5.7860, 35.7715, "Gare TGV\nTanger Ville", RED), (8, -5.8581, 35.7412, "Grand stade\nIbn Batouta", RED), (9, -5.9236, 35.7905, "Cap Spartel,\ngrottes d'Hercule", RED),
             (10, -5.7483, 35.8167, "Cap Malabata", RED)]
    off = {1: (900, 1500), 2: (0, -2300), 3: (-2600, -400), 4: (-2600, -1700), 5: (0, 2000), 6: (0, -2000), 7: (1900, -600), 8: (-200, -2100), 9: (0, 1700), 10: (1600, 1400)}
    for n, lon, lat, name, c in poles:
        x, y = marker(ax, lon, lat, n, color=c, fs=8, ring=True)
        dx, dy = off[n]
        txt(ax, x + dx, y + dy, name, size=8.5, color="white", halo="#2A2C2B", w="medium")
    for lon, lat, s in [(-5.83, 35.755, "TANGER"), (-5.37 - 0.0, 35.88, ""), (-5.61, 35.58, "")]:
        if s:
            lbl(ax, lon, lat, s, size=15, color="white", halo="#2A2C2B", spacing=True, w="semibold")
    lbl(ax, -5.62, 35.915, "DÉTROIT DE GIBRALTAR", size=10, color="#7FA3B3", halo=None, spacing=True, style="italic")
    lbl(ax, -6.03, 35.72, "OCÉAN\nATLANTIQUE", size=9, color="#7FA3B3", halo=None, w="medium", style="italic")
    lbl(ax, -5.545, 35.62, "FAHS-ANJRA", size=8, color="#A9A39A", halo=None, spacing=True)
    # distance rings from medina
    cx, cy = U(-5.812, 35.786)
    for km in (10, 20, 30):
        ax.add_patch(Circle((cx, cy), km * 1000, facecolor="none", edgecolor="#8A8A84", lw=0.5, linestyle=(0, (2, 3)), zorder=12))
        txt(ax, cx + km * 1000 * 0.71, cy - km * 1000 * 0.71, f"{km} km", size=7, color="#A9A39A", halo=None)
    scalebar(ax, 10, dark=True); northarrow(ax, dark=True)
    source(ax, "Sources : OpenStreetMap / Overture Maps (2026), ESA WorldCover 2021, Copernicus DEM GLO-30. Cartographie de l'auteur.", dark=True)
    save(fig, "m01_territoire")


def m_arrondissements():
    fig, ax = fig_ax(bnd_ll(-5.955, 35.705, -5.735, 35.815), 2000, 1600)
    landcover(ax, "neutral"); hillshade(ax, 0.3)
    T = pd.read_csv("a_table.csv")
    A = ARR.merge(T[["arr", "growth"]], on="arr")
    cm = LinearSegmentedColormap.from_list("g", ["#E9D9C9", "#DFA283", "#C8462B", "#7E2614"])
    for _, r in A.iterrows():
        v = (r.growth + 0.1) / 0.6
        gpd.GeoSeries([r.geometry]).plot(ax=ax, color=cm(np.clip(v, 0, 1)), alpha=0.55, zorder=3)
    # built mask overlay to keep texture
    roads(ax, minor=True, scale=0.8)
    boundaries(ax, lw=1.6)
    lab = {"Tanger-Médina": (-5.885, 35.778), "Beni Makada": (-5.832, 35.733), "Charf-Souani": (-5.821, 35.7665), "Charf-Mghogha": (-5.764, 35.786)}
    for _, r in A.iterrows():
        lon, lat = lab[r.arr]
        x, y = U(lon, lat)
        txt(ax, x, y + 380, r.arr.upper(), size=10.5, spacing=False, w="bold")
        txt(ax, x, y - 120, f"{r.pop24/1000:.0f} 000 hab.", size=9, w="medium")
        txt(ax, x, y - 520, f"{r.growth*100:+.0f} % (2014-2024)", size=9, w="bold", color=RED if r.growth > 0.3 else INK)
    scalebar(ax, 2); northarrow(ax)
    source(ax, "Population : HCP, RGPH 2014 et 2024 (via citypopulation.de). Limites : OSM / Overture. Cartographie de l'auteur.")
    save(fig, "m02_arrondissements")


def m_occupation():
    fig, ax = fig_ax(CITY_B, 2400, 1700)
    landcover(ax, "full"); hillshade(ax, 0.45)
    roads(ax, minor=True)
    rail(ax)
    boundaries(ax)
    for lon, lat, s in [(-5.812, 35.789, "MÉDINA"), (-5.86, 35.79, "MARSHAN / RMILAT"), (-5.815, 35.752, "BENI MAKADA"), (-5.855, 35.755, "MESNANA"),
                        (-5.905, 35.708, "GZENAYA"), (-5.775, 35.735, "MGHOGHA"), (-5.76, 35.80, "MALABATA"), (-5.93, 35.785, "CAP SPARTEL"), (-5.80, 35.735, "BIR CHIFA")]:
        lbl(ax, lon, lat, s, size=8.5, spacing=True, w="semibold")
    scalebar(ax, 2); northarrow(ax)
    source(ax, "Sources : ESA WorldCover 2021 (10 m), OpenStreetMap / Overture Maps (2026), Copernicus DEM. Cartographie de l'auteur.")
    save(fig, "m03_occupation")


def kde_layer(ax, pts, cmap, bounds, bw=0.18, levels=8, alpha=0.85, z=8):
    x0, y0, x1, y1 = bounds
    xx, yy = np.mgrid[x0:x1:300j, y0:y1:220j]
    k = gaussian_kde(np.vstack([pts.x, pts.y]), bw_method=bw)
    zz = k(np.vstack([xx.ravel(), yy.ravel()])).reshape(xx.shape)
    zz = zz / zz.max()
    lv = np.linspace(0.06, 1, levels)
    ax.contourf(xx, yy, zz, levels=lv, cmap=cmap, alpha=alpha, zorder=z, extend="max")
    ax.contour(xx, yy, zz, levels=lv, colors="white", linewidths=0.25, alpha=0.6, zorder=z + 0.1)


def m_deux_villes():
    b = bnd_ll(-5.945, 35.715, -5.74, 35.81)
    inc = PL[PL.within(CITY.buffer(500))]
    for name, fams, cmap, col in [("m04a_vitrine", ["lodging", "site", "beach"], LinearSegmentedColormap.from_list("t", ["#F3D6C8", "#DF8E6B", "#C8462B", "#7E2614"]), RED),
                                  ("m04b_vecue", ["school", "health"], LinearSegmentedColormap.from_list("b", ["#D6DFEA", "#8EA6C2", "#3E5F86", "#1F3A5F"]), BLUE)]:
        fig, ax = fig_ax(b, 1600, 1180)
        landcover(ax, "neutral"); hillshade(ax, 0.25)
        roads(ax, minor=True, scale=0.6, classes=["motorway", "trunk", "primary", "secondary", "tertiary", "residential"])
        pts = inc[inc.fam.isin(fams)].geometry
        kde_layer(ax, pts, cmap, ax.get_xlim()[:1] + ax.get_ylim()[:1] + ax.get_xlim()[1:] + ax.get_ylim()[1:])
        ax.scatter(pts.x, pts.y, s=4, color=col, edgecolor="white", linewidth=0.3, zorder=12)
        boundaries(ax, lw=1.2)
        for lon, lat, s in [(-5.812, 35.791, "MÉDINA"), (-5.815, 35.750, "BENI MAKADA"), (-5.775, 35.735, "MGHOGHA"), (-5.90, 35.725, "GZENAYA")]:
            lbl(ax, lon, lat, s, size=8, spacing=True)
        scalebar(ax, 2); northarrow(ax)
        save(fig, name)


def m_littoral():
    """bande de 1 km et hébergements"""
    fig, ax = fig_ax(bnd_ll(-5.945, 35.73, -5.735, 35.825), 2400, 1300)
    landcover(ax, "neutral"); hillshade(ax, 0.3)
    dist = ndi.distance_transform_edt(~SEA_M) * 10
    band = (dist > 0) & (dist <= 1000)
    rgba = np.zeros(W.shape + (4,)); rgba[band] = matplotlib.colors.to_rgba(RED, 0.10)
    ax.imshow(rgba, extent=WEXT, zorder=3)
    cs = ax.contour(np.flipud(dist) if False else dist, levels=[1000], extent=(WEXT[0], WEXT[1], WEXT[3], WEXT[2]), colors=RED, linewidths=0.9, linestyles="--", zorder=4)
    bm = (W == 50)
    rgba2 = np.zeros(W.shape + (4,)); rgba2[bm & band] = matplotlib.colors.to_rgba("#B7553A", 0.9); rgba2[bm & ~band] = matplotlib.colors.to_rgba("#9A9184", 0.55)
    ax.imshow(rgba2, extent=WEXT, zorder=4, interpolation="nearest")
    roads(ax, minor=False, scale=0.8)
    lod = PL[PL.fam.eq("lodging") & PL.within(CITY.buffer(800))].geometry
    ax.scatter(lod.x, lod.y, s=9, color=RED, edgecolor="white", linewidth=0.5, zorder=14)
    sch = PL[PL.fam.isin(["school", "health"]) & PL.within(CITY.buffer(800))].geometry
    ax.scatter(sch.x, sch.y, s=6, marker="s", color=BLUE, edgecolor="white", linewidth=0.3, zorder=13)
    boundaries(ax, lw=1.1)
    for lon, lat, s in [(-5.812, 35.7905, "MÉDINA"), (-5.765, 35.795, "MALABATA"), (-5.925, 35.788, "CAP SPARTEL"), (-5.815, 35.750, "BENI MAKADA"), (-5.86, 35.80, "RMILAT")]:
        lbl(ax, lon, lat, s, size=8, spacing=True)
    x, y = U(-5.80, 35.808)
    txt(ax, x, y, "bande littorale de 1 km", size=9, color=RED, w="semibold", style="italic")
    scalebar(ax, 2, pos=(0.04, 0.06)); northarrow(ax)
    source(ax, "Sources : ESA WorldCover 2021, OpenStreetMap / Overture Places (2026). Calculs et cartographie de l'auteur.")
    save(fig, "m05_littoral")


def m_mobilite():
    fig, ax = fig_ax(bnd_ll(-5.955, 35.70, -5.735, 35.815), 2400, 1700)
    landcover(ax, "neutral"); hillshade(ax, 0.3)
    stopbuf = unary_union(STOPS.buffer(300).values)
    import rasterio.features as rf
    served = rf.geometry_mask([stopbuf], W.shape, WT, invert=True)
    bm = (W == 50)
    cm_ = rf.geometry_mask([CITY.buffer(1500)], W.shape, WT, invert=True)
    rgba = np.zeros(W.shape + (4,))
    rgba[bm & served & cm_] = matplotlib.colors.to_rgba("#A9B6C6", 0.9)
    rgba[bm & ~served & cm_] = matplotlib.colors.to_rgba(RED, 0.95)
    ax.imshow(rgba, extent=WEXT, zorder=4, interpolation="nearest")
    roads(ax, minor=False, scale=1.0)
    ROADS[ROADS["class"].isin(["tertiary", "residential"])].plot(ax=ax, color="#D3CBC0", lw=0.2, zorder=5)
    rail(ax, lw=1.4)
    ax.scatter(STOPS.geometry.x, STOPS.geometry.y, s=1.5, color=BLUE, zorder=12, linewidths=0)
    boundaries(ax, lw=1.1)
    x, y = marker(ax, -5.7860, 35.7715, "", color=RED, fs=6)
    txt(ax, x + 300, y - 450, "Gare TGV Tanger Ville", size=8.5, color=RED, ha="left")
    for lon, lat, s in [(-5.812, 35.7905, "MÉDINA"), (-5.815, 35.750, "BENI MAKADA"), (-5.775, 35.733, "MGHOGHA"), (-5.905, 35.708, "GZENAYA"), (-5.855, 35.758, "MESNANA")]:
        lbl(ax, lon, lat, s, size=8.5, spacing=True)
    scalebar(ax, 2); northarrow(ax)
    source(ax, "Sources : arrêts de bus OpenStreetMap / Overture (2026), ESA WorldCover 2021. Rayon de 300 m à vol d'oiseau. Calculs de l'auteur.")
    save(fig, "m06_mobilite")


def m_medina():
    b = bnd_ll(-5.8185, 35.7808, -5.8020, 35.7922)
    fig, ax = fig_ax(b, 2000, 1500)
    ax.set_facecolor("#ECE8E0")
    sea = np.zeros(W.shape + (4,)); sea[SEA_M] = matplotlib.colors.to_rgba(SEA); sea[(W == 80) & ~SEA_M] = matplotlib.colors.to_rgba(SEA)
    ax.imshow(sea, extent=WEXT, zorder=1, interpolation="bilinear")
    LU[LU.subtype.isin(["park", "managed"])].plot(ax=ax, color="#C9D3BB", zorder=2)
    INF[INF["class"].eq("pier")].plot(ax=ax, color="#9A9A94", lw=1.5, zorder=3)
    ROADS[ROADS["class"].isin(["footway", "pedestrian", "steps", "path", "living_street", "residential", "service", "unclassified"])].plot(ax=ax, color="white", lw=1.6, zorder=3)
    ROADS[ROADS["class"].isin(["primary", "secondary", "tertiary", "trunk"])].plot(ax=ax, color="white", lw=4.0, zorder=3)
    ROADS[ROADS["class"].isin(["primary", "secondary", "tertiary", "trunk"])].plot(ax=ax, color="#C9BFB2", lw=0.6, zorder=3.1)
    BLD.plot(ax=ax, color="#B9B1A5", edgecolor="#8F877C", linewidth=0.15, zorder=4)
    INF[INF["class"].isin(["wall", "city_wall"])].plot(ax=ax, color=INK, lw=1.6, zorder=5)
    lod = PL[PL.fam.eq("lodging")].geometry
    site = PL[PL.fam.eq("site")].geometry
    ax.scatter(lod.x, lod.y, s=34, color=RED, edgecolor="white", linewidth=0.8, zorder=12)
    ax.scatter(site.x, site.y, s=34, marker="D", color=GOLD, edgecolor="white", linewidth=0.8, zorder=12)
    for lon, lat, s in [(-5.8130, 35.7843, "Grand Socco"), (-5.8106, 35.7855, "Petit Socco"), (-5.8125, 35.7890, "Kasbah"), (-5.8045, 35.7901, "Tanja Marina Bay"),
                        (-5.8090, 35.7818, "Bd Pasteur / ville nouvelle"), (-5.8075, 35.7873, "Port")]:
        lbl(ax, lon, lat, s, size=10, w="bold", halo="#ECE8E0")
    scalebar(ax, 0.2, pos=(0.04, 0.05)); northarrow(ax)
    source(ax, "Sources : bâti, voirie, remparts et lieux OpenStreetMap / Overture (2026). Cartographie de l'auteur.")
    save(fig, "m07_medina")


def m_port():
    b = bnd_ll(-5.8190, 35.7745, -5.7880, 35.7945)
    fig, ax = fig_ax(b, 2000, 1400)
    ax.set_facecolor("#ECE8E0")
    sea = np.zeros(W.shape + (4,)); sea[(W == 80)] = matplotlib.colors.to_rgba(SEA)
    ax.imshow(sea, extent=WEXT, zorder=1, interpolation="bilinear")
    LU[LU.subtype.isin(["park", "managed", "recreation"])].plot(ax=ax, color="#C9D3BB", zorder=2)
    LU[LU.subtype.isin(["transportation", "developed"])].plot(ax=ax, color="#DCD6CB", zorder=2)
    INF[INF["class"].eq("pier")].plot(ax=ax, color="#7E7E78", lw=1.8, zorder=6)
    ROADS[ROADS["class"].isin(["footway", "pedestrian", "steps", "path", "living_street", "residential", "service", "unclassified"])].plot(ax=ax, color="white", lw=1.2, zorder=3)
    for cl, lw in [("trunk", 7), ("primary", 6), ("secondary", 4.5), ("tertiary", 3)]:
        g = ROADS[ROADS["class"].eq(cl)]
        g.plot(ax=ax, color="#8E8E88", lw=lw + 1, zorder=3.5); g.plot(ax=ax, color="white", lw=lw, zorder=3.6)
    BLD.plot(ax=ax, color="#B9B1A5", edgecolor="#8F877C", linewidth=0.15, zorder=4)
    INF[INF["class"].isin(["wall", "city_wall"])].plot(ax=ax, color=INK, lw=1.4, zorder=5)
    lod = PL[PL.fam.eq("lodging")].geometry
    ax.scatter(lod.x, lod.y, s=30, color=RED, edgecolor="white", linewidth=0.8, zorder=12)
    save_ax = ax
    save(fig, "m08_port")


def profile(lon0, lat0, lon1, lat1, n=400):
    x0, y0 = U(lon0, lat0); x1, y1 = U(lon1, lat1)
    xs = np.linspace(x0, x1, n); ys = np.linspace(y0, y1, n)
    rows, cols = rasterio.transform.rowcol(DT, xs, ys)
    z = DEM[np.array(rows), np.array(cols)]
    d = np.hypot(xs - x0, ys - y0)
    return d, z, xs, ys


def m_coupe_old():
    # coupe A : Marshan -> Kasbah -> port -> mer ; coupe B : corniche -> Beni Makada
    A = (-5.8290, 35.7880, -5.7960, 35.7872)
    B = (-5.7990, 35.7800, -5.8160, 35.7400)
    for name, (lo0, la0, lo1, la1), marks in [("m09_coupeA", A, [(-5.8125, "Kasbah"), (-5.8080, "Port / marina"), (-5.8240, "Marshan")]),
                                             ("m09_coupeB", B, [])]:
        d, z, xs, ys = profile(lo0, la0, lo1, la1)
        z = np.where(z < 0, 0, z)
        fig = plt.figure(figsize=(2400 / 200, 700 / 200), dpi=200); fig.patch.set_facecolor(PAPER)
        ax = fig.add_axes([0.05, 0.16, 0.93, 0.78]); ax.set_facecolor(PAPER)
        ax.fill_between(d, -10, z, color="#D8CDBA", zorder=2)
        ax.plot(d, z, color=INK, lw=1.2, zorder=3)
        sea = z <= 1.5
        ax.fill_between(d, -10, 0, where=sea, color=SEA, zorder=1)
        # buildings along profile from WorldCover built mask
        rr, cc = rasterio.transform.rowcol(WT, xs, ys)
        built = W[np.array(rr), np.array(cc)] == 50
        for i in range(0, len(d), 3):
            if built[i] and z[i] > 1.5:
                hgt = 8 + (i * 7 % 9)
                ax.add_patch(Rectangle((d[i] - 4, z[i]), 8, hgt, facecolor="white", edgecolor=INK, lw=0.35, zorder=4))
        ax.set_xlim(0, d.max()); ax.set_ylim(-8, max(z.max() * 1.45, 40))
        for s_ in ["top", "right"]:
            ax.spines[s_].set_visible(False)
        ax.spines["left"].set_color(MUTED); ax.spines["bottom"].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=7)
        ax.set_xlabel("distance (m)", fontsize=8, color=MUTED); ax.set_ylabel("altitude (m)", fontsize=8, color=MUTED)
        ax.text(0.995, 0.97, "exagération verticale ×%d" % round((d.max() / 2400 * 0.93) / ((ax.get_ylim()[1] - ax.get_ylim()[0]) / 700 * 0.78)), transform=ax.transAxes, ha="right", va="top", fontsize=7, color=MUTED)
        np.save(f"{OUT}/{name}_prof.npy", np.vstack([d, z]))
        fig.savefig(f"{OUT}/{name}.png", dpi=200, facecolor=PAPER); plt.close(fig); print("saved", name, int(d.max()), int(z.max()))


def m_coupe_loc():
    fig, ax = fig_ax(bnd_ll(-5.835, 35.735, -5.785, 35.795), 900, 1000)
    landcover(ax, "neutral"); hillshade(ax, 0.4)
    roads(ax, minor=True, scale=0.6)
    for (lo0, la0, lo1, la1), n in [((-5.8290, 35.7880, -5.7960, 35.7872), "A"), ((-5.7990, 35.7800, -5.8160, 35.7400), "B")]:
        x0, y0 = U(lo0, la0); x1, y1 = U(lo1, la1)
        ax.plot([x0, x1], [y0, y1], color=RED, lw=2.2, zorder=20)
        txt(ax, x0, y0, n, size=11, color="white", halo=RED, w="bold"); txt(ax, x1, y1, n + "'", size=11, color="white", halo=RED, w="bold")
    scalebar(ax, 1); northarrow(ax)
    save(fig, "m09_coupe_loc")


def sat_crop(png, lonlat_box, out, w=1200, h=900, ann=None, bright=1.0):
    from PIL import Image, ImageEnhance
    from rasterio.warp import transform_bounds
    im = Image.open(png)
    # png covers EPSG:32630 window computed from bbox (-5.97,35.66,-5.68,35.84) at 10 m
    bb = transform_bounds(4326, 32630, -5.97, 35.66, -5.68, 35.84)
    x0, y0 = U(lonlat_box[0], lonlat_box[1]); x1, y1 = U(lonlat_box[2], lonlat_box[3])
    W_, H_ = im.size
    px = lambda x: (x - bb[0]) / (bb[2] - bb[0]) * W_
    py = lambda y: (bb[3] - y) / (bb[3] - bb[1]) * H_
    c = im.crop((int(px(x0)), int(py(y1)), int(px(x1)), int(py(y0))))
    c = ImageEnhance.Contrast(c).enhance(1.15); c = ImageEnhance.Brightness(c).enhance(bright)
    h = int(w * c.height / c.width)
    c = c.resize((w, h), Image.LANCZOS)
    c.save(f"{OUT}/{out}.png"); print("saved", out)


def m_satellites():
    a = "s2_S2B_30STE_20170716_0_L2A.png"; b = "s2_S2C_30STE_20250719_0_L2A.png"
    city = (-5.955, 35.705, -5.735, 35.815)
    sat_crop(a, city, "s01_ville_2017", 1500, 1000); sat_crop(b, city, "s01_ville_2025", 1500, 1000)
    port = (-5.8200, 35.7770, -5.7920, 35.7950)
    sat_crop(a, port, "s02_port_2017", 1000, 640, bright=1.1); sat_crop(b, port, "s02_port_2025", 1000, 640, bright=1.1)
    st = (-5.8720, 35.7330, -5.8440, 35.7500)
    sat_crop(a, st, "s03_stade_2017", 1000, 610, bright=1.1); sat_crop(b, st, "s03_stade_2025", 1000, 610, bright=1.1)
    cover = (-5.98, 35.70, -5.70, 35.84)
    sat_crop(b, cover, "s00_cover", 2400, 1200)


def m_synthese(proposals=False):
    fig, ax = fig_ax(bnd_ll(-5.955, 35.70, -5.735, 35.815), 2400, 1700)
    landcover(ax, "neutral"); hillshade(ax, 0.35)
    bm = (W == 50)
    rgba = np.zeros(W.shape + (4,)); rgba[bm] = matplotlib.colors.to_rgba("#C6B9A8", 0.9)
    ax.imshow(rgba, extent=WEXT, zorder=3, interpolation="nearest")
    trees = (W == 10)
    rgbt = np.zeros(W.shape + (4,)); rgbt[trees] = matplotlib.colors.to_rgba("#B4C6A2", 0.9)
    ax.imshow(rgbt, extent=WEXT, zorder=3, interpolation="nearest")
    roads(ax, minor=False, scale=0.9)
    rail(ax, lw=1.1)
    dist = ndi.distance_transform_edt(~SEA_M) * 10
    import rasterio.features as rf
    cm_ = rf.geometry_mask([CITY.buffer(800)], W.shape, WT, invert=True)
    if not proposals:
        band = (dist > 0) & (dist <= 1000) & cm_
        r1 = np.zeros(W.shape + (4,)); r1[band] = matplotlib.colors.to_rgba(RED, 0.30)
        ax.imshow(r1, extent=WEXT, zorder=5)
        ax.contour(dist, levels=[1000], extent=(WEXT[0], WEXT[1], WEXT[3], WEXT[2]), colors=RED, linewidths=1.2, zorder=6)
        # dense under-equipped periphery = Beni Makada hatch
        bm_g = ARR[ARR.arr.eq("Beni Makada")].geometry.iloc[0]
        gpd.GeoSeries([bm_g]).plot(ax=ax, facecolor="none", edgecolor=BLUE, hatch="////", linewidth=1.6, zorder=7)
        # forest pressure edge: built pixels within 250 m of trees in city west
        tdist = ndi.distance_transform_edt(~trees) * 10
        bdist = ndi.distance_transform_edt(~bm) * 10
        big_forest = ndi.binary_opening(trees, iterations=3)
        edge = big_forest & (bdist < 120) & cm_
        ed = ndi.binary_dilation(edge, iterations=2)
        r2 = np.zeros(W.shape + (4,)); r2[ed] = matplotlib.colors.to_rgba("#2F5E2A", 0.95)
        ax.imshow(r2, extent=WEXT, zorder=7)
        for n, lon, lat in [(1, -5.800, 35.795), (2, -5.818, 35.745), (3, -5.875, 35.790), (4, -5.858, 35.741), (5, -5.905, 35.712)]:
            marker(ax, lon, lat, n, color=INK, fs=9)
        name = "m10_synthese"
    else:
        # 1 pedestrian link medina-port-corniche
        pts, _ = route([(-5.8130, 35.7843), (-5.8070, 35.7866), (-5.8010, 35.7832), (-5.7900, 35.7790)])
        ax.plot(*zip(*pts), color=RED, lw=4, zorder=12, solid_capstyle="round")
        # 3 transit line (approx along main roads): Gzenaya - Mesnana - Beni Makada - centre - gare
        line, stations = route([(-5.905, 35.712), (-5.875, 35.735), (-5.850, 35.752), (-5.830, 35.745), (-5.812, 35.752), (-5.808, 35.765), (-5.800, 35.775), (-5.786, 35.7715)])
        ax.plot(*zip(*line), color=INK, lw=6, zorder=12, solid_capstyle="round", solid_joinstyle="round")
        ax.plot(*zip(*line), color="white", lw=1.6, zorder=12.1, linestyle=(0, (1, 2)))
        np.save(OUT + "/tl_len.npy", np.array([sum(np.hypot(a[0]-b[0], a[1]-b[1]) for a, b in zip(line[:-1], line[1:]))]))
        for p in stations:
            ax.add_patch(Circle(p, 180, facecolor="white", edgecolor=INK, lw=1.6, zorder=13))
        # 4 green belt around Rmilat / Cap Spartel: dilate forest
        tb = ndi.binary_closing(ndi.binary_opening(trees, iterations=4), iterations=10)
        lab_, n_ = ndi.label(tb); sz = ndi.sum(np.ones_like(lab_), lab_, range(n_ + 1)); sz[0] = 0
        trees_d = np.isin(lab_, np.where(sz > 40000)[0]) & (dist < 6000)
        ax.contour(trees_d.astype(float), levels=[0.5], extent=(WEXT[0], WEXT[1], WEXT[3], WEXT[2]), colors=GREEN, linewidths=1.6, linestyles="--", zorder=8)
        # 5 equipments in Beni Makada / Mghogha
        for lon, lat in [(-5.818, 35.748), (-5.808, 35.742), (-5.826, 35.741), (-5.790, 35.735), (-5.775, 35.728), (-5.850, 35.752)]:
            x, y = U(lon, lat); ax.add_patch(Rectangle((x - 140, y - 140), 280, 280, facecolor=GOLD, edgecolor="white", lw=1.2, zorder=14))
        for n, lon, lat in [(1, -5.795, 35.7875), (2, -5.8155, 35.7905), (3, -5.850, 35.747), (4, -5.885, 35.790), (5, -5.798, 35.735)]:
            marker(ax, lon, lat, n, color=INK, fs=9)
        name = "m11_propositions"
    boundaries(ax, lw=1.1)
    scalebar(ax, 2); northarrow(ax)
    source(ax, "Base : ESA WorldCover 2021, OpenStreetMap / Overture (2026), Copernicus DEM. Synthèse de l'auteur.")
    save(fig, name)


import networkx as nx
_G = None
def road_graph():
    global _G
    if _G is None:
        g = nx.Graph()
        R = ROADS[ROADS["class"].isin(["trunk", "primary", "secondary", "tertiary", "residential", "unclassified", "living_street", "pedestrian", "footway", "steps"])]
        for geom in R.geometry:
            lines = getattr(geom, "geoms", [geom])
            for ln in lines:
                c = list(ln.coords)
                for a, b in zip(c[:-1], c[1:]):
                    a = (round(a[0], 1), round(a[1], 1)); b = (round(b[0], 1), round(b[1], 1))
                    g.add_edge(a, b, w=np.hypot(a[0] - b[0], a[1] - b[1]))
        cc = max(nx.connected_components(g), key=len)
        _G = g.subgraph(cc).copy()
        _G_nodes = np.array(list(_G.nodes))
        globals()["_GN"] = _G_nodes
    return _G
def route(waypoints):
    g = road_graph(); N = globals()["_GN"]
    pts = [U(*p) for p in waypoints]
    near = [tuple(N[np.argmin(((N - np.array(p)) ** 2).sum(1))]) for p in pts]
    path = []
    for a, b in zip(near[:-1], near[1:]):
        path += nx.shortest_path(g, a, b, weight="w")
    return path, near

ALL = {k: v for k, v in globals().items() if k.startswith("m_")}



def m_coupe():
    A = ((-5.8290, 35.7880, -5.7960, 35.7872), [(-5.8235, 35.7880, "Marshan"), (-5.8128, 35.7889, "Kasbah"), (-5.8085, 35.7880, "rempart / porte"), (-5.8060, 35.7878, "route du port"), (-5.8035, 35.7876, "marina"), (-5.7990, 35.7873, "bassin")])
    B = ((-5.7990, 35.7800, -5.8160, 35.7400), [(-5.7988, 35.7795, "plage / corniche"), (-5.8020, 35.7740, "route littorale"), (-5.8060, 35.7650, "ville nouvelle"), (-5.8100, 35.7550, "Beni Makada"), (-5.8140, 35.7450, "collines sud")])
    for name, ((lo0, la0, lo1, la1), marks) in [("m09_coupeA", A), ("m09_coupeB", B)]:
        d, z, xs, ys = profile(lo0, la0, lo1, la1, n=500)
        z = np.where(z < 0, 0, z)
        fig = plt.figure(figsize=(2600 / 200, 820 / 200), dpi=200); fig.patch.set_facecolor(PAPER)
        ax = fig.add_axes([0.05, 0.14, 0.93, 0.70]); ax.set_facecolor(PAPER)
        rr, cc = rasterio.transform.rowcol(WT, xs, ys)
        cls = W[np.array(rr), np.array(cc)]
        ax.fill_between(d, -12, z, color="#D9CEBB", zorder=2)
        ax.fill_between(d, -12, 0.5, where=(cls == 80), color=SEA, zorder=3)
        ax.plot(d, z, color=INK, lw=1.3, zorder=5)
        step = 14
        for i in range(0, len(d) - step, step):
            if cls[i] == 50 and z[i] > 1:
                hgt = 9 + (i * 13 % 7) * 1.5
                ax.add_patch(Rectangle((d[i], z[i]), d[step] - d[0] - 2, hgt, facecolor="#F4F1EB", edgecolor="#4A4A4A", lw=0.5, zorder=4))
            elif cls[i] == 10 and z[i] > 1:
                ax.add_patch(Circle((d[i] + 10, z[i] + 7), 7, facecolor="#9DB38A", edgecolor="none", zorder=4))
        top = max(z.max() * 1.7, 50)
        ax.set_xlim(0, d.max()); ax.set_ylim(-12, top)
        x0m, y0m = U(lo0, la0); x1m, y1m = U(lo1, la1); L = np.hypot(x1m - x0m, y1m - y0m)
        for lon, lat, s_ in marks:
            px, py = U(lon, lat)
            t = ((px - x0m) * (x1m - x0m) + (py - y0m) * (y1m - y0m)) / L
            zi = np.interp(t, d, z)
            ax.plot([t, t], [zi + 14, top * 0.86], color=RED, lw=0.7, zorder=6)
            ax.text(t, top * 0.88, s_, ha="center", va="bottom", fontsize=9, color=RED, fontweight="bold", family=CF)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
        ax.spines["left"].set_color(MUTED); ax.spines["bottom"].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.set_xlabel("distance (m)", fontsize=9, color=MUTED, family=CF); ax.set_ylabel("altitude (m)", fontsize=9, color=MUTED, family=CF)
        fig.savefig(f"{OUT}/{name}.png", dpi=200, facecolor=PAPER); plt.close(fig); print("saved", name, int(d.max()), int(z.max()))

ALL["m_coupe"] = m_coupe

if __name__ == "__main__":
    names = sys.argv[1:] or list(ALL)
    for n in names:
        if n == "m_synthese":
            m_synthese(False); m_synthese(True)
        else:
            ALL[n]()


def m_industrie():
    fig, ax = fig_ax(bnd_ll(-5.98, 35.62, -5.47, 35.90), 2400, 1500)
    landcover(ax, "neutral"); hillshade(ax, 0.45)
    bm = (W == 50)
    rgba = np.zeros(W.shape + (4,)); rgba[bm] = matplotlib.colors.to_rgba("#BFB3A3", 1)
    ax.imshow(rgba, extent=WEXT, zorder=3, interpolation="nearest")
    ind = LU[LU["class"].eq("industrial")]
    ind.plot(ax=ax, color=BLUE, alpha=0.85, zorder=5)
    roads(ax, minor=False, scale=1.2, classes=["motorway", "trunk", "primary"])
    rail(ax, lw=1.1)
    boundaries(ax, arr=False, lw=1.2)
    origin = (-5.818, 35.748)
    ox, oy = U(*origin)
    ax.add_patch(Circle((ox, oy), 700, facecolor=RED, edgecolor="white", lw=1.5, zorder=30))
    txt(ax, ox - 900, oy - 1500, "Beni Makada\n567 000 hab.", size=10, color=RED, w="bold")
    res = []
    for lon, lat, s, dx, dy in [(-5.9053, 35.7155, "Zone franche", -1200, -1300), (-5.6868, 35.6916, "Renault Melloussa", 0, -1500),
                                 (-5.6618, 35.6575, "Tanger Automotive City", 0, -1500), (-5.5015, 35.8836, "Port Tanger Med", 0, -1500)]:
        x, y = U(lon, lat)
        dkm = np.hypot(x - ox, y - oy) / 1000
        ax.annotate("", xy=(x, y), xytext=(ox, oy), arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.4, linestyle=(0, (4, 2)), shrinkA=12, shrinkB=10), zorder=25)
        mx, my = (x + ox) / 2, (y + oy) / 2
        txt(ax, mx, my, f"{dkm:.0f} km", size=11, color=RED, w="bold")
        ax.add_patch(Circle((x, y), 550, facecolor=BLUE, edgecolor="white", lw=1.5, zorder=30))
        txt(ax, x + dx, y + dy, s, size=10, color=BLUE, w="bold")
        res.append((s, round(dkm, 1)))
    print(res)
    lbl(ax, -5.83, 35.785, "TANGER", size=13, spacing=True)
    lbl(ax, -5.80, 35.875, "DÉTROIT DE GIBRALTAR", size=10, color="#5C7884", halo=None, spacing=True, style="italic")
    scalebar(ax, 5); northarrow(ax, pos=(0.955, 0.16))
    source(ax, "Sources : zones industrielles et voirie OpenStreetMap / Overture (2026), ESA WorldCover 2021, Copernicus DEM. Distances à vol d'oiseau.")
    save(fig, "m12_industrie")
