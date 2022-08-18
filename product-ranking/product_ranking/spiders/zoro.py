from __future__ import absolute_import, division, unicode_literals

import json
import re
import traceback
import urlparse

from OpenSSL import SSL
from scrapy.conf import settings
from scrapy.core.downloader.contextfactory import ScrapyClientContextFactory
from scrapy.http import Request
from scrapy.log import WARNING
from twisted.internet._sslverify import ClientTLSOptions
from twisted.internet.ssl import ClientContextFactory

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import Price, SiteProductItem
from product_ranking.powerreviews import parse_powerreviews_buyer_reviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator


class CustomClientContextFactory(ScrapyClientContextFactory):
    def getContext(self, hostname=None, port=None):
        ctx = ClientContextFactory.getContext(self)
        ctx.set_options(SSL.OP_ALL)
        if hostname:
            ClientTLSOptions(hostname, ctx)
        return ctx

class ZoroProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'zoro_products'
    allowed_domains = ["www.zoro.com"]

    SEARCH_URL = "https://www.zoro.com/search?q={search_term}"

    REVIEWS_URL = "http://readservices-b2c.powerreviews.com/m/297763/l/en_US/product/{product_id}/reviews?"

    def __init__(self, *args, **kwargs):
        super(ZoroProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.spiders.zoro.CustomClientContextFactory'
        settings.overrides['USE_PROXIES'] = False

        pipelines = settings.get('ITEM_PIPELINES')
        pipelines['product_ranking.pipelines.BuyerReviewsAverageRating'] = None
        settings.overrides['ITEM_PIPELINES'] = pipelines

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        price = self._parse_price(response)
        product['price'] = price

        if product.get('price'):
            product['price'] = Price(
                price=product['price'].replace(',', '').replace(
                    '$', '').strip(),
                priceCurrency='USD'
            )

        product['locale'] = "en-US"

        description = self._parse_description(response)
        product['description'] = description

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._category_name(response)
        product['category'] = category

        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        cond_set_value(product, 'reseller_id', sku)
        if sku:
            return Request(
                self.REVIEWS_URL.format(product_id=sku),
                self.parse_buyer_reviews,
                headers={'Authorization': '90d71773-2b19-45c6-a4ec-053f308ea2cd'},
                meta={'product': product},
                dont_filter=True
            )
        return product

    def _parse_title(self, response):
        title = response.xpath("//span[@itemprop='name']/text()").extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = response.xpath("//span[@itemprop='brand']/text()").extract()

        if brand:
            brand = brand[0]
        if not brand and title:
            brand = guess_brand_from_first_words(title)

        return brand

    def _parse_categories(self, response):
        categories = response.xpath("//div[@class='breadcrumb']//li//a/text()").extract()
        return categories[1:] if categories else None

    def _category_name(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    def _parse_description(self, response):
        description = response.xpath("//span[@itemprop='description']").extract()
        return description[0] if description else None

    def _parse_image_url(self, response):
        main_image = response.xpath("//div[@id='main-image']//div[@class='img-container']//img/@src").extract()
        return main_image[0] if main_image else None

    def _parse_price(self, response):
        price = response.xpath("//span[@itemprop='price']/@content").extract()
        return price[0] if price else None

    def _parse_model(self, response):
        model = response.xpath("//span[@itemprop='mpn']/text()").extract()
        return model[0] if model else None

    def _parse_sku(self, response):
        sku = response.xpath("//span[@itemprop='sku']/text()").extract()
        return sku[0] if sku else None

    def _parse_out_of_stock(self, response):
        oos = response.xpath('.//*[contains(@class, "GreenBold") and contains(text(), "Out of Stock")]')
        return bool(oos)

    def parse_buyer_reviews(self, response):
        product = response.meta.get("product")
        product['buyer_reviews'] = parse_powerreviews_buyer_reviews(response)
        return product

    def _scrape_total_matches(self, response):
        total_match = response.xpath("//div[contains(@class, 'number-display')]//div/text()").extract()

        if total_match:
            try:
                total_match = self._find_between(self._clean_text(total_match[0]), 'of', 'results').replace(',', '')
            except Exception:
                self.log("Error while parsing total match: {}".format(traceback.format_exc()), WARNING)
                total_match = 0

        return int(total_match) if total_match else None


    def _scrape_product_links(self, response):
        self.product_links = []
        try:
            data = json.loads(self._find_between(response.body, 'items: djangoList(', ']),') + ']')

            for product_info in data:
                self.product_links.append(product_info['url'])

            for item_url in self.product_links:
                yield item_url, SiteProductItem()

        except Exception:
            self.log("Error while parsing product links : {}".format(traceback.format_exc()), WARNING)
            return

    def _scrape_next_results_page_link(self, response):
        next_page_link = response.xpath("//a[contains(@class, 'next')]/@href").extract()
        if next_page_link:
            return urlparse.urljoin(response.url, next_page_link[0])

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _find_between(self, s, first, last, offset=0):
        try:
            s = s.decode("utf-8")
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""
