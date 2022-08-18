# -*- coding: utf-8 -*-

from .barnesandnoble import BarnesandnobleProductsSpider
from scrapy.http import Request
import re
from product_ranking.items import SiteProductItem
import traceback
import urlparse


class BarnesandnobleShelfPagesSpider(BarnesandnobleProductsSpider):
    name = 'barnesandnoble_shelf_urls_products'
    allowed_domains = ["www.barnesandnoble.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(BarnesandnobleShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      )

    def _scrape_total_matches(self, response):
        totals = re.search('"productCount":(\d+),', response.body)

        if totals:
            totals = int(totals.group(1))
        else:
            totals = 0

        return totals

    def _scrape_product_links(self, response):
        product_links = response.xpath('//div[contains(@class, "product-shelf-title")]'
                                       '/a/@href').extract()
        if product_links:
            for link in product_links:
                link = urlparse.urljoin(response.url, link)
                yield link, SiteProductItem()
        else:
            self.log("Found no product links {}".format(traceback.format_exc()))

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        current_page += 1
        response.meta['current_page'] = current_page
        next_url = super(BarnesandnobleShelfPagesSpider, self)._scrape_next_results_page_link(response)
        if next_url:
            return Request(
                next_url,
                meta=response.meta
            )
