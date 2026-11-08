#!/usr/bin/env python3
"""Génère une série de fonds d'écran kitsch façon MS Paint pour meteo-wallpaper.

Usage : python3 gen_wallpapers.py [dossier_sortie] [--largeur 1920 --hauteur 1080]

Produit 6 météos x jour/nuit + defaut.png. Le décor (montagnes, lac,
maison, arbre) est identique dans toutes les variantes.
Dépendance : Pillow (pip install --user pillow).
"""
import argparse
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

# Palette par défaut de Paint
NOIR = (0, 0, 0)
BLANC = (255, 255, 255)
GRIS = (127, 127, 127)
GRIS_CLAIR = (195, 195, 195)
ROUGE = (237, 28, 36)
ORANGE = (255, 127, 39)
JAUNE = (255, 242, 0)
VERT = (34, 177, 76)
VERT_CLAIR = (181, 230, 29)
CYAN = (0, 162, 232)
BLEU_CLAIR = (153, 217, 234)
INDIGO = (63, 72, 204)
VIOLET = (163, 73, 164)
MARRON = (185, 122, 87)
MARRON_FONCE = (136, 0, 21)
ROSE = (255, 174, 201)
OR = (255, 201, 14)

# Visage du soleil et du nuage principal pour chaque météo.
# Soleil : "cool", "sourire", "triste", "pale" (sans visage)
# Nuage  : None, "sourire", "grognon", "pleure", "furieux"
VISAGES = {
    "soleil": {"soleil": "cool", "nuage": None},
    "nuageux": {"soleil": "triste", "nuage": "sourire"},
    "pluie": {"nuage": "pleure"},
    "orage": {"nuage": "furieux"},
    "neige": {"nuage": None},
    "brouillard": {},
}

W, H = 1920, 1080
TRAIT = 6  # épaisseur des contours


def police(taille):
    for chemin in (
        "/usr/share/fonts/truetype/comic/comicbd.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Comic_Sans_MS_Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(chemin).exists():
            return ImageFont.truetype(chemin, taille)

    return ImageFont.load_default(size=taille)


# ---------------------------------------------------------------- outils Paint

def tremble(points, rng, amp=6, pas=45, ferme=True):
    """Subdivise un tracé et ajoute un tremblement de main levée."""
    sortie = []
    n = len(points)

    for i in range(n if ferme else n - 1):
        (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
        long = math.hypot(x2 - x1, y2 - y1)
        k = max(1, int(long / pas))

        for j in range(k):
            t = j / k
            sortie.append((x1 + (x2 - x1) * t + rng.uniform(-amp, amp),
                           y1 + (y2 - y1) * t + rng.uniform(-amp, amp)))

    if not ferme:
        sortie.append(points[-1])

    return sortie


def forme(d, points, fond, rng, amp=6, contour=NOIR):
    pts = tremble(points, rng, amp)
    d.polygon(pts, fill=fond)

    if contour:
        d.line(pts + [pts[0]], fill=contour, width=TRAIT, joint="curve")


def rond(d, cx, cy, r, fond, rng, amp=4, contour=NOIR):
    n = max(12, int(r / 6))
    pts = [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
           for i in range(n)]
    forme(d, pts, fond, rng, amp, contour)


def bombe(d, cx, cy, r, n, couleur, rng, taille=3):
    """Outil aérographe de Paint."""

    for _ in range(n):
        a, rr = rng.uniform(0, 2 * math.pi), r * math.sqrt(rng.random())
        x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
        d.rectangle([x, y, x + taille, y + taille], fill=couleur)


def texte(d, xy, msg, taille, fond, contour=NOIR):
    f = police(taille)
    d.text(xy, msg, font=f, fill=fond, stroke_width=max(3, taille // 12), stroke_fill=contour)


# ---------------------------------------------------------------- éléments

def ciel(img, meteo, nuit):
    couleurs = {
        ("soleil", False): CYAN, ("nuageux", False): (120, 180, 210),
        ("pluie", False): (110, 130, 155), ("orage", False): (60, 55, 90),
        ("neige", False): (175, 195, 220), ("brouillard", False): (200, 200, 205),
        ("soleil", True): (10, 10, 70), ("nuageux", True): (25, 25, 60),
        ("pluie", True): (20, 25, 45), ("orage", True): (15, 10, 30),
        ("neige", True): (35, 40, 75), ("brouillard", True): (55, 55, 70),
    }
    base = couleurs[(meteo, nuit)]
    d = ImageDraw.Draw(img)
    # "Dégradé" fait main : bandes de couleur avec frontières tremblées
    rng = random.Random("ciel")
    bandes = 6

    for i in range(bandes):
        f = 1 + 0.07 * (i - 2)
        c = tuple(min(255, int(v * f)) for v in base)
        y = int(H * 0.62 * i / bandes) if i else -40
        bord = [(x, y + rng.uniform(-12, 12)) for x in range(-40, W + 80, 80)]
        d.polygon(bord + [(W, H), (0, H)], fill=c)


def soleil(d, cx, cy, r, humeur, rng):
    for i in range(16):
        a = 2 * math.pi * i / 16 + 0.1
        a1, a2 = a - 0.12, a + 0.12
        lg = r * (1.9 if i % 2 == 0 else 1.55)
        pts = [(cx + r * 0.9 * math.cos(a1), cy + r * 0.9 * math.sin(a1)),
               (cx + lg * math.cos(a), cy + lg * math.sin(a)),
               (cx + r * 0.9 * math.cos(a2), cy + r * 0.9 * math.sin(a2))]
        forme(d, pts, ORANGE if i % 2 else OR, rng, amp=3)
    rond(d, cx, cy, r, JAUNE, rng)

    if humeur == "cool":
        # Lunettes de soleil

        for dx in (-0.42, 0.42):
            forme(d, [(cx + (dx - 0.32) * r, cy - 0.28 * r), (cx + (dx + 0.32) * r, cy - 0.28 * r),
                      (cx + (dx + 0.25) * r, cy + 0.08 * r), (cx + (dx - 0.25) * r, cy + 0.08 * r)],
                  NOIR, rng, amp=2)
        d.line([(cx - 0.12 * r, cy - 0.22 * r), (cx + 0.12 * r, cy - 0.22 * r)], fill=NOIR, width=TRAIT)
        d.rectangle([cx - 0.62 * r, cy - 0.22 * r, cx - 0.52 * r, cy - 0.14 * r], fill=BLANC)
        d.arc([cx - 0.5 * r, cy - 0.15 * r, cx + 0.5 * r, cy + 0.6 * r], 20, 160, fill=NOIR, width=TRAIT + 2)
        rond(d, cx - 0.6 * r, cy + 0.25 * r, 0.12 * r, ROSE, rng, contour=None)
        rond(d, cx + 0.6 * r, cy + 0.25 * r, 0.12 * r, ROSE, rng, contour=None)
    elif humeur == "triste":
        for dx in (-0.3, 0.3):
            rond(d, cx + dx * r, cy - 0.15 * r, 0.09 * r, NOIR, rng, contour=None)
        d.arc([cx - 0.35 * r, cy + 0.25 * r, cx + 0.35 * r, cy + 0.7 * r], 200, 340, fill=NOIR, width=TRAIT)
    elif humeur == "sourire":
        for dx in (-0.3, 0.3):
            rond(d, cx + dx * r, cy - 0.15 * r, 0.09 * r, NOIR, rng, contour=None)
        d.arc([cx - 0.45 * r, cy - 0.2 * r, cx + 0.45 * r, cy + 0.55 * r], 20, 160, fill=NOIR, width=TRAIT + 2)


def lune(d, cx, cy, r, fond_ciel, rng):
    rond(d, cx, cy, r, (255, 250, 200), rng)
    rond(d, cx + r * 0.45, cy - r * 0.25, r * 0.85, fond_ciel, rng, contour=None)
    # Bonnet de nuit
    forme(d, [(cx - r * 0.75, cy - r * 0.55), (cx - r * 0.05, cy - r * 0.95),
              (cx + r * 0.35, cy - r * 1.7)], ROUGE, rng, amp=3)
    rond(d, cx + r * 0.35, cy - r * 1.7, r * 0.15, BLANC, rng)
    rond(d, cx - r * 0.55, cy - 0.05 * r, r * 0.07, NOIR, rng, contour=None)
    d.arc([cx - r * 0.75, cy + 0.15 * r, cx - r * 0.35, cy + 0.45 * r], 20, 120, fill=NOIR, width=TRAIT)
    texte(d, (cx + r * 0.6, cy - r * 1.3), "Zzz", int(r * 0.55), BLANC)


def etoiles(d, rng, n=40):
    for _ in range(n):
        x, y, t = rng.uniform(0, W), rng.uniform(0, H * 0.45), rng.uniform(8, 22)
        d.line([(x - t, y), (x + t, y)], fill=JAUNE, width=4)
        d.line([(x, y - t), (x, y + t)], fill=JAUNE, width=4)


def montagnes(d, neige):
    rng = random.Random("montagnes")
    sommets = [(150, 380, 700, VIOLET), (620, 300, 1200, MARRON), (1180, 340, 1750, VIOLET),
               (1500, 420, 2100, GRIS)]

    for x0, ys, x1, coul in sommets:
        xs = (x0 + x1) / 2 - 120
        base = H * 0.66
        forme(d, [(x0 - 250, base), (xs, ys), (x1, base)], coul, rng, amp=8)
        # Calotte de neige en zigzag (plus grosse s'il neige)
        f = 0.42 if neige else 0.22
        gx, dx_ = xs - (xs - (x0 - 250)) * f, xs + (x1 - xs) * f
        gy = ys + (base - ys) * f
        zig = [(gx, gy)]

        for k in range(1, 6):
            t = k / 6
            zig.append((gx + (dx_ - gx) * t, gy + (25 if k % 2 else -15)))
        zig.append((dx_, gy))
        forme(d, [(xs, ys)] + zig[::-1], BLANC, rng, amp=4)


def sol(d, meteo):
    rng = random.Random("sol")
    y = H * 0.64
    haut = [(x, y + rng.uniform(-18, 18)) for x in range(-40, W + 120, 120)]
    fond = BLANC if meteo == "neige" else VERT
    forme(d, haut + [(W + 40, H + 40), (-40, H + 40)], fond, rng, amp=5)
    # Lac
    rngl = random.Random("lac")
    eau = (200, 235, 250) if meteo == "neige" else INDIGO
    pts = [(520 + 380 * math.cos(a), 790 + 110 * math.sin(a))
           for a in [2 * math.pi * i / 28 for i in range(28)]]
    forme(d, pts, eau, rngl, amp=7)
    vague = random.Random("vagues")

    for _ in range(7):
        x, yv = vague.uniform(250, 720), vague.uniform(745, 840)

        if meteo == "neige":
            d.line([(x, yv), (x + 40, yv + 15)], fill=BLANC, width=4)  # fissures de glace
        else:
            d.arc([x, yv, x + 40, yv + 20], 200, 340, fill=BLANC, width=4)
            d.arc([x + 36, yv, x + 76, yv + 20], 200, 340, fill=BLANC, width=4)
    # Brins d'herbe
    herbe = random.Random("herbe")

    for _ in range(140):
        x, yh = herbe.uniform(0, W), herbe.uniform(H * 0.7, H)

        if 120 < x < 920 and 660 < yh < 920:
            continue
        coul = (220, 230, 240) if meteo == "neige" else VERT_CLAIR
        d.line([(x, yh), (x + herbe.uniform(-8, 8), yh - herbe.uniform(15, 35))], fill=coul, width=4)


def fleurs(d, meteo):
    if meteo == "neige":
        return
    rng = random.Random("fleurs")

    for _ in range(12):
        x, y = rng.uniform(950, 1850), rng.uniform(900, 1040)
        coul = rng.choice([ROUGE, ROSE, JAUNE, VIOLET, BLANC])
        d.line([(x, y), (x, y + 40)], fill=(0, 120, 40), width=5)

        for k in range(5):
            a = 2 * math.pi * k / 5
            rond(d, x + 16 * math.cos(a), y + 16 * math.sin(a), 11, coul, rng, amp=1, contour=None)
        rond(d, x, y, 9, OR, rng, amp=1, contour=None)


def maison(d, meteo):
    rng = random.Random("maison")
    x0, y0, x1, y1 = 1230, 600, 1560, 880
    forme(d, [(x0, y0), (x1, y0 - 12), (x1 + 6, y1), (x0 - 4, y1)], JAUNE, rng, amp=4)
    # Cheminée puis toit de travers
    forme(d, [(1440, 470), (1495, 465), (1500, 560), (1440, 560)], MARRON_FONCE, rng, amp=3)
    toit = [(x0 - 60, y0 + 10), (1385, 430), (x1 + 70, y0 - 5)]
    forme(d, toit, ROUGE, rng, amp=6)

    if meteo == "neige":
        forme(d, [(x0 - 30, y0 - 5), (1385, 430), (x1 + 40, y0 - 18), (1450, 500), (1385, 470),
                  (1300, 520)], BLANC, rng, amp=5)
    # Porte et fenêtres
    forme(d, [(1350, 740), (1430, 738), (1432, y1), (1350, y1)], MARRON, rng, amp=3)
    rond(d, 1415, 815, 7, OR, rng, amp=1, contour=None)

    for fx in (1260, 1465):
        forme(d, [(fx, 650), (fx + 75, 648), (fx + 76, 720), (fx, 722)], BLEU_CLAIR, rng, amp=3)
        d.line([(fx + 38, 650), (fx + 38, 720)], fill=NOIR, width=5)
        d.line([(fx, 686), (fx + 75, 686)], fill=NOIR, width=5)
        forme(d, [(fx - 15, 645), (fx + 8, 645), (fx + 8, 725), (fx - 15, 725)], ROUGE, rng, amp=2)
        forme(d, [(fx + 67, 643), (fx + 90, 643), (fx + 90, 725), (fx + 67, 725)], ROUGE, rng, amp=2)
    # Fumée en tortillons
    fumee = random.Random("fumee")

    for k in range(5):
        cx, cy = 1470 + 30 * k + fumee.uniform(-10, 10), 420 - 55 * k
        d.arc([cx - 30 - 6 * k, cy - 22, cx + 30 + 6 * k, cy + 22], 0, 300,
              fill=GRIS_CLAIR, width=TRAIT)


def arbre(d, meteo):
    rng = random.Random("arbre")
    forme(d, [(1690, 620), (1735, 620), (1745, 900), (1680, 900)], MARRON, rng, amp=4)
    feuillage = (0, 140, 60) if meteo != "neige" else (0, 120, 60)
    rond(d, 1712, 540, 140, feuillage, rng, amp=9)

    if meteo == "neige":
        forme(d, [(1590, 470), (1650, 410), (1760, 400), (1840, 460), (1712, 500)], BLANC, rng, amp=6)
    else:
        for px, py in ((1660, 500), (1760, 560), (1700, 610), (1770, 470)):
            rond(d, px, py, 16, ROUGE, rng, amp=2)  # pommes
            d.rectangle([px - 8, py - 10, px - 3, py - 5], fill=BLANC)


def bonhomme_neige(d):
    rng = random.Random("bonhomme")
    rond(d, 1050, 920, 85, BLANC, rng)
    rond(d, 1050, 790, 60, BLANC, rng)

    for y in (880, 920, 960):
        rond(d, 1050, y, 8, NOIR, rng, contour=None)
    rond(d, 1030, 780, 7, NOIR, rng, contour=None)
    rond(d, 1070, 780, 7, NOIR, rng, contour=None)
    forme(d, [(1048, 795), (1110, 808), (1048, 812)], ORANGE, rng, amp=1)
    forme(d, [(1000, 745), (1100, 745), (1090, 735), (1080, 680), (1020, 680), (1010, 735)], NOIR, rng, amp=2)
    d.line([(990, 820), (920, 770)], fill=MARRON, width=8)
    d.line([(1110, 820), (1180, 760)], fill=MARRON, width=8)
    d.line([(1000, 830), (1100, 832)], fill=ROUGE, width=16)


def nuage(d, cx, cy, s, fond, rng, visage=None):
    bulles = [(-1.1, 0.1, 0.55), (-0.45, -0.35, 0.7), (0.35, -0.3, 0.65),
              (1.0, 0.1, 0.55), (0, 0.25, 0.6), (-0.6, 0.3, 0.45), (0.6, 0.3, 0.45)]
    bulles = [(bx + rng.uniform(-0.1, 0.1), by + rng.uniform(-0.1, 0.1), br) for bx, by, br in bulles]

    for bx, by, br in bulles:  # contour noir, puis remplissage
        d.ellipse([cx + (bx - br) * s - TRAIT, cy + (by - br) * s - TRAIT,
                   cx + (bx + br) * s + TRAIT, cy + (by + br) * s + TRAIT], fill=NOIR)

    for bx, by, br in bulles:
        d.ellipse([cx + (bx - br) * s, cy + (by - br) * s, cx + (bx + br) * s, cy + (by + br) * s], fill=fond)

    if visage == "grognon":
        for dx in (-0.35, 0.35):
            rond(d, cx + dx * s, cy - 0.05 * s, 0.08 * s, NOIR, rng, contour=None)
            d.line([(cx + (dx - 0.18) * s, cy - (0.3 if dx < 0 else 0.18) * s),
                    (cx + (dx + 0.18) * s, cy - (0.18 if dx < 0 else 0.3) * s)], fill=NOIR, width=TRAIT)
        d.arc([cx - 0.3 * s, cy + 0.2 * s, cx + 0.3 * s, cy + 0.55 * s], 200, 340, fill=NOIR, width=TRAIT)
    elif visage == "furieux":
        for dx in (-0.35, 0.35):
            rond(d, cx + dx * s, cy, 0.1 * s, ROUGE, rng, contour=None)
            d.line([(cx + (dx - 0.22) * s, cy - (0.32 if dx < 0 else 0.1) * s),
                    (cx + (dx + 0.22) * s, cy - (0.1 if dx < 0 else 0.32) * s)], fill=NOIR, width=TRAIT + 2)
        forme(d, [(cx - 0.3 * s, cy + 0.45 * s), (cx - 0.15 * s, cy + 0.3 * s), (cx, cy + 0.45 * s),
                  (cx + 0.15 * s, cy + 0.3 * s), (cx + 0.3 * s, cy + 0.45 * s)], NOIR, rng, amp=1)
    elif visage == "sourire":
        for dx in (-0.35, 0.35):
            rond(d, cx + dx * s, cy - 0.05 * s, 0.08 * s, NOIR, rng, contour=None)
        d.arc([cx - 0.35 * s, cy - 0.1 * s, cx + 0.35 * s, cy + 0.5 * s], 20, 160, fill=NOIR, width=TRAIT + 2)
    elif visage == "pleure":
        for dx in (-0.35, 0.35):
            d.arc([cx + (dx - 0.12) * s, cy - 0.15 * s, cx + (dx + 0.12) * s, cy + 0.05 * s],
                  20, 160, fill=NOIR, width=TRAIT)
            forme(d, [(cx + dx * s, cy + 0.05 * s), (cx + (dx + 0.06) * s, cy + 0.25 * s),
                      (cx + (dx - 0.06) * s, cy + 0.25 * s)], CYAN, rng, amp=1)
        d.arc([cx - 0.25 * s, cy + 0.3 * s, cx + 0.25 * s, cy + 0.55 * s], 200, 340, fill=NOIR, width=TRAIT)


def pluie(d, rng, n, coul=CYAN):
    for _ in range(n):
        x, y = rng.uniform(-100, W), rng.uniform(250, H)
        d.line([(x, y), (x + 18, y + 55)], fill=coul, width=5)

    for _ in range(9):  # ronds dans l'eau
        x, y = rng.uniform(220, 800), rng.uniform(740, 850)
        d.ellipse([x - 30, y - 8, x + 30, y + 8], outline=BLANC, width=3)


def eclair(d, x, y, rng, echelle=1.0):
    e = echelle
    pts = [(x, y), (x + 90 * e, y), (x + 40 * e, y + 170 * e), (x + 120 * e, y + 160 * e),
           (x + 10 * e, y + 420 * e), (x + 35 * e, y + 230 * e), (x - 40 * e, y + 240 * e)]
    forme(d, pts, JAUNE, rng, amp=3)


def flocons(d, rng, n):
    for _ in range(n):
        x, y, t = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(8, 20)

        for k in range(3):
            a = math.pi * k / 3
            d.line([(x - t * math.cos(a), y - t * math.sin(a)), (x + t * math.cos(a), y + t * math.sin(a))],
                   fill=BLANC, width=4)


def brouillard(img, nuit):
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    rng = random.Random("brouillard")
    coul = (200, 200, 215) if nuit else (240, 240, 240)

    for i in range(9):
        y = 300 + i * 85
        pts = [(x, y + rng.uniform(-25, 25)) for x in range(-60, W + 120, 120)]
        bas = [(x, y + 70 + rng.uniform(-25, 25)) for x in range(W + 60, -120, -120)]
        d.polygon(pts + bas, fill=coul + (150,))

    for _ in range(40):
        bombe(d, rng.uniform(0, W), rng.uniform(250, H), rng.uniform(60, 160), 900, coul + (230,), rng)
    img.alpha_composite(calque)
    ImageDraw.Draw(img).text((60, 940), "on voit rien !!!", font=police(70),
                             fill=GRIS, stroke_width=4, stroke_fill=BLANC)


# ---------------------------------------------------------------- composition

def generer(meteo, nuit):
    img = Image.new("RGBA", (W, H), BLANC + (255,))
    ciel(img, meteo, nuit)
    d = ImageDraw.Draw(img)
    rng = random.Random(f"{meteo}-{nuit}")
    fond_ciel = img.getpixel((W // 2, 30))[:3]
    v = VISAGES.get(meteo, {})

    # Astres

    if nuit:
        if meteo in ("soleil", "nuageux", "neige"):
            etoiles(d, random.Random("etoiles"), 45 if meteo == "soleil" else 15)

        if meteo != "orage":
            lune(d, 260, 230, 110, fond_ciel, rng)
    else:
        if meteo == "soleil":
            soleil(d, 260, 220, 120, v.get("soleil", "cool"), rng)
        elif meteo == "nuageux":
            soleil(d, 300, 230, 100, v.get("soleil", "triste"), rng)
        elif meteo == "brouillard":
            rond(d, 300, 230, 90, (250, 245, 200), rng, contour=None)

    # Décor, assombri la nuit
    scene = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(scene)
    montagnes(ds, meteo == "neige")
    sol(ds, meteo)
    fleurs(ds, meteo)
    maison(ds, meteo)
    arbre(ds, meteo)

    if meteo == "neige":
        bonhomme_neige(ds)

    if nuit:
        r, g, b, a = scene.split()
        rgb = ImageChops.multiply(Image.merge("RGB", (r, g, b)), Image.new("RGB", (W, H), (85, 90, 150)))
        scene = Image.merge("RGBA", (*rgb.split(), a))
    img.alpha_composite(scene)
    d = ImageDraw.Draw(img)

    if nuit:  # fenêtres allumées par-dessus l'assombrissement
        rngm = random.Random("fenetres")

        for fx in (1260, 1465):
            forme(d, [(fx, 650), (fx + 75, 648), (fx + 76, 720), (fx, 722)], OR, rngm, amp=3)
            d.line([(fx + 38, 650), (fx + 38, 720)], fill=NOIR, width=5)
            d.line([(fx, 686), (fx + 75, 686)], fill=NOIR, width=5)

    # Météo
    blanc_nuage = (190, 195, 215) if nuit else BLANC
    gris_nuage = (90, 95, 115) if nuit else GRIS_CLAIR
    sombre = (45, 45, 60) if nuit else (100, 100, 110)

    if meteo == "soleil" and not nuit:
        nuage(d, 1000, 170, 90, BLANC, random.Random("n1"), visage=v.get("nuage"))
        nuage(d, 1600, 260, 70, BLANC, random.Random("n2"))
    elif meteo == "soleil":
        nuage(d, 1300, 200, 70, (60, 60, 110), random.Random("n2"))
    elif meteo == "nuageux":
        nuage(d, 470, 300, 140, gris_nuage, random.Random("n3"))
        nuage(d, 1000, 200, 160, blanc_nuage, random.Random("n4"), visage=v.get("nuage"))
        nuage(d, 1550, 260, 130, gris_nuage, random.Random("n5"))
        nuage(d, 1350, 420, 90, blanc_nuage, random.Random("n6"))
    elif meteo == "pluie":
        pluie(d, rng, 260)

        for i, (x, y, s) in enumerate([(300, 180, 150), (850, 150, 170), (1400, 190, 160), (1800, 140, 120)]):
            nuage(d, x, y, s, gris_nuage if i % 2 else sombre, random.Random(f"p{i}"),
                  visage=v.get("nuage") if i == 1 else None)
    elif meteo == "orage":
        pluie(d, rng, 380, (120, 150, 255))
        eclair(d, 560, 220, random.Random("e1"), 1.1)
        eclair(d, 1420, 250, random.Random("e2"), 0.8)

        for i, (x, y, s) in enumerate([(250, 150, 170), (800, 130, 190), (1350, 160, 180), (1800, 130, 140)]):
            nuage(d, x, y, s, sombre, random.Random(f"o{i}"), visage=v.get("nuage") if i == 1 else None)
        texte(d, (900, 400), "KRAKOOOM !!", 120, JAUNE, contour=ROUGE)
    elif meteo == "neige":
        for i, (x, y, s) in enumerate([(400, 170, 130), (1100, 150, 150), (1700, 190, 120)]):
            nuage(d, x, y, s, blanc_nuage, random.Random(f"s{i}"), visage=v.get("nuage") if i == 1 else None)
        flocons(d, rng, 160)
    elif meteo == "brouillard":
        brouillard(img, nuit)

    return img.convert("RGB")


METEOS = ["soleil", "nuageux", "pluie", "orage", "neige", "brouillard"]


def main():
    global W, H
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("sortie", nargs="?", default=str(Path.home() / "Images/paint-weather"))
    p.add_argument("--largeur", type=int, default=1920)
    p.add_argument("--hauteur", type=int, default=1080)
    a = p.parse_args()
    sortie = Path(a.sortie).expanduser()
    sortie.mkdir(parents=True, exist_ok=True)

    for meteo in METEOS:
        for nuit in (False, True):
            img = generer(meteo, nuit)

            if (a.largeur, a.hauteur) != (W, H):
                img = img.resize((a.largeur, a.hauteur), Image.NEAREST)
            nom = f"{meteo}-{'nuit' if nuit else 'jour'}.png"
            img.save(sortie / nom)

            if meteo == "soleil" and not nuit:
                img.save(sortie / "defaut.png")
            print(sortie / nom)


if __name__ == "__main__":
    main()
