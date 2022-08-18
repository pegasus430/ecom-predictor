#!/usr/bin/python

import re
import json
import urlparse
import traceback
from lxml import html
from HTMLParser import HTMLParser

from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words
from spiders_shared_code.bestbuy_variants import BestBuyVariants

class BestBuyScraper(Scraper):
    
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.bestbuy.com/site/<product-name>/<product-id>"

    PRICES_URL = 'https://www.bestbuy.com/api/1.0/carousel/prices?skus={}' 

    REVIEW_URL = 'https://bestbuy.ugc.bazaarvoice.com/3545w/{}/reviews.djs?format=embeddedhtml'

    FULFILLMENT_API = 'https://www.bestbuy.com/fulfillment/shipping/api/v1/fulfillment/sku;skuId={};postalCode={};deliveryDateOption=EARLIEST_AVAILABLE_DATE'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.specs_fetched = False
        self.specs = None

        self.videos_fetched = False
        self.videos = None

        self.bv = BestBuyVariants()

        self.variants_fetched = False
        self.variants = None

        self.zip_code = '94012'
        self.stock_info = {}

        self.embedded_json = {}
        self.price_info = {}

    def select_browser_agents_randomly(self):
        return 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots) Chrome'

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def check_url_format(self):
        m = re.match(r"https?://www\.bestbuy\.com/site/[a-zA-Z0-9%\-\%\_]+/.*", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if not self.tree_html.xpath("//meta[@property='og:type' and @content='product']"):
            if self._no_longer_available() == 1:
                return False
            return True
        self.bv.setupCH(self.tree_html, self.product_page_url)
        return False

    def _pre_scrape(self):
        self.embedded_json = json.loads(re.search('__UGC_APP_INITIAL_STATE__ = ({.*?})<', html.tostring(self.tree_html)).group(1))

        stock_info = self._request(self.FULFILLMENT_API.format(self._sku(), self.zip_code),
                                   headers={'x-client-id':' BROWSE'}).json()

        self.stock_info = stock_info['responseInfos'][0]

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        prod_id = self.tree_html.xpath("//span[@id='sku-value']/text()")
        return prod_id[0] if prod_id else None

    def _sku(self):
        return self._product_id()

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@class='type-subhead-alt-regular']/text()") or \
                self.tree_html.xpath("//div[@itemprop='name']/h1/text()")
        return product_name[0] if product_name else None
    
    def _model(self):
        return self.embedded_json.get('productDetails', {}).get('model')

    def _specs(self):
        if self.specs_fetched:
            return self.specs

        self.specs_fetched = True

        specs = {}

        data_tabs = self.tree_html.xpath("//div[@id='pdp-model-data']/@data-tabs")

        for tab in json.loads(data_tabs[0]):
            if tab['id'] == 'specifications' or 'Details' in tab['id']:
                url = urlparse.urljoin(self.product_page_url, tab['fragmentUrl'])

                specs_html = html.fromstring(self._request(url).content)
                specs_html = specs_html.xpath('//div[contains(@class, "key-specs")]')[0]

                names = specs_html.xpath(".//div[@class='specification-name']")
                values = specs_html.xpath(".//div[@class='specification-value']")

                for name, value in zip(names, values):
                    specs[name.text_content().strip()] = value.text_content().strip()

        if specs:
            self.specs = specs

        return self.specs

    def _features(self):
        features = []

        for f in self.tree_html.xpath('//div[@class="feature"]'):
            title = f.xpath('./span/text()')
            value = f.xpath('./p/text()')
            if title and value:
                if title == 'Need more information?':
                    continue
                features.append(title[0] + ': ' + value[0])
            if not title and value:
                features.append(value[0])
            if title and not value:
                features.append(title[0])

        if features:
            return features

    def _description(self):
        return self.embedded_json.get('productDetails', {}).get('description')

    def _variants(self):
        if self.variants_fetched:
            return self.variants

        self.variants_fetched = True

        self.variants = self.bv._variants()

        if self.variants:
            skus = [variant['sku_id'] for variant in self.variants]

            # Request prices for those skus
            self.price_info = self._request(self.PRICES_URL.format(','.join(skus))).json()  

            for variant in self.variants:
                for price in self.price_info:
                    if variant['sku_id'] == price['skuId']:
                        variant['price'] = price['currentPrice']

            return self.variants

        else:
            self.price_info = self._request(self.PRICES_URL.format(self._sku())).json()  

    def _no_longer_available(self):
        return int(not(self.embedded_json.get('productDetails', {}).get('active')))

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//script[@type="application/ld+json" and contains(text(), "ImageObject")]/text()')
        try:
            image_urls = json.loads(image_urls[0])
            return [i.get('thumbnailUrl') for i in image_urls if i.get("@type") == 'ImageObject']
        except:
            print traceback.format_exc()

        if not image_urls:
            image_urls = self.tree_html.xpath('//ol[@class="carousel-indicators"]//li//img/@data-src')
            image_urls = [re.sub(r';.*', '', image) for image in image_urls]

        return image_urls

    def _video_urls(self):
        if self.videos_fetched:
            return self.videos

        self.videos_fetched = True

        videos = []

        video_ids = re.findall('"liveClickerId":"([^"]+?)"', self.page_raw_text)

        for video_id in video_ids:
            video_url = 'https://sc.liveclicker.net/service/getXML?widget_id={}'.format(video_id)

            video_html = html.fromstring(self._request(video_url).content)

            videos.extend(video_html.xpath('//location/text()'))

        if not videos:
            media_script = self.tree_html.xpath('//script[contains(text(), "window.pdp.enlargeImage")]')
            media_info = None
            try:
                media_info = json.loads(re.findall(r'window.pdp.enlargeImage =(.*);}', html.tostring(media_script[0]))[0])
            except:
                print traceback.format_exc()

            if media_info:
                for media in media_info.get('multimedia', []):
                    if media.get('mediaType') == 'video':
                        videos.append(media.get('sources')[0].get('src'))

        if videos:
            self.videos = videos

        return self.videos

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        return self.embedded_json.get('productDetails', {}).get('price')

    def _in_stores(self):
        return 1

    def _marketplace(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return int(not(self.stock_info['deliveryEligible']))

    def _temp_price_cut(self):
        self._variants()
        for price in self.price_info:
            if price['skuId'] == self._sku():
                if price['pricingType'] == 'onSale':
                    return 1

        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//ol[@id='breadcrumb-list']/li/a/text()")[1:]

        if categories:
            return categories

    def _brand(self):
        return HTMLParser().unescape(self.embedded_json.get('productDetails', {}).get('brandName')) or \
                guess_brand_from_first_words(self._product_title())

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,
        "sku" : _sku,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "model" : _model,
        "description" : _description,
        "variants" : _variants,
        "no_longer_available" : _no_longer_available,
        "specs" : _specs,
        "features" : _features,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls" : _video_urls,

        # CONTAINER : SELLERS
        "price_amount" : _price_amount,
        "in_stores" : _in_stores,
        "marketplace" : _marketplace,
        "site_online" : _site_online,
        "site_online_out_of_stock" : _site_online_out_of_stock,
        "temp_price_cut" : _temp_price_cut,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
