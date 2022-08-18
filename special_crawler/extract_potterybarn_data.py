#!/usr/bin/python

import re
import json
import traceback

from lxml import html
from extract_data import Scraper


class PotteryBarnScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = 'Expected URL format is http(s)://www.potterybarn.com/products/<product-name>'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = None

    def check_url_format(self):
        m = re.match('https?://www.potterybarn.com/products/', self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype[0].strip() == 'product':
            self._extract_product_json()
            return False

        return True

    def _extract_product_json(self):
        if self.product_json:
            return

        try:
            product_json_text = re.search('({"attributes":.*?});', html.tostring(self.tree_html), re.DOTALL).group(1)
            self.product_json = json.loads(product_json_text)
        except:
            self.product_json = None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = re.search('"name":"(.*?)",', html.tostring(self.tree_html))
        return product_name.group(1) if product_name else None

    def _product_title(self):
        return self.tree_html.xpath("//meta[@property='og:title']/@content")[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath("//meta[@property='og:title']/@content")[0].strip()

    def _description(self):
        description_block = self.tree_html.xpath("//div[contains(@class, 'accordion-contents')]//p")[0]
        short_description = html.tostring(description_block).strip()

        return short_description if short_description else None

    def _long_description(self):
        description_block = self.tree_html.xpath("//div[contains(@class, 'accordion-tab-copy')]")[0]
        long_description = ""
        long_description_start = False

        for description_item in description_block:
            if description_item.tag == "h4":
                long_description_start = True

            if long_description_start:
                long_description = long_description + html.tostring(description_item)

        long_description = long_description.strip()

        return long_description if long_description else None

    def _no_longer_available(self):
        arr = self.tree_html.xpath('//div[@id="main-content"]//div[contains(@class,"error")]//text()')
        if "to view is not currently available." in " ".join(arr).lower():
            return 1
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_info = self.tree_html.xpath(
            "//div[contains(@class, 'scroller')]/ul/li"
            "/a[not(contains(@class, 'videoThumbnail'))]/img/@src")
        image_list = []
        for image_url in image_info:
            image_url = image_url.replace('r.jpg', 'l.jpg')
            image_list.append(image_url)

        return image_list if image_list else None

    def _video_urls(self):
        video_json_text = self.tree_html.xpath("//div[contains(@class, 'scroller')]"
                                          "//ul/li/a[contains(@class, 'videoThumbnail')]"
                                          "/@data-thumbnail")

        video_url_list = []
        youtube_format = 'https://www.youtube.com/watch?v={0}'

        for video_info in video_json_text:
            video_id = re.findall(r'id: \'(.*?)\'}', video_info, re.DOTALL)[0]
            video_url = youtube_format.format(video_id)
            video_url_list.append(video_url)

        return video_url_list if video_url_list else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price_sale = self.tree_html.xpath(
            "//div[contains(@class, 'pip-summary')]"
            "//span[contains(@class, 'price-state price-sale')]"
            "//span[contains(@class, 'price-amount')]/text()")
        price_special = self.tree_html.xpath(
            "//div[contains(@class, 'pip-summary')]"
            "//span[contains(@class, 'price-state price-special')]"
            "//span[contains(@class, 'price-amount')]/text()")
        price_standard = self.tree_html.xpath(
            "//div[contains(@class, 'pip-summary')]"
            "//span[contains(@class, 'price-state price-standard')]"
            "//span[contains(@class, 'price-amount')]/text()")

        ajax_price = re.search('min :(.*?),', html.tostring(self.tree_html), re.DOTALL)
        if ajax_price:
            ajax_price = ajax_price.group(1).replace('\n', '').strip()

        if price_sale:
            price_amount = price_sale[0].replace(',', '')
        elif price_special:
            price_amount = price_special[0].replace(',', '')
        elif price_standard:
            price_amount = price_standard[0].replace(',', '')
        else:
            price_amount = ajax_price

        try:
            price_amount = float(re.findall(r"\d*\.\d+|\d+", str(price_amount))[0])
        except Exception as e:
            print traceback.format_exc(e)

        return price_amount if price_amount else None

    def _temp_price_cut(self):
        return self.product_json["itemExtension"]["localStoreSku"]["pricing"]["itemOnSale"]

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath(
            "//ul[@class='breadcrumb-list']"
            "//span[@itemprop='name']/text()")[1:]

        return categories if categories else None

    def _brand(self):
        brand = re.search('brand: (.*?),', html.tostring(self.tree_html))
        return brand.group(1).replace('"', '') if brand else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "description": _description,
        "long_description": _long_description,
        "no_longer_available": _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "temp_price_cut": _temp_price_cut,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "in_stores_out_of_stock": _in_stores_out_of_stock,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
