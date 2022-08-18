#!/usr/bin/python

import re
import time
import json
import traceback

from lxml import html
from extract_data import Scraper
from HTMLParser import HTMLParser
from spiders_shared_code.staples_variants import StaplesVariants


class StaplesScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = 'Expected URL format is http(s)://www.staples.com/([a-zA-Z0-9\-/]+)/product_([a-zA-Z0-9]+)'

    WEBCOLLAGE_POWER_PAGE = 'http://content.webcollage.net/staples/power-page?ird=true&channel-product-id={}'
    WEBCOLLAGE_SMART_BUTTON = 'http://content.webcollage.net/staples/smart-button?ird=true&channel-product-id={}'
    WEBCOLLAGE_PRODUCT_CONTENT_PAGE = 'http://content.webcollage.net/staples/product-content-page?channel-product-id={}'

    CNET_CONTENT = 'http://ws.cnetcontent.com/d5eea376/script/522bca68e4?cpn={}&lang=EN&market=US&host=www.staples.com&nld=1'

    REVIEW_URL = 'https://static.www.turnto.com/sitedata/jwmno8RkY7SXz4jsite/v4_3/{}/d/en_US/catitemreviewshtml'

    PRICE_URL = 'https://www.staples.com/asgard-node/v1/nad/staplesus/price/{0}?offer_flag=true&warranty_flag=true&coming_soon=0&price_in_cart=0&productDocKey={0}'

    VARIANT_URL = "https://www.staples.com/product_{}"

    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)" \
                 " Chrome/65.0.3325.181 Safari/537.36"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = {}
        self.price_json = {}
        self.has_cnet_media = False
        self.cnet_videos = []

        self.version = 1
        self.sv = StaplesVariants()
        self.variants_checked = False
        self.variants = []

        self.product_page_url = re.sub('http://', 'https://', self.product_page_url)

    def check_url_format(self):
        m = re.match('https?://www.staples.com/(?:.*/)?product_([^/]+)', self.product_page_url.split('?')[0])
        if m:
            self.product_id = m.group(1)
        return bool(m)

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries(use_session=True, save_session=True)

    def not_a_product(self):
        self.sv.setupCH(self.page_raw_text)

        self._extract_product_json()

        if not self.product_json:
            return True

        # For updated site, price info is already in product json
        if self.version == 1:
            self._extract_price_json()

        self._extract_webcollage_contents()
        self._extract_cnet_content()

    def _extract_cnet_content(self):
        if not self.wc_videos:
            try:
                cnet = self._request(self.CNET_CONTENT.format(self.product_id), use_proxies=False).content
                if re.search('data-image-url=', cnet):
                    self.has_cnet_media = True
                video_urls = re.findall(r'ndata(?:-video)?-url=\\"(.*?)\\"', cnet)
                if video_urls:
                    self.cnet_videos = video_urls
            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', 'Error extracting cnet content: {}'.format(e))

    def _extract_product_json(self):
        try:
            selected_sku = self._find_between(self.page_raw_text, 'var selectedSKU = "', '";')

            if selected_sku:
                product_json = self._find_between(self.page_raw_text, 'products["{}"] ='.format(selected_sku), ';products["StaplesUSCAS/en-US/1/')

                if not product_json:
                    product_json = self._find_between(self.page_raw_text, 'products["{}"] ='.format(selected_sku), ";\n")

                self.product_json = json.loads(product_json)

            # CON-43379 site update
            else:
                self.version = 2
                product_json = re.search('content="({.*?})"', HTMLParser().unescape(self.page_raw_text))

                if product_json:
                    self.product_json = json.loads(product_json.group(1))

        except Exception as e:
            print traceback.format_exc()

            if self.lh:
                self.lh.add_list_log('errors', 'Error extracting product json: {}'.format(e))

    def _extract_price_json(self):
        for _ in range(5):
            try:
                self.price_json = self._request(self.PRICE_URL.format(self.product_id), session=self.session).json()
                return
            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', 'Error extracting price json: {}'.format(e))

                # wait between requests to avoid read timeout
                time.sleep(10)

    @staticmethod
    def _extract_variants_props(tree):
        props = {}
        color = tree.xpath('//div[@id="STP--Skuset-dropdown"]//div[@class="color-txt"]/strong/text()')
        if color:
            props['color'] = color[0].strip()
        selection = tree.xpath('//div[@id="STP--Skuset-dropdown"]//div[@id="subsFreq"]/text()')
        if selection:
            props['selection'] = selection[0].strip()
        return props

    def _extract_variant_data(self, sku):
        #  `use_user_agent=False` is used to avoid 'BadStatusLine' error CON-44190
        resp = self._request(self.VARIANT_URL.format(sku), session=self.session)
        if resp.status_code == 200:
            tree = html.fromstring(resp.text)
            variant_data = tree.xpath('//div[@id="analyticsItemData"]/@content')
            if variant_data:
                try:
                    json_data = json.loads(variant_data[0])
                    json_data['properties'] = self._extract_variants_props(tree)
                    return json_data
                except Exception as e:
                    print traceback.format_exc()

                    if self.lh:
                        self.lh.add_list_log('errors', 'Error extracting variant json: {}'.format(e))

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath('//span[@itemprop="name"]/text()')[0].strip()

    def _bullets(self):
        if self.version == 1:
            bullets = self._description_helper('Bullets')
            return '\n'.join(bullets.split('<br/>'))
        else:
            bullets = self.product_json['product']['description'].get('bullets')
            if bullets:
                return '\n'.join(bullets)

    def _specs(self):
        specs = {}

        if self.version == 1:
            specification = self.product_json['description'].get('specification')
            if specification:
                for s in specification:
                    specs[s['attribname']] = s['attrvalue']
                return specs

        else:
            specification = self.product_json['product']['description'].get('specification')
            if specification:
                for s in specification:
                    specs[s['name']] = s['value']
                return specs

    def _description_helper(self, name):
        for d in self.product_json['description']['details']:
            if d['description_type']['name'] == name:
                return '<br/>'.join(t['value'] for t in d['text'])

    def _description(self):
        if self.version == 1:
            description = self._description_helper('Paragraph')
            headliner = self._description_helper('Headliner')
        else:
            description = self.product_json['product']['description'].get('paragraph')
            headliner = self.product_json['product']['description'].get('headliner')

            description = description[0] if description else None
            headliner = headliner[0] if headliner else None

        if headliner:
            # CON-42398 add font size to distinguish headliner
            return '<font size="4">' + headliner + '</font><br/>' + (description or '')

        return description

    def _long_description(self):
        if self.version == 1:
            return self._description_helper('Expanded Descr')
        else:
            long_description = self.product_json.get('product', {}).get('description', {}).get('expandedDescr')
            return long_description[0] if long_description else None

    def _no_longer_available(self):
        if self.tree_html.xpath('//div[@class="content"]/p/text()'):
            return 1
        return 0

    def _model(self):
        if self.version == 1:
            return self.product_json['metadata']['mfpartnumber']
        else:
            return self.product_json['product']['manufacturerPartNumber']

    def _upc(self):
        if self.version == 1:
            upc = self.product_json['metadata']['upc_code']
        else:
            upc = self.product_json['product']['upcCode']
        return upc[-12:].zfill(12) if upc else None

    def _variants(self):
        if not self.variants_checked:
            self.variants_checked = True
            skus = self.tree_html.xpath('//div[@class="skuset"]//*[@data-sku]/@data-sku')
            if skus:
                data = []
                product_json = self.product_json.copy()
                product_json['properties'] = self._extract_variants_props(self.tree_html)
                data.append(product_json)
                skus.remove(self._product_id())
                for sku in set(skus):
                    variant_data = self._extract_variant_data(sku)
                    if variant_data:
                        data.append(variant_data)
                self.variants = self.sv._variants(data)
        return self.variants if self.variants else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        if self.version == 1:
            images = self.product_json['description']['media']['images']

            enlarged = images.get('enlarged')
            if enlarged:
                return [i['path'] + '_sc7' for i in enlarged]

            return [i['path'].split('?')[0] for i in images['standard']]
        else:
            return self.product_json['product']['images']['thumbnail']

    def _video_urls(self):
        if self.cnet_videos:
            return self.cnet_videos
        
        if self.wc_videos:
            return self.wc_videos

    def _cnet(self):
        if self.has_cnet_media:
            return 1
        return 0

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        if self.is_review_checked:
            return self.reviews

        self.is_review_checked = True

        for _ in range(3):
            try:
                review_html = html.fromstring(self._request(self.REVIEW_URL.format(self.product_id), use_proxies=False).content)

                average_review = review_html.xpath('//*[@id="TTreviewSummaryAverageRating"]/text()')

                if not average_review:
                    return

                self.average_review = float(average_review[0].split('/')[0])

                reviews = []

                for i in range(5, 0, -1):
                    review_count = review_html.xpath('//*[@id="TTreviewSummaryBreakdown-{}"]/text()'.format(i))[0]
                    reviews.append([i, int(review_count)])

                self.reviews = reviews
                return self.reviews
            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', 'Error extracting reviews: {}'.format(e))

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        if self.version == 1:
            return float(self.tree_html.xpath("//span[@itemprop='price']/text()")[0])
        else:
            return self.product_json['price']['item'][0]['finalPrice']

    def _site_online(self):
        return 1

    def _in_stores(self):
        return int(not bool(
            self.tree_html.xpath('//div[@class="sold-in-store" and .//*[contains(text(), "not available")]]')
        ))

    def _site_online_out_of_stock(self):
        if self._site_online():
            if self.version == 1:
                return int(self.price_json['cartAction'] == 'currentlyOutOfStock')
            else:
                return int(self.product_json['inventory']['items'][0]['productIsOutOfStock'])

    def _marketplace(self):
        return 0

    def _temp_price_cut(self):
        if self.version == 1:
            return 1 if self.price_json['pricing']['totalSavings'] else 0
        else:
            return 1 if self.product_json['price']['item'][0]['totalSavings'] else 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _brand(self):
        if self.version == 1:
            return self.product_json['metadata']['mfname']
        else:
            return self.product_json['product']['manufacturerName']

    def _categories(self):
        if self.version == 1:
            categories = self.tree_html.xpath("//li[@typeof='v:Breadcrumb']/a/text()")
            if categories:
                return [category.strip() for category in categories[1:]]
        else:
            return [c['name'] for c in self.product_json['product']['breadcrumb']]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        'product_id' : _product_id,

        # CONTAINER : PRODUCT_INFO
        'product_name' : _product_name,
        'bullets': _bullets,
        'specs' : _specs,
        'description' : _description,
        'long_description' : _long_description,
        'no_longer_available' : _no_longer_available,
        'model' : _model,
        'upc' : _upc,
        'variants' : _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        'image_urls' : _image_urls,
        'video_urls' : _video_urls,
        'cnet' : _cnet,

        # CONTAINER : SELLERS
        'price_amount' : _price_amount,
        'site_online' : _site_online,
        'site_online_out_of_stock' : _site_online_out_of_stock,
        'marketplace' : _marketplace,
        'temp_price_cut' : _temp_price_cut,
        "in_stores": _in_stores,

         # CONTAINER : REVIEWS
        'reviews' : _reviews,

        # CONTAINER : CLASSIFICATION
        'brand' : _brand,
        'categories' : _categories,
        }
