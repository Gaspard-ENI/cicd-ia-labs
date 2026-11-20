
import re
import pytest
from playwright.sync_api import Page, expect
from tests.e2e.pages.shop_page import ShopPage

pytestmark = pytest.mark.e2e


@pytest.fixture
def shop(page: Page, app_url):
    page.goto(app_url)
    return ShopPage(page)

def test_page_accueil(shop):
    expect(shop.page).to_have_title(re.compile("MiniShop"))
    expect(shop.page.get_by_test_id("products").locator("li")).to_have_count(5)

def test_parcours_achat(shop):
    # Ajouter deux mugs
    shop.add("mug")
    shop.add("mug")

    # Appliquer la réduction
    shop.apply_coupon("WELCOME10")

    # Vérifier le total
    expect(shop.total()).to_be_visible()

    # Commander
    shop.order()


def test_coupon_invalide(shop):
    shop.add("mug")
    shop.apply_coupon("TEST")

    expect(shop.page.get_by_role("alert")).to_have_text(
        "Coupon inconnu : TEST"
    )


def test_commander_desactive_si_panier_vide(shop):
    expect(shop.page.get_by_test_id("order-btn")).to_be_disabled()
    shop.add("mug")
    expect(shop.page.get_by_test_id("order-btn")).to_be_enabled()

