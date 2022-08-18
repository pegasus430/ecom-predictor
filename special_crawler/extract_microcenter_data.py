#!/usr/bin/python

import re
from extract_data import Scraper


class MicrocenterScraper(Scraper):
    INVALID_URL_MESSAGE = "Expected URL format is http://www.microcenter.com/product/<product-id>/<product-name>"
    REVIEW_URL = 'http://microcenter.ugc.bazaarvoice.com/3520-en_us/{}/reviews.djs?format=embeddedhtml'

    def check_url_format(self):
        m = re.match(r"^http://www\.microcenter\.com/product/[a-zA-Z0-9%\-\%\_]+/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if self.tree_html.xpath("//meta[@property='og:type' and @content='product']"):
            return False
        return True

    def _product_id(self):
        prod_id = self.tree_html.xpath('//span[@itemprop="name"]/span/@data-id')
        if prod_id:
            return prod_id[0]

    def _product_name(self):
        product_name = self.tree_html.xpath('//span[@itemprop="name"]/span/@data-name')
        if product_name:
            return product_name[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _model(self):
        model_info = self.tree_html.xpath('//dd[@itemprop="mpn"]/text()')
        if model_info:
            return model_info[0].strip()

    def _upc(self):
        upc = self.tree_html.xpath('//dd[preceding-sibling::dt[contains(text(), "UPC")]]/text()')
        if upc:
            return upc[0].strip()

    def _sku(self):
        sku = self.tree_html.xpath('//dd[@itemprop="sku"]/text()')
        if sku:
            return sku[0].strip()

    def _specs(self):
        specs = {}
        current_chapter = specs
        specs_pool = self.tree_html.xpath('//div[@class="SpecTable"]')
        if specs_pool:
            specs_pool = specs_pool[0]
            for string in specs_pool:
                if 'head' in string.xpath('@class')[0]:
                    chapter_name = string.xpath('div/text()')[0]
                    specs.update({chapter_name: {}})
                    current_chapter = specs[chapter_name]
                elif 'body' in string.xpath('@class')[0]:
                    label = string.xpath('div[1]/text()')[0]
                    value = string.xpath('div[2]/text()')[0]
                    current_chapter.update({label: value})
        return specs

    def _description(self):
        description = self.tree_html.xpath("//div[@itemprop='description']/p/text()")
        if description:
            return description[0].strip()

    def _no_longer_available(self):
        return 0

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//img[@class="productImageZoom"]/@src')
        if image_urls:
            image_urls = [url.replace('thumbnail', 'zoom') for url in image_urls]
            return image_urls
        else:
            main_image = self.tree_html.xpath('//img[@alt="Main Product Image"]/@src')
            if main_image:
                return main_image

    def _reviews(self):
        review_url = self.REVIEW_URL.format(self._product_id().zfill(7))
        return super(MicrocenterScraper, self)._reviews(review_url)

    def _price(self):
        price = self.tree_html.xpath('//span[@itemprop="price"]/text()')
        if price:
            return price[0].strip()

    def _price_amount(self):
        price_amount = self.tree_html.xpath('//span[@itemprop="price"]/@content')
        if price_amount:
            price_amount = price_amount[0]
            price_amount = price_amount.replace(',', '')
            return float(price_amount)

    def _price_currency(self):
        price_currency = self.tree_html.xpath('//span[@class="upper"]/text()')
        if price_currency:
            price_currency = price_currency[0]
            if '$' in price_currency:
                return "USD"
            return price_currency

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _temp_price_cut(self):
        price_cut = self.tree_html.xpath('//div[@class="savings"]')
        return 1 if price_cut else 0

    def _categories(self):
        categories = self.tree_html.xpath('//small/a/text()')
        if categories:
            categories = categories[1:-1]
            return categories

    def _brand(self):
        brand = self.tree_html.xpath('//span[@itemprop="name"]/span/@data-brand')
        if brand:
            return brand[0]

    DATA_TYPES = {
        "product_id": _product_id,

        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "model": _model,
        "sku": _sku,
        "upc": _upc,
        "description": _description,
        "specs": _specs,
        "no_longer_available": _no_longer_available,

        "image_urls": _image_urls,

        "review": _reviews,

        "price": _price,
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "temp_price_cut": _temp_price_cut,

        "categories": _categories,
        "brand": _brand,
    }
