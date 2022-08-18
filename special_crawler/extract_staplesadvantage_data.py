#!/usr/bin/python

import re
import requests
import traceback

from lxml import html
from extract_data import Scraper


class StaplesAdvantageScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.staplesadvantage.com/shop/StplShowItem?.* or " \
                          "http(s)://www.staplesadvantage.com/webapp/wcs/stores/servlet/StplShowItem?.*"

    LOGIN_URL = 'https://www.staplesadvantage.com/webapp/wcs/stores/servlet/StplLogon?catalogId=4&langId=-1&storeId=10101'

    HEADERS = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept-Language': 'en-US,en;q=0.8',
        "Origin": "https://www.staplesadvantage.com",
        "Referer": "https://www.staplesadvantage.com/webapp/wcs/stores/servlet/StplLogon?catalogId=4&langId=-1&storeId=10101"
    }

    SIGNIN = {
        "login-domain": "order",
        "userID": "CANDICE@CONTENTANALYTICSINC.COM",
        "password": "Staples1",
        "companyID": "10201633",
        "URL": "redirect",
        "relogonurl": "salogon",
        "errURL": "salogon"
    }

    def check_url_format(self):
        m = re.match(r"^https?://www.staplesadvantage.com/webapp/wcs/stores/servlet/StplShowItem?.*$", self.product_page_url)
        n = re.match(r"^https?://www.staplesadvantage.com/shop/StplShowItem?.*$", self.product_page_url)
        return bool(m or n)

    def _extract_page_tree(self):
        for i in range(3):
            try:
                with requests.Session() as s:
                    resp = self._request(self.LOGIN_URL, data=self.SIGNIN, verb='post', session=s)

                    if resp.ok:
                        r = self._request(self.product_page_url, session=s, log_status_code=True)
                        self.tree_html = html.fromstring(r.content)
                        return
            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

        self.is_timeout = True

    def not_a_product(self):
        product_section = self.tree_html.xpath('//div[contains(@class,"product-list-container")]')
        return False if product_section else True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        prod_id = self.tree_html.xpath("//div[@class='maindetailitem']//input[@name='currentSKUNumber']/@value")

        if not prod_id:
            prod_id = self.tree_html.xpath("//input[@name='currentSKUNumber']/@value")

        if prod_id:
            return prod_id[0].strip()

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[contains(@class,'search-prod-desc')]//text()[normalize-space()!='']")
        return product_name[0].strip() if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _description(self):
        description = self.tree_html.xpath("//*[contains(@class, 'headliner')]//text()")
        return description[0] if description else None

    def _long_description(self):
        description = self.tree_html.xpath("//*[contains(@class, 'whyBuyProductDetailPage')]//text()")
        return description[0] if description else None

    def _bullets(self):
        bullets = self.tree_html.xpath("//div[contains(@class,'product-details-desc')]//ul/li//text()")
        bullets = [b for b in bullets if self._clean_text(b)]
        if bullets:
            return '\n'.join(bullets)

    def _specs(self):
        specs = {}

        for row in self.tree_html.xpath('//table[@class="specy-table"]//tr'):
            tds = row.xpath('./td/text()')
            if len(tds) > 1:
                specs[tds[0].strip()] = tds[1].strip()

        if specs:
            return specs

    def _upc(self):
        upc = self.tree_html.xpath('//input[@name="upcCode"]/@value')
        return upc[0].strip() if upc else None

    def _no_longer_available(self):
        if self._product_name():
            return 0
        return 1

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//ul[@class="overview"]//li/a/img/@src')
        image_urls = [i + '&hei=570&wid=570&op_sharpen=1' for i in image_urls]

        if image_urls:
            return image_urls

        image_url = re.search("var enlargedImageURL = \\'(.+?)\\'", html.tostring(self.tree_html))

        if image_url:
            return [image_url.group(1)]

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        if self.is_review_checked:
            return self.reviews

        self.reviews_checked = True

        review_list = [[5, 0], [4, 0], [3, 0], [2, 0], [1, 0]]
        review_text = self.tree_html.xpath('//div[@id="star_image"]/@data-histogram')
        review_values = re.findall(r'(\d+)', review_text[0]) if review_text else None

        if not review_values:
            return

        review_count = review_values.pop(0)
        self.review_count = int(review_count)

        average_review = self.tree_html.xpath('//span[@class="starNumbers"]/text()')
        if average_review:
            try:
                self.average_review = float(average_review[0].strip())
            except Exception as e:
                print traceback.format_exc()
                self.average_review = None

        for idx, star in enumerate(review_values):
            if star:
                review_list[idx][1] = int(star)

        self.reviews = review_list
        return self.reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//*[@id='autorepricing']//input[@type='hidden']/@value")
        if not price:
            price = self.tree_html.xpath("//div[contains(@class, 'specialoffer-price')]"
                                         "//span[contains(@class, 'specialoffer-price-color')]/text()")

        return price[0].strip() if price else None

    def _site_online(self):
        if not self._no_longer_available():
            return 1

    def _in_stores(self):
        if not self._no_longer_available():
            return 1

    def _site_online_out_of_stock(self):
        if self._site_online():
            return 0

    def _in_stores_out_of_stock(self):
        if self._in_stores():
            return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//ul[contains(@class,'search-breadcrumb')]//li//text()")
        categories = [self._clean_text(c) for c in categories]
        if categories and categories[0] == 'Home':
            categories = categories[1:]
        if categories:
            return categories

    def _brand(self):
        brand = self.tree_html.xpath("//td[@class='productspeci-value']//text()")
        return brand[0].strip() if brand else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("&nbsp;", " ", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo" : _title_seo,
        "description" : _description,
        "long_description" : _long_description,
        "bullets" : _bullets,
        "specs" : _specs,
        "upc" : _upc,
        "no_longer_available" : _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,

        # CONTAINER : SELLERS
        "price" : _price,
        "in_stores" : _in_stores,
        "site_online" : _site_online,
        "in_stores_out_of_stock" : _in_stores_out_of_stock,
        "site_online_out_of_stock" : _site_online_out_of_stock,

         # CONTAINER : REVIEWS
        "reviews" : _reviews,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
