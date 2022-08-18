#!/usr/bin/python

import re
from lxml import html

from extract_data import Scraper


class StoresScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://123stores.com/.*"

    def __init__(self, **kwargs):  # **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)
        self.product_json = None
        self._set_proxy()

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries(use_session=True)

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://123stores.com/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        return False if self.tree_html.xpath('//div[@itemtype="http://schema.org/Product"]') else True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _product_id(self):
        product_id = re.findall(r'var magicToolboxProductId = (.*?);', html.tostring(self.tree_html))
        return product_id[0] if product_id else None

    def _sku(self):
        sku = self.tree_html.xpath('//table[@id="product-attribute-specs-table"]/tr[contains(td/text(), "SKU")]'
                                   '/td[@class="data"]/text()')
        return sku[0] if sku else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        title = self.tree_html.xpath('//*[@class="product-name"]/text()')
        return self._clean_text(title[0]) if title else None

    def _brand(self):
        brand = self.tree_html.xpath('//table[@id="product-attribute-specs-table"]/tr[contains(td/text(), "Brand")]'
                                     '/td[@class="data"]/text()')
        return brand[0] if brand else None

    def _product_title(self):
        return self._product_name()

    def _model(self):
        short_description = self.tree_html.xpath('//div[@class="short-description"]')
        text = html.tostring(short_description[0]) if short_description else ""
        model = re.findall(r'<b>Model # </b>(.*?)<br>', text)
        return '#' + model[0] if model else None

    def _long_description(self):
        long_description = self.tree_html.xpath('//div[@id="product_tabs_description_contents"]//div[@class="product-specs"]')
        if not long_description:
            return None
        text = self._find_between(html.tostring(long_description[0]), '<div class="product-specs">', '</div>')
        return text if text else None

    def _description(self):
        short_desc = self.tree_html.xpath('//div[@class="short-description"]/text()')
        short_desc = self._clean_text(' '.join(short_desc))

        return short_desc

    def _upc(self):
        upc = self.tree_html.xpath('//table[@id="product-attribute-specs-table"]/tr[contains(td/text(), "UPC")]'
                                   '/td[@class="data"]/text()')
        return upc[0] if upc else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _image_urls(self):
        img_urls = self.tree_html.xpath('//div[contains(@id, "MagicToolboxSelectors")]//a[@onclick="magicToolboxOnChangeSelector(this);"]/@href')
        if not img_urls:
            img_urls = self.tree_html.xpath('//div[@class="product-img-box"]//img/@src')
        return img_urls if img_urls else None

    def _video_urls(self):
        video_url = self.tree_html.xpath('//iframe/@src')
        return video_url if video_url else None

    def _pdf_urls(self):
        pdf_urls = self.tree_html.xpath('//a[contains(@href, ".pdf")]/@href')
        return pdf_urls if pdf_urls else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//div[@class="price-box"]//*[@class="price"]/text()')
        return self._clean_text(price[0]) if price else None

    def _price_currency(self):
        return "USD"

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        out_of_stock = None
        stock_info = self.tree_html.xpath("//p[@class='non-availability']/text()")

        if stock_info:
            out_of_stock = stock_info[0].lower()
        if out_of_stock == 'availability: out of stock.':
            return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//ul[@class="breadcrumbs"]/li/a/text()')
        return categories[1:] if categories else None

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "model": _model,
        "sku": _sku,
        "upc": _upc,
        "description" : _description,
        "long_description" : _long_description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "pdf_urls": _pdf_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }