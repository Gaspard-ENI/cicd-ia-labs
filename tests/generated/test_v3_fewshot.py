from decimal import Decimal

import pytest

from minishop.pricing import coupon_discount, line_total, money, quote, shipping_cost

pytestmark = [pytest.mark.generated, pytest.mark.unit]


# ---------------------------------------------------------------------------
# Scénarios de la spécification
# ---------------------------------------------------------------------------


def test_panier_vide():
    """Un panier vide a un total nul et aucuns frais de livraison."""
    q = quote([])
    assert q.subtotal == Decimal("0.00")
    assert q.shipping == Decimal("0.00")
    assert q.total == Decimal("0.00")


def test_achat_simple_avec_frais_de_livraison():
    """Deux mugs (25,00 €) sous le seuil de 50 € ajoutent 4,90 € de livraison."""
    q = quote([{"product_id": "mug", "qty": 2}])
    assert q.subtotal == Decimal("25.00")
    assert q.shipping == Decimal("4.90")
    assert q.total == Decimal("29.90")


def test_livraison_offerte_a_partir_de_50_euros():
    """Un hoodie et un mug (56,50 €) bénéficient de la livraison offerte."""
    q = quote(
        [
            {"product_id": "hoodie", "qty": 1},
            {"product_id": "mug", "qty": 1},
        ]
    )
    assert q.shipping == Decimal("0.00")
    assert q.total == Decimal("56.50")


def test_remise_volume_des_10_unites():
    """10 stickers déclenchent la remise volume de 5 % : sous-total 23,28 €."""
    q = quote([{"product_id": "sticker", "qty": 10}])
    assert q.subtotal == Decimal("23.28")


def test_coupon_de_bienvenue():
    """WELCOME10 applique -10 % sur 25,00 € : remise 2,50 €, total 27,40 €."""
    q = quote([{"product_id": "mug", "qty": 2}], coupon="WELCOME10")
    assert q.discount == Decimal("2.50")
    assert q.total == Decimal("27.40")


def test_coupon_de_bienvenue_sous_le_seuil():
    """WELCOME10 n'est pas appliqué sur un sous-total de 12,50 € (sous 20 €)."""
    q = quote([{"product_id": "mug", "qty": 1}], coupon="WELCOME10")
    assert q.discount == Decimal("0.00")


def test_coupon_de_livraison_offerte():
    """FREESHIP annule les frais de livraison sur un petit panier."""
    q = quote([{"product_id": "sticker", "qty": 1}], coupon="FREESHIP")
    assert q.shipping == Decimal("0.00")
    assert q.total == Decimal("2.45")


def test_coupon_inconnu():
    """Un coupon absent du référentiel lève une ValueError 'Coupon inconnu'."""
    with pytest.raises(ValueError, match="Coupon inconnu"):
        quote([{"product_id": "mug", "qty": 1}], coupon="NOEL2026")


def test_produit_inconnu():
    """Un produit absent du catalogue lève une erreur 'Produit inconnu'."""
    # DIVERGENCE SPEC/CODE : la spec attend une ValueError 'Produit inconnu',
    # alors que le code délègue à get_product qui lève une KeyError (cf. commentaire
    # "KeyError si inconnu"). Le test suit la spécification.
    with pytest.raises(ValueError, match="Produit inconnu"):
        quote([{"product_id": "licorne", "qty": 1}])


def test_coupon_fixed5_exactement_au_seuil_de_44_euros():
    """Deux hoodies (88,00 €) : FIXED5 retire 5,00 € et le total passe à 83,00 €."""
    # DIVERGENCE SPEC/CODE : le titre du scénario mentionne un seuil de 44 €,
    # alors que le code applique FIXED5 dès un sous-total >= 30 €. Le test suit
    # les montants chiffrés du scénario (88,00 / 5,00 / 83,00), cohérents avec le code.
    q = quote([{"product_id": "hoodie", "qty": 2}], coupon="FIXED5")
    assert q.subtotal == Decimal("88.00")
    assert q.discount == Decimal("5.00")
    assert q.total == Decimal("83.00")


def test_cumul_remise_volume_et_coupon_welcome10():
    """10 stickers + WELCOME10 : remise volume puis coupon, total 25,85 €."""
    q = quote([{"product_id": "sticker", "qty": 10}], coupon="WELCOME10")
    assert q.subtotal == Decimal("23.28")
    assert q.discount == Decimal("2.33")
    assert q.shipping == Decimal("4.90")
    assert q.total == Decimal("25.85")


def test_quantite_zero_interdite():
    """Une quantité de 0 lève une ValueError 'Quantité hors limites'."""
    with pytest.raises(ValueError, match="Quantité hors limites"):
        quote([{"product_id": "mug", "qty": 0}])


# ---------------------------------------------------------------------------
# Cas limites (non cités par la spécification)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("qty", "expected_subtotal"),
    [(1, "2.45"), (99, "230.42")],
)
def test_limite_quantite_bornes_acceptees(qty, expected_subtotal):
    """Les quantités 1 et 99 sont les bornes incluses autorisées."""
    q = quote([{"product_id": "sticker", "qty": qty}])
    assert q.lines[0].qty == qty
    assert q.subtotal == Decimal(expected_subtotal)


@pytest.mark.parametrize("qty", [0, 100, -1])
def test_limite_quantite_hors_bornes(qty):
    """Une quantité hors de 1..99 lève une ValueError."""
    with pytest.raises(ValueError, match="Quantité hors limites"):
        quote([{"product_id": "sticker", "qty": qty}])


@pytest.mark.parametrize("qty", [2.0, "2", True, None])
def test_limite_quantite_non_entiere(qty):
    """Une quantité non entière (float, chaîne, booléen, None) lève une ValueError."""
    with pytest.raises(ValueError, match="entier"):
        line_total(Decimal("12.50"), qty)


@pytest.mark.parametrize(
    ("qty", "expected_subtotal"),
    [(9, "22.05"), (10, "23.28"), (11, "25.60")],
)
def test_limite_remise_volume_seuil_10(qty, expected_subtotal):
    """9 unités : pas de remise ; 10 unités et plus : remise de 5 % sur la ligne."""
    q = quote([{"product_id": "sticker", "qty": qty}])
    assert q.subtotal == Decimal(expected_subtotal)


def test_limite_remise_volume_cumule_lignes_meme_produit():
    """Deux lignes de 5 stickers totalisant 10 unités ouvrent droit à la remise volume."""
    # DIVERGENCE SPEC/CODE : la spec parle de "10 unités du même produit", ce qui
    # implique un cumul par produit. Le code applique la remise ligne par ligne
    # (5 + 5 stickers = 24,50 € au lieu de 23,28 €). Le test suit la spécification.
    q = quote(
        [
            {"product_id": "sticker", "qty": 5},
            {"product_id": "sticker", "qty": 5},
        ]
    )
    assert q.subtotal == Decimal("23.28")


@pytest.mark.parametrize(
    ("subtotal", "expected"),
    [(Decimal("19.99"), Decimal("0.00")), (Decimal("20.00"), Decimal("2.00"))],
)
def test_limite_welcome10_seuil_20(subtotal, expected):
    """WELCOME10 s'applique à partir de 20,00 € inclus, pas en dessous."""
    assert coupon_discount(subtotal, "WELCOME10") == expected


@pytest.mark.parametrize(
    ("subtotal", "expected"),
    [(Decimal("29.99"), Decimal("0.00")), (Decimal("30.00"), Decimal("5.00"))],
)
def test_limite_fixed5_seuil_30(subtotal, expected):
    """FIXED5 s'applique à partir de 30,00 € inclus, pas en dessous."""
    assert coupon_discount(subtotal, "FIXED5") == expected


def test_limite_fixed5_sous_seuil_sur_panier_reel():
    """Deux mugs (25,00 €) : FIXED5 n'est pas appliqué, total 29,90 €."""
    q = quote([{"product_id": "mug", "qty": 2}], coupon="FIXED5")
    assert q.discount == Decimal("0.00")
    assert q.total == Decimal("29.90")


def test_limite_coupon_insensible_a_la_casse():
    """Un coupon en minuscules est normalisé en majuscules et appliqué."""
    q = quote([{"product_id": "mug", "qty": 2}], coupon="  welcome10 ")
    assert q.coupon == "WELCOME10"
    assert q.discount == Decimal("2.50")


@pytest.mark.parametrize("coupon", ["", None])
def test_limite_coupon_vide_sans_remise(coupon):
    """Un coupon vide ou absent n'apporte aucune remise."""
    assert coupon_discount(Decimal("25.00"), coupon) == Decimal("0.00")


def test_limite_freeship_sur_gros_panier():
    """FREESHIP sur 88,00 € : livraison nulle et aucune remise monétaire."""
    q = quote([{"product_id": "hoodie", "qty": 2}], coupon="FREESHIP")
    assert q.discount == Decimal("0.00")
    assert q.shipping == Decimal("0.00")
    assert q.total == Decimal("88.00")


@pytest.mark.parametrize(
    ("amount", "coupon", "expected"),
    [
        (Decimal("50.00"), None, Decimal("0.00")),
        (Decimal("49.99"), None, Decimal("4.90")),
        (Decimal("49.99"), "FREESHIP", Decimal("0.00")),
        (Decimal("49.99"), "freeship", Decimal("0.00")),
    ],
)
def test_limite_livraison_seuil_50_inclus(amount, coupon, expected):
    """La livraison est offerte à partir de 50,00 € inclus ou avec FREESHIP."""
    assert shipping_cost(amount, coupon, empty=False) == expected


def test_limite_livraison_panier_vide_ignore_seuil():
    """Un panier vide n'a jamais de frais de livraison, même avec un coupon."""
    assert shipping_cost(Decimal("0.00"), "FREESHIP", empty=True) == Decimal("0.00")
    assert shipping_cost(Decimal("0.00"), None, empty=True) == Decimal("0.00")


def test_limite_panier_vide_avec_coupon_sans_remise():
    """Un panier vide avec un coupon valide ne produit aucune remise."""
    q = quote([], coupon="WELCOME10")
    assert q.discount == Decimal("0.00")
    assert q.total == Decimal("0.00")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("0.125"), Decimal("0.13")),
        (Decimal("2.344"), Decimal("2.34")),
        (Decimal("2.345"), Decimal("2.35")),
        ("10", Decimal("10.00")),
    ],
)
def test_limite_money_arrondi_commercial(monkeypatch, value, expected):
    """L'arrondi au centime est commercial (ROUND_HALF_UP) et accepte les chaînes."""
    monkeypatch.delenv("MINISHOP_BUG", raising=False)
    assert money(value) == expected


def test_limite_remise_volume_arrondie_au_centime():
    """10 stickers : 23,275 € arrondis à 23,28 € (demi supérieur)."""
    assert line_total(Decimal("2.45"), 10) == Decimal("23.28")


def test_limite_coupon_student15_hors_spec():
    """STUDENT15 existe dans le code mais pas dans la spec : 15 % sous 10 €."""
    # Comportement non spécifié : test de caractérisation du code existant.
    assert coupon_discount(Decimal("9.00"), "STUDENT15") == Decimal("1.35")
    assert coupon_discount(Decimal("10.00"), "STUDENT15") == Decimal("0.00")


def test_limite_as_dict_montants_en_chaines():
    """La sérialisation expose les montants sous forme de chaînes à deux décimales."""
    d = quote([{"product_id": "mug", "qty": 2}]).as_dict()
    assert d["subtotal"] == "25.00"
    assert d["total"] == "29.90"
    assert d["coupon"] is None
