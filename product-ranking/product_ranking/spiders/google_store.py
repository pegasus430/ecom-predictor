from urlparse import urljoin

import re
import string
import traceback
import urllib
from logging import WARNING

from scrapy.conf import settings
from scrapy.http import Request

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.guess_brand import guess_brand_from_first_words


class GoogleStoreProductsSpider(BaseProductsSpider):
    name = 'google_store_products'
    allowed_domains = ['store.google.com']

    DEFAULT_BRAND = 'Google'  # All products without leading brand in title are google
    DEFAULT_COUNTRY = {
        'code': 'us',
        'locale': 'en-US',
        'currency': 'USD',
    }

    COUNTRY = DEFAULT_COUNTRY  # Must override in subclasses
    SEARCH_URL = 'https://store.google.com/{country_code}/search?q={search_term}&hl={locale}'
    PRODUCT_LINK = "https://store.google.com/{country_code}{link}?hl={locale}"

    def __init__(self, *args, **kwargs):
        settings.overrides['USE_PROXIES'] = True
        super(GoogleStoreProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def start_requests(self):
        if not self.searchterms:
            for request in super(GoogleStoreProductsSpider, self).start_requests():
                yield request

        for st in self.searchterms:
            yield Request(
                url=self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote(st.encode('utf-8')),
                    country_code=self.COUNTRY.get('code', None),
                    locale=self.COUNTRY.get('locale', None)
                ),
                meta={
                    'search_term': st,
                    'remaining': self.quantity
                }
            )

    def parse_product(self, response):
        product = response.meta['product']

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        if not brand:
            brand = guess_brand_from_first_words(product.get('title', '').strip())
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse reseller_id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id, conv=string.strip)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse stock status
        out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        # Parse "no longer available"
        no_longer_available = self._parse_no_longer_available(response)
        cond_set_value(product, 'no_longer_available', no_longer_available)

        return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_next_results_page_link(self, response):
        # There is no pagination on this store
        pass

    def _scrape_total_matches(self, response):
        total_matches = response.xpath(
            '//div[@class="results-container"]'
            '//div[contains(@class, "search-results-header")]/text()'
        ).extract()

        if total_matches:
            total_matches = re.search(r'(\d+):?', total_matches[0])
            if total_matches:
                return int(total_matches.group(1))

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//*[contains(@class, "search-results-grid")]'
            '//*[contains(@class, "product")]'
            '/a[contains(@class, "card-link-target")]'
            '/@href'
        ).extract()
        for link in links:
            if not link.startswith("/" + self.COUNTRY["code"]):
                link = self.PRODUCT_LINK.format(country_code=self.COUNTRY.get("code", None),
                                                link=link, locale=self.COUNTRY.get("locale", None))
            yield link, SiteProductItem()

    @staticmethod
    def _parse_title(response):
        title = response.xpath(
            '//*[contains(@class, "title-price-container")]'
            '/*[contains(@class, "title-text")]'
            '/text()'
        ).extract()
        if title:
            return title[0]

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath(
            '//*[@itemprop="brand"]'
            '/@content'
        ).extract()
        if brand:
            return brand[0]

    def _parse_description(self, response):
        description = response.xpath(
            '//div[@class="column-section-container"]'
            '//*[contains(@class, "paragraph")]/text()'
        ).extract()

        if not description:
            description = response.xpath('//*[@itemprop="description"]/@content').extract()

        description = self._clean_text(" ".join(description))

        return description if description else None

    def _parse_price(self, response):
        currency = response.xpath('//meta[@itemprop="priceCurrency"]/@content').extract()
        if currency:
            currency = currency[0].strip()
        else:
            currency = self.COUNTRY.get('currency', None)

        price = response.xpath(
            '//span[@class="is-price"]/text()'
        ).extract()
        if price:
            try:
                price_amount = re.findall(FLOATING_POINT_RGEX, price[0])[0]
                return Price(
                    currency,
                    price=price_amount
                )
            except:
                self.log(
                    'Error while parsing price field {}'.format(traceback.format_exc()),
                    level=WARNING
                )

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = response.xpath(
            '//*[@itemprop="sku"]'
            '/@content'
        ).extract()
        if reseller_id:
            return reseller_id[0]

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath(
            '//div[contains(@class, "bg-cover")]'
            '//div[@data-breakpoint="MD"]/@data-src'
        ).extract()

        if not image_url:
            image_url = response.xpath(
                '//div[contains(@class, "bg-cover")]'
                '//div[@data-breakpoint="SM"]/@data-src'
            ).extract()

        if image_url:
            return urljoin(response.url, image_url[0])

        image_url = response.xpath(
            '//*[contains(@class, "background bg-cover")]'
            '/@data-default-src'
        ).extract()

        if image_url:
            return urljoin(response.url, image_url[0])

    @staticmethod
    def _parse_is_out_of_stock(response):
        in_stock = response.xpath(
            '//*[contains(@href, "InStock")]'
            '[@itemprop="availability"]'
        )
        return not in_stock

    @staticmethod
    def _parse_no_longer_available(response):
        # Impossible to get "inla" field
        pass

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t\r]", "", text).strip()
