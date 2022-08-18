#!/usr/bin/python

import re
import json
import urlparse
from lxml import html
from extract_data import Scraper
from spiders_shared_code.petsmart_variants import PetsmartVariants

import traceback


class PetsmartScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    REVIEW_URL = "http://api.bazaarvoice.com/data/batch.json?" \
                 "passkey=208e3foy6upqbk7glk4e3edpv&" \
                 "apiversion=5.5&" \
                 "displaycode=4830-en_us&" \
                 "resource.q0=products&" \
                 "filter.q0=id%3Aeq%3A{product_id}&" \
                 "stats.q0=reviews&"

    MEDIA_URL = "https://images.petsmartassets.com/is/image/{}?req=set,json,UTF-8"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.images_checked = False
        self.video_checked = False

        self.vnt = PetsmartVariants()
        self.temp_price_cut = 0

        self.features = []
        self.ingredients = None
        self.directions = None

        self.checked_long_desc = False

    def not_a_product(self):
        self.vnt.setupCH(self.tree_html)
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath('//span[contains(@class,"ws-product-item-number-value")]/text()')
        if not product_id:
            product_id = self.tree_html.xpath("//span[@class='productID']/text()")
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _brand(self):
        brand = self.tree_html.xpath('//span[@itemprop="brand"]//text()')
        if brand:
            return self._clean_text(brand[0])
        elif self._get_product_data():
            return self._get_product_data().get('brand')

    def _product_name(self):
        product_name = self.tree_html.xpath('//h1[@data-dynamic-block-name="Title"]/text()')
        if not product_name:
            product_name = self.tree_html.xpath("//h1[@class='product-name']/text()")
        return product_name[0] if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self.tree_html.xpath('//title/text()')[0].strip()

    def _description(self):
        description = self.tree_html.xpath('//div[@class="product-description"]'
                                           '//div[@itemprop="description"]/text()')
        return self._clean_text(description[0]) if description else None

    def _long_description(self):
        long_desc = []
        self.checked_long_desc = True
        desc_block = self.tree_html.xpath('//div[@class="product-description"]'
                                          '//div[@itemprop="description"]')

        if desc_block:
            desc_block = html.tostring(desc_block[0]).replace('<br>', '')
            desc_block = html.fromstring(desc_block).xpath("./descendant::text()")

        idx = 0
        while idx < len(desc_block):
            if 'Ingredients:' in desc_block[idx]:
                ingredients = desc_block[idx + 1]
                self.ingredients = ingredients.split(',')
                idx += 2
            elif 'Features:' in desc_block[idx]:
                feature = desc_block[idx + 1]
                self.features.append(feature)
                idx += 2
            elif 'Directions:' in desc_block[idx] or 'Direction for Use:' in desc_block[idx]:
                directions = desc_block[idx + 1]
                self.directions = self._clean_text(directions)
                idx += 2
            else:
                long_desc.append(desc_block[idx])
                idx += 1

        if long_desc:
            long_desc = self._clean_text(''.join(long_desc)).replace(self._description(), '')

        return long_desc if long_desc else None

    def _features(self):
        if self.checked_long_desc is False:
            self._long_description()

        return self.features if self.features else None

    def _ingredients(self):
        if self.checked_long_desc is False:
            self._long_description()

        return self.ingredients

    def _directions(self):
        if self.checked_long_desc is False:
            self._long_description()

        return self.directions

    def _variants(self):
        self.variants = self.vnt._variants()
        return self.variants

    def _no_longer_available(self):
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        if self.images_checked:
            return self.images
        base_path = re.search(r'(?<!//)s7params.*serverurl\",\s\"(.*?)\"', self.page_raw_text)
        if base_path:
            base_path = 'https:' + base_path.group(1) + '/'
        data = re.search(r'(?<!//)s7params.*MediaSet.asset\",\s\"(.*?)\"', self.page_raw_text)
        if data and base_path:
            response = self._request(self.MEDIA_URL.format(data.group(1).split(',')[0]))
            self.images = self._get_media_data(base_path, response.text)
            return self.images

    def _video_urls(self):
        if self.video_checked:
            return self.videos
        base_path = re.search(r'(?<!//)s7params.*videoserverurl\",\s\"(.*?)\"', self.page_raw_text)
        if base_path:
            base_path = 'https:' + base_path.group(1)
        data = re.search(r'(?<!//)s7params.*MediaSet.asset\",\s\"(.*?)\"', self.page_raw_text)
        if data and base_path:
            response = self._request(self.MEDIA_URL.format(data.group(1).split(',')[1]))
            self.videos = self._get_media_data(base_path, response.text)
            return self.videos

    def _pdf_urls(self):
        pdf_urls = []

        for link in self.tree_html.xpath('//a/@href'):
            if re.match('.*\.pdf$', link):
                pdf_urls.append(link)

        if pdf_urls:
            return pdf_urls

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    def _reviews(self):
        product_id = self.tree_html.xpath('//span[@class="productID"]/@data-masterid')

        if product_id:
            review_url = self.REVIEW_URL.format(product_id=product_id[0])
            return super(PetsmartScraper, self)._reviews(review_url=review_url)

    def _price(self):
        price_info = self.tree_html.xpath("//div[@class='ship-to-me-price']//div[@class='product-price']")

        if price_info:
            sale_price = price_info[0].xpath("//span[@class='price-sales']/text()")
            regular_price = price_info[0].xpath("//span[@class='price-regular']/text()")
            standard_price = price_info[0].xpath("//span[@class='price-standard']/text()")

        if sale_price:
            final_price = sale_price[0]
            self.temp_price_cut = 1
        elif regular_price:
            final_price = regular_price[0]
        elif standard_price:
            final_price = standard_price[0]
        else:
            final_price = None

        return final_price

    def _temp_price_cut(self):
        return self.temp_price_cut

    def _site_online(self):
        if re.search('(Not Sold Online)|(Sold in Stores)', self.page_raw_text):
            return 0
        return 1

    def _site_online_out_of_stock(self):
        if self._site_online():
            if re.search('Out of Stock Online', self.page_raw_text):
                return 1
            return 0

    def _in_stores(self):
        if re.search('Not Sold In Stores', self.page_raw_text):
            return 0
        return 1

    def _web_only(self):
        if not self._in_stores():
            return 1
        return 0

    def _home_delivery(self):
        if self._site_online():
            return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        category = self.tree_html.xpath('//a[@class="breadcrumb-element"]//text()')
        if category:
            category = self._clean_text(category[0].replace('back to', ''))
            return [category] if category else None
        elif self._get_product_data():
            category = self._get_product_data().get('category')
            return [category.replace('-', ' ')] if category else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        return re.sub('\s+', ' ', text).strip()

    def _clean_html(self, html):
        html = re.sub('<(\w+)[^>]*>', r'<\1>', html)
        return self._clean_text(html)

    @staticmethod
    def _get_media_data(base_path, raw_data):
        media_json = json.loads(re.search(r'\(({".*?),""\);', raw_data).group(1))
        items = media_json.get('set', {}).get('item', {})
        is_video = media_json.get('set', {}).get('type') == 'video_set'
        urls = []
        if isinstance(items, dict):
            items = [items]
        for data in items:
            url = data.get('i', {}).get('n')
            if url:
                if is_video:
                    if 'Flash9' in url:
                        urls.append(urlparse.urljoin(base_path, url))
                else:
                    urls.append(urlparse.urljoin(base_path, url))
        return urls if urls else None

    def _get_product_data(self):
        product_data = self.tree_html.xpath('//div[@class="product-actions"]/a/@data-gtm')
        return json.loads(product_data[0]) if product_data else None


    ##########################################
    ################ RETURN TYPES
    ##########################################
    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service
    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "brand" : _brand,
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo" : _title_seo,
        "features" : _features,
        "description" : _description,
        "long_description" : _long_description,
        "ingredients" : _ingredients,
        "directions" : _directions,
        "variants" : _variants,
        "no_longer_available" : _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls": _video_urls,
        "pdf_urls" : _pdf_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "temp_price_cut": _temp_price_cut,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores": _in_stores,
        "web_only": _web_only,
        "home_delivery": _home_delivery,

         # CONTAINER : REVIEWS
        "reviews": _reviews,

        # CONTAINER : CLASSIFICATION
        "categories": _categories
        }
