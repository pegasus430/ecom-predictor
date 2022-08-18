#!/usr/bin/python

import re, requests
from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class CheggScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.chegg.com/.*$"

    def _extract_page_tree(self):
        headers = {
            'User-Agent': self.select_browser_agents_randomly(),
            'accept-language': 'en-US',
            'accept': 'text/html',
            'x-forwarded-for': '172.0.01',
        }

        r = requests.get(self.product_page_url, headers = headers, timeout = 20)

        if self.lh:
            self.lh.add_log('status_code', r.status_code)

        if r.status_code != 200:
            self.ERROR_RESPONSE['failure_type'] = r.status_code
            self.is_timeout = True
            return

        self.tree_html = html.fromstring(r.content)

    def check_url_format(self):
        m = re.match(r"^http://www.chegg.com/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[contains(@itemtype,"http://schema.org/")]')) > 0:
            return False
        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _product_id(self):
        product_id = re.search('"productID":(.*?),', html.tostring(self.tree_html), re.DOTALL).group(1).replace('"', '')
        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath("//span[@itemprop='name']/text()")[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _features(self):
        feature_txts = iter(self.tree_html.xpath("//table[@class='specs-table']//tr/td/text()"))
        features = []
        for k, v in zip(feature_txts, feature_txts):
            if k.strip():
                features.append("%s: %s" % (k.strip(), v.strip()))
        if features:
            return features

    def _description(self):
        short_description = self.tree_html.xpath("//div[@itemprop='description']")[0].text_content().strip()

        if short_description:
            return short_description

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _image_urls(self):
        image_list = []
        image_urls = self.tree_html.xpath("//div[@class='book-thumb-container']"
                                          "/div[contains(@class,'book-img')]"
                                          "/img[@itemprop='image']/@src")[0].replace('//', '')
        image_list.append(image_urls)

        return image_list

    def _no_longer_available(self):
        arr = self.tree_html.xpath('//div[@id="productinfo_ctn"]//div[contains(@class,"error")]//text()')
        if "to view is not currently available." in " ".join(arr).lower():
            return 1
        return 0

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        if self._review_count() > 0:
            return float(self.tree_html.xpath("//span[@itemprop='ratingValue']//text()")[0])

    def _review_count(self):
        review_count = re.findall(
            r'\d+',
            self.tree_html.xpath("//div[contains(@class,'pdpRatingsReviews')]"
                                 "//span[contains(@class,'hilight')]//text()")[0].replace(",", "")
        )

        if review_count:
            return int(review_count[0])

        return 0

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = re.search('"price":(.*?),', html.tostring(self.tree_html), re.DOTALL).group(1).replace('"', '')
        return '$' + price

    def _price_amount(self):
        return float(self._price()[1:])

    def _price_currency(self):
        return "USD"

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath("//div[@itemprop='breadcrumb']/div/a//text()")

        return categories[1:]

    def _brand(self):
        return guess_brand_from_first_words(self._product_name())

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        return re.sub("&nbsp;", " ", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id" : _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "features" : _features, \
        "description" : _description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \
        "no_longer_available" : _no_longer_available, \

        # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "in_stores" : _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores_out_of_stock": _in_stores_out_of_stock, \
        "marketplace" : _marketplace, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "brand" : _brand, \
        }
