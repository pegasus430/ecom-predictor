import re
import urlparse
import string
import math

from scrapy import Request
from scrapy.conf import settings

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, cond_set_value,
                                     FLOATING_POINT_RGEX, FormatterWithDefaults)
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty


class ChicagofaucetshoppeProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'chicagofaucetshoppe_products'
    allowed_domains = ['chicagofaucetshoppe.com']
    handle_httpstatus_list = [404]

    SEARCH_URL = 'http://www.chicagofaucetshoppe.com/searchresults.asp?' \
                 'searching=Y&sort={sort_mode}&search={search_term}&' \
                 'show=180&page={page_num}'

    SORT_MODES = {
        'price_asc': '1',
        'price_desc': '2',
        'newest': '3',
        'oldest': '4',
        'most_popular': '5',
        'title': '7',
        'manufacturer': '9',
        'availability': '11',
    }

    def __init__(self, sort_mode='most_popular', *args, **kwargs):
        RETRY_HTTP_CODES = settings.get('RETRY_HTTP_CODES')
        if 404 in RETRY_HTTP_CODES:
            RETRY_HTTP_CODES.remove(404)
        self.SORTING = self.SORT_MODES[sort_mode.lower()]
        super(ChicagofaucetshoppeProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                sort_mode=self.SORTING, page_num=1),
            *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product['locale'] = "en-US"
        product['not_found'] = response.status == 404

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        price_original = self._parse_price_original(response)
        cond_set_value(product, 'price_original', price_original)

        brand = self._parse_brand(response, title)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)
        cond_set_value(product, 'reseller_id', sku)

        categories = self._parse_categories(response)
        if categories:
            cond_set_value(product, 'categories', categories)
            cond_set_value(product, 'department', categories[-1])

        variants = self._parse_variants(response)
        if variants:
            product['is_out_of_stock'] = False
            cond_set_value(product, 'price', Price('USD', variants[0]['price']))
            cond_set_value(product, 'variants', variants)

        return product

    @staticmethod
    def _parse_title(response):
        title = is_empty(
            response.xpath('//*[@itemprop="name"]/text()').extract()
        )

        return title

    @staticmethod
    def _parse_is_out_of_stock(response):
        is_out_of_stock = 'InStock' != is_empty(
            response.xpath(
                '//*[@itemprop="availability"]/@content'
            ).extract()
        )

        return is_out_of_stock

    @staticmethod
    def _parse_price(response):
        price = response.xpath('//div[@class="product_productprice"]//span').re(FLOATING_POINT_RGEX)
        return Price(price=price[0], priceCurrency='USD') if price else None

    @staticmethod
    def _parse_price_original(response):
        price_original = is_empty(
            response.xpath('.//*[@class="product_listprice"]/b/text()').re(FLOATING_POINT_RGEX)
        )
        if price_original:
            currency = is_empty(
                response.xpath(
                    '//*[@itemprop="priceCurrency"]/@content'
                ).extract(), 'USD'
            )
            price_original = Price(currency, price_original)
            return price_original
        return None

    @staticmethod
    def _parse_brand(response, title):
        brand = is_empty(
            response.xpath('//*[@itemprop="manufacturer"]/@content').extract()
        )
        if not brand and title:
            brand = guess_brand_from_first_words(title)

        return brand

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(
            response.xpath(
                '//a[contains(@id, "product_photo_zoom")]/@href|'
                '//*[@itemprop="image"]/@src'
            ).extract()
        )

        if image_url:
            if 'nophoto' in image_url:
                image_url = None
            else:
                image_url = urlparse.urljoin(response.url, image_url)

        return image_url

    @staticmethod
    def _parse_description(response):
        description = is_empty(response.xpath(
            '//table[@class="colors_descriptionbox"]|'
            '//span[@id="product_description"]'
        ).extract())

        return description

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath(
            '//td[contains(@class, "breadcrumb")]//a/text()'
        ).extract()

        return map(string.strip, categories)

    @staticmethod
    def _parse_sku(response):
        sku = is_empty(
            response.xpath('//*[@name="ProductCode"]/@value').extract()
        )

        return sku

    @staticmethod
    def _parse_variants(response):
        variants = []
        items = response.xpath('//tr[contains(@class, "Multi-Child")]')
        for item in items:
            sku = is_empty(item.xpath('td[1]/text()').extract())
            name = is_empty(item.xpath('td[2]/text()').extract())
            price = is_empty(item.xpath('td[4]//span').re(FLOATING_POINT_RGEX))
            variant = {'properties': {'sku': sku, 'name': name}, 'price': price}
            variants.append(variant)

        return variants

    def _scrape_total_matches(self, response):
        total_matches = is_empty(
            response.xpath(
                '//div[@class="matching_results_text"]'
            ).re('\d+'), 0
        )

        return int(total_matches)

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//a[contains(@class, "v-product__title")]/@href'
        ).extract()
        for link in links:
            prod = SiteProductItem()
            req = Request(
                url=link,
                callback=self.parse_product,
                dont_filter=True, # some items redirect to the same 404 page
                meta={'product': prod},
            )
            yield req, prod

    def _scrape_next_results_page_link(self, response):
        current_page = int(is_empty(re.findall('page=(\d+)', response.url), 0))
        totals = response.meta.get('total_matches')
        per_page = response.meta.get('products_per_page')
        if current_page and totals and per_page \
                and current_page < math.ceil(totals / float(per_page)):
            search_term = response.meta.get('search_term')
            url = self.url_formatter.format(self.SEARCH_URL, sort=self.SORTING,
                search_term=search_term, page_num=current_page + 1)
            return url
