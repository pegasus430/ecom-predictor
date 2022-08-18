#!/usr/bin/python

import re
import json
import requests
import urlparse
import traceback

from lxml import html
from extract_data import Scraper

from spiders_shared_code.gap_variants import GapVariants


class GapScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=tpy1b18t8bg5lp4y9hfs0qm31" \
            "&apiversion=5.5" \
            "&displaycode=3755_27_0-en_us" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=reviews"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = None
        self.gv = GapVariants()

    def _extract_page_tree(self):
        for i in range(3):
            try:
                with requests.Session() as s:
                    # do not redirect more than 3 times
                    for t in range(3):
                        response = s.get(self.product_page_url)

                        if response.ok:
                            content = response.text
                            self.tree_html = html.fromstring(content)

                            redirect_url = self.get_redirect_url(self.tree_html)

                            if redirect_url and not redirect_url == self.product_page_url:
                                self.product_page_url = redirect_url
                                continue

                            return

                        else:
                            self.ERROR_RESPONSE['failure_type'] = response.status_code
                            break

            except Exception as e:
                print 'ERROR EXTRACTING PAGE TREE', self.product_page_url, e

        self.is_timeout = True  # return failure

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[contains(@class, "page-content")]')) < 1:
            return True

        self._extract_product_json()
        self.gv.setupCH(self.tree_html, self.product_json)

        return False

    def _extract_product_json(self):
        product_json = self._find_between(html.tostring(self.tree_html), 'gap.pageProductData = ', '};')

        try:
            self.product_json = json.loads(product_json + '}')
        except:
            self.product_json = None

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = re.search('pid=(\d+)', self.product_page_url)
        return product_id.group(1) if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_json['name']

    def _description(self):
        desc = self.tree_html.xpath('//div[@class="sp_top_sm"]/p/text()')
        return desc[0] if desc else None

    def _long_description(self):
        long_description = []
        description_info = self.tree_html.xpath("//ul[@class='sp_top_sm dash-list']")
        if description_info:
            for description in description_info:
                long_description.append(html.tostring(description))

        if long_description:
            long_description = self._clean_text(''.join(long_description))
            long_description = re.sub(' +', ' ', long_description)

        return long_description

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_url_list = []
        try:
            product_image_info = self.product_json['productImages']
            product_color_images = self.product_json['variants'][0]['productStyleColors'][0][0]['productStyleColorImages']

            for product_color in product_color_images:
                image_url_list.append(urlparse.urljoin(self.product_page_url, product_image_info[product_color]['xlarge']))
        except Exception as e:
            print traceback.format_exc(e)

        return image_url_list

    def _video_urls(self):
        video_list = []
        video_url = self.product_json['productImages']
        for v_url in video_url:
            if video_url[v_url]['video']:
                video_list.append(urlparse.urljoin(self.product_page_url, video_url[v_url]['video']))
        return video_list if video_list else None

    def _variants(self):
        return self.gv._variants()

    def _swatches(self):
        return self.gv.swatches(self._image_urls())

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        base_price = self.tree_html.xpath("//h5[@class='product-price']/text()")
        special_price = self.tree_html.xpath("//h5[contains(@class, 'product-price--highlight')]/text()")
        other_price = self.tree_html.xpath("//h5[@class='product-price']/span/text()")

        if base_price:
            price = self._clean_text(base_price[0])
        if special_price:
            price = re.search('\d+\.\d*', self._clean_text(special_price[0])).group()
            price = '$' + price
        if other_price:
            price = self._clean_text(other_price[0]).split('-')
            min_price = '$' + re.search('\d+\.\d*', price[0]).group()
            max_price = '$' + re.search('\d+\.\d*', price[1]).group()
            price = min_price + '-' + max_price
            
        return price if price else None

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

    def _brand(self):
        return 'GAP'

    def _sku(self):
        sku = self.tree_html.xpath("//meta[@itemprop='sku']/@content")
        return sku[0] if sku else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "sku": _sku,
        "description": _description,
        "long_description": _long_description,
        "swatches": _swatches,
        "variants": _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "brand": _brand,
        }
