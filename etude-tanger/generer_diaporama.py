# -*- coding: utf-8 -*-
"""Tanger, ville-vitrine : deck critique en français, cartes et schémas vectoriels natifs."""
import math
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree

W, H = 1920, 1080
EMU = 6350  # 1 px
FONT = "Inter"

PAPER = "F5F1EA"; INK = "1C1C1C"; MUTED = "6E6A64"; RULE = "CFC8BC"
TOUR = "C8462B"; TOUR_L = "F2CDBF"
LIVE = "1F3A5F"; LIVE_L = "C9D5E3"
SEA = "D3E3EA"; LAND = "EFE9DE"; GREEN = "8FAE82"; GREEN_L = "D5E3CC"
BUILT = "D4CCBE"; GOLD = "D9A441"; WHITE = "FFFFFF"

prs = Presentation()
prs.slide_width = Emu(W * EMU)
prs.slide_height = Emu(H * EMU)
BLANK = prs.slide_layouts[6]
TOTAL = 17


def px(v):
    return Emu(int(round(v * EMU)))


def rgb(h):
    return RGBColor.from_string(h)


def _line(shape, color, width, dash=None):
    if color is None:
        shape.line.fill.background()
        return
    shape.line.color.rgb = rgb(color)
    shape.line.width = px(width)
    if dash:
        ln = shape.line._get_or_add_ln()
        pd = etree.SubElement(ln, qn("a:prstDash"))
        pd.set("val", dash)


def _fill(shape, color, alpha=None):
    if color is None:
        shape.fill.background()
        return
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(color)
    if alpha is not None:
        srgb = shape.fill._xPr.find(qn("a:solidFill")).find(qn("a:srgbClr"))
        a = etree.SubElement(srgb, qn("a:alpha"))
        a.set("val", str(int(alpha * 100000)))


def _noshadow(shape):
    sp = shape._element.spPr
    etree.SubElement(sp, qn("a:effectLst"))


def rect(s, x, y, w, h, fill=None, line=None, lw=2, radius=None, alpha=None, dash=None):
    shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                             px(x), px(y), px(w), px(h))
    if radius:
        shp.adjustments[0] = min(0.5, radius / min(w, h))
    _fill(shp, fill, alpha); _line(shp, line, lw, dash); _noshadow(shp)
    return shp


def oval(s, cx, cy, r, fill=None, line=None, lw=2, alpha=None, ry=None):
    ry = ry or r
    shp = s.shapes.add_shape(MSO_SHAPE.OVAL, px(cx - r), px(cy - ry), px(2 * r), px(2 * ry))
    _fill(shp, fill, alpha); _line(shp, line, lw); _noshadow(shp)
    return shp


def text(s, x, y, w, h, content, size=14, color=INK, bold=False, italic=False,
         align="l", anchor="t", spacing=1.15, font=FONT, caps=False):
    """content: str (\n = paragraph) or list of paragraphs; paragraph = str or list of runs
    run = (text, {opts})"""
    tb = s.shapes.add_textbox(px(x), px(y), px(w), px(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    paras = content.split("\n") if isinstance(content, str) else content
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        para.line_spacing = spacing
        runs = [(p, {})] if isinstance(p, str) else p
        for rt, o in runs:
            r = para.add_run()
            r.text = rt.upper() if (o.get("caps", caps)) else rt
            f = r.font
            f.name = font
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.color.rgb = rgb(o.get("color", color))
    return tb


def poly(s, pts, fill=None, line=None, lw=2, closed=True, alpha=None, dash=None):
    ff = s.shapes.build_freeform(px(pts[0][0]), px(pts[0][1]), scale=1.0)
    ff.add_line_segments([(px(x), px(y)) for x, y in pts[1:]], close=closed)
    shp = ff.convert_to_shape()
    if not closed:
        fill = None
    _fill(shp, fill, alpha); _line(shp, line, lw, dash); _noshadow(shp)
    return shp


def seg(s, x1, y1, x2, y2, color=INK, lw=2, dash=None, head=False, tail=False):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, px(x1), px(y1), px(x2), px(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = px(lw)
    ln = c.line._get_or_add_ln()
    if dash:
        pd = etree.SubElement(ln, qn("a:prstDash")); pd.set("val", dash)
    if tail:
        e = etree.SubElement(ln, qn("a:headEnd")); e.set("type", "triangle"); e.set("w", "med"); e.set("len", "med")
    if head:
        e = etree.SubElement(ln, qn("a:tailEnd")); e.set("type", "triangle"); e.set("w", "med"); e.set("len", "med")
    return c


def path(s, pts, color=INK, lw=3, dash=None, head=False):
    """polyline; arrow head drawn as last connector segment"""
    if len(pts) > 2:
        poly(s, pts[:-1], line=color, lw=lw, closed=False, dash=dash)
    seg(s, pts[-2][0], pts[-2][1], pts[-1][0], pts[-1][1], color, lw, dash, head=head)


def smooth(pts, n=8, closed=False):
    """Catmull-Rom"""
    P = list(pts)
    if closed:
        P = [P[-1]] + P + [P[0], P[1]]
    else:
        P = [P[0]] + P + [P[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    if not closed:
        out.append(pts[-1])
    return out


def badge(s, cx, cy, label, fill=INK, r=19, size=12, fg=WHITE):
    oval(s, cx, cy, r, fill=fill, line=WHITE, lw=3)
    text(s, cx - r, cy - r, 2 * r, 2 * r, label, size=size, bold=True, color=fg, align="c", anchor="m")


def north(s, x, y):
    poly(s, [(x, y), (x + 12, y + 34), (x, y + 26), (x - 12, y + 34)], fill=INK)
    text(s, x - 20, y + 38, 40, 20, "N", size=11, bold=True, align="c")


def new_slide(num, kicker, title, subtitle=None, bg=PAPER):
    s = prs.slides.add_slide(BLANK)
    rect(s, 0, 0, W, H, fill=bg)
    if title is not None:
        text(s, 80, 50, 1200, 30, kicker, size=11, bold=True, color=TOUR, caps=True)
        text(s, 80, 80, 1760, 70, title, size=28, bold=True, spacing=1.0)
        if subtitle:
            text(s, 80, 150, 1760, 70, subtitle, size=12.5, color=MUTED, spacing=1.15)
        seg(s, 80, 222, W - 80, 222, RULE, 2)
        # footer
        seg(s, 80, H - 62, W - 80, H - 62, RULE, 1.5)
        text(s, 80, H - 50, 800, 24, "TANGER, VILLE-VITRINE  ·  CRITIQUE URBAINE", size=9, bold=True, color=MUTED)
        text(s, 760, H - 50, 400, 24, "[Nom]  ·  [Cours]  ·  [Date]", size=9, color=MUTED, align="c")
        text(s, W - 380, H - 50, 300, 24, f"{num:02d} / {TOTAL}", size=9, bold=True, color=INK, align="r")
    return s


def note(s, x, y, w, t):
    text(s, x, y, w, 24, t, size=9, italic=True, color=MUTED)


def legend_item(s, x, y, kind, color, label, w=360, color2=None):
    if kind == "box":
        rect(s, x, y + 3, 30, 20, fill=color, line=color2)
    elif kind == "hatch":
        rect(s, x, y + 3, 30, 20, fill=color, alpha=0.35, line=color, lw=2)
    elif kind == "line":
        seg(s, x, y + 13, x + 30, y + 13, color, 5)
    elif kind == "dash":
        seg(s, x, y + 13, x + 30, y + 13, color, 4, dash="dash")
    elif kind == "dot":
        oval(s, x + 15, y + 13, 9, fill=color, line=WHITE, lw=2)
    elif kind == "arrow":
        seg(s, x, y + 13, x + 30, y + 13, color, 4, head=True)
    text(s, x + 44, y, w, 26, label, size=11)


def panel_title(s, x, y, t, color=INK):
    text(s, x, y, 600, 22, t, size=10.5, bold=True, color=color, caps=True)


# ---------------------------------------------------------------- base map
COAST_N = [(0, 52), (60, 40), (120, 62), (190, 70), (260, 84), (330, 96), (400, 112),
           (450, 128), (485, 150), (505, 175)]
BAY = [(505, 175), (530, 220), (575, 262), (640, 288), (710, 294), (775, 278), (830, 248),
       (870, 205), (895, 160), (925, 135), (965, 128), (1000, 132)]
ATL_W = [(0, 52), (8, 110), (14, 200), (8, 320), (12, 460), (0, 600)]


def coast_line():
    return smooth(COAST_N, 6) + smooth(BAY, 6)[1:]


def coast_band(x_from=40, x_to=905, width=38, out=4):
    pts = [p for p in coast_line() if x_from <= p[0] <= x_to]
    a, b = [], []
    for i, (x, y) in enumerate(pts):
        p0 = pts[max(0, i - 1)]; p1 = pts[min(len(pts) - 1, i + 1)]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        a.append((x - nx * out, y - ny * out))
        b.append((x + nx * width, y + ny * width))
    return a + b[::-1]


def tangier_map(s, x0, y0, w, h, sea_label=True):
    """Draw schematic Tangier on frame; returns transform f(mx,my)->px."""
    sx, sy = w / 1000.0, h / 600.0
    f = lambda mx, my: (x0 + mx * sx, y0 + my * sy)
    rect(s, x0, y0, w, h, fill=SEA)
    land = [f(*p) for p in coast_line()] + [f(1000, 600), f(0, 600)]
    poly(s, land, fill=LAND, line=None)
    poly(s, [f(*p) for p in coast_line()], line="8C9AA0", lw=2.5, closed=False)
    if sea_label:
        text(s, *f(250, 8), 400, 24, "DÉTROIT DE GIBRALTAR", size=10, italic=True, color="5C7884", bold=True)
        tx, ty = f(640, 150)
        text(s, tx, ty, 260, 24, "Baie de Tanger", size=10, italic=True, color="5C7884")
    rect(s, x0, y0, w, h, line=RULE, lw=1.5)
    return f


def blob(s, f, cx, cy, rx, ry, fill, line=None, alpha=None, n=10, wob=0.12, seed=1, lw=2, dash=None):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1 + wob * math.sin(3 * a + seed) * math.cos(2 * a + seed * 0.7)
        pts.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
    sm = smooth(pts, 5, closed=True)
    return poly(s, [f(*p) for p in sm], fill=fill, line=line, alpha=alpha, lw=lw, dash=dash)


def label(s, f, mx, my, t, size=10.5, color=INK, bold=True, w=220, align="c", italic=False):
    x, y = f(mx, my)
    xx = x - w / 2 if align == "c" else x
    text(s, xx, y - 12, w, 40, t, size=size, color=color, bold=bold, align=align, italic=italic)


def districts(s, f, style="neutral"):
    pop = LIVE_L if style == "split" else BUILT
    a = None
    blob(s, f, 560, 330, 85, 55, BUILT, seed=2)                    # centre
    blob(s, f, 420, 380, 95, 70, pop, alpha=a, seed=3)             # Beni Makada
    blob(s, f, 285, 320, 80, 55, pop, alpha=a, seed=4)             # Mesnana
    blob(s, f, 600, 450, 85, 55, pop, alpha=a, seed=5)             # Bir Chifa
    blob(s, f, 240, 500, 95, 55, pop, alpha=a, seed=6)             # Gzenaya
    blob(s, f, 175, 150, 110, 55, GREEN_L, line=GREEN, seed=7)     # Rmilat
    blob(s, f, 860, 225, 50, 34, BUILT, seed=8)                    # Malabata


# ================================================================ SLIDE 1
s = new_slide(1, None, None, bg=PAPER)
rect(s, 0, 0, 760, H, fill=INK)
text(s, 90, 120, 600, 30, "ÉTUDE DE CAS  ·  CRITIQUE URBAINE", size=12, bold=True, color=TOUR)
text(s, 90, 175, 640, 260, "Tanger,\nville-vitrine", size=46, bold=True, color=WHITE, spacing=1.0)
text(s, 90, 430, 600, 160, "Quand l'urbanisme se met au service du tourisme : lecture critique de la transformation de Tanger, 2007-2030",
     size=16, color="D8D2C8", spacing=1.25)
seg(s, 90, 640, 190, 640, TOUR, 4)
text(s, 90, 670, 560, 160, "[Nom de l'étudiant·e]\n[Cours]  ·  [Professeur·e]\n[Date]", size=13, color="D8D2C8", spacing=1.4)
text(s, 90, 950, 600, 60, "Carte : la ville montrée (en rouge) et la ville habitée (en bleu).",
     size=10, italic=True, color="A9A39A")
f = tangier_map(s, 820, 120, 1020, 640)
districts(s, f, "split")
poly(s, [f(*p) for p in coast_band()], fill=TOUR, line=None)
for (mx, my, t) in [(420, 380, "Beni Makada"), (285, 320, "Mesnana"), (600, 450, "Bir Chifa"), (240, 500, "Gzenaya")]:
    label(s, f, mx, my, t, color=LIVE, size=11)
label(s, f, 400, 205, "Médina", color=TOUR, size=11, w=120)
label(s, f, 690, 345, "Corniche", color=TOUR, size=11)
label(s, f, 950, 245, "Malabata", color=TOUR, size=11, w=120)
label(s, f, 110, 125, "Cap Spartel", color=TOUR, size=11)
north(s, 1800, 680)
# locator
rect(s, 820, 790, 300, 190, fill=SEA, line=RULE, lw=1.5)
poly(s, [(820, 790), (1120, 790), (1120, 830), (1040, 845), (960, 830), (900, 820), (820, 815)], fill=LAND, line="8C9AA0", lw=1.5)
poly(s, [(820, 880), (900, 868), (960, 872), (1010, 862), (1120, 870), (1120, 980), (820, 980)], fill=LAND, line="8C9AA0", lw=1.5)
oval(s, 930, 872, 9, fill=TOUR, line=WHITE, lw=2)
text(s, 1000, 800, 120, 20, "ESPAGNE", size=8, bold=True, color=MUTED)
text(s, 990, 930, 120, 20, "MAROC", size=8, bold=True, color=MUTED)
text(s, 872, 890, 120, 20, "Tanger", size=9, bold=True)
text(s, 1160, 790, 680, 60, "14 km", size=24, bold=True, color=TOUR)
text(s, 1160, 852, 680, 130, "C'est la largeur du détroit à son point le plus étroit. Cette position entre Europe et Afrique est le moteur de tous les projets étudiés ici : port, marina, croisières, TGV et Mondial 2030.",
     size=12, color=INK, spacing=1.3)

# ================================================================ SLIDE 2
s = new_slide(2, "Problématique et méthode", "Pour qui construit-on Tanger ?",
              "Hypothèse : depuis 2007, la ville est d'abord aménagée pour être vue (visiteurs, investisseurs, événements), avant d'être habitée.")
text(s, 80, 255, 1760, 80, [[("« Pour ceux qui la visitent, ou pour ceux qui y vivent ? »", {"bold": True})]], size=26, color=INK)
# two columns
for i, (col, light, head, items, who) in enumerate([
    (TOUR, TOUR_L, "LA VILLE-VITRINE", ["Marina et front de mer", "Terminal de croisière", "Médina restaurée", "Corniche, hôtels de Malabata", "Grand stade, TGV Al Boraq"], "visiteurs · investisseurs · événements"),
    (LIVE, LIVE_L, "LA VILLE VÉCUE", ["Logement abordable", "Bus et grands taxis", "Écoles, santé, équipements", "Parcs et espaces verts", "Trajets vers la zone franche"], "habitants · ouvriers · familles")]):
    x = 80 + i * 620
    rect(s, x, 400, 560, 470, fill=WHITE, line=RULE, lw=1.5)
    rect(s, x, 400, 560, 12, fill=col)
    text(s, x + 36, 440, 480, 30, head, size=16, bold=True, color=col)
    text(s, x + 36, 478, 480, 24, who, size=11, italic=True, color=MUTED)
    for k, it in enumerate(items):
        oval(s, x + 46, 548 + k * 60, 7, fill=col)
        text(s, x + 70, 535 + k * 60, 460, 30, it, size=14)
oval(s, 670, 635, 38, fill=INK)
text(s, 632, 597, 76, 76, "vs", size=18, bold=True, color=WHITE, align="c", anchor="m")
# method
panel_title(s, 1360, 400, "Méthode : 4 outils")
for k, (n, t, d) in enumerate([("01", "CARTES", "où va l'investissement, où vit la population"),
                                ("02", "COUPE", "de la Kasbah à la mer : l'accès réel"),
                                ("03", "SCHÉMAS", "les mécanismes : rente, éviction, exception"),
                                ("04", "MATRICE", "qui gagne, qui paie : projet par projet")]):
    y = 440 + k * 108
    text(s, 1360, y, 80, 50, n, size=26, bold=True, color=TOUR)
    text(s, 1450, y + 2, 400, 26, t, size=14, bold=True)
    text(s, 1450, y + 32, 400, 50, d, size=11.5, color=MUTED)

# ================================================================ SLIDE 3  chronologie
s = new_slide(3, "Chronologie", "Deux calendriers : celui de l'image et celui du quotidien",
              "Les projets tournés vers l'extérieur sont livrés à l'heure ; ceux destinés aux habitants arrivent en retard, ou pas du tout.")
X0, X1 = 230, 1840
yr = lambda y: X0 + (y - 2006) / (2031 - 2006) * (X1 - X0)
AXIS = 580
BW, BH = 250, 72
rect(s, X0, AXIS - 4, X1 - X0, 8, fill=INK)
for y in range(2006, 2031, 2):
    seg(s, yr(y), AXIS - 12, yr(y), AXIS + 12, INK, 2)
    text(s, yr(y) - 40, AXIS + 18, 80, 22, str(y), size=10, bold=True, align="c", color=MUTED)
text(s, 80, 300, 140, 30, "L'IMAGE", size=12, bold=True, color=TOUR)
text(s, 80, 330, 140, 90, "tourisme,\nvitrine,\névénements", size=10, color=MUTED)
text(s, 80, 700, 145, 30, "LE QUOTIDIEN", size=10, bold=True, color=LIVE)
text(s, 80, 730, 140, 90, "logement,\ntransport,\nquartiers", size=10, color=MUTED)

def tl_box(x, y, t, d, c):
    bx = min(max(x - BW / 2, 230), 1840 - BW)
    rect(s, bx, y, BW, BH, fill=WHITE, line=c, lw=2)
    text(s, bx + 6, y + 9, BW - 12, 26, t, size=10.5, bold=True, align="c")
    text(s, bx + 6, y + 39, BW - 12, 26, d, size=10, color=c, align="c", bold=True)

top = [(2007, "Port Tanger Med", "ouverture", 1), (2013, "Tanger Métropole", "7,66 Md MAD", 1), (2018.45, "Tanja Marina Bay", "juin 2018", 1),
       (2018.9, "TGV Al Boraq", "novembre 2018", 2), (2020, "Programme médina", "850 M MAD", 3), (2024, "Stade agrandi", "65 000 → 85 000", 1),
       (2025, "167 100 croisiéristes", "+81 % en un an", 2), (2030, "Coupe du monde", "Tanger ville hôte", 1)]
for (y, t, d, lvl) in top:
    x = yr(y); ty = AXIS - 50 - BH - (lvl - 1) * 92
    seg(s, x, ty + BH, x, AXIS - 6, TOUR, 2)
    oval(s, x, AXIS, 10, fill=TOUR, line=WHITE, lw=3)
for (y, t, d, lvl) in sorted(top, key=lambda r: -r[3]):
    x = yr(y); ty = AXIS - 50 - BH - (lvl - 1) * 92
    tl_box(x, ty, t, d, TOUR)
bot = [(2009, "Ville nouvelle Chrafate", "150 000 hab. prévus", 1), (2014, "Recensement", "1,07 M habitants", 1),
       (2024, "Chrafate : 36 habitants", "Cour des comptes", 1), (2026, "Bâtiments en ruine", "98 M MAD, 2024-2027", 2)]
for (y, t, d, lvl) in bot:
    x = yr(y); ty = AXIS + 56 + (lvl - 1) * 92
    seg(s, x, AXIS + 6, x, ty, LIVE, 2)
    oval(s, x, AXIS, 8, fill=LIVE, line=WHITE, lw=3)
for (y, t, d, lvl) in sorted(bot, key=lambda r: -r[3]):
    x = yr(y); ty = AXIS + 56 + (lvl - 1) * 92
    tl_box(x, ty, t, d, LIVE)
rect(s, yr(2009), 900, yr(2030) - yr(2009), 44, fill=LIVE_L, line=LIVE, lw=1.5, dash="dash")
text(s, yr(2009) + 20, 900, 1300, 44, "2024 : 1,49 M habitants (+40 % en dix ans), et toujours pas de tramway ni de métro", size=11.5, bold=True, color=LIVE, anchor="m")

# ================================================================ SLIDE 4  tourisme en chiffres
s = new_slide(4, "Le tourisme en chiffres", "Une croissance touristique pilotée par l'offre",
              "On construit et on promet plus vite que les visiteurs n'arrivent.")
def card(x, y, w, h):
    rect(s, x, y, w, h, fill=WHITE, line=RULE, lw=1.5)
CT, CB = 245, 790          # card top / bottom
base = 650
for cx in (80, 520, 960, 1400):
    card(cx, CT, 410 if cx < 1400 else 440, CB - CT)
# A nuitées
panel_title(s, 110, 268, "Nuitées, hôtels classés")
text(s, 110, 296, 360, 22, "Tanger-Assilah, janvier-septembre", size=10, color=MUTED)
for i, (lab, v, c) in enumerate([("2024", 1.336, BUILT), ("2025", 1.55, TOUR)]):
    hh = v / 1.6 * 240; x = 150 + i * 150
    rect(s, x, base - hh, 100, hh, fill=c)
    text(s, x - 25, base - hh - 36, 150, 30, f"{v:.2f} M".replace(".", ","), size=14, bold=True, align="c")
    text(s, x, base + 10, 100, 22, lab, size=11, bold=True, align="c", color=MUTED)
text(s, 110, 700, 360, 80, [[("+16 % ", {"bold": True, "color": TOUR}), ("de nuitées, mais taux d'occupation ", {}), ("53 % → 50 %", {"bold": True})]], size=11, spacing=1.2)
# B croisières
panel_title(s, 550, 268, "Croisiéristes")
text(s, 550, 296, 360, 22, "port de Tanger Ville : réel vs objectif", size=10, color=MUTED)
mx = 750000
for i, (lab, v, c) in enumerate([("2024", 104000, BUILT), ("2025", 167100, TOUR), ("Objectif", 750000, None)]):
    hh = v / mx * 290; x = 565 + i * 120
    if c:
        rect(s, x, base - hh, 90, hh, fill=c)
    else:
        rect(s, x, base - hh, 90, hh, fill=None, line=INK, lw=2, dash="dash")
    t = "104 k" if v == 104000 else ("167 k" if v == 167100 else "750 k")
    text(s, x - 20, base - hh - 34, 130, 28, t, size=13, bold=True, align="c")
    text(s, x - 15, base + 10, 120, 22, lab, size=9.5, bold=True, align="c", color=MUTED)
text(s, 550, 700, 360, 80, [[("La promesse valait 4,5 fois le résultat.", {"bold": True, "color": TOUR})]], size=11, spacing=1.2)
# C FIFA
panel_title(s, 990, 268, "Évaluation FIFA (/5)")
text(s, 990, 296, 360, 22, "notes rapportées par la presse, 2024", size=10, color=MUTED)
for i, (lab, v, c) in enumerate([("Stade", 4.0, TOUR), ("Transports", 2.6, LIVE), ("Hôtels", 2.2, BUILT)]):
    y = 350 + i * 100
    text(s, 990, y, 200, 24, lab, size=12, bold=True)
    rect(s, 990, y + 34, 280, 30, fill="EEE9E0")
    rect(s, 990, y + 34, v / 5 * 280, 30, fill=c)
    text(s, 990 + v / 5 * 280 + 10, y + 34, 70, 30, f"{v:.1f}".replace(".", ","), size=13, bold=True, anchor="m")
text(s, 990, 672, 350, 110, [[("Réponse annoncée : ", {"bold": True}), ("permis hôteliers exceptionnels ; rien d'équivalent pour les trajets des habitants.", {})]], size=10.5, spacing=1.15)
# D ranking
panel_title(s, 1430, 268, "Classement des nuitées")
text(s, 1430, 296, 380, 22, "janvier-septembre 2025, en millions", size=10, color=MUTED)
for i, (lab, v) in enumerate([("Marrakech", 7.64), ("Agadir", 5.30), ("Casablanca", 1.86), ("Tanger", 1.55)]):
    y = 340 + i * 84
    tg = lab == "Tanger"
    text(s, 1430, y, 200, 24, lab, size=11.5, bold=tg, color=TOUR if tg else INK)
    rect(s, 1430, y + 32, v / 7.64 * 290, 26, fill=TOUR if tg else BUILT)
    text(s, 1430 + v / 7.64 * 290 + 10, y + 32, 80, 26, f"{v:.2f}".replace(".", ","), size=11.5, bold=True, anchor="m")
text(s, 1430, 690, 390, 90, [[("4e destination ", {"bold": True}), ("du pays : la ville se remodèle pour un rang qu'elle n'a pas.", {})]], size=10.5, spacing=1.15)
text(s, 80, 815, 1760, 130, [[("Lecture critique. ", {"bold": True, "color": TOUR}),
     ("Les nuitées augmentent, mais le taux d'occupation baisse : l'offre grandit plus vite que la demande. "
      "Les croisières restent très loin des 750 000 passagers annoncés. L'urbanisme suit une demande espérée, pas une demande constatée.", {})]], size=12.5, spacing=1.3)
note(s, 80, 960, 1760, "Sources : ONT via Hespress FR (nov. 2025) ; port de Tanger Ville via Finances News Hebdo et Le360 ; évaluation FIFA via Bladi (2024).")

# ================================================================ SLIDE 5  carte vitrine
s = new_slide(5, "Carte 1 : géographie de la vitrine", "L'argent suit la côte, la population s'étale au sud",
              "Les projets pour le visiteur forment un ruban littoral ; la croissance démographique se fait dans des quartiers que le visiteur ne voit pas.")
f = tangier_map(s, 80, 230, 1180, 720)
districts(s, f, "split")
poly(s, [f(*p) for p in coast_band()], fill=TOUR, line=None)
pois = [(1, 505, 172, "Port Tanger Ville, marina"), (2, 470, 200, "Médina et Kasbah"), (3, 680, 300, "Corniche"),
        (4, 875, 205, "Malabata : hôtels, résidences"), (5, 55, 70, "Cap Spartel, grottes d'Hercule"),
        (6, 770, 320, "Gare Al Boraq"), (7, 520, 520, "Grand stade Ibn Batouta")]
for n, mxp, myp, _ in pois:
    badge(s, *f(mxp, myp), str(n), fill=TOUR)
for (mxp, myp, t) in [(420, 395, "Beni Makada"), (285, 335, "Mesnana"), (610, 465, "Bir Chifa"), (240, 515, "Gzenaya, zone franche,\naéroport"), (560, 340, "Centre"), (175, 160, "Forêt de Rmilat")]:
    label(s, f, mxp, myp, t, color=LIVE if t not in ("Centre", "Forêt de Rmilat") else INK, size=11)
# arrows: growth south
for (a, b) in [((520, 300), (440, 420)), ((540, 320), (610, 480)), ((470, 290), (280, 500))]:
    seg(s, *f(*a), *f(*b), LIVE, 3, dash="dash", head=True)
north(s, 1210, 860)
note(s, 80, 958, 1180, "Carte schématique de l'auteur, positions approximatives, sans échelle.")
x = 1310
panel_title(s, x, 240, "Légende")
legend_item(s, x, 275, "box", TOUR, "Ruban de la vitrine", w=480)
legend_item(s, x, 310, "box", LIVE_L, "Quartiers populaires en forte croissance", w=480)
legend_item(s, x, 345, "box", BUILT, "Centre et autres tissus bâtis", w=480)
legend_item(s, x, 380, "box", GREEN_L, "Forêt, espaces naturels", color2=GREEN, w=480)
legend_item(s, x, 415, "dash", LIVE, "Direction de la croissance urbaine", w=480)
seg(s, x, 465, 1840, 465, RULE, 1.5)
panel_title(s, x, 480, "Projets de la vitrine")
for k, (n, _, _, t) in enumerate(pois):
    badge(s, x + 18, 528 + k * 44, str(n), fill=TOUR, r=15, size=10)
    text(s, x + 46, 516 + k * 44, 480, 26, t, size=11.5)
seg(s, x, 840, 1840, 840, RULE, 1.5)
text(s, x, 855, 530, 140, [[("Lecture : ", {"bold": True, "color": TOUR}), ("presque tous les grands projets touchent la mer ou le patrimoine. Les quartiers qui ont absorbé +430 000 habitants en dix ans n'en accueillent aucun.", {})]], size=11.5, spacing=1.25)

# ================================================================ SLIDE 6  mécanique
s = new_slide(6, "Schéma 1 : la mécanique", "Le cercle de la ville-vitrine",
              "Comment un projet d'image produit, étape par étape, de la rente pour quelques-uns et de l'éviction pour les autres.")
CX, CY, R = 600, 615, 290
nodes = [("Ambition\ninternationale", "Mondial, croisières,\nrang touristique", TOUR),
         ("Grands projets\nvitrines", "marina, corniche,\nmédina restaurée", TOUR),
         ("Hausse de la\nrente foncière", "le front de mer et la\nmédina prennent de la valeur", GOLD),
         ("Hôtels, résidences,\nmaisons d'hôtes", "le sol va à l'usage\nle plus rentable", GOLD),
         ("Hausse des prix,\ndépart des ménages", "les familles modestes\nquittent le centre", LIVE),
         ("Étalement en\npériphérie", "quartiers sous-équipés,\ninvisibles, jamais prioritaires", LIVE)]
BW2, BH2 = 300, 136
pos = []
for i in range(6):
    a_ = -math.pi / 2 + i * 2 * math.pi / 6
    pos.append((CX + R * 1.12 * math.cos(a_), CY + R * math.sin(a_)))
oval(s, CX, CY, R, line=RULE, lw=3)
for i in range(6):
    a0 = -math.pi / 2 + i * 2 * math.pi / 6 + 0.42
    a1 = -math.pi / 2 + (i + 1) * 2 * math.pi / 6 - 0.42
    pts = [(CX + R * math.cos(a0 + (a1 - a0) * t / 8), CY + R * math.sin(a0 + (a1 - a0) * t / 8)) for t in range(9)]
    path(s, pts, INK, 4, head=True)
for i, ((x, y), (t, d, c)) in enumerate(zip(pos, nodes)):
    rect(s, x - BW2 / 2, y - BH2 / 2, BW2, BH2, fill=WHITE, line=c, lw=3, radius=14)
    badge(s, x - BW2 / 2 + 4, y - BH2 / 2 + 4, str(i + 1), fill=c, r=18, size=11)
    text(s, x - BW2 / 2 + 20, y - BH2 / 2 + 12, BW2 - 40, 60, t, size=12, bold=True, align="c", spacing=1.0)
    text(s, x - BW2 / 2 + 10, y + 6, BW2 - 20, 56, d, size=9.5, color=MUTED, align="c", spacing=1.05)
text(s, CX - 140, CY - 45, 280, 30, "LE CERCLE", size=13, bold=True, color=TOUR, align="c")
text(s, CX - 140, CY - 10, 280, 60, "chaque tour renforce\nle suivant", size=11, italic=True, color=MUTED, align="c")
# who wins / who pays
x = 1200
for (yy, col, head, items) in [(245, TOUR, "QUI GAGNE", ["Promoteurs et investisseurs", "Hôtels, opérateurs de croisière", "Propriétaires du front de mer", "L'image nationale"]),
                               (610, LIVE, "QUI PAIE", ["Locataires de la médina et du centre", "Pêcheurs de l'ancien port", "Quartiers sans équipements", "Le budget public"])]:
    rect(s, x, yy, 640, 330, fill=WHITE, line=RULE, lw=1.5)
    rect(s, x, yy, 10, 330, fill=col)
    text(s, x + 36, yy + 24, 580, 30, head, size=15, bold=True, color=col)
    for k, t in enumerate(items):
        oval(s, x + 46, yy + 98 + k * 56, 6, fill=col)
        text(s, x + 66, yy + 82 + k * 56, 560, 34, t, size=13)
note(s, 1200, 958, 640, "Schéma d'analyse de l'auteur, d'après les cas étudiés.")

# ================================================================ SLIDE 7 port
s = new_slide(7, "Cas 1 : le port", "Du port qui travaille au port qui se visite",
              "La reconversion a ouvert la baie au public, mais elle a aussi remplacé le travail par la consommation de loisirs.")
def port_plan(x0, y0, after):
    rect(s, x0, y0, 560, 380, fill=SEA)
    land = [(x0, y0 + 250), (x0 + 120, y0 + 230), (x0 + 250, y0 + 255), (x0 + 400, y0 + 290), (x0 + 560, y0 + 300), (x0 + 560, y0 + 380), (x0, y0 + 380)]
    poly(s, land, fill=LAND, line="8C9AA0", lw=2)
    poly(s, [(x0 + 10, y0 + 255), (x0 + 110, y0 + 240), (x0 + 140, y0 + 330), (x0 + 30, y0 + 350)], fill=TOUR, alpha=0.8)
    text(s, x0 + 30, y0 + 285, 100, 24, "Médina", size=11, bold=True, color=WHITE)
    if not after:
        poly(s, [(x0 + 140, y0 + 240), (x0 + 200, y0 + 90), (x0 + 330, y0 + 70), (x0 + 340, y0 + 250)], fill="8A8A8A")
        seg(s, x0 + 120, y0 + 60, x0 + 360, y0 + 40, INK, 5)
        text(s, x0 + 190, y0 + 130, 150, 60, "PORT ACTIF\nferries · pêche", size=11, bold=True, color=WHITE, align="c")
        seg(s, x0 + 130, y0 + 245, x0 + 360, y0 + 265, TOUR, 3, dash="dash")
        text(s, x0 + 360, y0 + 200, 200, 40, "clôture portuaire", size=10, bold=True, color=TOUR)
        for k in range(4):
            oval(s, x0 + 420 + k * 30, y0 + 120, 9, fill=INK)
        text(s, x0 + 395, y0 + 140, 160, 40, "bateaux de pêche", size=9.5, color=INK)
    else:
        poly(s, [(x0 + 150, y0 + 240), (x0 + 190, y0 + 110), (x0 + 300, y0 + 90), (x0 + 310, y0 + 240)], fill=TOUR)
        seg(s, x0 + 120, y0 + 60, x0 + 360, y0 + 40, INK, 5)
        text(s, x0 + 180, y0 + 150, 120, 50, "MARINA\n1 400 anneaux", size=10.5, bold=True, color=WHITE, align="c")
        poly(s, [(x0 + 330, y0 + 240), (x0 + 340, y0 + 150), (x0 + 430, y0 + 150), (x0 + 440, y0 + 250)], fill=GOLD)
        text(s, x0 + 330, y0 + 175, 120, 50, "terminal\ncroisière", size=10, bold=True, color=INK, align="c")
        poly(s, [(x0 + 330, y0 + 70), (x0 + 360, y0 + 40), (x0 + 400, y0 + 40), (x0 + 380, y0 + 80)], fill="8A8A8A")
        text(s, x0 + 400, y0 + 40, 160, 40, "port de pêche\nrepoussé au large", size=9.5, bold=True)
        seg(s, x0 + 130, y0 + 262, x0 + 560, y0 + 310, "6E7F86", 10)
        seg(s, x0 + 130, y0 + 250, x0 + 560, y0 + 297, GREEN, 4)
        text(s, x0 + 400, y0 + 318, 160, 24, "route littorale", size=9.5, bold=True, color=WHITE)
        text(s, x0 + 150, y0 + 330, 140, 20, "promenade", size=9.5, bold=True, color=GREEN)
panel_title(s, 80, 230, "Avant  (port actif jusqu'aux années 2010)")
port_plan(80, 260, False)
panel_title(s, 690, 230, "Après  (inauguration le 7 juin 2018)")
port_plan(690, 260, True)
seg(s, 646, 450, 684, 450, INK, 4, head=True)
note(s, 80, 650, 1170, "Plans schématiques de l'auteur, positions indicatives.")
# usage shift diagram
panel_title(s, 80, 700, "Glissement des usages du front d'eau")
before = ["pêche", "ferries", "réparation navale", "dockers"]
after_ = ["plaisance", "croisières", "cafés et enseignes", "promenade"]
for k, t in enumerate(before):
    rect(s, 80, 740 + k * 50, 300, 40, fill="E3DED4", radius=8)
    text(s, 80, 740 + k * 50, 300, 40, t, size=12, bold=True, align="c", anchor="m")
for k, t in enumerate(after_):
    c = GREEN if t == "promenade" else TOUR
    rect(s, 950, 740 + k * 50, 300, 40, fill=c, radius=8)
    text(s, 950, 740 + k * 50, 300, 40, t, size=12, bold=True, align="c", anchor="m", color=WHITE)
for k in range(4):
    seg(s, 395, 760 + k * 50, 935, 760 + k * 50, MUTED, 2, dash="dash", head=True)
text(s, 400, 700, 540, 26, "le travail sort, le loisir entre  →", size=11, italic=True, color=MUTED, align="r")
# figures
x = 1310
panel_title(s, x, 230, "Chiffres clés")
for k, (v, d) in enumerate([("6,2 Md MAD", "programme de reconversion du port"), ("1 400", "anneaux prévus, plus grande marina du Maroc"),
                             ("635 M MAD", "coût de la marina"), ("1,19 Md MAD", "coût du nouveau port de pêche")]):
    text(s, x, 262 + k * 84, 520, 44, v, size=20, bold=True, color=TOUR if k != 3 else LIVE)
    text(s, x, 310 + k * 84, 520, 26, d, size=10.5, color=MUTED)
seg(s, x, 610, 1840, 610, RULE, 1.5)
panel_title(s, x, 625, "Bilan")
for k, (sg, t, c) in enumerate([("+", "Promenade publique continue sur la baie", GREEN), ("−", "Port de travail rejeté hors du regard", TOUR),
                                 ("−", "Route littorale : ville et plage séparées", TOUR), ("−", "Usages payants : visiteurs et plaisanciers", TOUR)]):
    badge(s, x + 16, 678 + k * 56, sg, fill=c, r=15, size=14)
    text(s, x + 46, 664 + k * 56, 500, 30, t, size=11.5)

# ================================================================ SLIDE 8 coupe
s = new_slide(8, "Coupe A-A", "De la Kasbah à la mer : si près, si loin",
              "La coupe montre ce que le plan cache : remparts, dénivelé et route à plusieurs voies séparent la médina de l'eau.")
G = 820
prof = [(80, G - 360), (180, G - 355), (300, G - 330), (420, G - 290), (540, G - 230), (640, G - 160), (720, G - 90), (790, G - 30), (840, G), (1500, G), (1500, G + 40), (80, G + 40)]
poly(s, prof, fill="E3D9C6", line=INK, lw=2.5)
# houses
for k, (hx, hy) in enumerate([(110, G - 358), (170, G - 356), (230, G - 345), (290, G - 332), (350, G - 312), (410, G - 293), (470, G - 265), (530, G - 235), (590, G - 200), (650, G - 155)]):
    hh = 70 + (k % 3) * 15
    rect(s, hx, hy - hh, 50, hh, fill=WHITE, line=INK, lw=2)
rect(s, 700, G - 210, 34, 150, fill=TOUR, line=INK, lw=2)
# road
rect(s, 860, G - 16, 260, 16, fill="5B5B5B")
for k in range(5):
    rect(s, 880 + k * 50, G - 10, 26, 4, fill=WHITE)
for k in range(3):
    rect(s, 880 + k * 80, G - 34, 50, 18, fill="9AA3A8", line=INK, lw=1.5)
# corniche
for k in range(2):
    seg(s, 1170 + k * 50, G, 1170 + k * 50, G - 50, INK, 3)
    oval(s, 1170 + k * 50, G - 62, 18, fill=GREEN)
rect(s, 1260, G - 60, 100, 60, fill=TOUR_L, line=TOUR, lw=2)
text(s, 1260, G - 60, 100, 60, "cafés\nenseignes", size=9.5, bold=True, color=TOUR, align="c", anchor="m")
# sea
rect(s, 1500, G - 10, 340, 50, fill=SEA)
for k in range(3):
    poly(s, [(1540 + k * 100, G - 20), (1600 + k * 100, G - 20), (1590 + k * 100, G - 6), (1550 + k * 100, G - 6)], fill=WHITE, line=INK, lw=2)
    seg(s, 1570 + k * 100, G - 20, 1570 + k * 100, G - 80, INK, 2)
# walking route
wr = [(150, G - 375), (400, G - 315), (600, G - 205), (700, G - 120), (760, G - 70), (850, G - 40), (1120, G - 40), (1180, G - 15), (1480, G - 15)]
poly(s, wr, line=TOUR, lw=4, closed=False, dash="dash")
badge(s, 990, G - 70, "!", fill=TOUR, r=18, size=14)
# callouts
for (bx, by, t, ax, ay, c) in [(330, 260, "Dénivelé et remparts : la vieille\nville regarde la mer de haut", 560, G - 240, TOUR),
                               (760, 260, "Route à plusieurs voies :\nla vraie frontière", 990, G - 95, INK),
                               (1150, 440, "Espace public organisé\nautour de la consommation", 1310, G - 66, TOUR),
                               (1490, 260, "Anneaux privés :\nl'eau est aux plaisanciers", 1670, G - 85, LIVE)]:
    rect(s, bx, by, 340, 84, fill=WHITE, line=c, lw=2)
    text(s, bx + 10, by + 8, 320, 70, t, size=10.5, bold=True, color=c, align="c", anchor="m")
    seg(s, bx + 170, by + 84, ax, ay, c, 2, head=True)
for (x1, x2, t, c) in [(80, 690, "KASBAH ET MÉDINA", TOUR), (695, 845, "REMPART", TOUR), (850, 1130, "ROUTE LITTORALE", INK), (1135, 1490, "CORNICHE", LIVE), (1495, 1840, "MARINA ET MER", LIVE)]:
    seg(s, x1, G + 80, x2, G + 80, c, 4)
    text(s, x1, G + 92, x2 - x1, 24, t, size=10.5, bold=True, color=c, align="c")
legend_item(s, 80, 950, "dash", TOUR, "parcours piéton depuis la médina : escaliers, portes, traversée dangereuse", w=900)
note(s, 1100, 958, 740, "Coupe schématique de l'auteur, sans échelle.")

# ================================================================ SLIDE 9 médina
s = new_slide(9, "Cas 2 : la médina", "Réhabiliter, ou repeindre le décor ?",
              "Le programme 2020-2024 suit les parcours des visiteurs ; l'habitat qui menace ruine relève d'un budget séparé, près de neuf fois plus petit.")
x0, y0, ww, hh = 80, 240, 1080, 680
rect(s, x0, y0, ww, hh, fill=LAND, line=RULE, lw=1.5)
poly(s, [(x0, y0), (x0 + ww, y0), (x0 + ww, y0 + 120), (x0 + 700, y0 + 90), (x0 + 400, y0 + 60), (x0, y0 + 80)], fill=SEA)
text(s, x0 + 420, y0 + 16, 300, 24, "BAIE ET PORT", size=10, bold=True, italic=True, color="5C7884")
wall = smooth([(130, 360), (330, 320), (560, 330), (800, 360), (980, 430), (1060, 580), (980, 760), (760, 860), (480, 870), (230, 800), (120, 640)], 6, closed=True)
poly(s, wall, fill="E8DFCF", line=INK, lw=6)
# residential tissue
for (cx, cy, rx, ry, sd) in [(330, 560, 150, 110, 2), (620, 720, 170, 90, 3), (860, 560, 110, 120, 4), (450, 430, 100, 50, 5)]:
    pts = [(cx + rx * math.cos(2 * math.pi * i / 10) * (1 + 0.1 * math.sin(i * sd)), cy + ry * math.sin(2 * math.pi * i / 10) * (1 + 0.1 * math.cos(i * sd))) for i in range(10)]
    poly(s, smooth(pts, 4, closed=True), fill=LIVE_L, line=LIVE, lw=1.5, dash="dash")
# ruin markers
import random
random.seed(4)
for (cx, cy, rx, ry) in [(330, 560, 130, 90), (620, 720, 150, 70), (860, 560, 90, 100), (450, 430, 80, 35)]:
    for _ in range(6):
        a = random.random() * 2 * math.pi; r = random.random() ** 0.5
        px_, py_ = cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)
        poly(s, [(px_, py_ - 9), (px_ + 9, py_ + 7), (px_ - 9, py_ + 7)], fill=LIVE)
# tourist circuit
circ = smooth([(560, 880), (600, 790), (520, 640), (600, 520), (720, 430), (840, 410), (950, 470)], 6)
poly(s, circ, line=TOUR, lw=12, closed=False)
circ2 = smooth([(600, 520), (520, 420), (380, 380), (240, 410), (180, 470)], 6)
poly(s, circ2, line=TOUR, lw=12, closed=False)
for (cx, cy, t, al) in [(560, 880, "Grand Socco", "l"), (600, 520, "Petit Socco", "l"), (180, 470, "Kasbah", "l"), (950, 470, "Porte du port", "l")]:
    oval(s, cx, cy, 16, fill=WHITE, line=TOUR, lw=5)
    text(s, cx + (22 if al == "l" else -90), cy + (-40 if al == "l" else 20), 200, 26, t, size=11.5, bold=True, color=TOUR)
note(s, 80, 935, 1080, "Plan conceptuel de l'auteur : parcours indicatifs, non relevés ; triangles illustratifs.")
x = 1220
panel_title(s, x, 245, "Légende")
legend_item(s, x, 278, "line", TOUR, "Circuit des visiteurs, restauré en priorité", w=560)
legend_item(s, x, 313, "box", LIVE_L, "Tissu résidentiel dense et vieillissant", color2=LIVE, w=560)
poly(s, [(x + 15, 350), (x + 27, 370), (x + 3, 370)], fill=LIVE)
text(s, x + 44, 348, 560, 26, "Bâtiment menaçant ruine", size=11)
seg(s, x, 395, 1840, 395, RULE, 1.5)
panel_title(s, x, 410, "Où va l'argent ?")
for k, (lab, v, c) in enumerate([("Programme médina 2020-2024", 850, TOUR), ("Bâtiments menaçant ruine 2024-2027", 98, LIVE)]):
    y = 445 + k * 92
    text(s, x, y, 600, 26, lab, size=11.5, bold=True)
    bw = v / 850 * 440
    rect(s, x, y + 32, bw, 40, fill=c)
    text(s, x + bw + 12, y + 32, 200, 40, ("850 M MAD" if k == 0 else "≈ 98 M MAD"), size=13, bold=True, anchor="m", color=c)
text(s, x, 640, 620, 50, "× 8,7", size=26, bold=True, color=TOUR)
text(s, x + 150, 646, 470, 60, "plus d'argent pour le décor que pour la sécurité des logements", size=11.5, spacing=1.2)
seg(s, x, 725, 1840, 725, RULE, 1.5)
for k, (v, d) in enumerate([("26 ha", "surface de la médina"), ("328", "bâtiments résidentiels menaçant ruine"), ("4 axes", "espace urbain, patrimoine, lieux de culte, attractivité touristique")]):
    text(s, x, 742 + k * 70, 170, 50, v, size=20, bold=True, color=LIVE if k == 1 else INK)
    text(s, x + 170, 748 + k * 70, 450, 60, d, size=10.5, color=MUTED, spacing=1.1)

# ================================================================ SLIDE 10 touristification
s = new_slide(10, "Schéma 2 : la touristification", "De la médina habitée à la médina-décor",
              "Un processus en cinq étapes, documenté dans d'autres médinas marocaines. À Tanger, chaque étape reste une hypothèse à vérifier sur le terrain.")
steps = [("Restaurer", "les façades", "portes, places et parcours visibles sont refaits en premier", "façades restaurées vs ruelles résidentielles"),
         ("Acheter", "les maisons", "des investisseurs achètent dar et riads", "annonces « projet maison d'hôtes »"),
         ("Convertir", "en hébergement", "maisons d'hôtes et locations de courte durée", "nombre d'hébergements par rue"),
         ("Monter", "les prix", "loyers et prix hors de portée des familles, qui partent", "loyers, prix au m², ménages partis"),
         ("Exposer", "la médina-décor", "souvenirs et cafés remplacent épiceries, artisans, fours", "commerces de proximité vs souvenirs")]
for i, (t1, t2, d, ind) in enumerate(steps):
    x = 80 + i * 356; y = 610 - i * 72
    c = [TOUR, TOUR, GOLD, LIVE, INK][i]
    rect(s, x, y, 320, 120, fill=c, radius=12)
    text(s, x + 22, y + 22, 60, 70, f"{i + 1}", size=32, bold=True, color=WHITE)
    text(s, x + 82, y + 24, 230, 34, t1, size=17, bold=True, color=WHITE)
    text(s, x + 82, y + 62, 230, 34, t2, size=13, color=WHITE)
    text(s, x, y + 134, 320, 80, d, size=11.5, color=INK, spacing=1.2)
    rect(s, x, 870, 320, 92, fill=WHITE, line=c, lw=2)
    text(s, x + 16, 880, 290, 20, "À OBSERVER", size=8.5, bold=True, color=c)
    text(s, x + 16, 904, 290, 54, ind, size=10.5, color=INK, spacing=1.1)
    if i < 4:
        seg(s, x + 324, y + 30, x + 352, y - 20, INK, 3, head=True)
text(s, 80, 248, 1200, 26, "TEMPS  →  la valeur touristique monte, la population résidente baisse", size=10.5, bold=True, color=MUTED)
seg(s, 80, 290, 1840, 290, MUTED, 2, dash="dash", head=True)
seg(s, 80, 850, 1840, 850, RULE, 1.5)

# ================================================================ SLIDE 11 Mondial
s = new_slide(11, "Cas 3 : Mondial 2030", "Mondial 2030 : l'urbanisme d'exception",
              "Le stade est noté 4/5, les hôtels 2,2/5. La réponse annoncée : construire vite, par dérogation, pour une date fixée de l'extérieur.")
panel_title(s, 80, 240, "Capacité du grand stade Ibn Batouta (places)")
for k, (lab, v, c) in enumerate([("Origine", 45000, BUILT), ("Après extension", 65000, TOUR), ("Objectif Mondial", 85000, TOUR)]):
    xx = 120 + k * 190; hh = v / 85000 * 380
    rect(s, xx, 720 - hh, 130, hh, fill=c, alpha=None if k < 2 else 0.55, line=TOUR if k == 2 else None, lw=2, dash="dash" if k == 2 else None)
    text(s, xx - 20, 720 - hh - 34, 170, 30, (">40 000" if k == 0 else f"{v:,}".replace(",", " ") if k == 1 else "≥85 000"), size=14, bold=True, align="c")
    text(s, xx - 20, 730, 170, 44, lab, size=10.5, bold=True, align="c", color=MUTED)
text(s, 80, 790, 620, 140, [[("Lecture : ", {"bold": True, "color": TOUR}), ("deux agrandissements successifs pour quelques matchs, alors que la ville n'a toujours pas de transport en site propre.", {})]], size=12, spacing=1.25)
# rule vs exception diagram
x = 780
panel_title(s, x, 240, "Deux chemins pour construire")
text(s, x, 280, 300, 26, "LA RÈGLE", size=13, bold=True, color=LIVE)
rule = ["Plan\nd'aménagement", "Enquête\npublique", "Avis des\nhabitants", "Permis de\nconstruire"]
for k, t in enumerate(rule):
    bx = x + k * 265
    rect(s, bx, 320, 220, 100, fill=WHITE, line=LIVE, lw=2.5, radius=10)
    text(s, bx, 320, 220, 100, t, size=13, bold=True, align="c", anchor="m", color=LIVE)
    if k < 3:
        seg(s, bx + 224, 370, bx + 261, 370, LIVE, 3, head=True)
text(s, x, 445, 1000, 26, "temps long, débat public, arbitrage entre usages", size=11, italic=True, color=MUTED)
text(s, x, 520, 300, 26, "L'EXCEPTION", size=13, bold=True, color=TOUR)
exc = ["Événement\n(Mondial 2030)", "Urgence\n« date FIFA »", "Autorisation\nexceptionnelle", "Hôtels et\nrésidences"]
for k, t in enumerate(exc):
    bx = x + k * 265
    rect(s, bx, 560, 220, 100, fill=TOUR, radius=10)
    text(s, bx, 560, 220, 100, t, size=13, bold=True, align="c", anchor="m", color=WHITE)
    if k < 3:
        seg(s, bx + 224, 610, bx + 261, 610, TOUR, 3, head=True)
text(s, x, 685, 1000, 26, "temps court, décision d'en haut, priorité au visiteur", size=11, italic=True, color=MUTED)
# skip arrows
seg(s, x + 110 + 265, 560, x + 110 + 265, 430, TOUR, 2, dash="dash")
seg(s, x + 110 + 530, 560, x + 110 + 530, 430, TOUR, 2, dash="dash")
text(s, x + 420, 492, 220, 30, "étapes contournées", size=10.5, bold=True, color=TOUR, align="c")
rect(s, x, 750, 1060, 190, fill=WHITE, line=RULE, lw=1.5)
rect(s, x, 750, 10, 190, fill=TOUR)
text(s, x + 36, 768, 1000, 160, [[("La critique. ", {"bold": True, "color": TOUR}),
     ("Quand la date du tournoi devient l'horizon du projet urbain, ce qui peut être livré à temps (stade, hôtels, façades) passe devant ce qui demande du temps (logement social, transport, équipements). "
      "L'héritage du Mondial devra se mesurer dans les quartiers, pas dans les tribunes.", {})]], size=12, spacing=1.3)
note(s, 80, 958, 700, "Capacités : Medias24 (2024). Notes FIFA : presse (Bladi, 2024). Schéma de l'auteur.")

# ================================================================ SLIDE 12 Chrafate
s = new_slide(12, "Cas 4 : Chrafate", "La ville des ouvriers n'a pas été construite",
              "Pendant que la marina, la gare TGV et le stade sortaient de terre, la ville prévue pour les ouvriers de l'industrie restait presque vide.")
x0, y0 = 80, 240
rect(s, x0, y0, 760, 520, fill=SEA)
land = [(x0, y0 + 130), (x0 + 120, y0 + 110), (x0 + 220, y0 + 150), (x0 + 300, y0 + 120), (x0 + 420, y0 + 100), (x0 + 560, y0 + 70), (x0 + 660, y0 + 80), (x0 + 760, y0 + 110)]
poly(s, smooth(land, 5) + [(x0 + 760, y0 + 520), (x0, y0 + 520)], fill=LAND, line=None)
poly(s, smooth(land, 5), line="8C9AA0", lw=2, closed=False)
rect(s, x0, y0, 760, 520, line=RULE, lw=1.5)
text(s, x0 + 220, y0 + 30, 360, 24, "DÉTROIT DE GIBRALTAR", size=10, bold=True, italic=True, color="5C7884")
pts = {"Tanger": (x0 + 150, y0 + 170), "Tanger Med": (x0 + 640, y0 + 120), "Chrafate": (x0 + 420, y0 + 380), "Renault / TAC": (x0 + 330, y0 + 300)}
seg(s, *pts["Tanger"], x0 + 500, y0 + 330, INK, 5)
seg(s, x0 + 500, y0 + 330, *pts["Tanger Med"], INK, 5)
seg(s, *pts["Tanger"], *pts["Chrafate"], TOUR, 3, dash="dash")
text(s, x0 + 200, y0 + 300, 120, 30, "≈ 18 km", size=12, bold=True, color=TOUR)
oval(s, *pts["Tanger"], 34, fill=INK)
text(s, pts["Tanger"][0] - 80, pts["Tanger"][1] - 75, 160, 30, "TANGER", size=12, bold=True, align="c")
oval(s, *pts["Tanger Med"], 16, fill=LIVE, line=WHITE, lw=3)
text(s, pts["Tanger Med"][0] - 100, pts["Tanger Med"][1] + 22, 200, 30, "Port Tanger Med", size=11, bold=True, align="c", color=LIVE)
rect(s, pts["Renault / TAC"][0] - 14, pts["Renault / TAC"][1] - 14, 28, 28, fill=LIVE)
text(s, pts["Renault / TAC"][0] + 22, pts["Renault / TAC"][1] - 14, 200, 30, "Renault / TAC", size=11, bold=True, color=LIVE)
oval(s, *pts["Chrafate"], 46, fill=None, line=TOUR, lw=3)
oval(s, *pts["Chrafate"], 6, fill=TOUR)
text(s, pts["Chrafate"][0] - 130, pts["Chrafate"][1] + 54, 260, 40, "CHRAFATE\nville prévue, restée vide", size=11, bold=True, align="c", color=TOUR)
note(s, 80, 770, 760, "Carte schématique de l'auteur, positions approximatives.")
# dots
x = 900
panel_title(s, x, 240, "Prévu vs compté")
text(s, x, 266, 900, 22, "chaque point = 1 500 habitants prévus", size=10.5, color=MUTED)
for i in range(100):
    cx = x + 14 + (i % 20) * 40; cy = 316 + (i // 20) * 40
    oval(s, cx, cy, 13, fill=LIVE_L, line=LIVE, lw=1.5)
text(s, x, 510, 420, 60, "150 000", size=30, bold=True, color=LIVE)
text(s, x, 578, 420, 30, "habitants prévus (Al Omrane, 2009)", size=11, color=MUTED)
oval(s, x + 478, 540, 3, fill=TOUR)
text(s, x + 500, 510, 340, 60, "36", size=30, bold=True, color=TOUR)
text(s, x + 500, 578, 420, 30, "comptés (Cour des comptes, 2024)", size=11, color=MUTED)
seg(s, x, 630, 1840, 630, RULE, 1.5)
for k, (v, d) in enumerate([("2009", "lancement"), ("24 Md MAD", "investissement annoncé"), ("2025", "relance annoncée")]):
    text(s, x + k * 320, 648, 300, 44, v, size=20, bold=True)
    text(s, x + k * 320, 700, 300, 30, d, size=11, color=MUTED)
rect(s, x, 760, 940, 185, fill=WHITE, line=RULE, lw=1.5)
rect(s, x, 760, 10, 185, fill=TOUR)
text(s, x + 36, 776, 880, 160, [[("Le contraste. ", {"bold": True, "color": TOUR}),
     ("Les projets pour le visiteur ont été livrés en moins de dix ans. Le projet pour les ouvriers qui font tourner le port et les usines attend depuis 2009. "
      "La main-d'œuvre vit donc dans les quartiers les plus denses et fait de longs trajets.", {})]], size=12, spacing=1.3)

# ================================================================ SLIDE 13 mobilité
s = new_slide(13, "Carte 2 : mobilité", "Deux réseaux : un pour arriver, un pour vivre",
              "Tanger est très bien reliée à Casablanca, à l'Europe et aux paquebots. Entre ses quartiers, elle dépend de la voiture, du bus et du grand taxi.")
f = tangier_map(s, 80, 230, 1180, 720)
districts(s, f, "split")
for (mxp, myp, t) in [(420, 395, "Beni Makada"), (285, 335, "Mesnana"), (610, 465, "Bir Chifa"), (240, 515, "Gzenaya")]:
    label(s, f, mxp, myp, t, color=LIVE, size=11)
label(s, f, 560, 340, "Centre", size=11)
# network of the showcase
tgv = smooth([(770, 320), (760, 400), (720, 500), (690, 600)], 6)
poly(s, [f(*p) for p in tgv], line=TOUR, lw=7, closed=False)
label(s, f, 600, 520, "TGV Al Boraq vers\nRabat, Casablanca", color=TOUR, size=11, w=220)
seg(s, *f(505, 172), *f(470, 30), TOUR, 6, head=True)
label(s, f, 600, 40, "ferries et paquebots", color=TOUR, size=11)
cor = smooth([(505, 185), (560, 250), (640, 282), (710, 288), (775, 272), (830, 242), (870, 205)], 6)
poly(s, [f(*p) for p in cor], line=TOUR, lw=7, closed=False)
seg(s, *f(870, 205), *f(990, 260), TOUR, 6, head=True)
label(s, f, 930, 330, "vers Tanger Med", color=TOUR, size=11, w=170)
badge(s, *f(770, 320), "", fill=TOUR, r=12)
badge(s, *f(505, 175), "", fill=TOUR, r=12)
# daily network
for a, b in [((420, 380), (240, 500)), ((285, 320), (240, 500)), ((420, 380), (560, 330)), ((600, 450), (560, 330)), ((600, 450), (960, 470))]:
    seg(s, *f(*a), *f(*b), LIVE, 4, dash="sysDash", head=True)
label(s, f, 880, 420, "navettes vers les\nzones industrielles", color=LIVE, size=11, w=220)
oval(s, *f(150, 560), 14, fill=INK)
label(s, f, 150, 590, "Aéroport", size=10.5)
north(s, 1210, 860)
note(s, 80, 958, 1180, "Schéma de l'auteur. L'épaisseur des traits indique la priorité donnée par l'investissement, pas des flux mesurés.")
x = 1310
panel_title(s, x, 240, "Légende")
legend_item(s, x, 275, "line", TOUR, "Réseau de la vitrine : TGV, port, corniche", w=490)
legend_item(s, x, 310, "dash", LIVE, "Réseau du quotidien : bus, taxis, navettes", w=490)
legend_item(s, x, 345, "box", LIVE_L, "Quartiers populaires", w=490)
seg(s, x, 395, 1840, 395, RULE, 1.5)
panel_title(s, x, 410, "Comparer")
rect(s, x, 445, 530, 120, fill=TOUR, radius=10)
text(s, x + 24, 458, 490, 34, "Tanger → Casablanca", size=14, bold=True, color=WHITE)
text(s, x + 24, 500, 490, 60, "environ 2 h 10 en TGV, depuis 2018", size=12, color=WHITE)
rect(s, x, 585, 530, 130, fill=LIVE, radius=10)
text(s, x + 24, 598, 490, 34, "Beni Makada → zone franche", size=14, bold=True, color=WHITE)
text(s, x + 24, 640, 490, 70, "aucun transport en site propre : bus, taxi ou navette d'entreprise", size=12, color=WHITE, spacing=1.15)
seg(s, x, 740, 1840, 740, RULE, 1.5)
panel_title(s, x, 755, "Ce qui manque")
for k, t in enumerate(["Une ligne de tram ou de BHNS", "Des traversées piétonnes sûres", "Un réseau qui relie quartiers et emplois"]):
    text(s, x, 790 + k * 40, 530, 30, "—  " + t, size=12)

# ================================================================ SLIDE 14 littoral / nature
s = new_slide(14, "Schéma 3 : le littoral", "La côte : bien commun ou produit touristique ?",
              "Lecture linéaire du littoral, du cap Spartel à Malabata. À compléter par un relevé de terrain des accès publics.")
segments = [("Cap Spartel,\ngrottes d'Hercule", 230, GREEN, "nature mise en scène,\naccès payants ou en voiture"),
            ("Forêt de Rmilat\net côte ouest", 300, GREEN_L, "pression des villas\net résidences"),
            ("Kasbah\net médina", 170, TOUR_L, "vue sur la mer depuis\nles terrasses d'hôtels"),
            ("Port et marina", 230, TOUR, "eau réservée aux\nplaisanciers et paquebots"),
            ("Corniche", 360, GOLD, "promenade publique,\nbordée de cafés"),
            ("Malabata", 270, LIVE, "hôtels, résidences fermées,\nvue privatisée")]
x = 160
tot = sum(w for _, w, _, _ in segments)
sc = 1600 / tot
rect(s, 160, 290, 1600, 90, fill=SEA)
text(s, 160, 296, 1600, 24, "MER  ·  DÉTROIT ET BAIE", size=10, bold=True, italic=True, color="5C7884", align="c")
for t, w, c, d in segments:
    ww = w * sc
    rect(s, x, 380, ww, 90, fill=c, line=WHITE, lw=3)
    text(s, x + 8, 380, ww - 16, 90, t, size=12, bold=True, align="c", anchor="m", color=WHITE if c in (TOUR, GREEN, LIVE) else INK)
    text(s, x + 8, 486, ww - 16, 70, d, size=10.5, align="c", color=INK)
    x += ww
text(s, 80, 410, 70, 30, "OUEST", size=10, bold=True, color=MUTED)
text(s, 1775, 410, 70, 30, "EST", size=10, bold=True, color=MUTED)
# access gauge
text(s, 160, 612, 1600, 26, "DEGRÉ D'ACCÈS LIBRE AU RIVAGE (LECTURE DE L'AUTEUR)", size=10.5, bold=True)
x = 160
for (t, w, c, d), lvl in zip(segments, [2, 1, 1, 1, 3, 1]):
    ww = w * sc
    for k in range(3):
        rect(s, x + 10, 650 + (2 - k) * 30, ww - 20, 22, fill=(INK if k < lvl else "E3DED4"))
    x += ww
text(s, 160, 748, 1600, 24, "3 barres = accès libre et gratuit  ·  1 barre = accès limité, payant ou privatisé", size=10.5, color=MUTED)
rect(s, 160, 795, 1600, 150, fill=WHITE, line=RULE, lw=1.5)
rect(s, 160, 795, 10, 150, fill=TOUR)
text(s, 196, 812, 1540, 130, [[("Lecture critique. ", {"bold": True, "color": TOUR}),
     ("Du cap Spartel à Malabata, seule la corniche reste un espace pleinement public. Partout ailleurs, la mer est transformée en vue que l'on vend (hôtel, résidence, marina) "
      "ou en paysage que l'on visite. La pression avance vers la forêt de Rmilat et le cap Spartel : sans limite ferme, ce sera le prochain front bâti.", {})]], size=12.5, spacing=1.3)

# ================================================================ SLIDE 15 matrice
s = new_slide(15, "Matrice d'évaluation", "Qui gagne ? Six projets, quatre groupes",
              "Pour chaque projet : à qui profite-t-il réellement ?")
cols = ["Visiteurs et\ncroisiéristes", "Investisseurs et\npromoteurs", "Habitants du\ncentre et de la médina", "Habitants des\npériphéries"]
ccol = [TOUR, TOUR, LIVE, LIVE]
rows = [("Port et marina", [2, 2, 1, 0]), ("Programme médina", [2, 2, 1, 0]), ("Corniche", [2, 1, 2, 1]),
        ("Stade et Mondial 2030", [2, 2, 0, 0]), ("TGV Al Boraq", [2, 2, 1, 0]), ("Ville nouvelle Chrafate", [0, 1, 0, 0])]
X, Y, CW, RH = 80, 245, 280, 84
for j, c in enumerate(cols):
    rect(s, X + 380 + j * CW, Y, CW - 10, 80, fill=ccol[j], radius=8)
    text(s, X + 380 + j * CW, Y, CW - 10, 80, c, size=11.5, bold=True, color=WHITE, align="c", anchor="m")
for i, (r, vals) in enumerate(rows):
    y = Y + 100 + i * RH
    rect(s, X, y, 380 + 4 * CW - 10, RH - 10, fill=WHITE if i % 2 == 0 else "EFEAE1")
    text(s, X + 20, y, 360, RH - 10, r, size=14, bold=True, anchor="m")
    for j, v in enumerate(vals):
        cx = X + 380 + j * CW + (CW - 10) / 2; cy = y + (RH - 10) / 2
        oval(s, cx, cy, 20, fill=WHITE, line=INK, lw=3)
        if v == 2:
            oval(s, cx, cy, 20, fill=INK, line=INK, lw=3)
        elif v == 1:
            poly(s, [(cx, cy - 20)] + [(cx + 20 * math.sin(math.pi * t / 12), cy - 20 * math.cos(math.pi * t / 12)) for t in range(13)], fill=INK)
x = 1600
panel_title(s, x, 250, "Clé")
for k, (v, t) in enumerate([(2, "bénéfice fort"), (1, "partiel"), (0, "faible ou nul")]):
    cy = 300 + k * 50
    oval(s, x + 20, cy, 16, fill=INK if v == 2 else WHITE, line=INK, lw=3)
    if v == 1:
        poly(s, [(x + 20, cy - 16)] + [(x + 20 + 16 * math.sin(math.pi * t_ / 12), cy - 16 * math.cos(math.pi * t_ / 12)) for t_ in range(13)], fill=INK)
    text(s, x + 50, cy - 13, 200, 26, t, size=12)
text(s, x, 470, 240, 260, "Évaluation qualitative de l'auteur, à partir des chiffres et observations des pages 3 à 14.", size=10.5, italic=True, color=MUTED)
rect(s, 80, 870, 1760, 80, fill=TOUR, radius=8)
text(s, 110, 870, 1700, 80, "CONSTAT : colonnes rouges pleines, colonnes bleues presque vides. Plus un projet est visible, moins il sert la périphérie.",
     size=13.5, bold=True, color=WHITE, anchor="m")

# ================================================================ SLIDE 16 propositions
s = new_slide(16, "Propositions", "Retourner la vitrine vers les habitants",
              "Cinq interventions localisées, et une règle : juger chaque projet touristique à ce qu'il apporte au quartier le plus éloigné.")
f = tangier_map(s, 80, 230, 1180, 720)
districts(s, f, "split")
for (mxp, myp, t) in [(420, 395, "Beni Makada"), (285, 335, "Mesnana"), (610, 465, "Bir Chifa"), (240, 515, "Gzenaya")]:
    label(s, f, mxp, myp, t, color=LIVE, size=11)
# 1 pedestrian link
poly(s, [f(*p) for p in smooth([(480, 205), (520, 230), (560, 262), (620, 285)], 5)], line=TOUR, lw=8, closed=False)
# 2 medina housing
blob(s, f, 485, 205, 30, 22, None, line=TOUR, lw=4, seed=1)
# 3 transit line
tl = [(240, 500), (285, 320), (420, 380), (560, 330), (600, 450), (770, 320)]
tls = smooth([(240, 500), (300, 400), (420, 380), (560, 330), (680, 320), (770, 320)], 6)
poly(s, [f(*p) for p in tls], line=INK, lw=9, closed=False)
for p in [(240, 500), (300, 400), (420, 380), (560, 330), (680, 320), (770, 320)]:
    oval(s, *f(*p), 10, fill=WHITE, line=INK, lw=4)
# 4 green limit
blob(s, f, 175, 150, 135, 75, None, line=GREEN, lw=5, seed=7, dash="dash")
# 5 equipment
for p in [(470, 420), (330, 355), (660, 480), (300, 540)]:
    rect(s, f(*p)[0] - 11, f(*p)[1] - 11, 22, 22, fill=GOLD, line=WHITE, lw=2)
for n, p in [(1, (600, 250)), (2, (470, 240)), (3, (700, 360)), (4, (120, 200)), (5, (360, 450))]:
    badge(s, *f(*p), str(n), fill=INK, r=20, size=13)
north(s, 1210, 860)
note(s, 80, 958, 1180, "Schéma de propositions de l'auteur, sans échelle.")
x = 1310
props = [("Reconnecter", "Passage piéton sûr et continu entre médina, port et corniche, en apaisant la route littorale.", TOUR),
         ("Habiter la médina", "Logement d'abord : restauration des 328 bâtiments en péril, quota de logements, encadrement des locations courtes.", TOUR),
         ("Relier les quartiers", "Une ligne structurante (tram ou BHNS) : Gzenaya, Mesnana, Beni Makada, centre, gare.", INK),
         ("Protéger", "Limite verte ferme autour de Rmilat et du cap Spartel ; rivage public garanti.", GREEN),
         ("Héritage Mondial", "Chaque dirham dépensé pour l'événement couplé à un équipement de quartier (école, santé, parc).", GOLD)]
for k, (t, d, c) in enumerate(props):
    y = 240 + k * 140
    badge(s, x + 20, y + 22, str(k + 1), fill=INK, r=20, size=13)
    rect(s, x + 52, y + 8, 8, 28, fill=c)
    text(s, x + 70, y + 8, 470, 30, t, size=15, bold=True)
    text(s, x + 52, y + 46, 490, 80, d, size=11.5, color=INK, spacing=1.2)

# ================================================================ SLIDE 17 conclusion
s = new_slide(17, "Conclusion", "Une ville à vivre, pas seulement à voir")
text(s, 80, 250, 1760, 150, [[("Tanger a été refaite pour son image, ses visiteurs et ses investisseurs. ", {"bold": True}),
     ("La prochaine décennie, et l'héritage du Mondial 2030, doivent être jugés dans ses quartiers.", {"color": TOUR, "bold": True})]], size=20, spacing=1.25)
for k, (v, d, c) in enumerate([("+40 %", "d'habitants en dix ans (1,07 → 1,49 M), sans tramway ni métro", LIVE),
                                ("36 / 150 000", "habitants comptés vs prévus à Chrafate", LIVE),
                                ("850 vs 98", "M MAD : décor de la médina vs bâtiments menaçant ruine", TOUR),
                                ("167 k / 750 k", "croisiéristes réels vs promis pour 2025", TOUR)]):
    x = 80 + k * 445
    rect(s, x, 420, 415, 200, fill=WHITE, line=RULE, lw=1.5)
    rect(s, x, 420, 415, 8, fill=c)
    text(s, x + 26, 448, 380, 56, v, size=24, bold=True, color=c)
    text(s, x + 26, 520, 370, 90, d, size=11.5, color=INK, spacing=1.2)
text(s, 80, 650, 1760, 60, "« Une ville se juge moins à son front de mer qu'à la vie quotidienne de son quartier le plus éloigné. »", size=16, italic=True, color=INK, align="c")
seg(s, 80, 730, 1840, 730, RULE, 1.5)
panel_title(s, 80, 745, "Sources")
text(s, 80, 775, 1760, 220, [
    "HCP, Recensement général de la population et de l'habitat 2014 et 2024  ·  Observatoire national du tourisme, via Hespress FR (nov. 2025) : nuitées Tanger-Assilah",
    "Finances News Hebdo (2025) et Le360 : croisières au port de Tanger Ville  ·  Medias24 (2024) : stade Ibn Batouta  ·  Bladi (2024) : évaluation FIFA, permis exceptionnels",
    "Ministère de l'Économie et des Finances (2018), Médias24 (2013-2014) : Tanger Métropole  ·  Le360, Finances News, Médias24 (juin 2018) : port, Tanja Marina Bay",
    "Médias24 (2020), Infomédiaire : programme médina 2020-2024  ·  TelQuel (2024) : bâtiments menaçant ruine  ·  Le Desk (2025), Cour des comptes (2024) : Chrafate",
    "Escher et Petermann : touristification des médinas marocaines  ·  Observations de terrain, photographies et dessins de l'auteur"],
    size=9.5, color=MUTED, spacing=1.35)

for sl in prs.slides:
    for st in sl.shapes._spTree.iter(qn("p:style")):
        pass
    for st in list(sl.shapes._spTree.iter(qn("p:style"))):
        st.getparent().remove(st)

out = "/tmp/claude-0/-home-user-Coucoy-ios/1964f313-0f78-55df-be40-f6671f5226fa/scratchpad/deck/Tanger_ville_vitrine.pptx"
prs.save(out)
print("saved", out, len(prs.slides))
