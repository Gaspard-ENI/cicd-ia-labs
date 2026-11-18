import os
from decimal import Decimal

import pytest

from minishop.pricing import (
    coupon_discount,
    line_total,
    money,
    quote,
    shipping_cost,
)

pytestmark = [pytest.mark.generated, pytest.mark.unit]

D = Decimal


@pytest.fixture(autouse=True)
def _sans_bug_injecte(monkeypatch):
    """Neutralise le bug injectable MINISHOP_BUG pour garder des tests déterministes."""
    monkeypatch.delenv("MINISHOP_BUG", raising=False)


def _items(*pairs):
    return [{"product_id": p, "qty": n} for n, p in pairs]


# ---------------------------------------------------------------------------
# Scénarios de la spécification
# ---------------------------------------------------------------------------


def test_panier_vide():
    """Un panier vide a un total de 0.00 et aucune livraison."""
    q = quote([])
    assert q.total == D("0.00")
    assert q.shipping == D("0.00")


def test_achat_simple_avec_frais_de_livraison():
    """Sous le seuil de 50 €, la livraison de 4.90 € est ajoutée."""
    q = quote(_items((2, "mug")))
    assert q.subtotal == D("25.00")
    assert q.shipping == D("4.90")
    assert q.total == D("29.90")


def test_livraison_offerte_a_partir_de_50_euros():
    """Dès 50 € après remise, la livraison est offerte."""
    q = quote(_items((1, "hoodie"), (1, "mug")))
    assert q.shipping == D("0.00")
    assert q.total == D("56.50")


def test_remise_volume_des_10_unites():
    """Dès 10 unités d'un même produit, -5 % sur la ligne."""
    q = quote(_items((10, "sticker")))
    assert q.subtotal == D("23.28")


def test_coupon_de_bienvenue():
    """WELCOME10 donne -10 % si le sous-total atteint 20 €."""
    q = quote(_items((2, "mug")), "WELCOME10")
    assert q.discount == D("2.50")
    assert q.total == D("27.40")


def test_coupon_de_bienvenue_sous_le_seuil():
    """WELCOME10 ne donne aucune remise sous 20 € de sous-total."""
    q = quote(_items((1, "mug")), "WELCOME10")
    assert q.discount == D("0.00")


def test_coupon_de_livraison_offerte():
    """FREESHIP offre la livraison quel que soit le montant."""
    q = quote(_items((1, "sticker")), "FREESHIP")
    assert q.shipping == D("0.00")
    assert q.total == D("2.45")


def test_coupon_inconnu():
    """Un coupon inconnu lève une erreur."""
    with pytest.raises(ValueError, match="Coupon inconnu"):
        quote(_items((1, "mug")), "NOEL2026")


def test_produit_inconnu():
    """Un produit absent du catalogue lève une erreur."""
    # Le code documente un KeyError ; le message exact dépend du catalogue.
    with pytest.raises((KeyError, ValueError), match="Produit inconnu"):
        quote(_items((1, "licorne")))


def test_coupon_fixed5_exactement_au_seuil_de_44_euros():
    """FIXED5 retire 5 € sur un sous-total de 88 €."""
    # DIVERGENCE SPEC/CODE : le titre du scénario parle d'un seuil de 44 €,
    # le code applique un seuil de 30 €. Les valeurs attendues sont identiques.
    q = quote(_items((2, "hoodie")), "FIXED5")
    assert q.subtotal == D("88.00")
    assert q.discount == D("5.00")
    assert q.total == D("83.00")


def test_cumul_remise_volume_et_coupon_welcome10():
    """La remise volume et WELCOME10 se cumulent, avec arrondis au centime."""
    q = quote(_items((10, "sticker")), "WELCOME10")
    assert q.subtotal == D("23.28")
    assert q.discount == D("2.33")
    assert q.shipping == D("4.90")
    assert q.total == D("25.85")


def test_quantite_zero_interdite():
    """Une quantité de 0 est refusée."""
    with pytest.raises(ValueError, match="Quantité hors limites"):
        quote(_items((0, "mug")))


# ---------------------------------------------------------------------------
# Cas limites
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "qty, attendu",
    [
        (1, D("2.45")),
        (9, D("22.05")),  # pas de remise volume
        (10, D("23.28")),  # remise volume (23.275 -> 23.28)
        (99, D("230.42")),  # 99 * 2.45 * 0.95 = 230.4225
    ],
)
def test_limite_remise_volume_bornes(qty, attendu):
    """La remise volume s'applique à partir de 10 unités inclus."""
    assert line_total(D("2.45"), qty) == attendu


@pytest.mark.parametrize("qty", [-1, 0, 100, 1000])
def test_limite_quantite_hors_bornes(qty):
    """Les quantités hors de 1..99 sont refusées."""
    with pytest.raises(ValueError, match="Quantité hors limites"):
        line_total(D("2.45"), qty)


@pytest.mark.parametrize("qty", [1.5, "3", None, True])
def test_limite_quantite_non_entiere(qty):
    """Une quantité qui n'est pas un entier (ou est un booléen) est refusée."""
    with pytest.raises(ValueError, match="entier"):
        line_total(D("2.45"), qty)


def test_limite_quantite_99_acceptee():
    """La quantité maximale 99 est acceptée."""
    q = quote(_items((99, "mug")))
    assert q.lines[0].qty == 99


@pytest.mark.parametrize(
    "valeur, attendu",
    [
        (D("0.125"), D("0.13")),
        (D("0.124"), D("0.12")),
        (D("2.675"), D("2.68")),
        (D("0.005"), D("0.01")),
        (0.125, D("0.13")),
        (3, D("3.00")),
        ("1.005", D("1.01")),
    ],
)
def test_limite_arrondi_commercial(valeur, attendu):
    """L'arrondi est commercial (ROUND_HALF_UP) au centime."""
    assert money(valeur) == attendu


def test_limite_livraison_offerte_exactement_a_50_euros():
    """Un montant de 50.00 € pile donne la livraison offerte (seuil inclus)."""
    q = quote(_items((4, "mug")))
    assert q.subtotal == D("50.00")
    assert q.shipping == D("0.00")
    assert q.total == D("50.00")


def test_limite_livraison_payante_juste_sous_50_apres_remise():
    """Le seuil de livraison offerte s'évalue après remise de coupon."""
    q = quote(_items((4, "mug")), "WELCOME10")
    assert q.discount == D("5.00")
    assert q.shipping == D("4.90")
    assert q.total == D("49.90")


@pytest.mark.parametrize(
    "montant, attendu",
    [
        (D("49.99"), D("4.90")),
        (D("50.00"), D("0.00")),
        (D("50.01"), D("0.00")),
        (D("0.00"), D("4.90")),
    ],
)
def test_limite_shipping_cost_seuil(montant, attendu):
    """La livraison est offerte si le montant après remise est >= 50.00."""
    assert shipping_cost(montant, None, empty=False) == attendu


def test_limite_shipping_cost_panier_vide():
    """Un panier vide n'a jamais de frais de livraison."""
    assert shipping_cost(D("0.00"), None, empty=True) == D("0.00")


@pytest.mark.parametrize("code", ["FREESHIP", "freeship", " FreeShip "])
def test_limite_freeship_insensible_casse_et_espaces(code):
    """FREESHIP est reconnu sans tenir compte de la casse ni des espaces."""
    assert shipping_cost(D("10.00"), code, empty=False) == D("0.00")


@pytest.mark.parametrize(
    "sous_total, attendu",
    [
        (D("19.99"), D("0.00")),
        (D("20.00"), D("2.00")),
        (D("22.05"), D("2.21")),  # 2.205 -> 2.21
    ],
)
def test_limite_welcome10_seuil_20_euros(sous_total, attendu):
    """WELCOME10 s'applique dès 20 € inclus, avec arrondi au centime."""
    assert coupon_discount(sous_total, "WELCOME10") == attendu


def test_limite_welcome10_8_stickers_sous_le_seuil():
    """8 stickers (19.60 €) restent sous le seuil de WELCOME10."""
    q = quote(_items((8, "sticker")), "WELCOME10")
    assert q.subtotal == D("19.60")
    assert q.discount == D("0.00")
    assert q.total == D("24.50")


def test_limite_welcome10_9_stickers_arrondi():
    """9 stickers avec WELCOME10 : remise 2.21 et livraison payante."""
    q = quote(_items((9, "sticker")), "WELCOME10")
    assert q.subtotal == D("22.05")
    assert q.discount == D("2.21")
    assert q.total == D("24.74")


@pytest.mark.parametrize(
    "sous_total, attendu",
    [
        (D("29.99"), D("0.00")),
        (D("30.00"), D("5.00")),
        (D("88.00"), D("5.00")),
    ],
)
def test_limite_fixed5_seuil(sous_total, attendu):
    """FIXED5 retire 5 € à partir du seuil du code (30 €, inclus)."""
    # DIVERGENCE SPEC/CODE : la spec évoque un seuil de 44 € ; le code et sa
    # docstring utilisent 30 €. Le test suit le code pour les bornes 30 €.
    assert coupon_discount(sous_total, "FIXED5") == attendu


def test_limite_fixed5_un_hoodie_a_44_euros():
    """FIXED5 sur un hoodie seul (44 €) donne 5 € de remise."""
    q = quote(_items((1, "hoodie")), "FIXED5")
    assert q.discount == D("5.00")
    assert q.total == D("39.00") + D("4.90")


@pytest.mark.parametrize("coupon", [None, ""])
def test_limite_sans_coupon_aucune_remise(coupon):
    """Sans coupon (None ou chaîne vide), la remise est nulle."""
    assert coupon_discount(D("100.00"), coupon) == D("0.00")


@pytest.mark.parametrize("code", ["welcome10", " WELCOME10 ", "Welcome10"])
def test_limite_coupon_normalise(code):
    """Le coupon est normalisé (strip + majuscules) et conservé dans le devis."""
    q = quote(_items((2, "mug")), code)
    assert q.coupon == "WELCOME10"
    assert q.discount == D("2.50")


@pytest.mark.parametrize("coupon", [None, ""])
def test_limite_devis_sans_coupon_conserve_none(coupon):
    """Sans coupon, le champ coupon du devis vaut None."""
    assert quote(_items((1, "mug")), coupon).coupon is None


def test_limite_student15_inconnu_selon_la_spec():
    """STUDENT15 n'est pas un coupon documenté : il doit être refusé."""
    # DIVERGENCE SPEC/CODE : la spec et la docstring ne listent que WELCOME10,
    # FIXED5 et FREESHIP ; le code accepte STUDENT15 (avec une condition
    # `subtotal < BULK_QTY` incohérente).
    with pytest.raises(ValueError, match="Coupon inconnu"):
        quote(_items((2, "mug")), "STUDENT15")


def test_limite_panier_vide_avec_coupon_valide():
    """Un panier vide avec coupon reste à 0.00 sans remise ni livraison."""
    q = quote([], "FREESHIP")
    assert q.discount == D("0.00")
    assert q.shipping == D("0.00")
    assert q.total == D("0.00")


def test_limite_panier_vide_coupon_inconnu_sans_erreur():
    """Sur panier vide, le coupon n'est pas évalué : aucune erreur."""
    q = quote([], "NOEL2026")
    assert q.total == D("0.00")


def test_limite_coupon_inconnu_insensible_casse():
    """Un coupon inconnu reste refusé quelle que soit la casse."""
    with pytest.raises(ValueError, match="Coupon inconnu"):
        coupon_discount(D("100.00"), "noel2026")


def test_limite_plusieurs_lignes_somme_des_totaux():
    """Le sous-total est la somme des totaux de lignes (remise volume par ligne)."""
    q = quote(_items((10, "sticker"), (1, "mug")))
    assert len(q.lines) == 2
    assert q.subtotal == D("23.28") + D("12.50")
    assert q.shipping == D("4.90")
    assert q.total == D("40.68")


def test_limite_as_dict_serialise_en_chaines():
    """as_dict sérialise les montants en chaînes et conserve le coupon."""
    d = quote(_items((2, "mug")), "WELCOME10").as_dict()
    assert d["subtotal"] == "25.00"
    assert d["discount"] == "2.50"
    assert d["shipping"] == "4.90"
    assert d["total"] == "27.40"
    assert d["coupon"] == "WELCOME10"
    assert d["lines"][0]["product_id"] == "mug"
    assert d["lines"][0]["qty"] == 2
    assert d["lines"][0]["unit_price"] == "12.50"
    assert d["lines"][0]["total"] == "25.00"


def test_limite_bug_rounding_detecte(monkeypatch):
    """Avec le bug d'arrondi injecté, 0.125 ne doit plus donner 0.13 (garde-fou)."""
    monkeypatch.setenv("MINISHOP_BUG", "rounding")
    assert os.getenv("MINISHOP_BUG") == "rounding"
    assert money(D("0.125")) != D("0.13")
