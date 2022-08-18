#!/usr/bin/python

import re
import json
import traceback
import requests

from lxml import html
from HTMLParser import HTMLParser
from extract_data import Scraper
from spiders_shared_code.walgreens_variants import WalgreensVariants


class WalgreensScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.walgreens.com/.*$"

    WEBCOLLAGE_POWER_PAGE = "http://content.webcollage.net/walgreens/smart-button?ird=true&channel-product-id=prod{}"

    REVIEW_URL = "http://api.bazaarvoice.com/data/batch.json?"\
                 "passkey=tpcm2y0z48bicyt0z3et5n2xf"\
                 "&apiversion=5.5"\
                 "&displaycode=2001-en_us"\
                 "&resource.q0=products"\
                 "&filter.q0=id%3Aeq%3Aprod{}"\
                 "&stats.q0=reviews"

    PRODUCT_URL = "https://www.walgreens.com/svc/products/prod{}/(PriceInfo+Inventory+ProductInfo+ProductDetails)"

    DESCRIPTION_URL = "https://www.walgreens.com/store/store/prodDesc.jsp?"\
                      "id=prod{}&callFrom=dotcom&instart_disable_injection=true"

    WARNINGS_URL = "https://www.walgreens.com/store/store/prodWarnings.jsp?id=prod{}"

    INGREDIENTS_URL = "https://www.walgreens.com/store/store/ingredient.jsp?id=prod{}"

    CATEGORIES_URL = "https://customersearch.walgreens.com/productsearch/v1/breadcrumbs?categoryId={}"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.price_info = None
        self.inventory = None
        self.ingredients_content = None
        self.product_json = None
        self.wv = WalgreensVariants()
        self.categories = None

    def check_url_format(self):
        if re.match('^https?://www.walgreens.com/store/c/.*$', self.product_page_url):
            return True
        return False

    def _extract_product_json(self):
        try:
            prod_id = self._product_id()
            self.product_json = self._request(self.PRODUCT_URL.format(prod_id)).json()
        except:
            print traceback.format_exc()

    def _extract_ingredients(self):
        try:
            prod_id = self._product_id()
            self.ingredients_content = self._request(self.INGREDIENTS_URL.format(prod_id)).content
        except:
            print traceback.format_exc()

    def _pre_scrape(self):
        self._extract_product_json()
        self._extract_ingredients()
        self._extract_webcollage_contents()
        self._reviews()

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return re.search('id=prod(\d+)', self.product_page_url.lower()).group(1)

    def _site_id(self):
        return self._product_id()

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _no_longer_available(self):
        no_longer_available = self.tree_html.xpath(
            '//*[@role="alert"]/span[contains(text(),"no longer available")]'
        )
        return bool(no_longer_available)

    def _product_name(self):
        title = self.tree_html.xpath('//title/text()')[0].split('|')[0]
        return self._clean_text(title)

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _model(self):
        model = self.review_json.get('ModelNumbers')
        return model[0] if model else None

    def _upc(self):
        return self.review_json['UPCs'][0]

    def _sku(self):
        sku = self.tree_html.xpath('//input[@id="hiddenSkuId"]/@value')
        return sku[0] if sku else None

    def _description(self):
        description_elements = self.product_json.get('prodDetails', {}).get('section')
        description = description_elements[0].get('description',{}).get('shortMessage')
        if description:
            description = html.fromstring(description).xpath('//text()')
            return self._clean_text(' '.join([x.strip() for x in description]))

    def _long_description(self):
        product_id = self._product_id()
        long_description = self._request(self.DESCRIPTION_URL.format(product_id)).content
        long_description = self._exclude_javascript_from_description(long_description)
        long_description = long_description.split('<hr></hr>')[0].strip()
        long_description = long_description = re.sub(r'</?div.*?>', '', long_description)
        long_description = self._clean_text(long_description)
        if long_description:
            return unicode(long_description, errors='replace')

    def _warnings(self):
        warnings_html = html.fromstring(self._request(self.WARNINGS_URL.format(self._product_id())).text)
        warnings = warnings_html.xpath('//text()')
        if warnings:
            return ' '.join([x.strip() for x in warnings])

    def _ingredients(self):
        if self.ingredients_content:
            ingredients = html.fromstring(self.ingredients_content).xpath('//p/text()')
            if ingredients:
                return [x.strip() for x in ''.join(ingredients).split(',')]

    def _variants(self):
        self._load_price_info_and_inventory()
        self.wv.setupCH(self.inventory)
        return self.wv._variants()

    def _swatches(self):
        self._load_price_info_and_inventory()
        swatches = []
        if self.inventory.get('relatedProducts'):
            for product in self.inventory['relatedProducts']['color']:
                swatch = {
                    'color' : product['value'],
                    'hero' : 0,
                    'hero_image' : None,
                    'swatch_name' : 'color',
                }

                if product.get('url'):
                    swatch['hero_image'] = [product['url'].split('?')[0][2:]]
                    swatch['hero'] = len( swatch['hero_image'])
                swatches.append(swatch)
        if swatches:
            return swatches

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _thumbnail(self):
        thumbnail = self.tree_html.xpath('//a[@id="product-50x50_a"]/img/@src')
        return thumbnail[0][2:] if thumbnail else None

    def _image_urls(self):
        images = []
        img_data = self.product_json.get('productInfo', {}).get('filmStripUrl', {})
        if img_data:
            for i in range(len(img_data)):
                image = 'https:' + img_data[i].get('largeImageUrl' + str(i + 1))
                cl = self._request(image, verb='head').headers['content-length']
                # content length of blank image is 3353
                if cl != '3353':
                    images.append(image)

        return images if images else None

    def _video_urls(self):
        if self.wc_videos:
            return self.wc_videos 

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _load_price_info_and_inventory(self):
        if not (self.price_info or self.inventory):
            self.price_info = self.product_json['priceInfo']
            self.inventory = self.product_json['inventory']

    def _price(self):
        self._load_price_info_and_inventory()
        # Account for price format 2/$p2 or 1/$p1 (use p1)
        if self.price_info.get('salePrice'):
            return self.price_info['salePrice'].split('or')[-1].split('/')[-1]
        elif self.price_info.get('regularPrice'):
            return self.price_info['regularPrice'].split('or')[-1].split('/')[-1]

    def _in_stores(self):
        self._load_price_info_and_inventory()
        if self.inventory.get('pickupAvailableMessage') == 'Not sold in stores':
            return 0
        return 1

    def _site_online(self):
        self._load_price_info_and_inventory()
        if self.inventory.get('shipAvailableMessage') and self.inventory['shipAvailableMessage'] == 'Not sold online':
            return 0
        return 1

    def _site_online_out_of_stock(self):
        self._load_price_info_and_inventory()
        if 'out of stock' in self.inventory.get('shipAvailableMessage', ''):
            return 1
        return 0

    def _in_stores_out_of_stock(self):
        self._load_price_info_and_inventory()
        if self._in_stores():
            if not 'Pickup' in self.inventory.get('availableOptions', ''):
                return 1
            return 0

    def _in_stock(self):
        if self._site_online():
            return self._site_online_in_stock()
        return 0

    def _marketplace(self):
        return 0

    def _temp_price_cut(self):
        self._load_price_info_and_inventory()
        if self.price_info.get('salePrice'):
            return 1
        return 0

    def _web_only(self):
        return not self._in_stores()

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        if self.categories:
            return self.categories

        categories = self.tree_html.xpath('//ul[contains(@class, "breadcrumb")]/li/a/text()')
        if not categories:
            categories = re.search(r'window\.__BTF_APP_INITIAL_STATE__ = .*"breadcrumbInfo":(\[.+?\])', self.page_raw_text, re.DOTALL)
            try:
                categories = json.loads(categories.group(1))
                categories = [
                    category.get('name')
                    for category in sorted(categories, key=lambda k: k.get('type'))
                    if category.get('name')
                ]
            except:
                print traceback.format_exc()
        else:
            categories = categories[2:]

        if not categories:
            category_id = re.search(r'"tier3Category":"(\d+)"', self.page_raw_text, re.DOTALL)
            try:
                breadcrumbs = self._request(self.CATEGORIES_URL.format(category_id.group(1))).json()
                categories = [breadcrumb.get('name') for breadcrumb in breadcrumbs]
            except:
                print traceback.format_exc()

        if categories:
            self.categories = categories

        return categories

    def _brand(self):
        return self.review_json['Brand']['Name']

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        text = re.sub('[\r\n\t]', '', text)
        return text.strip()

    def _clean_html(self, html):
        html = HTMLParser().unescape( html)
        html = re.sub( ' \w+="[^"]+"', '', html)
        return html

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,
        "site_id" : _site_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo" : _title_seo,
        "model" : _model,
        "upc" : _upc,
        "sku" : _sku,
        "description" : _description,
        "long_description" : _long_description,
        "warnings": _warnings,
        "ingredients" : _ingredients,
        "variants" : _variants,
        "swatches" : _swatches,
        "no_longer_available": _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "thumbnail" : _thumbnail,
        "image_urls" : _image_urls,
        "video_urls" : _video_urls,

        # CONTAINER : SELLERS
        "price" : _price,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,
        "marketplace" : _marketplace,
        "temp_price_cut" : _temp_price_cut,
        "web_only" : _web_only,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
