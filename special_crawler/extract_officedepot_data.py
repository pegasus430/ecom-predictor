#!/usr/bin/python

import re
import json
import urllib

from lxml import html
from extract_data import Scraper
from spiders_shared_code.officedepot_variants import OfficedepotVariants


class OfficeDepotScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.officedepot.com/a/products/<product-id>/<product-name>/"

    REVIEW_URL = "http://officedepot.ugc.bazaarvoice.com/2563/{0}/reviews.djs?format=embeddedhtml"

    VARIANTS_URL = 'http://www.officedepot.com/mobile/getSkuAvailable' \
                   'Options.do?familyDescription={name}&sku={sku}&noLogin=true'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.ov = OfficedepotVariants()
        self.variant_json = None

    def check_url_format(self):
        m = re.match(r"^https?://www\.officedepot\.com/a/products/[0-9]+(/.*)?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        self.ov.setupCH(self.tree_html)
        self.extract_variants_json()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def extract_variants_json(self):
        try:
            sku = self.tree_html.xpath('//input[@name="id"]/@value')[0]
            name = self.tree_html.xpath('//h1[@itemprop="name"]/text()')[0].split(',')[0]
            name = urllib.quote_plus(name.strip().encode('utf-8'))
            VARIANTS_URL = 'http://www.officedepot.com/mobile/getSkuAvailable' \
                           'Options.do?familyDescription={name}&sku={sku}&noLogin=true'
            self.variant_json = self._request(url=VARIANTS_URL.format(name=name, sku=sku)).json()
            return self.variant_json
        except:
            self.variant_json = None

    def _product_id(self):
        return re.search('products/(\d+)', self.product_page_url).group(1)

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath('//h1/text()')[0].strip()

    def _features(self):
        features_tr_list = self.tree_html.xpath('//section[@id="productDetails"]//table[@class="data tabDetails gw9"]//tbody//tr')
        features_list = []

        for tr in features_tr_list:
            features_list.append(tr.xpath(".//td")[0].text_content().strip() + ": " + tr.xpath(".//td")[1].text_content().strip())

        if features_list:
            return features_list

    def _description(self):
        description_block = self.tree_html.xpath("//div[@class='sku_desc show']")[0]
        short_description = ""

        for description_item in description_block:
            if description_item.tag == "ul":
                break

            if description_item.tag != "p":
                continue

            short_description = short_description + html.tostring(description_item)

        short_description = self._clean_text(short_description.strip())

        if short_description:
            return short_description

    def _long_description(self):
        description_block = self.tree_html.xpath("//div[@class='sku_desc show']")[0]
        long_description = ""
        long_description_start = False

        for description_item in description_block:
            if description_item.tag == "ul":
                long_description_start = True

            if long_description_start:
                long_description = long_description + html.tostring(description_item)

        long_description = self._clean_text(long_description.strip())

        if long_description:
            return long_description

    def _variants(self):
        return self.ov._variants(self.variant_json)

    def _item_num(self):
        item_num = self.tree_html.xpath('//*[@id="skuId"]/text()')[0]
        return item_num

    def _no_longer_available(self):
        if self.tree_html.xpath('//div[contains(@class,"no_longer_avail")]'):
            return 1
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_list = []

        if self.tree_html.xpath('//script[@id="skuImageData"]/text()'):
            image_data = self.tree_html.xpath('//script[@id="skuImageData"]/text()')[0]
            image_data = json.loads(image_data)
            image_len = len(image_data)
            for i in range(image_len):
                image_url = 'http://s7d1.scene7.com/is/image/officedepot/' + image_data['image_' + str(i)]
                image_list.append(image_url)
        else:
            main_image_url = self.tree_html.xpath("//img[@id='mainSkuProductImage']/@src")[0]
            main_image_url = main_image_url[:main_image_url.rfind("?")]
            image_list = [main_image_url]

        if image_list:
            return image_list

    def _video_urls(self):
        video_urls = []

        resource_base = re.search('data-resources-base="([^"]+)"', html.tostring(self.tree_html))
        if resource_base:
            resource_base = resource_base.group(1)[:-1] # remove trailing '/'

        wc_json = self.tree_html.xpath('//div[contains(@class,"wc-json-data")]/text()')

        if wc_json:
            wc_json = json.loads(wc_json[0])

            for video in wc_json['videos']:
                video_urls.append( resource_base + video['src']['src'])

        if video_urls:
            return video_urls

    def _video_count(self):
        videos = self._video_urls()

        embedded_videos = self.tree_html.xpath('//span[@class="LimelightEmbeddedPlayer"]')

        if videos:
            return len(videos) + len(embedded_videos)

        else:
            return len(embedded_videos)

    def _pdf_urls(self):
        urls = []

        pops = map( lambda x: x.get('href'), self.tree_html.xpath('//ul[@class="sku_icons"]/li/a'))
        for pop in pops:
            category = re.search( '/([^/]+)\.do', pop ).group(1).lower()
            id = re.search( '\?id=(\d+)', pop ).group(1)
            urls.append('http://www.officedepot.com/pdf/%s/%s.pdf' % (category, id))

        if urls:
            return urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//meta[@itemprop='price']/@content")
        if not price:
            price = self.tree_html.xpath(
                "//div[contains(@class, 'red_price')]"
                "//span[contains(@class, 'right')]/text()"
            )

        return price[0] if price else None

    def _temp_price_cut(self):
        if self.tree_html.xpath('//div[@class="unified_price_row unified_reg_price"]'):
            return 1
        return 0

    def _in_stores(self):
        if not self._no_longer_available():
            sold_in_stores = self.tree_html.xpath("//div[@class='soldInStores']")

            if sold_in_stores and \
                    "sold in stores" in sold_in_stores[0].text_content().lower():
                return 1
            return 0

    def _site_online(self):
        if not self._no_longer_available():
            return 1

    def _site_online_out_of_stock(self):
        if self._site_online():
            delivery_message = self.tree_html.xpath("//div[@class='deliveryMessage']")

            if delivery_message and \
                    "out of stock for delivery" in delivery_message[0].text_content().lower():
                return 1
            return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//div[@id='siteBreadcrumb']//li//span[@itemprop='name']/text()")
        if len(categories) > 1:
            return categories[1:]

    def _brand(self):
        return self.tree_html.xpath("//td[@id='attributebrand_namekey']/text()")[0].strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "features" : _features,
        "description" : _description,
        "item_num" : _item_num,
        "long_description" : _long_description,
        "variants" : _variants,
        "no_longer_available" : _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_count" : _video_count,
        "video_urls" : _video_urls,
        "pdf_urls" : _pdf_urls,

        # CONTAINER : SELLERS
        "price" : _price,
        "temp_price_cut": _temp_price_cut,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace" : _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
