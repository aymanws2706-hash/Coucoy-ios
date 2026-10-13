# -*- coding: utf-8 -*-
"""Assemble deck3.py (v4) from deck2.py blocks + new blocks (réglementation / expérimentation, patrimoine, croquis, coupes)."""
import re

src = open("deck2.py").read()
head, rest = src.split("# ================================================================= 1 COVER", 1)
parts = re.split(r"\n(?=# ================================================================= )", "# ================================================================= 1 COVER" + rest)
B = {}
for p in parts:
    key = p.split("\n", 1)[0].replace("# =================================================================", "").strip()
    B[key] = p
print(list(B))

# ---------------------------------------------------------------- header changes
head = head.replace("TOTAL = 25", "TOTAL = 32")
head = head.replace('text(s, W - 840, H - 34, 800, 20, f"[NOM]', 'text(s, W - 1040, H - 34, 1000, 20, f"[NOM]')
head = head.replace('f"[NOM]  ·  [COURS]  ·  [DATE]        {num:02d} / {TOTAL}"', 'f"I. SEFIANI · A. AZARKAN  ·  ENAT S7 G4  ·  SÉMINAIRE, M. H. BAHOUSS        {num:02d} / {TOTAL}"')
head = head.replace('"TANGER, VILLE-VITRINE  ·  ÉTUDE DE CAS"', '"TANGER, VILLE-VITRINE  ·  RÈGLE ET EXPÉRIMENTATION"')
head = head.replace("""    kx = W - 40
    for v, l in reversed(kpis):""", """    kx = W - 40
    if num % 2 == 0 and sketch is not False:
        f = SK[(num // 2) % len(SK)] if sketch is None else sketch
        im = Image.open("sk/" + f); iw, ih = im.size; sh = 112; sw = sh * iw / ih
        if sw > 150: sw = 150; sh = sw * ih / iw
        s.shapes.add_picture("sk/" + f, px(W - 40 - sw), px(22 + (112 - sh) / 2), px(sw), px(sh))
        kx -= sw + 40
    for v, l in reversed(kpis):""")
head = head.replace("def slide(num, title, sub=None, kpis=(), dark=False):", "def slide(num, title, sub=None, kpis=(), dark=False, sketch=None):")
head = head.replace("_N = [1]", """_N = [1]
SK = ["nc_sk_kasbah.png", "nc_sk_spartel.png", "nc_sk_minaret.png", "nc_sk_cervantes.png", "nc_sk_hafa.png", "nc_sk_standrew.png",
      "nc_sk_medina.png", "nc_sk_port.png", "nc_sk_legation.png", "nc_sk_stade.png"]""")
head = head.replace('    text(s, 40, 36, 1300, 50, title, size=24, font=TF, color=fg, spc=300, caps=True)\n    if sub:\n        text(s, 40, 90, 1250, 50, sub,',
                    '    text(s, 40, 36, 1300, 50, title, size=24, font=TF, color=fg, spc=300, caps=True)\n    if sub:\n        text(s, 40, 90, 1150, 50, sub,')

# ---------------------------------------------------------------- new / replaced blocks
NEW = {}
NEW["COVER"] = '''# ================================================================= 1 COVER
s = prs.slides.add_slide(BL)
pic(s, "s00_cover.jpg", 0, 0, w=W)
rect(s, 0, 0, 760, H, fill="1F2A32")
text(s, 70, 62, 300, 34, "ENAT", size=20, font=TF, bold=True, color=WHITE, spc=700)
seg(s, 72, 104, 150, 104, "D08A5C", 2.5)
text(s, 70, 114, 520, 20, "École Nationale d'Architecture de Tétouan", size=8.5, color="A6A29B")
text(s, 70, 200, 660, 50, "SÉMINAIRE  ·  URBANISATION ENTRE\\nRÉGLEMENTATION ET EXPÉRIMENTATION", size=11, font=TF, color="D08A5C", spc=350, spacing=1.3)
text(s, 70, 280, 680, 220, "TANGER,\\nVILLE-VITRINE", size=46, font=TF, color=WHITE, spc=300, spacing=1.0)
text(s, 70, 500, 600, 120, "Quand la règle et l'exception servent le tourisme. Lecture critique de la transformation de la ville, 2007-2030.", size=14, color="D6D2CB", spacing=1.35)
seg(s, 70, 650, 170, 650, "D08A5C", 3)
text(s, 70, 678, 600, 26, "ATELIER S7  ·  GROUPE 4", size=10.5, font=TF, bold=True, color=WHITE, spc=350)
text(s, 70, 716, 600, 70, "Ilaf Sefiani\\nAymane Azarkan", size=14, color="EDEDED", spacing=1.4)
text(s, 70, 800, 600, 26, "Encadrant : M. H. Bahouss", size=12, color="D6D2CB")
text(s, 70, 834, 600, 26, "Année universitaire 2026-2027", size=10, color="A6A29B")
text(s, 70, 940, 620, 80, "Cartes et coupes produites à partir de données réelles : OpenStreetMap / Overture Maps, ESA WorldCover, Copernicus DEM, Sentinel-2, Landsat, HCP.", size=9.5, color="A6A29B", spacing=1.35)
text(s, 1180, 1040, 700, 20, "Image : Sentinel-2 L2A, 19 juillet 2025 (Copernicus / ESA)", size=8, color="D6D2CB", align="r", font=TF, spc=200)

'''

NEW["HERO"] = '''# ================================================================= HERO
_N[0] += 1
s = prs.slides.add_slide(BL)
rect(s, 0, 0, W, H, fill="23303A")
pic(s, "p_hero.jpg", -262, 0, h=1080)
text(s, 70, 40, 1200, 110, "TANGER", size=66, font=TF, bold=True, color=WHITE, spc=900)
text(s, 74, 200, 1200, 40, "Entre deux mers et deux continents, une ville refaite pour être vue.", size=17, color=WHITE)
rect(s, W - 560, H - 46, 540, 30, fill="23303A")
text(s, W - 550, H - 41, 520, 20, "Vue de Tanger depuis le port · Mike McBey, CC BY 2.0, Wikimedia Commons", size=8, color="D6D2CB", align="r")

'''

NEW["PROBLEMATIQUE"] = '''# ================================================================= 2 PROBLEMATIQUE
s = slide(2, "Problématique : la règle, l'exception, la vitrine", "Le séminaire interroge l'urbanisation entre réglementation et expérimentation. À Tanger, cette tension a un bénéficiaire : le tourisme.",
          kpis=[("1992", "loi 12-90 :\\nla règle"), ("2013", "Tanger-Métropole :\\nle projet"), ("2030", "Mondial :\\nl'exception")])
text(s, 40, 160, 1840, 110, [[("« À Tanger, l'expérimentation urbaine (projets, programmes d'exception, dérogations) sert-elle la ville habitée, ou d'abord la ville montrée ? »", {"bold": True})]], size=25, font=TF, color=INK, spacing=1.1)
cards = [(BLUE, "LA RÉGLEMENTATION", "lente, générale, opposable", ["SDAU et plans d'aménagement (loi 12-90)", "Loi littoral 81-12 : 100 m inconstructibles", "Patrimoine classé (loi 22-80)", "Contrôle des infractions (loi 66-12)"]),
         (RED, "L'EXPÉRIMENTATION", "rapide, localisée, dérogatoire", ["Programmes royaux : Tanger-Métropole", "Sociétés dédiées : reconversion du port", "Dérogations d'urbanisme (CRI)", "Grands événements : CAN 2025, Mondial 2030"]),
         (INK, "HYPOTHÈSE", "une ville à deux vitesses", ["L'exception se concentre sur la vitrine : littoral, médina, port, stade", "La règle, tardive, s'applique d'abord à la ville ordinaire", "La croissance réelle se fait en périphérie, sous-équipée"])]
for i, (c, t, st, items) in enumerate(cards):
    x = 40 + i * 625
    rect(s, x, 300, 595, 330, fill="F8F5EF", line=RULE, lw=1)
    rect(s, x, 300, 595, 6, fill=c)
    text(s, x + 28, 326, 540, 30, t, size=17, font=TF, bold=True, color=c, spc=300)
    text(s, x + 28, 362, 540, 24, st, size=10.5, italic=True, color=MUTED)
    for k, it in enumerate(items):
        oval(s, x + 36, 420 + k * 52, 5, fill=c)
        text(s, x + 54, 409 + k * 52, 520, 48, it, size=11, spacing=1.1)
    if i == 0:
        seg(s, x + 597, 465, x + 623, 465, INK, 2, head=True)
ptitle(s, 40, 670, "Démarche")
steps = [("01", "CADRE", "La règle et les projets"), ("02", "TERRITOIRE", "Détroit, croissance, étalement"), ("03", "VILLE", "Occupation, usages, équipements"), ("04", "CAS ET COUPES", "Port, médina, stade, quartiers"), ("05", "PROPOSITIONS", "Un autre plan d'aménagement")]
for i, (n, t, d) in enumerate(steps):
    x = 40 + i * 372
    rect(s, x, 704, 350, 128, fill=WHITE, line=RULE, lw=1)
    text(s, x + 20, 714, 80, 40, n, size=22, font=TF, color=RED, bold=True)
    text(s, x + 20, 764, 320, 24, t, size=12, font=TF, bold=True, spc=300)
    text(s, x + 20, 792, 320, 30, d, size=9.5, color=MUTED)
    if i < 4:
        seg(s, x + 352, 768, x + 370, 768, INK, 1.5, head=True)
text(s, 40, 870, 1840, 120, [[("Données. ", {"bold": True}), ("OpenStreetMap / Overture Maps (2026-09) · ESA WorldCover 2021 · Copernicus DEM GLO-30 · Sentinel-2 (2017, 2025) · Landsat (2004-2021) · HCP, RGPH 2014 et 2024 · textes officiels (SGG, Adala, Bulletin officiel) et presse (2013-2025). ", {}),
     ("Les lieux recensés sont incomplets dans les quartiers populaires : les écarts mesurés sont des ordres de grandeur.", {"color": MUTED})]], size=10, spacing=1.4)

'''

NEW["REGLE"] = '''# ================================================================= REGLE
s = slide(0, "Le cadre réglementaire : ce que dit la règle", "Une chaîne de documents, de l'échelle nationale à la parcelle, et des lois sectorielles qui protègent, en théorie, le littoral et le patrimoine.",
          kpis=[("25 ans", "horizon maximal\\nd'un SDAU"), ("10 ans", "effets d'un PA\\n(utilité publique)"), ("100 m", "bande littorale\\ninconstructible")])
ptitle(s, 40, 160, "De l'échelle nationale à la parcelle : où en est Tanger ?")
levels = [("SNAT", "Schéma national d'aménagement du territoire", "années 2000 ; actualisation lancée en 2019", "9AA8B2"),
          ("SRAT", "Schéma régional Tanger-Tétouan-Al Hoceïma", "adopté le 13 janvier 2021, horizon 2046", "7F93A1"),
          ("SDAU", "Schéma directeur (loi 12-90, art. 4), 25 ans au plus", "nouveau SDAU du Grand Tanger lancé en octobre 2025", "62798A"),
          ("PA", "Plan d'aménagement : zonage, réserves d'équipements", "Mghogha et Souani (janv. 2023), Bni Makada (juin 2023) : premiers PA approuvés depuis 2016", "4A6274"),
          ("PERMIS", "Autorisations de construire et de lotir (loi 25-90)", "Règlement général de construction, décret 2-18-577 (2019)", "3E5A6E")]
for i, (ab, name, status, c) in enumerate(levels):
    y = 196 + i * 112
    wbar = 600 - i * 55
    rect(s, 40 + (600 - wbar) / 2, y, wbar, 92, fill=c)
    text(s, 40 + (600 - wbar) / 2, y + 4, wbar, 40, ab, size=24, font=TF, bold=True, color=WHITE, align="c", spc=300)
    text(s, 40 + (600 - wbar) / 2 + 10, y + 62, wbar - 20, 28, name, size=8.5, color="EDEDED", align="c", spacing=1.05)
    seg(s, 40 + (600 + wbar) / 2 + 6, y + 46, 680, y + 46, RULE, 1, dash="dash")
    text(s, 690, y + 18, 400, 70, status, size=10.5, spacing=1.25, color=INK)
text(s, 40, 772, 1030, 60, "Du plus général au plus précis : chaque niveau doit respecter le précédent. Le PA rend les réserves d'équipements d'utilité publique pendant 10 ans.", size=9.5, color=MUTED, spacing=1.3)
x = 1120
ptitle(s, x, 160, "Les lois sectorielles")
laws = [("1980", "Loi 22-80", "monuments historiques et sites : classement, servitudes autour des monuments"),
        ("1992", "Lois 12-90 et 25-90", "urbanisme (SDAU, PA) ; lotissements et groupes d'habitations"),
        ("1995", "Agence urbaine de Tanger", "instruction des documents et des autorisations (décret 2-94-334)"),
        ("2015", "Loi 81-12 sur le littoral", "100 m inconstructibles depuis le rivage (art. 15) ; Plan national du littoral en 2022"),
        ("2016", "Loi 66-12", "contrôle et répression des infractions d'urbanisme et de construction"),
        ("2025", "Loi 22-24 (CRI)", "les dérogations d'urbanisme restent possibles pour l'industrie et l'hôtellerie")]
for i, (yv, t, d) in enumerate(laws):
    y = 196 + i * 100
    rect(s, x, y, 92, 40, fill=RED if yv in ("2015", "2025") else INK)
    text(s, x, y + 2, 92, 34, yv, size=16, font=TF, bold=True, color=WHITE, align="c")
    text(s, x + 112, y - 2, 650, 26, t, size=12, bold=True)
    text(s, x + 112, y + 26, 650, 60, d, size=10, color=MUTED, spacing=1.25)
rect(s, 40, 850, 1840, 150, fill="F8F5EF", line=RULE, lw=1)
rect(s, 40, 850, 8, 150, fill=RED)
text(s, 76, 872, 1780, 120, [[("Lecture. ", {"bold": True, "color": RED}), ("Sur le papier, la règle protège exactement ce que le tourisme convoite : le rivage (81-12), le patrimoine (22-80), les réserves d'équipements (PA). "
     "Mais, selon l'Agence urbaine, aucun nouveau plan d'aménagement n'a été approuvé à Tanger entre 2016 et 2023, au moment même où se réalisaient la corniche, la marina et le stade. "
     "Et la seule dérogation que la réforme de 2025 conserve, à côté de l'industrie, est hôtelière.", {})]], size=12, spacing=1.4)

'''

NEW["EXPERIMENTATION"] = '''# ================================================================= EXPERIMENTATION
s = slide(0, "L'expérimentation : gouverner par projets", "Zones franches, sociétés d'aménagement, programmes royaux, grands événements : les outils d'exception ont avancé plus vite que les plans.",
          kpis=[("7,6 Md", "MAD, Tanger-Métropole\\n2013-2017"), ("850 M", "MAD, médina\\n2020-2024"), ("75 500", "places, grand\\nstade 2025")])
X0, X1, Y0 = 150, 1860, 1990
def xy(yr): return X0 + (yr - Y0) / 40 * (X1 - X0)
yP, yR = 430, 690
rect(s, xy(2016), yP + 20, xy(2023) - xy(2016), yR - yP - 40, fill="F1E3D8")
text(s, xy(2016), yP + 30, xy(2023) - xy(2016), 60, "2016-2023\\naucun nouveau PA approuvé", size=10, bold=True, color=RED, align="c", spacing=1.15)
text(s, xy(2016), yP + 76, xy(2023) - xy(2016), 60, "pendant ce temps : marina, LGV, médina, stade", size=9, color=RED, align="c", italic=True)
for yr in range(1990, 2031, 5):
    seg(s, xy(yr), yP - 4, xy(yr), yR + 4, "E2DCD1", 1)
    text(s, xy(yr) - 40, (yP + yR) / 2 - 12, 80, 24, str(yr), size=11, font=TF, bold=True, color=MUTED, align="c")
seg(s, X0, yP, X1, yP, RED, 3); seg(s, X0, yR, X1, yR, BLUE, 3)
text(s, 30, yP - 16, 115, 40, "PROJETS", size=9.5, font=TF, bold=True, color=RED, spc=150, spacing=1.1)
text(s, 30, yR - 16, 115, 40, "RÈGLES", size=9.5, font=TF, bold=True, color=BLUE, spc=150, spacing=1.1)
P = [(1999, "Tanger Free Zone", "zone franche, 350 ha"), (2003, "Circulaire 3020", "dérogations via les CRI"), (2007, "Tanger Med", "1er terminal"), (2010, "SAPT", "reconversion du port"),
     (2012, "Renault", "usine de Melloussa"), (2013, "Tanger-Métropole", "7,6 Md MAD"), (2018, "Marina · LGV", "Tanja Bay, Al Boraq"), (2020, "Médina", "850 M MAD"), (2025, "Grand stade", "75 500 places"), (2030, "Mondial", "Coupe du monde")]
R = [(1992, "Lois 12-90, 25-90", "urbanisme, lotissements"), (1995, "Agence urbaine", "de Tanger"), (2015, "Loi 81-12", "littoral, 100 m"), (2016, "Loi 66-12", "infractions"),
     (2019, "Règlement", "général de construction"), (2021, "SRAT", "région TTA, 2021-2046"), (2023, "PA 2023", "Mghogha, Souani, Bni Makada"), (2025, "Loi 22-24, SDAU", "dérogations ; nouveau SDAU")]
for lane, items, y, c, up in ((0, P, yP, RED, True), (1, R, yR, BLUE, False)):
    LV = {1999: 0, 2003: 1, 2007: 0, 2010: 2, 2012: 1, 2013: 0, 2018: 2, 2020: 1, 2025: 0, 2030: 2} if up else {1992: 0, 1995: 1, 2015: 0, 2016: 1, 2019: 2, 2021: 0, 2023: 1, 2025: 2}
    for k, (yr, t, d) in enumerate(items):
        xx = xy(yr); lvl = LV[yr]
        oval(s, xx, y, 8, fill=c, line=WHITE, lw=2)
        ty = (y - 66 - lvl * 60) if up else (y + 18 + lvl * 60)
        seg(s, xx, y + (-10 if up else 10), xx, ty + (50 if up else 0), c, 0.8)
        bx = min(xx - 100, X1 + 20 - 200)
        text(s, bx, ty, 200, 26, t, size=10, bold=True, align="c", color=c)
        text(s, bx, ty + 23, 200, 26, d, size=8.5, color=MUTED, align="c")
cards = [("VITESSE", "Un projet d'exception passe du lancement à l'inauguration en 2 à 5 ans ; un plan d'aménagement attend 7 ans son successeur."),
         ("GÉOGRAPHIE", "L'exception se concentre sur le littoral, la médina, le port et le stade : les lieux que l'on montre."),
         ("INSTRUMENT", "La dérogation, pensée comme exception, devient un mode de gestion : la réforme de 2025 la garde pour l'hôtellerie.")]
for i, (t, d) in enumerate(cards):
    x = 40 + i * 625
    rect(s, x, 908, 595, 100, fill="F8F5EF", line=RULE, lw=1); rect(s, x, 908, 6, 100, fill=RED)
    text(s, x + 26, 918, 540, 26, t, size=12, font=TF, bold=True, color=RED, spc=300)
    text(s, x + 26, 946, 550, 60, d, size=10, spacing=1.25)

'''

NEW["DEUXVITESSES"] = '''# ================================================================= DEUXVITESSES
s = slide(0, "Une règle à deux vitesses", "Mêmes lois, deux traitements : la vitrine reçoit l'exception et l'investissement ; la ville vécue reçoit la règle, tardive et répressive.",
          kpis=[("7,6 Md", "MAD pour\\nla vitrine (2013)"), ("0,17 m²", "de parc par habitant\\nà Beni Makada")])
cols = [(RED, "LA VILLE MONTRÉE", "littoral, médina, port, stade"), (BLUE, "LA VILLE VÉCUE", "Beni Makada, Mghogha, périphéries")]
rows = [("Outils", "Programmes royaux, sociétés dédiées (SAPT), conventions de financement", "Plan d'aménagement, contrôle des infractions (loi 66-12), démolitions"),
        ("Calendrier", "2 à 5 ans du lancement à l'inauguration", "PA de Bni Makada homologué en 2023, après des décennies de croissance"),
        ("Rapport à la règle", "Projets réalisés avant les plans ; dérogations possibles pour l'hôtellerie", "Règle appliquée après coup : régularisations, amendes, démolitions"),
        ("Argent public", "Milliards de MAD : corniche, port, médina, stade", "Équipements en attente : écoles, santé, parcs, transports"),
        ("Contrôle", "Visibilité nationale et internationale", "Cour des comptes (2014) : conformité des constructions non contrôlée"),
        ("Résultat", "Espaces publics soignés, foncier valorisé", "R+2 à R+5, rues de 4 à 8 m, 31 % du bâti à plus de 300 m d'un bus")]
for j, (c, t, st) in enumerate(cols):
    x = 400 + j * 750
    rect(s, x, 156, 730, 96, fill=c)
    text(s, x + 26, 164, 680, 34, t, size=20, font=TF, bold=True, color=WHITE, spc=300)
    text(s, x + 26, 214, 680, 24, st, size=11, color="EDEDED")
for i, (lab, a, b) in enumerate(rows):
    y = 262 + i * 104
    seg(s, 40, y, 1880, y, RULE, 1)
    text(s, 40, y + 18, 340, 60, lab.upper(), size=12, font=TF, bold=True, spc=250)
    text(s, 426, y + 16, 680, 80, a, size=12, spacing=1.3)
    text(s, 1176, y + 16, 680, 80, b, size=12, spacing=1.3)
seg(s, 40, 262 + 6 * 104, 1880, 262 + 6 * 104, RULE, 1)
text(s, 40, 920, 1840, 70, "La question n'est pas « règle ou expérimentation », mais : qui bénéficie de l'expérimentation, et qui subit la règle ?", size=20, font=TF, italic=True, color=INK, align="c")

'''

NEW["PHOTOS"] = '''# ================================================================= PHOTOS
s = slide(0, "Deux visages de Tanger", None, kpis=[("9", "photographies")])
photo(s, "p_pano", 40, 140, w=1840)
y0 = 140 + 1840 * 345 / 4000 + 18
ptitle(s, 40, y0, "La ville montrée", RED)
ptitle(s, 1240, y0, "La ville vécue", BLUE)
yy = y0 + 30
x = 40
for key, cap, cr in [("p_kasbah", "Place de la Kasbah", "Herbert wie"), ("p_port", "Gare maritime", "Jobt1962"), ("p_stade", "Grand stade, 2025", "CC0")]:
    ww, hh = photo(s, key, x, yy, h=245, cap=cap, credit=cr)
    x += ww + 18
x = 40; yy2 = yy + 245 + 46
for key, cap, cr in [("p_spartel", "Cap Spartel", "logopop"), ("p_baie", "La baie", "Herbert wie"), ("p_socco", "Grand Socco", "Shbbkr")]:
    ww, hh = photo(s, key, x, yy2, h=245, cap=cap, credit=cr)
    x += ww + 18
photo(s, "p_benimakada", 1240, yy, w=640, cap="Beni Makada", credit="Wikimedia Commons")
photo(s, "p_medina", 1240, yy + 360 + 46, w=330, cap="Ruelle de la médina", credit="Chris Yunker")
text(s, 1600, yy + 420, 280, 160, "Des quartiers où vivent 567 000 personnes, presque aucune image libre.", size=13, font=TF, color=BLUE, spacing=1.2)

'''

NEW["PATRIMOINE"] = '''# ================================================================= PATRIMOINE
s = slide(0, "Un patrimoine mis en vitrine", "Kasbah, remparts, théâtres, églises, phare : le patrimoine de Tanger porte l'image touristique. Sa protection reste sélective.",
          kpis=[("16", "sites classés\\nen 2015"), ("328", "bâtiments menaçant\\nruine en médina (2024)")])
row1 = [("p_kasbahmusee", "Musée de la Kasbah (Dar el Makhzen)", "Yamen, CC BY-SA 4.0"), ("p_babkasbah", "Bab el Kasbah", "David Jones, CC BY 2.0"),
        ("p_cervantes", "Gran Teatro Cervantes (1913)", "Diego Delso, CC BY-SA 4.0"), ("p_muralla", "Remparts et bastion sur le port", "Diego Delso, CC BY-SA 4.0"),
        ("p_standrew", "Église Saint-André (1894)", "Colin Hepburn, CC BY 2.0")]
row2 = [("p_phare", "Phare du cap Spartel (1864)", "Diego Delso, CC BY-SA 4.0"), ("p_hercule", "Grottes d'Hercule", "Diego Delso, CC BY-SA 4.0"),
        ("p_hafa", "Café Hafa (1921)", "Soukaina Amez, CC BY-SA 4.0"), ("p_sidibouabib", "Mosquée Sidi Bou Abib, Grand Socco", "Chris Yunker, CC BY-SA 2.0")]
for row, y, h in ((row1, 150, 285), (row2, 486, 285)):
    x = 40
    for key, cap, cr in row:
        ww, hh = photo(s, key, x, y, h=h, cap=cap, credit=cr)
        x += ww + 16
rect(s, 40, 838, 1840, 160, fill="F8F5EF", line=RULE, lw=1)
rect(s, 40, 838, 8, 160, fill=RED)
text(s, 76, 858, 1780, 130, [[("Lecture. ", {"bold": True, "color": RED}), ("Ce patrimoine est la matière première de la ville-vitrine : il figure sur chaque affiche et dans chaque programme. "
     "La loi 22-80 permet de le protéger, mais le classement reste ponctuel. Le théâtre Cervantes, fermé pendant des décennies, ne retrouve un projet qu'avec l'enjeu touristique ; "
     "dans la médina habitée, 328 bâtiments menaçant ruine attendent encore, quand les parcours de visite sont déjà restaurés.", {})]], size=12, spacing=1.4)

'''

NEW["CARNET"] = '''# ================================================================= CARNET
s = slide(0, "Carnet de croquis : Tanger dessinée", "Croquis à l'encre et au lavis des lieux qui fabriquent l'image de la ville. Ils reviennent, une page sur deux, dans la suite du dossier.",
          kpis=[("10", "lieux dessinés")], sketch=False)
SKC = ["sk_kasbah.png", "sk_medina.png", "sk_minaret.png", "sk_legation.png", "sk_cervantes.png", "sk_standrew.png", "sk_port.png", "sk_hafa.png", "sk_spartel.png", "sk_stade.png"]
for i, f in enumerate(SKC):
    cx = 40 + (i % 5) * 372; cy = 160 + (i // 5) * 420
    im = Image.open("sk/" + f); iw, ih = im.size
    sc = min(350 / iw, 400 / ih); w_, h_ = iw * sc, ih * sc
    s.shapes.add_picture("sk/" + f, px(cx + (350 - w_) / 2), px(cy + 400 - h_), px(w_), px(h_))

'''

NEW["C1"] = '''# ================================================================= COUPE C1
s = slide(0, "Coupe C1 · Le front de mer de la corniche", "Coupe à l'échelle réelle, sans exagération verticale, de la baie au boulevard Mohammed V (570 m). Sol : MNT Copernicus ; emprises, rues et étages : OSM ; usages des étages : estimation.",
          kpis=[("171 m", "de plage\\npublique"), ("R+8 / R+9", "front bâti\\n(OSM)"), ("env. 85 m", "du haut de plage\\nau premier immeuble")])
w_, h_ = pic(s, "k1_full.jpg", 40, 150, w=1840)
y = 150 + h_ + 22
ptitle(s, 40, y, "1 · Plage, promenade et avenue Mohammed VI", RED)
wa, ha = pic(s, "k1_zoomA.jpg", 40, y + 28, w=900)
ptitle(s, 980, y, "2 · Le front bâti en coupe : cafés, appartements, parkings", RED)
wb, hb = pic(s, "k1_zoomB.jpg", 980, y + 28, w=900)
yl = y + 28 + ha + 20
ptitle(s, 40, yl, "Usage des étages")
legend(s, 40, yl + 30, [("box", "DFA98F", "Hôtel, maison d'hôtes"), ("box", "E9C3AE", "Résidence secondaire, location saisonnière"), ("box", "EADCC4", "Logement permanent")], w=440)
legend(s, 480, yl + 30, [("box", "E8CF9C", "Commerce, café, restaurant"), ("box", "D8D4CD", "Stationnement enterré"), ("line", "8D7C66", "Volets clos hors saison")], w=440)
text(s, 40, yl + 124, 900, 200, [[("Lecture. ", {"bold": True, "color": RED}), ("L'espace public du front de mer est généreux : 171 m de sable et 65 m de promenade plantée, réaménagée par Tanger-Métropole. "
     "Le premier rang bâti, R+8 à R+9 sur deux niveaux de parking, est un front d'appartements dont une part n'est habitée qu'en été. "
     "À environ 85 m du haut de plage, il précède la loi littoral de 2015 (100 m inconstructibles), qui ne remet pas en cause l'existant.", {})]], size=10.5, spacing=1.4)

'''

NEW["C2"] = '''# ================================================================= COUPE C2
s = slide(0, "Coupe C2 · Beni Makada, la ville vécue", "Coupe à l'échelle réelle sur 540 m, d'ouest en est. Rues et vide central : OSM et ESA WorldCover ; gabarits R+2 à R+5 et usages : estimation sur vues aériennes.",
          kpis=[("4 à 12 m", "largeur\\ndes rues"), ("R+2 à R+5", "gabarits"), ("44 m", "seul espace\\nnon bâti")])
w_, h_ = pic(s, "k2_full.jpg", 40, 150, w=1840)
y = 150 + h_ + 22
ptitle(s, 40, y, "1 · Rue principale et derbs : commerces en rez-de-chaussée", BLUE)
wa, ha = pic(s, "k2_zoomA.jpg", 40, y + 28, w=900)
ptitle(s, 980, y, "2 · Le terrain non bâti, seul vide du transect", BLUE)
wb, hb = pic(s, "k2_zoomB.jpg", 980, y + 28, w=900)
y2 = y + 28 + max(ha, hb) + 24
text(s, 40, y2, 900, 260, [[("Lecture. ", {"bold": True, "color": BLUE}), ("Un tissu continu de maisons R+2 à R+5, construites par étapes : fers en attente sur les toits, derniers niveaux en brique creuse, encorbellements au-dessus des rues. "
     "Pas un arbre, pas de trottoir dans les derbs, un seul vide non aménagé. Le plan d'aménagement de Bni Makada n'a été homologué qu'en juin 2023 : ici, la règle arrive après la ville.", {})]], size=10.5, spacing=1.4)
x = 980
rows = [("Espace public", "plage 171 m, promenade 65 m", "terrain non bâti de 44 m"), ("Voie principale", "21 m, terre-plein planté", "12 m, sans arbres"), ("Gabarits", "R+8 / R+9, parkings enterrés", "R+2 à R+5, étages en attente"), ("Document", "projet avant le plan", "PA homologué en 2023")]
text(s, x + 200, y2, 300, 20, "C1 CORNICHE", size=9, bold=True, color=RED, font=TF, spc=150)
text(s, x + 560, y2, 300, 20, "C2 BENI MAKADA", size=9, bold=True, color=BLUE, font=TF, spc=150)
for i, (a, b, c) in enumerate(rows):
    yy = y2 + 30 + i * 46
    seg(s, x, yy - 6, 1880, yy - 6, RULE, 1)
    text(s, x, yy, 190, 40, a, size=10, bold=True)
    text(s, x + 200, yy, 340, 40, b, size=10, color=RED)
    text(s, x + 560, yy, 320, 40, c, size=10, color=BLUE)

'''

NEW["C3"] = '''# ================================================================= COUPE C3
s = slide(0, "Coupe C3 · De la Kasbah à la marina", "Coupe à l'échelle réelle sur 1 km : la médina descend vers la mer, puis la falaise, le boulevard du port, l'esplanade et le bassin de plaisance.",
          kpis=[("1 km", "de longueur"), ("74 m", "de dénivelé"), ("env. 50 m", "de boulevard\\nà traverser")])
w_, h_ = pic(s, "k3_full.jpg", 40, 150, w=1840)
y = 150 + h_ + 20
for i, (f, t) in enumerate([("k3_zoomA.jpg", "1 · Médina : maisons et riads convertis"), ("k3_zoomB.jpg", "2 · Remparts, falaise et boulevard"), ("k3_zoomC.jpg", "3 · Esplanade, gare maritime, marina")]):
    x = 40 + i * 620
    ptitle(s, x, y, t, OCHRE if i else RED)
    pic(s, f, x, y + 28, w=600)
y2 = y + 28 + 600 * 672 / 1920 + 24
pic(s, "m16_coupes_loc.jpg", 1600, y2 - 10, h=1000 - y2 + 10)
legend(s, 40, y2, [("box", "DFA98F", "Maison d'hôtes, riad converti"), ("box", "EADCC4", "Logement"), ("box", "E8CF9C", "Commerce"), ("box", "C8D3D9", "Équipement")], w=360)
text(s, 420, y2, 1150, 260, [[("Lecture. ", {"bold": True, "color": RED}), ("La médina garde sa trame de derbs de 2 à 4 m, mais une partie des maisons devient maisons d'hôtes. "
     "Au pied des remparts, il faut franchir un boulevard d'environ 50 m avant d'atteindre l'esplanade du port, occupée par les cars de tourisme, la gare maritime et la marina. "
     "La reconversion a soigné le front d'eau, pas la couture entre la vieille ville et la mer.", {})], "",
     [("Méthode. ", {"bold": True}), ("Sol : enveloppe basse du MNT Copernicus (30 m) ; rues, bâti et rivage : OSM, Overture, WorldCover ; étages et usages : estimation. Échelle 1:1.", {"color": MUTED})]], size=10.5, spacing=1.4)

'''

# ---------------------------------------------------------------- modifications of kept blocks
lit = B["9 LITTORAL"]
lit = lit.replace("La majorité des habitants vit à plus de 3 km de la mer.", "La majorité des habitants vit à plus de 3 km de la mer. La loi 81-12 (2015) gèle désormais 100 m de rivage, mais arrive après la construction du front.")
B["9 LITTORAL"] = lit
pl = B["PLAN"].replace('"Un autre plan d\'aménagement pour Tanger", "Proposition de zonage dans la logique d\'un plan d\'aménagement (PA) : densifier autour d\'un transport, protéger, équiper."',
                       '"Un autre PA : la règle au service de la ville vécue", "Proposition de zonage dans la logique d\'un PA (loi 12-90) : densifier autour d\'un transport, protéger le rivage (loi 81-12), réserver les équipements."')
B["PLAN"] = pl
pr = B["17 PROPOSITIONS"]
pr = pr.replace('"Propositions : retourner la vitrine", "Cinq interventions localisées, et une règle : juger chaque projet à ce qu\'il apporte au quartier le plus éloigné."',
                '"Propositions : retourner la vitrine", "Cinq interventions localisées, et une règle du jeu pour l\'expérimentation : chaque exception doit profiter au quartier le plus éloigné."')
pr = pr.replace('("Protéger la lisière", "Limite verte ferme autour de Rmilat, Perdicaris et cap Spartel ; rivage public garanti.", GREEN)',
                '("Protéger la lisière et le rivage", "Bande de 100 m de la loi 81-12 sans dérogation ; limite verte ferme autour de Rmilat, Perdicaris et cap Spartel.", GREEN)')
pr = pr.replace("    text(s, x + 40, yy + 38, 510, 100, d, size=10.5, spacing=1.35)", "    text(s, x + 40, yy + 36, 510, 90, d, size=10, spacing=1.3)")
pr = pr.replace("    yy = 160 + i * 150", "    yy = 150 + i * 122")
pr = pr.replace("y = 920\nlegend(s, x, y,", """rect(s, x, 796, 550, 112, fill="F8F5EF", line=RULE, lw=1); rect(s, x, 796, 6, 112, fill=RED)
text(s, x + 22, 806, 520, 100, [[("Règle du jeu. ", {"bold": True, "color": RED}), ("Toute dérogation (loi 22-24) ou tout projet d'exception est conditionné à une contrepartie équivalente en périphérie, inscrite au PA et suivie publiquement.", {})]], size=10, spacing=1.3)
y = 925
legend(s, x, y,""")
B["17 PROPOSITIONS"] = pr
co = B["18 CONCLUSION"]
co = co.replace('[[("Tanger a été refaite pour être vue. ", {"bold": True}), ("Les données le montrent : la vitrine se mesure en mètres depuis la mer, la ville vécue en kilomètres.", {"color": RED, "bold": True})]]',
                '[[("Tanger a été refaite pour être vue. ", {"bold": True}), ("L\'expérimentation a servi la vitrine, la règle a encadré, tardivement, la ville vécue.", {"color": RED, "bold": True})]]')
co = co.replace('"Méthode : reprojection UTM 30N', '"Textes : SGG et portail Adala (lois 12-90, 25-90, 22-80, 81-12, 66-12 ; décret 2-18-577) ; BO n° 7161 et 7209 (PA de 2023) ; Medias24, Le Desk, TelQuel, Le360, Hespress, Challenge (2013-2025).",\n       "Méthode : reprojection UTM 30N')
co = co.replace("Tous les calculs et cartes sont de l'auteur.", "Calculs, cartes, coupes et croquis : I. Sefiani et A. Azarkan.")
co = co.replace("prs.save(\"Tanger_ville_vitrine_v3.pptx\")", "prs.save(\"Tanger_ville_vitrine_v4.pptx\")")
co = co.replace('text(s, 40, 636, 1840, 200, src, size=9, color=MUTED, spacing=1.45)', 'text(s, 40, 632, 1840, 200, src, size=8.5, color=MUTED, spacing=1.4)')
B["18 CONCLUSION"] = co

order = [NEW["COVER"], NEW["HERO"], NEW["PROBLEMATIQUE"], NEW["REGLE"], NEW["EXPERIMENTATION"], NEW["DEUXVITESSES"], NEW["PHOTOS"], NEW["PATRIMOINE"], NEW["CARNET"],
         B["3 TERRITOIRE (dark)"], B["4 ARRONDISSEMENTS"], B["ETALEMENT"], B["5 OCCUPATION"], B["6 SATELLITE 2017 / 2025"], B["COUCHES"], B["7 DEUX VILLES"], B["8 INDICATEURS"],
         B["9 LITTORAL"], B["CYCLE"], B["10 PORT"], NEW["C1"], NEW["C2"], NEW["C3"], B["12 MEDINA"], B["13 MONDIAL"], B["14 INDUSTRIE / CHRAFATE"], B["15 MOBILITE"],
         B["16 SYNTHESE"], B["PLAN"], B["TOD"], B["17 PROPOSITIONS"], B["18 CONCLUSION"]]
open("deck3.py", "w").write(head + "\n".join(order))
print("slides", len(order))
