from __future__ import division, absolute_import, unicode_literals

import re
from urlparse import urljoin, urlparse

from scrapy import Field, Request
from scrapy.conf import settings

from product_ranking.spiders import BaseProductsSpider, cond_set_value, cond_replace_value
from product_ranking.items import SiteProductItem, scrapy_price_serializer, Price


class GooglePriceItem(SiteProductItem):
    shop_name = Field()
    shop_url = Field()
    tax = Field(serializer=scrapy_price_serializer)
    price_total = Field(serializer=scrapy_price_serializer)


class GooglePriceSpider(BaseProductsSpider):
    name = "google_price_products"
    allowed_domains = ["google.com"]

    SEARCH_URL = 'https://www.google.com/search?gl=us&hl=en&num=100&pws=0&filter=0&safe=images&tbm=shop&q={search_term}'

    MAX_RETRY_SEARCH = 5

    def __init__(self, upc=None, *args, **kwargs):
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

        if upc is not None:
            kwargs['searchterms_str'] = upc

        super(GooglePriceSpider, self).__init__(*args, **kwargs)

    def _scrape_total_matches(self, response):
        pass

    def _scrape_next_results_page_link(self, response):
        pass

    def parse(self, response):
        links = response.xpath(".//h3/a/@data-href|.//h3/a/@href")

        if links:
            for item in super(GooglePriceSpider, self).parse(response):
                yield item
        elif response.meta.get('retry_search', 0) < self.MAX_RETRY_SEARCH:
            self.log('Retry with other proxy')
            request = response.request.replace(dont_filter=True)
            request.meta['retry_search'] = request.meta.get('retry_search', 0) + 1

            yield request
        else:
            self.log('Product not found')

    def _scrape_product_links(self, response):
        links = response.xpath(".//h3/a/@data-href|.//h3/a/@href").extract()

        for link in links:
            if re.search(r'/shopping/product', link):
                price_page = re.sub(r'^([^?]*)', r'\1/online', link)
                price_page = urljoin(response.url, price_page)
                product = GooglePriceItem()

                yield Request(price_page,
                              callback=self.parse_product,
                              dont_filter=True,
                              meta={'product': product}), product
            elif re.search(r'/aclk', link):
                product_page = urljoin(response.url, re.sub(r'rct=j&?', '', link))
                product = GooglePriceItem()

                short_title = response.xpath(".//*[@href='{link}']/text()".format(link=link)).extract()
                if short_title:
                    cond_set_value(product, 'title', short_title[0])

                short_desc = response.xpath(".//*[@href='{link}']/following::*[1]".format(link=link))
                if short_desc:
                    cond_set_value(product, 'price', self._parse_short_price(short_desc))
                    cond_set_value(product, 'shop_name', self._parse_short_shop_name(short_desc))

                if not product.get('price'):
                    short_desc = response.xpath(".//*[@href='{link}']/preceding::*[@class='_OA'][1]".format(link=link))

                    if short_desc:
                        cond_set_value(product, 'price', self._parse_short_price(short_desc))
                        cond_set_value(product, 'shop_name', self._parse_short_shop_name(short_desc))

                cond_set_value(product, 'upc', self._parse_upc(response.meta))
                cond_set_value(product, 'price_total', product.get('price'))

                yield Request(product_page,
                              callback=self.parse_url,
                              dont_filter=True,
                              meta={'product': product}), product
            else:
                self.log('Unknown url format: {}'.format(link))

    def _parse_short_price(self, short_desc):
        price = short_desc.xpath(".//*[@class='price']/b/text()"
                                 "|.//b/text()").extract()

        if price:
            match = re.search(r'\$([\d.,]+)', price[0])

            if match:
                return Price('USD', match.group(1))

    def _parse_short_shop_name(self, short_desc):
        shop_name = short_desc.xpath(".//*[@class='price']/following-sibling::text()"
                                     "|.//b/following::*[1]/text()").extract()

        if shop_name:
            match = re.search(r'from\s+(.*)$', shop_name[0])

            if match:
                return match.group(1).strip()

            return shop_name[0]

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _parse_upc(self, product):
        return product.get('search_term')

    def _parse_shop_name(self, seller):
        shop_name = seller.xpath("*[@class='os-seller-name']//a/text()").extract()

        if shop_name:
            return shop_name[0].strip()

    def _parse_price(self, seller):
        price = seller.xpath("*[@class='os-price-col']/*[@class='os-base_price']/text()").extract()

        if price:
            match = re.search(r'\$([\d.,]+)', price[0])

            if match:
                return Price('USD', match.group(1))

    def _parse_tax(self, seller):
        price_description = seller.xpath("*[@class='os-price-col']"
                                         "/*[@class='os-total-description']/text()").extract()

        if price_description:
            match = re.search(r'\$([\d.,]+)\s+tax', price_description[0], re.I)

            if match:
                return Price('USD', match.group(1))

    def _parse_shipping_cost(self, seller):
        price_description = seller.xpath("*[@class='os-price-col']"
                                         "/*[@class='os-total-description']/text()").extract()

        if price_description:
            match = re.search(r'\$([\d.,]+)\s+shipping', price_description[0], re.I)

            if match:
                return Price('USD', match.group(1))

    def _parse_price_total(self, seller):
        price_total = seller.xpath("*[@class='os-total-col']/text()").extract()

        if price_total:
            match = re.search(r'\$([\d.,]+)', price_total[0])

            if match:
                return Price('USD', match.group(1))

    def _calculate_price_total(self, product):
        price_total = product.get('price').price if product.get('price') else 0

        if product.get('tax'):
            price_total += product.get('tax').price

        if product.get('shipping_cost'):
            price_total += product.get('shipping_cost').price

        return Price('USD', price_total)

    def _parse_title(self, response):
        title = response.xpath(".//*[@id='product-name']/text()").extract()

        if title:
            return title[0]

    def parse_product(self, response):
        title = self._parse_title(response)
        sellers = response.xpath(".//*[@class='os-row']")

        if sellers:
            for seller in sellers:
                product = GooglePriceItem(response.meta['product'])

                cond_set_value(product, 'title', title)
                cond_set_value(product, 'shop_name', self._parse_shop_name(seller))
                cond_set_value(product, 'price', self._parse_price(seller))
                cond_set_value(product, 'tax', self._parse_tax(seller))
                cond_set_value(product, 'shipping_cost', self._parse_shipping_cost(seller))
                cond_set_value(product, 'price_total', self._parse_price_total(seller))

                cond_set_value(product, 'upc', self._parse_upc(product))
                cond_set_value(product, 'price_total', self._calculate_price_total(product))

                product_url = seller.xpath("*[@class='os-seller-name']//a/@href").extract()
                if product_url:
                    product_url = re.sub(r'rct=j&?', '', product_url[0])  # disable JS redirect

                    meta = dict(response.meta)
                    meta['product'] = product

                    yield Request(urljoin(response.url, product_url),
                                  callback=self.parse_url,
                                  dont_filter=True,
                                  meta=meta)
        elif response.meta.get('retry_search_price', 0) < self.MAX_RETRY_SEARCH:
            self.log('Retry with other proxy')
            request = response.request.replace(dont_filter=True)
            request.meta['retry_search_price'] = request.meta.get('retry_search_price', 0) + 1

            yield request
        else:
            self.log('Price not found')

    def parse_url(self, response):
        product = response.meta['product']

        cond_replace_value(product, 'url', response.url)
        cond_set_value(product, 'shop_url', '://'.join(urlparse(response.url)[:2]))

        yield product
