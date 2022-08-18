#!/usr/bin/python

import re
import requests
from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class HebScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.heb.com/product-detail/<product-name>/<product-id>"
    REVIEW_URL = 'https://heb.ugc.bazaarvoice.com/9846products/{}/reviews.djs?format=embeddedhtml'

    def check_url_format(self):
        m = re.match("https?://www.heb.com/product-detail/.*", self.product_page_url)
        return bool(m)

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//input[@id='productId']/@value")
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@itemprop='name']/text()")
        if not product_name:
            product_name = self.tree_html.xpath("//input[@id='contentName']/@value")
        return product_name[0] if product_name else None

    def _description(self):
        desc = ''
        for div in self.tree_html.xpath('//div[@class="pdp-product-desc"]/div'):
            if div.xpath('./*[@itemprop="description"]'):
                for elem in div.xpath('.//*'):
                    if 'clearfix' in elem.xpath('./@class'):
                        break
                    elif elem.tag == 'p':
                        desc += elem.text_content() + '\n'
        return desc if desc else None

    def _ingredients(self):
        for div in self.tree_html.xpath('//div[@class="pdp-product-desc"]/div'):
            if div.xpath('./*[@itemprop="description"]'):
                for elem in div.xpath('.//*'):
                    if 'Ingredients' in elem.text_content():
                        ingredients = re.sub('Ingredients', '', elem.text_content())
                        return [i.strip() for i in ingredients.split(',')]

    def _specs(self):
        specs = {}

        for row in self.tree_html.xpath('//table[@class="pdp-product-desc_specs"]//tr'):
            spec_name_value = row.xpath('./td/text()')

            if spec_name_value and len(spec_name_value) == 2:
                specs[spec_name_value[0]] = spec_name_value[1]

        return specs if specs else None

    def _nutrition_fact_count(self):
        return len(self.tree_html.xpath('//dl[@class="nutrition-facts"]//table//tr'))

    ###########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ###########################################

    def _image_urls(self):
        image_url_list = []
        image_url = "https://images.heb.com/is/image/HEBGrocery/{image_id}-{index}"
        first_image = self.tree_html.xpath("//meta[@property='og:image']/@content")
        image_id = re.search('(\d+)', first_image[0], re.DOTALL).group(1)
        for i in range(1, 10):
            image = image_url.format(image_id=image_id, index=i)
            response = requests.get(image, timeout=10)
            if len(response.content) == 6227:
                break
            image_url_list.append(image)

        if not image_url_list:
            image_url_list.append(first_image[0])

        return image_url_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath("//meta[@itemprop='price']/@content")
        return float(price[0]) if price else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock = re.search(
            r'var priceObj = \{"isAddtoCartDisable" : \'(.*?)\'', html.tostring(self.tree_html)
        )
        if stock:
            return 1 if 'disabled' in stock.group(1) and self.tree_html.xpath('//button[@id="add-to-cart-button"]') else 0
        return 0


    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        if self._review_count():
            average_review = self.tree_html.xpath("//meta[@itemprop='ratingValue']/@content")
            if average_review and average_review[0]:
                return float(average_review[0])

    def _review_count(self):
        review_count = self.tree_html.xpath("//meta[@itemprop='reviewCount']/@content")

        if review_count and review_count[0]:
            return int(review_count[0])

        return 0

    def _reviews(self):
        if self._average_review():
            return super(HebScraper, self)._reviews()

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        return guess_brand_from_first_words(self._product_name())

    def _categories(self):
        categories = self.tree_html.xpath("//div[@class='breadcrumb clearfix']//a/@title")
        return categories[2:-1] if categories else None

    def _sku(self):
        sku = self.tree_html.xpath("//input[@id='defaultChildSku']/@value")
        return sku[0] if sku and sku[0] else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_name,
        "description": _description,
        "ingredients": _ingredients,
        "specs": _specs,
        "nutrition_fact_count": _nutrition_fact_count,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : REVIEWS
        "average_review": _average_review,
        "review_count": _review_count,
        "reviews": _reviews,

        # CONTAINER : CLASSIFICATION
        "brand": _brand,
        "categories": _categories,
        "sku": _sku,
        }
