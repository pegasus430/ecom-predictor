# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals

import json
import re
import string
import traceback
import urlparse

from scrapy.conf import settings

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults, cond_set_value)
from spiders_shared_code.telusca_variants import TelusCAVariants


class TelusCAProductsSpider(BaseProductsSpider):
    name = 'telusca_products'
    allowed_domains = ["telus.com"]

    SEARCH_URL = 'https://www.telus.com/search/api?q={search_term}&page={page_number}' \
                 '&filter=all&language=en&api=true'

    def __init__(self, *args, **kwargs):
        self.current_page = 1
        url_formatter = FormatterWithDefaults(page_number=1)

        super(TelusCAProductsSpider, self).__init__(
            url_formatter=url_formatter,
            site_name=self.allowed_domains[0],
            *args, **kwargs
        )

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta.get('product')

        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        brand = self._parse_brand(response)
        if not brand:
            brand = guess_brand_from_first_words(product.get('title', ''))
        cond_set_value(product, 'brand', brand)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        cond_set_value(product, 'reseller_id', sku)

        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        # Parse out of stock
        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        cond_set_value(product, 'locale', "en_CA")

        return product

    def _parse_title(self, response):
        xpathes = "//*[contains(@class, 'product-feature__title')]/text() |" \
                  "//h1[@id='page-title']/text() |" \
                  "//div[@class='device-config__device-name']//h1/text() |" \
                  "//div[contains(@class, 'page-title')]//h2/text() |" \
                  "//title/text()"

        product_title = response.xpath(xpathes).extract()

        if product_title:
            product_title = re.sub(u'\u2013|TELUS.com|- TELUS.com|Mobility|\|', '', product_title[0]).strip()
            return product_title

    def _parse_brand(self, response):
        brand = response.xpath(
            "//*[contains(@class, 'product-feature__brand')]/text()"
        ).extract()

        if not brand:
            brand = response.xpath(
                "//div[@class='device-config__device-name']//p/text()"
            ).extract()

        return brand[0] if brand else None

    def _parse_sku(self, response):
        sku = re.search('"sku":(.*?),', response.body)
        return sku.group(1).replace('\"', '').strip() if sku else None

    def _parse_upc(self, response):
        upc = re.search('"upc":(.*?),', response.body)
        return upc.group(1).replace('\"', '').strip() if upc else None

    def _parse_price(self, response):
        price_no_term = None
        price_groups = response.xpath("//div[contains(@class, 'price-options__item')]")
        for price_group in price_groups:
            if 'No term' in price_group.extract():
                price_no_term = price_group.xpath(".//span[contains(@class, 'price-options__tier-price')]"
                                                  "//span/text()").extract()

        if not price_no_term:
            price_groups = response.xpath("//div[@class='radio-selector-item__outer-container']")
            for price_group in price_groups:
                no_term = price_group.xpath("//input[@id='no-term']")
                if no_term:
                    price_no_term = price_group.xpath(".//*[@class='price__amount']/text()").extract()

        if price_no_term:
            price = price_no_term
        else:
            xpathes = "//h2[contains(@class, 'product-sale__title')]/@content |" \
                      "//p[@itemprop='price']/text() |" \
                      "//span[contains(@class, 'price-options__tier-price')]//span/text() |" \
                      "//h2[contains(@class, 'product-sale__title')]/text() |" \
                      "//div[@class='no-term']//h4//span/text() |" \
                      "//div[@class='detail-price']//div[@class='device-balance']" \
                      "//div[@class='no-term']//h4//span/text() |" \
                      "//span[@itemprop='price']/@content"

            price = response.xpath(xpathes).extract()

        try:
            price = float(re.search(r'\d*\.\d+|\d+', price[0].replace(',', '')).group())
            return Price(price=price, priceCurrency='CAD')
        except Exception as e:
            self.log('Price error {}'.format(traceback.format_exc(e)))

    def _parse_image_url(self, response):
        xpathes = '//div[@class="product-detail-slide__image"]//img/@src |' \
                  '//div[@class="product-image"]//img/@src |' \
                  '//div[contains(@class, "device-image-container")]//img[@class="device-image"]/@src'

        image = response.xpath(xpathes).extract()
        domain = 'https:'

        return urlparse.urljoin(domain, image[0]) if image else None

    def _parse_description(self, response):
        feature_blocks = response.xpath("//div[@class='collapsible-panel']")

        for block in feature_blocks:
            if 'Specifications' in block.xpath(".//*[@class='collapsible-panel__header']/text()").extract():
                long_desc = block.xpath(".//div[@class='collapsible-panel__content']").extract()
                if long_desc:
                    long_desc = self._clean_text(long_desc[0])

                    return long_desc

    def _parse_variants(self, response):
        tv = TelusCAVariants()
        tv.setupSC(response)

        return tv._variants()

    def _parse_out_of_stock(self, response):
        product_msg = response.xpath("//div[@class='product-quantity']"
                                     "//div[@class='product-feature-attribute__child']"
                                     "//p/text()").extract()
        if product_msg and 'Out of stock' in product_msg[0]:
            return True

        return False

    def _scrape_total_matches(self, response):
        try:
            products_data = json.loads(response.body).get('data')
            return int(products_data.get('totalResults', 0))
        except Exception as e:
            self.log('Total Matches error {}'.format(traceback.format_exc(e)))

    def _scrape_product_links(self, response):
        try:
            products_data = json.loads(response.body).get('data')
            items = products_data.get('item', [])

            for item in items:
                yield item.get('formattedUrl'), SiteProductItem()
        except Exception as e:
            self.log('Product Links error {}'.format(traceback.format_exc(e)))

    def _scrape_next_results_page_link(self, response):
        total_page_numbers = json.loads(response.body).get('data', {})\
            .get('pagination', {})\
            .get('totalNumberOfPages', 0)

        if self.current_page > total_page_numbers:
            return

        self.current_page += 1
        st = response.meta.get('search_term')

        return self.SEARCH_URL.format(search_term=st, page_number=self.current_page)

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
