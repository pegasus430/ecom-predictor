#!/usr/bin/python

import re
import requests
import traceback
import HTMLParser
from lxml import html

from extract_data import Scraper


class RiteAidScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://shop.riteaid.com/<product-name>-<skuid> or " \
                            "http(s)://(www.)riteaid.com/shop/<product-name>-<skuid>"

    REVIEW_URL = "http://api.bazaarvoice.com/data/reviews.json?apiversion=5.4" \
                    "&passkey=tezax0lg4cxakub5hhurfey5o&Filter=ProductId:{}" \
                    "&Include=Products&Stats=Reviews"

    def check_url_format(self):
        m = re.match('https?://shop.riteaid.com/.+-\d+', self.product_page_url)
        n = re.match('https?://(www.)?riteaid.com/shop/.+-\d+', self.product_page_url)
        return bool(m or n)

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def not_a_product(self):
        if not self.tree_html.xpath('//div[@itemtype="http://schema.org/Product"]'):
            return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.tree_html.xpath('//meta[@itemprop="sku"]/@content')[0]

    def _site_id(self):
        return self._product_id()

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath('//span[@itemprop="name"]/text()')[0]

    def _product_title(self):
        return self.tree_html.xpath('//title/text()')[0]

    def _title_seo(self):
        return self._product_title()

    def _model(self):
        model = self.tree_html.xpath('//th[text()="Model"]/following-sibling::td/text()')

        if model:
            return model[0]

    def _features(self):
        features = self.tree_html.xpath('//div[@class="std"]/ul')
        if features:
            return self._clean_text(html.tostring(features[0]))

    def _feature_count(self):
        features = self._features()

        if features:
            return len(features.split('</li><li>'))

    def _description(self):
        description = ''

        for element in self.tree_html.xpath('//dd[@class="tab-container"]')[0].xpath("./*"):
            if not element.text_content():
                continue

            description += self._clean_html(html.tostring(element))

        if description:
            return description

    def _long_description(self):
        description = ''

        if description:
            if description != self._description():
                return description

    def _ingredients(self):
        stds = self.tree_html.xpath('//div[@class="std"]')

        if len(stds) > 3:
            ingredients = stds[2].text_content().split(',')

            ingredients = map(lambda x: self._clean_text(x), ingredients)
            ingredients = filter(len, ingredients)

            if ingredients:
                return ingredients

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        images = []

        image_urls = self.tree_html.xpath('//div[@class="images"]//img/@src')

        for image in image_urls:
            is_video_image = False

            # Do not include video images
            for video_image in self.tree_html.xpath('//a[@data-colorbox="video"]/@style'):
                if image.split('/')[-1] in video_image:
                    is_video_image = True
                    break

            if is_video_image:
                continue

            if '/media/catalog/product' in image and not image in images:
                images.append(image)

        if images:
            return images

    def _video_urls(self):
        videos = []

        video_urls = self.tree_html.xpath('//a[@data-colorbox="video"]/@href')

        for video in video_urls:
            if not video in videos:
                videos.append(video)

        if videos:
            return videos

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        if not self.is_review_checked:
            self.is_review_checked = True

            try:
                sku = self.tree_html.xpath('//meta[@itemprop="sku"]/@content')[0]

                reviews_json = requests.get(self.REVIEW_URL.format(sku), timeout=10).json()

                reviews = reviews_json.get("Includes", {}).get("Products", {}) \
                                .get(sku, {}).get("ReviewStatistics", {})

                self.review_count = reviews['TotalReviewCount']

                if self.review_count:
                    self.average_review = reviews['AverageOverallRating']

                    self.reviews = []

                    for i in range(5, 0, -1):
                        review_found = False

                        for review in reviews['RatingDistribution']:
                            if review['RatingValue'] == i:
                                self.reviews.append([i, review['Count']])
                                review_found = True

                        if not review_found:
                            self.reviews.append([i, 0])

            except:
                print traceback.format_exc()

        return self.reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        return self.tree_html.xpath('//span[@class="price"]/text()')[0]

    def _price_currency(self):
        return self.tree_html.xpath('//meta[@itemprop="priceCurrency"]/@content')[0]

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self.tree_html.xpath('//link[@itemprop="availability"]/@href')[0] == 'http://schema.org/OutOfStock':
            return 1

        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = []

        for category in self.tree_html.xpath('//meta[@itemprop="category"]/@content')[0].split(' > '):
            if category and category not in categories:
                categories.append(category)

        return categories

    def _brand(self):
        brand = re.search('brand": "([^"]+)"', html.tostring(self.tree_html))

        if brand:
            return brand.group(1)

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        text = HTMLParser.HTMLParser().unescape(text)
        text = re.sub('[\r\n]', '', text)
        return text.strip()

    def _clean_html(self, html):
        html = re.sub('<(\w+)[^>]*>', r'<\1>', html)
        return self._clean_text(html)

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id" : _product_id, \
        "site_id" : _site_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "model" : _model, \
        "features" : _features, \
        "feature_count" : _feature_count, \
        "description" : _description, \
        "long_description" : _long_description, \
        "ingredients" : _ingredients, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \
        "video_urls" : _video_urls, \

        # CONTAINER : REVIEWS
        "reviews" : _reviews, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "price_currency" : _price_currency, \
        "in_stores" : _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "marketplace" : _marketplace, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "brand" : _brand, \
        }
