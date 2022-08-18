# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider
from product_ranking.spiders import FormatterWithDefaults
from product_ranking.spiders import cond_set_value
from scrapy.log import DEBUG
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
import urlparse


class JohnlewisProductsSpider(BaseProductsSpider):
    name = 'johnlewis_products'
    allowed_domains = ["www.johnlewis.com", "johnlewis.ugc.bazaarvoice.com"]

    SEARCH_URL = "http://www.johnlewis.com/search?Ntt={search_term}&Ns={sort_mode}"
    SORT_MODES = {
        "default": "",
        "priceHigh": "p_price.extravaganzaPriceListId|1",
        "priceLow": "p_price.extravaganzaPriceListId|0",
        "AZ": "p_displayName|0",
        "ZA": "p_displayName|1",
        "New": "p_dateAvailable|1",
        "popularity": "p_popularity|1",
        "rating": "p_productRating.averageRating|1||p_productRating.numberOfReviews|1",
    }

    def __init__(self, sort_mode="", *args, **kwargs):
        if sort_mode not in self.SORT_MODES:
            self.log('"%s" not in SORT_MODES')
            sort_mode = ''

        self.br = BuyerReviewsBazaarApi(called_class=self)
        formatter = FormatterWithDefaults(sort_mode=sort_mode)
        super(JohnlewisProductsSpider, self).__init__(
            formatter,
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        if response.xpath('''.//h1[contains(text(), "Sorry, we couldn't find this page")]'''):
            product["not_found"] = True
            return product

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        # Parse out of stock
        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # TODO implement reviews
        # # Parse buyer reviews
        # buyer_reviews = self._parse_buyer_reviews(response)
        # cond_set_value(product, 'buyer_reviews', buyer_reviews)

        # Parse reseller id
        _reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', _reseller_id)

        # Parse upc
        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        cond_set_value(product, 'category', categories[-1]) if categories else None

        # Parse variants
        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        return product

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id_regex = "/(p\d+)"
        reseller_id = re.findall(reseller_id_regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        return reseller_id

    @staticmethod
    def _parse_brand(response):
        brand = re.search('"brand":\s"(.*?)",', response.body_as_unicode())
        return brand.group(1).strip() if brand else None

    @staticmethod
    def _parse_title(response):
        title = re.search('"name":\s"(.*?)",', response.body_as_unicode())
        return title.group(1).strip() if title else None

    @staticmethod
    def _parse_out_of_stock(response):
        out_of_stock = response.xpath('.//p[starts-with(@class,"out-of-stock")]')
        return bool(out_of_stock)

    def _parse_price(self, response):
        price = re.search('"price":\s"(.*?)",', response.body_as_unicode())
        if price:
            price = price.group(1).replace('£', '')
            currency = re.search('"priceCurrency":\s"(.*?)"', response.body_as_unicode())
            currency = currency.group(1) if currency else None
            try:
                return Price(price=float(price), priceCurrency=currency)
            except:
                self.log("Error while converting str to int {}".format(traceback.format_exc()))

    @staticmethod
    def _parse_image_url(response):
        image_url = re.search('"image":\s"(.*?)",', response.body_as_unicode())
        return urlparse.urljoin(response.url, image_url.group(1)) if image_url else None

    @staticmethod
    def _parse_upc(response):
        upc = response.xpath("//div[@id='prod-product-code']/p/text()").extract()
        return upc[0] if upc else None

    def _parse_categories(self, response):
        try:
            data = re.search('jlData\s=\s(.*?);', response.body_as_unicode()).group(1)
            data = json.loads(data)
        except:
            self.log("Error while parsing JSON or Invalid JSON {}".format(traceback.format_exc()))
            data = None

        if data:
            category_list = []
            cats = data.get('page', {}).get('pageInfo', {}).get('breadCrumb')
            for cat in cats:
                category_list.append(cat.get('value'))

            return category_list

    @staticmethod
    def _parse_variants(response):
        product = response.meta['product']
        prod_url = product.get("url")
        canonical_url = prod_url.split("?")[0] if prod_url else None
        variants = []
        color_selectors = response.xpath('//ul[@class="swatch-list"]/li')
        sizes_selectors = response.xpath('.//*[@id="prod-product-size"]//li')
        if color_selectors and not sizes_selectors:
            sizes_selectors = ["placeholder_size"]
        for color in color_selectors:
            for size in sizes_selectors:
                variant = {}
                oos = None
                price = color.xpath("./@data-jl-price").extract()
                variant['price'] = float(price[0].replace("&pound;","")) if price else None
                selected = color.xpath("./a[contains(@class, 'current')]").extract()
                variant['selected'] = True if "selected" in ''.join(selected) else False
                props = {}
                col = color.xpath('./a/@title').extract()
                props['color'] = col[0] if col else None
                if not size == 'placeholder_size':
                    siz = size.xpath("./@data-jl-size").extract()
                    props['size'] = siz[0] if siz else None
                    url = "{}?selectedSize={}&colour={}&isClicked=true".format(canonical_url, props['size'],
                                                                               props['color'])
                else:
                    url = color.xpath("./a/@href").extract()
                    url = urlparse.urljoin(response.url, url[0]) if url else None
                variant['properties'] = props

                variant['url'] = url

                if not size == 'placeholder_size' and variant.get("selected"):
                    oos = size.xpath("./@class").extract()
                if size == 'placeholder_size' and variant.get("selected"):
                    oos = color.xpath("./@class").extract()
                in_stock = oos[0] if oos else None
                variant["in_stock"] = True if in_stock else False
                variants.append(variant)
        return variants

    def _scrape_total_matches(self, response):
        total = response.xpath(
            "//section[@class='search-results']/header/h1/span/text()").extract()
        if not total:
            total = response.xpath(
                ".//*[@id='result-count-header-label']/text()").re(r'.*\((\d+)\)')
        if not total:
            total = re.findall('"totalNumberOfResults":(\d+)}', response.body_as_unicode())
        try:
            total = int(total[0]) if total else 0
        except Exception as e:
            self.log("Exception converting total_matches to int: {}".format(e), DEBUG)
            total = 0
        finally:
            return total

    def _scrape_product_links(self, response):
        links = response.xpath('.//article/*[contains(@class, "product-link")]/@href').extract()

        if not links:
            links = response.xpath('//section[contains(@class, "product-list-item")]'
                                   '//a[contains(@class, "product-list-link--right")]/@href').extract()

        if not links:
            self.log("Found no product links.", DEBUG)

        for link in links:
            yield urlparse.urljoin(response.url, link), SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_link = response.xpath('//a[contains(@class, "pagination-next-link")]/@href').extract()
        if next_link:
            return urlparse.urljoin(response.url, next_link[0])
