
from playwright.sync_api import Page


class ShopPage:

    def __init__(self, page: Page):
        self.page = page

    def add(self, product):
        self.page.get_by_test_id(f"add-{product}").click()

    def apply_coupon(self, code):
        self.page.get_by_test_id("coupon").fill(code)
        self.page.get_by_test_id("quote-btn").click()

    def total(self):
        return self.page.get_by_text(
            "Total : 27.40 €"
        )

    def order(self):
        self.page.get_by_test_id("order-btn").click()
