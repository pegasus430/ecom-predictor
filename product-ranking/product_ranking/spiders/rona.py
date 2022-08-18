from __future__ import division, absolute_import, unicode_literals

import re
import urllib
import traceback
import urlparse

from scrapy.http import Request
from scrapy.conf import settings
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, \
    FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.utils import is_empty


class RonaProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'rona_products'
    allowed_domains = ["www.rona.ca"]

    SEARCH_URL = "https://www.rona.ca/webapp/wcs/stores/servlet/RonaAjaxCatalogSearchView?" \
                 "storeId={store_id}&catalogId={catalog_id}&langId={lang_id}&resultCatEntryType={entry_type}" \
                 "&searchKey=RonaEN&content=&keywords={search_term}"

    def __init__(self, *args, **kwargs):
        settings.overrides['USE_PROXIES'] = False
        settings.overrides['DOWNLOAD_DELAY'] = 1

        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes += [403, 302]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

        super(RonaProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

    def start_requests(self):
        yield Request(
            url="https://www.rona.ca/en",
            callback=self.after_start,
        )

    def after_start(self, response):
        storeId = is_empty(response.xpath(
            "//input[@name='storeId']/@value").extract(), "")
        catalogId = is_empty(response.xpath(
            "//input[@name='catalogId']/@value").extract(), "")
        langId = is_empty(response.xpath(
            "//input[@name='langId']/@value").extract(), "")
        entry_type = is_empty(response.xpath(
            "//form/.//input[@name='resultCatEntryType']/@value").extract(), "")

        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                    store_id=storeId, catalog_id=catalogId,
                    lang_id=langId, entry_type=entry_type
                ),
                meta={'search_term': st, 'remaining': self.quantity},
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})

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
        cond_set_value(product, 'price', price)

        product['locale'] = "en-US"

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._category_name(response)
        cond_set_value(product, 'department', category)

        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)
        cond_set_value(product, 'reseller_id', sku)

        return product

    def _parse_title(self, response):
        title = response.xpath("//h1[@itemprop='name']/text()").extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = response.xpath("//span[@itemprop='brand']/text()").extract()
        if not brand:
            brand = response.xpath('//span[@class="page-product__top-info__brand__name"]/a/text()').extract()

        if brand:
            brand = brand[0]
        if not brand and title:
            brand = guess_brand_from_first_words(title)

        return brand

    def _parse_categories(self, response):
        categories = response.xpath("//div[@id='breadcrumb']//a/text()").extract()
        return categories[1:] if categories else None

    def _category_name(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    def _parse_image_url(self, response):
        image = response.xpath('//meta[@property="og:image"]/@content').extract()
        return image[0] if image else None

    def _parse_price(self, response):
        price_integer = response.xpath('//div[contains(@class, "price-box")]'
                                       '//span[@class="price-box__price__amount__integer"]/text()').extract()

        price_decimal = response.xpath('//div[contains(@class, "price-box")]'
                                       '//*[@class="price-box__price__amount__decimal"]/text()').extract()

        if not price_decimal:
            price_decimal = ['00']

        price = None
        try:
            price = float('.'.join([price_integer[0], price_decimal[0]]))
        except:
            self.log("Error parsing price {}".format(traceback.format_exc()))

        if price:
            return Price(price=price, priceCurrency='CAD')

    def _parse_out_of_stock(self, response):
        oos = response.xpath('.//*[contains(@class, "GreenBold") and contains(text(), "Out of Stock")]')
        return bool(oos)

    def _parse_sku(self, response):
        sku = response.xpath("//meta[@itemprop='sku']/@content").extract()
        return sku[0] if sku else None

    def _parse_model(self, response):
        model = response.xpath("//meta[@itemprop='mpn']/@content").extract()
        return model[0] if model else None

    def _scrape_total_matches(self, response):
        total_match = response.xpath("//a[@id='Products']/text()").re(r'\d+')
        if not total_match:
            total_match = response.xpath("//h1[@class='sidebar__title']/text()").re(r'\d+')

        return int(total_match[0]) if total_match else 0

    def _scrape_product_links(self, response):
        product_links = response.xpath("//div[@class='productBox']/a[@class='productLink']/@href").extract()
        if not product_links:
            product_links = response.xpath("//div[contains(@class, 'product-tile')]"
                                           "//a[contains(@class, 'product-tile__title')]/@href").extract()

        for item_url in product_links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page_link = response.xpath("//a[contains(@class, 'pagination__button-arrow--next')]/@href").extract()
        if next_page_link:
            return urlparse.urljoin(response.url, next_page_link[0])
