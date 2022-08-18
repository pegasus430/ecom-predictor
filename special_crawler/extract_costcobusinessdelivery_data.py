#!/usr/bin/python

import re
import base64
import urlparse
import requests

from lxml import html
from extract_data import Scraper

from product_ranking.guess_brand import guess_brand_from_first_words


class CostcobusinessdeliveryScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    PRICE_DELIVERY_URL = 'https://www.costcobusinessdelivery.com/AjaxBusinessDeliveryBrowse'

    IMAGE_URL = "https://richmedia.channeladvisor.com/ViewerDelivery/productXmlService?" \
                "profileid={profileid}&itemid={itemid}&viewerid=1019"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.image_urls_checked = False
        self.image_urls = []

    def _extract_page_tree(self):
        headers = {'Content-Type': 'application/x-www-form-urlencoded',
                   'Referer': self.product_page_url,
                   'X-Requested-With': 'XMLHttpRequest',
                   }

        for i in range(5):
            try:
                with requests.Session() as s:
                    data = {'zipCodeFormDeliveryZipCode': '94117', 'storeId': '11301', 'catalogId': '11701',
                            'langId': '-1', 'currentZipCode': '', 'redirectURL': 'ProductDetails',
                            'submitButton': 'zipCodeForm', 'authToken': '-1002%2C5M9R2fZEDWOZ1d8MBwy40LOFIV0%3D'
                    }

                    self._request(self.PRICE_DELIVERY_URL, session=s, verb='post', data=data, headers=headers)
                    response = self._request(self.product_page_url, session = s, log_status_code = True)

                    if response.ok:
                        content = response.text
                        self.tree_html = html.fromstring(content)
                        return

                    else:
                        self.ERROR_RESPONSE['failure_type'] = response.status_code

                        if response.status_code == 403:
                            self._set_proxy()
 
            except Exception as e:
                if self.lh:
                    self.lh.add_list_log('errors', str(e))

            self.is_timeout = True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        prod_id = re.search('product.(\d+).html', self.product_page_url)
        return prod_id.group(1) if prod_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@itemprop='name']/text()")
        return product_name[0] if product_name else None

    def _model(self):
        model = self.tree_html.xpath("//p[@class='model-number']//span/@data-model-number")
        return model[0] if model else None

    def _description(self):
        description = self.tree_html.xpath("//h1[@itemprop='name']/text()")
        return description[0] if description else None

    def _long_description(self):
        long_description = self.tree_html.xpath('//div[@id="accordion-product-details"]/div')
        if long_description:
            long_description = html.tostring(long_description[0])
            return self._clean_text(long_description)

    def _specs(self):
        specs = {}

        for spec in self.tree_html.xpath('//div[contains(@class, "product-info-specs")]/div'):
            spec_name, spec_value = spec.xpath('.//div/text()')

            if spec_name and spec_value:
                specs[spec_name.strip()] = spec_value.strip()

        if specs:
            return specs

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        if not self.image_urls_checked:
            return self._get_image_urls()
        return self.image_urls

    def _get_image_urls(self):
        self.image_urls_checked = True
        profileid = re.search('profileId=(.*?)&', html.tostring(self.tree_html), re.DOTALL).group(1)
        url = self.IMAGE_URL.format(profileid=profileid, itemid=self._sku())
        data = self._request(url)
        self.image_urls = re.findall('path="(.*?)"', data.content)
        return self.image_urls

    def _video_urls(self):
        video_api_url = self.tree_html.xpath("//div[@class='genericESpot']//script[@type='text/javascript']/@src")
        if video_api_url:
            video_api_url = 'https:' + video_api_url[0].replace('getEmbed', 'getXML')
            xml_contents = html.fromstring(self._request(video_api_url).text)
            return xml_contents.xpath('.//location/text()')

    def _pdf_urls(self):
        pdf_urls = self.tree_html.xpath("//div[@class='image-column']//ul[@class='link-list']//a/@href")
        pdf_urls = [urlparse.urljoin(self.product_page_url, url) for url in pdf_urls if len(url) > 0]
        return pdf_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = re.search('"price" : "(.*?)"', html.tostring(self.tree_html))
        if price:
            price = base64.b64decode(price.group(1).strip())
            return '$' + price if price else None

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
        categories = self.tree_html.xpath('//div[@id="product-page"]'
                                          '//ul[@class="crumbs"]/li/a/text()')
        return categories[1:] if categories else None

    def _brand(self):
        specs = self._specs()
        if specs:
            return specs.get('Brand')
        title = self._product_title()
        return guess_brand_from_first_words(title) if title else None

    def _sku(self):
        sku = self.tree_html.xpath("//span[@itemprop='sku']/text()")
        return sku[0] if sku else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "model": _model,
        "description": _description,
        "long_description": _long_description,
        "specs": _specs,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "pdf_urls": _pdf_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        "sku": _sku
        }
