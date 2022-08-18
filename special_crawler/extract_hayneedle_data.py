#!/usr/bin/python

import re
import json
import traceback

from lxml import html
import spiders_shared_code.canonicalize_url
from extract_data import Scraper, deep_search
from spiders_shared_code.hayneedle_variants import HayneedleVariants


class HayneedleScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.hayneedle.com/<product-name>"

    REVIEW_URL = 'https://readservices-b2c.powerreviews.com/m/9890/l/en_US/product/{}/reviews?'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self._set_proxy()

        self.hv = HayneedleVariants()

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

        # If there are no images, try once more (CON-36698)
        if not self._image_urls():
            self._extract_page_tree_with_retries()

    def canonicalize_url(self, url):
        return spiders_shared_code.canonicalize_url.hayneedle(url)

    def check_url_format(self):
        m = re.match('https?://www.hayneedle.com/.*', self.product_page_url)
        return bool(m)

    def not_a_product(self):
        self.hv.setupCH(self.tree_html)
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _extract_auth_key(self):
        auth_pwr = re.findall(r'"pwr_api_key":"(.*?)"', html.tostring(self.tree_html))
        if auth_pwr:
            return auth_pwr[0]

    def _product_json(self):
        product_json_text = self.tree_html.xpath('//script[@type="application/ld+json"]/text()')[0]
        return json.loads(product_json_text)

    def _variant_product_json(self):
        try:
            return json.loads(re.search('window.__models__ = ({.*})', html.tostring(self.tree_html)).group(1))
        except Exception as e:
            print traceback.format_exc()

            if self.lh:
                self.lh.add_list_log('errors', 'Error extracting variant product json: {}'.format(e))

            return {}

    def _product_id(self):
        item_no = self.tree_html.xpath('//span[contains(@class,"breadcrumb-sku")]')
        if item_no:
            item_no = re.search('Item # (.+)', item_no[0].text_content().strip())
            item_no = [item_no.group(1)] if item_no else None

        if not item_no:
            item_no = self.tree_html.xpath('//span[@id="HN_PP"]/text()')

        return item_no[0] if item_no else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@itemprop='name']/text()")
        if not product_name:
            product_name = self.tree_html.xpath("//div[contains(@class,'pdp-title')]//h1/text()")

        return product_name[0] if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self.tree_html.xpath("//title/text()")[0]

    def _features(self):
        feature_txts = iter(self.tree_html.xpath("//table[@class='specs-table']//tr/td/text()"))

        features = []
        for k, v in zip(feature_txts, feature_txts):
            if k.strip():
                features.append("%s: %s" % (k.strip(), v.strip()))

        if features:
            return features

    def _description(self):
        for v in self._variant_product_json().values():
            description = v.get('productInfo', {}).get('description')
            if description:
                return description

        description = self.tree_html.xpath("//div[@class='pdp-product-info-description']"
                                           "//div[@class='pdp-bot-module-right']//p/text()")

        return self._clean_text(' '.join(description)) if description else None

    def _bullets(self):
        bullets = []
        for value in self._variant_product_json().values():
            bullets_html = value.get('socialIcons', {}).get('currentProduct', {}).get('bullets')
            if bullets_html:
                bullets = html.fromstring(bullets_html).xpath("//li/text()")

        return "\n".join(bullets) if bullets else None

    def _variants(self):
        return self.hv._variants()

    def _no_longer_available(self):
        if self._price():
            return 0
        return 1

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        for v in self._variant_product_json().values():
            images = v.get('images', {}).get('images', {}).get('images')
            if images:
                return [i['url'][2:] for i in images]

        images = self.tree_html.xpath("//ul[@class='alt-img-cont']//li/@zimg")
        if not images:
            images = self.tree_html.xpath("//ul[@class='alt-img-cont']//li//img/@src")
            images = list(filter(lambda image: 'data:image' < image, images))

        return images if images else None

    def _fix_image_url(self, url):
        if isinstance(url, (list, tuple)):
            if not url:
                return
            url = url[0]
        url = url.replace('?is=70,70,0xffffff', '')[2:]
        return url

    def _video_urls(self):
        video_list = []
        video_url = re.search('contentUrl":"(.*?)",', html.tostring(self.tree_html))
        if video_url:
            video_list.append(video_url.group(1))
        return video_list if video_list else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = None
        dollar = self.tree_html.xpath('//span[@class="pdp-dollar-price"]/text()')
        cent = self.tree_html.xpath('//span[@class="pdp-cent-price"]/text()')
        if dollar and cent:
            price = [dollar[0] + '.' + cent[0]]

        if not price:
            price = self.tree_html.xpath(
                '//div[contains(@class, "lg-price-container")]'
                '//div[contains(@class, "lg-display-price-container")]//span/text()'
            )

        if not price:
            price = self.tree_html.xpath('//meta[@property="og:price:amount"]/@content')

        if price:
            if '$' in price[0]:
                price = price[0]
            else:
                price = '$' + price[0]

        return price

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        for i in self._product_json():
            if i.get('@type') == 'Product':
                if i.get('offers', {}).get('availability') == 'http://schema.org/InStock':
                    return 0

        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//*[contains(@class, "breadcrumbs")]//a/text()')
        if not categories:
            categories = self.tree_html.xpath('//div[@id="HN_Breadcrumbs"]//*[contains(@class, "text-small")]/text()')

        return categories[1:] if categories else None

    def _brand(self):
        brand = deep_search('brand', self._product_json())
        if brand:
            return brand[0].get('name')

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
        "features" : _features,
        "description" : _description,
        "variants": _variants,
        "no_longer_available" : _no_longer_available,
        "bullets": _bullets,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price" : _price,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
