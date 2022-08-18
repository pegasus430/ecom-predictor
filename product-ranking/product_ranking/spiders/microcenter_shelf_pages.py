from __future__ import absolute_import, division, unicode_literals
import re
from scrapy.http import Request
from scrapy.log import INFO
from urlparse import urljoin
from product_ranking.items import SiteProductItem
from product_ranking.spiders.microcenter import MicrocenterProductsSpider


class MicrocenterShelfPagesSpider(MicrocenterProductsSpider):
    name = 'microcenter_shelf_urls_products'
    allowed_domains = ["microcenter.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(MicrocenterShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        if self.product_url:
            yield Request(self.product_url,
                          meta={'search_term': '', 'remaining': self.quantity},
                          )

    def _scrape_product_links(self, response):
        product_links = response.xpath(
            '//article[@id="productGrid"]//a[contains(@class, "ProductLink")]/@href').extract()
        product_links = [urljoin(self.BASE_URL, link) for link in product_links]
        shelf_categories = [category for category in
                            response.xpath('//div[@class="searchcorrections"]//span/text()').extract() if
                            not ('Selected' in category or 'Remove' in category)]
        shelf_category = shelf_categories[-1] if shelf_categories else None
        if product_links:
            for product in product_links:
                item = SiteProductItem()
                if shelf_category:
                    item['shelf_name'] = shelf_category
                if shelf_categories:
                    item['shelf_path'] = shelf_categories
                yield product, item
        else:
            self.log("No product links found in {url}".format(url=response.url), INFO)

    def _scrape_total_matches(self, response):
        totals = response.xpath('//div[@id="topPagination"]/p[@class="status"]/text()').extract()
        if totals:
            totals = totals[0]
            totals = re.findall(r'\d+', totals)[-1]
            totals = int(totals)
        return totals

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        next_page_selector = response.xpath('//a[text()=">"]/@href')
        if next_page_selector:
            next_page = next_page_selector[0].extract()
            return next_page
