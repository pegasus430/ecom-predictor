# -*- coding: utf-8 -*-#
import re
import json
import urllib
import urlparse
import traceback

from scrapy import Request
from scrapy.log import ERROR
from scrapy.conf import settings

from product_ranking.utils import urlEncodeNonAscii
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, \
    FormatterWithDefaults


class ShopColesProductsSpider(BaseProductsSpider):
    name = 'shop_coles_products'
    allowed_domains = ["shop.coles.com.au"]

    SEARCH_URL = 'https://shop.coles.com.au/online/COLRSSearchDisplay?' \
        'storeId=20601&searchTerm={search_term}&beginIndex={begin_index}' \
        '&showResultsPage=true'

    BASE_PRODUCT_URL = 'https://shop.coles.com.au/a/a-national/product/'

    PRODUCT_INFO_URL = 'https://shop.coles.com.au/search/resources/' \
                       'store/20601/productview/bySeoUrlKeyword/{}'

    def __init__(self, *args, **kwargs):
        super(ShopColesProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(begin_index=0),
            site_name=self.allowed_domains[0],
            *args, **kwargs)

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _parse_single_product(self, response):
        product_name = re.search('/product/(.*)', response.url, re.DOTALL)
        if not product_name:
            product = response.meta['product']
            product['not_found'] = True
            return product
        product_name = urllib.quote_plus(product_name.group(1))
        return Request(self.PRODUCT_INFO_URL.format(product_name),
                       meta=response.meta, callback=self.parse_product)

    def parse_product(self, response):
        product = response.meta['product']

        # Set locale
        product['locale'] = 'en_US'

        try:
            product_info = json.loads(response.body)
            data = product_info['catalogEntryView'][0]
        except:
            self.log('cannot find json data: {}'.format(traceback.format_exc()), ERROR)
            product['not_found'] = True
            return product

        # Parse title
        title = data.get('n')
        cond_set_value(product, 'title', title)

        # Parse brand
        brand = data.get('m')
        cond_set_value(product, 'brand', brand)

        # Parse categories
        categories = data.get('a', {}).get('P8')
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse price
        price = data.get('p1', {}).get('o')
        if price:
            is_out_of_stock = False
            cond_set_value(product, 'price', Price(price=price, priceCurrency='AUD'))
        else:
            is_out_of_stock = True

        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse special pricing
        is_special = data.get('p1', {}).get('l4')
        cond_set_value(product, 'special_pricing', bool(is_special))

        # Parse image url
        image_url = data.get('fi')
        if image_url:
            image_url = urlparse.urljoin(response.url, image_url)
            cond_set_value(product, 'image_url', image_url)

        # Parse sku
        sku = data.get('p')
        cond_set_value(product, 'sku', sku)

        reseller_id = data.get('p')
        cond_set_value(product, "reseller_id", reseller_id)

        return product

    def _scrape_results_per_page(self, response):
        page_size = re.search('"pageSize":(\d+)', response.body)
        return int(page_size.group(1)) if page_size else 0

    def _scrape_total_matches(self, response):
        totals = re.search('"totalCount":(\d+)', response.body)
        return int(totals.group(1)) if totals else 0

    def _scrape_product_links(self, response):
        items = re.search(r'"products":(\[.*\])\n', response.body)
        if not items:
            return
        try:
            items = json.loads(items.group(1))
        except:
            self.log('Invalid json {}'.format(traceback.format_exc()))
            return

        for item in items:
            item_link = item.get('s')
            if item_link and isinstance(item_link, basestring):
                item_link = urllib.quote_plus(urlEncodeNonAscii(item_link.encode('utf-8')))
                link = self.PRODUCT_INFO_URL.format(item_link)
                res_item = SiteProductItem()
                res_item['url'] = self.BASE_PRODUCT_URL + item_link
                yield link, res_item

    def _scrape_next_results_page_link(self, response):
        current_page = re.search('"currentPage":(\d+)', response.body)
        current_page = int(current_page.group(1)) if current_page else 0
        totals = self._scrape_total_matches(response)
        page_size = self._scrape_results_per_page(response)
        try:
            max_page = round(float(totals) / page_size)
        except ZeroDivisionError:
            max_page = None

        if not current_page or not max_page or current_page >= max_page:
            return None

        search_term = response.meta.get('search_term')
        return self.url_formatter.format(self.SEARCH_URL,
                                         search_term=search_term, begin_index=current_page * page_size)
