#!/usr/bin/python

import itertools
import json
import re
import requests

from lxml import html, etree
import xml.etree.ElementTree as ET
from extract_data import Scraper
from spiders_shared_code.verizonwireless_variants import VerizonWirelessVariants


class VerizonWirelessScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https?://www.verizonwireless.com/<product-category>/<product-name>$"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media
        self.wc_360 = 0
        self.wc_emc = 0
        self.wc_video = 0
        self.wc_pdf = 0
        self.wc_prodtour = 0

        self.features = None
        self.ingredients = None
        self.images = None
        self.videos = None
        self.json_data = None

        self.REVIEW_URL = "http://api.bazaarvoice.com/data/batch.json?passkey=e8bg3vobqj42squnih3a60fui&apiversion=5.5&displaycode=6543-en_us&resource.q0=products&filter.q0=id%3Aeq%3A{0}&stats.q0=questions%2Creviews&filteredstats.q0=questions%2Creviews"

        self.av = VerizonWirelessVariants()

    def check_url_format(self):
        m = re.match('^https?://www.verizonwireless.com/.*$', self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if not (self.tree_html.xpath('//*[@itemtype="http://schema.org/Product"]') \
            or self.tree_html.xpath('//script[@id="accessoryPdpJson"]')):
            return True
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        sku_text = self.tree_html.xpath('//*[@id="sku-id"]/text()')
        if sku_text:
            search_sku = re.search('\#(.*)', sku_text[0])
            return search_sku.group(1).strip() if search_sku else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self._product_title()

    def _product_title(self):
        title = self.tree_html.xpath('//*[@itemprop="name"]/text()')
        return title[0].strip() if title else None

    def _title_seo(self):
        return self._product_title()

    def _model(self):
        model = re.search('deviceModel":"(.*?)"', html.tostring(self.tree_html))
        return model.group(1) if model else None

    def _manufacturer(self):
        model = re.search('deviceManufacturer":"(.*?)"', html.tostring(self.tree_html))
        return model.group(1) if model else None

    def _features(self):
        features = self.tree_html.xpath(
            '//h2[@class="margin36 onlyTopMargin"]/text()')
        features += self.tree_html.xpath(
            '//*[@class="features"]//ul/li/text()')

        features = filter(None, map((lambda x: x.strip()), features))

        return features if features else None

    def _description(self):
        description = self.tree_html.xpath('//*[@id="pdp-ship-details"]//li//text()')

        return ''.join(filter(None, map((lambda x: x.strip()), description))).strip() if description else None

    def _long_description(self):
        desc_head = self.tree_html.xpath('//li[contains(@class, "overview")]//span[@id="pdp-span1"]/text()')
        if 'Description' in desc_head:
            desc = self.tree_html.xpath('//li[contains(@class, "overview")]//'
                                        'div[contains(@class, "pdp-overview-content")]//p[@id="pdp-p1"]')

            return self._clean_text(html.tostring(desc[0])) if desc else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _load_json_data(self):
        image_urls = self.tree_html.xpath(
            '//*[@property="og:image"]/@content')[0].split('?')[0]
        image_urls += "-mms?req=set,json,UTF-8&labelkey=label"
        image_urls = image_urls.replace('-iset', '')
        response = requests.get(image_urls, timeout=10)
        json_text = re.findall('s7jsonResponse\((.*),"', response.text)
        self.json_data = json.loads(json_text[0])

    def _image_urls(self):
        if self.images:
            return self.images

        self.images = []

        try:
            main_image_url = self.tree_html.xpath('//input[@id="MainProductImageURL"]/@value')[0].split('?')[0]

            c = requests.get(main_image_url + '?req=set').content
            x = ET.fromstring(c)

            for item in x:
                self.images.append('https://ss7.vzw.com/is/image/' + item[0].get('n') + '?scl=1')

            if self.images:
                return self.images

        except:
            pass

        try:
            if not self.images:
                if not self.json_data:
                    self._load_json_data()

                data = self.json_data.get('set', {})
                self.images = []
                images = []
                if data.get('type', None) == 'media_set':
                    try:
                        images += list(itertools.chain.from_iterable([x.get(
                            'set', {}).get('item') for x in data[
                                'item'] if x.get('type') == 'img_set']))
                        images = [x for x in data['item'] if x.get('dx')] + images

                    except:
                        data = self.json_data['set']['item']

                if data.get('set', {}).get('type', None) == 'img_set':
                    images += data.get('set', {}).get('item', [])

                for img in images:
                    self.images.append(
                        "https://ss7.vzw.com/is/image/" + img['i']['n'] + '?scl=1')

        except:
            self.images = [self.tree_html.xpath(
                '//*[@property="og:image"]/@content')[0].split('?')[0]]

        return self.images if self.images else [self.tree_html.xpath(
            '//*[@property="og:image"]/@content')[0].split('?')[0]]

    def _video_urls(self):
        if not self.videos:
            if not self.json_data:
                self._load_json_data()

            data = self.json_data.get('set', {})
            videos = []

            if data.get('type', None) == 'media_set':
                try:
                    videos += [x.get('set', {}).get('item', [])[-1] for x in data['item'] if x.get('type')=='video_set']
                    videos += [x for x in data['item'] if x.get('type') == 'video']
                except:
                    pass

            self.videos = []
            for video in videos:
                self.videos.append(
                    "https://ss7.vzw.com/is/content/" + video['i']['n'])

        return self.videos

    def _webcollage(self):
        """Uses video and pdf information
        to check whether product has any media from webcollage.
        Returns:
            1 if there is webcollage media
            0 otherwise
        """
        if self.wc_360 + self.wc_emc + self.wc_pdf + self.wc_prodtour + self.wc_video > 0:
            return 1

        return 0

    def _wc_360(self):
        if not self.json_data:
            self._load_json_data()

        try:
            data = self.json_data.get('set', {})
            self.wc_360 = 1 if len(filter((lambda x: x.get('type') == 'spin'),
                                   data.get('item'))) else 0
        except:
            self.wc_360 = 0

        return self.wc_360

    def _wc_emc(self):
        self._webcollage()

        return self.wc_emc

    def _wc_pdf(self):
        self._webcollage()

        return self.wc_pdf

    def _wc_prodtour(self):
        self._webcollage()

        return self.wc_prodtour

    def _wc_video(self):
        self._webcollage()

        return self.wc_video

    def _variants(self):
        self.av.setupCH(self.tree_html)
        return self.av._variants()

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _reviews(self):
        device_prod_id = re.search('deviceProdId=(.*?)&', html.tostring(self.tree_html))

        if device_prod_id:
            prod_id = device_prod_id.group(1)
        else:
            prod_id = self.tree_html.xpath('//input[@id="isProductId"]/@value')[0]

        review_url = self.REVIEW_URL.format(prod_id)

        return super(VerizonWirelessScraper, self)._reviews(review_url = review_url)

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _in_stock(self):
        in_stock = self.tree_html.xpath(
            '//*[@itemprop="availability" and @href="//schema.org/InStock"]')
        return int(bool(in_stock))

    def _price(self):
        price_amount = self._price_amount()
        return '$' + price_amount if price_amount else None

    def _price_amount(self):
        price_amount = self.tree_html.xpath('//div[contains(@class,"actual-price")]/@content')
        return price_amount[0] if price_amount else None

    def _price_currency(self):
        currency = self.tree_html.xpath('//*[@itemprop="priceCurrency"]/@content')
        return currency[0] if currency else None

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        availability = self.tree_html.xpath('//link[@itemprop="availability"]/@href')[0]
        return 1 if availability != 'http://schema.org/InStock' else 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        devices = ['/tablets/', '/smartphones/', '/basic-phones/']
        url = self.product_page_url
        categories = self.tree_html.xpath(
            '//*[@itemtype="https://data-vocabulary.org/Breadcrumb"]'
            '//span[@itemprop="title"]/text()')
        if categories and any([x in url for x in devices]):
            categories.insert(1, 'Devices')
        return categories

    def _brand(self):
        brand = self.tree_html.xpath('//*[@itemprop="brand"]/text()')
        return brand[0].strip() if brand else None

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
        "manufacturer": _manufacturer,
        "features": _features,
        "description": _description,
        "long_description": _long_description,
        "variants": _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,
        "wc_360": _wc_360,
        "wc_emc": _wc_emc,
        "wc_video": _wc_video,
        "wc_pdf": _wc_pdf,
        "wc_prodtour": _wc_prodtour,
        "webcollage": _webcollage,

        # CONTAINER : REVIEWS
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "in_stock": _in_stock,
        "price": _price,
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
