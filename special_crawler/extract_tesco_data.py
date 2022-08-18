#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import json
import urlparse
import traceback

from lxml import html
from extract_data import Scraper, deep_search

from product_ranking.guess_brand import guess_brand_from_first_words


class TescoScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.tesco.com/direct/<part-of-product-name>/<product_id>.prd " \
                          "or http(s)://www.tesco.com/groceries/product/details/?id=<product_id>"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
          "passkey=asiwwvlu4jk00qyffn49sr7tb&apiversion=5.5&" \
          "displaycode=1235-en_gb&resource.q0=products&" \
          "filter.q0=id:eq:{}&stats.q0=reviews&" \
          "filteredstats.q0=reviews"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_data = {}
        self.sku_data = {}

        self.version = None

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def check_url_format(self):
        if re.match('https?://www.tesco.com/groceries/', self.product_page_url):
            self.version = 'groceries'
        elif re.match('https?://www.tesco.com/direct/', self.product_page_url):
            self.version = 'direct'

        if self.version:
            return True

    def not_a_product(self):
        if self.version == 'groceries':
            try:
                product_data = json.loads(self.tree_html.xpath('//script[@type="application/ld+json"]/text()')[0])
                for data in product_data:
                    if data.get('@type') == 'Product':
                        self.product_data = data
                        break
            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

        else:
            try:
                product_data = re.search('product =\s+({.*?}),\n', self.page_raw_text, re.DOTALL)
                self.product_data = json.loads(product_data.group(1))
                sku_data = re.search('sku =\s+({.*?}),\n', self.page_raw_text, re.DOTALL)
                self.sku_data = json.loads(sku_data.group(1))
            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

        if not self.product_data:
            return True
    
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.product_data.get('id')
        if not product_id:
            product_id = re.search(r'(?:/|id=)(\d+)', self.product_page_url)
            product_id = product_id.group(1) if product_id else None
        if not product_id:
            product_id = self.sku_data.get('id')
        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        if self.version == 'groceries':
            return self.product_data['name']

        return self.product_data['displayName']

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self.tree_html.xpath('//title//text()')[0].strip()

    def _upc(self):
        upc = self.tree_html.xpath('//meta[@property="og:upc"]/@content')
        if not upc:
            upc = re.search(r'&quot;baseProductId&quot;,&quot;(\d+)&quot;', self.page_raw_text, re.DOTALL)
            upc = [upc.group(1)] if upc else None

        if upc:
            return upc[0]

    def _features(self):
        feature_rows = self.tree_html.xpath("//div[@id='product-spec-container']//div[@class='product-spec-row']")
        features = []

        for feature_row in feature_rows:
            features.append('{0} {1}'.format(
                feature_row.xpath('.//div[contains(@class, "product-spec-label")]/text()')[0].strip(),
                feature_row.xpath('.//div[contains(@class, "product-spec-value")]/text()')[0].strip()))

        if features:
            return features

    def _description(self):
        if self.tree_html.xpath("//ul[@class='multipack-details__accordion']"):
            description_blocks = self.tree_html.xpath('//ul[@class="multipack-details__accordion"][position()=1]'
                '//div[@id="multipack--description"] |'
                '//ul[@class="multipack-details__accordion"][position()=1]'
                '//div[@id="multipack--marketing"] |'
                '//ul[@class="multipack-details__accordion"][position()=1]'
                '//div[@id="multipack--features"]'
            )
        else:
            description_blocks = self.tree_html.xpath(
                '//div[@id="product-description"] |'
                '//div[@id="product-marketing"] |'
                '//div[@id="features"]'
            )
        if description_blocks:
            description = '. '.join(
                [x.text_content().replace('Product Description', '') for x in description_blocks]
            )
            return description if description else None
        else:
            description = self.tree_html.xpath('//div[contains(@class, "block-content")]/text()')
            return description[0] if description else None

    def _ingredients(self):
        if self.tree_html.xpath("//ul[@class='multipack-details__accordion']"):
            ingredients = self.tree_html.xpath("//ul[@class='multipack-details__accordion'][position()=1]"
                                            "//div[@id='multipack--ingredients']/p")
        else:
            ingredients = self.tree_html.xpath(
                '//div[@id="ingredients"]/p'
            )
        if ingredients:
            text = ingredients[0].text_content()
            ingredients = re.split(r",\s+(?=(?:(?:[^']*'){2})*[^']*$)", text)
            return [x.strip() for x in ingredients]

    def _nutrition_facts(self):
        nutrition_facts = []
        if self.tree_html.xpath("//ul[@class='multipack-details__accordion']"):
            nut_info = self.tree_html.xpath("//ul[@class='multipack-details__accordion'][position()=1]"
                                            "//section[@class='tabularContent'][1]/table/tbody//tr")
        else:
            nut_info = self.tree_html.xpath("//section[@class='tabularContent'][1]/table/tbody//tr")

        if nut_info:
            for data in nut_info:
                if data.xpath('//td'):
                    nutrition_facts.append(data.xpath('.//td/text()'))

        return nutrition_facts

    def _long_description(self):
        if self.version == 'groceries':
            desc_block = self.tree_html.xpath("//div[@class='product-info--wrapper']")
            if not desc_block:
                return None

            desc_raw_text = html.tostring(desc_block[0])
            nutrition_block = re.search(r'<section class="tabularContent".*?>(.*)</section>', desc_raw_text)
            if nutrition_block:
                nutrition_block = nutrition_block.group()
                desc_raw_text = desc_raw_text.replace(nutrition_block, '')

            long_desc = html.fromstring(desc_raw_text).xpath("./descendant::text()")

            return ",".join(long_desc).strip()

    def _no_longer_available(self):
        um = self.tree_html.xpath('//p[@class="warning unavailableMsg"]//text()')
        if um and 'not available' in um[0]:
            return 1
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        if self.version == 'groceries':
            images = self.product_data['image']

            if isinstance(images, dict):
                return [images['display'][0]['zoom']['url']]

            return images

        image_urls = []

        for asset in self.sku_data['mediaAssets']['skuMedia']:
            if asset['mediaType'] == 'Large':
                image_urls.append(urlparse.urljoin('https://www.tesco.com/', asset['src'].split('?')[0]))

        if image_urls:
            return image_urls

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        if self.version == 'direct':
            return super(TescoScraper, self)._reviews()

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        if self.version == 'groceries':
            price = self.product_data.get('offers', {}).get('price')
        else:
            price = self.product_data.get('prices', {}).get('price')

        return float(price) if price else None

    def _price_currency(self):
        currency = self.tree_html.xpath("//*[@class='currency']/text()")
        if currency and u'\xa3' in currency[0]:
            return 'GBP'
        return 'USD'

    def _temp_price_cut(self):
        if self.version == 'groceries':
            promo = self.tree_html.xpath('//*[@class="product-promotion"]')
            if promo and promo[0].text_content().startswith('Save'):
                return 1

        if self.tree_html.xpath('//span[@class="saving"]'):
            return 1

        return 0

    def _marketplace(self):
        if self._marketplace_sellers():
            return 1
        return 0

    def _marketplace_sellers(self):
        if self.version == 'direct':
            seller = self.tree_html.xpath('//p[@class="seller-name"]/strong/text()')[0]
            if not 'Tesco' in seller:
                return [seller]

    def _marketplace_out_of_stock(self):
        if self._marketplace():
            if self._no_longer_available():
                return 1
            return 0

    def _primary_seller(self):
        if self.version == 'direct':
            marketplace_sellers = self._marketplace_sellers()

            if marketplace_sellers:
                return marketplace_sellers[0]
 
            return 'Tesco'

    def _site_online(self):
        return 0 if self._marketplace() else 1

    def _site_online_out_of_stock(self):
        if self._site_online():
            if self._no_longer_available():
                return 1
            um = self.tree_html.xpath('//div[contains(@class, "product-info-message")]//p/text()')
            if um and 'Sorry' in um[0]:
                return 1
            return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        if self.version == 'groceries':
            brand = self.product_data.get('brand', {}).get('name')
            if not brand:
                brand = guess_brand_from_first_words(self._product_name())

            return brand

        return self.product_data['brand']

    def _categories(self):
        if self.version == 'groceries':
            categories = self.tree_html.xpath("//div[@class='plp--breadcrumbs']"
                                              "//span[@class='plp--breadcrumbs--crumb']//a/@title")

            return categories if len(categories) > 0 else None

        categories = self.tree_html.xpath("//div[@id='breadcrumb-v2']//ul/li//span[@itemprop='title']/text()")
        categories = [category.strip() for category in categories]
        return categories[1:5]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "upc": _upc,
        "features": _features,
        "description": _description,
        "ingredients": _ingredients,
        "long_description": _long_description,
        "no_longer_available": _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "temp_price_cut": _temp_price_cut,
        "marketplace": _marketplace,
        "marketplace_sellers": _marketplace_sellers,
        "marketplace_out_of_stock": _marketplace_out_of_stock,
        "primary_seller": _primary_seller,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
