import re
from urlparse import urlparse, parse_qs

from scrapy.http import Request
from scrapy.log import ERROR

from product_ranking.items import SiteProductItem
from product_ranking.spiders.ocado_mobile import OcadoMobileProductsSpider


class OcadoMobileShelfPagesSpider(OcadoMobileProductsSpider):
    name = 'ocado_mobile_shelf_urls_products'
    allowed_domains = ['ocado.com']

    PRODUCTS_LIMIT = 100 # There are no pagination and quantity param, need some limit
    CATALOGUE_URL = 'https://mobile.ocado.com/webservices/catalogue/browse?path=CATALOGUE{tag_id}' \
                    '&showProductLimit={limit}&productListOffset=0'

    def __init__(self, *args, **kwargs):
        self.product_url = kwargs['product_url']
        self.current_page = 1
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))
        super(OcadoMobileShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(
            url=self.AUTH_URL,
            callback=self._get_auth_id
        )

    def _scrape_product_links(self, response):
        ids = self._parse_all_items(response).extract()
        for _id in ids:
            link = self.PROD_URL.format(prod_id=_id)
            yield link, SiteProductItem()

    def _get_auth_id(self, response):
        try:
            self.auth_token = str(response.xpath('/device/token/text()').extract()[0])
            if self.auth_token:
                self.EXTRA_HEADERS.update({
                    'Authorization': self.AUTH_FORMAT.format(self.auth_token)
                })
                tag = self._parse_tag_id(self.product_url)
                if tag:
                    yield Request(
                        url=self.CATALOGUE_URL.format(
                            tag_id=tag,
                            limit=self.PRODUCTS_LIMIT
                        ),
                        meta={
                            'remaining': self.quantity,
                            'search_term': ''
                        },
                        headers=self.EXTRA_HEADERS
                    )
        except IndexError:
            self.log('Can\'t get auth_token', level=ERROR)

    @staticmethod
    def _parse_tag_id(target_url):
        query_string = urlparse(target_url).query
        if query_string:
            tags_raw = parse_qs(query_string).get('tags', [])
            if tags_raw:
                tags = re.findall(r'\|[0-9]+', tags_raw[0])
                return tags[-1] if tags else None