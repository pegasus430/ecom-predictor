#!/usr/bin/python

import re
import requests

from extract_data import Scraper


class CarrefourFrScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.rueducommerce.fr/produit/<product-name>"

    REVIEW_URL = 'https://api.bazaarvoice.com/data/batch.json?passkey=h5ixpqaqihdrrlt3vfc452td8&apiversion=5.5' \
                  '&displaycode=19395-fr_fr&resource.q0=reviews&filter.q0=rating%3Aeq%3A5&filter.q0=isratingsonly' \
                  '%3Aeq%3Afalse&filter.q0=productid%3Aeq%3A{review_id}&filter.q0=contentlocale%3Aeq%3Afr_FR' \
                  '&sort.q0=submissiontime%3Adesc&stats.q0=reviews&filteredstats.q0=reviews&include.q0=authors' \
                  '%2Cproducts%2Ccomments'

    def check_url_format(self):
        m = re.match(r"^https?://www.rueducommerce.fr/produit/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if not self.tree_html.xpath("//meta[@property='og:type' and @content='rue-du-commerce:product']"):
            return True

        self._extract_review_json()
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_review_json(self):
        self.review_id = self.tree_html.xpath('//div[@id="BVRRContainer"]/@data-mpid')
        if self.review_id:
            self.review_id = self.review_id[0]
        try:
            url = self.REVIEWS_URL.format(review_id=self.review_id)
            contents = requests.get(url, timeout=5).json()

            if contents:
                self.reviews_json = contents['BatchedResults']['q0']['Includes']
        except:
            self.reviews_json = None

    def _product_id(self):
        product_id = self.product_page_url.split('#')
        if product_id:
            product_id = product_id[0].split('-')
        return product_id[-1] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//div[@class='productDetails']//span[@itemprop='name']/text()")
        return ' '.join(product_name) if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _model(self):
        return self._product_id()

    def _description(self):
        short_description = self.tree_html.xpath("//p[@class='productDescText']/text()")
        return short_description[0] if short_description else None

    def _long_description(self):
        long_description = self.tree_html.xpath("//div[@id='blocDescriptionContent']//p/text()")
        if not long_description:
            long_description = self.tree_html.xpath("//div[@id='blocDescriptionContent']/text()")
        return ''.join(long_description) if long_description else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath("//li[@class='thumb']//a//img/@src")
        return image_urls if image_urls else None

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        reviews = []
        ratings_distribution = None

        if self.reviews_json:
            if self.review_id in self.reviews_json['Products']:
                ratings_distribution = self.reviews_json['Products'][self.review_id]['ReviewStatistics'][
                    'RatingDistribution']
                self.review_count = self.reviews_json['Products'][self.review_id]['ReviewStatistics'][
                    'TotalReviewCount']
                self.average_review = round(
                    self.reviews_json['Products'][self.review_id]['ReviewStatistics']['AverageOverallRating'], 1)

        if ratings_distribution:
            for i in range(0, 5):
                ratingFound = False

                for rating in ratings_distribution:
                    if rating['RatingValue'] == i + 1:
                        reviews.append([rating['RatingValue'], rating['Count']])
                        ratingFound = True
                        break

                if not ratingFound:
                    reviews.append([i + 1, 0])

            return reviews[::-1]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath("//div[contains(@class, 'main')]//meta[@itemprop='price']/@content")
        return float(price[0].replace(',', '.')) if price else None

    def _price_currency(self):
        price_currency = self.tree_html.xpath("//meta[@itemprop='priceCurrency']/@content")
        return price_currency[0] if price_currency else 'EUR'

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//a[@itemprop='item']//span/text()")
        return categories if categories else None

    def _brand(self):
        brand = self.tree_html.xpath("//span[@itemprop='brand']//span/text()")
        return brand[0] if brand else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "model": _model,
        "description": _description,
        "long_description": _long_description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : REVIEWS
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand
        }
