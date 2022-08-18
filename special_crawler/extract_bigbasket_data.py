#!/usr/bin/python

import re
import requests

from lxml import html

from extract_data import Scraper
from spiders_shared_code.bigbasket_variants import BigbasketVariants


class BigBasketScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https://www.bigbasket.com/pd/<product-id>/<product-name>"

    AUTH_URL = "https://www.bigbasket.com/skip_explore/?c=1&l=0&s=0&n=%2F"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.bgVnt = BigbasketVariants()

    def _extract_page_tree(self):
        agent = self.select_browser_agents_randomly()

        headers = {'Content-Type': 'application/json', 'User-agent': agent}

        with requests.Session() as s:
            # Set auth cookies
            s.get(
                self.AUTH_URL,
                headers=headers,
                timeout=5
            )
            # An authorised request.
            response = s.get(
                self.product_page_url,
                headers=headers,
                timeout=5
            )

            if self.lh:
                self.lh.add_log('status_code', response.status_code)
            if response != 'Error' and response.ok:
                contents = response.text
                try:
                    self.tree_html = html.fromstring(contents.decode("utf8"))
                except UnicodeError as e:
                    # if string was not utf8, don't deocde it
                    print "Error creating html tree from page content: ", e.message
                    self.tree_html = html.fromstring(contents)

    def check_url_format(self):
        m = re.match(r"^https://www.bigbasket.com/pd/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        try:
            self.bgVnt.setupCH(self.tree_html)
        except:
            pass

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return re.search('\d+', self.product_page_url).group()

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        title = self.tree_html.xpath(
            "//div[contains(@class, 'uiv2-product-heading-h2-section')]"
            "//h2/text()")
        if not title:
            title = self.tree_html.xpath('//div[@itemprop="name"]/h1/text()')
        return title[0].strip() if title else None

    def _title_seo(self):
        return self._product_name()

    def _description(self):
        short_description = self.tree_html.xpath(
            "//div[contains(@class, 'uiv2-tab-content')]//p/text()"
        )

        if short_description:
            short_description = self._clean_text(short_description[0]).replace('\'', '')

        return short_description

    def _variants(self):
        self.variants = self.bgVnt._variants()
        return self.variants

    def _no_longer_available(self):
        return 0

    def _ingredients(self):
        tab_contents = self.tree_html.xpath("//div[contains(@class, 'uiv2-tab-content')]//p/text()")
        tab_names = self.tree_html.xpath("//a[@class='uiv2-tab']/text()")

        ingredients = []
        for index, tab_name in enumerate(tab_names):
            if 'ingredients' in tab_name.lower():
                ingredient_list = tab_contents[index].split(',')
        for ingredient in ingredient_list:
            ingredients.append(ingredient.strip().replace('.', ''))

        return ingredients

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        product_id = self._product_id()
        if not product_id:
            return None

        image_wrapper_id = 'slidingProduct' + product_id

        images = self.tree_html.xpath(
            "//div[@id='%s']"
            "//div[@class='uiv2-product-large-img-container']"
            "//a[@class='jqzoom']/@href" % image_wrapper_id
        )

        if images:
            image_urls = map(lambda x: 'https:' + x, images)
            return image_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath(
            '//div[@class="uiv2-product-value"][@itemprop="offers"]'
            '//div[@class="uiv2-price"]/text()'
        )

        return price[0] if price else None

    def _temp_price_cut(self):
        if self.tree_html.xpath('//div[@class="uiv2-savings"]'):
            return 1
        return 0

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock_info = self.tree_html.xpath(
            '//meta[@itemprop="availability"]'
            '/@content'
        )

        if stock_info and 'out_of_stock' == stock_info[0].lower():
            return 1

        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath('//div[@class="breadcrumb-item"]//span[@itemprop="title"]/text()')

        return categories[1:] if categories else None

    def _brand(self):
        brand = self.tree_html.xpath('//div[@class="uiv2-brand-name"]//a/text()')

        return brand[0].strip() if brand else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()


    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "title_seo" : _title_seo,
        "description" : _description,
        "variants" : _variants,
        "no_longer_available" : _no_longer_available,
        "ingredients": _ingredients,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,

        # CONTAINER : SELLERS
        "price" : _price,
        "temp_price_cut": _temp_price_cut,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
    }
