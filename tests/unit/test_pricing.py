"""Tests unitaires des règles de prix — SOLUTION Atelier 1."""

from decimal import Decimal

import pytest

from minishop.pricing import (
    SHIPPING_FEE,
    coupon_discount,
    line_total,
    money,
    quote,
    shipping_cost,
)

pytestmark = pytest.mark.unit
D = Decimal


# ---------- money ----------
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("0.125", "0.13"),
        ("0.124", "0.12"),
        ("2.005", "2.01"),
        (10, "10.00"),
        ("-0.125", "-0.13"),
    ],
)
def test_money_arrondi_commercial(raw, expected):
    assert money(raw) == D(expected)


# ---------- line_total ----------
def test_line_total_sans_remise():
    assert line_total(D("12.50"), 2) == D("25.00")


def test_remise_volume_a_partir_de_10():
    assert line_total(D("2.45"), 10) == D("23.28")  # 24.50 * 0.95 = 23.275 -> 23.28


def test_pas_de_remise_volume_a_9():
    assert line_total(D("2.45"), 9) == D("22.05")


@pytest.mark.parametrize("qty", [0, -1, 100, "2", 2.0, True, None])
def test_quantite_invalide(qty):
    with pytest.raises(ValueError):
        line_total(D("10"), qty)


@pytest.mark.parametrize("qty", [1, 99])
def test_quantite_bornes_valides(qty):
    assert line_total(D("1.00"), qty) > 0


# ---------- coupons ----------
@pytest.mark.parametrize(
    "subtotal, coupon, expected",
    [
        ("20.00", "WELCOME10", "2.00"),  # seuil inclus
        ("19.99", "WELCOME10", "0.00"),  # sous le seuil
        ("30.00", "FIXED5", "5.00"),
        ("29.99", "FIXED5", "0.00"),
        ("100.00", "FREESHIP", "0.00"),  # FREESHIP n'est pas une remise sur le montant
        ("50.00", None, "0.00"),
        ("50.00", "", "0.00"),
        ("40.00", " welcome10 ", "4.00"),  # casse et espaces tolérés
    ],
)
def test_coupon_discount(subtotal, coupon, expected):
    assert coupon_discount(D(subtotal), coupon) == D(expected)


def test_coupon_inconnu():
    with pytest.raises(ValueError, match="Coupon inconnu"):
        coupon_discount(D("50"), "NOEL2026")


# ---------- livraison ----------
@pytest.mark.parametrize(
    "amount, coupon, empty, expected",
    [
        ("49.99", None, False, SHIPPING_FEE),
        ("50.00", None, False, D("0.00")),
        ("10.00", "FREESHIP", False, D("0.00")),
        ("0.00", None, True, D("0.00")),
    ],
)
def test_shipping_cost(amount, coupon, empty, expected):
    assert shipping_cost(D(amount), coupon, empty) == expected


# ---------- quote (intégration des règles) ----------
def test_quote_panier_vide():
    q = quote([])
    assert (q.total, q.shipping, q.discount) == (D("0.00"),) * 3


def test_quote_complet_avec_welcome10():
    q = quote([{"product_id": "mug", "qty": 2}], "WELCOME10")
    assert q.subtotal == D("25.00")
    assert q.discount == D("2.50")
    assert q.shipping == SHIPPING_FEE  # 22.50 < 50
    assert q.total == D("27.40")


def test_livraison_calculee_apres_remise():
    """52 € de sous-total -10 % = 46.80 € -> la livraison redevient payante."""
    q = quote([{"product_id": "hoodie", "qty": 1}, {"product_id": "sticker", "qty": 3}], "WELCOME10")
    assert q.subtotal == D("51.35")
    assert q.shipping == SHIPPING_FEE


def test_produit_inconnu():
    with pytest.raises(KeyError):
        quote([{"product_id": "licorne", "qty": 1}])


def test_as_dict_serialisable():
    d = quote([{"product_id": "book", "qty": 1}]).as_dict()
    assert d["total"] == "34.89" and d["lines"][0]["product_id"] == "book"


def test_bug_arrondi_detecte(monkeypatch):
    """Démontre que la suite attrape le bug injecté MINISHOP_BUG=rounding."""
    monkeypatch.setenv("MINISHOP_BUG", "rounding")
    assert money("0.125") != D("0.13")
