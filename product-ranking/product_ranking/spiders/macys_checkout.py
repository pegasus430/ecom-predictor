import re
import time

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from product_ranking.checkout_base import BaseCheckoutSpider

import scrapy

is_empty = lambda x, y="": x[0] if x else y
delete_commas = lambda x: x.replace(',', '')


class MacysSpider(BaseCheckoutSpider):
    name = 'macys_checkout_products'
    allowed_domains = ['macys.com']  # do not remove comment - used in find_spiders()

    SHOPPING_CART_URL = 'http://www1.macys.com/bag/index.ognc'

    def start_requests(self):
        yield scrapy.Request('http://www1.macys.com/', dont_filter=True)

    def _get_colors_names(self):
        xpath = '//div[@class="colorsSection"]//li[@data-title]'
        swatches = self._find_by_xpath(xpath)
        colors = [x.get_attribute("data-title").lower() for x in swatches]
        return colors if colors else [None]

    def select_size(self, element=None):
        size_attribute_xpath = (
            '*//*[@class="sizesSection"]//li[@class="swatch selected"]')

        size_attributes_xpath = (
            '*//*[@class="sizesSection"]//'
            'li[contains(@class, "swatch") '
            'and not(contains(@class, "disabled"))]')

        self._click_attribute(size_attribute_xpath,
                              size_attributes_xpath,
                              element)
        self.log('Size selected')

    def select_color(self, element=None, color=None):
        # If color was requested and is available
        color_attribute_xpath = (
            '*//div[@class="colorsSection"]//li[@class="swatch selected"]')
        color_attributes_xpath = (
            '*//*[@class="colorsSection"]//'
            'li[contains(@class, "swatch") '
            'and not(contains(@class, "disabled"))]')
        color = color.lower() if color else color
        if color and color in self.available_colors:
            color_attribute_xpath = (
                '*//div[@class="colorsSection"]//'
                'li[translate(@data-title,'
                '"ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")="%s"]' % color)


        self._click_attribute(color_attribute_xpath,
                              color_attributes_xpath,
                              element)

        self.log('Color selected')

    def _get_products(self):
        return self._find_by_xpath('//*[@id="productSidebar"]')

    def _add_to_cart(self):
        add_to_bag = self._find_by_xpath(
            '//*[contains(@class,"addToBagButton")]')

        if add_to_bag:
            add_to_bag[0].click()
            self.log('Added to cart')
            self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, '//a/text()[contains(., "added to your bag")]/..')
                )
            )

    def _set_quantity(self, product, quantity):
        quantity_option = Select(self.driver.find_element_by_xpath('*//*[@class="productQuantity"]'))
        try:
            quantity_option.select_by_value(str(quantity))
            quantity_selected = quantity_option.first_selected_option.text
            if quantity_selected != str(quantity):
                time.sleep(4)
            self.log('Quantity "{}" selected'.format(quantity))
        except:
            pass

    def _get_product_list_cart(self):
        self.wait.until(
            EC.presence_of_element_located((By.XPATH, '//ul[@class="guest-nav-dropdown"]'))
        )
        condition = EC.visibility_of_element_located(
            (By.ID, 'itemsContainer'))
        return self.wait.until(condition)

    def _get_products_in_cart(self, product_list):
        html_text = product_list.get_attribute('outerHTML')
        selector = scrapy.Selector(text=html_text)

        return selector.xpath('//*[contains(@id, "lineitem_")]')

    def _get_subtotal(self):
        order_subtotal_element = self.wait.until(
            EC.visibility_of_element_located((
                By.ID, 'bagMerchandiseTotal')))
        if order_subtotal_element:
            order_subtotal = order_subtotal_element.text
            return delete_commas(is_empty(re.findall('\$(.*)', order_subtotal)))

    def _get_total(self):
        order_total_element = self.wait.until(
            EC.element_to_be_clickable(
                (By.ID, 'bagTotal')))

        if order_total_element:
            order_total = order_total_element.text
            return delete_commas(is_empty(re.findall('\$(.*)', order_total)))

    def _get_item_name(self, item):
        return is_empty(item.xpath(
            '*//*[@class="itemName"]/a/text()').extract())

    def _get_item_id(self, item):
        return is_empty(item.xpath(
                        '*//*[@class="valWebId"]/text()').extract())

    def _get_item_price(self, item):
        return delete_commas(is_empty(item.xpath(
                        '*//*[@class="itemTotal"]/text()').re('\$(.*)')))

    def _get_item_price_on_page(self, item):
        prices = item.xpath('//*[@class="colPrice"]//text()').re('\$(.*)')
        prices = [float(delete_commas(price)) for price in prices]
        return min(prices)

    def _get_item_color(self, item):
        return delete_commas(is_empty(item.xpath(
                        '*//*[@class="valColor"]/text()').extract()))

    def _get_item_quantity(self, item):
        return is_empty(item.xpath(
                        '//*[@class="colQty"]//'
                        'option[@selected]/text()').extract())

    def _pre_parse_products(self):
        more_size_button = self._find_by_xpath(
            '//div[@class="sizesSection"]//*[@class="columns small-2 viewMore"]/a/text()[contains(., "More")]/..')
        if more_size_button and more_size_button[0].is_displayed():
            more_size_button[0].click()
            xpath = '//div[@class="sizesSection"]//*[@class="columns small-2 viewMore"]/a/text()[contains(., "Less")]/..'
            self.wait.until(
                EC.visibility_of_element_located((
                    By.XPATH, xpath)))

    def _parse_attributes(self, product, color, quantity):
        self._pre_parse_products()
        self.select_color(product, color)
        self.select_size(product)
        self._set_quantity(product, quantity)

    def _get_promo_subtotal(self):
        return self._get_subtotal()

    def _get_promo_total(self):
        return self._get_total()

    def _enter_promo_code(self, promo_code):
        self.log('Enter promo code: {}'.format(promo_code))
        promo_field = self._find_by_xpath('//input[@id="promoCode"]')[0]
        promo_field.send_keys(promo_code)
        time.sleep(2)
        promo_field.send_keys(Keys.ENTER)
        time.sleep(4)

    def _remove_promo_code(self):
        self.log('Remove promo code')
        try:
            remove_field = self._find_by_xpath('//a[@class="removelnk promocodeApply appliedRemovelnk"]')[0]
            remove_field.click()
            time.sleep(2)
        except IndexError:
            self.log('Invalid promo code')

    def _get_promo_invalid_message(self):
        return self.driver.find_element_by_id('promoCodeError').text

    def _parse_no_longer_available(self):
        return bool(self._find_by_xpath(
            '//*[contains(., "This product is currently unavailable") or '
            'contains(., "This product is no longer available.")]'))
