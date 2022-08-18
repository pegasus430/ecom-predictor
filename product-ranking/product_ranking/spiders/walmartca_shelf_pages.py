import re
import urlparse

from scrapy.http import Request

from product_ranking.items import SiteProductItem

from .walmartca import WalmartCaProductsSpider


class WalmartCaShelfPagesSpider(WalmartCaProductsSpider):
    name = 'walmartca_shelf_urls_products'
    allowed_domains = ["walmart.com", "walmart.ca",
                       "msn.com", 'api.walmartlabs.com',
                       'api.bazaarvoice.com', 'recs.richrelevance.com']  # without this find_spiders() fails

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
        self._setup_class_compatibility()

        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))

        super(WalmartCaShelfPagesSpider, self).__init__(*args, **kwargs)

        self.user_agent = "Mozilla/5.0 (X11; Linux i686 (x86_64))" \
            " AppleWebKit/537.36 (KHTML, like Gecko)" \
            " Chrome/37.0.2062.120 Safari/537.36"

        # variants are switched off by default, see Bugzilla 3982#c11
        self.scrape_variants_with_extra_requests = False
        if 'scrape_variants_with_extra_requests' in kwargs:
            scrape_variants_with_extra_requests = kwargs['scrape_variants_with_extra_requests']
            if scrape_variants_with_extra_requests in (1, '1', 'true', 'True', True):
                self.scrape_variants_with_extra_requests = True

    @staticmethod
    def valid_url(url):
        if not re.findall("http(s){0,1}\:\/\/", url):
            url = "http://" + url
        return url

    def start_requests(self):
        yield Request(url=self.valid_url(self.product_url),
                      meta=self._setup_meta_compatibility(),
                      callback=self.set_cookie)  # meta is for SC baseclass compatibility

