#!/usr/bin/python

import re, json, requests
from lxml import html

from extract_data import Scraper


class PetcoScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = 'Expected URL format is http(s)://www.petco.com/shop/en/petcostore/<product-name>'

    REVIEW_URL = 'http://api.bazaarvoice.com/data/batch.json?passkey=dpaqzblnfzrludzy2s7v27ehz&apiversion=5.5&displaycode=3554-en_us&resource.q0=products&filter.q0=id%3Aeq%3A{}&stats.q0=reviews'

    VIDEO_DATA_URL = 'https://sc.liveclicker.net/service/api?method=liveclicker.widget.getList&account_id=311&dim1={product_id}&status=online&format=json'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.prod_jsons_checked = False
        self.prod_jsons = None
        self.video_checked = False

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def check_url_format(self):
        if re.match('^https?://www\.petco\.com/shop/en/petcostore/.+$', self.product_page_url):
            return True
        return False

    def not_a_product(self):
        if self.ERROR_RESPONSE["failure_type"]:
            return True

        if 'Generic Error' in self.tree_html.xpath('//title/text()')[0]:
            self.ERROR_RESPONSE["failure_type"] = '404'
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self._prod_jsons()[self._catentry_id()]['catalogEntryIdentifier']['externalIdentifier']['partNumber']

    # specific to petco
    def _catentry_id(self):
        return self.tree_html.xpath('//input[@name="firstAvailableSkuCatentryId_avl"]/@value')[0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath('//div[contains(@class,"product-name")]/h1/text()')[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self.tree_html.xpath('//title/text()')[0].strip()

    def _sku(self):
        sku = self.tree_html.xpath('//input[@id="primarySku"]/@value')
        return sku[0] if sku else None

    def _description(self):
        description = ''

        description_elements = self.tree_html.xpath('//div[@id="description"]/div/*')

        for element in description_elements:
            if element.get('class') == 'row spacer-sm-top':
                continue

            description += self._clean_html(html.tostring(element))

        if description:
            return description

    def _long_description(self):
        long_description = ''

        description_elements = self.tree_html.xpath('//div[@id="shipping-returns_1"]/div/*')

        for element in description_elements:
            long_description += self._clean_html(html.tostring(element))

        if long_description:
            return long_description

    def _variants(self):
        variants = []

        for item in self._items_json():
            item_json = self._prod_jsons()[item['catentry_id']]

            if not item['Attributes']:
                continue

            item_attribute = item['Attributes'].keys()[0]

            sku = re.search(r'/(\d+)-', item.get('ItemImage', ''))
            sku = sku.group(1) if sku else None

            v = {
                'properties' : {
                    item_attribute.split('_')[0] : item_attribute.split('_')[1]
                    },
                'image_url' : item['ItemImage'],
                'price' : float(item_json['offerPrice'][1:]),
                'selected' : item['catentry_id'] == self._catentry_id(),
                'in_stock' : item_json['inventory']['onlineInventory']['status'] == 'In-Stock',
                'sku_id': sku,
            }

            variants.append(v)

        if len(variants) > 1:
            return variants

    def _no_longer_available(self):
        return 0

    def _ingredients(self):
        ingredients = self.tree_html.xpath('//div[contains(@id, "ingredients")]'
                                           '/div[@class="panel-body"]/p[1]/text()')
        ingredients = [i.strip() for i in ingredients if i.strip()]
        if ingredients:
            return ingredients[0].split(',')

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []

        image_inputs = self.tree_html.xpath('//input[starts-with(@id,"img_")]')

        for input in image_inputs:
            if self._product_id() in input.get('id') and not input.get('value') in image_urls:
                image_urls.append(input.get('value'))

        if self._items_json():
            for item in self._items_json():
                if item['catentry_id'] == self._catentry_id():
                    if not item['ItemImage'] in image_urls:
                        image_urls.append(item['ItemImage'])

        if image_urls:
            return image_urls

    def _pdf_urls(self):
        pdf_urls = []

        for link in self.tree_html.xpath('//a/@href'):
            if re.match('.*\.pdf$', link):
                pdf_urls.append(link)

        if pdf_urls:
            return pdf_urls

    def _video_urls(self):
        if not self.video_checked:
            self.video_checked = True
            self.video_urls = []
            product_id = self.tree_html.xpath(
                '//input[@id="productPartNo"]/@value'
            )
            if product_id:
                response = self._request(
                    self.VIDEO_DATA_URL.format(
                        product_id = product_id[0]
                    ),
                )
                if response.status_code == 200:
                    liveclicker_data = response.json()
                    for widget in liveclicker_data.get('widgets', {}).get('widget', []):
                        video_url = re.sub(r'/thumbnails/', '/videos/', widget.get('thumbnail'))
                        video_url = re.sub(r'_1_.*', '_1_liveclicker.mp4', video_url)
                        if video_url:
                            self.video_urls.append(video_url)
        return self.video_urls if self.video_urls else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _reviews(self):
        product_part_no = self.tree_html.xpath('//input[@id="productPartNo"]/@value')

        if product_part_no:
            review_url = self.REVIEW_URL.format(product_part_no[0])
            return super(PetcoScraper, self)._reviews(review_url = review_url)

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _prod_jsons(self):
        if not self.prod_jsons_checked:
            self.prod_jsons_checked = True

            self.prod_jsons = {}

            if self._items_json():
                iterate_over = self._items_json()
            else:
                iterate_over = [{'catentry_id' : self._catentry_id()}]

            for item in iterate_over:
                catentry_id = item['catentry_id']

                prod_json_url = 'http://www.petco.com/shop/GetCatalogEntryDetailsByIDView?catalogEntryId=' + catentry_id + '&catalogId=10051&langId=-1&storeId=10151'

                prod_json = requests.get(url=prod_json_url, timeout=30).content
                prod_json = re.search('{[^\*]*}', prod_json).group(0)
                prod_json = re.sub(',\s*\]', ']', prod_json)

                self.prod_jsons[catentry_id] = json.loads(prod_json)['catalogEntry']

                inventory_url = 'http://www.petco.com/shop/en/petcostore/GetInventoryStatusByIDView?catalogId=10051&itemId=' + catentry_id + '&langId=-1&storeId=10151'

                inventory_json = requests.get(url=inventory_url, timeout=30).content
                inventory_json = re.search('{[^\*]*}', inventory_json).group(0)
                inventory_json = re.sub('(\w+):', r'"\1":', inventory_json)

                self.prod_jsons[catentry_id]['inventory'] = json.loads(inventory_json)

        return self.prod_jsons

    def _price(self):
        # If the item with the main catentry id has no attributes, then use displayed price
        for item in self._items_json():
            if item['catentry_id'] == self._catentry_id() and not item['Attributes']:
                return self._clean_text(self.tree_html.xpath('//span[@itemprop="price"]/text()')[0])

        if self._prod_jsons()[self._catentry_id()]['offerPrice']:
            return self._prod_jsons()[self._catentry_id()]['offerPrice']

    def _temp_price_cut(self):
        if self._prod_jsons()[self._catentry_id()]['listPriced'] == 'true':
            return 1
        return 0

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock = self.tree_html.xpath('//*[@itemprop="availability"]/@href')
        if stock and 'instock' in stock[0].lower():
            return 0
        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return self.tree_html.xpath('//ol[@class="breadcrumb"]/li/a/text()')

    def _brand(self):
        return self.tree_html.xpath('//input[@id="tel_product_brand"]/@value')[0]

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        return re.sub('\s+', ' ', text).strip()

    def _clean_html(self, html):
        html = re.sub('<(\w+)[^>]*>', r'<\1>', html)
        return self._clean_text(html)
    
    def _items_json(self):
        return json.loads(self.tree_html.xpath('//div[starts-with(@id,"entitledItem")]/text()')[0])

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
        "sku" : _sku,
        "description" : _description,
        "long_description" : _long_description,
        "variants" : _variants,
        "no_longer_available" : _no_longer_available,
        "ingredients": _ingredients,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "pdf_urls" : _pdf_urls,
        "video_urls": _video_urls,

        # CONTAINER : REVIEWS
        "reviews" : _reviews,

        # CONTAINER : SELLERS
        "price" : _price,
        "temp_price_cut" : _temp_price_cut,
        "site_online" : _site_online,
        "site_online_out_of_stock" : _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }

