#!/usr/bin/python
#  -*- coding: utf-8 -*-

import re
import json
import traceback

from lxml import html
from extract_data import Scraper, deep_search


class AhScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.ah.nl/*"

    API_URL = "http://www.ah.nl/service/rest/delegate?url={product_url}"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.embedded_json = None
        self.source_json = None
        self.story_json = None

    def check_url_format(self):
        m = re.match("https?://www.ah.nl/.*", self.product_page_url)
        return bool(m)

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def not_a_product(self):
        self._get_embedded_json()

        if not self.embedded_json:
            return True

    def _get_embedded_json(self):
        url_frag = re.match('https?://www.ah.nl(.*)', self.product_page_url).group(1)
        api_url = self.API_URL.format(product_url=url_frag)

        try:
            self.source_json = self._request(api_url).text

            js = json.loads(self.source_json)
            self.embedded_json = next(lane for lane in js['_embedded']['lanes']
                                      if lane['type'] == 'ProductDetailLane')

            self.story_json = next(lane for lane in js['_embedded']['lanes']
                                   if lane['type'] == 'StoryLane')

            self.additional_json = next(lane for lane in js['_embedded']['lanes']
                                      if lane['type'] == 'Lane')

        except Exception as e:
            print traceback.format_exc()

            if self.lh:
                self.lh.add_list_log('errors', str(e))

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return deep_search('id', self.embedded_json)[0]

    def _sku(self):
        return str(deep_search('value', self.additional_json)[0])

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        name = deep_search('description', self.embedded_json)[0]
        unit_size = deep_search('unitSize', self.embedded_json)[0]
        return name.replace(u'\xad', '') + ', ' + unit_size

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _features(self):
        features = deep_search('features', self.embedded_json)
        if features and features[0]:
            return [r['text'] for r in features[0]]

    def _description(self):
        return deep_search('summary', self.embedded_json)[0]

    def _long_description(self):
        long_description = ''

        desc_json = next(lane for lane in self.story_json.get('_embedded', {}).get('items', [{}])[0]
                         .get('_embedded', {}).get('sections', {})
                         if lane.get('type') == 'StorySection')

        content = desc_json.get('_embedded', {}).get('content', [])

        if len(content) > 1:
            if content[0].get('text', {}).get('title'):
                body = content[1].get('text', {}).get('body', '').replace('[list]', '<ul><li>').replace('[/list]', '</li></ul>') \
                    .replace('[*]', '</li><li>').replace('<li></li>', '')
                long_description += body
            for desc in content[2:]:
                if desc.get('text', {}).get('subtitle', {}):
                    subtitle = '<h2>' + desc.get('text', {}).get('subtitle', '').strip() + '</h2>'
                    long_description += subtitle
                elif desc.get('text', {}).get('body', {}):
                    body = '<p>' + desc.get('text', {}).get('body', '').strip() + '</p>'
                    long_description += body

        return long_description if long_description else None

    def _ingredients(self):
        ingredients = re.search(u'Ingrediënten:(.+?)\.', self.source_json)
        if ingredients:
            return [i.strip() for i in ingredients.group(1).split(',')]

        source = json.loads(self.source_json)
        for lane in source['_embedded']['lanes']:
            ingredients_lane = json.dumps(lane, ensure_ascii=False)
            if re.search(u'Ingrediënten(.+?)\.', ingredients_lane) and \
                    re.search(u'"body":(.+?)\."', ingredients_lane):
                break
        else:
            ingredients_lane = None

        if ingredients_lane:
            ingredients = re.search(u'"body":(.+?)\."', ingredients_lane).group(1)
            ingredients = ingredients.replace('"', '').strip()
            if ingredients:
                # match all the commas which are not inside the parenthesis
                # example: 'vruchtensap 5% uit concentraat (limoensap 1,8%, citroensap 1,4%)'
                ingredients_list = re.split(r',\s*(?![^()]*\))', ingredients)
                if ingredients_list:
                    return [i.strip() for i in ingredients_list]

    def _warnings(self):
        warning_lane = None
        source = json.loads(self.source_json)
        for lane in source['_embedded']['lanes']:
            string_from_json = json.dumps(lane, ensure_ascii=False)
            if re.search(u'Bevat(.+?)\.', string_from_json) and \
                    re.search(u'"body":(.+?)\."', string_from_json):
                warning_lane = re.search(u'Bevat(.+?)\.', string_from_json).group()

        return warning_lane

    def _nutrition_facts(self):
        nutriton_facts = []
        try:
            source = json.dumps(json.loads(self.source_json)['_embedded']['lanes'])
            nutriton_html = re.search('"\[table](.+?)\[/table]', source).group().replace('\"', '').replace('[', '<').replace(']', '>').strip()
            nutriton_html = html.fromstring(nutriton_html).xpath(".//tr")
            for data in nutriton_html:
                if '<td>' in html.tostring(data):
                    nutriton_facts.append(': '.join(data.xpath('.//td/text()')))
        except:
            print traceback.format_exc()

        return nutriton_facts

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        arr = deep_search('images', self.embedded_json)[0]
        image_list = []
        max_height = max([img.get('height', 0) for img in arr])
        image = [img for img in arr if img['height'] == max_height]
        if image:
            image_list.append(image[0]['link']['href'])
        elif len(arr) > 1:
            image_list.append(arr[1]['link']['href'])
        else:
            image_list.append(arr[0]['link']['href'])

        return image_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = deep_search('priceLabel', self.embedded_json)[0]['now']
        return float(price)

    def _price_currency(self):
        return 'EUR'

    def _temp_price_cut(self):
        if deep_search('priceLabel', self.embedded_json)[0].get('was'):
            return 1
        return 0

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        if deep_search('availability', self.embedded_json)[0]['orderable']:
            return 0
        return 1

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = deep_search('categoryName', self.embedded_json)[0].split('/')
        return categories[:-1]

    def _brand(self):
        return deep_search('brandName', self.embedded_json)[0]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,
        "sku": _sku,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "title_seo": _title_seo,
        "features": _features,
        "description": _description,
        "long_description": _long_description,
        "ingredients": _ingredients,
        "warnings": _warnings,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "temp_price_cut": _temp_price_cut,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
