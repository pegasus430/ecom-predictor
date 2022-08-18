# todo:
#  reviews
#  xml file with fields


import re
import json
from urllib import quote
from scrapy import Request, FormRequest
from scrapy.log import ERROR, WARNING

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.rich_relevance_reviews_api import RichRelevanceApi
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set, \
    cond_set_value
from product_ranking.guess_brand import guess_brand_from_first_words


class HomebaseProductSpider(BaseProductsSpider):
    name = 'homebase_products'
    allowed_domains = ['homebase.co.uk', 'recs.richrelevance.com',
                       'homebase.ugc.bazaarvoice.com']
    start_urls = []

    # needed to get total results
    FIRST_URL = ('http://www.homebase.co.uk/en/homebaseuk/searchterm/'
                 '{search_term}')
    # url is the same for any request, all parameters passed via form data
    SEARCH_URL = ('http://www.homebase.co.uk/CategoryNavigationResultsView?'
                  'searchTermScope=&searchType=&filterTerm=&langId=110&'
                  'advancedSearch=&sType=SimpleSearch&metaData=&pageSize=12&'
                  'manufacturer=&filterType=&resultCatEntryType=&'
                  'catalogId=10011&searchForContent=false&categoryId=&'
                  'storeId=10201&filterFacet=')
    REVIEWS_URL = ('http://homebase.ugc.bazaarvoice.com/1494redes-en_gb/'
                   '{product_id}'
                   '/reviews.djs?format=embeddedhtml')
    RELATED_URL = ('http://recs.richrelevance.com/rrserver/p13n_generated.js?'
                   'a=04ba7209bebf8d76&'
                   'p={product_id}&'
                   'pt=%7Citem_page.recs_3%7Citem_page.recs_4%7Citem_page.recs_5&'
                   'cts=http%3A%2F%2Fwww.homebase.co.uk&l=1')
    # url to fetch value of is in store only
    IISO_URL = ('http://www.homebase.co.uk/en/homebaseuk/'
                'AjaxCheckStoreStockResults')
    RESULTS_PER_PAGE = 43
    SORT_MODES = {
        'default': '1',
        'relevance': '1',  # default
        'price_asc': '3',  # price low to high
        'price_desc': '4',  # price high to low
        'rating': '5'  # customers rating, high to low
    }
    FORM_DATA = {
        'contentBeginIndex': '0',  # always 0
        'beginIndex': '0',  # set items offset
        'isHistory': 'false',
        'pageView': '',
        'resultType': 'products',
        'orderByContent': '',
        'searchTerm': '',  # set search term
        'storeId': '10201',
        'catalogId': '10011',
        'langId': '110',
        'pageFromName': 'SearchPage',
        'pagename': 'Search successful',
        'objectId': '',
        'requesttype': 'ajax',
        'productBeginIndex': '0',  # set items offset
        'orderBy': ''  # set order type
    }
    # form data for request to get only in store value
    IISO_LOCATION = 'London'
    IISO_FORM_DATA = {
        'storeId': '10201',
        'catalogId': '10011',
        'langId': '110',
        'zipCode': IISO_LOCATION,
        'qty': '1',
        'articleNumber': '',  # replace with product id
        'requesttype': 'ajax'
    }
    # if item is out of stock, check it's only_in_store flag for this location

    def __init__(self, sort_mode=None, *args, **kwargs):
        if sort_mode not in self.SORT_MODES:
            sort_mode = 'default'
        self.SORT = self.SORT_MODES[sort_mode]
        self.pages = dict()
        self.br = BuyerReviewsBazaarApi(called_class=self)
        super(HomebaseProductSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

    def start_requests(self):
        for st in self.searchterms:
            form_data = self.FORM_DATA.copy()
            form_data['searchTerm'] = st
            form_data['orderBy'] = self.SORT
            self.pages[st] = 0
            # send request just to count number of total results
            yield Request(
                url=self.url_formatter.format(
                    self.FIRST_URL, search_term=quote(st)),
                callback=self.parse_total_and_start_search,
                meta={'form_data': form_data,
                      'search_term': st,
                      'remaining': self.quantity})
        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})

        if self.products_url:
            urls = self.products_url.split('||||')
            for url in urls:
                prod = SiteProductItem()
                prod['url'] = url
                prod['search_term'] = ''
                yield Request(url,
                              self._parse_single_product,
                              meta={'product': prod})

    def parse_total_and_start_search(self, response):
        self._scrape_total_matches(response)
        return self._scrape_next_results_page_link(response)

    def _scrape_product_links(self, response):
        items = response.css('.product_lister-product > '
                             '.product_lister-product-summary > '
                             'h4 > a::attr(href)').extract()
        for item in items:
            yield item, SiteProductItem()

    def _scrape_total_matches(self, response):
        items = response.meta.get('total_matches')
        if items is not None:
            return items
        else:
            items = response.css('#totalProcCount::attr(value)').extract()
            if not items or not items[0]:
                items = response.css('#catalog_search_result_information'
                                     '::text').re('Count:\s?(\d+)\,')
            try:
                items = int(items[0])
                response.meta['total_matches'] = items
                return items
            except (IndexError, ValueError) as e:
                self.log(str(e), WARNING)
                return 0

    def _scrape_results_per_page(self, response):
        items = response.css(
            '.product_lister-product > .product_lister-product-summary')
        per_page = len(items)
        if per_page != self.RESULTS_PER_PAGE:
            self.log('Got different results per page number', WARNING)
            self.RESULTS_PER_PAGE = per_page
        return per_page

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        st = meta['search_term']
        offset = self.pages[st] * self.RESULTS_PER_PAGE
        # check if there are no more products
        if offset >= meta.get('total_matches', 0):
            return None
        offset = str(offset)
        form_data = meta['form_data']
        form_data['beginIndex'] = offset
        form_data['productBeginIndex'] = offset
        self.pages[st] += 1
        return FormRequest(url=self.SEARCH_URL, formdata=form_data,
                           meta=meta, dont_filter=True)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _populate_from_html(self, response, prod):
        cond_set(prod, 'title',
                 response.css('.main_header[itemprop=name]::text').extract())
        # price
        currency = response.css(
            'span[itemprop=priceCurrency]::text').extract()
        price = response.css('#prodOfferPrice::attr(value)').extract()
        if currency and price:
            cond_set_value(prod, 'price', Price(price=price[0],
                                                priceCurrency=currency[0]))
        # image
        img = response.xpath(
            '/html/head/meta[@property="og:image"]/@content').extract()
        if img:
            cond_set_value(prod, 'image_url', 'http:%s' % img[0])
        # description
        cond_set(prod, 'description',
                 response.css('.product_detail-left-summary > div').extract())
        # brand
        brand = response.css('#supplier_shop img::attr(alt)').extract()
        if brand:
            brand = brand[0]
        else:
            brand = guess_brand_from_first_words(prod['title'])
        cond_set_value(prod, 'brand', brand)
        # model
        cond_set(prod, 'model',
                 response.css('span[itemprop=sku]::text').extract(),
                 unicode.strip)
        # reseller_id_regex
        reseller_id_regex = "-(\d+)$"
        reseller_id = re.findall(reseller_id_regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(prod, 'reseller_id', reseller_id)
        if not prod.get('reseller_id'):
            cond_set_value(prod, 'reseller_id', prod.get('model'))

        # out of stock
        cond_set_value(prod, 'is_out_of_stock',
                       response.css('.currently-out-of-stock'), bool)

    def parse_product(self, response):
        meta = response.meta.copy()
        prod = meta['product']
        cond_set_value(
            prod, 'locale', response.headers.get('Content-Language', 'en-GB'))
        self._populate_from_html(response, prod)
        return Request(
            self.url_formatter.format(
                self.RELATED_URL,
                product_id=prod['model']),
            callback=self.parse_related,
            meta=meta)

    def parse_related(self, response):
        """parse response from richrelevance api"""
        meta = response.meta.copy()
        prod = meta['product']
        rr = RichRelevanceApi(response, prod, 'http://www.homebase.co.uk')
        rr.parse_related_products()
        # if product is out of stock, check it's availability in store
        if prod['is_out_of_stock']:
            form_data = self.IISO_FORM_DATA.copy()
            form_data['articleNumber'] = prod['model']
            return FormRequest(
                self.IISO_URL, formdata=form_data,
                callback=self.parse_iiso, meta=meta, dont_filter=True)
        else:
            return Request(
                self.url_formatter.format(
                    self.REVIEWS_URL, product_id=prod['model']),
                callback=self.br.parse_buyer_reviews,
                meta=meta)

    def parse_iiso(self, response):
        """parse only in store value"""
        meta = response.meta.copy()
        prod = meta['product']
        js_data = json.loads(
            re.search('/\*(.+)\*/', response.body.replace('\n', '')).group(1))
        first_store = js_data.get('firstStore', {})
        ois = bool(first_store.get('stockAvl', 0))
        cond_set_value(prod, 'is_in_store_only', ois)
        return Request(
            self.url_formatter.format(
                self.REVIEWS_URL, product_id=prod['model']),
            callback=self.br.parse_buyer_reviews,
            meta=meta)
