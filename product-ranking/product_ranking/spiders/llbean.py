# coding=utf-8
from __future__ import division, absolute_import, unicode_literals

import re
import json
import urllib
import traceback
from urlparse import urljoin

from scrapy import Request
from scrapy.log import ERROR, INFO, WARNING

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults, \
    cond_set_value
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.utils import is_empty

data_re = re.compile('pdpJson = (.*);\r\n')
url_re = re.compile('(\d+).html')


class LLBeanProductsSpider(BaseProductsSpider):
    name = 'llbean_products'
    allowed_domains = ["llbean.com"]
    start_urls = []

    SEARCH_URL = "http://www.llbean.com/llb/gnajax/2?storeId=1&catalogId=1" \
                 "&langId=-1&position={pagenum}&sort_field={search_sort}&freeText={search_term}"

    URL = "http://www.llbean.com"
    OLD_URL_TEMPLATE = 'https://www.llbean.com/webapp/wcs/stores/servlet/' \
        'GuidednavDisplay?categoryId={}&storeId=1&catalogId=1&langId=-1'

    SEARCH_SORT = {
        'best_match': 'Relevance',
        'high_price': 'Price (Descending)',
        'low_price': 'Price (Ascending)',
        'best_sellers': 'Num_Of_Orders',
        'avg_review': 'Grade (Descending)',
        'product_az': 'Name (Ascending)',
    }

    image_url = "http://cdni.llbean.com/is/image/wim/"

    def __init__(self, search_sort='best_match', *args, **kwargs):
        if 'product_url' in kwargs:
            # convert new url to old
            product_id = url_re.search(kwargs['product_url'])
            product_url = self.OLD_URL_TEMPLATE.format(product_id.group(1))
            kwargs['product_url'] = product_url

        super(LLBeanProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(pagenum=1,
                                                search_sort=self.SEARCH_SORT[
                                                    search_sort]
            ),
            *args,
            **kwargs)

    def parse_product(self, response):
        product = response.meta['product']
        json_found = data_re.search(response.body)
        if json_found:
            body = json_found.group(1)
        else:
            self.log('Cannot found JSON', ERROR)
            return
        try:
            js = json.loads(body)
        except ValueError:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), ERROR)
            return

        title = js.get('name')
        if title:
            cond_set_value(product, 'title', title)
            brand = guess_brand_from_first_words(title)
            if brand:
                cond_set_value(product, 'brand', brand)

        desc = js.get('desc') or js.get('sellingDesc')
        cond_set_value(product, 'description', desc)

        try:
            reseller_id = js.get('catalog_id', '') + js['items'][0]['itemId']
            cond_set_value(product, 'reseller_id', reseller_id)

            price = js['items'][0]['prices'][-1]['price']
            cond_set_value(product, 'price', Price(price=price, priceCurrency="USD"))

            image_url = js['imageData']['path'] + js['imageData']['images'][0]['id']
            cond_set_value(product, 'image_url', image_url)
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), ERROR)

        self._populate_buyer_reviews(response)

        return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        data = json.loads(response.body_as_unicode())
        response.meta['position'] = {}
        response.meta['position'] = data[0]['productsPerPage']
        return data[0]['pageFoundSize']

    def _scrape_product_links(self, response):
        data = json.loads(response.body_as_unicode())
        for item in data[0]['products']:
            prod = SiteProductItem()
            prod['title'] = item['name']

            brand = item.get('brand')
            if brand and brand != '0':
                cond_set_value(prod, 'brand', brand)

            prod['upc'] = item['item'][0]['prodId']
            prod['image_url'] = self.image_url + item['img']
            cond_set_value(prod, 'is_out_of_stock',
                           item['item'][0]['stock'] != "IN")
            prod['locale'] = "en-US"
            url = urljoin(response.url, item['displayUrl'])
            yield url, prod

    def _scrape_next_results_page_link(self, response):
        data = json.loads(response.body_as_unicode())
        if response.meta['position'] == 48:
            pos = 49
            response.meta['position'] = pos
        else:
            pos = response.meta['position'] + data[0]['productsPerPage']
            response.meta['position'] = pos
        max_pages = data[0]['pageFoundSize']
        cur_page = pos
        if cur_page >= max_pages:
            return None

        st = urllib.quote(data[0]['originalSearchTerm'])
        return self.url_formatter.format(self.SEARCH_URL,
                                         search_term=st,
                                         pagenum=cur_page)

    def _populate_buyer_reviews(self, response):
        product = response.meta['product']
        total = int((response.css('.PPNumber::text').extract() or ['0'])[0])
        if not total:
            return
        avg = response.css('[itemprop=ratingValue]::attr(content)').extract()
        avg = float(avg[0])
        by_star = {int(div.css('.PPHistStarLabelText::text').re('\d+')[0]):
                       int(div.css('.PPHistAbsLabel::text').re('\d+')[0])
                   for div in response.css('.PPHistogramBarRow')}
        cond_set_value(product, 'buyer_reviews',
                       BuyerReviews(num_of_reviews=total,
                                    average_rating=avg,
                                    rating_by_star=by_star))


