# -*- coding: utf-8 -*-
"""Coupes urbaines semi-réalistes, à l'échelle 1:1 (pas d'exagération verticale).
Sol : enveloppe basse du MNT Copernicus GLO-30. Emprises, rues et nombre d'étages : OSM / Overture quand ils existent,
sinon gabarits relevés sur les vues aériennes et estimés (indiqués comme tels sur les planches)."""
import glob, os
import numpy as np, rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.font_manager as fm
from matplotlib.patches import Rectangle, Polygon, Circle, Ellipse, FancyBboxPatch, Wedge, PathPatch
from matplotlib.path import Path
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from pyproj import Transformer
from scipy.ndimage import map_coordinates, minimum_filter1d, gaussian_filter1d

for f in glob.glob(os.path.expanduser("~/.fonts/barlow*.ttf")):
    fm.fontManager.addfont(f)
CF = "Barlow Condensed"; plt.rcParams["font.family"] = CF
T4 = Transformer.from_crs(4326, 32630, always_xy=True)

PAPER = "#EFEBE3"; INK = "#23303A"; MUTED = "#7B746B"; TERRA = "#B5563C"; OCHRE = "#C9965A"; SAGE = "#7D9873"; SAGE_D = "#4F6B4A"
SEA = "#A8C0C6"; SEA_D = "#5F8796"; SLATE = "#3E5A6E"
EARTH_T = "#CDBA9C"; EARTH_B = "#A8916F"
USE = {"log": "#EADCC4", "sais": "#E9C3AE", "hot": "#DFA98F", "com": "#E8CF9C", "equip": "#C8D3D9", "park": "#D8D4CD", "vide": "#F3EFE8", "chantier": "#E3DDD3"}
USE_D = {k: tuple(np.array(to_rgb(v)) * 0.62) for k, v in USE.items()}
WALL = "#3B4249"


def mix(c, t=0.5, base=PAPER):
    a = np.array(to_rgb(c)); b = np.array(to_rgb(base)); return tuple(a * (1 - t) + b * t)


def ground_profile(a, b, win=50, sig=12):
    D = rasterio.open("u_dem20.tif"); A = D.read(1)
    p0 = T4.transform(*a); p1 = T4.transform(*b); n = int(np.hypot(p1[0] - p0[0], p1[1] - p0[1]))
    xs = np.linspace(p0[0], p1[0], n); ys = np.linspace(p0[1], p1[1], n); c, r = ~D.transform * (xs, ys)
    z = map_coordinates(A, [r - .5, c - .5], order=1)
    return gaussian_filter1d(minimum_filter1d(z, win), sig)


class Coupe:
    def __init__(self, zfun, x0, x1, zlo, zhi, seed=1):
        self.zfun = zfun; self.x0, self.x1, self.zlo, self.zhi = x0, x1, zlo, zhi; self.seed = seed
        self.items = []          # (callable) drawn in order
        self.labels = []         # (x, z_anchor, title, sub, color)
        self.dims = []           # boundaries for the dimension chain
        self.sea_until = None
        self.flats = []

    def zg(self, x):
        for a, b, z in self.flats:
            if a <= x <= b:
                return z
        return float(self.zfun(x))

    # -------------------------------------------------------------- rendering
    def render(self, out, ppm, xlim=None, zlim=None, labels=True, chain=True, frame=None):
        xa, xb = xlim or (self.x0, self.x1)
        za, zb = zlim or (self.zlo, self.zhi)
        band_top = 9.0 * 8 / ppm * (2 if labels else 0) if labels else 0
        top_extra = (250 / ppm) if labels else 0
        bot_extra = (60 / ppm) if chain else 0
        Wm = xb - xa; Hm = (zb - za) + top_extra + bot_extra
        fig = plt.figure(figsize=(Wm * ppm / 200, Hm * ppm / 200), dpi=200)
        ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(xa, xb); ax.set_ylim(za - bot_extra, zb + top_extra); ax.axis("off")
        fig.patch.set_facecolor(PAPER)
        self.ax = ax; self.ppm = ppm; self.rng = np.random.default_rng(self.seed)
        self.view = (xa, xb, za, zb)
        # sky
        sky = LinearSegmentedColormap.from_list("sky", ["#F3EEE5", "#E4E9E8", "#D9E3E5"])
        ax.imshow(np.linspace(0, 1, 256)[:, None], extent=(xa, xb, 0, zb), origin="lower", aspect="auto", cmap=sky, zorder=0)
        for fn in self.items:
            self.rng = np.random.default_rng(hash(fn.__name__ if hasattr(fn, "__name__") else 0) % 2**32 + self.seed)
            fn(self)
        if labels:
            ax.add_patch(Rectangle((xa, zb), xb - xa, top_extra + 5, facecolor=PAPER, edgecolor="none", zorder=50))
            ax.plot([xa, xb], [zb, zb], color="#D8D1C4", lw=0.6, zorder=50.5)
        if chain and self.dims:
            self.draw_chain(za - bot_extra)
        if labels:
            self.draw_labels(zb, top_extra)
        if frame:
            for (fa, fb_, fz0, fz1, n) in frame:
                ax.add_patch(Rectangle((fa, fz0), fb_ - fa, fz1 - fz0, fill=False, edgecolor=TERRA, lw=1.4, ls=(0, (4, 2)), zorder=90))
                ax.add_patch(Circle((fa, fz1), 2.6 * 8 / ppm * 1.4, color=TERRA, zorder=91))
                ax.text(fa, fz1, str(n), color="white", fontsize=10, ha="center", va="center", fontweight="bold", zorder=92)
        fig.savefig(out, dpi=200, facecolor=PAPER); plt.close(fig); print("saved", out)

    def lw(self, v):  # line width scaled with zoom
        return max(0.15, v * self.ppm / 8)

    # -------------------------------------------------------------- annotation
    def draw_labels(self, zb, extra):
        ax = self.ax; xa, xb, _, _ = self.view
        nrow = 3; rows = [-1e9] * nrow; u = 1 / self.ppm
        for x, za_, t, sub, col in sorted(self.labels):
            if not xa + 3 < x < xb - 3:
                continue
            w = max(len(t) * 15.5 * u, len(sub or "") * 10.5 * u) + 24 * u
            row = next((r for r in range(nrow) if x - w / 2 > rows[r]), nrow - 1)
            rows[row] = x + w / 2
            y = zb + extra - (34 + row * 74) * u
            ax.plot([x, x], [za_ + 1.0, y - (40 if sub else 12) * u], color=col, lw=0.6, zorder=60)
            ax.add_patch(Circle((x, za_ + 1.0), 4 * u, color=col, zorder=61))
            ax.text(x, y, t.upper(), fontsize=10.5, color=col, ha="center", va="center", fontweight="bold", zorder=62,
                    bbox=dict(boxstyle="square,pad=0.15", fc=PAPER, ec="none"))
            if sub:
                ax.text(x, y - 30 * u, sub, fontsize=8.8, color=MUTED, ha="center", va="center", zorder=62,
                        bbox=dict(boxstyle="square,pad=0.1", fc=PAPER, ec="none"))

    def draw_chain(self, ybase):
        ax = self.ax; xa, xb, _, _ = self.view
        y = ybase + 30 / self.ppm
        pts = sorted(self.dims); u = 8 / self.ppm
        ax.plot([max(pts[0], xa), min(pts[-1], xb)], [y, y], color=INK, lw=0.7, zorder=60)
        for i, x in enumerate(pts):
            if xa <= x <= xb:
                ax.plot([x - 1.0 * u, x + 1.0 * u], [y - 1.0 * u, y + 1.0 * u], color=INK, lw=1.0, zorder=60)
                ax.plot([x, x], [y - 2.2 * u, y + 2.2 * u], color=INK, lw=0.4, zorder=60)
            if i + 1 < len(pts):
                d = pts[i + 1] - x; xm = (x + pts[i + 1]) / 2
                if xa < xm < xb and d * self.ppm > 26:
                    ax.text(xm, y + 0.8 * u, f"{d:.0f}", fontsize=8.5, color=INK, ha="center", va="bottom", zorder=60)
        ax.text(min(pts[-1], xb) - 2 * u, y - 2.6 * u, "cotes en mètres", fontsize=7.5, color=MUTED, ha="right", va="top", zorder=60)

    def road(self, xa_, parts, z=None, name=None, sub=None, nets=True):
        """parts: list of (width, kind) with kind in sw, lane, lane-, park, med, medpalm, medtree, bike"""
        def fn(c):
            ax = c.ax; x = xa_
            for w, k in parts:
                zz = z if z is not None else c.zg(x + w / 2)
                if k == "sw":
                    ax.add_patch(Rectangle((x, zz), w, 0.18, facecolor="#D9D2C6", edgecolor=WALL, lw=c.lw(0.3), zorder=23))
                    if c.rng.random() < 0.8: c.person(x + w * c.rng.uniform(0.3, 0.7), zz + 0.18)
                elif k.startswith("lane") or k == "park":
                    ax.add_patch(Rectangle((x, zz - 0.35), w, 0.35, facecolor="#4C5257", edgecolor="none", zorder=23))
                    if k == "park" or c.rng.random() < 0.75:
                        c.car(x + (w - 4.3) / 2, zz, face=(-1 if k == "lane-" else 1))
                elif k.startswith("med"):
                    ax.add_patch(Rectangle((x, zz), w, 0.25, facecolor="#9DB08C", edgecolor=WALL, lw=c.lw(0.3), zorder=23))
                    if k == "medpalm": c.palm(x + w / 2, zz + 0.25, h=10)
                    if k == "medtree": c.tree(x + w / 2, zz + 0.25, h=7, r=2.4)
                elif k == "bike":
                    ax.add_patch(Rectangle((x, zz - 0.2), w, 0.2, facecolor="#B07A62", edgecolor="none", zorder=23))
                x += w
            if nets:
                zz = c.zg(xa_ + 3)
                for dx, dz, r, col in ((0.3, -1.8, 0.35, "#5F8796"), (0.55, -2.6, 0.55, "#8C6E52"), (0.8, -1.4, 0.18, "#C9965A")):
                    xx = xa_ + (x - xa_) * dx
                    ax.add_patch(Circle((xx, c.zg(xx) + dz), r, facecolor=col, edgecolor=WALL, lw=c.lw(0.3), zorder=6))
            if name:
                c.label((xa_ + x) / 2, (z if z is not None else c.zg((xa_ + x) / 2)) + 1.6, name, sub, INK)
        fn.__name__ = f"r{xa_:.0f}"; self.items.append(fn)

    def label(self, x, z, t, sub=None, col=INK):
        self.labels.append((x, z, t, sub, col))

    # -------------------------------------------------------------- terrain
    def terrain(self, xs=None, sea_until=None, shore=None):
        """Ground cut: earth poché with strata; optional sea up to x=sea_until."""
        def fn(c):
            ax = c.ax; xa, xb, za, zb = c.view
            X = np.linspace(c.x0, c.x1, 1500)
            Z = np.array([c.zg(x) for x in X])
            bottom = c.zlo - 50
            # earth gradient clipped to polygon
            poly = Polygon(np.r_[np.c_[X, Z], [[c.x1, bottom], [c.x0, bottom]]], closed=True, facecolor="none", edgecolor="none")
            ax.add_patch(poly)
            cm = LinearSegmentedColormap.from_list("e", [EARTH_B, EARTH_T])
            im = ax.imshow(np.linspace(0, 1, 256)[:, None], extent=(c.x0, c.x1, bottom, max(Z) + 1), origin="lower", aspect="auto", cmap=cm, zorder=5)
            im.set_clip_path(poly)
            # hatch strata
            for k in range(1, 9):
                ax.plot(X, Z - k * 1.6 - 0.25 * np.sin(X / (11 + k)), color="#9C8564", lw=c.lw(0.35), alpha=0.55, zorder=5.2)
            # stones
            rng = np.random.default_rng(4)
            for _ in range(int((c.x1 - c.x0) * 0.6)):
                x = rng.uniform(c.x0, c.x1); d = rng.uniform(0.6, 12)
                ax.add_patch(Ellipse((x, c.zg(x) - d), rng.uniform(0.2, 0.6), rng.uniform(0.15, 0.35), color="#8F7859", alpha=0.45, lw=0, zorder=5.3))
            ax.plot(X, Z, color=INK, lw=c.lw(1.6), zorder=40, solid_capstyle="round")
        fn.__name__ = "terrain"; self.items.append(fn)

    def sea(self, xa_, xb_, depth=8):
        def fn(c):
            ax = c.ax
            cm = LinearSegmentedColormap.from_list("s", ["#557F8E", "#7FA2AE", "#B4CBD0"])
            poly = Polygon([(xa_, 0), (xb_, 0), (xb_, -depth - 30), (xa_, -depth - 30)], facecolor="none", edgecolor="none"); ax.add_patch(poly)
            im = ax.imshow(np.linspace(0, 1, 256)[:, None], extent=(xa_, xb_, -depth - 30, 0), origin="lower", aspect="auto", cmap=cm, zorder=4.5)
            im.set_clip_path(poly)
            ax.plot([xa_, xb_], [0, 0], color=SEA_D, lw=c.lw(1.0), zorder=6)
            rng = np.random.default_rng(9)
            for _ in range(int((xb_ - xa_) * 0.5)):
                x = rng.uniform(xa_, xb_); z = rng.uniform(-depth, -0.3)
                ax.plot([x, x + rng.uniform(1, 3)], [z, z], color="white", lw=c.lw(0.4), alpha=0.5, zorder=4.6)
            # surface waves
            xs = np.linspace(xa_, xb_, 600)
            ax.plot(xs, 0.12 * np.sin(xs * 1.7), color="white", lw=c.lw(0.6), alpha=0.8, zorder=6)
        fn.__name__ = f"sea{xa_}"; self.items.append(fn)

    # -------------------------------------------------------------- background
    def backdrop(self, kind="city", seed=2, hmin=10, hmax=30, base=None, color="#D5D2CB", layer=1, x0=None, x1=None, alpha=1.0, minaret=None):
        def fn(c):
            ax = c.ax; rng = np.random.default_rng(seed)
            a = x0 if x0 is not None else c.x0; b = x1 if x1 is not None else c.x1
            x = a
            col = mix(color, 0.0)
            while x < b:
                w = rng.uniform(8, 22) if kind == "city" else rng.uniform(5, 10)
                h = rng.uniform(hmin, hmax)
                zb_ = base(x) if callable(base) else c.zg(x) + (base or 0)
                ax.add_patch(Rectangle((x, zb_ - 2), w - 0.4, h + 2, facecolor=col, edgecolor=mix(col, -0.0, "#B9B4AA"), lw=c.lw(0.3), zorder=1 + layer * 0.1, alpha=alpha))
                # windows grid (dots)
                if c.ppm > 3:
                    for fz in np.arange(zb_ + 3, zb_ + h - 1.5, 3.0):
                        for fx in np.arange(x + 1.2, x + w - 1.5, 2.6 if kind == "city" else 3.5):
                            if rng.random() < 0.8:
                                ax.add_patch(Rectangle((fx, fz), 0.9, 1.2, facecolor=mix(col, 0.0, "#A9AEB0"), lw=0, zorder=1.05 + layer * 0.1, alpha=alpha * 0.8))
                if kind == "medina" and rng.random() < 0.3:
                    ax.add_patch(Rectangle((x + w * 0.5, zb_ + h), 1.0, 0.8, facecolor=col, lw=0, zorder=1 + layer * 0.1))
                x += w
            if minaret:
                for mx, mz, mh in minaret:
                    ax.add_patch(Rectangle((mx - 2.2, mz), 4.4, mh, facecolor=col, edgecolor=mix(col, 0, "#B9B4AA"), lw=c.lw(0.4), zorder=1.02 + layer * 0.1))
                    ax.add_patch(Rectangle((mx - 1.3, mz + mh), 2.6, mh * 0.18, facecolor=col, edgecolor=mix(col, 0, "#B9B4AA"), lw=c.lw(0.4), zorder=1.02 + layer * 0.1))
                    ax.plot([mx, mx], [mz + mh * 1.18, mz + mh * 1.32], color="#B9B4AA", lw=c.lw(0.6), zorder=1.02 + layer * 0.1)
                    for k in range(3):
                        ax.add_patch(Circle((mx, mz + mh * 1.21 + k * 0.9), 0.35, color="#B9B4AA", zorder=1.03 + layer * 0.1))
        fn.__name__ = f"bg{seed}"; self.items.append(fn)

    def hills(self, pts, color="#D7DAD6", z=0.8):
        def fn(c):
            xs, zs = zip(*pts)
            c.ax.fill_between(xs, -5, zs, color=color, lw=0, zorder=z)
        fn.__name__ = "hills"; self.items.append(fn)

    # -------------------------------------------------------------- objects
    def person(self, x, z, h=1.72, col=None, sit=False, kid=False, face=1):
        ax = self.ax; col = col or self.rng.choice(["#2B3A44", "#5A4636", "#3E5A6E", "#7A5A4A", "#8B3E2F", "#56614F", "#6B6F73"])
        if kid: h = 1.15
        if sit:
            ax.add_patch(Polygon([(x - 0.18, z + 0.45), (x + 0.2, z + 0.45), (x + 0.2, z + 0.95), (x - 0.15, z + 0.95)], color=col, lw=0, zorder=self.zp))
            ax.add_patch(Polygon([(x + 0.2, z + 0.45), (x + 0.55 * face, z + 0.45), (x + 0.55 * face, z), (x + 0.45 * face, z), (x + 0.45 * face, z + 0.35), (x, z + 0.35)], color=col, lw=0, zorder=self.zp))
            ax.add_patch(Circle((x + 0.02, z + 1.1), 0.12, color=col, lw=0, zorder=self.zp))
            return
        s = h / 1.72
        body = [(x - 0.2 * s, z + 0.93 * s), (x - 0.23 * s, z + 1.42 * s), (x - 0.1 * s, z + 1.5 * s), (x + 0.1 * s, z + 1.5 * s), (x + 0.23 * s, z + 1.42 * s), (x + 0.2 * s, z + 0.93 * s)]
        ax.add_patch(Polygon(body, color=col, lw=0, zorder=self.zp))
        st = self.rng.uniform(0.05, 0.22) * s
        ax.add_patch(Polygon([(x - 0.17 * s, z + 0.95 * s), (x - 0.04 * s, z + 0.95 * s), (x - st, z), (x - st - 0.1 * s, z)], color=col, lw=0, zorder=self.zp))
        ax.add_patch(Polygon([(x + 0.17 * s, z + 0.95 * s), (x + 0.04 * s, z + 0.95 * s), (x + st, z), (x + st + 0.1 * s, z)], color=col, lw=0, zorder=self.zp))
        ax.add_patch(Circle((x, z + 1.6 * s), 0.115 * s, color=col, lw=0, zorder=self.zp))

    zp = 30

    def car(self, x, z, col=None, L=4.3, face=1):
        ax = self.ax; col = col or self.rng.choice(["#E9E6E0", "#A7B1B7", "#6E7B84", "#B5563C", "#2F3B44", "#C9B79E"])
        H = 1.45
        pts = [(0, 0.3), (0, 0.85), (0.15, 0.95), (0.95, 1.0), (1.45, 1.42), (3.0, 1.45), (3.65, 0.98), (4.2, 0.9), (4.3, 0.6), (4.3, 0.3)]
        if face < 0: pts = [(L - a, b) for a, b in pts]
        ax.add_patch(Polygon([(x + a, z + b) for a, b in pts], facecolor=col, edgecolor=INK, lw=self.lw(0.25), zorder=self.zp))
        win = [(1.55, 1.0), (1.6, 1.0), (1.75, 1.33), (2.95, 1.36), (3.45, 1.0)]
        if face < 0: win = [(L - a, b) for a, b in win]
        ax.add_patch(Polygon([(x + a, z + b) for a, b in win], facecolor="#B8C8CE", edgecolor="none", zorder=self.zp + 0.1))
        for wx in (0.85, 3.35):
            wx = wx if face > 0 else L - wx
            ax.add_patch(Circle((x + wx, z + 0.32), 0.32, facecolor="#2A2F33", edgecolor="none", zorder=self.zp + 0.2))
            ax.add_patch(Circle((x + wx, z + 0.32), 0.14, facecolor="#9AA1A5", edgecolor="none", zorder=self.zp + 0.3))

    def tree(self, x, z, h=8.0, r=3.0, cols=None, zo=None):
        ax = self.ax; zo = zo or 26
        cols = cols or [SAGE_D, "#6E8B63", SAGE, "#9AB08A"]
        ax.add_patch(Polygon([(x - 0.22, z), (x + 0.22, z), (x + 0.12, z + h * 0.55), (x - 0.12, z + h * 0.55)], color="#5E4C3B", lw=0, zorder=zo))
        cz = z + h - r * 0.95
        for k in range(14):
            a = self.rng.uniform(0, 2 * np.pi); d = self.rng.uniform(0, r * 0.55)
            rr = self.rng.uniform(r * 0.38, r * 0.62)
            ci = min(3, int(k / 14 * 4))
            ax.add_patch(Circle((x + d * np.cos(a), cz + d * np.sin(a) * 0.8 + (ci - 1.5) * r * 0.08), rr, color=cols[ci], alpha=0.93, lw=0, zorder=zo + 0.01 * k))

    def palm(self, x, z, h=11):
        ax = self.ax
        t = np.linspace(0, 1, 20); bend = 0.35 * np.sin(t * np.pi / 2)
        ax.fill_betweenx(z + t * h, x + bend - 0.22 + 0.06 * t, x + bend + 0.22 - 0.06 * t, color="#7A6550", lw=0, zorder=26)
        tx, tz = x + bend[-1], z + h
        ax.add_patch(Ellipse((tx, tz - 0.9), 0.9, 1.8, color="#8A7860", zorder=26.1))
        for ang in np.linspace(-170, -10, 11):
            a = np.radians(ang + self.rng.uniform(-6, 6)); L = self.rng.uniform(2.8, 3.8)
            s = np.linspace(0, 1, 12)
            px_ = tx + np.cos(a) * L * s; pz_ = tz - np.sin(a) * L * s * 0.55 - 1.4 * s ** 2 * L / 3.5
            ax.plot(px_, pz_, color=SAGE_D, lw=self.lw(2.2), solid_capstyle="round", zorder=26.2)
            for k in range(2, 12, 2):
                ax.plot([px_[k], px_[k] + 0.25 * np.cos(a - 0.9)], [pz_[k], pz_[k] - 0.45], color="#6E8B63", lw=self.lw(0.8), zorder=26.15)

    def lamp(self, x, z, h=8, arm=1):
        ax = self.ax
        ax.plot([x, x], [z, z + h], color=WALL, lw=self.lw(0.9), zorder=27)
        ax.plot([x, x + 1.2 * arm], [z + h, z + h + 0.2], color=WALL, lw=self.lw(0.9), zorder=27)
        ax.add_patch(Rectangle((x + 1.0 * arm - 0.3, z + h - 0.15), 0.6, 0.2, color=WALL, zorder=27))

    def bench(self, x, z):
        ax = self.ax
        ax.add_patch(Rectangle((x - 0.9, z + 0.42), 1.8, 0.08, color=WALL, zorder=27))
        for k in (-0.8, 0.8):
            ax.plot([x + k, x + k], [z, z + 0.45], color=WALL, lw=self.lw(0.7), zorder=27)

    def parasol(self, x, z, col=None):
        ax = self.ax; col = col or self.rng.choice([TERRA, OCHRE, "#F5F1E9", SLATE])
        ax.plot([x, x], [z, z + 2.3], color=WALL, lw=self.lw(0.6), zorder=27)
        ax.add_patch(Polygon([(x - 1.3, z + 2.05), (x, z + 2.55), (x + 1.3, z + 2.05)], facecolor=col, edgecolor=WALL, lw=self.lw(0.3), zorder=27))

    def furniture(self, x0, x1, zf, hfl, use):
        """silhouettes inside one floor of a cut building"""
        ax = self.ax; dc = USE_D[use]
        w = x1 - x0
        n = max(1, int(w / 6))
        for k in range(n):
            cx = x0 + (k + 0.5) * w / n + self.rng.uniform(-1, 1)
            r = self.rng.random()
            if use in ("com",):
                ax.add_patch(Rectangle((cx - 0.4, zf), 0.8, 0.75, color=dc, lw=0, zorder=21))
                ax.add_patch(Rectangle((cx - 0.5, zf + 0.72), 1.0, 0.06, color=dc, lw=0, zorder=21))
                if r < 0.8: self.zp = 21.5; self.person(cx + 0.9, zf, sit=True, col=dc, face=-1); self.zp = 30
                if r < 0.5: self.zp = 21.5; self.person(cx - 0.9, zf, sit=True, col=dc); self.zp = 30
            elif use in ("park",):
                if r < 0.75: self.zp = 21.5; self.car(cx - 2, zf, col=mix(dc, 0.35)); self.zp = 30
            elif use in ("equip",):
                ax.add_patch(Rectangle((cx - 0.6, zf), 1.2, 0.75, color=dc, lw=0, zorder=21))
                if r < 0.9: self.zp = 21.5; self.person(cx + 1.3, zf, kid=True, col=dc); self.zp = 30
            elif use in ("chantier", "vide"):
                pass
            else:
                if r < 0.35:   # bed
                    ax.add_patch(Rectangle((cx - 1.0, zf), 2.0, 0.5, color=dc, lw=0, zorder=21))
                    ax.add_patch(Rectangle((cx - 1.0, zf), 0.1, 0.95, color=dc, lw=0, zorder=21))
                elif r < 0.6:  # table + people
                    ax.add_patch(Rectangle((cx - 0.5, zf + 0.72), 1.0, 0.06, color=dc, lw=0, zorder=21))
                    ax.plot([cx, cx], [zf, zf + 0.72], color=dc, lw=self.lw(0.8), zorder=21)
                    self.zp = 21.5; self.person(cx - 0.9, zf, sit=True, col=dc); self.zp = 30
                elif r < 0.85:  # sofa + person standing
                    ax.add_patch(Rectangle((cx - 0.9, zf), 1.8, 0.45, color=dc, lw=0, zorder=21))
                    ax.add_patch(Rectangle((cx + 0.75, zf), 0.15, 0.85, color=dc, lw=0, zorder=21))
                    if use != "sais": self.zp = 21.5; self.person(cx - 1.6, zf, col=dc); self.zp = 30
                else:          # kitchen counter
                    ax.add_patch(Rectangle((cx - 0.9, zf), 1.8, 0.9, color=dc, lw=0, zorder=21))
                    ax.add_patch(Rectangle((cx - 0.9, zf + 1.6), 1.8, 0.6, color=dc, lw=0, zorder=21))
            # ceiling lamp
            ax.plot([cx, cx], [zf + hfl - 0.3, zf + hfl - 0.75], color=dc, lw=self.lw(0.4), zorder=21)
            ax.add_patch(Wedge((cx, zf + hfl - 0.85), 0.25, 0, 180, color=dc, lw=0, zorder=21))

    # -------------------------------------------------------------- buildings (cut)
    def building(self, x0, x1, floors, uses=None, gf=4.0, fh=3.0, base=None, basement=0, roof="flat", balcony=None,
                 facade=None, shutters_closed=0.0, cantilever=0.0, rebar=False, label=None, unfinished=False, wall=0.3, step=False):
        """A building cut by the section plane. uses: list per level from ground (len floors+1)."""
        zb0 = base if base is not None else (float(self.zfun((x0 + x1) / 2)) if step else min(float(self.zfun(x0)), float(self.zfun(x1))))
        self.flats.append((x0 - 0.3, x1 + 0.3, zb0))
        cl, cr = cantilever if isinstance(cantilever, tuple) else (cantilever, cantilever)
        def fn(c):
            ax = c.ax; zb = zb0
            us = uses or (["com"] + ["log"] * floors)
            levels = []
            z = zb
            for k in range(floors + 1):
                h = gf if k == 0 else fh
                levels.append((z, h, us[min(k, len(us) - 1)])); z += h
            ztop = z
            # basement
            for k in range(basement):
                zbk = zb - (k + 1) * 3.0
                ax.add_patch(Rectangle((x0, zbk), x1 - x0, 3.0, facecolor=USE["park"], edgecolor="none", zorder=20))
                c.furniture(x0 + 1, x1 - 1, zbk + 0.3, 3.0, "park")
                ax.add_patch(Rectangle((x0, zbk), x1 - x0, 0.3, color=WALL, zorder=22))
            if basement:
                ax.add_patch(Rectangle((x0 - 0.3, zb - basement * 3.0 - 0.5), 0.3, basement * 3.0 + 0.5, color=WALL, zorder=22))
                ax.add_patch(Rectangle((x1, zb - basement * 3.0 - 0.5), 0.3, basement * 3.0 + 0.5, color=WALL, zorder=22))
                ax.add_patch(Rectangle((x0 - 0.3, zb - basement * 3.0 - 0.5), x1 - x0 + 0.6, 0.5, color=WALL, zorder=22))
            for k, (z, h, u) in enumerate(levels):
                xi0 = x0 - (cl if k > 0 else 0); xi1 = x1 + (cr if k > 0 else 0)
                ax.add_patch(Rectangle((xi0, z), xi1 - xi0, h, facecolor=USE[u], edgecolor="none", zorder=20))
                # back wall shading (interior depth)
                ax.add_patch(Rectangle((xi0, z + h * 0.82), xi1 - xi0, h * 0.18 - 0.25, facecolor="#00000010", edgecolor="none", zorder=20.2))
                c.furniture(xi0 + 1.2, xi1 - 1.2, z + 0.25, h, u)
                # slab
                ax.add_patch(Rectangle((xi0, z + h - 0.28), xi1 - xi0, 0.28, color=WALL, zorder=22))
                if k > 0 and u not in ("park",):
                    rngp = np.random.default_rng(int(x0 * 10) + k)
                    px_ = xi0 + rngp.uniform(4, 7)
                    while px_ < xi1 - 3:
                        door = rngp.random() < 0.5
                        ax.add_patch(Rectangle((px_, z + (2.1 if door else 0)), 0.14, h - 0.28 - (2.1 if door else 0), color=mix(WALL, 0.25), zorder=21.8))
                        px_ += rngp.uniform(4.5, 8)
                # facade walls with window openings
                for wx, side in ((xi0, 1), (xi1 - wall, -1)):
                    if k == 0 and u == "com":
                        ax.add_patch(Rectangle((wx, z + h - 0.9), wall, 0.62, color=WALL, zorder=22))
                        ax.plot([wx + wall / 2, wx + wall / 2], [z, z + h - 0.9], color="#8FB0BB", lw=c.lw(1.2), zorder=22)
                    else:
                        sill = 0.9 if u != "hot" or wall > 0.4 else 0.3
                        ax.add_patch(Rectangle((wx, z), wall, sill, color=WALL, zorder=22))
                        ax.add_patch(Rectangle((wx, z + sill + 1.5 if u != "hot" else z + 2.4), wall, h - (sill + 1.5 if u != "hot" else 2.4), color=WALL, zorder=22))
                        closed = c.rng.random() < shutters_closed
                        ax.plot([wx + wall / 2, wx + wall / 2], [z + sill, z + (sill + 1.5 if u != "hot" else 2.4)], color="#8D7C66" if closed else "#8FB0BB", lw=c.lw(2.2 if closed else 1.2), zorder=22)
                    # balcony
                    if balcony and k > 0 and side == balcony[0] and c.rng.random() < balcony[1]:
                        bx = xi0 - 1.4 if side == 1 else xi1
                        ax.add_patch(Rectangle((bx, z - 0.28 + 0.0), 1.4, 0.2, color=WALL, zorder=22))
                        if balcony[2] == "glass":
                            ax.add_patch(Rectangle((bx if side == 1 else bx + 1.35, z - 0.08), 0.06, 1.05, color="#7FA6B3", zorder=22))
                            ax.add_patch(Rectangle((bx, z - 0.08), 1.4, 1.05, color="#A9C6CF", alpha=0.35, zorder=21.9))
                        else:
                            for q in np.linspace(bx + 0.1, bx + 1.3, 5):
                                ax.plot([q, q], [z - 0.08, z + 0.95], color=WALL, lw=c.lw(0.35), zorder=22)
                            ax.plot([bx, bx + 1.4], [z + 0.95, z + 0.95], color=WALL, lw=c.lw(0.6), zorder=22)
                        if balcony[2] != "glass" and c.rng.random() < 0.4:  # laundry
                            for q in np.linspace(bx + 0.2, bx + 1.2, 3):
                                ax.add_patch(Rectangle((q, z + 1.2), 0.25, 0.5, color=c.rng.choice([TERRA, "#F2F0EA", SLATE, OCHRE]), zorder=22))
                        if c.rng.random() < 0.3 and balcony[2] != "glass":
                            c.zp = 23; c.person(bx + 0.7, z - 0.08); c.zp = 30
                if k == 0 and u == "com":
                    # awning
                    for side in (1, -1):
                        bx = x0 if side == 1 else x1
                        ax.add_patch(Polygon([(bx, z + h - 0.7), (bx - 1.6 * side, z + h - 1.3), (bx - 1.6 * side, z + h - 1.5), (bx, z + h - 1.1)], color=c.rng.choice([TERRA, OCHRE, SLATE]), zorder=23))
            # roof
            if roof == "flat":
                for wx in (x0 - cl, x1 + cr - wall):
                    ax.add_patch(Rectangle((wx, ztop - 0.28), wall, 1.1, color=WALL, zorder=22))
                r = c.rng.random(); xm = (x0 + x1) / 2
                ax.add_patch(Rectangle((xm + 1.5, ztop), 1.4, 1.4, facecolor="#D9DAD6", edgecolor=WALL, lw=c.lw(0.3), zorder=22))  # tank
                ax.add_patch(Polygon([(xm - 3, ztop), (xm - 1.2, ztop), (xm - 1.2, ztop + 1.3)], facecolor="#9BB3BE", edgecolor=WALL, lw=c.lw(0.3), zorder=22))  # solar heater
                ax.add_patch(Ellipse((xm + 4.2, ztop + 1.1), 0.25, 1.0, angle=-25, facecolor="#ECEBE6", edgecolor=WALL, lw=c.lw(0.3), zorder=22))  # dish
                ax.plot([xm + 4.2, xm + 4.4], [ztop, ztop + 1.0], color=WALL, lw=c.lw(0.4), zorder=22)
                if x1 - x0 > 10 and r < 0.6:  # rooftop room / stair cabin
                    rx = x0 + 1.0 if r < 0.3 else x1 - 4.5
                    ax.add_patch(Rectangle((rx, ztop), 3.5, 2.5, facecolor=USE["vide"], edgecolor=WALL, lw=c.lw(0.8), zorder=21.5))
                if rebar:
                    for q in np.arange(x0 + 0.3, x1 - 0.2, 3.6):
                        for dq in (0, 0.25):
                            ax.plot([q + dq, q + dq], [ztop + 0.8, ztop + 2.4], color="#6B4B3A", lw=c.lw(0.5), zorder=22)
                        ax.add_patch(Rectangle((q - 0.05, ztop + 0.8), 0.4, 0.9, color="#9C9890", zorder=21.9))
                if c.rng.random() < 0.5:
                    for q in np.linspace(x0 + 2, x0 + 5, 4):
                        ax.add_patch(Rectangle((q, ztop + 1.1), 0.35, 0.6, color=c.rng.choice([TERRA, "#F2F0EA", SLATE]), zorder=22))
                    ax.plot([x0 + 1.8, x0 + 5.6], [ztop + 1.75, ztop + 1.75], color=WALL, lw=c.lw(0.3), zorder=22)
            if unfinished:  # top floor in hollow brick, no render
                z, h, u = levels[-1]
                for bz in np.arange(z + 0.2, z + h - 0.3, 0.45):
                    for bxx in (x0, x1 - wall):
                        ax.add_patch(Rectangle((bxx, bz), wall, 0.38, color="#B86A4B", zorder=22.1))
            if label:
                c.label((x0 + x1) / 2, ztop + 2, *label)
        fn.__name__ = f"b{x0:.0f}"; self.items.append(fn)

    def elev(self, x0, x1, h, base=None, col="#E7E1D6", win=(1.2, 1.5, 3.0), gf=4.0, zo=10, arches=False, shade=0.0, balcons=False):
        """A building seen in elevation behind the cut plane."""
        def fn(c):
            ax = c.ax; zb = base if base is not None else min(c.zg(x0), c.zg(x1)) - 0.5
            cc = mix(col, shade, "#BFC3C3")
            ax.add_patch(Rectangle((x0, zb), x1 - x0, h, facecolor=cc, edgecolor=mix(WALL, 0.55), lw=c.lw(0.5), zorder=zo))
            wcol = mix("#7F97A1", shade * 0.8, "#BFC3C3")
            ww, wh, sp = win
            nwin = max(1, int((x1 - x0 - 1) // sp))
            for fz in np.arange(zb + gf + 0.9, zb + h - 1.6, 3.0):
                for k in range(nwin):
                    wx = x0 + (x1 - x0) / nwin * (k + 0.5) - ww / 2
                    ax.add_patch(Rectangle((wx, fz), ww, wh, facecolor=wcol, lw=0, zorder=zo + 0.1))
                    if balcons and k % 2 == 0:
                        ax.add_patch(Rectangle((wx - 0.4, fz - 0.15), ww + 0.8, 0.5, facecolor=mix(cc, 0.0, "#9DA3A6"), lw=0, zorder=zo + 0.15))
            if arches:
                for k in range(nwin):
                    wx = x0 + (x1 - x0) / nwin * (k + 0.5)
                    ax.add_patch(Rectangle((wx - 1.0, zb), 2.0, 2.5, facecolor=mix("#6C6A66", shade), lw=0, zorder=zo + 0.1))
                    ax.add_patch(Wedge((wx, zb + 2.5), 1.0, 0, 180, facecolor=mix("#6C6A66", shade), lw=0, zorder=zo + 0.1))
            else:
                ax.add_patch(Rectangle((x0 + 0.5, zb + 0.5), x1 - x0 - 1, gf - 1.4, facecolor=mix("#8C8A84", shade + 0.2), lw=0, zorder=zo + 0.1))
            ax.add_patch(Rectangle((x0, zb + h), x1 - x0, 0.9, facecolor=cc, edgecolor=mix(WALL, 0.55), lw=c.lw(0.4), zorder=zo))
        fn.__name__ = f"e{x0:.0f}"; self.items.append(fn)

    def custom(self, f):
        self.items.append(f)


    def bus(self, x, z, col="#E9E4DA"):
        ax = self.ax
        ax.add_patch(FancyBboxPatch((x, z + 0.4), 12, 3.0, boxstyle="round,pad=0,rounding_size=0.4", facecolor=col, edgecolor=WALL, lw=self.lw(0.4), zorder=self.zp))
        for k in range(7):
            ax.add_patch(Rectangle((x + 0.8 + k * 1.6, z + 1.9), 1.3, 1.1, facecolor="#9FB6BE", lw=0, zorder=self.zp + 0.1))
        ax.add_patch(Rectangle((x, z + 1.0), 12, 0.35, facecolor=TERRA, lw=0, zorder=self.zp + 0.1))
        for wx in (2.2, 9.5):
            ax.add_patch(Circle((x + wx, z + 0.45), 0.5, color="#2A2F33", zorder=self.zp + 0.2))

    def yacht(self, x, L=12, col="#F5F2EC"):
        ax = self.ax
        ax.add_patch(Polygon([(x, 1.2), (x + L, 1.6), (x + L * 0.92, -0.5), (x + L * 0.1, -0.5)], facecolor=col, edgecolor=WALL, lw=self.lw(0.4), zorder=8))
        ax.add_patch(Polygon([(x + L * 0.25, 1.25), (x + L * 0.3, 2.6), (x + L * 0.7, 2.6), (x + L * 0.8, 1.45)], facecolor=col, edgecolor=WALL, lw=self.lw(0.4), zorder=8))
        ax.add_patch(Rectangle((x + L * 0.35, 1.8), L * 0.3, 0.45, facecolor="#5E7D8A", lw=0, zorder=8.1))
        ax.plot([x + L * 0.5, x + L * 0.5], [2.6, 2.6 + L * 1.1], color=WALL, lw=self.lw(0.5), zorder=8)
