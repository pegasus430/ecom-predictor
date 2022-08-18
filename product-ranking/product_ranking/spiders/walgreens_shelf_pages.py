import copy
import json
import re
import urlparse

from scrapy.http import FormRequest

from product_ranking.items import SiteProductItem

from .walgreens import WalGreensProductsSpider


class WalgreensShelfPagesSpider(WalGreensProductsSpider):
    name = 'walgreens_shelf_urls_products'
    allowed_domains = ["walgreens.com", "api.bazaarvoice.com"]  # without this find_spiders() fails

    AJAX_PRODUCT_LINKS_URL = "http://www.walgreens.com/svc/products/search"

    JSON_SEARCH_STRUCT = {"p": "1", "s": "24", "sort": "Top Sellers", "view": "allView",
                          "geoTargetEnabled": 'false', "id": "[{page_id}]", "requestType": "tier3",
                          "deviceType": "desktop",}

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}.copy()

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))

        self.user_agent = "Mozilla/5.0 (X11; Linux i686 (x86_64))" \
            " AppleWebKit/537.36 (KHTML, like Gecko)" \
            " Chrome/37.0.2062.120 Safari/537.36"
        super(WalgreensShelfPagesSpider, self).__init__(*args, **kwargs)

    @staticmethod
    def _get_page_id(url):
        _id = re.search(r'N=([\d\-]+)', url)
        if not _id:
            _id = re.search(r'ID=([\d\-]+)', url)
        if _id:
            return _id.group(1).replace('-', ',')

    def start_requests(self):
        self.page_id = self._get_page_id(self.product_url)

        json_struct = copy.deepcopy(self.JSON_SEARCH_STRUCT)
        json_struct['id'] = json_struct['id'].format(page_id=self.page_id)

        yield FormRequest(self.AJAX_PRODUCT_LINKS_URL,
                          meta=self._setup_meta_compatibility(),
                          formdata=json_struct)

    def _scrape_product_links(self, response):
        for j_product in json.loads(response.body).get('products', []):
            j_url = j_product.get('productInfo', {}).get('productURL', '')
            if j_url.startswith('/'):
                j_url = urlparse.urljoin(response.url, j_url)
            yield j_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        # TODO fix pagination properly
        return
        if self.current_page >= self.num_pages:
            return
        self.current_page += 1

        json_struct = copy.deepcopy(self.JSON_SEARCH_STRUCT)
        json_struct['id'] = json_struct['id'].format(page_id=self.page_id)
        json_struct['p'] = str(self.current_page)

        return FormRequest(self.AJAX_PRODUCT_LINKS_URL,
                          meta=self._setup_meta_compatibility(),
                          formdata=json_struct)
