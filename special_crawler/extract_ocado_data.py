# -*- coding: utf-8 -*-
#!/usr/bin/python

import re
import json
import requests
import urlparse

from lxml import html
from extract_data import Scraper
from spiders_shared_code.ocado_variants import OcadoVariants


class OcadoScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https://www.ocado.com/webshop/product/<product-name>/<product-id>"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.ov = OcadoVariants()

    def check_url_format(self):
        m = re.match(r"^https://www.ocado.com/webshop/product/.*", self.product_page_url)
        return bool(m)

    def _extract_page_tree(self):
        with requests.Session() as s:
            s.get('https://www.ocado.com/webshop/startWebshop.do')
            self._extract_page_tree_with_retries(session=s)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')[0].strip()

        if itemtype != "product":
            return True

        self.ov.setupCH(self.tree_html)
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self._find_between(html.tostring(self.tree_html), 'PID = ', ';').strip().replace("'", "")

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_title = self.tree_html.xpath("//h1[@class='productTitle']")
        if product_title:
            product_title = ' '.join([t.strip() for t in product_title[0].itertext() if t.strip()])
            return re.sub('Offer - ', '', product_title)

    def _product_title(self):
        product_title = self.tree_html.xpath("//title/text()")

        return self._clean_text(product_title[0]) if product_title else None

    def _title_seo(self):
        return self.tree_html.xpath("//meta[@property='og:title']/@content")[0].strip()

    def _description(self):
        short_description = self.tree_html.xpath(
            "//div[@class='bopSection']"
            "//div[@class='description']/descendant::text()"
        )
        short_description = '\n'.join(short_description)

        return short_description

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        images = self.tree_html.xpath(
            "//ul[@id='galleryImages']"
            "//li[contains(@class, 'zoomable')]//a/@href"
        )
        domain = 'https://www.ocado.com'
        for image in images:
            image_urls.append(urlparse.urljoin(domain, image))

        return image_urls if image_urls else None

    def _video_urls(self):
        try:
            videos_info = html.tostring(self.tree_html.xpath("//ul[@id='galleryVideos']")[0])
        except:
            return None

        video_urls = []
        videos_wrapper = html.fromstring(videos_info.replace('<!--', '').replace('-->', ''))
        videos = videos_wrapper.xpath("//li//iframe/@src")
        for video in videos:
            video_urls.append(urlparse.urljoin('https:', video))

        return video_urls if video_urls else None

    def _variants(self):
        return self.ov._variants()

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        if self._review_count() == 0:
            return None

        average_review = self.tree_html.xpath("//*[@id='rating']/@title")
        try:
            average_review = average_review[0].split('out')[0]
            return float(average_review)
        except:
            return None

    def _review_count(self):
        review_count_info = self.tree_html.xpath("//span[@class='reviewCount']/text()")
        try:
            review_count = re.findall(r'(\d+)', review_count_info[0])[0]
            return int(review_count)
        except:
            return None

    def _reviews(self):
        rating_star_list = self.tree_html.xpath(
            "//ul[@class='snapshotList']"
            "//li//span[@class='reviewsCount']/text()")

        if rating_star_list:
            review_list = [[1, 0], [2, 0], [3, 0], [4, 0], [5, 0]]

            for i in range(0, 5):
                try:
                    review_list[i][1] = int(re.findall(r'\d+', rating_star_list[4 - i])[0])
                except:
                    review_list[i][1] = 0

            return review_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        return "£{:.2f}".format(self._price_amount())

    def _price_amount(self):
        price = self.tree_html.xpath("//meta[@itemprop='price' and not(@content='0.00')]/@content")[0]

        return float(price)

    def _price_currency(self):
        return self.tree_html.xpath("//meta[@itemprop='priceCurrency']/@content")[0]

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return int(bool(self.tree_html.xpath('//meta[@itemprop="availability" and contains(@content, "OutOfStock")]')))

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//ul[@class="categories"]/li[1]//a/text()')
        categories = filter(None, [i.strip() for i in categories])
        return categories

    def _brand(self):
        brand = self.tree_html.xpath(
            "//span[@itemprop='brand']//span[@itemprop='name']/text()"
        )
        if brand:
            brand = self._clean_text(brand[0])

        return brand

    def _sku(self):
        product_info = self._product_json()
        try:
            sku = product_info['sku']
            return sku
        except:
            return None

    def _ingredients(self):
        header = self.tree_html.xpath('//h3[text()="Ingredients"]')
        if header:
            header = header[0]
            for sib in header.itersiblings():
                if 'Allergy Advice' in sib.text_content():
                    continue
                else:
                    try:
                        ingredients = re.match('<[^>]*>(.*)<[^>]*>$', html.tostring(sib).strip()).group(1)
                    except:
                        ingredients = sib.text_content()

                    if ingredients.strip():
                        return [i.strip() for i in ingredients.split(',')]

    def _nutrition_facts(self):
        nutrition_facts = []
        nut_info = self.tree_html.xpath("//table[@class='nutrition']//tr")
        for data in nut_info:
            if '<td>' in html.tostring(data):
                nutrition_facts.append(': '.join(data.xpath('.//td/text()')))

        return nutrition_facts

    def _warnings(self):
        warnings = self.tree_html.xpath("//div[@id='bopBottom']//div['@bobSection']//p/text()")
        for data in warnings:
            if 'Contains Barley' in data:
                return data

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _product_json(self):
        product_info = self._find_between(html.tostring(self.tree_html), 'like">', '</script>').strip()
        try:
            return json.loads(product_info)
        except:
            return None

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
        "description": _description,
        "sku": _sku,
        "ingredients": _ingredients,
        "warnings": _warnings,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,
        "variants": _variants,

        # CONTAINER : REVIEWS
        "review_count": _review_count,
        "average_review": _average_review,
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price": _price,
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
