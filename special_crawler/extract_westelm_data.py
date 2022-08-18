#!/usr/bin/python

import re, json
from lxml import html
from extract_data import Scraper

class WestElmScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.westelm.com/product/*"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = None

    def check_url_format(self):
        if re.match(r"https?://www.westelm.com/products/.*", self.product_page_url):
            return True
        return False

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype and itemtype[0].strip() == "product":
            self._extract_product_json()
            return False

        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = re.search('-(\w\d+)', self.product_page_url)
        if product_id:
            return product_id.group(1)

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _extract_product_json(self):
        j = re.search('digitalData.product = ({.*?});', self.page_raw_text, re.S).group(1)
        j = re.sub('\n', '', j)
        j = re.sub('(\w+) :', r'"\1":', j)
        self.product_json = json.loads(j)

    def _product_name(self):
        return self.tree_html.xpath('//div[contains(@class,"pip-summary")]/h1/text()')[0].strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _description(self):
        description = self.tree_html.xpath('//div[@class="accordion-tab-copy"]//text()')[0]
        return description

    def _long_description(self):
        description = ''

        start = False

        for e in self.tree_html.xpath('//div[@class="accordion-tab-copy"]')[0]:
            e = html.tostring(e).strip()

            if e == '<p>&#160;</p>':
                start = True
                continue

            if not start:
                continue

            description += e

        if description:
            return description

    def _no_longer_available(self):
        if self._price():
            return 0
        return 1

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):        
        image_list = self.tree_html.xpath("//div[@class='scroller']//ul/li/a/img/@src")

        if not image_list:
            image_list = self.tree_html.xpath("//div[contains(@class, 'hero-image')]/img/@src")

        return map(lambda i: re.sub('-x.jpg', '-z.jpg', i), image_list)

    @staticmethod
    def _clean_bullet_html(el):
        l = el.xpath(".//text()")
        l = " ".join(l)
        l = " ".join(l.split())
        return l

    def _bullets(self):
        bullets = self.tree_html.xpath('//dd[@id="tab0"]//div[@class="accordion-tab-copy"]//ul//li')
        bullets = [self._clean_bullet_html(b) for b in bullets if self._clean_bullet_html(b)]
        if len(bullets) > 0:
            return "\n".join(bullets)

    def _variants(self):
        variants = []

        variant_json = json.loads(re.search('WSI.assortmentJson=({.*?});', self.page_raw_text).group(1))
        strings = variant_json['strings']
        
        for item in variant_json['groups']['main']['subsets'][0]['skus']:
            properties_map = item[-6]
            properties = {}

            for pair in properties_map.iteritems():
                k = strings[int(pair[0])]

                if k == 'availability':
                    continue

                properties[k] = strings[pair[1]]

            variant = {
                'sku': item[0],
                'price': item[4],
                'image_url': 'http://rk.weimgs.com/weimgs/rk/images/wcm/{0}z.jpg'.format(strings[item[12]]),
                'properties': properties,
                'selected': False,
                'in_stock': item[-2]
            }

            variants.append(variant)

        if variants:
            return variants

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        if not self.product_json['price']:
            return
            
        selling = self.product_json['price']['selling']

        if selling.get('max'):
            return '${0}~${1}'.format(selling['min'], selling['max'])

        return '${0}'.format(selling['min'])

    def _price_amount(self):
        if self.product_json['price']:
            return self.product_json['price']['selling']['min']

    def _temp_price_cut(self):
        if self.product_json['price'].get('regular'):
            return 1
        return 0

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self._no_longer_available():
            return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//ul[@id='breadcrumb-list']/li[@itemprop='itemListElement']/a/span/text()")
        return categories[1:]

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("&nbsp;", " ", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo" : _title_seo,
        "description" : _description,
        "long_description" : _long_description,
        "bullets": _bullets,
        "no_longer_available": _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "variants": _variants,

        # CONTAINER : SELLERS
        "price" : _price,
        "price_amount" : _price_amount,
        "temp_price_cut" : _temp_price_cut,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        }
