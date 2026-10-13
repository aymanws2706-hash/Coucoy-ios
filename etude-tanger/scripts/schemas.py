# -*- coding: utf-8 -*-
import glob, os, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.font_manager as fm
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle, Wedge, Polygon, FancyBboxPatch, Arc
for f in glob.glob(os.path.expanduser("~/.fonts/barlow*.ttf")):
    fm.fontManager.addfont(f)
CF = "Barlow Condensed"; plt.rcParams["font.family"] = CF
PAPER = "#EFEBE3"; INK = "#23303A"; MUTED = "#7B746B"; TERRA = "#B5563C"; OCHRE = "#C9965A"; SAGE = "#7D9873"; SAGE_D = "#4F6B4A"
SEA = "#A8C0C6"; SLATE = "#3E5A6E"; SAND = "#E6DCCB"


def cycle():
    fig = plt.figure(figsize=(12, 10), dpi=200); fig.patch.set_facecolor(PAPER)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(-1.75, 1.75); ax.set_ylim(-1.32, 1.38); ax.set_aspect("equal"); ax.axis("off")
    nodes = [("AMBITION\nINTERNATIONALE", "Mondial 2030, croisières,\nrang touristique", TERRA),
             ("PROJETS\nVITRINES", "marina, corniche,\nmédina restaurée, stade", TERRA),
             ("RENTE\nFONCIÈRE", "le front de mer et la médina\nprennent de la valeur", OCHRE),
             ("CONVERSION\nDU SOL", "hôtels, résidences,\nmaisons d'hôtes", OCHRE),
             ("ÉVICTION", "loyers en hausse, départ\ndes ménages modestes", SLATE),
             ("ÉTALEMENT", "périphérie dense et\nsous-équipée, hors du regard", SLATE)]
    R = 0.86
    ax.add_patch(Circle((0, 0), R, facecolor="none", edgecolor="#D3CABC", lw=18, zorder=1))
    for i in range(6):
        a0 = 90 - i * 60 - 14; a1 = 90 - (i + 1) * 60 + 14
        col = nodes[i][2]
        ax.add_patch(Arc((0, 0), 2 * R, 2 * R, theta1=a1, theta2=a0, color=col, lw=5, zorder=2))
        t = np.radians(a1); ax.add_patch(FancyArrowPatch((R * np.cos(t + 0.06), R * np.sin(t + 0.06)), (R * np.cos(t), R * np.sin(t)),
                                                         arrowstyle="-|>,head_length=10,head_width=7", color=col, lw=0, zorder=3))
    for i, (t, d, c) in enumerate(nodes):
        a = np.radians(90 - i * 60)
        x, y = R * np.cos(a), R * np.sin(a)
        ax.add_patch(Circle((x, y), 0.17, facecolor=c, edgecolor=PAPER, lw=4, zorder=4))
        ax.text(x, y + 0.01, f"{i + 1}", ha="center", va="center", fontsize=24, color="white", fontweight="bold", zorder=5)
        ca = np.cos(a)
        if abs(ca) < 0.2:   # top / bottom : text above / below
            if y > 0:
                ax.text(x, y + 0.42, t.replace("\n", " "), ha="center", va="bottom", fontsize=15, color=c, fontweight="bold", zorder=5)
                ax.text(x, y + 0.40, d.replace("\n", " "), ha="center", va="top", fontsize=11, color=MUTED, zorder=5)
                ax.plot([x, x], [y + 0.18, y + 0.30], color=c, lw=1)
            else:
                ax.text(x, y - 0.22, t.replace("\n", " "), ha="center", va="top", fontsize=15, color=c, fontweight="bold", zorder=5)
                ax.text(x, y - 0.31, d.replace("\n", " "), ha="center", va="top", fontsize=11, color=MUTED, zorder=5)
            continue
        else:
            tx, ty, ha = x + (0.22 if ca > 0 else -0.22), y, ("left" if ca > 0 else "right")
        ax.text(tx, ty + 0.015, t.replace("\n", " "), ha=ha, va="bottom", fontsize=15, color=c, fontweight="bold", zorder=5)
        ax.text(tx, ty - 0.015, d, ha=ha, va="top", fontsize=11, color=MUTED, linespacing=1.15, zorder=5)
    ax.text(0, 0.12, "LE CERCLE DE LA", ha="center", fontsize=14, color=MUTED, fontweight="bold")
    ax.text(0, -0.02, "VILLE-VITRINE", ha="center", fontsize=26, color=INK, fontweight="bold")
    ax.text(0, -0.17, "chaque tour renforce le suivant :\nla périphérie, invisible, n'est jamais prioritaire", ha="center", va="top", fontsize=11, color=MUTED, linespacing=1.2)
    fig.savefig("maps/s_cycle.png", dpi=200, facecolor=PAPER); plt.close(fig); print("saved s_cycle")


def tod():
    fig = plt.figure(figsize=(14, 9), dpi=200); fig.patch.set_facecolor(PAPER)
    ax = fig.add_axes([0.0, 0.0, 0.62, 1]); ax.set_xlim(-620, 620); ax.set_ylim(-560, 560); ax.set_aspect("equal"); ax.axis("off")
    rng = np.random.default_rng(2)
    # rings
    for r, c, a in [(500, "#E8DCC8", 1), (300, "#E6CBB0", 1), (120, "#DDAE8C", 1)]:
        ax.add_patch(Circle((0, 0), r, facecolor=c, edgecolor="none", zorder=1, alpha=a))
    # street grid
    for v in np.arange(-600, 601, 90):
        ax.plot([v, v], [-600, 600], color=PAPER, lw=4, zorder=2); ax.plot([-600, 600], [v, v], color=PAPER, lw=4, zorder=2)
    # blocks: density by distance
    for x in np.arange(-585, 586, 90):
        for y in np.arange(-585, 586, 90):
            d = np.hypot(x, y)
            if d > 560:
                continue
            cx, cy = x + 45 - 45, y
            if abs(x) < 80 and abs(y) < 80:
                continue
            if d < 130:
                c = TERRA; s = 70
            elif d < 320:
                c = "#C97E5C"; s = 66
            else:
                c = "#D9B79A"; s = 58
            ax.add_patch(Rectangle((x - s / 2, y - s / 2), s, s, facecolor=c, edgecolor=PAPER, lw=0.8, zorder=3))
    # linear park along oued (diagonal)
    xs = np.linspace(-600, 600, 50); ys = 0.55 * xs - 230 + 40 * np.sin(xs / 120)
    ax.fill_between(xs, ys - 28, ys + 28, color=SAGE, zorder=4)
    ax.plot(xs, ys, color="#5F8796", lw=2.5, zorder=5)
    # equipment
    for (x, y, t) in [(-180, 180, "école"), (200, -60, "santé"), (-200, -170, "marché"), (180, 210, "sport")]:
        ax.add_patch(Rectangle((x - 32, y - 32), 64, 64, facecolor=OCHRE, edgecolor="white", lw=2, zorder=6))
        ax.text(x, y - 52, t, ha="center", va="top", fontsize=11, color=INK, fontweight="bold", zorder=7)
    # public square + station
    ax.add_patch(Rectangle((-60, -60), 120, 120, facecolor="#F4EFE6", edgecolor=INK, lw=1, zorder=6))
    ax.plot([-620, 620], [-10, -10], color="white", lw=14, zorder=7); ax.plot([-620, 620], [-10, -10], color=INK, lw=8, zorder=7.1)
    ax.add_patch(Circle((0, -10), 30, facecolor="white", edgecolor=INK, lw=3, zorder=8))
    ax.text(0, 70, "place de la station", ha="center", fontsize=11, color=INK, fontweight="bold", zorder=9)
    for r, t in [(120, "120 m"), (300, "300 m"), (500, "500 m")]:
        ax.add_patch(Circle((0, 0), r, facecolor="none", edgecolor=INK, lw=0.8, linestyle=(0, (4, 3)), zorder=8))
        ax.text(r * 0.72, r * 0.72, t, fontsize=10, color=INK, zorder=9, bbox=dict(fc=PAPER, ec="none", pad=1))
    ax.text(-600, 520, "tram / BHNS", fontsize=11, color=INK, fontweight="bold")
    ax.text(-300, -470, "parc linéaire d'oued", fontsize=11, color=SAGE_D, fontweight="bold")
    # right: principles
    ax2 = fig.add_axes([0.63, 0.04, 0.36, 0.92]); ax2.axis("off"); ax2.set_xlim(0, 1); ax2.set_ylim(0, 1)
    items = [(TERRA, "0-120 m : cœur de station", "commerces, services, logements R+5 à R+6 ; place publique et correspondances"),
             ("#C97E5C", "120-300 m : densité intermédiaire", "logements R+4, rez-de-chaussée actifs, rues apaisées à 30 km/h"),
             ("#D9B79A", "300-500 m : tissu existant", "réhabilitation, pas d'extension ; traversées piétonnes vers la station"),
             (OCHRE, "Équipements de proximité", "école, santé, marché, sport à moins de 5 minutes à pied de la station"),
             (SAGE, "Trame verte et bleue", "les oueds deviennent des parcs linéaires qui relient les quartiers")]
    for i, (c, t, d) in enumerate(items):
        y = 0.9 - i * 0.18
        ax2.add_patch(Rectangle((0.0, y - 0.025), 0.06, 0.05, facecolor=c, edgecolor="none"))
        ax2.text(0.09, y + 0.01, t, fontsize=15, color=INK, fontweight="bold", va="center")
        ax2.text(0.09, y - 0.035, d, fontsize=11, color=MUTED, va="top", wrap=True)
    fig.savefig("maps/s_tod.png", dpi=200, facecolor=PAPER); plt.close(fig); print("saved s_tod")


if __name__ == "__main__":
    cycle(); tod()
