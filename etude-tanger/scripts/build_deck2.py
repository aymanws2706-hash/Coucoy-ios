# -*- coding: utf-8 -*-
"""Assemble deck2.py from deck.py: harmonised palette, new boards, photo frames."""
import re
src = open("deck.py").read()
head, rest = src.split("# ================================================================= 1 COVER", 1)
blocks = {}
parts = re.split(r"(# ================================================================= \d+ [^\n]*\n)", "# ================================================================= 1 COVER" + rest)
cur = None
for p in parts:
    m = re.match(r"# ================================================================= (\d+) ", p)
    if m:
        cur = int(m.group(1)); blocks[cur] = p
    elif cur is not None:
        blocks[cur] += p
tail_idx = blocks[18].index("for sl in prs.slides:")
tail = blocks[18][tail_idx:]
blocks[18] = blocks[18][:tail_idx]

# ---------------------------------------------------------------- palette & helpers
head = head.replace('BG = "E9E7E2"; INK = "2B2B2B"; MUTED = "77736C"; RULE = "C9C4BA"; WHITE = "FFFFFF"',
                    'BG = "EFEBE3"; INK = "23303A"; MUTED = "7B746B"; RULE = "CFC6B8"; WHITE = "FFFFFF"')
head = head.replace('RED = "C8462B"; BLUE = "1F3A5F"; GREEN = "5E7F4F"; GOLD = "D9A441"; GREY = "B9B1A5"; SALMON = "DFA283"',
                    'RED = "B5563C"; BLUE = "3E5A6E"; GREEN = "4F6B4A"; GOLD = "C9965A"; GREY = "C2B8AA"; SALMON = "D7A88A"; SAGE = "7D9873"; OCHRE = "C9965A"; P04 = "3B4650"; P14 = "B5563C"; P21 = "E0A86A"')
head = head.replace("TOTAL = 18", "TOTAL = 25")
head = head.replace("w_ = max(120, 15 * len(v) + 20, 6.2 * len(l))", "w_ = max(120, 21 * len(v) + 10, 6.4 * max(len(t) for t in l.split(chr(10))))")
head = head.replace('bg = "232526" if dark else BG', 'bg = "23303A" if dark else BG')
head = head.replace('seg(s, 40, H - 44, W - 40, H - 44, "4A4C4D" if dark else RULE, 1)', 'seg(s, 40, H - 44, W - 40, H - 44, "45535D" if dark else RULE, 1)')
head = head.replace("def slide(num, title, sub=None, kpis=(), dark=False):\n    s = prs.slides.add_slide(BL)",
                    "_N = [1]\ndef slide(num, title, sub=None, kpis=(), dark=False):\n    _N[0] += 1; num = _N[0]\n    s = prs.slides.add_slide(BL)")
head += '''

def photo(s, key, x, y, w=None, h=None, credit=None, cap=None, dark=False):
    ww, hh = pic(s, key + ".jpg", x, y, w=w, h=h)
    if cap or credit:
        text(s, x, y + hh + 6, ww, 34, [[((cap + "  ") if cap else "", {"bold": True, "color": "E0E0E0" if dark else INK}), (credit or "", {"italic": True})]], size=8, color="A6A29B" if dark else MUTED, spacing=1.1)
    return ww, hh

'''
REPL = [("E07A3F", "D08A5C"), ('"1B1D1E"', '"1F2A32"'), ('"A3B78F"', '"A9BB97"'), ('"A9C3CC"', '"A8C0C6"'), ('"D9824F"', '"C9965A"'), ('"B7553A"', '"B5563C"'),
        ('"2F5E2A"', '"4F6B4A"'), ('"B4C6A2"', '"BAC8A8"'), ('"E9B6A8"', '"E6C3B2"'), ('"E4A08A"', '"E0A86A"'), ('"8C8478"', '"8E8578"'), ('"C9D5E3"', '"CFD9DE"')]
for k in blocks:
    for a, b in REPL:
        blocks[k] = blocks[k].replace(a, b)
for a, b in REPL:
    head = head.replace(a, b)

# ---------------------------------------------------------------- photo board (after cover)
PHOTOS = '''
# ================================================================= PHOTOS
s = slide(0, "Deux visages de Tanger", "La ville montrée sur les cartes postales, et la ville où vivent la plupart des habitants.",
          kpis=[("9", "photographies\\n(Wikimedia Commons)")])
photo(s, "p_pano", 40, 150, w=1840)
y0 = 150 + 1840 * 345 / 4000 + 18
ptitle(s, 40, y0, "La ville montrée", RED)
ptitle(s, 1240, y0, "La ville vécue", BLUE)
yy = y0 + 30
x = 40
for key, cap, cr in [("p_kasbah", "Place de la Kasbah", "Herbert wie, CC BY-SA"), ("p_port", "Gare maritime, port de Tanger Ville", "Jobt1962, CC BY-SA 4.0"), ("p_stade", "Grand stade, 2025", "domaine public (CC0)")]:
    ww, hh = photo(s, key, x, yy, h=235, cap=cap, credit=cr)
    x += ww + 18
x = 40; yy2 = yy + 235 + 52
for key, cap, cr in [("p_spartel", "Cap Spartel", "logopop, CC BY-SA 3.0"), ("p_baie", "La baie depuis la ville", "Herbert wie, CC BY-SA"), ("p_socco", "Grand Socco", "Shbbkr, CC BY-SA 4.0")]:
    ww, hh = photo(s, key, x, yy2, h=235, cap=cap, credit=cr)
    x += ww + 18
photo(s, "p_benimakada", 1240, yy, w=640, cap="Avenue Moulay Ali Charif, Beni Makada", credit="Wikimedia Commons")
photo(s, "p_medina", 1240, yy + 360 + 52, w=330, cap="Ruelle de la médina", credit="Chris Yunker, CC BY-SA 2.0")
text(s, 1590, yy + 412, 290, 240, [[("Lecture. ", {"bold": True, "color": RED}), ("Les images qui circulent montrent la Kasbah, le port, le cap et le stade. Celles des quartiers où vivent 567 000 personnes sont rares, y compris dans les bases d'images libres.", {})]], size=10, spacing=1.35)
text(s, 40, 1000, 1500, 20, "Photographies : Wikimedia Commons (auteurs et licences indiqués). Panorama : Börste, CC BY-SA 3.0.", size=8, italic=True, color=MUTED)

'''

# ---------------------------------------------------------------- sprawl
SPRAWL = '''
# ================================================================= ETALEMENT
s = slide(0, "Vingt ans d'étalement : 2004 → 2021", "Surfaces bâties estimées à partir des images Landsat 2004, 2014 et 2021, classées sur la base d'ESA WorldCover.",
          kpis=[("28,7 → 50,8", "km² bâtis dans\\nla commune"), ("+77 %", "en 17 ans"), ("2 → 27 km²", "bâtis hors commune\\n(zone d'étude)")])
pic(s, "m13_etalement.jpg", 40, 150, w=1250)
x = 1330
for i, yr in enumerate(["2004", "2014", "2021"]):
    pic(s, f"m13_{yr}.jpg", x + i * 186, 150, w=176)
ptitle(s, x, 290, "Légende")
y = legend(s, x, 320, [("box", P04, "Bâti avant 2004"), ("box", P14, "Bâti entre 2004 et 2014"), ("box", P21, "Bâti entre 2014 et 2021"), ("line", INK, "Commune, voies express")])
ptitle(s, x, y + 20, "Surface bâtie par arrondissement (km²)")
data = [("Tanger-Médina", 7.65, 12.3, 20.1), ("Beni Makada", 7.99, 10.97, 13.4), ("Charf-Mghogha", 8.52, 9.77, 12.51), ("Charf-Souani", 4.53, 4.56, 4.75)]
for i, (a, v1, v2, v3) in enumerate(data):
    yy = y + 52 + i * 38
    text(s, x, yy, 130, 22, a, size=9.5, bold=(a == "Tanger-Médina"))
    sc = 380 / 20.1
    rect(s, x + 132, yy + 3, v1 * sc, 16, fill=P04); rect(s, x + 132 + v1 * sc, yy + 3, (v2 - v1) * sc, 16, fill=P14); rect(s, x + 132 + v2 * sc, yy + 3, (v3 - v2) * sc, 16, fill=P21)
    text(s, x + 138 + v3 * sc, yy, 60, 22, f"{v3:.1f}".replace(".", ","), size=9.5, bold=True)
text(s, x, y + 220, 550, 330, [[("Lecture. ", {"bold": True, "color": RED}), ("La tache urbaine a presque doublé en vingt ans. La croissance ne se fait pas dans le centre, déjà saturé, mais par lotissements successifs au sud et à l'ouest (Boukhalef, Gzenaya, Mghogha), le long des voies express, loin de la mer et des projets d'image. "
     "Hors des limites communales, les surfaces bâties de la zone d'étude passent d'environ 2 à 27 km² : zones industrielles, lotissements et équipements routiers.", {})]], size=10, spacing=1.38)
text(s, 40, 975, 1250, 40, "Méthode : forêt aléatoire entraînée sur Landsat 8 (2021) et ESA WorldCover ; précision 96 % sur les pixels de référence 2021. Les surfaces 2004 et 2014 sont des estimations (résolution 30 m).", size=8.5, italic=True, color=MUTED)

'''

LAYERS = '''
# ================================================================= COUCHES
s = slide(0, "Lire le territoire par couches", "Cinq couches de données réelles superposées : relief, trame verte et bleue, bâti dans le temps, réseaux, usages.",
          kpis=[("5", "couches"), ("150 km²", "d'emprise")])
pic(s, "m14_couches.jpg", 40, 140, h=880)
x = 1150
text(s, x, 170, 720, 700, [[("Ce que montre la superposition", {"bold": True, "size": 14, "font": TF})], "",
     [("1. Le relief commande la ville. ", {"bold": True}), ("La vieille ville tient la falaise au-dessus du détroit ; la croissance a contourné les collines boisées du nord-ouest pour s'étaler sur les plateaux du sud.", {})], "",
     [("2. La trame verte est au nord, la population au sud. ", {"bold": True}), ("Rmilat, Perdicaris et Malabata concentrent les arbres ; la tache bâtie récente n'en contient presque aucun.", {})], "",
     [("3. Le bâti récent suit les réseaux, pas les équipements. ", {"bold": True}), ("Les extensions 2004-2021 se collent aux voies express et à la voie ferrée.", {})], "",
     [("4. Les usages se séparent. ", {"bold": True}), ("Les hébergements (rouge) se massent sur la côte ; écoles et santé (bleu) restent concentrées dans le centre ancien, loin des nouveaux quartiers.", {})]],
     size=11, spacing=1.38)

'''

CYCLE = '''
# ================================================================= CYCLE
s = slide(0, "La mécanique de la ville-vitrine", "Comment un projet d'image produit, étape par étape, de la rente pour quelques-uns et de l'éviction pour les autres.",
          kpis=[("6", "étapes"), ("1", "boucle qui\\nse renforce")])
pic(s, "s_cycle.jpg", 20, 130, h=900)
x = 1150
for (yy, col, head_, items) in [(170, RED, "QUI GAGNE", ["Promoteurs et investisseurs immobiliers", "Hôtels, opérateurs de croisière", "Propriétaires du front de mer et de la médina", "L'image nationale et internationale"]),
                               (560, BLUE, "QUI PAIE", ["Locataires de la médina et du centre", "Pêcheurs et usagers de l'ancien port", "Quartiers périphériques sans équipements", "Le budget public (milliards de MAD engagés)"])]:
    rect(s, x, yy, 730, 350, fill="F8F5EF", line=RULE, lw=1)
    rect(s, x, yy, 8, 350, fill=col)
    text(s, x + 34, yy + 26, 660, 30, head_, size=16, font=TF, bold=True, color=col, spc=300)
    for k, t in enumerate(items):
        oval(s, x + 44, yy + 104 + k * 60, 6, fill=col)
        text(s, x + 64, yy + 90 + k * 60, 640, 30, t, size=13)

'''

COUPES = '''
# ================================================================= COUPES C1 C2
s = slide(0, "Coupes : la ville montrée, la ville vécue", "Coupes semi-réalistes à l'échelle : sol réel (MNT Copernicus), emprises et rues réelles (OSM, WorldCover), gabarits estimés.",
          kpis=[("27 m", "Av. Mohammed VI"), ("4-12 m", "rues de\\nBeni Makada"), ("R+7 / R+4", "gabarits")])
ptitle(s, 40, 150, "C1 · Le front de mer : plage, corniche, front hôtelier", RED, w=1300)
pic(s, "c1_corniche.jpg", 40, 178, w=1840)
ptitle(s, 40, 560, "C2 · Beni Makada : le tissu dense de la ville vécue", BLUE, w=1300)
pic(s, "c2_benimakada.jpg", 40, 588, w=1460)
x = 1530
ptitle(s, x, 590, "Comparer")
rows = [("Rue principale", "27 m, terre-plein planté", "8-12 m, sans arbres"), ("Ruelles", "accès direct à la plage", "4-6 m, passages"), ("Espace vert", "promenade, palmiers", "un jardin sur 540 m"), ("Accès à la mer", "immédiat", "à près de 5 km")]
text(s, x + 120, 618, 110, 20, "C1 VITRINE", size=8.5, bold=True, color=RED, font=TF, spc=150)
text(s, x + 240, 618, 110, 20, "C2 VÉCUE", size=8.5, bold=True, color=BLUE, font=TF, spc=150)
for i, (a, b, c) in enumerate(rows):
    yy = 646 + i * 72
    seg(s, x, yy - 6, 1880, yy - 6, RULE, 1)
    text(s, x, yy, 115, 60, a, size=9.5, bold=True)
    text(s, x + 120, yy, 112, 60, b, size=9, color=RED, spacing=1.15)
    text(s, x + 240, yy, 110, 60, c, size=9, color=BLUE, spacing=1.15)

# ================================================================= COUPE C3
s = slide(0, "Coupe C3 : de la Kasbah au port", "Un kilomètre de la Kasbah au bassin : derbs de 2 à 4 m, rempart, boulevard de 46 m, esplanade portuaire.",
          kpis=[("1 km", "de longueur"), ("61 m", "de dénivelé"), ("46 m", "de boulevard\\nà traverser")])
pic(s, "c3_kasbah_port.jpg", 40, 160, w=1840)
pic(s, "m16_coupes_loc.jpg", 40, 540, h=470)
x = 500
text(s, x, 560, 640, 450, [[("Lecture. ", {"bold": True, "color": RED}), ("La médina descend vers la mer par une trame de derbs de 2 à 4 m. Au pied du rempart, le promeneur doit franchir un boulevard de près de 46 m (Avenue Mohammed VI et contre-allées) avant d'atteindre l'esplanade du port. "
     "La reconversion a soigné le front d'eau, pas la couture entre la vieille ville et la mer.", {})], "",
     [("Méthode des coupes. ", {"bold": True}), ("Profil du sol extrait du MNT Copernicus (30 m), rues et emprises bâties relevées sur OpenStreetMap et ESA WorldCover le long du tracé ; hauteurs et façades estimées par type de tissu. Échelle verticale ×1,5.", {"color": MUTED})]],
     size=10.5, spacing=1.4)
ptitle(s, 1200, 560, "Repérage des coupes")
legend(s, 1200, 592, [("line", RED, "C1 · front de mer, corniche"), ("line", BLUE, "C2 · Beni Makada"), ("line", OCHRE, "C3 · Kasbah, médina, port")])

'''

PLAN = '''
# ================================================================= PLAN
s = slide(0, "Un autre plan d'aménagement pour Tanger", "Proposition de zonage dans la logique d'un plan d'aménagement (PA) : densifier autour d'un transport, protéger, équiper.",
          kpis=[("17 km", "de tram / BHNS,\\n8 stations"), ("325 ha", "de réserves pour\\nparcs et équipements"), ("3,1 km²", "de littoral public")])
pic(s, "m15_plan.jpg", 40, 150, w=1250)
x = 1320
ptitle(s, x, 150, "Zonage proposé")
z = [("box", "A9BC97", "N  · forêts protégées : Rmilat, Perdicaris, Malabata"), ("box", "ECE6D3", "A  · zone agricole hors limite d'urbanisation"),
     ("box", "DCCDB9", "U  · tissu existant à requalifier"), ("box", "E2B48F", "UT · densification mixte à 500 m du tram"),
     ("box", "F0D9B8", "AU · extension maîtrisée autour des stations"), ("box", "9EB78E", "LP · littoral public (100 m) rendu aux habitants"),
     ("box", "9DB98F", "Parcs linéaires d'oued (trame bleue)"), ("box", "B9C9A2", "Réserves foncières mobilisées"), ("sq", OCHRE, "Équipements de quartier prioritaires"),
     ("line", "2F3E48", "Ligne de tram / BHNS et stations"), ("dash", INK, "Limite d'urbanisation"), ("dash", RED, "Liaison piétonne médina-port-corniche"),
     ("hatch", RED, "Médina : logement d'abord")]
y = legend(s, x, 182, z, w=570)
text(s, x, y + 16, 560, 200, [[("Principe. ", {"bold": True, "color": RED}), ("L'investissement suit la population, pas l'image : chaque mètre carré ouvert à l'urbanisation est desservi par le tram et accompagné d'équipements ; la forêt et le littoral deviennent des biens communs protégés.", {})]], size=10, spacing=1.35)

# ================================================================= TOD
s = slide(0, "Le quartier de station : un modèle pour la périphérie", "Schéma de principe d'un quartier organisé autour d'une station du tram proposé, appliqué à Beni Makada et Mghogha.",
          kpis=[("500 m", "rayon à pied"), ("5 min", "vers l'école\\net la santé")])
pic(s, "s_tod.jpg", 290, 150, h=860)

'''

# ---------------------------------------------------------------- photo insertions in existing blocks
blocks[10] = blocks[10].replace('''text(s, 40, y, pw, 120, "Chantier en cours''', '''photo(s, "p_port", 40, y + 90, h=250, cap="Gare maritime du port de Tanger Ville", credit="Jobt1962, CC BY-SA 4.0")
text(s, 440, y + 90, 820, 200, [[("Ce que la photo ne montre pas. ", {"bold": True}), ("Les pêcheurs déplacés vers le nouveau port, les dockers et les ateliers de réparation navale qui faisaient vivre le front d'eau.", {})]], size=10.5, spacing=1.4, color=MUTED)
text(s, 40, y, pw, 120, "Chantier en cours''')
blocks[13] = blocks[13].replace('''text(s, x, 380, 550, 600, [[("Lecture. "''', '''photo(s, "p_stade", x, 375, w=550, cap="Le grand stade en 2025", credit="Wikimedia Commons, CC0")
text(s, x, 720, 550, 300, [[("Lecture. "''')
blocks[13] = blocks[13].replace('''"La réponse annoncée : des permis hôteliers exceptionnels, pour tenir une date fixée de l'extérieur. Ce qui peut être livré à temps (stade, hôtels, façades) passe devant ce qui demande du temps : logement, transport, équipements de quartier.", {})], "",
     [("L'héritage du Mondial devra se mesurer dans les quartiers, pas dans les tribunes.", {"bold": True})]], size=10.5, spacing=1.4)''', '''"Ce qui peut être livré à temps (stade, hôtels, façades) passe devant le logement, le transport et les équipements de quartier.", {})]], size=10, spacing=1.35)''')
blocks[9] = blocks[9].replace('''"La majorité des habitants vit à plus de 3 km de la mer et n'y accède que par la route.", {})], "",
     [("Médiane de la distance à la mer : ", {"bold": True}), ("390 m pour un hébergement, 1,8 km pour une école, 4,9 km pour le bâti de Beni Makada.", {})]], size=10.5, spacing=1.4)''', '''"La majorité des habitants vit à plus de 3 km de la mer.", {})]], size=10, spacing=1.35)
photo(s, "p_spartel", x, 690, w=420, cap="Cap Spartel", credit="logopop, CC BY-SA 3.0")''')
# conclusion credits
blocks[18] = blocks[18].replace('''       "Méthode : reprojection UTM 30N''', '''       "Images : Landsat 5 et 8 (USGS, via Google Cloud Public Data), Sentinel-2 (Copernicus). Photographies : Wikimedia Commons, auteurs et licences indiqués sur chaque planche.",
       "Méthode : reprojection UTM 30N''')
blocks[18] = blocks[18].replace("text(s, 40, 636, 1840, 380, src, size=9.5", "text(s, 40, 636, 1840, 200, src, size=9")
blocks[18] += """photo(s, "p_pano", 40, 836, w=1840)
text(s, 40, 1000, 1200, 20, "Panorama de Tanger depuis le port : Börste, Wikimedia Commons, CC BY-SA 3.0", size=8, italic=True, color=MUTED)
"""

order = [blocks[1], PHOTOS, blocks[2], blocks[3], blocks[4], SPRAWL, blocks[5], blocks[6], LAYERS, blocks[7], blocks[8], blocks[9], CYCLE,
         blocks[10], COUPES, blocks[12], blocks[13], blocks[14], blocks[15], blocks[16], PLAN, blocks[17], blocks[18]]
out = head + "\n".join(order) + tail.replace("Tanger_ville_vitrine_planches.pptx", "Tanger_ville_vitrine_v3.pptx")
open("deck2.py", "w").write(out)
print("slides:", len(order))
