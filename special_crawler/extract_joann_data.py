#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
from extract_data import Scraper
from lxml import html
from spiders_shared_code.joann_variants import JoannVariants
from product_ranking.guess_brand import guess_brand_from_first_words

class JoannScraper(Scraper):

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.joann.com/*"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?"\
                 "passkey=e7zwsgz8csw4fd3opkunhjl78"\
                 "&apiversion=5.5"\
                 "&displaycode=12608-en_us"\
                 "&resource.q0=products"\
                 "&&filter.q0=id:eq:{}"\
                 "&stats.q0=reviews"

    STOCK_URL = 'http://www.joann.com/on/demandware.store/Sites-JoAnn-Site/default' \
                '/ProductCont-QuantityControls?pid={sku}'

    WEBCOLLAGE_POWER_PAGE = "http://content.webcollage.net/joann/power-page?ird=true&channel-product-id={}"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.jv = JoannVariants()

    def _pre_scrape(self):
        self._extract_webcollage_contents()

    def check_url_format(self):
        m = re.match(r"https?://www.joann.com/.*", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if self.tree_html.xpath('//div[@class="pt_product-details"]') < 1:
            return True
        self.jv.setupCH(self.tree_html)
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _product_id(self):
        product_id = self.tree_html.xpath("//meta[@itemprop='productID']/@content")
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath('//span[@itemprop="name"]/text()')
        return product_name[0].strip() if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        title_seo = self.tree_html.xpath('//title/text()')
        return title_seo[0] if title_seo else None

    def _features(self):
        feature_items = self.tree_html.xpath('//div[@class="product-description"]/ul//li/text()')
        return feature_items if feature_items else None

    def _description(self):
        description = self.tree_html.xpath('//div[@id="short-description-content"]//p/text() | '
                                           '//div[@id="short-description-content"]/text()')
        if not description:
            description = self.tree_html.xpath('//div[@class="product-description"]/text()')
        return self._clean_text(''.join(description)) if description else None

    def _long_description(self):
        desc = self.tree_html.xpath('//div[@id="short-description-content"]//ul')
        return self._clean_text(html.tostring(desc[0])) if desc else None

    def _sku(self):
        sku = re.search(r'sku: \'(.*?)\'', self.page_raw_text)
        return sku.group(1) if sku else None

    def _variants(self):
        stock_info = self._parse_stocks()
        return self.jv._variants(stock_info)

    def _parse_stocks(self):
        stock_list = []
        sku_list = self.tree_html.xpath("//div[contains(@class, 'product-variant-tile')]/@data-pid")

        for sku_id in sku_list:
            url = self.STOCK_URL.format(sku=sku_id)
            stock_list.append(self.get_stock(url))
        return stock_list

    def get_stock(self, url):
        in_stock = True
        response = self._request(url)

        if response.ok:
            content = response.text
            raw_specs = html.fromstring(content)
            stock_option = html.tostring(raw_specs.xpath("//input[contains(@class, 'fancy-radio-button')]")[0])
            if 'disabled' in stock_option:
                in_stock = False

        return in_stock

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _image_urls(self):
        image_urls = []
        image_data = self.tree_html.xpath('//img[@class="productthumbnail"]/@data-yo-src')
        if image_data:
            for url in image_data:
                image_urls.append(url.replace(';', '&').replace('amp', ''))
        return image_urls

    def _video_urls(self):
        if self.wc_videos:
            return self.wc_videos

    def _pdf_urls(self):
        if self.wc_pdfs:
            return self.wc_pdfs

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price_amount(self):
        price = self.tree_html.xpath('//span[contains(@class, "on-sale")]/text() | '
                                     '//div[@class="variant-prices"]//span[contains(@class, "standard-price")]/text()')
        if price:
            price = re.search('\d+\.?\d*', price[0])
            return float(price.group()) if price else None

    def _site_online(self):
        return 1

    def _in_stores(self):
        online_only = self.tree_html.xpath('//span[contains(@class, "online-only")]/text()')
        if online_only and online_only[0].strip().lower() == 'online only - not sold in stores':
            return 0
        return 1

    def _site_online_out_of_stock(self):
        availability = self.tree_html.xpath('//div[contains(@class, "in-stock")]/text()')
        if self._clean_text(''.join(availability)).lower() == 'out of stock':
            return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath('//li[@class="breadcrumb"]//a/text()')
        categories = [self._clean_text(category) for category in categories if categories]
        return categories[1:] if categories else None

    def _brand(self):
        brand = guess_brand_from_first_words(self._product_name())
        return brand if brand else None

    ##########################################
    ################ RETURN TYPES
    ##########################################
    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "features": _features,
        "description": _description,
        "long_description": _long_description,
        "sku": _sku,
        "variants": _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,
        "pdf_urls": _pdf_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "site_online": _site_online,
        "in_stores": _in_stores,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }