#!/usr/bin/python

import re
import HTMLParser
import json
import requests
from urlparse import urljoin
from urllib import quote

from lxml import html, etree
from extract_data import Scraper


class ATTScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.att.com/.*.html(?)(#sku=sku<skuid>)"

    REVIEW_URL = 'https://api.bazaarvoice.com/data/batch.json?passkey=9v8vw9jrx3krjtkp26homrdl8&apiversion=5.5&displaycode=4773-en_us&resource.q0=products&filter.q0=id%3Aeq%3Asku{0}&stats.q0=questions%2Creviews'

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.videos = None
        self.videos_checked = False

        self.variants = None
        self.variants_checked = False

        self.pricearea_html = None
        self.pricearea_html_checked = False

        self.product_xml = None
        self.product_xml_checked = False

        self.product_details = None
        self.product_details_checked = False

    def check_url_format(self):
        m = re.match('^https?://www.att.com/.*\.html\??(#sku=sku\d+)?$', self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if not self.tree_html.xpath('//div[@itemtype="http://schema.org/Product"]'):
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        id_xpath = [
            '//span[@id="skuIDToDisplay"]/text()',
            '//meta[@itemprop="sku"]/@content'
        ]
        for path in id_xpath:
            product_id = self.tree_html.xpath(path)
            if product_id:
                return re.findall('sku(\d+)', product_id[0])[0]

        return re.findall('sku(\d+)', html.tostring(self.tree_html))[0]

    def _site_id(self):
        return self._product_id()

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _get_pricearea_html(self):
        if not self.pricearea_html_checked:
            self.pricearea_html_checked = True

            url = re.match('(.*).html.*', self.product_page_url).group(1) + '.pricearea.xhr.html?locale=en_US&skuId=sku' + self._product_id() + '&pageType=accessoryDetails&_=1461605909259'

            self.pricearea_html = html.fromstring( self.load_page_from_url_with_number_of_retries(url))

        return self.pricearea_html

    def _get_product_xml(self):
        if not self.product_xml_checked:
            self.product_xml_checked = True

            response = requests.get('https://www.att.com/shop/360s/xml/' + self._product_id() + '.xml')

            if response.status_code == 200:
                self.product_xml = etree.XML(response.content.replace(' encoding="UTF-8"', '').replace('&', '&amp;'))

        return self.product_xml

    def _get_product_details(self):
        if not self.product_details_checked:
            self.product_details_checked = True

            try:
                product_details = json.loads( self.load_page_from_url_with_number_of_retries('https://www.att.com/services/shopwireless/model/att/ecom/api/DeviceDetailsActor/getDeviceProductDetails?includeAssociatedProducts=true&includePrices=true&skuId=sku' + self._product_id()))
                self.product_details = product_details['result']['methodReturnValue']

            except:
                pass

        return self.product_details

    def _product_name(self):
        return self.tree_html.xpath('//meta[@itemprop="name"]/@content')[0]

    def _product_title(self):
        return self.tree_html.xpath('//meta[@property="og:title"]/@content')[0]

    def _title_seo(self):
        return self._product_title()

    def _upc(self):
        product_id = self.tree_html.xpath('//meta[@itemprop="productID"]/@content')[0]
        return re.match('upc:(.+)', product_id).group(1)

    def _description(self):
        return self.tree_html.xpath('//meta[@property="og:description" or @name="og:description"]/@content')[0]

    def _variants(self):
        if self.variants_checked:
            return self.variants

        self.variants_checked = True
        variants = []
        if self._get_product_details():
            for skuItem in self.product_details['skuItems'].values():
                price = self._get_price(skuItem['priceList'])[0]
                size = skuItem.get('size')
                if price:
                    price = float(price[1:])
                variant = {
                    "in_stock": skuItem['outOfStock'],
                    "price": price,
                    "properties": {
                        "color": skuItem['color'],
                    },
                    "selected": skuItem['selectedSku'],
                }
                if size:
                    variant['properties']['size'] = size
                variants.append(variant)

        else:
            for variant_html in self._get_pricearea_html().xpath('//span[@id="colorInput"]/a'):
                in_stock = self.pricearea_html.xpath('//div[@id="deliveryPromise"]/@data-outofstock')[0] == 'false'
                price = self.pricearea_html.xpath('//div[@id="dueToday"]/div[contains(@class,"price")]/text()')
                price = self._clean_text(price[0]) if price else None
                variant = {
                    "in_stock": in_stock,
                    "price": price,
                    "properties": {
                        "color": variant_html.get('title'),
                    },
                    "selected": 'current' in variant_html.get('class'),
                }
                variants.append(variant)

        if variants:
            self.variants = variants

        return self.variants

    @staticmethod
    def _compose_img_urls(item):
        manufacturer = item['manufacturer']
        if manufacturer.count('BlackBer') > 0:
            manufacturer = 'BlackBerry'

        model = item['model']
        bill_code = item['billCode'].lower()
        color = item['color']

        if not model:
            full_product = manufacturer + " " + item['productDisplayName']
        else:
            full_product = manufacturer + " " + model

        base_path = "/catalog/en/skus/" + manufacturer + "/" + full_product + "/hi_res_images/"
        base_path = base_path.strip()

        if not model:
            hires_img = base_path + bill_code + "-hero.jpg"
            hires_zoom_img = base_path + bill_code + "-hero-zoom.jpg"
        else:
            hires_img = base_path + color.lower() + "-hero.jpg"
            hires_zoom_img = base_path + color.lower() + "-hero-zoom.jpg"

        hires_img = urljoin('https://www.att.com', quote(hires_img))
        hires_zoom_img = urljoin('https://www.att.com', quote(hires_zoom_img))

        return {
            'hires_img': hires_img,
            'hires_zoom_img': hires_zoom_img
        }

    def _get_swatch(self, item):
        img_urls = self._compose_img_urls(item)
        return {
            "color": item['color'],
            "swatch_name": "color",
            "hero_image": [img_urls['hires_img']],
            "hero": 1
        }

    def _swatches(self):
        swatches = []
        if self._get_product_details():
            for sku, item in self.product_details['skuItems'].items():
                swatches.append(
                    self._get_swatch(item)
                )
        if swatches:
            return swatches

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        images = []
        if self._get_product_xml():
            for image in self.product_xml.xpath('//image_info'):
                images.append('https://www.att.com' + image.get('path') + image.get('suffix'))

        if self._get_product_details():
            for sku, item in self.product_details['skuItems'].items():
                if sku.endswith(self._product_id()):
                    img_urls = self._compose_img_urls(item)
                    if img_urls.get('hires_img'):
                        images.append(img_urls['hires_img'])

        if images:
            return images

    def _video_urls(self):
        if self.videos_checked:
            return self.videos

        self.videos_checked = True
        videos = []

        if self._get_product_xml():
            # extract video IDs from XML
            video_ids = [str(vid) for vid in self.product_xml.xpath('//movie/@gvpURL')]
            if video_ids:
                # compose URL query to extract available video urls from API; example:
                # source URl: https://www.att.com/cellphones/samsung/galaxy-s8.html
                # composed videos URL: https://services.att.com/search/v1/videoservice?app-id=gvp&q=id:5000673+OR+id:5000674+OR+id:5000675+OR+id:5000677+OR+id:5000678+OR+id:5000679+OR+id:50007
                query = '+OR+id:'.join(video_ids)
                url = 'https://services.att.com/search/v1/videoservice?app-id=gvp&q=id:{}'.format(query)

                response = self.load_page_from_url_with_number_of_retries(url) or ''
                # remove js variables
                content = response.replace('gvp.getMetaData_success(', '')[:-1]
                if content:
                    try:
                        content = json.loads(content)
                        for doc in content['response']['docs']:
                            v_url = doc['url_videoMobile']
                            if v_url.startswith('//'):
                                v_url = 'https:' + v_url

                            if v_url not in videos:
                                videos.append(v_url)

                    except:
                        pass

        if videos:
            self.videos = videos

        return self.videos

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        if self._get_product_details():
            variant = self._get_selected_variant()
            if variant:
                return self._get_price(variant['priceList'])[0]

        return self._clean_text(
            self._get_pricearea_html().xpath('//div[@id="dueToday"]/div[contains(@class,"price")]/text()')[0])

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self._get_product_details():
            if self._get_selected_variant()['outOfStock']:
                return 1
            return 0

        if self._get_pricearea_html().xpath('//div[@id="addToCartDiv"]'):
            return 0
        return 1

    def _marketplace(self):
        return 0

    def _temp_price_cut(self):
        if self._get_product_details():
            return self._get_price( self._get_selected_variant()['priceList'])[1]

        if self._get_pricearea_html().xpath('//div[contains(@class,"pricingregular")]//div[contains(@class,"price")]/text()')[0] != self._price():
            return 1

        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        #self._url().split('/')[3:-1]
        breadcrumbs = self.tree_html.xpath('//div[@ng-controller="breadCrumbsController"]/@ng-init')[0]
        return re.findall('"title":"([^"]+)"', breadcrumbs)[:-1]

    def _brand(self):
        return self.tree_html.xpath('//meta[@itemprop="brand"]/@content')[0]

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        text = HTMLParser.HTMLParser().unescape(text)
        text = re.sub('[\r\n]', '', text)
        return text.strip()

    def _get_price(self, price_list):
        low_price = None
        on_sale = 0
        for price_json in price_list:
            price = price_json['dueToday']
            if price_json['leaseTotalMonths'] == 0:
                if price_json['salePrice']:
                    price = price_json['salePrice']
                    on_sale = 1

            if not low_price or price < low_price:
                low_price = price

        return ('$' + str(low_price), on_sale)

    def _get_selected_variant(self):
        if self._get_product_details():
            for skuId in self.product_details['skuItems']:
                variant_json = self.product_details['skuItems'][skuId]
                if variant_json['selectedSku'] or len(self.product_details['skuItems']) == 1:
                    return variant_json

            # if current skuId is not in the skuItems, then we select first one skuItem
            # based on https://www.att.com/shopcms/shopetc/att/wireless/components/page/hardrockangular/clientlib.min.js
            if self.product_details['skuItems']:
                skuIds = sorted(self.product_details['skuItems'].keys(), reverse=True)
                return self.product_details['skuItems'][skuIds[0]]

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
        "upc" : _upc,\
        "description" : _description, \
        "variants" : _variants, \
        "swatches": _swatches, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \
        "video_urls" : _video_urls, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "in_stores" : _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "marketplace": _marketplace, \
        "temp_price_cut" : _temp_price_cut, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "brand" : _brand, \
        }
