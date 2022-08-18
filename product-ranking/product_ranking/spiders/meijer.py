from __future__ import division, absolute_import, unicode_literals

import re
import string
import traceback
import urlparse

from scrapy import Request
from scrapy.log import INFO
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.guess_brand import guess_brand_from_first_words
from scrapy.conf import settings
from product_ranking.utils import is_empty


class MeijerProductsSpider(BaseProductsSpider):
    name = "meijer_products"
    allowed_domains = ["meijer.com"]

    SEARCH_URL = "https://www.meijer.com/catalog/search_command.cmd?keyword={search_term}"

    PRODUCTS_URL = "https://www.meijer.com/catalog/thumbnail_wrapper.jsp?" \
                   "tierId=&keyword={search_term}&sort=1&rows={rows}&start={start}" \
                   "&spellCorrection=&facet="

    STORE_URL = "https://www.meijer.com/includes/ajax/account_store_data.jsp"

    count_per_page = 40

    def __init__(self, *args, **kwargs):
        super(MeijerProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)
        # Fix for ssl issue
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

        self.current_page = 0
        self.total = 0

    def start_requests(self):
        yield Request(
            self.STORE_URL,
            callback=self._start_requests,
            dont_filter=True
        )

    def _start_requests(self, response):
        for request in super(MeijerProductsSpider, self).start_requests():
            request = request.replace(dont_filter=True)
            yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        no_longer_available = self._parse_no_longer_available(response)
        cond_set_value(product, 'no_longer_available', no_longer_available)

        in_store_only = self._parse_in_store_only(response)
        cond_set_value(product, 'is_in_store_only', in_store_only)

        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        brand = guess_brand_from_first_words(product.get('title', '').strip())
        if brand:
            cond_set_value(product, 'brand', brand)

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        price_per_volume, volume_measure = self._parse_price_volume(response)
        cond_set_value(product, 'price_per_volume', price_per_volume)
        cond_set_value(product, 'volume_measure', volume_measure)

        save_amount = self._parse_save_amount(response)
        cond_set_value(product, 'save_amount', save_amount)

        was_now  = self._parse_was_now(response)
        cond_set_value(product, 'was_now', was_now)

        cond_set_value(product, 'promotions', any([was_now, save_amount, price_per_volume]))

        out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        product['locale'] = "en-US"

        return product

    @staticmethod
    def _parse_no_longer_available(response):
        msg = response.xpath('//div[@id="noProductMsg"]/text()').extract()
        if msg and 'product not available' in msg[0].lower():
            return True

        return False

    @staticmethod
    def _parse_in_store_only(response):
        in_store_status = response.xpath("//button[contains(@class, 'instore')]/text()").extract()
        if in_store_status and 'available in-store only' in in_store_status[0].lower():
            return True
        return False

    @staticmethod
    def _parse_title(response):
        title = response.xpath("//h1[@itemprop='name']/text()").extract()
        return title[0] if title else None

    @staticmethod
    def _parse_upc(response):
        upc = response.xpath("//input[@name='upc']/@value").extract()

        return upc[0] if upc else None

    def _parse_description(self, response):
        description = response.xpath("//div[@itemprop='description']/text()").extract()
        description = self._clean_text("".join(description))

        return description if description else None

    @staticmethod
    def _parse_current_price(response):
        price = is_empty(response.xpath(
            "//input[@name='salePrice' and @value!='0.0']/@value"
        ).re(FLOATING_POINT_RGEX), None)
        if not price:
            price = is_empty(response.xpath(
                "//input[@name='price']/@value"
            ).re(FLOATING_POINT_RGEX), None)
        return price if price else None

    def _parse_price(self, response):
        currency = 'USD'
        price = self._parse_current_price(response)
        if price:
            return Price(price=float(price.replace(',', '')), priceCurrency=currency)

    @staticmethod
    def _parse_image(response):
        image_url = is_empty(response.xpath(
            "//li[@id='product-image']"
            "//img[@itemprop='image']/@src").extract())

        return urlparse.urljoin(response.url, image_url) if image_url else None

    def _parse_price_volume(self, response):
        volume_measure = is_empty(
            response.xpath('//span[@class="prodDtlSalePrice"]//span[@class="uom"]/text()').extract()
        )
        price_per_volume = is_empty(
            response.xpath('//span[@class="prodDtlSalePrice"]//span[@itemprop="price"]/text()').re(FLOATING_POINT_RGEX)
        )
        if all([volume_measure, price_per_volume]):
            return price_per_volume, self._clean_text(volume_measure)
        return None, None

    @staticmethod
    def _parse_save_amount(response):
        save_amount = is_empty(response.xpath('//span[@class="prodDtlSavings"]/text()').re(FLOATING_POINT_RGEX))
        return save_amount

    def _parse_was_now(self, response):
        old_price = is_empty(
            response.xpath('//div[@class="prodDtlRegPrice"]/text()').re(FLOATING_POINT_RGEX)
        )
        price = self._parse_current_price(response)
        if all([old_price, price]):
            return '{}, {}'.format(price, old_price)

    @staticmethod
    def _parse_out_of_stock(response):
        out_of_stock = False
        stock_string = response.xpath(
            "//span[@class='availability-message']/text()").extract()
        if stock_string and 'out of stock' in stock_string[0].lower():
            out_of_stock = True

        return out_of_stock

    def _scrape_total_matches(self, response):
        total_info = response.xpath(
            "//div[contains(@class, 'list-results')]"
            "//span[@class='pagination-summary' and contains(text(), 'of')]"
            "/following-sibling::span[@class='pagination-number']"
            "//text()").extract()

        try:
            self.total = int(total_info[0])
        except Exception as e:
            self.log('Total Match Error {}'.format(traceback.format_exc(e)))

        return self.total

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//div[contains(@class, 'grid-view')]"
            "//li[contains(@class, 'thumbFlexChild')]"
            "//div[contains(@class, 'thumb-image')]"
            "//a/@href").extract()

        if links:
            for item_url in links:
                yield item_url, SiteProductItem()
        else:
            self.log("Found no product links in {url}".format(
                url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        self.current_page += 1
        search_keyword = re.sub(r' +', '+', response.meta['search_term'].strip())
        start_number = self.count_per_page * self.current_page

        if start_number > self.total:
            return

        st = response.meta['search_term']
        return Request(
            self.PRODUCTS_URL.format(
                search_term=search_keyword,
                rows=self.count_per_page,
                start=start_number
            ),
            meta={
                'search_term': st,
                'remaining': self.quantity,
                'page': self.current_page
            }
        )

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t\r]", "", text).strip()
