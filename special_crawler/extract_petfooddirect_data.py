#!/usr/bin/python
#  -*- coding: utf-8 -*-

import re, json, requests
from lxml import html, etree
from extract_data import Scraper

class PetFoodDirectScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = 'Expected URL format is http://www.petfooddirect.com/product/<prod-id>/<prod-name>'

    def check_url_format(self):
        if re.match('^http://www\.petfooddirect\.com/product/\d+/.+$', self.product_page_url):
            return True
        return False

    def not_a_product(self):
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _url(self):
        return self.product_page_url

    def _product_id(self):
        return self._products_json()['productId']

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        try:
            return self.tree_html.xpath('//h1[@itemprop="name"]/text()')[0]
        except:
            return self.tree_html.xpath('//meta[@property="og:title"]/@content')[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self.tree_html.xpath('//title/text()')[0].strip()

    def _description(self):
        #description = self.tree_html.xpath('//div[@class="short_description"]')[0]
        #return self._clean_html(html.tostring(description))
        return self._products_json()['shortDescription']

    def _long_description(self):
        #long_description = self.tree_html.xpath('//div[@class="description"]')[0]

        # overlap with short description
        #long_description = self._description() + self._clean_html(html.tostring(long_description))
        long_description = self._description() + self._products_json()['description']
        if not long_description == self._description():
            return long_description

    def _features(self):
        features = self.tree_html.xpath('//div[@class="description"]//ul/li/text()')
        if features:
            return features

    def _feature_count(self):
        if self._features():
            return len(self._features())
        return 0

    def _ingredients(self):
        ingredients = []

        for ingredient_list in self.tree_html.xpath('//div[@class="product-ingredients"]/text()'):
            ingredient_list = map(self._clean_text, ingredient_list.split(','))
            ingredient_list = filter(len, ingredient_list)

            ingredients.extend(ingredient_list)

        if ingredients:
            return ingredients

    def _ingredient_count(self):
        if self._ingredients():
            return len(self._ingredients())
        return 0

    def _variants(self):
        variants = []

        products_json = self._products_json()

        for variant_id in products_json['childProducts']:
            variant = products_json['childProducts'][variant_id]

            properties = {}

            for attribute in products_json['attributes'].values():
                if attribute['label'] == 'Soft Roll Version':
                    continue

                for option in attribute['options']:
                    if variant_id in option['products']:
                        properties[ attribute['label']] = option['label']

            v = {
                'properties' : properties,
                'price' : float(variant['finalPrice']),
                'sku' : variant['productSku'],
                #'in_stock' : item_json['inventory']['onlineInventory']['status'] == 'In-Stock',
                'selected' : False,
            }

            variants.append(v)

        if len(variants) > 1:
            return variants

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _keywords(self):
        return self.tree_html.xpath('//meta[@name="keywords"]/@content')[0]

    def _htags(self):
        htags_dict = {}

        htags_dict['h1'] = map(lambda t: self._clean_text(t), self.tree_html.xpath('//h1//text()[normalize-space()!=""]'))
        htags_dict['h2'] = map(lambda t: self._clean_text(t), self.tree_html.xpath('//h2//text()[normalize-space()!=""]'))

        return htags_dict

    def _canonical_link(self):
        return self.tree_html.xpath('//link[@rel="canonical"]/@href')[0]

    def _image_urls(self):
        image_urls = []

        images = self.tree_html.xpath('//p[@class="image"]/img/@src')
        image_urls.extend(images)

        if image_urls:
            return image_urls

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())
        return 0

    def _video_urls(self):
        return None

    def _video_count(self):
        return None

    def _pdf_urls(self):
        pdf_urls = []

        for link in self.tree_html.xpath('//a/@href'):
            if re.match('.*\.pdf$', link):
                pdf_urls.append(link)

        if pdf_urls:
            return pdf_urls

    def _pdf_count(self):
        if self._pdf_urls():
            return len(self._pdf_urls())
        return 0

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    def _average_review(self):
        average_review = self.tree_html.xpath('//span[contains(@class,"average")]/text()')
        if average_review:
            return float(average_review[0])

    def _review_count(self):
        review_count = self.tree_html.xpath('//span[@class="count"]/text()')
        if review_count:
            return int(review_count[0])
        return 0

    def _max_review(self):
        if self._reviews():
            for review in self._reviews():
                if review[1] != 0:
                    return review[0]

    def _min_review(self):
        if self._reviews():
            for review in reversed(self._reviews()):
                if review[1] != 0:
                    return review[0]

    def _reviews(self):
        if self.tree_html.xpath('//span[@class="no-reviews"]'):
            return None

        reviews = []

        for i in reversed(range(1,6)):
            count = self.tree_html.xpath('//li[contains(@class,"pr-histogram-' + str(i) + 'Stars")]/p[@class="pr-histogram-count"]/span/text()')[0]

            count = int(re.match('\((\d+)\)', count).group(1))

            reviews.append([i, count])

        return reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _products_json(self):
        products_config = re.search('Product.Config\((.*)\);', self.page_raw_text).group(1)
        return json.loads(products_config)

    def _price(self):
        if self._variants():
            low_price = None
            high_price = None

            for variant in self._variants():
                if not low_price or variant['price'] < low_price:
                    low_price = variant['price']
                if not high_price or variant['price'] > high_price:
                    high_price = variant['price']

            max_price = self._products_json().get('maxPrice')
            if max_price:
                high_price = float(max_price)

            return '$%.2f - $%.2f' % (low_price, high_price)

        return self.tree_html.xpath('//span[@class="price"]/text()')[0].split(' - ')[0]

    def _price_amount(self):
        return float(self._price().split(' - ')[0][1:])

    def _price_currency(self):
        return self.tree_html.xpath('//meta[@property="product:price:currency"]/@content')[0]

    def _temp_price_cut(self):
        if self.tree_html.xpath('//span[@class="special"]'):
            return 1
        return 0

    def _web_only(self):
        return 1

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath('//div[@id="breadcrumbs"]/ul/li[not(@class="home") and not(@class="product")]')
        return map(lambda c: self._clean_text(c.text_content()), categories)

    def _category_name(self):
        if self._categories():
            return self._categories()[-1]

    def _brand(self):
        return re.search("setTargeting\('cm_bd', '([^']+)'\)", self.page_raw_text).group(1)

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        return re.sub('\s+', ' ', text).strip()

    def _clean_html(self, html):
        html = re.sub('<(\w+)[^>]*>', r'<\1>', html)
        return self._clean_text(html)

    ##########################################
    ################ RETURN TYPES
    ##########################################
    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service
    DATA_TYPES = { \
        # CONTAINER : NONE
        "url" : _url, \
        "product_id" : _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "description" : _description, \
        "long_description" : _long_description, \
        "features" : _features, \
        "feature_count" : _feature_count, \
        "ingredients" : _ingredients, \
        "ingredient_count" : _ingredient_count, \
        "variants" : _variants, \

        # CONTAINER : PAGE_ATTRIBUTES
        "htags" : _htags, \
        "keywords" : _keywords, \
        "canonical_link" : _canonical_link, \
        "image_urls" : _image_urls, \
        "image_count" : _image_count, \
        "video_urls" : _video_urls, \
        "video_count" : _video_count, \
        "pdf_urls" : _pdf_urls, \
        "pdf_count" : _pdf_count, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "temp_price_cut" : _temp_price_cut, \
        "web_only" : _web_only, \
        "in_stores" : _in_stores, \
        "site_online" : _site_online, \
        "site_online_out_of_stock" : _site_online_out_of_stock, \

         # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \
        "reviews" : _reviews, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand, \

        "loaded_in_seconds": None \
        }

    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
    }
