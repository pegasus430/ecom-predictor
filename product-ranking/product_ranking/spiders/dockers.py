from __future__ import division, absolute_import, unicode_literals

import json
import re
import urlparse
from scrapy.conf import settings as crawler_settings

from scrapy import Request
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from scrapy.conf import settings
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.settings import ZERO_REVIEWS_VALUE


class DockersProductsSpider(BaseProductsSpider):
    name = 'dockers_products'
    allowed_domains = ["dockers.com", "www.dockers.com"]

    SEARCH_URL = "https://www.dockers.com/US/en_US/search/{search_term}"

    VARIANTS_DATA_URL = "https://www.dockers.com/US/en_US/p/{product_id}/data"

    REVIEWS_URL = "https://api.bazaarvoice.com/data/batch.json?"\
                  "passkey=casXO49OnnLONGhfxN6TSfvEmsGWbyrfjtFtLGZWnBUeE"\
                  "&apiversion=5.5"\
                  "&displaycode=18029-en_us"\
                  "&resource.q0=products"\
                  "&filter.q0=id%3Aeq%3A{product_id}"\
                  "&stats.q0=reviews"\
                  "&filteredstats.q0=reviews"\
                  "&filter_reviews.q0=contentlocale%3Aeq%3Aen*%2Cen_US"\
                  "&filter_reviewcomments.q0=contentlocale%3Aeq%3Aen*%2Cen_US"\
                  "&resource.q1=reviews"

    RETRY_HTTP_CODES = settings.get('RETRY_HTTP_CODES')
    if 404 in RETRY_HTTP_CODES:
        RETRY_HTTP_CODES.remove(404)
    handle_httpstatus_list = [404]

    def __init__(self, *args, **kwargs):
        super(DockersProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

        self.ignore_color_variants = kwargs.get('ignore_color_variants', True)
        if self.ignore_color_variants in ('0', False, 'false', 'False'):
            self.ignore_color_variants = False
        else:
            self.ignore_color_variants = True
        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) ' \
                          'Chrome/57.0.2987.133 Safari/537.36 (Content Analytics)'

        self.br = BuyerReviewsBazaarApi(called_class=self)

        retry_codes = crawler_settings.get('RETRY_HTTP_CODES', [])
        retry_codes = [c for c in retry_codes if c not in self.handle_httpstatus_list]
        crawler_settings.overrides['RETRY_HTTP_CODES'] = retry_codes

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta.get('product', SiteProductItem())
        product.update({"locale": 'en-US'})
        if response.status == 404 or "this product is no longer available" in response.body_as_unicode() or \
                "www.dockers.com/US/en_US/error" in response.url:
            product.update({"not_found": True})
            product.update({"no_longer_available": True})
            return product
        else:
            product.update({"no_longer_available": False})

        product_json = self._get_product_json(response)

        # brand
        cond_set_value(product, 'brand', 'Dockers')

        # title
        cond_set_value(product, 'title', self._parse_title(response))

        # product_id, reseller_id
        product_id = self._parse_product_id(product['url'], product_json)
        cond_set_value(product, 'reseller_id', product_id)
        cond_set_value(product, 'sku', product_id)

        # department, departments
        departments = self._parse_departments(response)
        if departments:
            cond_set_value(product, 'categories', departments)
            cond_set_value(product, 'department', departments[-1])

        # price
        price_amount = self._parse_price_amount(product_json)
        price_currency = self._parse_price_currency(product_json)
        cond_set_value(product, 'price', Price(price=price_amount, priceCurrency=price_currency))

        # image_url
        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        is_out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        variants_color_data = self._parse_variant_colors(product_json, price_amount)
        if variants_color_data:
            return Request(
                url=self.VARIANTS_DATA_URL.format(product_id=product_id),
                meta={'product': product,
                      'variants_color_data': variants_color_data
                     },
                callback=self._parse_variants
            )

        return product

    @staticmethod
    def _get_product_json(response):
        """ Get product json
        :param response (HtmlResponse): general url response
        :return (dict) product json data
        """
        raw_data = re.search(
            r'LSCO.dtos = (.*?)LSCO',
            response.body,
            re.DOTALL
        )
        if raw_data:
            product_json = json.loads(raw_data.group(1))
            return product_json

    @staticmethod
    def _parse_variant_colors(product_json, price_amount):
        return [{
            'colorName': x.get('colorName'),
            'sku': x.get('code'),
            'url': x.get('url'),
            'active': x.get('active'),
            "price": price_amount
        } for x in product_json.get('swatches', [])]

    def _parse_variants(self, response):
        """Get product variants (full data)
        :param response (HtmlResponse): general url response
        :return (product): product `variants`
        """
        meta = response.meta.copy()
        product = response.meta.get('product')
        size_data = json.loads(response.body_as_unicode())
        variants_color_data = meta.get('variants_color_data')
        variant_data = None
        variants = meta.get('variants', [])
        for i, x in enumerate(variants_color_data):
            if x['sku'] == size_data.get('code'):
                variant_data = variants_color_data.pop(i)
        if variant_data:
            for data in size_data.get('variantOptions', []):
                variants.append({
                    'in_stock': bool(data.get('stock', {}).get('stockLevel')),
                    'colorid': variant_data.get('sku'),
                    'sku': variant_data.get('sku'),
                    'price': variant_data.get('price'),
                    'properties': {
                        'color': variant_data.get('colorName'),
                        'size': data.get('displaySizeDescription')
                    },
                    'selected': variant_data.get('active'),
                    'url': urlparse.urljoin(response.url, '/US/en_US' + variant_data.get('url'))
                })
            product['variants'] = variants
            if variants_color_data and not self.ignore_color_variants:
                return Request(
                    url=self.VARIANTS_DATA_URL.format(product_id=variants_color_data[0]['sku']),
                    meta={
                        'variants_color_data': variants_color_data,
                        'variants': variants,
                        'product': product
                    },
                    callback=self._parse_variants
                )
            else:
                product_id = product.get('reseller_id')
                if product_id:
                    return Request(
                        url=self.REVIEWS_URL.format(product_id=product_id),
                        callback=self._parse_buyer_reviews,
                        dont_filter=True,
                        meta={
                            'product': product
                        }
                    )
                else:
                    product["buyer_reviews"] = ZERO_REVIEWS_VALUE

        return product

    @staticmethod
    def _parse_is_out_of_stock(response):
        return bool(response.xpath(
            '//button[contains(@class, "outOfStock")]'
        ))

    @staticmethod
    def _parse_product_id(product_url, product_json):
        """ Get product_id
        :param product_url (str): product url
        :param product_json (dict): product json from method `_get_product_json`
        :return (str) product `product_id`
        """
        product_id = re.search(r'/p/(.+)[/&$]?', product_url)
        return product_id.group(1) if product_id else product_json.get('code')

    @staticmethod
    def _parse_departments(response):
        """ Get departments
        :param response (HtmlResponse): general url response
        :return (list) product `departments`
        """
        departments = response.xpath(
            '//ol[@class="breadcrumb"]//li/a/text()'
        ).extract()
        return departments if departments else None

    @staticmethod
    def _parse_title(response):
        title = response.xpath(
            '//div[contains(@class, "-title")]/*[@itemprop="name"]/text()').extract()
        return title[0] if title else ""

    @staticmethod
    def _parse_price_amount(product_json):
        """ Get price amount
        :param price (str): price from method `_parse_price`
        :return (float) product `price amount`
        """
        price_amount = product_json.get('product', {}).get('price', {}).get('softPrice')
        if not price_amount:
            price_amount = product_json.get('product', {}).get('price', {}).get('hardPrice')
        if not price_amount:
            price_amount = product_json.get('product', {}).get('price', {}).get('regularPrice')
        return float(price_amount) if price_amount else None

    @staticmethod
    def _parse_price_currency(product_json):
        """ Get price currency
        :param product_json (dict): product json from method `_get_product_json`
        :return (str) product `price currency`
        """
        return product_json.get('product', {}).get('price', {}).get('currencyIso')

    @staticmethod
    def _parse_image(response):
        image = response.xpath("//picture[@class='product-image-first']/img/@data-src").extract()
        return image[0] if image else None

    def _parse_buyer_reviews(self, response):
        product = response.meta.get('product')

        try:
            raw_json = json.loads(response.body_as_unicode())
        except Exception as e:
            self.log('Invalid reviews: {}'.format(str(e)))
            return product

        buyer_reviews_data = raw_json.get('BatchedResults', {}).get('q0', {})
        response = response.replace(body=json.dumps(buyer_reviews_data))
        buyer_reviews = BuyerReviews(
            **self.br.parse_buyer_reviews_products_json(response))
        product['buyer_reviews'] = buyer_reviews

        return product

    def _scrape_total_matches(self, response):
        total_matches = response.xpath(
            '//div[@class="pagination-bar-results"]/text()'
        ).re(r'\d+')
        return int(total_matches[0]) if total_matches else None

    def _scrape_product_links(self, response):
        links = response.xpath('//a[@class="name"]/@href').extract()
        for link in [urlparse.urljoin(response.url, link) for link in links]:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath(
            '//a[@class="prevNextLabel"]/@href'
        ).extract()

        if next_page:
            return next_page[0]
