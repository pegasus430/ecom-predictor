#!/usr/bin/python

import re
import json
import requests
import traceback

from lxml import html
from extract_data import Scraper
from spiders_shared_code.walmartca_variants import WalmartCAVariants


class WalmartCAScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=e6wzzmz844l2kk3v6v7igfl6i" \
            "&apiversion=5.5" \
            "&displaycode=2036-en_ca" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=reviews"

    AVAILABILITY_URL = 'https://www.walmart.ca/ws/en/products/availability-pip'

    STORE_ID = '1015'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.wcv = WalmartCAVariants()

        self.product_json = {}
        self.variant_json = None
        self.inventory_json = {}

        self._set_proxy()

    def _extract_page_tree(self):
        self.product_page_url = re.sub('https://', 'http://', self.product_page_url)

        for i in range(10):
            try:
                with requests.Session() as self.session:
                    self._request('http://www.walmart.ca', session=self.session)  # get the homepage first
                    self.page_raw_text = self._request(self.product_page_url, session=self.session).content
                    self.tree_html = html.fromstring(self.page_raw_text)
                    if not self._product_name():
                        continue
                return
            except Exception as e:
                print traceback.format_exc()
                if self.lh:
                    self.lh.add_list_log('errors', 'Error extracting page tree: {}'.format(str(e)))

    def _pre_scrape(self):
        self._load_product_json()
        self._load_availability()
        self.wcv.setupCH(self.variant_json, self.tree_html)
        self.session.close()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _load_product_json(self):
        try:
            # Extract base product info from JS
            data = re.findall(
                    r'productPurchaseCartridgeData\[\"%s\"\]\s*=\s*(\{(.|\n)*?\});' % self._product_id(),
                    self.page_raw_text
            )

            if data:
                data = list(data)[0]
                data = data[0].replace('numberOfVariants', '"numberOfVariants"').replace('variantDataRaw', '"variantDataRaw"')
                data = data.replace(' :', ':')

                try:
                    self.variant_json = json.loads(data)
                except ValueError:
                    return
            else:
                return

            refinements_json = re.search('walmartAnalytics.refinementsJson = (\[.+\]);', self.page_raw_text)
            if refinements_json:
                self.product_json = json.loads(refinements_json.group(1))

        except:
            print traceback.format_exc()

    def _load_availability(self):
        sku = self._sku()
        upc = self._upc()
        product_id = self._product_id()
        if sku and upc and product_id:
            data = {
                "stores": [self.STORE_ID],
                "products": {
                    product_id: [{
                        "sku": sku,
                        "upc": [upc]
                    }]
                },
                "origin": "pip"
            }
            headers = {
                'x-requested-with': 'XMLHttpRequest',
                'content-type': 'application/json'
            }
            r = self._request(self.AVAILABILITY_URL, verb='post', data=json.dumps(data), session=self.session, headers=headers)
            if r.status_code == 200:
                self.inventory_json = r.json()

    def _sku(self):
        sku = self.tree_html.xpath("//*[@data-sku]/@data-sku | //*[@data-sku-id]/@data-sku-id")
        return sku[0] if sku else None

    def _upc(self):
        upc = re.search(r'\"upc\":\[\"(.*?)\"', self.page_raw_text)
        if not upc:
            upc = re.search(r'\"upc_nbr\":\[\"(.*?)\"', self.page_raw_text)
        if upc:
            return upc.group(1).zfill(12)[-12:]

    def _model(self):
        model = self.tree_html.xpath("//*[@itemprop='model']/text()")
        return model[0] if model else None

    def _product_id(self):
        product_id = re.search(r'/([0-9A-Z]+)(?:\?|$)', self.product_page_url)
        return product_id.group(1) if product_id else None

    def _specs(self):
        names = self.tree_html.xpath(
            '//div[@id="spec-group"]//div[contains(@class, "name")]/text()'
        )
        values = self.tree_html.xpath(
            '//div[@id="spec-group"]//div[contains(@class, "value")]'
        )
        if names and values and len(names) == len(values):
            specs = {}
            for i,name in enumerate(names):
                if values[i].xpath('./@data-original-text'):
                    value = values[i].xpath('./@data-original-text')
                elif values[i].xpath('./span/text()'):
                    value = values[i].xpath('./span/text()')
                else:
                    value = values[i].xpath('./text()')
                specs[name.strip()] = value[0].strip() if value else None
            return specs if specs else None

    def _walmart_no(self):
        for spec_name, spec_value in (self._specs() or {}).iteritems():
            if spec_name == 'Walmart Item #':
                return spec_value

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//h1[@data-analytics-type="productPage-productName"]/text()')
        return product_name[0].strip() if product_name else None

    def _features(self):
        if not self.tree_html.xpath("//div[@id='specGroup']"):
            return None

        if self._sku():
            feature_name_list = self.tree_html.xpath("//div[@id='specGroup']/div[@data-sku-id={}]//div[contains(@class, 'name')]".format(self._sku()))
            feature_value_list = self.tree_html.xpath("//div[@id='specGroup']/div[@data-sku-id={}]//div[contains(@class, 'value')]".format(self._sku()))
        else:
            feature_name_list = self.tree_html.xpath("//div[@id='specGroup']//div[contains(@class, 'name')]")
            feature_value_list = self.tree_html.xpath("//div[@id='specGroup']//div[contains(@class, 'value')]")

        feature_list = []

        for index, feature_name in enumerate(feature_name_list):
            feature_list.append(feature_name.text_content().strip() + " " + feature_value_list[index].text_content().strip())

        if feature_list:
            return feature_list

    def _description(self):
        return self.tree_html.xpath("//div[@itemprop='description']/div[contains(@class, 'description')]")[0].text_content().strip()

    def _long_description(self):
        return self.tree_html.xpath("//div[@itemprop='description']/div[contains(@class, 'bullets')]")[0].text_content().strip()

    def _variants(self):
        return self.wcv._variants()

    def _rollback(self):
        for r in self.product_json:
            if r['displayName'] == 'RollbackProduct' and r['label'] == 'Yes':
                return 1
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        slider_images = self.tree_html.xpath("//div[@id='carousel']//ul[@class='slides']//img/@src")

        if slider_images:
            for index, image in enumerate(slider_images):
                if image.startswith("http:") or image.startswith("https:"):
                    continue

                slider_images[index] = "http:" + image

            return slider_images

        main_image = self.tree_html.xpath("//div[@id='product-images']//div[@class='centered-img-wrap']//img/@src")

        if main_image:
            return main_image

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        try:
            return self.tree_html.xpath("//span[@itemprop='price']/text()")[0]
        except:
            return self.tree_html.xpath("//span[@itemprop='lowPrice']/text()")[0] + " to " + self.tree_html.xpath("//span[@itemprop='highPrice']/text()")[0]

    def _primary_seller(self):
        return 'Walmart'

    def _site_online(self):
        if self.inventory_json.get(self._product_id(), {}).get('onlineSummary'):
            return 1
        return 0

    def _in_stores(self):
        if self.inventory_json.get(self._product_id(), {}).get('storeSummary'):
            return 1
        return 0

    def _site_online_out_of_stock(self):
        if self._site_online():
            return int(
                self.inventory_json.get(self._product_id(), {}).get('onlineSummary', {}).get('status') != 'Available'
            )

    def _in_stores_out_of_stock(self):
        if self._in_stores():
            return int(
                self.inventory_json.get(self._product_id(), {}).get('storeSummary', {}).get('status') != 'Available'
            )

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################    

    def _categories(self):
        categories = self.tree_html.xpath('//*[@itemprop="itemListElement"]//span[@itemprop="name"]/text()')
        return categories[1:]

    def _brand(self):
        return self.tree_html.xpath("//span[@itemprop='brand']/text()")[0].strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "features": _features,
        "description": _description,
        "long_description": _long_description,
        "variants": _variants,
        "rollback": _rollback,
        "upc": _upc,
        "sku": _sku,
        "model": _model,
        "specs": _specs,
        "walmart_no": _walmart_no,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "primary_seller": _primary_seller,
        "marketplace": _marketplace,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores": _in_stores,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
