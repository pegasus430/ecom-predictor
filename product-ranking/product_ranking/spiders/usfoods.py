# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urlparse
import urllib
import traceback

from scrapy.conf import settings
from scrapy.http import Request
from lxml import html

from product_ranking.items import (SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults
from product_ranking.validation import BaseValidator
from product_ranking.utils import is_empty


class UsfoodsProductsSpider(BaseValidator, BaseProductsSpider):

    name = 'usfoods_products'
    allowed_domains = ["www3.usfoods.com"]

    SEARCH_URL = "https://www3.usfoods.com/order/faces/oracle/webcenter/portalapp/pages/shop/products.jspx"

    HOME_URL = 'https://www3.usfoods.com'

    user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                 "Chrome/55.0.2987.98 Safari/537.36"

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'User-agent': user_agent,
        'Accept-Language': 'en-US, en;q=0.8',
        'Adf-Rich-Message': 'true',
        'Connection': 'keep-alive',
        'Host': 'www3.usfoods.com',
        'Origin': 'https://www3.usfoods.com',
    }

    REDIRECT_PRODUCT_URL = 'https://www3.usfoods.com/order/faces/oracle/webcenter/portalapp/pages/productdetail/productDetail.jspx' \
                  '?productNumber={productNumber}' \
                  '&_afrLoop={afrLoop}' \
                  '&_afrWindowMode=0' \
                  '&_afrWindowId=twc3g78fs_231'

    PRODUCT_URL = 'https://www3.usfoods.com/order/faces/oracle/webcenter/portalapp/pages/productdetail/productDetail.jspx' \
                  '?productNumber={productNumber}'

    results_per_page = 50

    def __init__(self, *args, **kwargs):
        self.product_number = None
        self.refer_url = None
        super(UsfoodsProductsSpider, self).__init__(*args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        yield Request(
            self.HOME_URL,
            callback=self._start_requests
        )

    def _start_requests(self, response):
        a_redirect = re.search('"_afrLoop", (.*?);', response.body)

        if a_redirect:
            a_redirect = a_redirect.group(1).replace('"', '').replace(')', '')
            yield Request(
                'https://www3.usfoods.com/order/faces/oracle/webcenter/portalapp/pages/login.jspx?' + '_afrLoop={}'.format(a_redirect),
                callback=self.login_handler,
            )

    def login_handler(self, response):
        view_state = response.xpath("//input[@name='javax.faces.ViewState']/@value").extract()
        if view_state:
            data = {
                "it9": "CONTENTANALYTICS",
                "it1": "Victory16",
                "it2": "1440x900",
                "it3": "Netscape",
                "it4": "5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.98"
                       " Safari/537.36",
                "it5": "true", "it6": "Linux x86_64",
                "org.apache.myfaces.trinidad.faces.FORM": "f1",
                "javax.faces.ViewState": view_state[0],
                "event": "cb1",
                "event.cb1": "<m xmlns='http://oracle.com/richClient/comm'><k v='type'><s>action</s></k></m>"
            }

            log_in = response.xpath("//form[@id='f1']/@action")[0].extract()

            yield Request(
                urlparse.urljoin(response.url, log_in),
                method='POST',
                body=urllib.urlencode(data),
                callback=self.after_login,
                headers=self.headers,
                meta={"view_state": view_state}
            )

    def after_login(self, response):
        for request in super(UsfoodsProductsSpider, self).start_requests():
            if not self.product_url:
                redirect_link = response.xpath('//redirect/text()').extract()
                if redirect_link:
                    url = urlparse.urljoin(response.url, redirect_link[0])
                    yield request.replace(url=url, callback=self._parse_search)
            else:
                product_number = re.search(r'productNumber=(\d+)(?:$|&)', self.product_url, re.DOTALL)
                if product_number:
                    url = self.PRODUCT_URL.format(productNumber=product_number.group(1))
                    yield request.replace(url=url)
                else:
                    self.log('Not Product Url')

    def _parse_search(self, response):
        meta = response.meta.copy()
        st = response.meta['search_term']

        view_state = response.xpath("//input[@name='javax.faces.ViewState']/@value").extract()
        search_post = response.xpath("//form[@id='f1']/@action").extract()
        if view_state and search_post:
            payload = {
                'dgfSPT:pt_s36:pt_it4': st,
                'org.apache.myfaces.trinidad.faces.FORM': 'f1',
                'javax.faces.ViewState': view_state[0],
                'event': 'dgfSPT:pt_s36:pt_cil2',
                'event.dgfSPT:pt_s36:pt_cil2': '<m xmlns="http://oracle.com/richClient/comm">'
                                               '<k v="type"><s>action</s></k></m>',
                'oracle.adf.view.rich.PPR_FORCED': 'true'
            }

            return Request(
                urlparse.urljoin(response.url, search_post[0]),
                method='POST',
                body=urllib.urlencode(payload),
                callback=self._parse_redirect,
                headers=self.headers,
                meta=meta,
            )

    def _parse_redirect(self, response):
        meta = response.meta.copy()
        products_url = response.xpath("//redirect/text()").extract()
        if products_url:
            return Request(
                urlparse.urljoin(response.url, products_url[0]),
                headers=self.headers,
                meta=meta,
            )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        meta = response.meta.copy()

        product = meta['product']

        if '_afrLoop' not in response.url:
            afr_loop = re.search(r'"_afrLoop", "(\d+)"', response.body, re.DOTALL)
            product_number = re.search(r'productNumber=(\d+)(?:$|&)', response.url, re.DOTALL)
            if afr_loop and product_number:
                url = self.REDIRECT_PRODUCT_URL.format(afrLoop=afr_loop.group(1), productNumber=product_number.group(1))
                return Request(
                    url=url,
                    headers=self.headers,
                    meta=meta,
                    callback=self.parse_product
                )
            else:
                return product

        # Set locale
        product['locale'] = 'en_US'

        # Set url
        product['url'] = response.url

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        return product

    @staticmethod
    def _parse_title(response):
        selector = html.fromstring(response.body)
        title = is_empty(selector.xpath("//span[@class='x2cg']/text()"))
        return str(title) if title else None

    def _parse_price(self, response):
        currency = "USD"
        selector = html.fromstring(response.body)
        price_data = selector.xpath("//div[@class='x1a']//span[@class='x246']/text()")
        try:
            price = re.search('(.*?) ', str(price_data[-1]))
            return Price(price=float(price.group(1).replace('$', '')), priceCurrency=currency)
        except Exception as e:
            self.log('Price error {}'.format(traceback.format_exc(e)))

    @staticmethod
    def _parse_image_url(response):
        selector = html.fromstring(response.body)
        image_urls = selector.xpath('//div[@class="x2cv x1a"]//img[@class="xjd"]/@src')

        if image_urls and 'no_image_productDetail' not in image_urls[0]:
            return urlparse.urljoin(response.url, image_urls[0])

    @staticmethod
    def _parse_description(response):
        selector = html.fromstring(response.body)
        desc_array = selector.xpath('//div[@id="pt1:r1:0:r1:0:pt1:pgl88"]//span[@class="x242"]/text()')
        description = ''.join(desc_array)
        return description if description else None

    @staticmethod
    def _parse_sku(response):
        selector = html.fromstring(response.body)
        sku = is_empty(selector.xpath('//table[@class="x1a"]//span[@class="x242"]/text()'))
        sku = re.search('(\d+)', sku)
        if sku:
            return sku.group(1)

    def _parse_product_info(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        products_html = html.fromstring(response.body)

        totals = products_html.xpath("//table[@id='r1:0:pt1:r1:0:pt1:pgl12']//span[@class='x273']/text()")

        if totals:
            totals = re.search('(\d+)', totals[0])

            return int(totals.group(1)) if totals else 0

    def _scrape_product_links(self, response):
        products_html = html.fromstring(response.body)
        links = products_html.xpath('//div[@class="x1a"]//span[@class="x2fc"]/text()')
        if not links:
            self.log('No Product links')
        for link in links:
            product_number = re.search(r'# (\d+)$', link, re.DOTALL)
            if product_number:
                url = self.PRODUCT_URL.format(productNumber=product_number.group(1))
                yield url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        current_page = meta.get('current_page', 1)
        total_matches = meta.get('total_matches', 0)
        if self.results_per_page * current_page >= total_matches:
            return

        products_html = html.fromstring(response.body)

        next_page_post = re.sub(r'&_afrLoop=\d+', '', response.url)
        view_state = products_html.xpath("//input[@name='javax.faces.ViewState']/@value")
        if view_state:
            event = 'r1:0:pt1:r1:0:pt1:i5:{}:cl8'.format(current_page)

            current_page += 1
            meta['current_page'] = current_page
            payload = {
                'r1:0:pt1:pt_s36:pt_it4': 'Search Catalog',
                'r1:0:pt1:r1:0:pt1:s36:it1': 'Search Within',
                'r1:0:pt1:r1:0:pt1:cc_soc1:soc2': 0,
                'org.apache.myfaces.trinidad.faces.FORM': 'f1',
                'javax.faces.ViewState': view_state[0],
                'event': event,
                'event.{}'.format(event): '<m xmlns="http://oracle.com/richClient/comm">'
                                          '<k v="type"><s>action</s></k></m>',
                'oracle.adf.view.rich.PROCESS': 'r1:0:pt1:r1'
            }

            next_page_req = Request(
                next_page_post,
                method='POST',
                body=urllib.urlencode(payload),
                headers=self.headers,
                meta=meta,
            )

            return next_page_req
