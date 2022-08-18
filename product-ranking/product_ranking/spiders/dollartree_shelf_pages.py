# -*- coding: utf-8 -*-

from product_ranking.spiders.dollartree import DollartreeProductsSpider
from scrapy.http import Request
from product_ranking.items import SiteProductItem
import traceback
import re


class DollartreeShelfPagesSpider(DollartreeProductsSpider):
    name = 'dollartree_shelf_urls_products'
    allowed_domains = ["www.dollartree.com"]

    COOKIE = {'_br_uid_2': 'uid%3D4502590902255%3Av%3D11.8%3Ats%3D1501877588545%3Ahc%3D33;'}

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(DollartreeShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(url=self.product_url,
                      meta={'search_term': "", 'remaining': self.quantity},
                      cookies=self.COOKIE
                      )

    def _scrape_total_matches(self, response):
        total = re.search('numFound":(.*?),', response.body, re.DOTALL)
        try:
            total_matches = int(total.group(1).strip())
            return total_matches
        except:
            self.log('Found no products: {}'.format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        links = response.xpath('//div[@class="docCollectionContainer"]//div/div/a/@href').extract()
        for link in links:
            item = SiteProductItem()
            yield link, item

    def _scrape_next_results_page_link(self, response):
        try:
            total_matches = response.meta.get('total_matches')
            next_page = response.xpath('//a[@id="nextPageLink"]/@href').extract()[0]
            next_page_num = re.findall(r'(?<=pageIndex=)\d+', next_page)
            next_page_num = int(next_page_num[0])
            if next_page_num < total_matches:
                return next_page
        except:
            self.log("Failed to get next products page: {}".format(traceback.format_exc()))