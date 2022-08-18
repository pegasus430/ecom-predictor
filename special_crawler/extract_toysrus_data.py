#!/usr/bin/python

import re
import json
import traceback

from extract_data import deep_search
from product_ranking.guess_brand import guess_brand_from_first_words

from lxml import html
from extract_data import Scraper
from spiders_shared_code.toysrus_variants import ToysrusVariants


class ToysRusScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.toysrus.com/.*"

    BASE_URL_WEBCOLLAGE_CONTENTS = "http://content.webcollage.net/toysrus/power-page?" \
                                   "ird=true&channel-product-id={}"

    VIDEO_URL = "https://e.invodo.com/4.0/pl/{version}/toysrus/{product_id}.js"

    REVIEW_URL = "https://readservices-b2c.powerreviews.com/m/713039/l/en_US/product/{}" \
                 "/reviews"

    HEADERS = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.8',
        'Host': 'www.toysrus.com',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36',
    }

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.video_urls_checked = False
        self.video_urls = []
        self.product_json = {}
        self.review_json = {}
        self.tv = ToysrusVariants()

    def _extract_page_tree(self):
        prod_id = re.search('productId=(\d+)', self.product_page_url)

        if not prod_id:
            prod_id = re.search('(\d+)$', self.product_page_url.split('?')[0])

        if prod_id:
            self.product_page_url = 'https://www.toysrus.com/product?productId=' + prod_id.group(1)

        self._extract_page_tree_with_retries(use_session=True)

    def check_url_format(self):
        m = re.match(r"^https?://www.toysrus.com/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype:
            self.version = 1
        else:
            self.version = 2

        try:
            product_json = re.search('pdpResponse.response = ({.*?});', self.page_raw_text).group(1)
            if product_json:
                self.product_json = json.loads(product_json.group(1))
            self.version = 3
        except Exception as e:
            print traceback.format_exc(e)

        self.tv.setupCH(self.tree_html, self.product_page_url)

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _extract_auth_key(self):
        auth_pwr = re.findall('"apiKey":"(.*?)",', html.tostring(self.tree_html))
        if auth_pwr:
            return auth_pwr[0]

    def _product_id(self):
        if self.product_json:
            return self.product_json['identifier']

        if self.version == 2:
            return re.search('productId=(.*?)"', self.page_raw_text).group(1)

        return self.tree_html.xpath('//input[@name="productId"]/@value')[0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = None
        if self.product_json:
            product_name = [self.product_json.get('name')]

        if not product_name:
            product_name = self.tree_html.xpath('//div[contains(@class, "product-title")]/@title')

        if not product_name:
            product_name = self.tree_html.xpath('//div[@id="lTitle"]/h1/text()')

        if not product_name:
            product_name = self.tree_html.xpath('//title/text()')

        if product_name:
            return product_name[0].replace('- Toys"R"Us', '').strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self.tree_html.xpath('//title/text()')[0]

    def _sku(self):
        sku = self.tree_html.xpath("//input[@id='pdpSkuId']/@value")
        return sku[0] if sku else None

    def _upc(self):
        if self.version == 2:
            return re.search('"upcNumber":"(.*?)",', self.page_raw_text).group(1).zfill(12)

        return self.tree_html.xpath("//p[@class='upc']/span[@class='value']/text()")[0].zfill(12)

    def _features(self):
        if self.version == 2:
            features = re.search('"features":\[(.*?)]\,', self.page_raw_text).group(1).split(',')
            features_list = [i.strip().replace('"', '') for i in features]

        else:
            features_list = self.tree_html.xpath('//div[@id="Features"]/ul/li/text()')

        if features_list:
            return features_list

    def _description(self):
        if self.product_json:
            return self.product_json['properties']['iteminfo']['description'][0]['value']

        if self.version == 2:
            short_description = self.tree_html.xpath('//div[@class="pdp-details__description"]')[0].text_content().strip()

        else:
            short_description = self.tree_html.xpath("//div[@id='Description']/p")[0].text_content().strip()

        if short_description:
            return short_description

    def _long_description(self):
        long_description = self.tree_html.xpath("//div[@id='Description']")[0].text_content().strip()
        short_description = self._description()

        if long_description.startswith("Product Description"):
            long_description = long_description[len("Product Description"):].strip()

        if short_description:
            long_description = long_description.replace(short_description, "").strip()

        if long_description:
            return long_description

    def _variants(self):
        return self.tv._variants()

    def _sku(self):
        sku = re.search('"SKU":"(.*?)",', self.page_raw_text).group(1)
        return sku

    def _manufacturer(self):
        manufacturer = re.search('"manufacturer":"(.*?)",', self.page_raw_text).group(1)
        return manufacturer

    def _brand(self):
        if self.product_json:
            return self.product_json['properties']['iteminfo']['brand']

        if self.version == 2:
            return re.search('"brandName":"(.*?)",', self.page_raw_text).group(1)

        return guess_brand_from_first_words(self._product_name())

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):        
        if self.product_json:
            return [i['image'] for i in self.product_json['properties']['iteminfo']['bigimage']]

        if self.version == 2:
            image_list = self.tree_html.xpath('//div[contains(@class, "gallery-thumbnails")]/img/@src')
            return [i.split('?')[0] for i in image_list]

        image_list = self.tree_html.xpath("//div[@class='altImages fl']//img/@src")

        for index, url in enumerate(image_list):
            if not url.startswith("http://www.toysrus.com"):
                image_list[index] = "http://www.toysrus.com" + url.replace("t50.jpg", "dt.jpg")

        if image_list:
            return image_list
        elif self.tree_html.xpath("//img[@name='prodShot_0']/@src"):
            main_image_url = self.tree_html.xpath("//img[@name='prodShot_0']/@src")

            if not main_image_url[0].startswith("http://www.toysrus.com"):
                main_image_url[0] = "http://www.toysrus.com" + main_image_url[0]

            return main_image_url

    def _video_urls(self):
        if self.video_urls_checked:
            return self.video_urls

        self.video_urls_checked = True

        for i in range(1,7):
            headers = {
                'Referer':self.product_page_url,
            }
            r = self._request(self.VIDEO_URL.format(version=i, product_id=self._product_id()), headers=headers)
            if r.status_code == 200:
                j = json.loads(re.search('({.*})\);', r.text).group(1))
                encodings = deep_search('encodings', j)
                if encodings:
                    self.video_urls.append(max(encodings[0])['http'])
                    break

        return self.video_urls

    def _pdf_urls(self):
        pdf_links = self.tree_html.xpath("//a[contains(@href,'.pdf')]/@href")

        if pdf_links:
            return pdf_links

    def _site_version(self):
        return self.version

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        if self.version == 1:
            price = self._find_between(html.tostring(self.tree_html), "trusJspVariables.productPrice = ", ";").strip()
            return '$' + price

        if self.version == 2:
            price = re.search('"salePrice":(.*?),', self.page_raw_text).group(1)
            if not price:
                price = self.tree_html.xpath('//div[@class="prices"]//span[@class="price"]/text()')[0].strip()
            if not price:
                price = self.tree_html.xpath('//div[@class="prices"]//span[@class="sale-price"]/text()')[0].strip()
            if not price:
                price = self.tree_html.xpath('//*[contains(@class, "product-price")]/text()')[0].strip()
            if not '$' in price:
                price = '$' + price
            return price

        price = self.product_json['properties']['buyinfo']['pricing']
        try:
            price = price['prices'][1]['value']
        except:
            price = price['prices'][0]['value']

        return '$' + price

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self.product_json:
            if self.product_json['properties']['buyinfo']['instock']:
                return 1
            return 0

        if self.version == 2:
            for o in self.tree_html.xpath('//div[contains(@class,"out-of-stock")]'):
                if 'out of stock' in o.text_content():
                    return 1
            stock_info = self.tree_html.xpath('//span[contains(text(), "out of stock")]')
            if stock_info:
                return 1
            return 0

        if self.tree_html.xpath('//div[@id="productOOS"]'):
            return 1

        stock_info = self.tree_html.xpath('//div[@id="addToCartDivSpace"]'
                                          '//button[contains(@class, "add-to-cart")]/text()')

        if stock_info and 'out of stock' in stock_info[0]:
            return 1

        return 0

    def _in_stores_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        if self.product_json:
            breadcrumbs = self.product_json['properties']['state']['breadcrumb']
            return [b['name'] for b in breadcrumbs[1:]]

        if self.version == 2:
            return self.tree_html.xpath("//*[contains(@class,'breadcrumb')]/li/a/text()")

        return self.tree_html.xpath("//div[@id='breadCrumbs']/a/text()")[1:]
    
    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo" : _title_seo,
        "upc" : _upc,
        "features" : _features,
        "description" : _description,
        "long_description" : _long_description,
        "variants": _variants,
        "brand" : _brand,
        "sku" : _sku,
        "manufacturer" : _manufacturer,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls" : _video_urls,
        "pdf_urls" : _pdf_urls,
        "site_version" : _site_version,

        # CONTAINER : SELLERS
        "price" : _price,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        }
