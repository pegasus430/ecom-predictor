import re
import time

from product_ranking.utils import is_empty
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from product_ranking.checkout_base import BaseCheckoutSpider, retry_func
from product_ranking.items import CheckoutProductItem
from scrapy.log import WARNING

import scrapy


class JetSpider(BaseCheckoutSpider):
    name = 'jet_checkout_products'
    allowed_domains = ['jet.com']  # do not remove comment - used in find_spiders()

    SHOPPING_CART_URL = 'https://jet.com/cart'

    def start_requests(self):
        yield scrapy.Request('https://jet.com/')

    def _parse_attributes(self, product, color, quantity):
        if color:
            self.select_color(product, color)
            self.select_size(product)
        if quantity:
            self._set_quantity(product, quantity)

    def _get_colors_names(self):
        time.sleep(2)
        xpath = '//div[@rel="Color"]//div[@class="items"]/a'
        colors = self._find_by_xpath(xpath)
        return [x.get_attribute("rel") for x in colors]

    def select_size(self, element=None):
        time.sleep(4)
        items = self._find_by_xpath('//div[@rel="Size"]//div[@class="items"]')
        if items:
            if not items[0].is_displayed():
                xpath = '//div[@rel="Size"]/div[@class="input"]'
                # open dropdown if not already opened
                self._find_by_xpath(xpath)[0].click()

        xpath = '//div[@rel="Size"]//a[contains(@class, "item") ' \
                'and not(contains(@class, "unavailable"))]'
        size_elems = self._find_by_xpath(xpath)
        if size_elems:
            # click on available size
            size_elems[0].click()

        time.sleep(2)

    def select_color(self, element=None, color=None):
        time.sleep(3)
        if color and color.lower() in map(
                (lambda x: x.lower()), self.available_colors):
            # open dropdown
            self._find_by_xpath(
                '//div[@rel="Color"]/div[@class="input"]')[0].click()

            xpath = '//div[@rel="Color"]//div[@class="items"]/a[@rel="{}"]'
            color_elem = self._find_by_xpath(xpath.format(color))
            if color_elem:
                color_elem[0].click()

        time.sleep(3)

    def _parse_no_longer_available(self):
        xpath = '//div[contains(@class, "were_sorry")]'
        not_available = bool(self._find_by_xpath(xpath))
        return not_available

    def _get_products(self):
        return self._find_by_xpath('//div[@id="pdv"]')

    def _add_to_cart(self, color=None):
        time.sleep(3)
        cart_xpath = '//i[contains(@class, "icon-cart")]/' \
                     'span[contains(@class, "count circle")]'
        amount_in_cart = self._find_by_xpath(cart_xpath)
        amount_in_cart = amount_in_cart[0].text if amount_in_cart else 0
        self.log("Amount of items in cart: %s" % amount_in_cart, level=WARNING)
        time.sleep(3)

        add_btn = self._find_by_xpath('//a[contains(@class, "add-button")]')
        if add_btn:
            add_btn[0].click()
        time.sleep(10)

        amount_in_cart = self._find_by_xpath(cart_xpath)
        amount_in_cart = amount_in_cart[0].text if amount_in_cart else None
        self.log("Amount of items in cart after first try: %s" % amount_in_cart, level=WARNING)

        if not amount_in_cart or int(amount_in_cart) == 0:
            item = CheckoutProductItem()
            item['requested_color_not_available'] = True
            item['color'] = color
            return item

    def _set_quantity(self, product, quantity):
        xpath = '//a[contains(@class, "quantity") and contains(@rel, "{}")]'
        quantity_elem = self._find_by_xpath(xpath.format(quantity))
        if not quantity_elem:
            self.log('Requested quantity not available')
            elems = self._find_by_xpath(
                '//a[contains(@class, "quantity") and @rel]'
            )
            self.log('Max available quantity: {}'.format(len(elems)))
            quantity_elem = elems[-1] if elems else None
        else:
            quantity_elem = quantity_elem[0]

        while True:
            time.sleep(1)
            if not quantity_elem.is_displayed():
                right_arrow = self._find_by_xpath('//div[@class="arrow-right"]')
                if right_arrow:
                    right_arrow[0].click()
            else:
                break

        time.sleep(2)
        if quantity_elem.is_displayed():
            quantity_elem.click()

        time.sleep(2)

    def _get_product_list_cart(self):
        element = self._find_by_xpath('//div[contains(@class, "cart-products")]')
        element = element[0] if element else None
        return element

    def _get_products_in_cart(self, product_list):
        html_text = product_list.get_attribute('outerHTML')
        selector = scrapy.Selector(text=html_text)
        return selector.xpath('//div[contains(@class, "cart-item")]')

    def _get_subtotal(self):
        subtotal = filter(
            lambda x: x.is_displayed(),
            self._find_by_xpath('//h5[@data-subtotal]')
        )
        return subtotal[0].get_attribute('data-subtotal') if subtotal else None

    def _get_total(self):
        total = filter(
            lambda x: x.is_displayed(),
            self._find_by_xpath('//h4[@data-order-total]')
        )
        return total[0].get_attribute('data-order-total') if total else None

    def _get_item_name(self, item):
        return is_empty(item.xpath(
            './/a[contains(@class, "name")]/text()').extract())

    def _get_item_id(self, item):
        return is_empty(item.xpath('@data-sku').extract())

    def _get_item_price(self, item):
        return self._get_subtotal()

    def _get_item_price_on_page(self, item):
        price_on_page =  is_empty(item.xpath(
            '//div[contains(@class, "price-market")' \
            'and contains(@class, "block")]/text()'
        ).re('\$(.*)'))

        if not price_on_page:
            btn_id = is_empty(item.xpath('.//input[@checked="true"]/@id').extract())
            price_on_page = is_empty(
                item.xpath(
                    '//label[@for="{}"]//span[contains(@class, "number")]/text()'
                .format(btn_id)).re('\$(.*)'))

        return round(float(price_on_page.replace(',', '')), 2)

    def _get_item_color(self, item):
        variants = item.xpath(
            '//div[@class="product-variants"]/h5/text()'
        ).extract()
        for var in variants:
            k, v = var.split(':')
            if k == 'Color':
                return v.strip()

    def _get_item_quantity(self, item):
        return is_empty(
            item.xpath(
                '//div[contains(@class, "quantity-selector-item") '
                'and contains(@class, "active")]/@data-qty'
            ).extract())
