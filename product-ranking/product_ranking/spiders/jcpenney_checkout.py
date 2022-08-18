import re
import time
import json
import inspect

from scrapy import Selector
from selenium.webdriver.support.select import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from product_ranking.checkout_base import BaseCheckoutSpider
from product_ranking.spiders import FLOATING_POINT_RGEX

import scrapy
from scrapy.log import INFO

is_empty = lambda x, y="": x[0] if x else y


class JCpenneySpider(BaseCheckoutSpider):
    name = 'jcpenney_checkout_products'
    allowed_domains = ['jcpenney.com']  # do not remove comment - used in find_spiders()

    SHOPPING_CART_URL = 'https://www.jcpenney.com/cart'
    CHECKOUT_PAGE_URL = "https://www.jcpenney.com/dotcom/" \
                        "jsp/checkout/secure/checkout.jsp"

    def start_requests(self):
        yield scrapy.Request('http://www.jcpenney.com/')

    def _get_colors_names(self):
        swatches = self._find_by_xpath('//ul[@class="List-list-ul"]//img')
        return [x.get_attribute("alt") for x in swatches]

    def select_size(self, element=None):
        default_attr_xpath = '//*[contains(@class, "SelectDropdown-selectOption")]//option[@class="available"]'
        avail_attr_xpath = '//select[@name="size"]/option[not(contains(text(), "Out of Stock")) and not(@value="size")]'
        self.select_attribute(default_attr_xpath, avail_attr_xpath, element)

    def select_color(self, element=None, color=None):
        if color and color.lower() in map(
                (lambda x: x.lower()), self._get_colors_names()):
            color_attribute_xpath = '//button[contains(@class, "ProductOptions-colorSelected")]' \
                                    '//img[@alt="%s"]' % color
        else:
            color_attribute_xpath = '//button[contains(@class, "ProductOptions-colorSelected")]//img'

        color_attributes_xpath = ('//button[@class="ProductOptions-optionColor"]//img')
        self.select_attribute(color_attribute_xpath,
                              color_attributes_xpath,
                              element)

    def click_condition(self, default_xpath, all_xpaths):
        return self._find_by_xpath(default_xpath) or self._find_by_xpath(all_xpaths)

    def select_attribute(self, default_attr_xpath, avail_attr_xpath, element):
        max_retries = 20
        retries = 0
        if self.click_condition(default_attr_xpath, avail_attr_xpath):
            self._click_attribute(default_attr_xpath,
                                  avail_attr_xpath,
                                  element)
            while self.driver.find_elements(By.ID, 'page_loader') and retries < max_retries:
                time.sleep(1)
                retries += 1
            print(inspect.currentframe().f_back.f_code.co_name)

    def select_width(self, element=None):
        default_attr_xpath = '*//div[@id="skuOptions_width"]//' \
                             'li[@class="sku_select"]'
        avail_attr_xpath = '*//*[@id="skuOptions_width"]//' \
                           'li[not(@class="sku_not_available" or @class="sku_illegal")]/a'

        self.select_attribute(default_attr_xpath, avail_attr_xpath, element)

    def select_waist(self, element=None):
        default_attr_xpath = (
            '*//*[@id="skuOptions_waist"]//li[@class="sku_select"]')
        avail_attr_xpath = ('*//*[@id="skuOptions_waist"]//'
                            'li[not(@class="sku_not_available" '
                            'or @class="sku_illegal")]')

        self.select_attribute(default_attr_xpath, avail_attr_xpath, element)

    def select_inseam(self, element=None):
        default_attr_xpath = (
            '*//*[@id="skuOptions_inseam"]//li[@class="sku_select"]')
        avail_attr_xpath = ('*//*[@id="skuOptions_inseam"]//'
                            'li[not(@class="sku_not_available" '
                            'or @class="sku_illegal")]')

        self.select_attribute(default_attr_xpath, avail_attr_xpath, element)

    def select_neck(self, element=None):
        default_attr_xpath = (
            '*//*[@id="skuOptions_neck size"]//li[@class="sku_select"]')

        avail_attr_xpath = ('*//*[@id="skuOptions_neck size"]//'
                            'li[not(@class="sku_not_available" '
                            'or @class="sku_illegal")]')

        self.select_attribute(default_attr_xpath, avail_attr_xpath, element)

    def select_sleeve(self, element=None):
        default_attr_xpath = (
            '*//*[@id="skuOptions_sleeve"]//li[@class="sku_select"]')

        avail_attr_xpath = ('*//*[@id="skuOptions_sleeve"]//'
                            'li[not(@class="sku_not_available" '
                            'or @class="sku_illegal")]')

        self.select_attribute(default_attr_xpath, avail_attr_xpath, element)

    def _parse_attributes(self, product, color, quantity):
        time.sleep(10)
        self.select_color(product, color)
        self.select_size(product)
        self.select_width(product)
        self.select_waist(product)
        self.select_inseam(product)
        self.select_neck(product)
        self.select_sleeve(product)
        self._set_quantity(product, quantity)

    def _get_products(self):
        return self._find_by_xpath('//*[@id="content"]')

    def _add_to_cart(self):
        addtobagbopus = self._find_by_xpath('//*[@data-automation-id="addToCartBlock"]')
        addtobag = self._find_by_xpath('//*[@id="addtobag"]')

        if addtobagbopus:
            # self._click_on_element_with_id('Button-btn Button-btnLg Button-btnPrimary AddToCart-addToCartBtn')
            self.driver.find_element_by_xpath('//button[contains(@class, "addToCartBtn")]').click()
        elif addtobag:
            self._click_on_element_with_id('addtobag')
        time.sleep(5)

    def _do_others_actions(self):
        skip_this_offer = self._find_by_xpath('//button[contains(@data-automation-id, "checkout-button")]')
        if skip_this_offer:
            skip_this_offer[0].click()
            time.sleep(4)

    def _set_quantity(self, product, quantity):
        quantity_option = Select(self.driver.find_element_by_xpath('//*[@name="quantity"]'))
        try:
            quantity_option.select_by_value(str(quantity))
            quantity_selected = quantity_option.first_selected_option.text
            if quantity_selected != str(quantity):
                time.sleep(4)
            self.log('Quantity "{}" selected'.format(quantity))
        except:
            pass

    def _get_product_list_cart(self):
        time.sleep(10)
        self.page_source = self.driver.page_source
        self.page_selector = Selector(text=self.page_source)
        try:
            item_info = re.findall('window.__PRELOADED_STATE__=(\{.+?\});', self.page_source, re.MULTILINE)[0]
            item_info = item_info[:-1] + '"' + item_info[-1:] + '}}'
            self.item_info = json.loads(item_info)
            return self.item_info
        except IndexError:
            return None

    def _get_products_in_cart(self, product_list):
        return product_list.get('orderItems')

    def _parse_cart_page(self):
        # get cookies with our cart stuff and filter them
        dom_name = self._get_current_domain_name()
        cart_cookies = [c for c in self.driver.get_cookies() if dom_name in c['domain']]
        self.log("Got cookies from page: %s" % len(cart_cookies), level=INFO)
        product_list = self._load_cart_page(cart_cookies=cart_cookies)
        for product in self._get_products_in_cart(product_list):
            item = self._parse_item(product)
            item['order_subtotal'] = float(self._get_subtotal())
            item['order_total'] = float(self._get_total())
            yield item

    def _get_subtotal(self):
        return self.item_info.get('merchantTotalWithSavings')

    def _get_total(self):
        return self.item_info.get('orderTotal')

    def _get_item_name(self, item):
        return item.get('displayName')

    def _get_item_id(self, item):
        return item.get('itemNumber')[2:]

    def _get_item_price(self, item):
        return str(item.get('lineTotalPrice'))

    def _get_item_price_on_page(self, item):
        price_on_page_from_json = float(item.get('lineUnitPrice'))
        price_on_page_from_html = self.page_selector.xpath(
            '//span[contains(@data-anid, "product_CurrentSellingPrice")]/text()').re(FLOATING_POINT_RGEX)
        price_on_page_from_html = float(is_empty(price_on_page_from_html, 0))
        return price_on_page_from_json if price_on_page_from_json >= 0 else price_on_page_from_html

    def _get_item_color(self, item):
        selector = scrapy.Selector(text=self.page_source)
        color_new = is_empty(
            selector.xpath('//span[@class="size" and '
                           'contains(text(),"color:")]/text()').re('color\:\n(.+)'))
        color_old = is_empty(selector.xpath(
            '//span[@class="size" and contains(text(),"color:")]'
            '/strong/text()').extract())
        return color_new or color_old

    def _get_item_quantity(self, item):
        return item.get('quantity')

    def _enter_promo_code(self, promo_code):
        self.log('Enter promo code: {}'.format(promo_code))
        promo_field = self._find_by_xpath('//*[@id="cr-code"]')[0]
        promo_field.send_keys(promo_code)
        time.sleep(2)
        promo_field.send_keys(Keys.ENTER)
        time.sleep(5)
        self.driver.refresh()
        time.sleep(5)
        self.item_info = self._get_product_list_cart()

    def _remove_promo_code(self):
        self.log('Remove promo code')
        self.driver.execute_script("removePromoCode('promoCodeRemovalForm_1');")
        time.sleep(10)

    def _get_promo_total(self):
        return self._get_total()

    def _get_promo_subtotal(self):
        return str(self._get_subtotal())

    def _parse_no_longer_available(self):
        return bool(self._find_by_xpath(
            '//*[@class="error_holder"]'))
