from __future__ import division, absolute_import, unicode_literals

from .groupon import GrouponProductsSpider
from scrapy.http import Request
from product_ranking.utils import is_empty


class GrouponShelfPagesSpider(GrouponProductsSpider):
    name = 'groupon_shelf_urls_products'
    allowed_domains = ["groupon.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(GrouponShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility())

    def _scrape_total_matches(self, response):
        """
        Scraping number of resulted product links
        """
        total_matches = is_empty(
            response.xpath('//p[contains(@class, "results")]//span/text()').re(r'\d+'), 0
        )

        if total_matches:
            return int(total_matches)
        else:
            return 0

    def _scrape_next_results_page_link(self, response):
        if self.current_page > self.num_pages:
            return

        self.current_page += 1

        links = response.xpath(
            "//ul[contains(@class, 'pagination_links')]"
            "//li[contains(@class, 'box')]"
            "//following-sibling::li[1]"
            "//a/@href"
        ).extract()

        if links:
            link = links[0]
        else:
            link = None

        return link
