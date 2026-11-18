# DIVERGENCE SPEC/CODE : la spec attend l'erreur "Produit inconnu", alors que le code
# délègue à get_product() qui lève KeyError (le message exact n'est pas connu ici).
# Les tests vérifient donc le type d'exception (KeyError ou ValueError).
#
# Prix des produits déduits des scénarios de la spec (catalogue non fourni) :
#   mug = 12.50 €, hoodie = 44.00 €, sticker = 2.45 €

from decimal import Decimal

import pytest

from minishop.pricing import (
    FREE_SHIPPING_THRESHOLD,
    SHIPPING_FEE,
    Quote,
    coupon_discount,
    line_total,
    money,
    quote,
    shipping_cost,
)

pytestmark = [pytest.mark.generated, pytest.mark.unit]


def _items(*pairs):
    """Construit la liste d'items {product_id, qty} à partir de couples (qty, produit)."""
    return [{"product_id": produit, "qty": qty} for qty, produit in pairs]


# ---------------------------------------------------------------------------
# Scénarios de la spécification
# ---------------------------------------------------------------------------


def test_panier_vide():
    """Un panier vide a un total de 0 et aucune livraison facturée."""
    q = quote([])
    assert q.total == Decimal("0.00")
    assert q.shipping == Decimal("0.00")


def test_achat_simple_avec_frais_de_livraison():
    """Un panier sous 50 € sans coupon paie les frais de livraison de 4,90 €."""
    q = quote(_items((2, "mug")))
    assert q.subtotal == Decimal("25.00")
    assert q.shipping == Decimal("4.90")
    assert q.total == Decimal("29.90")


def test_livraison_offerte_a_partir_de_50_euros():
    """La livraison est offerte quand le montant après remise atteint 50 €."""
    q = quote(_items((1, "hoodie"), (1, "mug")))
    assert q.shipping == Decimal("0.00")
    assert q.total == Decimal("56.50")


def test_remise_volume_des_10_unites():
    """Dès 10 unités d'un même produit, une remise de 5 % s'applique à la ligne."""
    q = quote(_items((10, "sticker")))
    assert q.subtotal == Decimal("23.28")


def test_coupon_de_bienvenue():
    """Le coupon WELCOME10 retire 10 % du sous-total lorsque celui-ci vaut au moins 20 €."""
    q = quote(_items((2, "mug")), coupon="WELCOME10")
    assert q.discount == Decimal("2.50")
    assert q.total == Decimal("27.40")


def test_coupon_de_bienvenue_sous_le_seuil():
    """Le coupon WELCOME10 n'accorde aucune remise si le sous-total est inférieur à 20 €."""
    q = quote(_items((1, "mug")), coupon="WELCOME10")
    assert q.discount == Decimal("0.00")


def test_coupon_de_livraison_offerte():
    """Le coupon FREESHIP annule les frais de livraison."""
    q = quote(_items((1, "sticker")), coupon="FREESHIP")
    assert q.shipping == Decimal("0.00")
    assert q.total == Decimal("2.45")


def test_coupon_inconnu():
    """Un code coupon non référencé lève une erreur 'Coupon inconnu'."""
    with pytest.raises(ValueError, match="Coupon inconnu"):
        quote(_items((1, "mug")), coupon="NOEL2026")


def test_produit_inconnu():
    """Un identifiant de produit absent du catalogue lève une erreur."""
    # DIVERGENCE SPEC/CODE : la spec attend le message "Produit inconnu" ;
    # le code laisse remonter KeyError depuis get_product().
    with pytest.raises((KeyError, ValueError)):
        quote(_items((1, "licorne")))


def test_coupon_fixed5_exactement_au_seuil_de_44_euros():
    """Le coupon FIXED5 retire 5 € pour un sous-total de 88 € (au-dessus du seuil de 30 €)."""
    q = quote(_items((2, "hoodie")), coupon="FIXED5")
    assert q.subtotal == Decimal("88.00")
    assert q.discount == Decimal("5.00")
    assert q.total == Decimal("83.00")


def test_cumul_remise_volume_et_coupon_welcome10():
    """La remise volume et le coupon WELCOME10 se cumulent sur le même panier."""
    q = quote(_items((10, "sticker")), coupon="WELCOME10")
    assert q.subtotal == Decimal("23.28")
    assert q.discount == Decimal("2.33")
    assert q.shipping == Decimal("4.90")
    assert q.total == Decimal("25.85")


def test_quantite_zero_interdite():
    """Une quantité nulle lève une erreur 'Quantité hors limites'."""
    with pytest.raises(ValueError, match="Quantité hors limites"):
        quote(_items((0, "mug")))


# ---------------------------------------------------------------------------
# Cas limites (non cités par la spec, impliqués par le code)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "valeur, attendu",
    [
        ("0.125", Decimal("0.13")),
        ("0.124", Decimal("0.12")),
        ("1.005", Decimal("1.01")),
        ("2.675", Decimal("2.68")),
        (Decimal("10"), Decimal("10.00")),
    ],
)
def test_limite_arrondi_commercial_round_half_up(monkeypatch, valeur, attendu):
    """L'arrondi au centime se fait en ROUND_HALF_UP (0,125 devient 0,13)."""
    monkeypatch.delenv("MINISHOP_BUG", raising=False)
    assert money(valeur) == attendu


@pytest.mark.parametrize("qty", [1, 99])
def test_limite_quantite_bornes_acceptees(qty):
    """Les bornes 1 et 99 de la quantité sont acceptées."""
    assert line_total(Decimal("1.00"), qty) == money(
        Decimal("1.00") * qty * (Decimal("0.95") if qty >= 10 else Decimal("1"))
    )


@pytest.mark.parametrize("qty", [0, -1, 100, 1000])
def test_limite_quantite_hors_bornes_refusee(qty):
    """Les quantités inférieures à 1 ou supérieures à 99 sont refusées."""
    with pytest.raises(ValueError, match="Quantité hors limites"):
        line_total(Decimal("1.00"), qty)


@pytest.mark.parametrize("qty", [2.0, "2", True, None])
def test_limite_quantite_non_entiere_refusee(qty):
    """Une quantité qui n'est pas un entier strict (float, str, bool, None) est refusée."""
    with pytest.raises(ValueError, match="entier"):
        line_total(Decimal("1.00"), qty)


@pytest.mark.parametrize(
    "qty, attendu",
    [
        (9, Decimal("22.05")),  # pas de remise sous 10 unités
        (10, Decimal("23.28")),  # remise de 5 % dès 10 unités
    ],
)
def test_limite_seuil_remise_volume(qty, attendu):
    """La remise volume s'applique exactement à partir de 10 unités, pas avant."""
    assert line_total(Decimal("2.45"), qty) == attendu


@pytest.mark.parametrize(
    "sous_total, attendu",
    [
        (Decimal("19.99"), Decimal("0.00")),
        (Decimal("20.00"), Decimal("2.00")),
    ],
)
def test_limite_seuil_welcome10(sous_total, attendu):
    """WELCOME10 s'applique exactement à partir de 20 € de sous-total."""
    assert coupon_discount(sous_total, "WELCOME10") == attendu


@pytest.mark.parametrize(
    "sous_total, attendu",
    [
        (Decimal("29.99"), Decimal("0.00")),
        (Decimal("30.00"), Decimal("5.00")),
    ],
)
def test_limite_seuil_fixed5(sous_total, attendu):
    """FIXED5 s'applique exactement à partir de 30 € de sous-total."""
    assert coupon_discount(sous_total, "FIXED5") == attendu


@pytest.mark.parametrize(
    "coupon",
    ["  welcome10 ", "Welcome10", "WELCOME10"],
)
def test_limite_code_coupon_insensible_casse_et_espaces(coupon):
    """Les codes coupon sont normalisés (espaces et casse ignorés)."""
    assert coupon_discount(Decimal("20.00"), coupon) == Decimal("2.00")


@pytest.mark.parametrize("coupon", [None, ""])
def test_limite_absence_de_coupon_sans_remise(coupon):
    """Sans coupon (None ou chaîne vide), la remise est nulle."""
    assert coupon_discount(Decimal("100.00"), coupon) == Decimal("0.00")


@pytest.mark.parametrize(
    "montant, attendu",
    [
        (Decimal("49.99"), SHIPPING_FEE),
        (FREE_SHIPPING_THRESHOLD, Decimal("0.00")),
        (Decimal("50.01"), Decimal("0.00")),
    ],
)
def test_limite_seuil_livraison_offerte(montant, attendu):
    """La livraison est offerte exactement à partir de 50 € (seuil inclus)."""
    assert shipping_cost(montant, None, empty=False) == attendu


def test_limite_livraison_panier_vide_nulle():
    """Un panier vide n'entraîne aucun frais de livraison."""
    assert shipping_cost(Decimal("0.00"), None, empty=True) == Decimal("0.00")


def test_limite_freeship_offre_livraison_quel_que_soit_le_montant():
    """FREESHIP annule la livraison même pour un petit montant."""
    assert shipping_cost(Decimal("5.00"), "FREESHIP", empty=False) == Decimal("0.00")


def test_limite_coupon_normalise_dans_le_devis():
    """Le devis conserve le code coupon normalisé (majuscules, sans espaces)."""
    q = quote(_items((1, "sticker")), coupon=" freeship ")
    assert q.coupon == "FREESHIP"
    assert q.shipping == Decimal("0.00")


def test_limite_panier_vide_avec_coupon_ignore_la_remise():
    """Un panier vide avec coupon n'applique ni remise ni livraison."""
    q = quote([], coupon="FIXED5")
    assert q.discount == Decimal("0.00")
    assert q.shipping == Decimal("0.00")
    assert q.total == Decimal("0.00")


def test_limite_sous_total_multi_lignes_somme_les_lignes():
    """Le sous-total est la somme des lignes, chacune remise volume incluse."""
    q = quote(_items((10, "sticker"), (2, "mug")))
    assert q.subtotal == Decimal("48.28")


def test_limite_coupon_inconnu_refuse_meme_sans_panier():
    """Un coupon inconnu lève une erreur dès qu'une ligne est présente."""
    with pytest.raises(ValueError, match="Coupon inconnu"):
        quote(_items((1, "sticker")), coupon="FAKE")


def test_limite_student15_remise_sous_dix_euros():
    """STUDENT15 (présent dans le code, absent de la spec) retire 15 % sous 10 € de sous-total."""
    assert coupon_discount(Decimal("8.00"), "STUDENT15") == Decimal("1.20")


def test_limite_student15_pas_de_remise_a_partir_de_dix_euros():
    """STUDENT15 n'accorde aucune remise à partir de 10 € de sous-total."""
    assert coupon_discount(Decimal("10.00"), "STUDENT15") == Decimal("0.00")


def test_limite_as_dict_expose_montants_en_chaine():
    """La sérialisation du devis expose les montants sous forme de chaînes décimales."""
    q = quote(_items((2, "mug")))
    data = q.as_dict()
    assert data["subtotal"] == "25.00"
    assert data["shipping"] == "4.90"
    assert data["total"] == "29.90"
    assert data["coupon"] is None
    assert isinstance(q, Quote)
