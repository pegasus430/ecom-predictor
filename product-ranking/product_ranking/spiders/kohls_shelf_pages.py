import re

from scrapy.http import Request

from product_ranking.items import SiteProductItem
from product_ranking.utils import valid_url

from .kohls import KohlsProductsSpider


class KohlsShelfPagesSpider(KohlsProductsSpider):
    name = 'kohls_shelf_urls_products'

    def _setup_class_compatibility(self):
        """ Needed to maintain compatibility with the SC spiders baseclass """
        self.quantity = 99999
        self.site_name = self.allowed_domains[0]
        self.user_agent_key = None
        self.zip_code = '12345'
        self.current_page = 1

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': 99999, 'search_term': ''}.copy()

    def __init__(self, *args, **kwargs):
        super(KohlsShelfPagesSpider, self).__init__(*args, **kwargs)
        self._setup_class_compatibility()
        self.product_url = kwargs['product_url']

        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1

        self.user_agent = "Mozilla/5.0 (X11; Linux i686 (x86_64))" \
            " AppleWebKit/537.36 (KHTML, like Gecko)" \
            " Chrome/37.0.2062.120 Safari/537.36"

        # variants are switched off by default, see Bugzilla 3982#c11
        self.scrape_variants_with_extra_requests = False
        if 'scrape_variants_with_extra_requests' in kwargs:
            scrape_variants_with_extra_requests = kwargs['scrape_variants_with_extra_requests']
            if scrape_variants_with_extra_requests in (1, '1', 'true', 'True', True):
                self.scrape_variants_with_extra_requests = True

    def start_requests(self):
        yield Request(url=valid_url(self.product_url),
                      meta=self._setup_meta_compatibility())

    def _scrape_product_links(self, response):
        prod_urls = response.xpath('//*[contains(@id, "content")]'
                                   '//noscript//a[contains(@href, "prd-")]/img/../@href').extract()
        if not prod_urls:
            prod_urls = re.findall(
                r'prodSeoURL[\"\']\s?:\s?[\"\']([^\.]+?\.jsp)',
                # r'"prodSeoURL"\s?:\s+\"(.+)\"',
                response.body_as_unicode()
            )

        urls = ['https://www.kohls.com' + i for i in prod_urls]
        breadcrumb = response.xpath('//title/text()').extract()

        shelf_categories = breadcrumb[0].split()[:-2]
        shelf_categories = [i for i in reversed(shelf_categories)]
        shelf_category = shelf_categories[-1] if shelf_categories else None

        for url in urls:
            item = SiteProductItem()
            if shelf_category:
                item['shelf_name'] = shelf_category
            if shelf_categories:
                item['shelf_path'] = shelf_categories
            yield url, item

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1
        return super(KohlsShelfPagesSpider,
                     self)._scrape_next_results_page_link(response)

    def parse_product(self, response):
        return super(KohlsShelfPagesSpider, self).parse_product(response)
