# -*- coding: utf-8 -*-

from .newegg import NeweggProductSpider
from scrapy.http import Request


class NeweggShelfPagesSpider(NeweggProductSpider):
    name = 'newegg_shelf_urls_products'
    allowed_domains = ["www.newegg.com"]

    USER_AGENT = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(NeweggShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      headers={'User-Agent': self.USER_AGENT}
                      )

    def _get_products(self, response):
        for request in super(NeweggShelfPagesSpider, self)._get_products(response):
            request = request.replace(headers={'User-Agent': self.USER_AGENT}, dont_filter=True)
            yield request

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page')
        if not current_page:
            current_page = 1
        if current_page >= self.num_pages:
            return
        request = super(NeweggShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)
        request = request.replace(headers={'User-Agent': self.USER_AGENT})
        return request
