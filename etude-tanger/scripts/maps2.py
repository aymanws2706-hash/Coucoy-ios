# -*- coding: utf-8 -*-
import sys
import numpy as np, geopandas as gpd, rasterio, rasterio.features as rf
import matplotlib.pyplot as plt, matplotlib
from matplotlib.patches import Rectangle, Circle, Polygon as MPoly
from matplotlib.transforms import Affine2D
from scipy import ndimage as ndi
from rasterio.warp import reproject, Resampling
from shapely.ops import unary_union
import maps as M
from maps import *

TERRA = "#B5563C"; OCHRE = "#C9965A"
SLATE_D = "#2F3E48"; P04 = "#3B4650"; P14 = "#B5563C"; P21 = "#E0A86A"


def sprawl_layers():
    d = np.load("sprawl.npz")
    return d["b04"], d["b14"], d["b21"], float(d["x0"]), float(d["y1"]), float(d["res"])


def m_sprawl():
    b04, b14, b21, x0, y1, res = sprawl_layers()
    ext = (x0, x0 + b04.shape[1] * res, y1 - b04.shape[0] * res, y1)
    fig, ax = fig_ax(bnd_ll(-5.99, 35.655, -5.68, 35.835), 2400, 1550)
    landcover(ax, "neutral", alpha=0.75); hillshade(ax, 0.35)
    rgba = np.zeros(b04.shape + (4,))
    rgba[b21] = matplotlib.colors.to_rgba(P21); rgba[b14] = matplotlib.colors.to_rgba(P14); rgba[b04] = matplotlib.colors.to_rgba(P04)
    ax.imshow(rgba, extent=ext, zorder=5, interpolation="nearest")
    ROADS[ROADS["class"].isin(["motorway", "trunk"])].plot(ax=ax, color="white", lw=2.6, zorder=6)
    ROADS[ROADS["class"].isin(["motorway", "trunk"])].plot(ax=ax, color=INK, lw=0.9, zorder=6.1)
    boundaries(ax, lw=1.3)
    for lon, lat, s in [(-5.812, 35.791, "MÉDINA"), (-5.815, 35.748, "BENI MAKADA"), (-5.775, 35.733, "MGHOGHA"), (-5.905, 35.703, "GZENAYA"),
                        (-5.875, 35.735, "BOUKHALEF"), (-5.86, 35.80, "RMILAT"), (-5.765, 35.795, "MALABATA")]:
        lbl(ax, lon, lat, s, size=8.5, spacing=True)
    scalebar(ax, 2); northarrow(ax)
    source(ax, "Estimation de l'auteur : classification Landsat 5 (24/07/2004), Landsat 8 (05/08/2014, 08/08/2021), entraînée sur ESA WorldCover 2021. Résolution 30 m.")
    save(fig, "m13_etalement")
    # small multiples
    for yr, layers in [("2004", [b04]), ("2014", [b04, b14]), ("2021", [b04, b14, b21])]:
        fig, ax = fig_ax(bnd_ll(-5.97, 35.68, -5.70, 35.83), 900, 620)
        landcover(ax, "neutral", alpha=0.6)
        rg = np.zeros(b04.shape + (4,))
        cols = [P04, P14, P21]
        for i, l in reversed(list(enumerate(layers))):
            rg[l] = matplotlib.colors.to_rgba(cols[i])
        rg[b04] = matplotlib.colors.to_rgba(P04)
        if yr != "2004":
            rg[b14 & ~b04] = matplotlib.colors.to_rgba(P14)
        ax.imshow(rg, extent=ext, zorder=5, interpolation="nearest")
        boundaries(ax, arr=False, lw=1.0)
        x0_, x1_ = ax.get_xlim(); y0_, y1_ = ax.get_ylim()
        txt(ax, x0_ + (x1_ - x0_) * 0.06, y1_ - (y1_ - y0_) * 0.1, yr, size=22, w="bold", ha="left", halo=None, color=INK)
        save(fig, f"m13_{yr}")


def layer_rasters(b):
    """raster layers over bounds b (UTM) at 40 m"""
    x0, y0, x1, y1 = b; res = 40
    w = int((x1 - x0) / res); h = int((y1 - y0) / res)
    tr = rasterio.transform.from_origin(x0, y1, res, res)
    def rs(arr, src_tr, method=Resampling.nearest, dtype=np.float32):
        out = np.zeros((h, w), dtype)
        reproject(arr.astype(dtype), out, src_transform=src_tr, src_crs="EPSG:32630", dst_transform=tr, dst_crs="EPSG:32630", resampling=method)
        return out
    wc = rs(W, WT, Resampling.mode, np.uint8)
    dem = rs(DEM, DT, Resampling.bilinear)
    hs = rs(HS, DT, Resampling.bilinear)
    sea = rs(SEA_M.astype(np.uint8), WT, Resampling.mode, np.uint8).astype(bool)
    b04, b14, b21, sx0, sy1, sres = sprawl_layers()
    str_ = rasterio.transform.from_origin(sx0, sy1, sres, sres)
    per = np.zeros(b04.shape, np.uint8); per[b21] = 3; per[b14] = 2; per[b04] = 1
    per = rs(per, str_, Resampling.mode, np.uint8)
    roads = rf.rasterize([(g.buffer(30 if c in ("motorway", "trunk") else 18), 1) for g, c in zip(ROADS.geometry, ROADS["class"]) if c in ("motorway", "trunk", "primary", "secondary")],
                         out_shape=(h, w), transform=tr)
    rail = rf.rasterize([(g.buffer(25), 1) for g in RAIL.geometry], out_shape=(h, w), transform=tr)
    pts = {}
    for fam in ("lodging", "school", "health"):
        q = PL[PL.fam.eq(fam)]
        pts[fam] = [(int((y1 - p.y) / res), int((p.x - x0) / res)) for p in q.geometry if x0 < p.x < x1 and y0 < p.y < y1]
    return dict(wc=wc, dem=dem, hs=hs, sea=sea, per=per, roads=roads, rail=rail, pts=pts, shape=(h, w))


def m_layers():
    b = bnd_ll(-5.95, 35.70, -5.74, 35.815)
    L = layer_rasters(b); h, w = L["shape"]
    to = lambda c: np.array(matplotlib.colors.to_rgba(c))
    def blank():
        return np.zeros((h, w, 4))
    sea = L["sea"]
    layers = []
    # 1 relief
    im = blank(); cm = LinearSegmentedColormap.from_list("r", ["#E9E2D3", "#CDBB9F", "#9E8A6E"])
    im[:] = cm(np.clip(L["dem"] / 160, 0, 1)); im[..., :3] *= (0.55 + 0.45 * L["hs"][..., None]); im[sea] = to(SEA)
    layers.append(("RELIEF", "Copernicus DEM : collines au sud, falaise de la Kasbah", im))
    # 2 trame verte et bleue
    im = blank(); im[L["wc"] == 10] = to("#8FA77E"); im[np.isin(L["wc"], [20, 30])] = to("#C9D1B3"); im[L["wc"] == 80] = to(SEA); im[sea] = to(SEA)
    layers.append(("TRAME VERTE ET BLEUE", "forêts de Rmilat, Perdicaris, Malabata ; plans d'eau", im))
    # 3 bâti par période
    im = blank(); im[L["per"] == 3] = to(P21); im[L["per"] == 2] = to(P14); im[L["per"] == 1] = to(P04)
    layers.append(("BÂTI 2004 / 2014 / 2021", "la tache urbaine double vers le sud et l'ouest", im))
    # 4 réseaux
    im = blank(); im[L["roads"] == 1] = to(INK); im[L["rail"] == 1] = to(TERRA)
    layers.append(("RÉSEAUX", "voies express, routes principales, LGV et voie ferrée", im))
    # 5 vitrine vs équipements
    im = blank()
    for fam, c in (("school", BLUE), ("health", BLUE), ("lodging", RED)):
        for r_, c_ in L["pts"][fam]:
            im[max(0, r_ - 2):r_ + 3, max(0, c_ - 2):c_ + 3] = to(c)
    layers.append(("USAGES", "hébergements (rouge) contre écoles et santé (bleu)", im))
    fig = plt.figure(figsize=(2400 / 200, 2000 / 200), dpi=200); fig.patch.set_facecolor(PAPER)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_facecolor(PAPER); ax.set_axis_off()
    gap = h * 0.62
    A = Affine2D().scale(1.0, 0.42).skew_deg(-38, 0)
    for i, (t, sub, im) in enumerate(layers):
        off = i * gap
        tr = Affine2D().scale(1, 1) + A + Affine2D().translate(w * 0.62, off)
        # slab frame
        corners = np.array([[0, 0], [w, 0], [w, h], [0, h]])
        cc = tr.transform(corners)
        ax.add_patch(MPoly(cc, closed=True, facecolor="#FBF8F2", edgecolor=INK, lw=0.8, zorder=i * 3, alpha=0.96))
        ax.imshow(np.flipud(im), extent=(0, w, 0, h), transform=tr + ax.transData, zorder=i * 3 + 1, interpolation="nearest", origin="lower")
        ax.add_patch(MPoly(cc, closed=True, facecolor="none", edgecolor=INK, lw=0.8, zorder=i * 3 + 2))
        # label at left
        lx, ly = cc[3]
        ax.plot([lx - 40, lx - 260], [ly - h * 0.21, ly - h * 0.21], color=MUTED, lw=0.6, zorder=50)
        ax.text(lx - 270, ly - h * 0.21 + 8, f"{i + 1:02d}  {t}", ha="right", va="bottom", fontsize=13, color=INK, fontweight="bold", family=CF)
        ax.text(lx - 270, ly - h * 0.21 - 6, sub, ha="right", va="top", fontsize=9.5, color=MUTED, family=CF)
    ax.set_xlim(-w * 0.55, w * 1.65); ax.set_ylim(-h * 0.1, gap * 4 + h * 0.62)
    fig.savefig("maps/m14_couches.png", dpi=200, facecolor=PAPER); plt.close(fig); print("saved m14_couches")


def m_plan():
    """Plan d'aménagement alternatif (logique PA / SDAU) sur base réelle."""
    fig, ax = fig_ax(bnd_ll(-5.955, 35.700, -5.735, 35.815), 2400, 1700, bg="#F6F3EC")
    gx0, gx1 = ax.get_xlim(); gy0, gy1 = ax.get_ylim()
    c0 = int((gx0 - 1000 - WT.c) / WT.a); c1 = int((gx1 + 1000 - WT.c) / WT.a); r0 = int((gy1 + 1000 - WT.f) / WT.e); r1 = int((gy0 - 1000 - WT.f) / WT.e)
    c0, r0 = max(c0, 0), max(r0, 0)
    W = M.W[r0:r1, c0:c1]; SEA_M = M.SEA_M[r0:r1, c0:c1]
    WT_ = rasterio.transform.Affine(WT.a, 0, WT.c + c0 * WT.a, 0, WT.e, WT.f + r0 * WT.e)
    WEXT = (WT_.c, WT_.c + WT_.a * W.shape[1], WT_.f + WT_.e * W.shape[0], WT_.f)
    sea_rgba = np.zeros(W.shape + (4,), np.uint8); sea_rgba[(W == 80) | SEA_M] = (np.array(matplotlib.colors.to_rgba(SEA)) * 255).astype(np.uint8)
    ax.imshow(sea_rgba, extent=WEXT, zorder=1, interpolation="nearest")
    hillshade(ax, 0.22)
    city_m = rf.geometry_mask([CITY.buffer(600)], W.shape, WT_, invert=True)
    built = ndi.binary_closing(W == 50, iterations=3)
    trees = W == 10
    forest = ndi.binary_closing(ndi.binary_opening(trees, iterations=3), iterations=8)
    lab, n = ndi.label(forest); sz = ndi.sum(np.ones_like(lab), lab, range(n + 1)); sz[0] = 0
    forest = np.isin(lab, np.where(sz > 30000)[0])
    dist_sea = ndi.distance_transform_edt(~SEA_M) * 10
    # tram line & TOD
    line, stations = M.route([(-5.905, 35.712), (-5.875, 35.735), (-5.850, 35.752), (-5.830, 35.745), (-5.812, 35.752), (-5.808, 35.765), (-5.800, 35.775), (-5.786, 35.7715)])
    from shapely.geometry import LineString, Point
    tl = LineString(line)
    tod = rf.geometry_mask([tl.buffer(500)], W.shape, WT_, invert=True)
    stn = rf.geometry_mask([unary_union([Point(p).buffer(700) for p in stations])], W.shape, WT_, invert=True)
    agri = np.isin(W, [20, 30, 40, 60]) & ~forest
    # growth boundary = closed(built) dilated 150 m + AU near stations
    au = stn & ~built & ~forest & ~SEA_M & (W != 80) & city_m
    au = ndi.binary_opening(au, iterations=2)
    urb = (built | au)
    lim0 = ndi.gaussian_filter(urb.astype(np.float32), 25) > 0.18
    labl, nl = ndi.label(lim0); szl = ndi.sum(np.ones_like(labl), labl, range(nl + 1)); szl[0] = 0
    limit = np.isin(labl, np.argsort(szl)[::-1][:2]) & ~SEA_M
    # reserves inside urban fabric: unbuilt holes > 1.5 ha within built envelope in Beni Makada / Mghogha
    env = ndi.binary_fill_holes(ndi.binary_closing(built, iterations=6))
    holes = env & ~built & ~SEA_M & (W != 80)
    lab2, n2 = ndi.label(holes); sz2 = ndi.sum(np.ones_like(lab2), lab2, range(n2 + 1)); sz2[0] = 0
    arr_bm = rf.geometry_mask([unary_union(ARR[ARR.arr.isin(["Beni Makada", "Charf-Mghogha"])].geometry.values)], W.shape, WT_, invert=True)
    reserves = np.isin(lab2, np.where((sz2 > 150) & (sz2 < 2500))[0]) & arr_bm
    littoral = (dist_sea > 0) & (dist_sea <= 100) & city_m
    def paint(mask, color, alpha=1.0, z=3):
        rg = np.zeros(W.shape + (4,), np.uint8); rg[mask] = (np.array(matplotlib.colors.to_rgba(color, alpha)) * 255).astype(np.uint8)
        ax.imshow(rg, extent=WEXT, zorder=z, interpolation="nearest")
    paint(agri & ~limit, "#ECE6D3", 1, 2)                       # A
    paint(forest, "#A9BC97", 1, 3)                               # N
    paint(built & ~tod, "#DCCDB9", 1, 4)                         # U
    paint(built & tod, "#E2B48F", 1, 4.1)                        # UT (TOD)
    paint(au & ~built, "#F0D9B8", 1, 4.2)                        # AU
    paint(reserves, "#B9C9A2", 1, 4.3)                           # parcs / équipements
    paint(littoral & ~built, "#9EB78E", 1, 4.4)                  # LP
    # hatches via contourf
    for mask, hatch, col in [(forest, "\\\\\\\\", "#5E7E55"), (au & ~built, "....", "#B5803F"), (littoral, "||||", "#4F6B4A")]:
        cs = ax.contourf(mask.astype(float), levels=[0.5, 1.5], extent=(WEXT[0], WEXT[1], WEXT[3], WEXT[2]), colors="none", hatches=[hatch], zorder=5)
        for c in cs.collections if hasattr(cs, "collections") else [cs]:
            try:
                c.set_edgecolor(col); c.set_linewidth(0)
            except Exception:
                pass
    # trame bleue : oueds
    WAT = gpd.read_parquet("u_water_region.parquet")
    streams = WAT[WAT.subtype.isin(["stream", "river", "canal"]) & WAT.intersects(CITY.buffer(1500))]
    streams.buffer(60).plot(ax=ax, color="#9DB98F", zorder=6, alpha=0.9)
    streams.plot(ax=ax, color="#5F8796", lw=1.4, zorder=6.1)
    # roads base
    ROADS[ROADS["class"].isin(["motorway", "trunk", "primary"])].plot(ax=ax, color="white", lw=2.6, zorder=7)
    ROADS[ROADS["class"].isin(["motorway", "trunk", "primary"])].plot(ax=ax, color="#9C8F80", lw=0.9, zorder=7.1)
    ROADS[ROADS["class"].isin(["secondary", "tertiary"])].plot(ax=ax, color="#B9AE9F", lw=0.4, zorder=7)
    # growth limit
    ax.contour(limit.astype(float), levels=[0.5], extent=(WEXT[0], WEXT[1], WEXT[3], WEXT[2]), colors=INK, linewidths=1.6, linestyles=[(0, (6, 3))], zorder=9)
    # tram
    ax.plot(*zip(*line), color="white", lw=8, zorder=10, solid_capstyle="round")
    ax.plot(*zip(*line), color=SLATE_D, lw=5, zorder=10.1, solid_capstyle="round")
    for p in stations:
        ax.add_patch(Circle(p, 500, facecolor="none", edgecolor=SLATE_D, lw=0.8, linestyle=(0, (3, 2)), zorder=10))
        ax.add_patch(Circle(p, 140, facecolor="white", edgecolor=SLATE_D, lw=2, zorder=11))
    # pedestrian waterfront link
    pl, _ = M.route([(-5.8130, 35.7843), (-5.8070, 35.7866), (-5.8010, 35.7832), (-5.7900, 35.7790)])
    ax.plot(*zip(*pl), color=TERRA, lw=3.5, zorder=12, linestyle=(0, (2, 1.2)))
    # medina housing priority
    mx0, my0 = U(-5.8170, 35.7830); mx1, my1 = U(-5.8050, 35.7905)
    ax.add_patch(Rectangle((mx0, my0), mx1 - mx0, my1 - my0, facecolor="none", edgecolor=TERRA, hatch="xxxx", lw=1.2, zorder=12))
    # equipment squares on reserves centroids
    labr, nr = ndi.label(reserves)
    cents = ndi.center_of_mass(reserves, labr, range(1, nr + 1))
    sizes = ndi.sum(reserves, labr, range(1, nr + 1))
    order = np.argsort(sizes)[::-1][:9]
    for k in order:
        r_, c_ = cents[k]; x = WT_.c + c_ * WT_.a; y = WT_.f + r_ * WT_.e
        ax.add_patch(Rectangle((x - 130, y - 130), 260, 260, facecolor=OCHRE, edgecolor="white", lw=1.4, zorder=13))
    boundaries(ax, arr=False, lw=1.0)
    for lon, lat, s in [(-5.812, 35.7915, "MÉDINA"), (-5.815, 35.748, "BENI MAKADA"), (-5.775, 35.733, "MGHOGHA"), (-5.905, 35.703, "GZENAYA"), (-5.875, 35.795, "RMILAT")]:
        lbl(ax, lon, lat, s, size=8.5, spacing=True, halo="#F6F3EC")
    # zone codes
    for code, lon, lat in [("N", -5.880, 35.780), ("N", -5.738, 35.806), ("UT", -5.842, 35.748), ("AU", -5.893, 35.722), ("A", -5.80, 35.712), ("LP", -5.925, 35.760), ("U", -5.790, 35.745)]:
        x, y = U(lon, lat)
        txt(ax, x, y, code, size=12, w="bold", color=INK, halo="#F6F3EC")
    scalebar(ax, 2); northarrow(ax)
    source(ax, "Proposition de l'auteur sur base ESA WorldCover 2021, OpenStreetMap / Overture (2026), Copernicus DEM. Tracés et périmètres indicatifs.")
    a_km2 = lambda m: m.sum() * 100 / 1e6
    print("AU km2", round(a_km2(au & ~built), 2), "reserves ha", round(reserves.sum() * 100 / 1e4, 1), "LP km2", round(a_km2(littoral & ~built), 2),
          "tod built km2", round(a_km2(built & tod), 2), "stations", len(stations), "N km2 (city+600)", round(a_km2(forest & city_m), 1))
    save(fig, "m15_plan")





def m_coupes_loc():
    fig, ax = fig_ax(bnd_ll(-5.832, 35.744, -5.788, 35.796), 1000, 1150)
    landcover(ax, "neutral"); hillshade(ax, 0.35)
    roads(ax, minor=True, scale=0.7)
    for (lo0, la0, lo1, la1), n, c in [((-5.7962, 35.7808, -5.7998, 35.7748), "C1", TERRA), ((-5.8190, 35.7525, -5.8130, 35.7525), "C2", BLUE), ((-5.8140, 35.7890, -5.8030, 35.7878), "C3", OCHRE)]:
        x0, y0 = U(lo0, la0); x1, y1 = U(lo1, la1)
        ax.plot([x0, x1], [y0, y1], color="white", lw=6, zorder=20); ax.plot([x0, x1], [y0, y1], color=c, lw=3.2, zorder=21)
        txt(ax, x0, y0, n, size=12, color="white", halo=c, w="bold", z=22)
    scalebar(ax, 1); northarrow(ax)
    save(fig, "m16_coupes_loc")


if __name__ == "__main__":
    for n in sys.argv[1:]:
        globals()[n]()
