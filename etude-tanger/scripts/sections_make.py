# -*- coding: utf-8 -*-
import sys, numpy as np
from coupes2 import *
from scipy.ndimage import gaussian_filter1d

def C1():
    g = ground_profile((-5.7962, 35.7808), (-5.7998, 35.7748))
    def z(x):
        if x < 189: return -(189 - x) * 0.06
        if x < 360: return 0 + (x - 189) / 171 * 2.0
        if x < 362: return 2.0 + (x - 360) / 2 * 2.8
        if x < 446: return 4.8 + (x - 362) / 84 * 0.6
        v = max(5.4, float(np.interp(x, np.arange(len(g)), g)) - 2.2)
        return 5.4 + (v - 5.4) * min(1, (x - 446) / 40)
    c = Coupe(z, 172, 741, -9, 46, seed=3)
    # distant city on the hills
    c.hills([(150, 0), (420, 4), (520, 22), (600, 30), (680, 38), (741, 42)], color="#DCDDD8", z=0.6)
    c.backdrop("city", seed=11, hmin=8, hmax=26, base=lambda x: float(np.interp(x, [420, 520, 600, 680, 741], [4, 22, 30, 38, 42])) - 3, color="#DAD8D2", layer=2, x0=430, x1=741, alpha=1)
    c.backdrop("city", seed=12, hmin=18, hmax=36, color="#D0CCC4", layer=4, x0=446, x1=741, base=None)
    c.sea(150, 189 + 1, depth=6)
    c.terrain()
    # beach
    def beach(cc):
        ax = cc.ax
        xs = np.linspace(189, 360, 200); ax.fill_between(xs, [cc.zg(x) - 0.6 for x in xs], [cc.zg(x) for x in xs], color="#E6D4AE", lw=0, zorder=6)
        ax.fill_between(np.linspace(189, 203, 30), [cc.zg(x) - 0.6 for x in np.linspace(189, 203, 30)], [cc.zg(x) for x in np.linspace(189, 203, 30)], color="#C9B48C", lw=0, zorder=6.1)
        for x in np.arange(214, 345, 11.5):
            cc.parasol(x, cc.zg(x)); cc.person(x + 1.6, cc.zg(x), sit=True); 
            if cc.rng.random() < 0.6: cc.person(x - 1.8, cc.zg(x))
        for x in (196, 199.5, 238, 291): cc.person(x, cc.zg(x), kid=(x % 2 > 0.5))
        for x in (176, 182): cc.ax.add_patch(Circle((x, 0.1), 0.15, color="#5A4636", zorder=7))
        # lifeguard tower
        x = 262; zz = cc.zg(x)
        for d in (-1, 1): ax.plot([x + d * 1.0, x + d * 0.6], [zz, zz + 3], color=WALL, lw=cc.lw(0.8), zorder=27)
        ax.add_patch(Rectangle((x - 1.1, zz + 3), 2.2, 1.8, facecolor="#F5F1E9", edgecolor=WALL, lw=cc.lw(0.5), zorder=27))
        ax.add_patch(Polygon([(x - 1.4, zz + 4.8), (x + 1.4, zz + 4.8), (x, zz + 5.6)], facecolor=TERRA, edgecolor=WALL, lw=cc.lw(0.4), zorder=27))
        cc.person(x, zz + 3.0)
        # small boat
        ax.add_patch(Polygon([(160, 0.4), (167, 0.4), (166, -0.3), (161.5, -0.3)], facecolor="#F5F1E9", edgecolor=WALL, lw=cc.lw(0.5), zorder=7))
        ax.add_patch(Rectangle((160, 0.3), 7, 0.15, color=SLATE, zorder=7.1))
        # sea wall + stairs + promenade
        ax.add_patch(Polygon([(359.5, 1.9), (362.5, 1.9), (362.5, 4.8), (360.3, 4.8)], facecolor="#CFC5B3", edgecolor=WALL, lw=cc.lw(0.7), zorder=24))
        for k in range(8):
            ax.add_patch(Rectangle((352 + k * 1.0, 2.0 + k * 0.35), 1.0, 0.35, facecolor="#D9D0BF", edgecolor=WALL, lw=cc.lw(0.3), zorder=7))
        ax.plot([362.3, 362.3], [4.8, 5.85], color=WALL, lw=cc.lw(0.7), zorder=24); ax.plot([360.6, 362.3], [5.85, 5.85], color=WALL, lw=cc.lw(0.7), zorder=24)
        xs = np.linspace(362, 425, 100)
        ax.fill_between(xs, [cc.zg(x) - 0.3 for x in xs], [cc.zg(x) for x in xs], color="#D9D0BF", lw=0, zorder=23)
        ax.fill_between(np.linspace(364, 377, 20), [cc.zg(x) for x in np.linspace(364, 377, 20)], [cc.zg(x) + 0.3 for x in np.linspace(364, 377, 20)], color="#9DB08C", lw=0, zorder=23)
        for x in (370, 383, 397, 411):
            cc.palm(x, cc.zg(x), h=float(cc.rng.uniform(10, 13)))
        for x in (376, 404): cc.lamp(x, cc.zg(x), h=6)
        for x in (379, 390, 401, 416): cc.person(x, cc.zg(x))
        cc.bench(387, cc.zg(387)); cc.person(387.3, cc.zg(387), sit=True)
        # cyclist (simple)
        x = 420; zz = cc.zg(x)
        for wx in (x - 0.55, x + 0.55): ax.add_patch(Circle((wx, zz + 0.35), 0.35, fill=False, edgecolor=WALL, lw=cc.lw(0.5), zorder=29))
        cc.person(x, zz + 0.45, h=1.3)
    beach.__name__ = "beach"; c.custom(beach)
    c.road(425, [(1.0, "sw"), (6.6, "lane"), (3.4, "medpalm"), (6.6, "lane-"), (3.4, "sw")], name="Av. Mohammed VI", sub="2 × 2 voies, terre-plein planté")
    c.label(175, 1.0, "Baie de Tanger", None, SEA_D)
    c.label(275, 9.0, "Plage publique", "171 m de sable, accès libre", OCHRE)
    c.label(392, 18.0, "Promenade de la corniche", "réaménagée par Tanger-Métropole (2013-2017)", TERRA)
    # front bâti
    U8 = ["com", "sais", "sais", "log", "sais", "log", "sais", "sais", "sais"]
    U9 = ["com", "log", "sais", "log", "log", "sais", "log", "sais", "sais", "sais"]
    c.building(446.5, 473, 8, uses=U8, gf=4.5, basement=2, balcony=(1, 0.9, "glass"), shutters_closed=0.45,
               label=("Front bâti R+8 / R+9", "cafés en RDC, appartements, location saisonnière", TERRA))
    c.flats.append((473, 483.4, float(z(446.5))))
    def court(cc):
        cc.tree(478, cc.zg(478), h=7, r=2.6)
        cc.ax.fill_between(np.linspace(473, 483.4, 10), [cc.zg(x) for x in np.linspace(473, 483.4, 10)], [cc.zg(x) + 0.2 for x in np.linspace(473, 483.4, 10)], color="#D9D0BF", zorder=23)
    court.__name__ = "court"; c.custom(court)
    c.building(483.4, 540, 9, uses=U9, gf=4.5, basement=2, balcony=(1, 0.7, "glass"), shutters_closed=0.4)
    c.road(540.5, [(2.5, "sw"), (2.4, "park"), (6.2, "lane"), (2.4, "park"), (2.5, "sw")], name="Av. de New York", sub=None)
    # villas & gardens
    def garden(cc):
        for x in (560, 567, 576, 588, 593): cc.tree(x, cc.zg(x), h=float(cc.rng.uniform(8, 13)), r=float(cc.rng.uniform(3, 4.5)), zo=12)
        ax = cc.ax
        for xw in (556.5, 595.5):
            ax.add_patch(Rectangle((xw, cc.zg(xw)), 0.4, 2.4, color=WALL, zorder=22))
        cc.person(583, cc.zg(583))
    garden.__name__ = "garden"; c.custom(garden)
    c.elev(568, 585, 8.5, col="#F2ECE1", zo=11, arches=True)
    c.label(575, 16, "Villas et jardins", "tissu des années 1930-1950", SAGE_D)
    c.road(596, [(2.0, "sw"), (6.4, "lane"), (2.4, "sw")], name="Rue de Floride", nets=False)
    c.building(607.5, 650, 5, uses=["com", "log", "log", "log", "log", "log"], gf=4.0, balcony=(1, 0.5, "rail"), shutters_closed=0.1)
    c.building(650, 681.3, 8, uses=["com"] + ["log", "sais"] * 4, gf=4.2, basement=1, balcony=(-1, 0.5, "rail"), shutters_closed=0.2,
               label=("Immeubles R+5 à R+8", "logements permanents, commerces", INK))
    c.road(682, [(3.0, "sw"), (7.0, "lane"), (2.5, "medtree"), (7.0, "lane-"), (3.0, "sw")], name="Bd Mohammed V")
    c.building(704.5, 741, 6, uses=["com"] + ["log"] * 6, gf=4.2, balcony=(1, 0.5, "rail"))
    c.dims = [172, 189, 360, 425, 446.5, 540, 556, 596, 607.5, 681.3, 704.5]
    return c

if __name__ == "__main__" and len(sys.argv) == 1:
    c = C1()
    c.render("maps/k1_full.png", ppm=6, frame=[(330, 452, -3, 17, 1), (438, 548, -6, 42, 2)])
    c.render("maps/k1_zoomA.png", ppm=22, xlim=(330, 452), zlim=(-3, 17), labels=False, chain=False)
    c.render("maps/k1_zoomB.png", ppm=22, xlim=(438, 548), zlim=(-6, 42), labels=False, chain=False)


def C2():
    g = ground_profile((-5.8190, 35.7525), (-5.8130, 35.7525))
    zf = lambda x: float(np.interp(x, np.arange(len(g)), g))
    c = Coupe(zf, 0, 542, 26, 60, seed=5)
    c.hills([(0, 50), (120, 54), (260, 58), (400, 56), (542, 52)], color="#DCDDD8", z=0.6)
    c.backdrop("medina", seed=21, hmin=8, hmax=15, base=lambda x: 40 + 6 * np.sin(x / 90), color="#DDD8CF", layer=2,
               minaret=[(205, 47, 22)])
    c.terrain()
    streets = [(13.9, 4), (45, 4), (60.5, 12), (84.6, 4), (111.1, 4), (136.5, 4), (180.9, 8), (281, 10), (312.5, 8), (367.4, 8), (389.3, 8), (467.9, 8), (490.8, 8), (528.3, 8)]
    rng = np.random.default_rng(8)
    edges = [(-5, 0)] + [(p - w / 2, p + w / 2) for p, w in streets] + [(547, 552)]
    for i in range(len(edges) - 1):
        a = edges[i][1]; b = edges[i + 1][0]
        if a < 234 < b:  # open lot splits block
            blocks = [(a, 232), (276, b)]
        else:
            blocks = [(a, b)]
        for ba, bb in blocks:
            x = ba
            while x < bb - 3:
                w = min(float(rng.uniform(7, 11)), bb - x)
                if bb - (x + w) < 4: w = bb - x
                fl = int(rng.choice([2, 3, 3, 4, 4, 4, 5]))
                uses = [rng.choice(["com", "com", "log"])] + ["log"] * fl
                left_w = streets[i - 1][1] if i > 0 and x == ba else 0
                right_w = streets[i][1] if i < len(streets) and abs(x + w - bb) < 0.01 else 0
                cl = 0.9 if (x == ba and left_w >= 8) else 0
                cr = 0.9 if (abs(x + w - bb) < 0.01 and right_w >= 8) else 0
                c.building(x + 0.1, x + w - 0.1, fl, uses=uses, gf=3.4, fh=2.9, balcony=(1 if cl else -1, 0.6 if (cl or cr) else 0, "rail"),
                           cantilever=(cl, cr), rebar=rng.random() < 0.45, unfinished=rng.random() < 0.3, wall=0.25, step=True)
                x += w
    for p, w in streets:
        if w >= 8:
            parts = [(1.2, "sw"), (w - 2.4, "lane" if w < 12 else "lane"), (1.2, "sw")] if w < 12 else [(2.0, "sw"), (2.4, "park"), (3.6, "lane"), (2.0, "sw"), (2.0, "sw")]
            c.road(p - w / 2, parts, nets=True)
        else:
            def derb(cc, p=p, w=w):
                zz = cc.zg(p); cc.ax.add_patch(Rectangle((p - w / 2, zz - 0.15), w, 0.15, color="#CFC6B6", zorder=23))
                cc.person(p - 0.6, zz); cc.person(p + 0.7, zz, kid=True)
            derb.__name__ = f"d{p}"; c.custom(derb)
    def lot(cc):
        ax = cc.ax; xs = np.linspace(232, 276, 60)
        ax.fill_between(xs, [cc.zg(x) for x in xs], [cc.zg(x) + 0.25 for x in xs], color="#C5BC9A", lw=0, zorder=23)
        for x, h in ((240, 0.9), (244, 0.6), (266, 1.1)):
            ax.add_patch(Ellipse((x, cc.zg(x) + 0.2), 3.2, h, color="#8F8676", zorder=23.5))
        for gx in (247.5, 262.5):
            ax.plot([gx, gx], [cc.zg(gx), cc.zg(gx) + 2.0], color=WALL, lw=cc.lw(0.8), zorder=27)
        for x in (251, 254, 256.5, 259):
            cc.person(x, cc.zg(x), kid=True)
        ax.add_patch(Circle((255.5, cc.zg(255.5) + 0.12), 0.12, color="white", zorder=31))
    lot.__name__ = "lot"; c.custom(lot)
    c.label(254, 47, "Terrain non bâti", "seul vide du transect, sans aménagement", OCHRE)
    c.label(60.5, 49, "Rue principale", "12 m, commerces en RDC", INK)
    c.label(111, 52, "Derbs de 4 m", "sans trottoir ni arbre", SLATE)
    c.label(160, 54, "Habitat R+2 à R+5", "encorbellements, étages en attente", TERRA)
    c.label(367.4, 49, "Rues de 8 m", "voiture et piéton mélangés", INK)
    c.label(205, 70, "Mosquée de quartier", None, MUTED)
    c.dims = [0, 11.9, 15.9, 43, 47, 54.5, 66.5, 82.6, 86.6, 109.1, 113.1, 134.5, 138.5, 176.9, 184.9, 232, 276, 286, 308.5, 316.5, 363.4, 371.4, 385.3, 393.3, 463.9, 471.9, 486.8, 494.8, 524.3, 532.3, 542]
    return c


def C3():
    g = ground_profile((-5.8140, 35.7890), (-5.8030, 35.7878))
    def zf(x):
        if x >= 930: return -7.0
        v = float(np.interp(x, np.arange(len(g)), g))
        if x > 545: v = max(2.6, min(v, 3.6))
        return v
    c = Coupe(zf, 0, 1003, -10, 100, seed=7)
    c.hills([(0, 70), (300, 40), (600, 8), (1003, 4)], color="#DFE0DB", z=0.6)
    c.backdrop("medina", seed=31, hmin=7, hmax=12, base=lambda x: float(np.interp(x, [0, 150, 300, 450, 520], [74, 62, 44, 30, 26])) - 1, color="#E4E1DB", layer=2, x0=0, x1=520,
               minaret=[(60, 78, 16), (418, 32, 20)])
    c.sea(930, 1003, depth=7)
    c.terrain()
    rng = np.random.default_rng(3)
    # kasbah + medina houses (stepped on the slope)
    derbs = [8.3, 33.9, 175.4, 218.7, 255.6, 318.6, 385.6, 417.1]
    x = 0.0
    while x < 448:
        if x < 135 or x > 150:
            w = float(rng.uniform(5, 9))
            if any(abs((x + w / 2) - d) < w / 2 + 1.5 for d in derbs):
                x += 3.0; continue
            fl = int(rng.choice([1, 2, 2, 2, 3]))
            u = "hot" if rng.random() < 0.22 else "log"
            c.building(x + 0.1, x + w - 0.1, fl, uses=["log"] + [u] * fl, gf=3.2, fh=3.0, wall=0.5, step=True)
            x += w
        else:
            x = 150.5
    # kasbah wall + gate
    def kwall(cc):
        ax = cc.ax; z0 = cc.zg(138)
        ax.add_patch(Rectangle((135, z0 - 0.5), 3.2, 9.5, facecolor="#D9BE97", edgecolor=WALL, lw=cc.lw(0.8), zorder=24))
        for k in range(3):
            ax.add_patch(Rectangle((135 + k * 1.15, z0 + 9), 0.8, 0.9, facecolor="#D9BE97", edgecolor=WALL, lw=cc.lw(0.5), zorder=24))
        for x in (141, 146): cc.tree(x, cc.zg(x), h=7, r=2.5)
    kwall.__name__ = "kwall"; c.custom(kwall)
    # rampart at cliff top + cannon
    def rampart(cc):
        ax = cc.ax; z0 = cc.zg(462)
        ax.add_patch(Polygon([(458, z0 - 6), (466, z0 - 6), (464, z0 + 7.5), (459.5, z0 + 7.5)], facecolor="#D9BE97", edgecolor=WALL, lw=cc.lw(0.9), zorder=24))
        for k in range(3):
            ax.add_patch(Rectangle((459.5 + k * 1.6, z0 + 7.5), 1.0, 1.0, facecolor="#D9BE97", edgecolor=WALL, lw=cc.lw(0.5), zorder=24))
        for k in range(4): cc.person(445 + k * 2.4, cc.zg(445 + k * 2.4))
        xs = np.linspace(470, 545, 60)
        for x in xs[::6]: cc.tree(x, cc.zg(x), h=float(rng.uniform(3, 6)), r=1.6, cols=["#7C8F6A", "#93A47E", "#A9B691", "#B8C2A0"])
    rampart.__name__ = "rampart"; c.custom(rampart)
    c.road(548, [(3, "sw"), (7, "lane"), (3, "medpalm"), (7, "lane-"), (3, "sw"), (7, "lane"), (3, "medpalm"), (7, "lane-"), (5, "sw")], name="Av. Mohammed VI", sub="boulevard du port, env. 50 m")
    def port(cc):
        ax = cc.ax
        xs = np.linspace(596, 930, 200)
        ax.fill_between(xs, [cc.zg(x) - 0.3 for x in xs], [cc.zg(x) for x in xs], color="#D9D0BF", lw=0, zorder=23)
        for x in (612, 640, 668): cc.palm(x, cc.zg(x), h=11)
        for x in np.arange(604, 690, 7): cc.person(x + rng.uniform(-2, 2), cc.zg(x))
        for k, x in enumerate((706, 722, 738)): cc.zp = 29; cc.bus(x, cc.zg(x), col=["#E9E4DA", "#D7DDE0", "#EBDCC9"][k]); cc.zp = 30
        for x in (757, 763, 769, 775, 781): cc.car(x, cc.zg(x))
        # quay wall
        ax.add_patch(Rectangle((928.5, -7.5), 1.5, cc.zg(925) + 7.5, facecolor="#BDB3A2", edgecolor=WALL, lw=cc.lw(0.6), zorder=24))
        for k in range(4): cc.person(915 + k * 3, cc.zg(915 + k * 3))
        for x in (940, 958, 978): cc.yacht(x, L=float(rng.uniform(11, 15)))
    port.__name__ = "port"; c.custom(port)
    c.building(800, 905, 2, uses=["com", "equip", "com"], gf=5.0, fh=4.5, balcony=(1, 0.0, "glass"), wall=0.3,
               label=("Gare maritime et commerces", "terminal de croisière et ferry", OCHRE))
    c.label(70, 80, "Kasbah", "env. 74 m d'altitude", TERRA)
    c.label(140, 70, "Bab el Kasbah", None, MUTED)
    c.label(300, 52, "Médina", "maisons R+1 à R+3, derbs de 2 à 4 m", TERRA)
    c.label(380, 38, "Riads convertis", "maisons d'hôtes (en rouge)", TERRA)
    c.label(462, 34, "Remparts", "falaise de 20 m sur le port", INK)
    c.label(650, 16, "Esplanade du port", "réaménagée par la SAPT (2010-2018)", OCHRE)
    c.label(745, 9, "Cars de tourisme", None, MUTED)
    c.label(960, 4, "Marina", "Tanja Marina Bay, 2018", SEA_D)
    c.dims = [0, 135, 150, 458, 548, 596, 800, 905, 930, 1003]
    return c


if __name__ == "__main__" and len(sys.argv) > 1:
    if sys.argv[1] == "c2":
        c = C2(); c.render("maps/k2_full.png", ppm=6.4, frame=[(30, 140, 28, 56, 1), (215, 330, 30, 60, 2)])
        c.render("maps/k2_zoomA.png", ppm=22, xlim=(30, 140), zlim=(28, 56), labels=False, chain=False)
        c.render("maps/k2_zoomB.png", ppm=22, xlim=(215, 330), zlim=(30, 60), labels=False, chain=False)
    if sys.argv[1] == "c3":
        c = C3(); c.render("maps/k3_full.png", ppm=3.5, frame=[(300, 420, 20, 62, 1), (445, 600, -2, 32, 2), (780, 1003, -8, 25, 3)])
        c.render("maps/k3_zoomA.png", ppm=16, xlim=(300, 420), zlim=(20, 62), labels=False, chain=False)
        c.render("maps/k3_zoomB.png", ppm=10, xlim=(445, 600), zlim=(-2, 32), labels=False, chain=False)
        c.render("maps/k3_zoomC.png", ppm=10, xlim=(780, 1003), zlim=(-8, 25), labels=False, chain=False)
