#!/usr/bin/python

import re
from lxml import html
import urlparse
import traceback
from extract_data import Scraper


class DollarTreeScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.dollartree.com/.*"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
                  "passkey=ca4585394e115511e6b1d60ea0ad7a5351&" \
                  "apiversion=5.5&" \
                  "displaycode=16649-en_us&" \
                  "resource.q0=products&" \
                  "filter.q0=id:eq:{}&" \
                  "stats.q0=reviews"

    VIDEO_API_URL = "https://sc.liveclicker.net/service/getXML?widget_id={}"

    def __init__(self, **kwargs):  # **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)
        self._set_proxy()

        self.video_urls_checked = False
        self.video_urls = None

    def check_url_format(self):
        m = re.match(r"^https?://www.dollartree.com/.*?", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[@id="content_wrap"]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_id(self):
        product_id = re.search(r'"product_id"   : \["(\d+)"\]', html.tostring(self.tree_html), re.DOTALL)
        return product_id.group(1) if product_id else None

    def _sku(self):
        sku = re.search(r'SKU: (\d+)', html.tostring(self.tree_html), re.DOTALL)
        return sku.group(1) if sku else None

    def _brand(self):
        brand = re.search('Brand(</b>|</strong>):&#160;(.*?)&', html.tostring(self.tree_html), re.DOTALL).group(2)
        return brand

    def _product_name(self):
        return self._product_title()

    def _product_title(self):
        title = re.search(r'"product_name"   : \["(.*?)"\]', html.tostring(self.tree_html), re.DOTALL)
        return title.group(1).strip() if title else None

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        description = self.tree_html.xpath('//div[@id="productDescription"]//p/text()')
        if not description:
            description = self.tree_html.xpath('//div[@id="productDescription"]/text()')
        if description:
            description = self._clean_text(description[0])
            return description

    def _specs(self):
        specs = {}

        for elem in self.tree_html.xpath("//div[@class='productDesc']"):
            if elem.xpath('./p[contains(@id, "specifications")]/text()')[0].strip() == 'Specifications':
                spec_name_list = elem.xpath('./strong/text()')
                spec_value_list = elem.xpath('./text()')
                spec_value_list = filter(None, [i.replace(':', '').strip() for i in spec_value_list])
                for spec_name in spec_name_list:
                    if len(spec_name_list) == len(spec_value_list):
                        specs[spec_name] = spec_value_list[spec_name_list.index(spec_name)]
                return specs

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        temp_urls = self.tree_html.xpath('//div[@class="altImageContainer"]//img/@src')
        for url in temp_urls:
            image_urls.append(url.replace('thumbnail', 'xlarge'))
        return image_urls

    def _video_urls(self):
        if self.video_urls_checked:
            return self.video_urls

        self.video_urls_checked = True

        external_url = self.tree_html.xpath('//div[@id="videos"]//script/@src')
        try:
            data = self._request(urlparse.urljoin(self.product_page_url, external_url[0])).content
            widget_id = re.search("widget_id=(.*?)&", data).group(1)
            video_info = self._request(self.VIDEO_API_URL.format(widget_id)).content
            self.video_urls = [re.search('<location>(.*?)</location>', video_info).group(1)]
            return self.video_urls
        except:
            print traceback.format_exc()

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        review_url = self.REVIEW_URL.format(self._sku())
        return super(DollarTreeScraper, self)._reviews(review_url=review_url)

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath(
            '//span[@class="unitCaseNum"]'
            '/text()'
        )
        price = re.search('(.*) Per', price[0]).group(1)
        return price

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if "The item you have selected is currently out of stock" in html.tostring(self.tree_html):
            return 1
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//div[@id="breadcrumb"]'
                                          '//li/a/text()')
        return [self._clean_text(category) for category in categories[1:]]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {

        # CONTAINER : PRODUCT_INFO
        "brand": _brand,
        "product_id": _product_id,
        "sku": _sku,
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo": _title_seo,
        "description": _description,
        "specs": _specs,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,

        }
