# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import hjson
import re
import string

from scrapy.http import Request
from scrapy.log import ERROR, INFO, WARNING

from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults, \
    cond_set_value
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi

is_empty = lambda x, y=None: x[0] if x else y


class HalfordsProductSpider(BaseProductsSpider):

    name = 'halfords_products'
    allowed_domains = [
        "halfords.com",
        "halfords.ugc.bazaarvoice.com"
    ]

    SEARCH_URL = "http://www.halfords.com/webapp/wcs/stores/servlet/" \
                 "SearchCmd?srch={search_term}&action=search&storeId=10001" \
                 "&catalogId=10151&langId=-1"

    BUYER_REVIEWS_URL = "http://halfords.ugc.bazaarvoice.com/4028-redes/" \
                        "{product_id}/reviews.djs?format=embeddedhtml"

    IMG_URL = "http://i1.adis.ws/s/washford/684906_is.js?deep=true&" \
              "timestamp=1442469600000&arg=%{cat_code}_is%27&" \
              "func=amp.jsonReturn"

    _SORT_MODES = {
        'price asc': 'price-low-to-high',
        'price desc': 'price-high-to-low',
        'best seller': 'best-seller',
        'star rating': 'star-rating',
        'recommended': 'we-recommend'
    }

    def __init__(self, search_sort='recommended', *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)

        super(HalfordsProductSpider, self).__init__(
            site_name=self.allowed_domains[0],
            url_formatter=FormatterWithDefaults(
                sort=self._SORT_MODES[search_sort]
            ),
            *args, **kwargs)

    def parse_product(self, response):
        reqs = []
        product = response.meta['product']

        # Set locale
        product['locale'] = 'en_GB'

        # Set product id
        product_id = is_empty(
            response.xpath(
                '//input[@name="catCode"]/@value'
            ).extract(), '0'
        )

        # Set title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Set price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Set special pricing
        special_pricing = self._parse_special_pricing(response)
        cond_set_value(product, 'special_pricing', special_pricing, conv=bool)

        # Set image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Set categories
        category = self._parse_category(response)
        cond_set_value(product, 'category', category)
        if category:
            # Set department
            department = category[-1]
            cond_set_value(product, 'department', department, conv=string.strip)

        # Set variants
        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)
        # variant_request = Request(
        #     url=self.IMG_URL.format(cat_code=cat_code),
        #     callback=self.info_variant_parse,
        #     dont_filter=True,
        # )

        # reqs.append(variant_request)

        #  Set stock status
        is_out_of_stock = self._parse_stock_status(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock, conv=bool)

        #  Set description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        #  Parse related products
        related_products = self._parse_related_products(response)
        cond_set_value(product, 'related_products', related_products)

        # Parse buyer reviews
        if product_id:
            reqs.append(
                Request(
                    url=self.BUYER_REVIEWS_URL.format(product_id=product_id),
                    dont_filter=True,
                    callback=self.br.parse_buyer_reviews,
                    meta={'product': product, 'product_id': product_id},
                )
            )

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_title(self, response):
        title = is_empty(
            response.xpath(
                '//h1[@class="productDisplayTitle"]/text()'
            ).extract()
        )

        return title

    def _parse_price(self, response):
        price = is_empty(
            response.xpath('//div[@id="priceAndRating"]/h2/text()').extract(),
            0.00
        )
        if price:
            price = is_empty(
                re.findall(
                    r'(\d+\.?\d+?)',
                    price
                ), 0.00
            )

        return Price(
            price=price,
            priceCurrency='GBP'
        )

    def _parse_special_pricing(self, response):
        special_pricing = is_empty(
            response.xpath(
                '//div[@class="saveWasPricing"]/./'
                '/span[@class="wasValue"]'
            ).extract(), False
        )

        return special_pricing

    def _parse_image_url(self, response):
        image_url = is_empty(is_empty(
            response.xpath(
                '//img[@class="photo"]/@src'
            ).extract()).split('?'))

        return image_url

    def _parse_category(self, response):
        category = response.xpath(
            '//*[@id="breadcrumb"]/.//li/a/text()'
        ).extract()

        if category:
            category = category[1:]
            category[-1] = category[-1].strip()

        return category

    def _parse_stock_status(self, response):
        is_out_of_stock = is_empty(
            response.xpath(
                '//*[@id="productBuyable"][@class="hidden"]'
            ).extract(), False
        )

        return is_out_of_stock

    def _parse_description(self, response):
        description = is_empty(
            response.xpath(
                '//*[@id="descriptionDetails"]'
            ).extract()
        )

        return description

    def _parse_related_products(self, response):
        related_products = []
        data = response.xpath(
            '//*[@id="PDPCrossSellContent"]/li'
        )

        if data:
            for item in data:
                title = is_empty(
                    item.xpath(
                        './/a[@class="productModuleTitleLink"]/text()'
                    ).extract()
                )
                url = is_empty(
                    item.xpath(
                        './/a[@class="productModuleTitleLink"]/@href'
                    ).extract()
                )

                if url and title:
                    related_products.append(
                        RelatedProduct(
                            url=url,
                            title=title.strip()
                        )
                    )

        return related_products

    def _parse_variants(self, response):
        product = response.meta['product']

        number_of_variants = is_empty(
            re.findall(
                r'var ItemVariantSelectionWidget\s?=\s?\{(?:.|\n)+'
                r'numberOfVariants:\s+(\d+),',
                response.body_as_unicode()
            )
        )

        if number_of_variants:
            data = is_empty(
                re.findall(
                    r'(ItemVariantSelectionWidget\s?=\s?\{(?:.|\n)+?\};)',
                    response.body_as_unicode()
                )
            )

            name = is_empty(
                re.findall(
                    r'ItemVariantSelectionWidget\s?=\s?\{(?:.|\n)+variant1:\s+\{'
                    r'(?:.|\n)+name:\s+\'(.+)?\',',
                    data
                )
            )

            if name:
                name = name.replace('-', ' ').lower()

                variants_data = is_empty(
                    re.findall(
                        r'ItemVariantSelectionWidget\s?=\s?\{(?:.|\n)+multiVariantArray'
                        r':\s+(\[(?:.|\n)+?\]),',
                        data
                    )
                )
                try:
                    variants_data = hjson.loads(variants_data, object_pairs_hook=dict)
                except ValueError as exc:
                    self.log('Unable to parse variants on {url}: {exc}'.format(
                        url=response.url,
                        exc=exc
                    ), WARNING)
                    return []

                variants = []

                for item in variants_data:
                    image_url ='http://i1.adis.ws/i/washford/' + item['thumbNail'].replace('cdn/', '')
                    stock = item['inStock']
                    if item['value2'] == '':
                        color = None
                        size = item['value1']
                    else:
                        color = item['value1']
                        size = item['value2']
                    properties = {
                        name: size,
                        'image_url': image_url,
                        'color': color
                    }
                    variants.append({
                        'in_stock': stock,
                        'price': product['price'].price.__float__(),
                        'properties': properties
                    })

                return variants

        return []

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """
        req = reqs.pop(0)
        if reqs:
            req.meta["reqs"] = reqs

        return req

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        """
        Scraping number of resulted product links
        """
        total_matches = is_empty(
            response.xpath(
                '//*[@id="resultsTabs"]/.//a[@data-tabname="products"]'
                '/span/text()'
            ).extract(), '0'
        )

        if total_matches == '0':
            total_matches = is_empty(
                    response.xpath('//p[@id="productCount"]/span/text()'
                ).extract(), '0'
            )

        return int(total_matches)

    def _scrape_results_per_page(self, response):
        """
        Number of results on page
        """
        num = is_empty(
            response.xpath(
                '//*[@id="pgSize"]/option[@selected="selected"]'
                '/@value'
            ).extract(), '0'
        )

        return int(num)

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath(
            '//div[@id="product-listing"]/ul/li'
        )

        if items:
            for item in items:
                link = is_empty(
                    item.xpath('.//a[@class="productModuleImageLink"]/@href')
                        .extract()
                )
                res_item = SiteProductItem()
                yield link, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        url = is_empty(
            response.xpath(
                '//a[contains(@class, "pageLink next")]/@href').extract()
        )

        if url:
            return url
        else:
            self.log("Found no 'next page' links", WARNING)
            return None
