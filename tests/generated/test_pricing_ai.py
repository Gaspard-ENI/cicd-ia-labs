from decimal import Decimal
from types import SimpleNamespace

import pytest

from minishop import pricing
from minishop.pricing import line_total, money, quote

pytestmark = [pytest.mark.generated, pytest.mark.unit]


def _items(*pairs):
    """Construit la liste d'items {product_id, qty} attendue par quote()."""
    return [{"product_id": pid, "qty": qty} for qty, pid in pairs]


@pytest.fixture
def catalogue(monkeypatch):
    """Catalogue de test injecté dans pricing.get_product pour fixer des seuils exacts."""
    prices: dict[str, Decimal] = {}

    def fake_get_product(pid):
        if pid not in prices:
            raise KeyError(pid)
        return SimpleNamespace(id=pid, price=prices[pid])

    monkeypatch.setattr(pricing, "get_product", fake_get_product)
    return prices


# ---------------------------------------------------------------------------
# Scénarios de la spécification
# ---------------------------------------------------------------------------


def test_panier_vide():
    """Un panier vide a un total de 0 et aucuns frais de livraison."""
    q = quote([])
    assert q.subtotal == Decimal("0.00")
    assert q.total == Decimal("0.00")
    assert q.shipping == Decimal("0.00")


def test_achat_simple_avec_frais_de_livraison():
    """Un achat sous 50 € ajoute les frais de livraison de 4,90 €."""
    q = quote(_items((2, "mug")))
    assert q.subtotal == Decimal("25.00")
    assert q.shipping == Decimal("4.90")
    assert q.total == Decimal("29.90")


def test_livraison_offerte_a_partir_de_50_euros():
    """Un total après remise d'au moins 50 € offre la livraison."""
    q = quote(_items((1, "hoodie"), (1, "mug")))
    assert q.shipping == Decimal("0.00")
    assert q.total == Decimal("56.50")


def test_remise_volume_des_10_unites():
    """Dix unités d'un même produit bénéficient d'une remise volume de 5 %."""
    q = quote(_items((10, "sticker")))
    assert q.subtotal == Decimal("23.28")


def test_coupon_de_bienvenue():
    """Le coupon WELCOME10 retire 10 % du sous-total dès 20 €."""
    q = quote(_items((2, "mug")), coupon="WELCOME10")
    assert q.discount == Decimal("2.50")
    assert q.total == Decimal("27.40")


def test_coupon_de_bienvenue_sous_le_seuil():
    """Le coupon WELCOME10 n'accorde aucune remise sous le seuil de 20 €."""
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
    """Un produit absent du catalogue lève une erreur 'Produit inconnu'."""
    # DIVERGENCE SPEC/CODE : la spec exige une ValueError "Produit inconnu",
    # alors que le commentaire du code indique que get_product lève une KeyError.
    # Le test suit la spécification.
    with pytest.raises(ValueError, match="Produit inconnu"):
        quote(_items((1, "licorne")))


def test_coupon_fixed5_exactement_au_seuil_de_44_euros():
    """Le coupon FIXED5 retire 5 € sur un sous-total de 88 € (2 hoodies) et le total est correct."""
    q = quote(_items((2, "hoodie")), coupon="FIXED5")
    assert q.subtotal == Decimal("88.00")
    assert q.discount == Decimal("5.00")
    assert q.total == Decimal("83.00")


def test_cumul_remise_volume_et_coupon_welcome10():
    """La remise volume et le coupon WELCOME10 se cumulent sur le sous-total."""
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
# Cas limites (non cités par la spécification)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("0.125", "0.13"),
        ("0.135", "0.14"),
        ("0.124", "0.12"),
        ("1.005", "1.01"),
        ("10", "10.00"),
    ],
)
def test_limite_arrondi_au_centime_demi_superieur(value, expected):
    """money() arrondit au centime en ROUND_HALF_UP."""
    assert money(value) == Decimal(expected)


@pytest.mark.parametrize(
    "qty, expected",
    [
        (1, "2.00"),
        (9, "18.00"),
        (10, "19.00"),
        (99, "188.10"),
    ],
)
def test_limite_seuil_remise_volume_inclusif_a_10(qty, expected):
    """La remise volume s'applique à partir de 10 unités incluses, pas avant."""
    assert line_total(Decimal("2.00"), qty) == Decimal(expected)


@pytest.mark.parametrize("qty", [0, -1, 100, 1000])
def test_limite_quantite_hors_bornes_rejetee(qty):
    """Les quantités sous 1 ou au-dessus de 99 sont rejetées."""
    with pytest.raises(ValueError):
        line_total(Decimal("2.00"), qty)


@pytest.mark.parametrize("qty", [1, 99])
def test_limite_quantite_bornes_acceptees(qty):
    """Les bornes 1 et 99 sont des quantités valides."""
    assert line_total(Decimal("1.00"), qty) >= Decimal("0.00")


@pytest.mark.parametrize("qty", [True, False, 2.0, "2"])
def test_limite_quantite_non_entiere_rejetee(qty):
    """Une quantité non entière (booléen, float, chaîne) est rejetée."""
    with pytest.raises(ValueError):
        line_total(Decimal("2.00"), qty)


def test_limite_welcome10_exactement_au_seuil_de_20(catalogue):
    """WELCOME10 s'applique exactement à 20,00 € de sous-total."""
    catalogue["pivot"] = Decimal("20.00")
    q = quote(_items((1, "pivot")), coupon="WELCOME10")
    assert q.discount == Decimal("2.00")


def test_limite_welcome10_juste_sous_le_seuil(catalogue):
    """WELCOME10 ne s'applique pas à 19,99 € de sous-total."""
    catalogue["pivot"] = Decimal("19.99")
    q = quote(_items((1, "pivot")), coupon="WELCOME10")
    assert q.discount == Decimal("0.00")


def test_limite_fixed5_exactement_au_seuil_de_30(catalogue):
    """FIXED5 s'applique exactement à 30,00 € de sous-total."""
    catalogue["pivot"] = Decimal("30.00")
    q = quote(_items((1, "pivot")), coupon="FIXED5")
    assert q.discount == Decimal("5.00")


def test_limite_fixed5_juste_sous_le_seuil(catalogue):
    """FIXED5 ne s'applique pas à 29,99 € de sous-total."""
    catalogue["pivot"] = Decimal("29.99")
    q = quote(_items((1, "pivot")), coupon="FIXED5")
    assert q.discount == Decimal("0.00")


def test_limite_livraison_offerte_exactement_a_50(catalogue):
    """La livraison est offerte pour un total exactement égal à 50,00 €."""
    catalogue["pivot"] = Decimal("50.00")
    q = quote(_items((1, "pivot")))
    assert q.shipping == Decimal("0.00")
    assert q.total == Decimal("50.00")


def test_limite_livraison_facturee_juste_sous_50(catalogue):
    """La livraison est facturée pour un total de 49,99 €."""
    catalogue["pivot"] = Decimal("49.99")
    q = quote(_items((1, "pivot")))
    assert q.shipping == Decimal("4.90")
    assert q.total == Decimal("54.89")


def test_limite_seuil_livraison_evalue_apres_remise(catalogue):
    """Le seuil de livraison gratuite porte sur le montant après remise."""
    catalogue["pivot"] = Decimal("55.00")
    q = quote(_items((1, "pivot")), coupon="WELCOME10")
    assert q.discount == Decimal("5.50")
    assert q.shipping == Decimal("4.90")
    assert q.total == Decimal("54.40")


def test_limite_coupon_insensible_a_la_casse_et_aux_espaces(catalogue):
    """Le code coupon est normalisé (espaces et casse ignorés)."""
    catalogue["pivot"] = Decimal("20.00")
    q = quote(_items((1, "pivot")), coupon="  welcome10 ")
    assert q.coupon == "WELCOME10"
    assert q.discount == Decimal("2.00")


def test_limite_coupon_chaine_vide_equivaut_a_aucun_coupon():
    """Une chaîne vide comme coupon équivaut à l'absence de coupon."""
    q = quote(_items((2, "mug")), coupon="")
    assert q.coupon is None
    assert q.discount == Decimal("0.00")
    assert q.total == Decimal("29.90")


def test_limite_panier_vide_avec_coupon_valide():
    """Un panier vide avec un coupon valide ne génère ni remise ni livraison."""
    q = quote([], coupon="WELCOME10")
    assert q.discount == Decimal("0.00")
    assert q.shipping == Decimal("0.00")
    assert q.total == Decimal("0.00")


def test_limite_remise_volume_arrondie_au_centime():
    """La remise volume sur 10 stickers est arrondie au centime (23,275 -> 23,28)."""
    assert line_total(Decimal("2.45"), 10) == Decimal("23.28")


def test_limite_remise_welcome10_arrondie_au_centime(catalogue):
    """La remise WELCOME10 est arrondie au centime (2,328 -> 2,33)."""
    catalogue["pivot"] = Decimal("23.28")
    q = quote(_items((1, "pivot")), coupon="WELCOME10")
    assert q.discount == Decimal("2.33")
