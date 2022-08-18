from __future__ import division, absolute_import, unicode_literals

from .amazonfresh_shelf_pages import AmazonFreshShelfPagesSpider

class AmazonFreshCoUkShelfPagesSpider(AmazonFreshShelfPagesSpider):
    name = 'amazonfreshcouk_shelf_urls_products'
    allowed_domains = ["www.amazon.co.uk"]

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(AmazonFreshShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

        self.detect_shelf_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_shelf_ads = True

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def _scrape_total_matches(self, response):
        total_matches = response.xpath('//*[@id="s-result-count"]/text()').re('(\d+) results')

        if total_matches:
            return int(total_matches[0])

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            self.current_page += 1

            return super(AmazonFreshCoUkShelfPagesSpider, self)._scrape_next_results_page_link(response)
