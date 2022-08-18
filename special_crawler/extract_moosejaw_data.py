#!/usr/bin/python

import re
from lxml import html
from extract_data import Scraper
from spiders_shared_code.moosejaw_variants import MoosejawVariants


class MoosejawScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=llqzkbnfdrdrj79t4ci66vkeh" \
            "&apiversion=5.5" \
            "&displaycode=18209-en_us" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=reviews"

    VIDEO_URL = "https://www.youtube.com/embed/{}?showinfo=0&modestbranding=1" \
                "&rel=0&iv_load_policy=3&enablejsapi=1&origin=https%3A%2F%2Fwww.moosejaw.com&widgetid=1"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.mv = MoosejawVariants()

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype and itemtype[0] == 'product':
            self.mv.setupCH(self.tree_html)
            return False

        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//span[@id='pd_skuText']/text()")
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//span[@id='product_name']/text()")
        return product_name[0] if product_name else None

    def _description(self):
        short_description = self.tree_html.xpath("//span[@itemprop='description']//p/text()")
        return short_description[0] if short_description else None

    def _long_description(self):
        long_description = self.tree_html.xpath("//article[@class='pdp-productFeatures']//ul")
        if long_description:
            long_description = html.tostring(long_description[0])

        return long_description

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _video_urls(self):
        video_id = re.search(r"videoId: '(.*?)'", html.tostring(self.tree_html))
        if video_id:
            return [self.VIDEO_URL.format(video_id.group(1))]

    def _image_urls(self):
        image_url_list = []
        image_urls_info = self.tree_html.xpath("//div[@class='alt-color-img-box']//img/@src")
        if image_urls_info:
            for image_url in image_urls_info:
                image_url_list.append('https:' + image_url.replace('50', '1000'))
                image_url_list = list(set(image_url_list))

        return image_url_list

    def _variants(self):
        return self.mv._variants()

    def _swatches(self):
        return self.mv.swatches()

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//span[@class='price-set']//span/text()")
        return self._clean_text(price[0]) if price else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//div[@class='breadcrumb-itm']"
                                          "//a//span[@itemprop='title']/text()")

        return categories[1:] if categories else None

    def _brand(self):
        brand = self.tree_html.xpath("//meta[@itemprop='brand']/@content")
        return brand[0] if brand else None

    def _sku(self):
        sku = self.tree_html.xpath("//meta[@itemprop='sku']/@content")
        return sku[0] if sku else None

    def _specs(self):
        specs = {}
        specs_groups = self.tree_html.xpath('//div[@class="pdp-table-container"]//tr')
        for spec in specs_groups:
            spec_set = spec.xpath('.//td/text()')
            if spec_set:
                spec_name, spec_value = spec_set[0].strip(), spec_set[1].strip()
            if spec_name and spec_value:
                specs.update({spec_name: spec_value})

        return specs if specs else None

    def _clean_text(self, text):
        return re.sub("[\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "sku": _sku,
        "description": _description,
        "long_description": _long_description,
        "swatches": _swatches,
        "variants": _variants,
        "specs": _specs,

        # CONTAINER : PAGE_ATTRIBUTES
        "video_urls": _video_urls,
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
