#!/usr/bin/python

import re
import json
import traceback

from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class SupplyWorksScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://(www.)supplyworks.com/Sku/<product_id>"

    def check_url_format(self):
        m = re.match("https?://(www.)?supplyworks.com/Sku/.*", self.product_page_url)
        return bool(m)

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath('//span[@class="num-crumb" and contains(text(), "Item")]/text()')
        if product_id:
            return re.findall('\d+', product_id[0])[0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[contains(@class, 'margin-top-half-em')]/text()")

        return product_name[0] if product_name else None

    def _description(self):
        description = self.tree_html.xpath("//div[contains(@class, 'sku-details-block')]/p")

        if description:
            return description[0].text_content()

    def _specs(self):
        specs = {}

        for row in self.tree_html.xpath("//div[@data-id='specifications']//tr"):
            spec_name, spec_value = row.xpath('./td/text()')
            specs[spec_name] = spec_value

        return specs if specs else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        try:
            images_info = self._find_between(html.tostring(self.tree_html), 'skuImagesData:', 'sku360Data')
            images = json.loads(images_info.strip()[:-1])
            for image in images:
                image_urls.append(image.get('zoomImageUrl'))

            return image_urls
        except Exception as e:
            print('Error while parsing Image Urls: {}'.format(traceback.format_exc(e)))

    def _video_urls(self):
        video_urls = []
        try:
            videos_info = self._find_between(html.tostring(self.tree_html), 'invodoVideoData:', 'invodoVideoCount')
            videos = json.loads(videos_info.strip()[:-1])
            for video in videos:
                video_url = video.get('ThumbnailUrl').replace('_pre.jpg', '.mp4')
                video_urls.append(video_url)

            return video_urls
        except Exception as e:
            print('Error while parsing Video Urls: {}'.format(traceback.format_exc(e)))

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

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
        categories = self.tree_html.xpath("//div[contains(@class, 'breadcrumbs')]//a/text()")
        return categories[1:] if categories else None

    def _brand(self):
        title = self._product_name()
        brand = re.search('brandName = (.*?);', html.tostring(self.tree_html))
        if brand:
            brand = brand.group(1).replace("\'", "")
        if not brand and title:
            brand = guess_brand_from_first_words(title)

        return brand

    def _sku(self):
        return self._product_id()

    def _upc(self):
        upc = self.tree_html.xpath('//span[@class="num-crumb" and contains(text(), "UPC")]/text()')
        if upc:
            return re.findall('\d+', upc[0])[0]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//span[@data-id='currentPrice']/text()")
        return self._clean_text(price[0]) if price else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "description" : _description,
        "specs" : _specs,

        # CONTAINER : SELLERS
        "price": _price,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "site_online" : _site_online,
        "in_stores" : _in_stores,
        "in_stores_out_of_stock" : _in_stores_out_of_stock,
        "site_online_out_of_stock" : _site_online_out_of_stock,
        "marketplace" : _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        "sku" : _sku,
        "upc" : _upc,
        }
