#!/usr/bin/python

import re
import json
import requests
import traceback
from lxml import html

from extract_data import Scraper
from spiders_shared_code.jet_variants import JetVariants
from product_ranking.guess_brand import guess_brand_from_first_words


class JetScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = 'Expected URL format is http(s)://(www.)jet.com/product/(<product-name>/)<product-id>'

    API_URL = 'https://jet.com/api/product/v2'

    REVIEW_URL = 'http://readservices-b2c.powerreviews.com/m/786803/l/en_US/product/' \
                 '{}/reviews?'

    HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko)'
                             ' Chrome/66.0.3359.139 Safari/537.36',
               'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
               'Accept-encoding': 'gzip, deflate, br',
               'Cache-control': 'no-cache',
               'Pragma': 'no-cache',
               'Upgrade-insecure-requests': '1',
               'X-Forwarded-For': '127.0.0.1'}

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_data = None
        self.image_dimensions = None
        self.zoom_image_dimensions = None
        self.got_image_dimensions = False

        self.jv = JetVariants()
        self.variants_data = []

    def _extract_page_tree(self):
        for i in range(3):
            try:
                with requests.session() as s:
                    try:
                        r = self._request(self.product_page_url, session=s, log_status_code=True)
                        self.tree_html = html.fromstring(r.content)
                    except Exception as e:
                        raise Exception('Error fetching page html: {}'.format(str(e)))

                    csrf_token = self.tree_html.xpath('//*[@data-id="csrf"]/@data-val') or \
                        re.findall('"clientCsrfToken":"([^"]+?)"', html.tostring(self.tree_html))
                    if not csrf_token:
                        raise Exception('No csrf token')
                    csrf_token = csrf_token[0].replace('"', '')

                    headers = {'X-Requested-With': 'XMLHttpRequest',
                               'content-type': 'application/json',
                               'user-agent': 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)',
                               'x-csrf-token': csrf_token,
                               'referer': self.product_page_url
                               }

                    body = json.dumps({'sku': self._product_id(), 'origination': 'none'})

                    try:
                        self.product_data = self._request(self.API_URL,
                                                          session=s,
                                                          verb='post',
                                                          headers=headers,
                                                          data=body).json()['result']
                    except Exception as e:
                        raise Exception('Error fetching product data: {}'.format(str(e)))

                    if self.product_data.get('statusCode') in [404, 410]:
                        self.ERROR_RESPONSE['failure_type'] = '404'
                        self.is_timeout = True
                        return

                    self.jv.setupCH(self.product_data)

                    self.variants_data = [self.product_data]

                    variations = self.product_data.get('productVariations', [])

                    # Only get variant prices if there aren't an astronomical number of them
                    if len(variations) <= 10:
                        # Make additional variants requests to get variants data (with prices)
                        for sku in (v.get('retailSkuId') for v in variations):
                            try:
                                body = json.dumps({'sku': sku, 'origination': 'none'})
                                variant_data = s.post(self.API_URL, headers=headers, data=body).content
                                self.variants_data.append(json.loads(variant_data)['result'])
                            except Exception as e:
                                raise Exception('Error fetching variant data: {}'.format(str(e)))

                    return

            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

                    if str(e) == 'No csrf token' and i > 1:
                        self.lh.add_list_log('errors', html.tostring(self.tree_html))

    def check_url_format(self):
        m = re.match('^https?://(www\.)?jet\.com/(product/)?(.+/)?[\w\d]+$', self.product_page_url, re.U)
        return bool(m)

    def not_a_product(self):
        if not self._product_name():
            return True
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_auth_key(self):
        auth_pwr = re.findall(r'"powerReviews":{"apiKey":"(.*?)"', html.tostring(self.tree_html))
        if auth_pwr:
            return auth_pwr[0]

    def _product_id(self):
        product_id = re.search('([^/]+)$', self._url())
        return product_id.group(1).lower() if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return re.sub('\(Pack of (\d+)\)', '', self.product_data['title']).strip()

    def _model(self):
        return self.product_data.get('part_no')

    def _upc(self):
        upc = self.product_data['upc']
        return upc[-12:]

    def _description(self):
        return self.product_data['description']

    def _ingredients(self):
        ingredients = re.search(r'Ingredients:(.*?)\.', self.product_data['description'])
        if ingredients:
            ingredients = [x.strip() for x in ingredients.group(1).split(', ')]

        return ingredients if ingredients else None

    def _specs(self):
        specs = {}

        for attribute in self.product_data['attributes']:
            if attribute['display']:
                specs[attribute['name']] = attribute['value']
        if specs:
            return specs

    def _bullets(self):
        bullets = self.product_data['bullets']
        bullets = [self._clean_text(r) for r in bullets if len(self._clean_text(r))>0]
        if len(bullets) > 0:
            return "\n".join(bullets)

    def _variants(self):
        variants = self.jv._variants()
        if variants and self.variants_data:
            # Insert price, stock status and image from variants_data
            for variant, variant_data in zip(variants, self.variants_data):
                variant['price'] = variant_data.get('productPrice', {}).get('referencePrice')
                variant['in_stock'] = variant_data.get('addToCart', False)
                variant['image_url'] = variant_data.get('images', [{}])[0].get('raw')

            return variants

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        return map(lambda i: i['raw'], self.product_data['images'])

    def _get_image_dimensions(self):
        if self.got_image_dimensions:
            return

        self.got_image_dimensions = True

        image_dims = []
        zoom_image_dims = []

        for image in self.product_data['images']:
            cl_raw = requests.head(image['raw']).headers['content-length']
            cl_500 = requests.head(image['x500']).headers['content-length']
            cl_1500 = requests.head(image['x1500']).headers['content-length']

            if cl_raw != cl_500:
                image_dims.append(1)
            else:
                image_dims.append(0)

            if cl_raw != cl_1500:
                zoom_image_dims.append(1)
            else:
                zoom_image_dims.append(0)

        self.image_dimensions = image_dims
        self.zoom_image_dimensions = zoom_image_dims

    def _image_dimensions(self):
        self._get_image_dimensions()
        return self.image_dimensions

    def _zoom_image_dimensions(self):
        self._get_image_dimensions()
        return self.zoom_image_dimensions

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        return self.product_data['productPrice']['referencePrice']

    def _temp_price_cut(self):
        if not self.product_data['productPrice']['listPrice']:
            return 0
        return 1

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if not self.product_data['display']:
            return 1

        if self._site_online() == 0:
            return None

        in_stock = self.tree_html.xpath('//div[contains(@class, "were_sorry")]//text()')
        in_stock = " ".join(in_stock)
        if 'this item is unavailable right now' in in_stock.lower():
            return 1

        return 0

    def _web_only(self):
        return 1

    def _primary_seller(self):
        return self.product_data.get('manufacturer')

    def _owned(self):
        brand = self._brand()
        seller = self._primary_seller()
        if brand and seller and brand.lower() == seller.lower():
            return 1

        return 0

    def _marketplace(self):
        return 1 - self._owned()

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return self.product_data['categoryPath'].split('|')

    def _brand(self):
        brand = self.product_data.get('manufacturer')
        if not brand:
            brand = guess_brand_from_first_words(self._product_name())
        return brand

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "model" : _model,
        "upc" : _upc,
        "description" : _description,
        "ingredients" : _ingredients,
        "specs" : _specs,
        "variants" : _variants,
        "bullets": _bullets,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "image_dimensions" : _image_dimensions,
        'zoom_image_dimensions' : _zoom_image_dimensions,

        # CONTAINER : SELLERS
        "price_amount" : _price_amount,
        "temp_price_cut" : _temp_price_cut,
        "in_stores": _in_stores,
        "site_online" : _site_online,
        "site_online_out_of_stock" : _site_online_out_of_stock,
        "web_only" : _web_only,
        "primary_seller" : _primary_seller,
        "owned" : _owned,
        "marketplace" : _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
    }
