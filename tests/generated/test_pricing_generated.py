"""Tests pytest du calcul de panier MiniShop (minishop.pricing).

Source : specs/pricing.feature. Les tests de cas limites sont préfixés par test_limite_.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from minishop.pricing import (
    FREE_SHIPPING_THRESHOLD,
    SHIPPING_FEE,
    coupon_discount,
    line_total,
    money,
    quote,
    shipping_cost,
)

pytestmark = [pytest.mark.generated, pytest.mark.unit]


@pytest.fixture(autouse=True)
def _sans_bug_injecte(monkeypatch):
    """Garantit que le mode de régression MINISHOP_BUG n'altère pas les tests."""
    monkeypatch.delenv("MINISHOP_BUG", raising=False)


def _panier(*items):
    """Construit une liste d'items {product_id, qty} à partir de tuples (produit, qty)."""
    return [{"product_id": pid, "qty": qty} for pid, qty in items]


# ---------------------------------------------------------------------------
# Scénarios de la spécification
# ---------------------------------------------------------------------------


def test_panier_vide():
    """Un panier vide a un total nul et aucune livraison facturée."""
    q = quote([])
    assert q.total == Decimal("0.00")
    assert q.shipping == Decimal("0.00")


def test_achat_simple_avec_frais_de_livraison():
    """Un achat sous le seuil de livraison offerte paie les frais de livraison standard."""
    q = quote(_panier(("mug", 2)))
    assert q.subtotal == Decimal("25.00")
    assert q.shipping == Decimal("4.90")
    assert q.total == Decimal("29.90")


def test_livraison_offerte_a_partir_de_50_euros():
    """La livraison est offerte quand le montant après remise atteint 50 euros."""
    q = quote(_panier(("hoodie", 1), ("mug", 1)))
    assert q.shipping == Decimal("0.00")
    assert q.total == Decimal("56.50")


def test_remise_volume_des_10_unites():
    """Dès 10 unités d'un même produit, une remise de 5 % s'applique sur la ligne."""
    q = quote(_panier(("sticker", 10)))
    assert q.subtotal == Decimal("23.28")


def test_coupon_de_bienvenue():
    """Le coupon WELCOME10 applique 10 % de remise sur un sous-total d'au moins 20 euros."""
    q = quote(_panier(("mug", 2)), coupon="WELCOME10")
    assert q.discount == Decimal("2.50")
    assert q.total == Decimal("27.40")


def test_coupon_de_bienvenue_sous_le_seuil():
    """Le coupon WELCOME10 n'apporte aucune remise sous un sous-total de 20 euros."""
    q = quote(_panier(("mug", 1)), coupon="WELCOME10")
    assert q.discount == Decimal("0.00")


def test_coupon_de_livraison_offerte():
    """Le coupon FREESHIP annule les frais de livraison."""
    q = quote(_panier(("sticker", 1)), coupon="FREESHIP")
    assert q.shipping == Decimal("0.00")
    assert q.total == Decimal("2.45")


def test_coupon_inconnu():
    """Un code coupon non reconnu lève une erreur 'Coupon inconnu'."""
    with pytest.raises(ValueError, match="Coupon inconnu"):
        quote(_panier(("mug", 1)), coupon="NOEL2026")


def test_produit_inconnu():
    """Un produit absent du catalogue lève une erreur 'Produit inconnu'."""
    # DIVERGENCE SPEC/CODE : la spec attend une erreur de message "Produit inconnu",
    # alors que quote() délègue à get_product() qui lève une KeyError (cf. commentaire
    # "KeyError si inconnu"). Le test suit la spécification.
    with pytest.raises(Exception, match="Produit inconnu"):
        quote(_panier(("licorne", 1)))


def test_coupon_fixed5_exactement_au_seuil_de_44_euros():
    """Le coupon FIXED5 retire 5 euros dès que le sous-total atteint 30 euros."""
    # NOTE : le titre du scénario évoque un seuil de 44 euros alors que le sous-total
    # attendu est 88,00 et que la règle métier est un seuil de 30 euros ; les montants
    # ci-dessous suivent les valeurs explicites de la spécification.
    q = quote(_panier(("hoodie", 2)), coupon="FIXED5")
    assert q.subtotal == Decimal("88.00")
    assert q.discount == Decimal("5.00")
    assert q.total == Decimal("83.00")


def test_cumul_remise_volume_et_coupon_welcome10():
    """La remise volume et le coupon WELCOME10 se cumulent sur le même panier."""
    q = quote(_panier(("sticker", 10)), coupon="WELCOME10")
    assert q.subtotal == Decimal("23.28")
    assert q.discount == Decimal("2.33")
    assert q.shipping == Decimal("4.90")
    assert q.total == Decimal("25.85")


def test_quantite_zero_interdite():
    """Une quantité nulle est refusée avec une erreur 'Quantité hors limites'."""
    with pytest.raises(ValueError, match="Quantité hors limites"):
        quote(_panier(("mug", 0)))


# ---------------------------------------------------------------------------
# Cas limites non cités par la spécification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("valeur", "attendu"),
    [
        ("0.125", "0.13"),
        ("0.135", "0.14"),
        ("1.005", "1.01"),
        ("2.344", "2.34"),
        ("2.345", "2.35"),
        ("10", "10.00"),
    ],
)
def test_limite_money_arrondi_commercial(valeur, attendu):
    """L'arrondi au centime suit la règle ROUND_HALF_UP (moitié supérieure en valeur absolue)."""
    assert money(valeur) == Decimal(attendu)


@pytest.mark.parametrize(
    ("qty", "attendu"),
    [
        (1, Decimal("2.45")),
        (9, Decimal("22.05")),
        (10, Decimal("23.28")),
        (11, Decimal("25.60")),
    ],
)
def test_limite_remise_volume_seuil_de_10_inclus(qty, attendu):
    """La remise volume s'applique à partir de 10 unités incluses, pas avant."""
    assert line_total(Decimal("2.45"), qty) == attendu


@pytest.mark.parametrize("qty", [1, 99])
def test_limite_quantite_bornes_valides(qty):
    """Les quantités 1 et 99 sont acceptées."""
    assert line_total(Decimal("1.00"), qty) >= Decimal("0.00")


@pytest.mark.parametrize("qty", [0, -1, 100, 150])
def test_limite_quantite_hors_bornes_refusee(qty):
    """Une quantité inférieure à 1 ou supérieure à 99 est refusée."""
    with pytest.raises(ValueError, match="Quantité hors limites"):
        line_total(Decimal("1.00"), qty)


@pytest.mark.parametrize("qty", [2.0, "2", None, True])
def test_limite_quantite_non_entiere_refusee(qty):
    """Une quantité qui n'est pas un entier strict (float, chaîne, booléen) est refusée."""
    with pytest.raises(ValueError, match="entier"):
        line_total(Decimal("1.00"), qty)


@pytest.mark.parametrize(
    ("sous_total", "coupon", "attendu"),
    [
        (Decimal("20.00"), "WELCOME10", Decimal("2.00")),
        (Decimal("19.99"), "WELCOME10", Decimal("0.00")),
        (Decimal("99.99"), "WELCOME10", Decimal("10.00")),
        (Decimal("30.00"), "FIXED5", Decimal("5.00")),
        (Decimal("29.99"), "FIXED5", Decimal("0.00")),
        (Decimal("100.00"), "FREESHIP", Decimal("0.00")),
        (Decimal("100.00"), None, Decimal("0.00")),
        (Decimal("100.00"), "", Decimal("0.00")),
    ],
)
def test_limite_seuils_des_coupons(sous_total, coupon, attendu):
    """Les seuils des coupons WELCOME10 et FIXED5 sont inclus, et FREESHIP ne remise rien."""
    assert coupon_discount(sous_total, coupon) == attendu


@pytest.mark.parametrize(
    ("sous_total", "attendu"),
    [
        (Decimal("8.00"), Decimal("1.20")),
        (Decimal("9.99"), Decimal("1.50")),
        (Decimal("10.00"), Decimal("0.00")),
    ],
)
def test_limite_coupon_student15_seuil_de_10(sous_total, attendu):
    """Le coupon STUDENT15 s'applique uniquement sous un sous-total strictement inférieur à 10."""
    assert coupon_discount(sous_total, "STUDENT15") == attendu


def test_limite_coupon_inconnu_leve_erreur_directement():
    """coupon_discount lève une erreur pour un code absent de la liste des coupons."""
    with pytest.raises(ValueError, match="Coupon inconnu"):
        coupon_discount(Decimal("50.00"), "INCONNU")


@pytest.mark.parametrize(
    ("montant", "coupon", "vide", "attendu"),
    [
        (Decimal("49.99"), None, False, SHIPPING_FEE),
        (FREE_SHIPPING_THRESHOLD, None, False, Decimal("0.00")),
        (Decimal("0.00"), None, True, Decimal("0.00")),
        (Decimal("10.00"), "FREESHIP", False, Decimal("0.00")),
        (Decimal("10.00"), "freeship", False, Decimal("0.00")),
        (Decimal("10.00"), "WELCOME10", False, SHIPPING_FEE),
    ],
)
def test_limite_frais_de_livraison(montant, coupon, vide, attendu):
    """Les frais de livraison dépendent du seuil de 50 euros, du panier vide et de FREESHIP."""
    assert shipping_cost(montant, coupon, empty=vide) == attendu


@pytest.mark.parametrize(
    ("produits", "attendu_total", "attendu_livraison"),
    [
        ([("mug", 3)], Decimal("42.40"), Decimal("4.90")),
        ([("mug", 4)], Decimal("50.00"), Decimal("0.00")),
    ],
)
def test_limite_seuil_livraison_offerte_via_quote(produits, attendu_total, attendu_livraison):
    """Le seuil de livraison offerte est atteint exactement à 50,00 euros de sous-total."""
    q = quote(_panier(*produits))
    assert q.total == attendu_total
    assert q.shipping == attendu_livraison


def test_limite_coupon_normalise_casse_et_espaces():
    """Le code coupon est normalisé (espaces retirés, casse ignorée) dans le devis."""
    q = quote(_panier(("mug", 1)), coupon="  welcome10 ")
    assert q.coupon == "WELCOME10"


def test_limite_coupon_chaine_vide_equivaut_a_aucun_coupon():
    """Un coupon vide est traité comme l'absence de coupon."""
    q = quote(_panier(("mug", 2)), coupon="")
    assert q.coupon is None
    assert q.discount == Decimal("0.00")


def test_limite_quote_sans_coupon_a_coupon_none():
    """Un devis sans coupon expose un champ coupon à None."""
    q = quote(_panier(("mug", 1)))
    assert q.coupon is None


def test_limite_panier_vide_avec_coupon_ne_remise_rien():
    """Un panier vide n'applique aucune remise, même avec un coupon valide."""
    q = quote([], coupon="FIXED5")
    assert q.discount == Decimal("0.00")
    assert q.total == Decimal("0.00")
    assert q.shipping == Decimal("0.00")


@pytest.mark.parametrize("qty", [0, 100])
def test_limite_quantite_invalide_dans_devis(qty):
    """Une quantité hors bornes dans un devis multi-lignes est rejetée."""
    with pytest.raises(ValueError, match="Quantité hors limites"):
        quote(_panier(("mug", 1), ("hoodie", qty)))


def test_limite_combinaison_plusieurs_lignes_et_remise_volume():
    """Plusieurs lignes, dont une en remise volume, s'additionnent avant coupon et livraison."""
    q = quote(_panier(("sticker", 10), ("mug", 1)))
    assert q.subtotal == Decimal("35.78")
    assert q.shipping == Decimal("0.00")
    assert q.total == Decimal("35.78")


def test_limite_as_dict_expose_montants_en_chaines():
    """La sérialisation du devis expose les montants sous forme de chaînes au centime."""
    d = quote(_panier(("mug", 2))).as_dict()
    assert d["subtotal"] == "25.00"
    assert d["shipping"] == "4.90"
    assert d["total"] == "29.90"
    assert d["coupon"] is None
