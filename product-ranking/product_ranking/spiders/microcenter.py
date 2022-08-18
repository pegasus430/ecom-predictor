from __future__ import absolute_import, division, unicode_literals

import re
import urllib
import traceback
from urlparse import urljoin
from scrapy.log import INFO, ERROR, WARNING

from product_ranking.items import (BuyerReviews, SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from scrapy import Request

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi


class MicrocenterProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'microcenter_products'
    allowed_domains = ["microcenter.com"]

    BASE_URL = "http://www.microcenter.com"
    SEARCH_URL = "http://www.microcenter.com/search/search_results.aspx?Ntt={search_term}&myStore=false"
    NEXT_PAGE_URL = "http://www.microcenter.com/search/search_results.aspx?NTT={search_term}&page={page_number}&myStore=false"
    BUYER_REVIEWS_URL = 'http://microcenter.ugc.bazaarvoice.com/3520-en_us/{reseller_id}/reviews.djs?format=embeddedhtml'
    current_page = 1

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)

        super(MicrocenterProductsSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                ),
                dont_filter=True,
                meta={'search_term': st, 'remaining': self.quantity}
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse description
        description = self._parse_description(response)
        product['description'] = description

        # Parse reseller id
        reseller_id = self._parse_product_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        new_meta = {}
        new_meta['product'] = product

        if reseller_id:
            return Request(self.BUYER_REVIEWS_URL.format(reseller_id=reseller_id),
                           dont_filter=True,
                           callback=self.parse_buyer_reviews,
                           meta=new_meta)
        return product

    @staticmethod
    def _parse_product_id(response):
        product_id = response.xpath('//input[@name="productId"]/@value').extract()
        if product_id:
            product_id = product_id[0]
            if not product_id[0] == '0':
                product_id = '0' + product_id
            return product_id

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//title/text()').extract()
        if title:
            return title[0]

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//small[@itemprop="brand"]/a/text()').extract()
        if brand:
            return brand[0]

    def _parse_price(self, response):
        currency = "USD"
        price = response.xpath('//span[@itemprop="price"]/@content').extract()
        if not price:
            price = response.xpath('//span[@data-price]/@data-price').extract()
        if price and price[0].strip():
            try:
                price = float(price[0].replace(',', ''))
            except:
                self.log("Failed to parse price {}".format(traceback.format_exc()))
                return
            return Price(price=price, priceCurrency=currency)

    def _parse_image_url(self, response):
        image_url = response.xpath('//img[@class="productImageZoom"]/@src').extract()
        if not image_url:
            image_url = response.xpath('//img[@alt="Main Product Image"]/@src').extract()
        return image_url[0] if image_url else None

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//div[@id="product-details-control"]/h1/small/a/text()').extract()
        if categories:
            return categories[1:]

    def parse_buyer_reviews(self, response):
        buyer_reviews_per_page = self.br.parse_buyer_reviews_per_page(response)
        product = response.meta['product']
        product['buyer_reviews'] = BuyerReviews(**buyer_reviews_per_page)
        return product

    @staticmethod
    def _parse_description(response):
        description = response.xpath('//div[@itemprop="description"]/p/text()').extract()
        if description:
            return description[0]

    def _scrape_total_matches(self, response):
        totals = response.xpath('//div[@id="topPagination"]/p[@class="status"]/text()').extract()
        try:
            totals = re.findall(r'\d+', totals[0])[-1]
            return int(totals)
        except:
            self.log("Failed to patse total macthes count", WARNING)
            return

    def _scrape_product_links(self, response):
        items = response.xpath('//a[contains(@class, "ProductLink")]/@href').extract()

        if items:
            for item in items:
                item = urljoin(self.BASE_URL, item)
                res_item = SiteProductItem()
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        next_page_selector = response.xpath('//a[text()=">"]/@href')
        if next_page_selector:
            next_page = next_page_selector[0].extract()
            return next_page
