# -*- coding: utf-8 -*-
"""Coupes semi-réalistes : sol réel (Copernicus DEM), emprises réelles (OSM/Overture, ESA WorldCover), gabarits estimés."""
import json, glob, os, sys
import numpy as np, geopandas as gpd, rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Rectangle, Polygon, Circle, Ellipse, FancyBboxPatch
from shapely.geometry import LineString
from pyproj import Transformer
from scipy.ndimage import map_coordinates, gaussian_filter1d

for f in glob.glob(os.path.expanduser("~/.fonts/barlow*.ttf")):
    fm.fontManager.addfont(f)
CF = "Barlow Condensed"; plt.rcParams["font.family"] = CF
T = Transformer.from_crs(4326, 32630, always_xy=True)

# palette
PAPER = "#EFEBE3"; INK = "#23303A"; MUTED = "#7B746B"; TERRA = "#B5563C"; OCHRE = "#C9965A"; SAGE = "#7D9873"; SAGE_D = "#4F6B4A"
SEA = "#A8C0C6"; SEA_D = "#6F94A0"; SLATE = "#3E5A6E"; EARTH = "#D9CBB6"; EARTH_D = "#C2B29A"
FACADE = ["#F6F1E8", "#F1E8DA", "#EADFCF", "#F3EEE6", "#E9DCCB", "#F7F3EC"]
WHITEWASH = ["#FAF8F4", "#F4F1EC", "#EEF0F0", "#F7F2EA"]

WC = rasterio.open("u_wc10.tif"); W = WC.read(1)
DEMR = rasterio.open("u_dem20.tif"); DEM = DEMR.read(1)
SEA_M = np.load("a_sea.npy")
SEG = gpd.read_parquet("u_seg_region.parquet"); ROADS = SEG[SEG.subtype.eq("road")]
INF = gpd.read_parquet("u_infra_region.parquet")
RW = {"trunk": 30, "primary": 24, "secondary": 20, "tertiary": 12, "residential": 8, "unclassified": 7, "living_street": 6, "service": 6,
      "pedestrian": 4, "footway": 3, "steps": 3, "path": 2.5, "track": 4, "unknown": 5}


def sample(lonlat0, lonlat1):
    p0 = T.transform(*lonlat0); p1 = T.transform(*lonlat1)
    L = LineString([p0, p1]); n = int(L.length)
    xs = np.linspace(p0[0], p1[0], n); ys = np.linspace(p0[1], p1[1], n)
    # DEM bilinear
    inv = ~DEMR.transform
    cc, rr = inv * (xs, ys)
    z = map_coordinates(DEM, [rr - 0.5, cc - 0.5], order=1)
    z = np.where(z < 0, 0, z)
    winv = ~WC.transform
    wc_c, wc_r = winv * (xs, ys)
    cls = W[wc_r.astype(int), wc_c.astype(int)]
    sea = SEA_M[wc_r.astype(int), wc_c.astype(int)]
    # roads
    hits = []
    for g, c, nm in zip(ROADS.geometry, ROADS["class"], ROADS["name"]):
        if g.intersects(L):
            it = L.intersection(g)
            pts = [it] if it.geom_type == "Point" else list(getattr(it, "geoms", [it.representative_point()]))
            for p in pts:
                name = None
                if isinstance(nm, str):
                    try:
                        name = json.loads(nm).get("primary") if nm.startswith("{") else nm
                    except Exception:
                        name = nm
                hits.append((L.project(p), c, name))
    hits.sort()
    infra = []
    for g, c in zip(INF.geometry, INF["class"]):
        if g.intersects(L) and c in ("city_wall", "wall", "breakwater", "pier", "fence"):
            infra.append((L.project(L.intersection(g).representative_point()), c))
    return dict(n=n, z=z, cls=cls, sea=sea, roads=hits, infra=infra)


def merge_roads(hits, merge=18):
    out = []
    for pos, c, nm in hits:
        if out and pos - out[-1][1] < merge and (c == out[-1][2] or RW.get(c, 5) >= 12 and RW.get(out[-1][2], 5) >= 12):
            out[-1][1] = pos
            continue
        out.append([pos, pos, c, nm])
    res = []
    for a, b, c, nm in out:
        w = RW.get(c, 5)
        if b - a > 2:  # dual carriageway
            w = (b - a) + w * 0.9
        res.append(((a + b) / 2, w, c, nm))
    return res


class Section:
    def __init__(self, name, a, b, exag=1.6, px_per_m=5.5, seed=1, crop=None, profile=None):
        self.name = name; self.d = sample(a, b); self.ex = exag; self.k = px_per_m
        self.rng = np.random.default_rng(seed)
        n = self.d["n"]
        self.x0, self.x1 = crop or (0, n)
        self.profile = profile or (lambda pos: (2, 4))
        self.z = gaussian_filter1d(self.d["z"], 6)
        self.roads = [r for r in merge_roads(self.d["roads"]) if self.x0 <= r[0] <= self.x1]
        self.labels = []

    # ---------------------------------------------------------------- helpers
    def zg(self, pos):
        return float(np.interp(pos, np.arange(len(self.z)), self.z))

    def occ(self):
        n = self.d["n"]; occ = np.array(["open"] * n, dtype=object)
        cls = self.d["cls"]; sea = self.d["sea"]
        occ[cls == 50] = "built"; occ[np.isin(cls, [10])] = "tree"; occ[np.isin(cls, [30, 20, 40])] = "green"; occ[cls == 60] = "bare"
        occ[sea | (cls == 80)] = "sea"
        for pos, w, c, nm in self.roads:
            a, b = int(max(0, pos - w / 2)), int(min(n, pos + w / 2))
            occ[a:b] = "road"
        return occ

    def draw(self, out, title, notes=(), height_px=None, sky=True):
        occ = self.occ()
        zmax = max(self.z[self.x0:self.x1].max(), 5)
        top = zmax + 30
        W_ = (self.x1 - self.x0) * self.k
        H_ = height_px or int((top + 9 + 18) * self.ex * self.k)
        fig = plt.figure(figsize=(W_ / 200, H_ / 200), dpi=200)
        ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(self.x0, self.x1)
        ybot = -9
        ax.set_ylim(ybot * self.ex, ybot * self.ex + H_ / self.k)
        ax.set_axis_off(); fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
        self.ax = ax; E = self.ex
        X = np.arange(self.x0, self.x1)
        Z = self.z[self.x0:self.x1] * E
        if sky:
            grad = np.linspace(0, 1, 100)[:, None]
            ax.imshow(grad, extent=(self.x0, self.x1, 0, (top + 20) * E), aspect="auto", cmap=matplotlib.colors.LinearSegmentedColormap.from_list("s", ["#F5F2EC", "#E3E9EA"]), zorder=0, origin="lower", alpha=0.9)
        # sea
        seam = (occ[self.x0:self.x1] == "sea")
        if seam.any():
            xs = X[seam]
            for a, b in self.runs(seam):
                ax.add_patch(Rectangle((X[a], ybot * E), X[b - 1] - X[a] + 1, -ybot * E, facecolor=SEA, edgecolor="none", zorder=2))
                for k in range(a, b, 6):
                    ax.plot([X[k], X[k] + 3], [-0.6 * E, -0.6 * E], color="white", lw=0.6, zorder=3, alpha=0.8)
                ax.plot([X[a], X[b - 1]], [0, 0], color=SEA_D, lw=1.2, zorder=3)
        # ground mass
        Zg = np.where(seam, -6 * E, Z)
        ax.fill_between(X, ybot * E, Zg, color=EARTH, zorder=4, linewidth=0)
        ax.plot(X, Zg, color=INK, lw=1.4, zorder=12)
        for i in range(1, 4):  # soil strata
            ax.plot(X, Zg - i * 3.2 * E, color=EARTH_D, lw=0.5, zorder=4.5, alpha=0.8)
        ax.fill_between(X, ybot * E, ybot * E + 1.2 * E, color=EARTH_D, zorder=4.6)
        # elements
        self.draw_roads(occ)
        self.draw_built(occ)
        self.draw_green(occ)
        self.draw_infra()
        # scale bar
        sx = self.x1 - 120
        for i in range(5):
            ax.add_patch(Rectangle((sx + i * 10, ybot * E + 4.2 * E), 10, 0.8 * E, facecolor=INK if i % 2 == 0 else "white", edgecolor=INK, lw=0.5, zorder=30))
        for v in (0, 25, 50):
            ax.text(sx + v, ybot * E + 5.4 * E, f"{v}" + (" m" if v == 50 else ""), fontsize=8, ha="center", color=INK, zorder=30)
        ax.text(sx + 56, ybot * E + 4.2 * E, f"échelle verticale ×{self.ex:g}", fontsize=8, color=MUTED, zorder=30)
        # labels with leader lines
        ly0 = (top + 2) * E
        rows_end = [-1e9, -1e9, -1e9, -1e9]
        cw = 10.5 / self.k  # metres per character approx
        for pos, txt, col in sorted(self.labels):
            if not (self.x0 + 6 < pos < self.x1 - 6):
                continue
            wdt = max(len(t) for t in txt.split("\n")) * cw
            row = next((i for i, e in enumerate(rows_end) if pos - wdt / 2 > e + 2), 3)
            rows_end[row] = pos + wdt / 2
            ly = ly0 + row * 5.2 * E
            zl = self.top_at(pos)
            ax.plot([pos, pos], [zl + 1 * E, ly - 0.8 * E], color=col, lw=0.6, zorder=25)
            ax.add_patch(Circle((pos, zl + 1 * E), 0.55, color=col, zorder=26))
            ax.text(pos, ly, txt, fontsize=10, color=col, ha="center", va="bottom", fontweight="bold", zorder=26, linespacing=1.0,
                    bbox=dict(boxstyle="square,pad=0.15", fc=PAPER, ec="none", alpha=0.85))
        # zone band
        for a_, b_, t_, c_ in getattr(self, "zones", []):
            yb = ybot * E + 0.6 * E
            ax.add_patch(Rectangle((a_, yb), b_ - a_ - 1.5, 0.7 * E, facecolor=c_, edgecolor="none", zorder=29))
            ax.text((a_ + b_) / 2, yb + 1.3 * E, t_, fontsize=10, color=c_, ha="center", va="bottom", fontweight="bold", zorder=29)
        # height dimension
        for xh, zlo, zhi, t_ in getattr(self, "dims", []):
            ax.annotate("", xy=(xh, zlo), xytext=(xh, zhi), arrowprops=dict(arrowstyle="<->", color=TERRA, lw=0.8), zorder=27)
            ax.text(xh + 1.5, (zlo + zhi) / 2, t_, fontsize=9, color=TERRA, va="center", fontweight="bold", zorder=27, bbox=dict(boxstyle="square,pad=0.1", fc=PAPER, ec="none", alpha=0.8))
        fig.savefig(out, dpi=200, facecolor=PAPER); plt.close(fig); print("saved", out, W_, H_)

    def runs(self, mask):
        out = []; i = 0; n = len(mask)
        while i < n:
            if mask[i]:
                j = i
                while j < n and mask[j]:
                    j += 1
                out.append((i, j)); i = j
            else:
                i += 1
        return out

    def top_at(self, pos):
        return getattr(self, "_tops", {}).get(int(pos), self.zg(pos) * self.ex)

    # ---------------------------------------------------------------- roads
    def draw_roads(self, occ):
        ax = self.ax; E = self.ex
        for pos, w, c, nm in self.roads:
            z = self.zg(pos) * E
            a, b = pos - w / 2, pos + w / 2
            if w >= 7:
                sw = 2.5 if w < 15 else 4
                ax.add_patch(Rectangle((a, z - 0.6 * E), w, 0.6 * E, facecolor="#5D646A", edgecolor=INK, lw=0.4, zorder=13))
                for s0 in (a, b - sw):
                    ax.add_patch(Rectangle((s0, z), sw, 0.25 * E, facecolor="#D8D2C8", edgecolor=INK, lw=0.3, zorder=13))
                # cars
                lanes = max(1, int((w - 2 * sw) // 3.5))
                for k in range(lanes):
                    if self.rng.random() < 0.65:
                        cx = a + sw + 0.5 + k * 3.5 + self.rng.random() * 0.4
                        self.car(cx, z, flip=k % 2)
                if w >= 18:  # central reservation with trees
                    ax.add_patch(Rectangle((pos - 1.5, z), 3, 0.3 * E, facecolor=SAGE, edgecolor=INK, lw=0.3, zorder=13))
                    self.tree(pos, z + 0.3 * E, h=7, r=2.6, palm=True)
                if w >= 12:
                    for s0 in (a + sw / 2, b - sw / 2):
                        self.lamp(s0, z)
                        if self.rng.random() < 0.7:
                            self.person(s0 + (0.6 if s0 < pos else -0.6), z)
                if c in ("trunk", "primary", "secondary") and nm:
                    nn = " ".join([t for t in nm.split(" ") if t.isascii()][:3]).replace("Avenue", "Av.").replace("Boulevard", "Bd")
                    self.labels.append((pos, f"{nn}\n{w:.0f} m", INK))
                else:
                    self.labels.append((pos, f"rue · {w:.0f} m", MUTED))
            else:
                ax.add_patch(Rectangle((a, z - 0.3 * E), w, 0.3 * E, facecolor="#CFC6B8", edgecolor=INK, lw=0.3, zorder=13))
                if self.rng.random() < 0.6:
                    self.person(pos, z)

    # ---------------------------------------------------------------- built
    def draw_built(self, occ):
        ax = self.ax; E = self.ex; tops = {}
        seg = occ[self.x0:self.x1] == "built"
        for a, b in self.runs(seg):
            a += self.x0; b += self.x0
            x = a
            while x < b - 3:
                fl_min, fl_max, style = self.profile(x)
                w = float(self.rng.uniform(*((6, 10) if style == "medina" else (8, 15))))
                w = min(w, b - x)
                if w < 4:
                    break
                fl = int(self.rng.integers(fl_min, fl_max + 1))
                self.building(x, w, fl, style, tops)
                x += w
        self._tops = tops

    def building(self, x, w, floors, style, tops):
        ax = self.ax; E = self.ex
        zb = min(self.zg(x), self.zg(x + w)) * E
        zt = max(self.zg(x), self.zg(x + w)) * E
        fh = 3.0 * E
        h = floors * fh + (zt - zb)
        col = self.rng.choice(WHITEWASH if style == "medina" else FACADE)
        if style == "hotel":
            col = self.rng.choice(["#F3EDE3", "#E8E3DA", "#DDE3E4"])
        ax.add_patch(Rectangle((x, zb), w, h, facecolor=col, edgecolor=INK, lw=0.6, zorder=8))
        # shade side
        ax.add_patch(Rectangle((x + w - 0.8, zb), 0.8, h, facecolor="#00000014", edgecolor="none", zorder=8.1))
        # ground floor shop / door
        gf = zt
        if style in ("dense", "hotel", "ville"):
            ax.add_patch(Rectangle((x + 0.8, gf - (zt - zb) + 0.1 * E if False else zb), w - 1.6, min(2.6 * E, h * 0.3), facecolor="#8E7F6F" if style == "dense" else "#93A6AE", edgecolor=INK, lw=0.3, zorder=8.2))
        # windows
        wcol = "#7F96A0" if style != "medina" else "#5E6F78"
        for f in range(1 if style != "medina" else 0, floors):
            fy = zt + f * fh + 0.9 * E
            nwin = max(1, int((w - 1) // (3.2 if style != "medina" else 4.5)))
            for k in range(nwin):
                wx = x + (w / nwin) * (k + 0.5) - 0.6
                if style == "medina" and self.rng.random() < 0.45:
                    continue
                ww_ = 1.2 if style != "hotel" else 2.2
                ax.add_patch(Rectangle((wx, fy), ww_, 1.4 * E if style != "medina" else 0.9 * E, facecolor=wcol, edgecolor="none", zorder=8.3))
                if style in ("dense", "ville"):
                    ax.add_patch(Rectangle((wx - 0.35, fy), 0.3, 1.4 * E, facecolor="#C7B9A6", edgecolor="none", zorder=8.3))
                    ax.add_patch(Rectangle((wx + ww_ + 0.05, fy), 0.3, 1.4 * E, facecolor="#C7B9A6", edgecolor="none", zorder=8.3))
                if style == "dense" and self.rng.random() < 0.35:  # balcony with railing / laundry
                    ax.plot([wx - 0.5, wx + 1.7], [fy - 0.05 * E, fy - 0.05 * E], color=INK, lw=0.7, zorder=8.4)
                    for q in np.linspace(wx - 0.5, wx + 1.7, 5):
                        ax.plot([q, q], [fy - 0.05 * E, fy + 0.5 * E], color=INK, lw=0.3, zorder=8.4)
                    ax.plot([wx - 0.5, wx + 1.7], [fy + 0.5 * E, fy + 0.5 * E], color=INK, lw=0.4, zorder=8.4)
                if style == "dense" and self.rng.random() < 0.15:  # AC unit
                    ax.add_patch(Rectangle((wx + 1.4, fy + 0.2 * E), 0.7, 0.45 * E, facecolor="#E2E2DE", edgecolor=INK, lw=0.25, zorder=8.4))
                if style == "hotel" and self.rng.random() < 0.6:  # balcony glass
                    ax.add_patch(Rectangle((wx - 0.3, fy - 0.1 * E), 2.8, 0.45 * E, facecolor="#BFD0D6", edgecolor=INK, lw=0.3, zorder=8.4))
        if style in ("dense", "ville") and self.rng.random() < 0.6:
            awc = self.rng.choice([TERRA, OCHRE, SAGE, "#3E5A6E"])
            ax.add_patch(Polygon([(x + 0.6, zb + 2.6 * E), (x + w - 0.6, zb + 2.6 * E), (x + w - 0.2, zb + 2.1 * E), (x + 0.2, zb + 2.1 * E)], facecolor=awc, edgecolor=INK, lw=0.3, zorder=8.45))
        if style == "hotel":
            for f in range(1, floors):
                ax.plot([x, x + w], [zt + f * fh, zt + f * fh], color=INK, lw=0.35, zorder=8.4)
        if style == "medina" and self.rng.random() < 0.5:
            dc = self.rng.choice(["#4F6B7A", "#5E7F4F", "#7A4B3A"])
            ax.add_patch(Rectangle((x + w / 2 - 0.7, zb), 1.4, 1.8 * E, facecolor=dc, edgecolor="none", zorder=8.3))
            ax.add_patch(Ellipse((x + w / 2, zb + 1.8 * E), 1.4, 0.7 * E, facecolor=dc, edgecolor="none", zorder=8.3))
        if style == "medina" and self.rng.random() < 0.25:  # moucharabieh
            ax.add_patch(Rectangle((x + 1, zb + h * 0.55), 1.6, 1.2 * E, facecolor="#9C7A5B", edgecolor=INK, lw=0.3, zorder=8.35))
        # roof terrace elements
        rt = zb + h
        ax.plot([x, x + w], [rt + 0.35 * E, rt + 0.35 * E], color=INK, lw=0.5, zorder=8.5)
        ax.plot([x, x], [rt, rt + 0.35 * E], color=INK, lw=0.5, zorder=8.5); ax.plot([x + w, x + w], [rt, rt + 0.35 * E], color=INK, lw=0.5, zorder=8.5)
        r = self.rng.random()
        if r < 0.35:   # water tank
            ax.add_patch(Rectangle((x + w * 0.6, rt), 1.2, 0.9 * E, facecolor="#D5D7D6", edgecolor=INK, lw=0.4, zorder=8.5))
        elif r < 0.6:  # satellite dish
            ax.add_patch(Ellipse((x + w * 0.3, rt + 0.7 * E), 1.0, 0.8 * E, facecolor="#E9E9E6", edgecolor=INK, lw=0.4, zorder=8.5))
        elif r < 0.75 and style != "hotel":  # stair cabin
            ax.add_patch(Rectangle((x + 0.6, rt), 2.4, 2.2 * E, facecolor=col, edgecolor=INK, lw=0.5, zorder=8.5))
        for xi in range(int(x), int(x + w) + 1):
            tops[xi] = rt
        if style == "medina" and floors >= 3 and self.rng.random() < 0.025:  # minaret
            ax.add_patch(Rectangle((x + w / 2 - 1.5, rt), 3, 10 * E, facecolor="#F1EADF", edgecolor=INK, lw=0.6, zorder=8.6))
            ax.add_patch(Polygon([(x + w / 2 - 1.5, rt + 10 * E), (x + w / 2 + 1.5, rt + 10 * E), (x + w / 2, rt + 12 * E)], facecolor=SAGE, edgecolor=INK, lw=0.5, zorder=8.6))

    # ---------------------------------------------------------------- green & misc
    def draw_green(self, occ):
        ax = self.ax; E = self.ex
        for kind in ("tree", "green", "bare"):
            seg = occ[self.x0:self.x1] == kind
            for a, b in self.runs(seg):
                a += self.x0; b += self.x0
                if kind == "tree":
                    for x in np.arange(a + 2, b - 1, 5.5):
                        self.tree(x, self.zg(x) * E, h=float(self.rng.uniform(6, 11)), r=float(self.rng.uniform(2.5, 4)))
                elif kind == "green":
                    ax.fill_between(np.arange(a, b), [self.zg(x) * E for x in range(a, b)], [self.zg(x) * E + 0.4 * E for x in range(a, b)], color=SAGE, zorder=6)
                    for x in np.arange(a + 3, b - 2, 9):
                        if self.rng.random() < 0.6:
                            self.tree(x, self.zg(x) * E, h=float(self.rng.uniform(5, 8)), r=2.4)
                elif kind == "bare":
                    near_sea = (occ[max(0, a - 20):b + 20] == "sea").any()
                    col = "#E8D9B5" if near_sea else "#DDD2BE"
                    ax.fill_between(np.arange(a, b), [self.zg(x) * E for x in range(a, b)], [self.zg(x) * E + 0.3 * E for x in range(a, b)], color=col, zorder=6)
                    if near_sea:
                        for x in np.arange(a + 4, b - 3, 12):
                            self.parasol(x, self.zg(x) * E)

    def draw_infra(self):
        ax = self.ax; E = self.ex
        for pos, c in self.d["infra"]:
            if not (self.x0 < pos < self.x1):
                continue
            z = self.zg(pos) * E
            if c == "city_wall":
                ax.add_patch(Rectangle((pos - 3, z), 6, 11 * E, facecolor="#D9B48F", edgecolor=INK, lw=0.8, zorder=10))
                for k in range(3):
                    ax.add_patch(Rectangle((pos - 3 + k * 2.2, z + 11 * E), 1.3, 0.9 * E, facecolor="#D9B48F", edgecolor=INK, lw=0.5, zorder=10))
                self.labels.append((pos, "rempart", TERRA))
            elif c == "breakwater":
                ax.add_patch(Polygon([(pos - 8, -6 * E), (pos - 3, 2.5 * E), (pos + 3, 2.5 * E), (pos + 8, -6 * E)], facecolor="#B9B3A8", edgecolor=INK, lw=0.6, zorder=10))
                self.labels.append((pos, "digue", MUTED))

    def car(self, x, z, flip=0):
        ax = self.ax; E = self.ex
        col = self.rng.choice(["#E7E3DC", "#9AA6AE", "#C9B9A6", "#6C7A84", "#B5563C"])
        ax.add_patch(FancyBboxPatch((x, z + 0.25 * E), 2.8, 0.75 * E, boxstyle="round,pad=0,rounding_size=0.3", facecolor=col, edgecolor=INK, lw=0.35, zorder=14))
        ax.add_patch(FancyBboxPatch((x + 0.5, z + 0.95 * E), 1.6, 0.5 * E, boxstyle="round,pad=0,rounding_size=0.3", facecolor="#AFC0C7", edgecolor=INK, lw=0.3, zorder=14))

    def person(self, x, z, col=None):
        ax = self.ax; E = self.ex
        col = col or self.rng.choice(["#23303A", "#5C4A3D", "#3E5A6E", "#7B746B", "#B5563C"])
        h = float(self.rng.uniform(1.6, 1.85)) * E
        ax.add_patch(Rectangle((x - 0.22, z), 0.44, h * 0.82, facecolor=col, edgecolor="none", zorder=15))
        ax.add_patch(Ellipse((x, z + h * 0.9), 0.42, 0.22 * E, facecolor=col, edgecolor="none", zorder=15))

    def tree(self, x, z, h=8, r=3, palm=False):
        ax = self.ax; E = self.ex
        if palm:
            ax.plot([x, x], [z, z + h * E], color="#6B5A48", lw=1.0, zorder=11)
            for ang in np.linspace(-150, -30, 6):
                a = np.radians(ang)
                ax.plot([x, x + 2.8 * np.cos(a) * -1], [z + h * E, z + h * E + 1.2 * E * np.sin(-a) * 0.6], color=SAGE_D, lw=1.2, zorder=11)
            return
        ax.plot([x, x], [z, z + h * 0.45 * E], color="#6B5A48", lw=1.0, zorder=11)
        col = self.rng.choice([SAGE, "#8EA67F", "#6F8C66"])
        ax.add_patch(Ellipse((x, z + h * 0.65 * E), 2 * r, r * 1.5 * E, facecolor=col, edgecolor=SAGE_D, lw=0.5, alpha=0.95, zorder=11))

    def lamp(self, x, z):
        ax = self.ax; E = self.ex
        ax.plot([x, x], [z, z + 7 * E], color=INK, lw=0.6, zorder=12)
        ax.plot([x, x + 1.2], [z + 7 * E, z + 7 * E], color=INK, lw=0.6, zorder=12)

    def parasol(self, x, z):
        ax = self.ax; E = self.ex
        ax.plot([x, x], [z, z + 2.2 * E], color=INK, lw=0.5, zorder=12)
        ax.add_patch(Polygon([(x - 1.4, z + 2.0 * E), (x + 1.4, z + 2.0 * E), (x, z + 2.6 * E)], facecolor=self.rng.choice([TERRA, OCHRE, "#F4F1EC"]), edgecolor=INK, lw=0.4, zorder=12))
        self.person(x + 1.2, z)

    def boats(self, a, b, n=6):
        ax = self.ax; E = self.ex
        for x in np.linspace(a, b, n):
            ax.add_patch(Polygon([(x - 4, 0.2 * E), (x + 4, 0.2 * E), (x + 3, -0.6 * E), (x - 3, -0.6 * E)], facecolor="white", edgecolor=INK, lw=0.5, zorder=13))
            ax.plot([x, x], [0.2 * E, 9 * E], color=INK, lw=0.6, zorder=13)
            ax.add_patch(Polygon([(x + 0.2, 1.0 * E), (x + 0.2, 8.6 * E), (x + 3.4, 1.0 * E)], facecolor="#F7F5F0", edgecolor=INK, lw=0.4, zorder=13))
        ax.add_patch(Rectangle((a - 5, 0), b - a + 10, 0.5 * E, facecolor="#B9AE9D", edgecolor=INK, lw=0.4, zorder=12.5))


def run():
    # C1 : front de mer / corniche (vitrine)
    def prof1(x):
        return (6, 9, "hotel")
    s1 = Section("C1", (-5.7962, 35.7808), (-5.7998, 35.7748), exag=1.5, px_per_m=5.2, seed=3, profile=prof1)
    pass
    seg = s1.occ()
    first_bare = next((i for i, v in enumerate(seg) if v == "bare"), None)
    pass
    occ1 = s1.occ(); rd = [r_ for r_ in s1.roads if r_[1] >= 20]
    sea_end = max(i for i, v in enumerate(occ1) if v == "sea")
    av = rd[0][0] if rd else sea_end + 300
    s1.x0 = max(0, sea_end - 70)
    s1.zones = [(s1.x0, sea_end, "MER", SEA_D), (sea_end, av - 30, "PLAGE  ·  ACCÈS LIBRE", OCHRE), (av - 30, av + 20, "CORNICHE", TERRA), (av + 20, s1.d["n"], "FRONT HÔTELIER ET RÉSIDENTIEL  (R+6 À R+9)", TERRA)]
    s1.labels.append((av - 18, "promenade", TERRA))
    s1.dims = [(av + 40, s1.zg(av + 40) * 1.5, s1.zg(av + 40) * 1.5 + 8 * 3 * 1.5, "env. 24 m (R+7)")]
    s1.draw("maps/c1_corniche.png", "C1")
    # C2 : Beni Makada (ville vécue)
    s2 = Section("C2", (-5.8190, 35.7525), (-5.8130, 35.7525), exag=1.5, px_per_m=6.4, seed=5, profile=lambda x: (3, 5, "dense"))
    n2 = s2.d["n"]
    s2.zones = [(0, n2, "TISSU DENSE CONTINU  ·  R+3 À R+5  ·  RUES DE 4 À 12 M  ·  QUASI AUCUN ESPACE VERT", SLATE)]
    s2.dims = [(205, s2.zg(205) * 1.5, s2.zg(205) * 1.5 + 5 * 3 * 1.5, "env. 15 m (R+4)")]
    s2.draw("maps/c2_benimakada.png", "C2")
    # C3 : Kasbah -> port (médina)
    def prof3(x):
        if x < 540:
            return (2, 3, "medina")
        return (3, 6, "ville")
    s3 = Section("C3", (-5.8140, 35.7890), (-5.8030, 35.7878), exag=1.5, px_per_m=4.0, seed=7, profile=prof3)
    s3.labels += [(380, "derbs de 2 à 4 m", TERRA), (700, "esplanade", MUTED)]
    occ = s3.occ(); sea_idx = [i for i, v in enumerate(occ) if v == "sea"]
    n3 = s3.d["n"]; s0 = sea_idx[0] if sea_idx else n3
    s3.zones = [(0, 230, "KASBAH", TERRA), (230, 530, "MÉDINA", TERRA), (530, 620, "REMPART + BOULEVARD", INK), (620, s0, "PORT RECONVERTI", OCHRE), (s0, n3, "BASSIN", SEA_D)]
    s3.dims = [(560, s3.zg(560) * 1.5, s3.zg(100) * 1.5, "%d m de dénivelé" % round(s3.zg(100) - s3.zg(560)))]
    s3.draw("maps/c3_kasbah_port.png", "C3")


if __name__ == "__main__":
    run()
