# -*- coding: utf-8 -*-
"""Croquis à l'encre et lavis (style carnet) de lieux de Tanger, PNG transparents."""
import glob, os, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.font_manager as fm
from matplotlib.patches import Polygon, Rectangle, Circle, Ellipse, Arc, Wedge, PathPatch
from matplotlib.path import Path

for f in glob.glob(os.path.expanduser("~/.fonts/barlow*.ttf")):
    fm.fontManager.addfont(f)
plt.rcParams["font.family"] = "Barlow Condensed"
INKC = "#2B3640"
W_TERRA = "#C97B5E"; W_OCHRE = "#D8AE72"; W_SEA = "#8FB2BC"; W_SAGE = "#93AA86"; W_SAND = "#E7D3B1"; W_GREEN = "#5F8B6E"; W_SKY = "#B9CED3"
rng = np.random.default_rng(1)


def new():
    plt.rcParams["path.sketch"] = (0.9, 70, 1.6)
    fig = plt.figure(figsize=(5, 5), dpi=200); fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off"); ax.set_aspect("equal")
    return fig, ax


def wash(ax, pts, col, a=0.55, off=1.2):
    """watercolour: 2 offset translucent fills, no outline"""
    pts = np.array(pts, float)
    for k in range(2):
        d = rng.normal(0, off, 2) if k else np.zeros(2)
        p = Polygon(pts + d + rng.normal(0, 0.35, pts.shape), closed=True, facecolor=col, edgecolor="none", alpha=a * (0.7 if k else 1))
        p.set_sketch_params(None); ax.add_patch(p)


def ink(ax, pts, lw=1.2, closed=False, col=INKC):
    pts = np.array(pts, float)
    if closed: pts = np.r_[pts, pts[:1]]
    ax.plot(pts[:, 0], pts[:, 1], color=col, lw=lw, solid_capstyle="round", solid_joinstyle="round")


def rect(ax, x, y, w, h, lw=1.2, col=None, a=0.55):
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    if col: wash(ax, pts, col, a)
    ink(ax, pts, lw, closed=True)


def hatch(ax, x0, y0, x1, y1, n=8, lw=0.5, ang=1.0):
    for k in range(n):
        t = k / n
        ax.plot([x0 + (x1 - x0) * t, x0 + (x1 - x0) * t + 3 * ang], [y0, y0 + 3], color=INKC, lw=lw, alpha=0.6)


def arch(ax, cx, y, w, h, lw=1.0, col=None, horseshoe=False, a=0.6):
    r = w / 2
    th = np.linspace(-0.35 if horseshoe else 0, np.pi + (0.35 if horseshoe else 0), 30)
    top = np.c_[cx + r * 1.0 * np.cos(th[::-1]) * (-1) * -1, y + h - r + r * np.sin(th[::-1])]
    top = np.c_[cx - r * np.cos(th), y + h - r + r * np.sin(th)]
    pts = np.r_[[(cx - r * (0.85 if horseshoe else 1), y)], top, [(cx + r * (0.85 if horseshoe else 1), y)]]
    if col: wash(ax, pts, col, a)
    ink(ax, pts, lw)


def ground(ax, y=12, x0=4, x1=96):
    xs = np.linspace(x0, x1, 40)
    ax.plot(xs, y + rng.normal(0, 0.25, 40), color=INKC, lw=1.0)
    for k in range(10):
        x = rng.uniform(x0 + 4, x1 - 6); ax.plot([x, x + rng.uniform(2, 5)], [y - 1.6, y - 1.6], color=INKC, lw=0.5, alpha=0.6)


def figure(ax, x, y, h=6, col=INKC):
    ax.add_patch(Circle((x, y + h * 0.9), h * 0.09, color=col, lw=0))
    ink(ax, [(x, y + h * 0.78), (x, y + h * 0.42)], lw=1.4, col=col)
    ink(ax, [(x - h * 0.08, y), (x, y + h * 0.42), (x + h * 0.08, y)], lw=1.0, col=col)


def palm(ax, x, y, h=30):
    t = np.linspace(0, 1, 20); xs = x + 2 * np.sin(t * 1.4); ys = y + t * h
    ax.plot(xs, ys, color=INKC, lw=1.6)
    tx, ty = xs[-1], ys[-1]
    for a in np.linspace(-170, -10, 9):
        r = np.radians(a); L = rng.uniform(8, 12); s = np.linspace(0, 1, 10)
        px = tx + np.cos(r) * L * s; py = ty - np.sin(r) * L * s * 0.5 - 3 * s ** 2
        ax.plot(px, py, color=W_GREEN, lw=1.6, alpha=0.9); ax.plot(px, py, color=INKC, lw=0.5)


def tree(ax, x, y, h=16, r=7):
    ink(ax, [(x, y), (x, y + h * 0.5)], 1.2)
    for k in range(6):
        ax.add_patch(Circle((x + rng.normal(0, r * 0.35), y + h - r * 0.7 + rng.normal(0, r * 0.25)), r * rng.uniform(0.45, 0.65), color=W_SAGE, alpha=0.45, lw=0))
    th = np.linspace(0, 2 * np.pi, 40); rr = r * (1 + 0.12 * np.sin(th * 7))
    ink(ax, np.c_[x + rr * np.cos(th), y + h - r * 0.7 + rr * 0.75 * np.sin(th)], 0.8, closed=True)


def save(fig, name, caption):
    ax = fig.axes[0]
    fig.savefig(f"sk/nc_{name}.png", dpi=200, transparent=True)
    ax.text(50, 2.5, caption, ha="center", va="bottom", fontsize=17, color=INKC, fontstyle="italic", sketch_params=None)
    fig.savefig(f"sk/{name}.png", dpi=200, transparent=True); plt.close(fig); print("saved", name)


# ----------------------------------------------------------------------------------------------
def spartel():
    fig, ax = new(); ground(ax, 12)
    wash(ax, [(4, 12), (96, 12), (96, 8), (4, 8)], W_SAND, 0.4)
    # building around courtyard, crenellated
    rect(ax, 14, 12, 72, 18, col=W_SAND)
    for x in np.arange(14, 86, 4.5):
        rect(ax, x, 30, 2.6, 2.2, lw=0.9)
    for x in (22, 34, 66, 78):
        arch(ax, x, 15, 5, 9, lw=0.9, col=W_SEA)
    # tower
    rect(ax, 42, 30, 16, 40, col=W_SAND, a=0.7)
    for y in (38, 50, 60):
        arch(ax, 50, y, 3.6, 6, lw=0.9, col=W_SEA)
    rect(ax, 40, 70, 20, 3, lw=1.1, col=W_TERRA)
    for x in np.arange(40.5, 60, 3.4):
        rect(ax, x, 73, 1.8, 1.8, lw=0.8)
    rect(ax, 45, 75, 10, 9, lw=1.0, col=W_SKY, a=0.7)
    for x in (47.5, 50, 52.5): ink(ax, [(x, 75), (x, 84)], 0.6)
    ink(ax, [(44, 84), (50, 90), (56, 84)], 1.2); ax.add_patch(Circle((50, 91), 0.9, color=INKC))
    # light rays
    for a in (-12, -4, 4, 12):
        r = np.radians(a); ink(ax, [(57, 80), (57 + 30 * np.cos(r), 80 + 30 * np.sin(r))], 0.4)
    hatch(ax, 58, 32, 58, 68, n=1)
    for y in np.arange(32, 68, 3): ink(ax, [(56, y), (58, y + 1.5)], 0.4)
    save(fig, "sk_spartel", "Phare du cap Spartel")


def kasbah_gate():
    fig, ax = new(); ground(ax, 12)
    rect(ax, 8, 12, 84, 46, col=W_OCHRE, a=0.5)
    for x in np.arange(8, 92, 7):
        rect(ax, x, 58, 4.2, 4, lw=1.0, col=W_OCHRE, a=0.5)
    # gate frame
    rect(ax, 33, 12, 34, 38, col=W_SAND, a=0.6)
    arch(ax, 50, 12, 20, 30, lw=1.5, col="#4E6470", horseshoe=True, a=0.75)
    arch(ax, 50, 12, 24, 33, lw=0.8, horseshoe=True)
    # zellige band
    for x in np.arange(34, 66, 2.2):
        rect(ax, x, 46, 1.6, 1.6, lw=0.4, col=W_GREEN, a=0.7)
    # stone joints
    for k in range(40):
        x = rng.uniform(10, 90); y = rng.uniform(14, 56)
        if 30 < x < 70 and y < 50: continue
        ink(ax, [(x, y), (x + rng.uniform(2, 4), y)], 0.4)
    figure(ax, 47, 12, 10); figure(ax, 75, 12, 9, col="#5A4636")
    tree(ax, 86, 12, h=24, r=7)
    save(fig, "sk_kasbah", "Bab el Kasbah")


def minaret():
    fig, ax = new(); ground(ax, 10)
    # mosque body
    rect(ax, 10, 10, 50, 20, col=W_SAND, a=0.5)
    for x in (18, 30, 42, 54):
        arch(ax, x, 10, 6, 12, lw=0.9, col=W_SEA)
    wash(ax, [(10, 30), (60, 30), (56, 34), (14, 34)], W_GREEN, 0.7); ink(ax, [(10, 30), (14, 34), (56, 34), (60, 30)], 1.0)
    # minaret
    rect(ax, 58, 10, 18, 66, col=W_SAND, a=0.55)
    for y in np.arange(18, 70, 7):
        for x in np.arange(59, 75, 3.2):
            rect(ax, x, y, 2.4, 2.4, lw=0.35, col=[W_GREEN, W_TERRA, W_SEA, W_OCHRE][int((x + y) % 4)], a=0.75)
    arch(ax, 67, 40, 5, 9, lw=1.0, col="#4E6470", a=0.8)
    arch(ax, 67, 56, 4, 7, lw=1.0, col="#4E6470", a=0.8)
    for x in np.arange(58, 76, 3):
        rect(ax, x, 76, 2.0, 2.2, lw=0.8)
    rect(ax, 62.5, 76, 9, 11, col=W_SAND, a=0.6)
    arch(ax, 67, 78, 3.4, 6, lw=0.8, col="#4E6470")
    wash(ax, [(62, 87), (72, 87), (67, 91)], W_GREEN, 0.8); ink(ax, [(62, 87), (67, 91), (72, 87)], 1.0)
    ink(ax, [(67, 91), (67, 99)], 1.0)
    for k, r in enumerate((1.2, 1.0, 0.8)):
        ax.add_patch(Circle((67, 93 + k * 2.3), r, color=W_OCHRE, ec=INKC, lw=0.7))
    palm(ax, 88, 10, 42)
    figure(ax, 34, 10, 9); figure(ax, 38, 10, 8, col="#8B3E2F")
    save(fig, "sk_minaret", "Minaret de Sidi Bou Abib, Grand Socco")


def cervantes():
    fig, ax = new(); ground(ax, 10)
    rect(ax, 10, 10, 80, 50, col="#E9DCC7", a=0.6)
    # curved pediment
    th = np.linspace(0, np.pi, 40)
    pts = np.c_[50 - 22 * np.cos(th), 60 + 12 * np.sin(th)]
    wash(ax, np.r_[[(28, 60)], pts, [(72, 60)]], "#E9DCC7", 0.7); ink(ax, pts, 1.3)
    th2 = np.linspace(0, np.pi, 40); ink(ax, np.c_[50 - 17 * np.cos(th2), 60 + 8.5 * np.sin(th2)], 0.7)
    wash(ax, [(36, 61), (64, 61), (64, 66), (36, 66)], "#4E7C7A", 0.6)
    ax.text(50, 63.5, "GRAN TEATRO CERVANTES", fontsize=6.6, ha="center", va="center", color=INKC, fontweight="bold")
    # pilasters
    for x in (10, 30, 70, 88):
        rect(ax, x, 10, 2.2, 50, lw=0.9, col=W_OCHRE, a=0.5)
    # large central window
    arch(ax, 50, 30, 26, 26, lw=1.3, col=W_SEA, a=0.65)
    for x in (42, 50, 58): ink(ax, [(x, 30), (x, 52)], 0.6)
    ink(ax, [(37, 42), (63, 42)], 0.6)
    # doors
    for x in (40, 50, 60):
        arch(ax, x, 10, 7, 14, lw=1.0, col="#6B5A48", a=0.6)
    for x in (20, 80):
        arch(ax, x, 30, 9, 15, lw=1.0, col=W_SEA)
        arch(ax, x, 10, 9, 14, lw=1.0, col="#6B5A48", a=0.5)
    # balcony rail
    ink(ax, [(36, 30), (64, 30)], 1.2)
    for x in np.arange(36, 64, 1.6): ink(ax, [(x, 28), (x, 30)], 0.4)
    # cracks / patina
    for k in range(10):
        x = rng.uniform(12, 88); y = rng.uniform(14, 58); ink(ax, [(x, y), (x + rng.uniform(-2, 2), y - rng.uniform(1, 4))], 0.35)
    figure(ax, 25, 10, 9)
    save(fig, "sk_cervantes", "Gran Teatro Cervantes (1913)")


def standrew():
    fig, ax = new(); ground(ax, 10)
    # nave
    rect(ax, 8, 10, 52, 26, col="#F1ECE2", a=0.7)
    wash(ax, [(6, 36), (62, 36), (56, 46), (12, 46)], W_TERRA, 0.55); ink(ax, [(6, 36), (12, 46), (56, 46), (62, 36)], 1.2)
    for x in (16, 28, 40, 52):
        arch(ax, x, 18, 5, 11, lw=0.9, col=W_SEA)
    # tower like minaret
    rect(ax, 60, 10, 18, 56, col="#F1ECE2", a=0.7)
    for y in (22, 38, 52):
        arch(ax, 69, y, 5, 9, lw=1.0, col=W_SEA)
    for x in np.arange(60, 78, 3.2):
        rect(ax, x, 66, 2.0, 2.4, lw=0.8)
    rect(ax, 64, 66, 10, 10, col="#F1ECE2", a=0.7)
    ink(ax, [(69, 76), (69, 86)], 1.0); ink(ax, [(66, 82.5), (72, 82.5)], 1.0)
    # cemetery + trees
    for x in (14, 24, 34):
        rect(ax, x, 10, 3, 4.5, lw=0.7, col="#D6D2C8")
    tree(ax, 88, 10, h=34, r=9)
    palm(ax, 4, 10, 40)
    save(fig, "sk_standrew", "Église Saint-André (1894)")


def hafa():
    fig, ax = new()
    # sea
    wash(ax, [(0, 8), (100, 8), (100, 38), (0, 38)], W_SEA, 0.55)
    for k in range(14):
        x = rng.uniform(4, 90); y = rng.uniform(12, 36); ink(ax, [(x, y), (x + rng.uniform(3, 7), y)], 0.5)
    ink(ax, [(0, 38), (100, 38)], 0.9)
    # spanish coast
    wash(ax, [(52, 38), (64, 43), (78, 41), (100, 46), (100, 38)], "#B7C0C4", 0.6); ink(ax, [(52, 38), (64, 43), (78, 41), (100, 46)], 0.7)
    # cliff with terraces
    terr = [(0, 50), (14, 50), (14, 44), (30, 44), (30, 37), (46, 37), (46, 30), (60, 30), (60, 22), (72, 22), (72, 6), (0, 6)]
    wash(ax, terr, W_SAND, 0.75); ink(ax, terr[:-1], 1.3)
    for (x0, y0, x1) in ((0, 50, 14), (14, 44, 30), (30, 37, 46), (46, 30, 60), (60, 22, 72)):
        for x in np.arange(x0 + 3, x1 - 2, 5):
            ax.add_patch(Circle((x, y0 + 2.6), 1.1, facecolor="white", edgecolor=INKC, lw=0.6))
            ink(ax, [(x, y0), (x, y0 + 2.4)], 0.6)
            if rng.random() < 0.6: figure(ax, x + 2, y0, 4.5, col=["#8B3E2F", INKC, "#3E5A6E"][int(x) % 3])
    # white wall + blue band
    wash(ax, [(0, 50), (16, 50), (16, 58), (0, 58)], "#FFFFFF", 0.9); ink(ax, [(0, 58), (16, 58), (16, 50)], 1.1)
    wash(ax, [(0, 50), (16, 50), (16, 52), (0, 52)], "#5E87A6", 0.8)
    tree(ax, 24, 44, h=22, r=7)
    ax.text(8, 61, "CAFÉ HAFA", fontsize=8, ha="center", color=INKC, fontweight="bold")
    save(fig, "sk_hafa", "Café Hafa, terrasses sur le détroit")


def hercule():
    fig, ax = new()
    wash(ax, [(0, 0), (100, 0), (100, 100), (0, 100)], "#B7A58A", 0.55)
    th = np.linspace(0, 2 * np.pi, 200)
    # africa-shaped opening (stylised)
    af = np.array([(30, 78), (44, 82), (52, 78), (58, 80), (66, 72), (70, 60), (64, 50), (60, 38), (54, 28), (48, 20), (44, 24), (42, 36), (36, 46), (28, 56), (26, 68)])
    wash(ax, af, W_SKY, 0.85, off=0.4)
    wash(ax, [(26, 46), (72, 46), (70, 30), (28, 30)], W_SEA, 0.5, off=0.3)
    ink(ax, af, 1.6, closed=True)
    for k in range(30):
        a = rng.uniform(0, 2 * np.pi); r = rng.uniform(38, 50)
        x = 50 + r * np.cos(a); y = 52 + r * np.sin(a)
        ink(ax, [(x, y), (x + rng.uniform(-4, 4), y + rng.uniform(-4, 4))], 0.5)
    wash(ax, [(0, 0), (100, 0), (100, 14), (0, 18)], "#8E7A62", 0.6); ink(ax, [(0, 18), (100, 14)], 1.0)
    figure(ax, 38, 16, 10); figure(ax, 46, 16, 9, col="#8B3E2F")
    save(fig, "sk_hercule", "Grottes d'Hercule")


def medina():
    fig, ax = new(); ground(ax, 8)
    houses = [(4, 8, 20, 40, "#FFFFFF"), (24, 14, 18, 34, "#E9F0F2"), (42, 20, 22, 30, "#FFFFFF"), (64, 26, 16, 30, "#F4EADC"), (80, 32, 18, 26, "#FFFFFF")]
    for x, y, w, h, col in houses:
        rect(ax, x, y, w, h, col=col, a=0.9)
        wash(ax, [(x, y), (x + w, y), (x + w, y + 3), (x, y + 3)], W_SEA, 0.5)
        ink(ax, [(x, y + h), (x, y + h + 2), (x + w, y + h + 2), (x + w, y + h)], 0.9)
    # doors & windows
    arch(ax, 12, 8, 6, 12, lw=1.0, col="#3E6C8A", a=0.85)
    arch(ax, 52, 20, 6, 12, lw=1.0, col="#5E7F4F", a=0.85)
    arch(ax, 88, 32, 5, 10, lw=1.0, col="#7A4B3A", a=0.85)
    for (x, y) in ((28, 34), (34, 34), (68, 44), (46, 38), (58, 40), (84, 46)):
        rect(ax, x, y, 3, 4, lw=0.8, col="#3E6C8A", a=0.7)
    rect(ax, 30, 22, 8, 6, lw=0.8, col="#9C7A5B", a=0.7)
    for x in np.arange(30.5, 38, 1.4): ink(ax, [(x, 22), (x, 28)], 0.4)
    # stairs (derb)
    for k in range(10):
        ink(ax, [(20 + k * 6, 8 + k * 2.6), (26 + k * 6, 8 + k * 2.6)], 0.7)
    # plants / laundry
    for x in (6, 8, 10): ax.add_patch(Circle((x, 49.5), 1.0, color=W_TERRA, alpha=0.8))
    ink(ax, [(44, 52), (60, 52)], 0.5)
    for x in (46, 50, 54, 58): wash(ax, [(x, 52), (x + 2, 52), (x + 2, 48.5), (x, 48.5)], [W_TERRA, W_OCHRE, W_SEA, W_SAGE][int(x) % 4], 0.8)
    figure(ax, 33, 14, 9, col="#8B3E2F"); figure(ax, 70, 26, 8)
    save(fig, "sk_medina", "Derb de la médina")


def stade():
    fig, ax = new()
    ground(ax, 22)
    # stadium bowl
    th = np.linspace(0, np.pi, 80)
    outer = np.c_[50 - 44 * np.cos(th), 22 + 30 * np.sin(th) * 0.7]
    wash(ax, np.r_[outer, [(94, 22), (6, 22)]], "#E3DED6", 0.8)
    ink(ax, outer, 1.4)
    # roof canopy
    roof = np.c_[50 - 46 * np.cos(th), 22 + 30 * np.sin(th) * 0.7 + 4]
    ink(ax, roof, 1.0)
    wash(ax, np.r_[roof, outer[::-1]], W_SKY, 0.55)
    for t in np.linspace(0.05, np.pi - 0.05, 24):
        ink(ax, [(50 - 44 * np.cos(t), 22 + 21 * np.sin(t)), (50 - 46 * np.cos(t), 26 + 21 * np.sin(t))], 0.5)
    # facade ribs
    for t in np.linspace(0.08, np.pi - 0.08, 22):
        ink(ax, [(50 - 44 * np.cos(t), 22), (50 - 44 * np.cos(t), 22 + 21 * np.sin(t))], 0.45)
    wash(ax, [(6, 22), (94, 22), (94, 25), (6, 25)], W_TERRA, 0.6)
    # forecourt & flags
    for x in (12, 20, 80, 88):
        ink(ax, [(x, 22), (x, 40)], 0.7); wash(ax, [(x, 40), (x + 5, 39), (x, 37)], W_TERRA, 0.9)
    for x in np.arange(18, 84, 9): figure(ax, x + rng.uniform(-2, 2), 12, 7, col=[INKC, "#8B3E2F", "#3E5A6E"][int(x) % 3])
    wash(ax, [(4, 6), (96, 6), (96, 22), (4, 22)], "#D9D0BF", 0.5)
    save(fig, "sk_stade", "Grand stade de Tanger, 2025")


def port():
    fig, ax = new()
    # kasbah skyline
    wash(ax, [(0, 34), (0, 70), (20, 72), (40, 66), (60, 58), (75, 48), (100, 42), (100, 34)], "#F3EFE8", 0.95)
    xs = 0
    while xs < 92:
        w = rng.uniform(5, 9); h = 70 - xs * 0.32 + rng.uniform(-3, 3)
        ink(ax, [(xs, h - 6), (xs, h), (xs + w, h), (xs + w, h - 6)], 0.6)
        for k in range(2):
            rect(ax, xs + 1.5 + k * 3, h - 5, 1.4, 2, lw=0.4, col="#3E6C8A", a=0.6)
        xs += w
    rect(ax, 14, 70, 4, 14, lw=0.9, col=W_SAND)
    wash(ax, [(0, 34), (100, 34), (100, 38), (0, 38)], "#D9BE97", 0.8); ink(ax, [(0, 38), (100, 38)], 1.0)
    for x in np.arange(0, 100, 4): rect(ax, x, 38, 2.4, 2.2, lw=0.6)
    # water + boats
    wash(ax, [(0, 4), (100, 4), (100, 34), (0, 34)], W_SEA, 0.55)
    for k in range(12):
        x = rng.uniform(2, 90); y = rng.uniform(6, 20); ink(ax, [(x, y), (x + rng.uniform(3, 7), y)], 0.5)
    for x, L in ((10, 20), (38, 16), (62, 24)):
        hull = [(x, 24), (x + L, 25), (x + L * 0.9, 20), (x + L * 0.1, 20)]
        wash(ax, hull, "#FFFFFF", 0.95); ink(ax, hull, 1.0, closed=True)
        ink(ax, [(x + L * 0.5, 25), (x + L * 0.5, 25 + L * 1.6)], 0.8)
        wash(ax, [(x + L * 0.25, 25), (x + L * 0.35, 28), (x + L * 0.7, 28), (x + L * 0.8, 25)], "#FFFFFF", 0.9)
    save(fig, "sk_port", "La marina sous la Kasbah")


def legation():
    fig, ax = new(); ground(ax, 10)
    rect(ax, 10, 10, 80, 54, col="#F4F0E8", a=0.85)
    for x in np.arange(10, 90, 4): rect(ax, x, 64, 2.4, 2.4, lw=0.6)
    # moorish arcade top floor
    for x in np.arange(22, 82, 10):
        arch(ax, x, 44, 7, 14, lw=1.0, col="#7A9A8A", horseshoe=True, a=0.6)
    # mashrabiya balcony
    rect(ax, 36, 26, 28, 12, lw=1.0, col="#8C6B4E", a=0.7)
    for x in np.arange(37, 64, 1.6): ink(ax, [(x, 26), (x, 38)], 0.35)
    for y in np.arange(27, 38, 1.6): ink(ax, [(36, y), (64, y)], 0.35)
    # door
    arch(ax, 50, 10, 10, 14, lw=1.2, col="#3E6C8A", a=0.85)
    for x in (20, 80): rect(ax, x - 3, 28, 6, 8, lw=0.9, col="#3E6C8A", a=0.6)
    wash(ax, [(10, 40), (90, 40), (90, 42), (10, 42)], "#5E87A6", 0.6)
    ax.add_patch(Rectangle((84, 66), 0.5, 14, color=INKC)); wash(ax, [(84.5, 80), (94, 79), (94, 74), (84.5, 74.5)], W_TERRA, 0.8)
    save(fig, "sk_legation", "Légation américaine (1821)")


if __name__ == "__main__":
    os.makedirs("sk", exist_ok=True)
    for f in (spartel, kasbah_gate, minaret, cervantes, standrew, hafa, hercule, medina, stade, port, legation):
        f()
