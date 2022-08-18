import json
import os
import random
import re
import socket
import sys
import time
import traceback
import urlparse
import itertools
from functools import wraps
import inspect

from abc import abstractmethod
from selenium.webdriver.common.by import By


from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from product_ranking.items import CheckoutProductItem

import scrapy
from scrapy.conf import settings
from scrapy.http import FormRequest
from scrapy.log import INFO, WARNING, ERROR
from scrapy import log as scrapy_logger
import lxml.html


CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(CWD, '..', '..', '..', '..', '..'))

try:
    from search.captcha_solver import CaptchaBreakerWrapper
except ImportError as e:
    CaptchaBreakerWrapper = None
    print 'Error loading captcha breaker!', str(e)


def _get_random_proxy():
    proxy_file = '/tmp/http_proxies.txt'
    if os.path.exists(proxy_file):
        with open(proxy_file, 'r') as fh:
            lines = [l.strip().replace('http://', '')
                     for l in fh.readlines() if l.strip()]
            return random.choice(lines)


def _get_domain(url):
    return urlparse.urlparse(url).netloc.replace('www.', '')


def retry_func(ExceptionToCheck, tries=10, delay=2):
    """Retry call for decorated function"""

    def ext_retry(f):

        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck as e:
                    msg = "Exception - {}, retrying method {} in {} seconds, retries left: {}...".format(
                        str(e), f.__name__, mdelay, mtries)
                    func_args = "Arguments: {}".format(inspect.getargspec(f))
                    trb = "################### TRACEBACK HERE ############## \n {} ################".format(
                        traceback.format_exc())
                    scrapy_logger.msg(msg, level=WARNING)
                    scrapy_logger.msg(func_args, level=WARNING)
                    scrapy_logger.msg(trb, level=WARNING)
                    time.sleep(mdelay)
                    mtries -= 1
            return f(*args, **kwargs)
        return f_retry  # true decorator
    return ext_retry


class BaseCheckoutSpider(scrapy.Spider):
    allowed_domains = []  # do not remove comment - used in find_spiders()
    available_drivers = ['chromium', 'firefox']

    handle_httpstatus_list = [403, 404, 502, 500]

    SHOPPING_CART_URL = ''
    CHECKOUT_PAGE_URL = ""

    retries = 0
    MAX_RETRIES = 10
    SOCKET_WAIT_TIME = 100
    WEBDRIVER_WAIT_TIME = 60

    def __init__(self, *args, **kwargs):
        settings.overrides['ITEM_PIPELINES'] = {}
        super(BaseCheckoutSpider, self).__init__(*args, **kwargs)
        self.user_agent = kwargs.get(
            'user_agent',
            ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.89 Safari/537.36')
        )

        self.product_urls = kwargs.get('product_urls', None)
        self.product_data = kwargs.get('product_data', "[]")
        self.product_data = json.loads(self.product_data)
        self.driver_name = kwargs.get('driver', None)
        self.proxy = kwargs.get('proxy', '')  # e.g. 192.168.1.42:8080
        self.proxy_type = kwargs.get('proxy_type', '')  # http|socks5
        self.disable_site_settings = kwargs.get('disable_site_settings', None)
        self.quantity = kwargs.get('quantity', None)

        self.requested_color = None
        self.is_requested_color = False

        self.promo_code = kwargs.get('promo_code', '') # ticket 10585
        self.promo_code = [promo_code.strip() for promo_code in self.promo_code.split(',')]
        self.promo_price = int(kwargs.get('promo_price', 0))
        self.promo_mod = self.promo_code and self.promo_price

        from pyvirtualdisplay import Display
        display = Display(visible=False, size=(1280, 720))
        display.start()

        if self.quantity:
            self.quantity = [int(x) for x in self.quantity.split(',')]
            self.quantity = sorted(self.quantity)
        else:
            self.quantity = [1]

    def closed(self, reason):
        print "## closing all driver windows"
        self.driver.quit()

    def parse(self, request):
        is_iterable = isinstance(self.product_data, (list, tuple))
        self.product_data = (self.product_data
                             if is_iterable
                             else list(self.product_data))

        for product in self.product_data:
            self.log("Product: %r" % product)
            url = product.get('url')
            self._open_new_session(url)
            self.requested_color = None
            self.is_requested_color = False
            self.no_longer_available = self._parse_no_longer_available()
            self.available_colors = self._get_colors_names() if not self.no_longer_available else [None]
            if product.get('FetchAllColors'):
                # Parse all the products colors
                self._pre_parse_products()
                colors = self.available_colors

            else:
                # Only parse the selected color
                # if None, the first fetched will be selected
                colors = product.get('color', None)

                if colors:
                    self.is_requested_color = True

                if isinstance(colors, basestring) or not colors:
                    colors = [colors]
            self.log('Got colors {}'.format(colors), level=WARNING)
            for variant in self._parse_variants(colors, url):
                yield variant
        self.driver.quit()

    def _parse_items(self, items, url):
        for item in items:
            item['url'] = url
            if self.promo_mod:
                for item_promo in self.promo_logic(item):
                    yield item_promo
            else:
                yield item

    def _parse_variants(self, colors, url):
        for i, (qty, color) in enumerate(itertools.product(self.quantity, colors)):
            self.log('Parsing color - {}, quantity - {}'.format(
                color or 'None', qty), level=WARNING)
            if self.no_longer_available:
                for promo_code in self.promo_code:
                    self.log('No longer available {}'.format(self.no_longer_available), level=WARNING)
                    item = CheckoutProductItem()
                    item['url'] = url
                    item['color'] = color
                    item['quantity'] = qty
                    if self.promo_mod:
                        item['promo_code'] = promo_code
                    item['no_longer_available'] = True
                    item['not_found'] = True
                    yield item
            else:
                if i > 0:
                    self.driver.delete_all_cookies()
                    self.driver.get(url)
                if self.is_requested_color:
                    self.requested_color = color
                self.current_color = color
                self.current_quantity = qty
                self._parse_product_page(url, qty, color)
                items = self._parse_cart_page()
                for item in self._parse_items(items, url):
                    yield item

    @retry_func(Exception)
    def _open_new_session(self, url):
        old_driver = getattr(self, 'driver', None)
        if old_driver and not isinstance(old_driver, str):
            self.driver.quit()
        self.driver = self.init_driver()
        self.wait = WebDriverWait(self.driver, self.WEBDRIVER_WAIT_TIME)
        socket.setdefaulttimeout(self.SOCKET_WAIT_TIME)
        self.driver.get(url)

    def _parse_item(self, product):
        item = CheckoutProductItem()
        name = self._get_item_name(product)
        item['name'] = name.strip() if name else name
        item['id'] = self._get_item_id(product)
        price = self._get_item_price(product)
        item['price_on_page'] = self._get_item_price_on_page(product)
        color = self._get_item_color(product)
        quantity = self._get_item_quantity(product)
        item['no_longer_available'] = False
        item['not_found'] = False

        if quantity and price:
            quantity = int(quantity)
            item['price'] = round(float(price.replace(',', '')) / quantity, 2)
            item['quantity'] = quantity
            item['requested_color'] = self.requested_color
            item['requested_quantity_not_available'] = quantity != self.current_quantity

        if color:
            item['color'] = color

        item['requested_color_not_available'] = (
            color and self.requested_color and
            (self.requested_color.lower() != color.lower()))
        return item

    def _parse_attributes(self, product, color, quantity):
        self.select_color(product, color)
        self.select_size(product)
        self._set_quantity(product, quantity)

    def _parse_product_page(self, product_url, quantity, color=None):
        """ Process product and add it to the cart"""
        products = self._get_products()

        # Make it iterable for convenience
        is_iterable = isinstance(products, (list, tuple))
        products = products if is_iterable else list(products)

        for product in products:
            self._parse_one_product_page(product, quantity, color)

    @retry_func(Exception)
    def _parse_one_product_page(self, product, quantity, color=None):
        # this is moved to separate method to avoid situations in future
        # where multiple product are given, and add to cart button not worked in one of them
        # self._open_new_session(url)
        self._pre_parse_products()
        self._parse_attributes(product, color, quantity)
        self._add_to_cart()
        self._do_others_actions()

    @retry_func(Exception)
    def _load_cart_page(self, cart_cookies=None):
        self.driver.get(self.SHOPPING_CART_URL)
        product_list = self._get_product_list_cart()
        if product_list:
            return product_list
        else:
            # selenium need actual page opened to import cookies
            self._open_new_session(self.SHOPPING_CART_URL)
            time.sleep(5)
            self.driver.delete_all_cookies()
            time.sleep(5)
            if cart_cookies:
                for cookie in cart_cookies:
                    self.driver.add_cookie(cookie)
            time.sleep(5)
            # retry the page until we get correct element
            raise Exception

    # @retry_func(Exception)
    def _get_current_domain_name(self):
        # trying to get current domain to filter cookies
        url = self.driver.current_url
        dom_name = urlparse.urlparse(url).netloc.replace(
            'www1', '').replace('www3', '').replace('www', '')
        if not dom_name:
            dom_name = self.allowed_domains[0]
        self.log("Got domain name: %s" % dom_name, level=WARNING)
        return dom_name

    def _parse_cart_page(self):
        # get cookies with our cart stuff and filter them
        dom_name = self._get_current_domain_name()
        cart_cookies = [c for c in self.driver.get_cookies() if dom_name in c.get('domain')]
        self.log("Got cookies from page: %s" % len(cart_cookies), level=WARNING)
        product_list = self._load_cart_page(cart_cookies=cart_cookies)
        for product in self._get_products_in_cart(product_list):
            item = self._parse_item(product)
            item['order_subtotal'] = float(self._get_subtotal())
            item['order_total'] = float(self._get_total())
            yield item

    def _find_by_xpath(self, xpath, element=None):
        """
        Find elements by xpath,
        if element is defined, search from that element node
        """
        if element:
            target = element
        else:
            target = self.driver
        return target.find_elements(By.XPATH, xpath)

    # @retry_func(Exception)
    def _click_attribute(self, selected_attribute_xpath, others_attributes_xpath, element=None):
        """
        Check if the attribute given by selected_attribute_xpath is checkout
        if checkeck don't do it anything,
        else find the first available attribute and click on it
        """
        if element:
            target = element
        else:
            target = self.driver

        selected_attribute = target.find_elements(
            By.XPATH, selected_attribute_xpath)

        available_attributes = target.find_elements(
            By.XPATH, others_attributes_xpath)

        # If not attribute is set and there are available attributes
        if not selected_attribute and available_attributes:
            available_attributes[0].click()
        elif selected_attribute:
            selected_attribute[0].click()

    def promo_logic(self, item):
        for promo_code in self.promo_code:
            item['promo_code'] = promo_code
            self._enter_promo_code(promo_code)
            promo_order_total = float(self._get_promo_total())
            promo_order_subtotal = float(self._get_promo_subtotal().replace(',', ''))
            promo_price = round(promo_order_subtotal / item['quantity'], 2)
            is_promo_code_valid = not promo_order_total == item['order_total']
            item['is_promo_code_valid'] = is_promo_code_valid
            if not is_promo_code_valid:
                item['promo_invalid_message'] = self._get_promo_invalid_message()
            else:
                item.pop('promo_invalid_message', None)
            if self.promo_price == 1:
                item['order_total'] = promo_order_total
                item['order_subtotal'] = promo_order_subtotal
                item['price'] = promo_price
            if self.promo_price == 2:
                item['promo_order_total'] = promo_order_total
                item['promo_order_subtotal'] = promo_order_subtotal
                item['promo_price'] = promo_price
            self._remove_promo_code()
            yield item

    @abstractmethod
    def _get_promo_invalid_message(self):
        return

    @abstractmethod
    def _get_promo_subtotal(self):
        return

    @abstractmethod
    def _get_promo_total(self):
        return

    @abstractmethod
    def _enter_promo_code(self, promo_code):
        return

    @abstractmethod
    def _remove_promo_code(self):
        return

    @abstractmethod
    def _get_product_list_cart(self):
        return

    @abstractmethod
    def start_requests(self):
        return

    @abstractmethod
    def _get_colors_names(self):
        """Return the name of all the colors availables"""
        return

    @abstractmethod
    def select_size(self, element=None):
        """Select the size for the product"""
        return

    @abstractmethod
    def select_color(self, element=None, color=None):
        """Select the color for the product"""
        return

    @abstractmethod
    def select_width(self, element=None):
        """Select the width for the product"""
        return

    @abstractmethod
    def select_others(self, element=None):
        """Select others attributes for the product"""
        return

    @abstractmethod
    def _set_quantity(self, product, quantity):
        """Select the quantity for the product"""
        return

    @abstractmethod
    def _get_products(self):
        """Return the products on the page"""
        return

    @abstractmethod
    def _add_to_cart(self):
        """Add the product to the cart"""
        return

    @abstractmethod
    def _do_others_actions(self):
        """Do actions after adding product to cart"""
        return

    @abstractmethod
    def _get_item_name(self, item):
        return

    @abstractmethod
    def _get_item_id(self, item):
        return

    @abstractmethod
    def _get_item_price(self, item):
        return

    @abstractmethod
    def _get_item_price_on_page(self, item):
        return

    @abstractmethod
    def _get_item_color(self, item):
        return

    @abstractmethod
    def _get_item_quantity(self, item):
        return

    @abstractmethod
    def _get_subtotal(self):
        return

    @abstractmethod
    def _get_total(self):
        return

    @abstractmethod
    def _pre_parse_products(self):
        return

    @abstractmethod
    def _parse_no_longer_available(self):
        return False

    # @retry_func(Exception)
    def _click_on_element_with_id(self, _id):
        element = self.wait.until(EC.element_to_be_clickable((By.ID, _id)))
        element.click()

    def _choose_another_driver(self):
        for d in self.available_drivers:
            if d != self._driver:
                return d

    def _init_chromium(self):
        from selenium import webdriver
        chrome_flags = webdriver.DesiredCapabilities.CHROME  # this is for Chrome?
        chrome_options = webdriver.ChromeOptions()  # this is for Chromium
        if self.proxy:
            chrome_options.add_argument(
                '--proxy-server=%s' % self.proxy_type + '://' + self.proxy)
        chrome_flags["chrome.switches"] = ['--user-agent=%s' % self.user_agent]
        chrome_options.add_argument('--user-agent=%s' % self.user_agent)
        executable_path = '/usr/sbin/chromedriver'
        if not os.path.exists(executable_path):
            executable_path = '/usr/local/bin/chromedriver'
        # initialize webdriver, open the page
        driver = webdriver.Chrome(desired_capabilities=chrome_flags,
                                  chrome_options=chrome_options,
                                  executable_path=executable_path)
        # driver.set_page_load_timeout(self.SOCKET_WAIT_TIME)
        # driver.maximize_window()
        return driver

    def _init_firefox(self):
        from selenium import webdriver
        profile = webdriver.FirefoxProfile()
        profile.set_preference("general.useragent.override", self.user_agent)
        profile.set_preference("network.proxy.type", 1)  # manual proxy configuration
        if self.proxy:
            if 'socks' in self.proxy_type:
                profile.set_preference("network.proxy.socks", self.proxy.split(':')[0])
                profile.set_preference("network.proxy.socks_port", int(self.proxy.split(':')[1]))
            else:
                profile.set_preference("network.proxy.http", self.proxy.split(':')[0])
                profile.set_preference("network.proxy.http_port", int(self.proxy.split(':')[1]))
        profile.update_preferences()
        driver = webdriver.Firefox(profile)
        return driver

    def init_driver(self, name=None):
        if name:
            self._driver = name
        else:
            if not self.driver_name:
                self._driver = 'chromium'
            elif self.driver_name == 'random':
                self._driver = random.choice(self.available_drivers)
            else:
                self._driver = self.driver_name
        self.log('Using driver: ' + self._driver)
        init_driver = getattr(self, '_init_' + self._driver)
        return init_driver()

    @staticmethod
    def _get_proxy_ip(driver):
        driver.get('http://icanhazip.com')
        ip = re.search('(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', driver.page_source)
        if ip:
            ip = ip.group(1)
            return ip

    def _has_captcha(self, response_or_text):
        if not isinstance(response_or_text, (str, unicode)):
            response_or_text = response_or_text.body_as_unicode()
        return '.images-amazon.com/captcha/' in response_or_text

    def _solve_captcha(self, response_or_text):
        if not isinstance(response_or_text, (str, unicode)):
            response_or_text = response_or_text.body_as_unicode()
        doc = lxml.html.fromstring(response_or_text)
        forms = doc.xpath('//form')
        assert len(forms) == 1, "More than one form found."

        captcha_img = forms[0].xpath(
            '//img[contains(@src, "/captcha/")]/@src')[0]

        self.log("Extracted capcha url: %s" % captcha_img, level=WARNING)

        return CaptchaBreakerWrapper().solve_captcha(captcha_img)

    def _handle_captcha(self, response, callback):
        # FIXME This is untested and wrong.
        captcha_solve_try = response.meta.get('captcha_solve_try', 0)
        url = response.url

        self.log("Captcha challenge for %s (try %d)."
                 % (url, captcha_solve_try),
                 level=INFO)

        captcha = self._solve_captcha(response)
        if captcha is None:
            self.log(
                "Failed to guess captcha for '%s' (try: %d)." % (
                    url, captcha_solve_try),
                level=ERROR
            )
            result = None
        else:
            self.log(
                "On try %d, submitting captcha '%s' for '%s'." % (
                    captcha_solve_try, captcha, url),
                level=INFO
            )

            meta = response.meta.copy()
            meta['captcha_solve_try'] = captcha_solve_try + 1

            result = FormRequest.from_response(
                response,
                formname='',
                formdata={'field-keywords': captcha},
                callback=callback,
                dont_filter=True,
                meta=meta)

        return result
