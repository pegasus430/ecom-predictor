# -*- coding: utf-8 -*-

from product_ranking.spiders.costcobusinessdelivery import CostCoBusinessDeliveryProductsSpider


class CostCoBusinessDeliveryShelfPagesSpider(CostCoBusinessDeliveryProductsSpider):
    name = 'costcobusinessdelivery_shelf_urls_products'
    allowed_domains = ["www.costcobusinessdelivery.com"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(CostCoBusinessDeliveryShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        for req in super(CostCoBusinessDeliveryShelfPagesSpider, self).start_requests():
            req = req.replace(meta={'search_term': "", 'remaining': self.quantity},
                              callback=self.parse)
            yield req

    def _scrape_total_matches(self, response):
        totals = response.xpath('//span[contains(text(), "Showing ")]/text()').re('of (\d+)')
        return int(totals[0]) if totals else None

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        return super(CostCoBusinessDeliveryShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)
