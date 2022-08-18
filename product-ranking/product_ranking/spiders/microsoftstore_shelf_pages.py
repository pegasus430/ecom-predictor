# -*- coding: utf-8 -*-#

import urlparse
from scrapy.http import Request
from scrapy.log import INFO

from product_ranking.items import SiteProductItem

from product_ranking.spiders.microsoftstore import MicrosoftStoreProductSpider

is_empty = lambda x, y=None: x[0] if x else y


class MicrosoftStoreShelfPagesSpider(MicrosoftStoreProductSpider):

    name = 'microsoftstore_shelf_urls_products'

    PAGINATE_URL = 'https://www.microsoftstore.com/store/msusa/en_US/filterSearch/' \
                   'categoryID.{category_id}/startIndex.{start_index}/size.{size}/sort.ranking%' \
                   '20ascending?keywords=*%3A*&Env=BASE&callingPage=categoryProductListPage'


    def __init__(self, *args, **kwargs):
        super(MicrosoftStoreShelfPagesSpider, self).__init__(*args, **kwargs)
        self.current_page = 1
        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1  # See https://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=3313#c0

    def start_requests(self):
        if self.product_url:
            yield Request(self.product_url,
                meta={'search_term': '', 'remaining': self.quantity},
            )

    def _scrape_results_per_page(self, response):
        per_page = is_empty(response.xpath(
            './/*[@class="fromTo"]/text()').re(r'-(\d+)'))
        per_page = int(per_page) if per_page else None
        if not per_page:
            links = response.xpath(
                './/a[contains(@class, "product") and contains(@href, "/pdp/")]/@href'
            ).extract()

            per_page = len(links)
        return per_page

    def _scrape_product_links(self, response):
        shelf_categories = response.meta.get('shelf_categories')
        """
        Scraping product links from search page
        """
        links = response.xpath(
            './/a[contains(@class, "product")]/@href'
        ).extract()
        if links:
            if not shelf_categories:
                shelf_categories = self._get_shelf_path(response)
            shelf_category = shelf_categories[-1] if shelf_categories else None
            for link in links:
                # sometimes there is link to category instead of a product like here:
                # https://www.microsoftstore.com/store/msusa/en_US/cat/Microsoft-Lumia/categoryID.66852000?icid=en_US_Homepage_whatsnew_5_TEST_EDU_160525
                if '/pdp/' not in link:
                    self.log("Found shelf link instead of product link {url}".format(url=link), INFO)
                else:
                    item = SiteProductItem()
                    if shelf_category:
                        item['shelf_name'] = shelf_category
                    if shelf_categories:
                        item['shelf_path'] = shelf_categories
                    yield urlparse.urljoin(response.url, link), item

        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _get_shelf_path(self, response):
        shelf_categories = response.xpath('.//*[@class="breadcrumbs breadcrumbs-padded"]//text()').extract()
        shelf_categories = [c.strip() for c in shelf_categories if len(c.strip()) > 1]
        if shelf_categories:
            return shelf_categories

    def _scrape_next_results_page_link(self, response):
        shelf_categories = response.meta.get('shelf_categories')
        if not shelf_categories:
            shelf_categories = self._get_shelf_path(response)
        meta = response.meta
        meta['shelf_categories'] = shelf_categories
        total = self._scrape_total_matches(response)
        size = self._scrape_results_per_page(response)
        self.start_index += size
        if self.start_index != total and self.current_page < self.num_pages:
            self.current_page += 1
            category_id = is_empty(
                response.xpath(
                    "//div[@id='productListContainer']/@category-id").extract())
            return Request(
                self.PAGINATE_URL.format(
                    size=size,
                    start_index=self.start_index,
                    category_id=category_id),
                    meta=meta
                )
