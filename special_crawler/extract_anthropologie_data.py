#!/usr/bin/python

import re
import json
import requests

from lxml import html
from extract_data import Scraper
from spiders_shared_code.anthropologie_variants import AnthropologieVariants


class AnthropologieScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.anthropologie.com/shop/<product-name>"

    REVIEW_URL = "https://api.bazaarvoice.com/data/reviews.json?apiversion=5.4" \
                 "&passkey=earms252hrs84gbtggw3p47ou&Filter=ProductId:{}" \
                 "&Filter=ContentLocale:fr_CA,en_US&Include=Products,Comments,Authors" \
                 "&Stats=Reviews&Limit=5&Offset=0&Locale=en_US"

    VARIANTS_URL = 'https://www.anthropologie.com/orchestration/features/shop?' \
                   'exclude-filter=&includePools=00443&productId={}&trim=true'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = None
        self.variants_json = None

        self.av = AnthropologieVariants()

    def check_url_format(self):
        m = re.match('https?://www.anthropologie.com/shop/.*', self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype and itemtype[0].strip() == 'product':
            self._extract_product_json()
            self._extract_variants_json()

            if not self.product_json:
                return True

            self.av.setupCH(self.tree_html)

            return False

        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_product_json(self):
        try:
            product_json = self.tree_html.xpath('//script[@type="application/ld+json"]')[0].text_content()
            self.product_json = json.loads(product_json, strict=False)
        except:
            self.product_json = None

    def _extract_variants_json(self):
        try:
            prod_id = re.search('product_id : (.*?)]', html.tostring(self.tree_html))
            prod_id = prod_id.group(1).replace('[', '').replace('"', '')
            self.variants_json = requests.get(self.VARIANTS_URL.format(prod_id), timeout=10).json()
        except:
            self.variants_json = None

    def _product_id(self):
        try:
            return re.search('page_id : "PRODUCT:(.*?)",', html.tostring(self.tree_html)).group(1)
        except:
            return re.findall(r'\d+$', self.product_page_url)[0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_json['name']

    def _product_title(self):
        return self.tree_html.xpath("//meta[@property='og:title']/@content")[0].strip()

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        short_description = self.product_json['description']
        if short_description:
            if '**' in short_description:
                i = short_description.find("**")
                short_description_index = short_description[:i]
                if short_description_index:
                    if '\n' in short_description_index:
                        return short_description_index.replace('\n', '')
                    return short_description_index

            elif '\n' in short_description:
                short_description = short_description.replace('\n', '')
                return short_description

    def _variants(self):
        return self.av._variants(variants_json=self.variants_json)

    def _no_longer_available(self):
        if 'no longer available' in html.tostring(self.tree_html):
            return 1
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        media_info_xml_multiple = []
        image_url_info_list = []
        image_url_list = []

        current_color_id = self.tree_html.xpath(
            "//li[@class='o-list-swatches__li']"
            "/a[contains(@class, 'o-list-swatches__a o-list-swatches__a--selected js-swatch-link-product')]"
            "/@data-color-code")
        if current_color_id:
            current_color_id = current_color_id[0]

        current_image_list = self.tree_html.xpath(
            "//div[contains(@class, 'o-slider-thumbnails__slide--product-image')]"
            "//div[contains(@class, 'o-slider-thumbnails__slide-inner')]//img/@src")

        for current_image_url in current_image_list:
            current_image_url = current_image_url.replace('hei=150&', 'hei=900&').replace('//', 'http://')
            image_url_list.append(current_image_url)

        if self._canonical_link():
            product_url = self._canonical_link()
        image_url_temp = product_url + '?' + 'color=' + '{0}'

        color_info = self.variants_json['product']['skuInfo']['secondarySlice']['sliceItems'][0]['colorCodesForFit']

        if color_info:
            for color_id in color_info:
                if color_id != current_color_id:
                    try:
                        media_info_xml = html.fromstring(
                            self.load_page_from_url_with_number_of_retries(image_url_temp.format(color_id)))
                        media_info_xml_multiple.append(media_info_xml)
                    except Exception as e:
                        print str(e)

        for media_info_xml_single in media_info_xml_multiple:
            image_url_info = media_info_xml_single.xpath(
                "//div[contains(@class, 'o-carousel__inner js-carousel-zoom__inner--shadow-zoom')]"
                "//div[contains(@class, 'c-zoom-overlay')]//img/@src")
            image_url_info_list.append(image_url_info)

        if image_url_info_list:
            for image_url in image_url_info_list:
                for image_real_url in image_url:
                    image_real_url = image_real_url.replace('hei=150&', 'hei=900&').replace('//', 'http://')
                    image_url_list.append(image_real_url)

        if image_url_list:
            return image_url_list

    def _video_urls(self):
        video_urls = self.tree_html.xpath('//video[contains(@class, "c-product-video")]/@src')
        if video_urls:
            return [v.replace('//', 'http://') for v in video_urls]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        return self.product_json['offers']['lowPrice']

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath(
                "//ol[contains(@class, 'c-breadcrumb__ol u-clearfix')]"
                "//li[not(contains(@class, 'c-breadcrumb__li--last'))]//span[contains(@itemprop, 'name')]/text()")

        return categories if categories else None
    
    def _brand(self):
        return self.tree_html.xpath('//meta[@property="product:brand"]/@content')[0].replace('|', '').strip()

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
        "description" : _description,
        "variants" : _variants,
        "no_longer_available" : _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls" : _video_urls,

        # CONTAINER : SELLERS
        "price_amount" : _price_amount,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
    }
