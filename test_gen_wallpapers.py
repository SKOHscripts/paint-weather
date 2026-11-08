"""Tests de gen_wallpapers.py : une classe par fonction, un test par cas.

Lancer : pytest --cov=gen_wallpapers --cov-report=term-missing
"""
import random
import runpy
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image, ImageStat

import gen_wallpapers as gen


@pytest.fixture
def rng():
    return random.Random(0)


@pytest.fixture
def d():
    """Faux ImageDraw : on vérifie les appels de dessin sans rendre d'image."""
    return MagicMock()


def appels(d, nom):
    return [c for c in d.method_calls if c[0] == nom]


def points_polygone(appel):
    return appel.args[0]


# ---------------------------------------------------------------- police

class TestPolice:
    @pytest.fixture
    def faux(self, monkeypatch):
        """Path dont seuls les chemins de `existants` existent ; truetype/load_default espionnés."""
        existants = set()

        class FauxPath:
            def __init__(self, chemin):
                self.chemin = chemin

            def exists(self):
                return self.chemin in existants

        monkeypatch.setattr(gen, "Path", FauxPath)
        monkeypatch.setattr(gen.ImageFont, "truetype", lambda chemin, taille: ("truetype", chemin, taille))
        monkeypatch.setattr(gen.ImageFont, "load_default", lambda size: ("defaut", size))
        return existants

    def test_premier_chemin(self, faux):
        faux.add("/usr/share/fonts/truetype/comic/comicbd.ttf")
        assert gen.police(30) == ("truetype", "/usr/share/fonts/truetype/comic/comicbd.ttf", 30)

    def test_deuxieme_chemin(self, faux):
        faux.add("/usr/share/fonts/truetype/msttcorefonts/Comic_Sans_MS_Bold.ttf")
        assert gen.police(30)[1].endswith("Comic_Sans_MS_Bold.ttf")

    def test_troisieme_chemin(self, faux):
        faux.add("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        assert gen.police(30)[1].endswith("DejaVuSans-Bold.ttf")

    def test_premier_chemin_prioritaire(self, faux):
        faux.update({"/usr/share/fonts/truetype/comic/comicbd.ttf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"})
        assert gen.police(30)[1].endswith("comicbd.ttf")

    def test_aucune_police_repli_sur_defaut(self, faux):
        assert gen.police(42) == ("defaut", 42)


# ---------------------------------------------------------------- tremble

class TestTremble:
    CARRE = [(0, 0), (100, 0), (100, 100), (0, 100)]

    def test_ferme_sans_tremblement_rejoint_les_sommets(self, rng):
        sortie = gen.tremble(self.CARRE, rng, amp=0, pas=100)
        assert sortie == [(0, 0), (100, 0), (100, 100), (0, 100)]

    def test_ferme_boucle_sur_le_premier_point(self, rng):
        # le dernier segment va de (0,100) vers (0,0)
        sortie = gen.tremble(self.CARRE, rng, amp=0, pas=50)
        assert sortie[-1] == (0, 50)

    def test_ouvert_ajoute_le_dernier_point(self, rng):
        sortie = gen.tremble([(0, 0), (100, 0)], rng, amp=0, pas=100, ferme=False)
        assert sortie == [(0, 0), (100, 0)]

    def test_ouvert_ne_boucle_pas(self, rng):
        sortie = gen.tremble(self.CARRE, rng, amp=0, pas=1000, ferme=False)
        assert sortie == [(0, 0), (100, 0), (100, 100), (0, 100)]

    def test_segment_court_donne_un_seul_point(self, rng):
        assert len(gen.tremble([(0, 0), (10, 0)], rng, amp=0, pas=45, ferme=False)) == 2

    def test_segment_long_est_subdivise(self, rng):
        sortie = gen.tremble([(0, 0), (90, 0)], rng, amp=0, pas=45, ferme=False)
        assert sortie == [(0, 0), (45, 0), (90, 0)]

    def test_tremblement_borne_par_amp(self, rng):
        sortie = gen.tremble([(0, 0), (100, 0)], rng, amp=5, pas=10, ferme=False)
        assert all(-5 <= x <= 105 and -5 <= y <= 5 for x, y in sortie[:-1])

    def test_tremblement_deterministe_avec_meme_graine(self):
        a = gen.tremble(self.CARRE, random.Random(1))
        b = gen.tremble(self.CARRE, random.Random(1))
        assert a == b


# ---------------------------------------------------------------- forme

class TestForme:
    TRI = [(0, 0), (50, 0), (25, 40)]

    def test_remplit_le_polygone(self, d, rng):
        gen.forme(d, self.TRI, gen.ROUGE, rng)
        assert appels(d, "polygon")[0].kwargs["fill"] == gen.ROUGE

    def test_trace_le_contour_par_defaut(self, d, rng):
        gen.forme(d, self.TRI, gen.ROUGE, rng)
        ligne = appels(d, "line")[0]
        assert ligne.kwargs["fill"] == gen.NOIR
        assert ligne.kwargs["width"] == gen.TRAIT

    def test_contour_ferme_sur_le_premier_point(self, d, rng):
        gen.forme(d, self.TRI, gen.ROUGE, rng)
        pts = points_polygone(appels(d, "line")[0])
        assert pts[0] == pts[-1]

    def test_contour_personnalise(self, d, rng):
        gen.forme(d, self.TRI, gen.ROUGE, rng, contour=gen.VERT)
        assert appels(d, "line")[0].kwargs["fill"] == gen.VERT

    def test_sans_contour(self, d, rng):
        gen.forme(d, self.TRI, gen.ROUGE, rng, contour=None)
        assert appels(d, "line") == []
        assert len(appels(d, "polygon")) == 1


# ---------------------------------------------------------------- rond

class TestRond:
    def test_petit_rayon_utilise_12_points_minimum(self, d, rng):
        gen.rond(d, 0, 0, 10, gen.ROUGE, rng, amp=0)
        assert len(points_polygone(appels(d, "polygon")[0])) == 12  # un point par segment

    def test_grand_rayon_ajoute_des_points(self, d, rng):
        gen.rond(d, 0, 0, 120, gen.ROUGE, rng, amp=0)
        assert len(points_polygone(appels(d, "polygon")[0])) >= 20

    def test_points_sur_le_cercle_sans_tremblement(self, d, rng):
        gen.rond(d, 100, 100, 10, gen.ROUGE, rng, amp=0)
        for x, y in points_polygone(appels(d, "polygon")[0]):
            assert ((x - 100) ** 2 + (y - 100) ** 2) ** 0.5 == pytest.approx(10)

    def test_couleur_de_fond(self, d, rng):
        gen.rond(d, 0, 0, 10, gen.VERT, rng)
        assert appels(d, "polygon")[0].kwargs["fill"] == gen.VERT

    def test_sans_contour(self, d, rng):
        gen.rond(d, 0, 0, 10, gen.VERT, rng, contour=None)
        assert appels(d, "line") == []

    def test_avec_contour_par_defaut(self, d, rng):
        gen.rond(d, 0, 0, 10, gen.VERT, rng)
        assert len(appels(d, "line")) == 1


# ---------------------------------------------------------------- bombe

class TestBombe:
    def test_dessine_n_carres(self, d, rng):
        gen.bombe(d, 50, 50, 20, 30, gen.BLANC, rng)
        assert len(appels(d, "rectangle")) == 30

    def test_aucun_point_si_n_nul(self, d, rng):
        gen.bombe(d, 50, 50, 20, 0, gen.BLANC, rng)
        assert appels(d, "rectangle") == []

    def test_points_dans_le_disque(self, d, rng):
        gen.bombe(d, 50, 50, 20, 200, gen.BLANC, rng, taille=0)
        for c in appels(d, "rectangle"):
            x, y = c.args[0][0], c.args[0][1]
            assert ((x - 50) ** 2 + (y - 50) ** 2) ** 0.5 <= 20 + 1e-9

    def test_taille_et_couleur(self, d, rng):
        gen.bombe(d, 0, 0, 5, 1, gen.ROUGE, rng, taille=7)
        c = appels(d, "rectangle")[0]
        x0, y0, x1, y1 = c.args[0]
        assert (x1 - x0, y1 - y0) == pytest.approx((7, 7))
        assert c.kwargs["fill"] == gen.ROUGE


# ---------------------------------------------------------------- texte

class TestTexte:
    @pytest.fixture(autouse=True)
    def police_factice(self, monkeypatch):
        monkeypatch.setattr(gen, "police", lambda taille: f"police{taille}")

    def test_ecrit_le_message(self, d):
        gen.texte(d, (1, 2), "coucou", 60, gen.JAUNE)
        c = appels(d, "text")[0]
        assert c.args == ((1, 2), "coucou")
        assert c.kwargs["fill"] == gen.JAUNE
        assert c.kwargs["font"] == "police60"

    def test_contour_noir_par_defaut(self, d):
        gen.texte(d, (0, 0), "x", 60, gen.JAUNE)
        assert appels(d, "text")[0].kwargs["stroke_fill"] == gen.NOIR

    def test_contour_personnalise(self, d):
        gen.texte(d, (0, 0), "x", 60, gen.JAUNE, contour=gen.ROUGE)
        assert appels(d, "text")[0].kwargs["stroke_fill"] == gen.ROUGE

    def test_epaisseur_proportionnelle_a_la_taille(self, d):
        gen.texte(d, (0, 0), "x", 120, gen.JAUNE)
        assert appels(d, "text")[0].kwargs["stroke_width"] == 10

    def test_epaisseur_minimale_de_3(self, d):
        gen.texte(d, (0, 0), "x", 12, gen.JAUNE)
        assert appels(d, "text")[0].kwargs["stroke_width"] == 3


# ---------------------------------------------------------------- ciel

class TestCiel:
    COMBOS = [(m, n) for m in gen.METEOS for n in (False, True)]

    @pytest.mark.parametrize("meteo,nuit", COMBOS)
    def test_remplit_toute_l_image(self, meteo, nuit):
        img = Image.new("RGBA", (gen.W, gen.H), gen.BLANC + (255,))
        gen.ciel(img, meteo, nuit)
        assert img.getpixel((gen.W // 2, 30))[:3] != gen.BLANC
        assert img.getpixel((5, gen.H - 5))[:3] != gen.BLANC

    @pytest.mark.parametrize("meteo", gen.METEOS)
    def test_nuit_plus_sombre_que_jour(self, meteo):
        pixels = {}
        for nuit in (False, True):
            img = Image.new("RGBA", (gen.W, gen.H), gen.BLANC + (255,))
            gen.ciel(img, meteo, nuit)
            pixels[nuit] = sum(img.getpixel((gen.W // 2, 30))[:3])
        assert pixels[True] < pixels[False]

    def test_meteo_inconnue_leve_keyerror(self):
        img = Image.new("RGBA", (10, 10))
        with pytest.raises(KeyError):
            gen.ciel(img, "tornade", False)

    def test_bandes_de_couleurs_differentes(self):
        img = Image.new("RGBA", (gen.W, gen.H), gen.BLANC + (255,))
        gen.ciel(img, "soleil", False)
        assert img.getpixel((gen.W // 2, 30)) != img.getpixel((gen.W // 2, int(gen.H * 0.6)))


# ---------------------------------------------------------------- soleil

class TestSoleil:
    def test_dessine_16_rayons_et_le_disque(self, d, rng):
        gen.soleil(d, 0, 0, 100, None, rng)
        assert len(appels(d, "polygon")) == 17

    def test_rayons_alternent_or_et_orange(self, d, rng):
        gen.soleil(d, 0, 0, 100, None, rng)
        couleurs = [c.kwargs["fill"] for c in appels(d, "polygon")[:16]]
        assert couleurs[0] == gen.OR and couleurs[1] == gen.ORANGE

    def test_disque_jaune(self, d, rng):
        gen.soleil(d, 0, 0, 100, None, rng)
        assert appels(d, "polygon")[16].kwargs["fill"] == gen.JAUNE

    def test_humeur_cool_porte_des_lunettes(self, d, rng):
        gen.soleil(d, 0, 0, 100, "cool", rng)
        assert len(appels(d, "rectangle")) == 1  # reflet blanc
        assert appels(d, "arc")[0].args[1:3] == (20, 160)

    def test_humeur_cool_a_les_joues_roses(self, d, rng):
        gen.soleil(d, 0, 0, 100, "cool", rng)
        fonds = [c.kwargs["fill"] for c in appels(d, "polygon")]
        assert fonds.count(gen.ROSE) == 2
        assert fonds.count(gen.NOIR) == 2  # deux verres

    def test_humeur_triste_a_la_bouche_inversee(self, d, rng):
        gen.soleil(d, 0, 0, 100, "triste", rng)
        assert appels(d, "arc")[0].args[1:3] == (200, 340)

    def test_humeur_triste_a_deux_yeux(self, d, rng):
        gen.soleil(d, 0, 0, 100, "triste", rng)
        fonds = [c.kwargs["fill"] for c in appels(d, "polygon")]
        assert fonds.count(gen.NOIR) == 2

    def test_humeur_sourire(self, d, rng):
        gen.soleil(d, 0, 0, 100, "sourire", rng)
        assert appels(d, "arc")[0].args[1:3] == (20, 160)
        assert appels(d, "rectangle") == []

    def test_humeur_pale_sans_visage(self, d, rng):
        gen.soleil(d, 0, 0, 100, "pale", rng)
        assert appels(d, "arc") == []
        assert len(appels(d, "polygon")) == 17

    def test_humeur_none_sans_visage(self, d, rng):
        gen.soleil(d, 0, 0, 100, None, rng)
        assert appels(d, "arc") == []


# ---------------------------------------------------------------- lune

class TestLune:
    def test_ecrit_zzz(self, d, rng):
        gen.lune(d, 200, 200, 100, (10, 10, 70), rng)
        assert appels(d, "text")[0].args[1] == "Zzz"

    def test_dessine_la_bouche(self, d, rng):
        gen.lune(d, 200, 200, 100, (10, 10, 70), rng)
        assert len(appels(d, "arc")) == 1

    def test_croissant_decoupe_avec_la_couleur_du_ciel(self, d, rng):
        ciel = (10, 10, 70)
        gen.lune(d, 200, 200, 100, ciel, rng)
        fonds = [c.kwargs["fill"] for c in appels(d, "polygon")]
        assert fonds[0] == (255, 250, 200)
        assert fonds[1] == ciel

    def test_bonnet_rouge_avec_pompon_blanc(self, d, rng):
        gen.lune(d, 200, 200, 100, (10, 10, 70), rng)
        fonds = [c.kwargs["fill"] for c in appels(d, "polygon")]
        assert gen.ROUGE in fonds and gen.BLANC in fonds


# ---------------------------------------------------------------- etoiles

class TestEtoiles:
    def test_nombre_par_defaut(self, d, rng):
        gen.etoiles(d, rng)
        assert len(appels(d, "line")) == 80  # 2 traits par étoile

    def test_nombre_personnalise(self, d, rng):
        gen.etoiles(d, rng, n=5)
        assert len(appels(d, "line")) == 10

    def test_aucune_etoile(self, d, rng):
        gen.etoiles(d, rng, n=0)
        assert appels(d, "line") == []

    def test_etoiles_jaunes_dans_le_haut_du_ciel(self, d, rng):
        gen.etoiles(d, rng, n=30)
        for c in appels(d, "line"):
            assert c.kwargs["fill"] == gen.JAUNE
            assert all(y <= gen.H * 0.45 + 22 for _, y in c.args[0])


# ---------------------------------------------------------------- montagnes

class TestMontagnes:
    @staticmethod
    def calottes(d):
        return [c for c in appels(d, "polygon") if c.kwargs["fill"] == gen.BLANC]

    @staticmethod
    def largeur(appel):
        xs = [x for x, _ in points_polygone(appel)]
        return max(xs) - min(xs)

    def test_quatre_montagnes_et_quatre_calottes(self, d):
        gen.montagnes(d, False)
        assert len(appels(d, "polygon")) == 8
        assert len(self.calottes(d)) == 4

    def test_couleurs_des_montagnes(self, d):
        gen.montagnes(d, False)
        fonds = [c.kwargs["fill"] for c in appels(d, "polygon")][::2]
        assert fonds == [gen.VIOLET, gen.MARRON, gen.VIOLET, gen.GRIS]

    def test_calotte_plus_grosse_sous_la_neige(self, d):
        d_neige = MagicMock()
        gen.montagnes(d, False)
        gen.montagnes(d_neige, True)
        sans = sum(self.largeur(c) for c in self.calottes(d))
        avec = sum(self.largeur(c) for c in self.calottes(d_neige))
        assert avec > sans * 1.5


# ---------------------------------------------------------------- sol

class TestSol:
    @staticmethod
    def fonds(d):
        return [c.kwargs["fill"] for c in appels(d, "polygon")]

    def test_herbe_verte_hors_neige(self, d):
        gen.sol(d, "soleil")
        assert self.fonds(d)[0] == gen.VERT

    def test_sol_blanc_sous_la_neige(self, d):
        gen.sol(d, "neige")
        assert self.fonds(d)[0] == gen.BLANC

    def test_lac_bleu_hors_neige(self, d):
        gen.sol(d, "pluie")
        assert self.fonds(d)[1] == gen.INDIGO

    def test_lac_gele_sous_la_neige(self, d):
        gen.sol(d, "neige")
        assert self.fonds(d)[1] == (200, 235, 250)

    def test_vagues_en_arcs_hors_neige(self, d):
        gen.sol(d, "soleil")
        assert len(appels(d, "arc")) == 14  # 7 vagues, 2 arcs chacune

    def test_fissures_de_glace_sous_la_neige(self, d):
        gen.sol(d, "neige")
        assert appels(d, "arc") == []

    def test_brins_d_herbe_clairs_hors_neige(self, d):
        gen.sol(d, "soleil")
        assert all(c.kwargs["fill"] in (gen.VERT_CLAIR, gen.BLANC) for c in appels(d, "line") if c.kwargs["width"] == 4)
        assert any(c.kwargs["fill"] == gen.VERT_CLAIR for c in appels(d, "line"))

    def test_brins_d_herbe_givres_sous_la_neige(self, d):
        gen.sol(d, "neige")
        assert any(c.kwargs["fill"] == (220, 230, 240) for c in appels(d, "line"))
        assert not any(c.kwargs["fill"] == gen.VERT_CLAIR for c in appels(d, "line"))

    def test_pas_d_herbe_sur_la_maison_et_le_lac(self, d):
        gen.sol(d, "soleil")
        for c in appels(d, "line"):
            if c.kwargs["fill"] == gen.VERT_CLAIR:
                x, y = c.args[0][0]
                assert not (120 < x < 920 and 660 < y < 920)


# ---------------------------------------------------------------- fleurs

class TestFleurs:
    def test_rien_sous_la_neige(self, d):
        gen.fleurs(d, "neige")
        assert d.method_calls == []

    def test_douze_tiges(self, d):
        gen.fleurs(d, "soleil")
        tiges = [c for c in appels(d, "line") if c.kwargs["fill"] == (0, 120, 40)]
        assert len(tiges) == 12

    def test_cinq_petales_et_un_coeur_par_fleur(self, d):
        gen.fleurs(d, "soleil")
        assert len(appels(d, "polygon")) == 12 * 6

    def test_coeur_dore(self, d):
        gen.fleurs(d, "pluie")
        assert appels(d, "polygon")[5].kwargs["fill"] == gen.OR


# ---------------------------------------------------------------- maison

class TestMaison:
    def test_sans_neige_deux_fenetres_a_volets(self, d):
        gen.maison(d, "soleil")
        fonds = [c.kwargs["fill"] for c in appels(d, "polygon")]
        assert fonds.count(gen.BLEU_CLAIR) == 2
        assert fonds.count(gen.ROUGE) == 1 + 4  # toit + 4 volets

    def test_facade_jaune_et_porte_marron(self, d):
        gen.maison(d, "soleil")
        fonds = [c.kwargs["fill"] for c in appels(d, "polygon")]
        assert gen.JAUNE in fonds and gen.MARRON in fonds

    def test_neige_ajoute_un_toit_blanc(self, d):
        d_neige = MagicMock()
        gen.maison(d, "soleil")
        gen.maison(d_neige, "neige")
        assert len(appels(d_neige, "polygon")) == len(appels(d, "polygon")) + 1
        assert gen.BLANC in [c.kwargs["fill"] for c in appels(d_neige, "polygon")]

    def test_sans_neige_pas_de_blanc(self, d):
        gen.maison(d, "pluie")
        assert gen.BLANC not in [c.kwargs["fill"] for c in appels(d, "polygon")]

    def test_fumee_cinq_tortillons(self, d):
        gen.maison(d, "soleil")
        assert len(appels(d, "arc")) == 5
        assert all(c.kwargs["fill"] == gen.GRIS_CLAIR for c in appels(d, "arc"))


# ---------------------------------------------------------------- arbre

class TestArbre:
    def test_pommes_hors_neige(self, d):
        gen.arbre(d, "soleil")
        assert len(appels(d, "rectangle")) == 4  # reflets blancs
        fonds = [c.kwargs["fill"] for c in appels(d, "polygon")]
        assert fonds.count(gen.ROUGE) == 4

    def test_feuillage_vert_hors_neige(self, d):
        gen.arbre(d, "soleil")
        assert appels(d, "polygon")[1].kwargs["fill"] == (0, 140, 60)

    def test_neige_sur_le_feuillage(self, d):
        gen.arbre(d, "neige")
        fonds = [c.kwargs["fill"] for c in appels(d, "polygon")]
        assert fonds[1] == (0, 120, 60)
        assert fonds[2] == gen.BLANC

    def test_pas_de_pommes_sous_la_neige(self, d):
        gen.arbre(d, "neige")
        assert appels(d, "rectangle") == []
        assert gen.ROUGE not in [c.kwargs["fill"] for c in appels(d, "polygon")]

    def test_tronc_marron(self, d):
        gen.arbre(d, "soleil")
        assert appels(d, "polygon")[0].kwargs["fill"] == gen.MARRON


# ---------------------------------------------------------------- bonhomme_neige

class TestBonhommeNeige:
    def test_deux_boules_blanches(self, d):
        gen.bonhomme_neige(d)
        fonds = [c.kwargs["fill"] for c in appels(d, "polygon")]
        assert fonds[:2] == [gen.BLANC, gen.BLANC]

    def test_trois_boutons_et_deux_yeux_noirs(self, d):
        gen.bonhomme_neige(d)
        fonds = [c.kwargs["fill"] for c in appels(d, "polygon")]
        assert fonds.count(gen.NOIR) == 5 + 1  # boutons, yeux, chapeau

    def test_nez_carotte(self, d):
        gen.bonhomme_neige(d)
        assert gen.ORANGE in [c.kwargs["fill"] for c in appels(d, "polygon")]

    def test_bras_en_branches(self, d):
        gen.bonhomme_neige(d)
        bras = [c for c in appels(d, "line") if c.kwargs["fill"] == gen.MARRON and c.kwargs["width"] == 8]
        assert len(bras) == 2

    def test_echarpe_rouge(self, d):
        gen.bonhomme_neige(d)
        echarpe = [c for c in appels(d, "line") if c.kwargs["fill"] == gen.ROUGE]
        assert len(echarpe) == 1 and echarpe[0].kwargs["width"] == 16


# ---------------------------------------------------------------- nuage

class TestNuage:
    def test_sept_bulles_en_contour_puis_en_fond(self, d, rng):
        gen.nuage(d, 500, 300, 100, gen.BLANC, rng)
        ellipses = appels(d, "ellipse")
        assert len(ellipses) == 14
        assert all(c.kwargs["fill"] == gen.NOIR for c in ellipses[:7])
        assert all(c.kwargs["fill"] == gen.BLANC for c in ellipses[7:])

    def test_sans_visage(self, d, rng):
        gen.nuage(d, 500, 300, 100, gen.BLANC, rng, visage=None)
        assert appels(d, "arc") == [] and appels(d, "line") == []

    def test_visage_inconnu_ignore(self, d, rng):
        gen.nuage(d, 500, 300, 100, gen.BLANC, rng, visage="rigolo")
        assert appels(d, "arc") == [] and appels(d, "line") == []

    def test_visage_grognon(self, d, rng):
        gen.nuage(d, 500, 300, 100, gen.BLANC, rng, visage="grognon")
        assert len(appels(d, "line")) == 2  # sourcils
        assert appels(d, "arc")[0].args[1:3] == (200, 340)

    def test_visage_furieux(self, d, rng):
        gen.nuage(d, 500, 300, 100, gen.BLANC, rng, visage="furieux")
        fonds = [c.kwargs["fill"] for c in appels(d, "polygon")]
        assert fonds.count(gen.ROUGE) == 2  # yeux
        assert gen.NOIR in fonds            # bouche en dents de scie
        assert appels(d, "arc") == []

    def test_visage_sourire(self, d, rng):
        gen.nuage(d, 500, 300, 100, gen.BLANC, rng, visage="sourire")
        assert len(appels(d, "arc")) == 1
        assert appels(d, "arc")[0].args[1:3] == (20, 160)

    def test_visage_pleure(self, d, rng):
        gen.nuage(d, 500, 300, 100, gen.BLANC, rng, visage="pleure")
        assert len(appels(d, "arc")) == 3  # 2 yeux fermés + bouche
        assert [c.kwargs["fill"] for c in appels(d, "polygon")].count(gen.CYAN) == 2  # larmes

    def test_taille_proportionnelle_a_s(self, rng):
        petit, grand = MagicMock(), MagicMock()
        gen.nuage(petit, 500, 300, 50, gen.BLANC, random.Random(0))
        gen.nuage(grand, 500, 300, 200, gen.BLANC, random.Random(0))
        largeur = lambda m: max(c.args[0][2] for c in appels(m, "ellipse")) - min(c.args[0][0] for c in appels(m, "ellipse"))
        assert largeur(grand) > largeur(petit) * 3


# ---------------------------------------------------------------- pluie

class TestPluie:
    def test_n_gouttes(self, d, rng):
        gen.pluie(d, rng, 25)
        assert len(appels(d, "line")) == 25

    def test_gouttes_cyan_par_defaut(self, d, rng):
        gen.pluie(d, rng, 5)
        assert all(c.kwargs["fill"] == gen.CYAN for c in appels(d, "line"))

    def test_couleur_personnalisee(self, d, rng):
        gen.pluie(d, rng, 5, (1, 2, 3))
        assert all(c.kwargs["fill"] == (1, 2, 3) for c in appels(d, "line"))

    def test_neuf_ronds_dans_l_eau(self, d, rng):
        gen.pluie(d, rng, 0)
        assert len(appels(d, "ellipse")) == 9

    def test_ronds_blancs_sur_le_lac(self, d, rng):
        gen.pluie(d, rng, 0)
        for c in appels(d, "ellipse"):
            assert c.kwargs["outline"] == gen.BLANC


# ---------------------------------------------------------------- eclair

class TestEclair:
    def test_forme_jaune(self, d, rng):
        gen.eclair(d, 100, 100, rng)
        assert appels(d, "polygon")[0].kwargs["fill"] == gen.JAUNE

    def test_contour_noir(self, d, rng):
        gen.eclair(d, 100, 100, rng)
        assert appels(d, "line")[0].kwargs["fill"] == gen.NOIR

    def test_echelle_agrandit_l_eclair(self):
        petit, grand = MagicMock(), MagicMock()
        gen.eclair(petit, 0, 0, random.Random(0), 1.0)
        gen.eclair(grand, 0, 0, random.Random(0), 2.0)
        hauteur = lambda m: max(y for _, y in points_polygone(appels(m, "polygon")[0]))
        assert hauteur(grand) > hauteur(petit) * 1.8

    def test_echelle_par_defaut_est_un(self):
        a, b = MagicMock(), MagicMock()
        gen.eclair(a, 0, 0, random.Random(0))
        gen.eclair(b, 0, 0, random.Random(0), 1.0)
        assert appels(a, "polygon")[0].args == appels(b, "polygon")[0].args


# ---------------------------------------------------------------- flocons

class TestFlocons:
    def test_trois_traits_par_flocon(self, d, rng):
        gen.flocons(d, rng, 10)
        assert len(appels(d, "line")) == 30

    def test_aucun_flocon(self, d, rng):
        gen.flocons(d, rng, 0)
        assert appels(d, "line") == []

    def test_flocons_blancs(self, d, rng):
        gen.flocons(d, rng, 5)
        assert all(c.kwargs["fill"] == gen.BLANC for c in appels(d, "line"))

    def test_traits_centres_sur_le_flocon(self, d, rng):
        gen.flocons(d, rng, 1)
        (x0, y0), (x1, y1) = appels(d, "line")[0].args[0]
        assert 0 <= (x0 + x1) / 2 <= gen.W
        assert 0 <= (y0 + y1) / 2 <= gen.H


# ---------------------------------------------------------------- brouillard

class TestBrouillard:
    @pytest.fixture(autouse=True)
    def sans_texte(self, monkeypatch):
        # évite de dépendre des polices installées
        monkeypatch.setattr(gen, "police", lambda taille: gen.ImageFont.load_default(size=taille))

    @staticmethod
    def image():
        return Image.new("RGBA", (gen.W, gen.H), (0, 0, 0, 255))

    def test_modifie_l_image(self):
        img = self.image()
        vide = img.copy()
        gen.brouillard(img, False)
        assert img.tobytes() != vide.tobytes()

    def test_jour_plus_clair_que_nuit(self):
        jour, nuit = self.image(), self.image()
        gen.brouillard(jour, False)
        gen.brouillard(nuit, True)
        luminosite = lambda im: ImageStat.Stat(im.convert("L")).mean[0]
        assert luminosite(jour) > luminosite(nuit)

    def test_ecrit_le_texte_en_bas_a_gauche(self):
        img = self.image()
        gen.brouillard(img, False)
        zone = img.crop((60, 940, 700, 1030)).convert("RGB")
        assert gen.BLANC in {c for _, c in zone.getcolors(maxcolors=10**6)}

    def test_image_garde_sa_taille(self):
        img = self.image()
        gen.brouillard(img, True)
        assert img.size == (gen.W, gen.H)


# ---------------------------------------------------------------- generer

class TestGenerer:
    COMBOS = [(m, n) for m in gen.METEOS for n in (False, True)]

    @pytest.mark.parametrize("meteo,nuit", COMBOS)
    def test_image_rgb_a_la_bonne_taille(self, meteo, nuit):
        img = gen.generer(meteo, nuit)
        assert img.mode == "RGB"
        assert img.size == (gen.W, gen.H)

    @pytest.mark.parametrize("meteo", gen.METEOS)
    def test_jour_et_nuit_different(self, meteo):
        assert gen.generer(meteo, False).tobytes() != gen.generer(meteo, True).tobytes()

    def test_deterministe(self):
        assert gen.generer("pluie", False).tobytes() == gen.generer("pluie", False).tobytes()

    def test_visages_lus_dans_le_dictionnaire(self, monkeypatch):
        vus = []
        vrai = gen.nuage
        monkeypatch.setattr(gen, "nuage", lambda *a, visage=None, **k: (vus.append(visage), vrai(*a, visage=visage, **k)))
        monkeypatch.setitem(gen.VISAGES, "soleil", {"soleil": "triste", "nuage": "grognon"})
        gen.generer("soleil", False)
        assert "grognon" in vus

    def test_meteo_absente_des_visages_utilise_les_defauts(self, monkeypatch):
        monkeypatch.setattr(gen, "VISAGES", {})
        assert gen.generer("soleil", False).size == (gen.W, gen.H)

    def test_neige_dessine_un_bonhomme(self, monkeypatch):
        appele = []
        monkeypatch.setattr(gen, "bonhomme_neige", lambda d: appele.append(True))
        gen.generer("neige", False)
        assert appele

    def test_pas_de_bonhomme_hors_neige(self, monkeypatch):
        appele = []
        monkeypatch.setattr(gen, "bonhomme_neige", lambda d: appele.append(True))
        gen.generer("soleil", False)
        assert not appele

    def test_nuit_orageuse_sans_lune(self, monkeypatch):
        appele = []
        monkeypatch.setattr(gen, "lune", lambda *a: appele.append(True))
        gen.generer("orage", True)
        assert not appele

    def test_nuit_claire_avec_lune(self, monkeypatch):
        appele = []
        monkeypatch.setattr(gen, "lune", lambda *a: appele.append(True))
        gen.generer("soleil", True)
        assert appele

    @pytest.mark.parametrize("meteo,attendu", [("soleil", 45), ("nuageux", 15), ("neige", 15)])
    def test_etoiles_selon_la_meteo(self, monkeypatch, meteo, attendu):
        vus = []
        monkeypatch.setattr(gen, "etoiles", lambda d, rng, n: vus.append(n))
        gen.generer(meteo, True)
        assert vus == [attendu]

    @pytest.mark.parametrize("meteo", ["pluie", "orage", "brouillard"])
    def test_pas_d_etoiles_par_temps_couvert(self, monkeypatch, meteo):
        vus = []
        monkeypatch.setattr(gen, "etoiles", lambda *a, **k: vus.append(1))
        gen.generer(meteo, True)
        assert not vus

    def test_orage_ecrit_krakoom(self, monkeypatch):
        messages = []
        vrai = gen.texte
        monkeypatch.setattr(gen, "texte", lambda d, xy, msg, *a, **k: (messages.append(msg), vrai(d, xy, msg, *a, **k)))
        gen.generer("orage", False)
        assert "KRAKOOOM !!" in messages


# ---------------------------------------------------------------- main

class TestMain:
    @pytest.fixture(autouse=True)
    def generation_rapide(self, monkeypatch):
        """Remplace generer par une image minuscule : on teste le câblage, pas le dessin."""
        monkeypatch.setattr(gen, "generer", lambda meteo, nuit: Image.new("RGB", (4, 4), gen.ROUGE))

    def lancer(self, monkeypatch, *args):
        monkeypatch.setattr(sys, "argv", ["gen_wallpapers.py", *args])
        gen.main()

    def test_cree_les_douze_images_et_le_defaut(self, monkeypatch, tmp_path):
        self.lancer(monkeypatch, str(tmp_path))
        noms = {p.name for p in tmp_path.iterdir()}
        attendus = {f"{m}-{j}.png" for m in gen.METEOS for j in ("jour", "nuit")} | {"defaut.png"}
        assert noms == attendus

    def test_defaut_est_une_copie_de_soleil_jour(self, monkeypatch, tmp_path):
        self.lancer(monkeypatch, str(tmp_path))
        assert (tmp_path / "defaut.png").read_bytes() == (tmp_path / "soleil-jour.png").read_bytes()

    def test_cree_le_dossier_de_sortie(self, monkeypatch, tmp_path):
        cible = tmp_path / "a" / "b"
        self.lancer(monkeypatch, str(cible))
        assert cible.is_dir()

    def test_taille_par_defaut_pas_de_redimensionnement(self, monkeypatch, tmp_path):
        self.lancer(monkeypatch, str(tmp_path))
        assert Image.open(tmp_path / "pluie-jour.png").size == (4, 4)

    def test_redimensionne_si_resolution_differente(self, monkeypatch, tmp_path):
        self.lancer(monkeypatch, str(tmp_path), "--largeur", "8", "--hauteur", "6")
        assert Image.open(tmp_path / "pluie-jour.png").size == (8, 6)

    def test_affiche_les_chemins(self, monkeypatch, tmp_path, capsys):
        self.lancer(monkeypatch, str(tmp_path))
        sortie = capsys.readouterr().out.splitlines()
        assert len(sortie) == 12
        assert str(tmp_path / "soleil-jour.png") in sortie

    def test_dossier_par_defaut_dans_images_du_home(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        self.lancer(monkeypatch)
        assert (tmp_path / "Images/paint-weather/defaut.png").exists()

    def test_tilde_developpe(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        self.lancer(monkeypatch, "~/out")
        assert (tmp_path / "out/defaut.png").exists()

    def test_option_inconnue_quitte(self, monkeypatch, tmp_path):
        with pytest.raises(SystemExit):
            self.lancer(monkeypatch, str(tmp_path), "--bidule")


class TestPointDEntree:
    def test_execute_main_quand_lance_comme_script(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "argv", ["gen_wallpapers.py", str(tmp_path), "--largeur", "16", "--hauteur", "9"])
        runpy.run_path(str(Path(gen.__file__)), run_name="__main__")
        assert Image.open(tmp_path / "defaut.png").size == (16, 9)
